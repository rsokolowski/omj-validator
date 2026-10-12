"""Automatic failover Gemini -> Claude: when, when never, breaker, gate, meta, alerts."""

import asyncio

import pytest

from app.ai import factory, failover
from app.ai.config_store import ActiveModel
from app.ai.factory import AIContentBlockedError, AIProviderError, AIUnavailableError
from app.ai.failover import FailoverProvider, breaker
from app.config import settings
from app.models import PrivateTaskMeta, SubmissionResult


class FakeProvider:
    """Scripted provider: each call pops the next outcome (exception or value)."""

    def __init__(self, provider, model):
        self.provider_name, self.model_name = provider, model
        self.outcomes: list = []
        self.calls: list[str] = []

    def get_timeout(self):
        return 90

    async def _next(self, method, default):
        self.calls.append(method)
        outcome = self.outcomes.pop(0) if self.outcomes else default
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def generate_private_task_meta(self, title, content):
        return await self._next(
            "meta", PrivateTaskMeta(hints=["h"], checked=True, meta={"provider": self.provider_name, "model": self.model_name})
        )

    async def analyze_solution_stream(self, *args, on_thinking=None, **kwargs):
        if on_thinking:
            await on_thinking(f"**{self.provider_name}**")
        return await self._next(
            "grade",
            SubmissionResult(score=6, feedback="ok", scoring_meta={"provider": self.provider_name, "model": self.model_name}),
        )


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    factory.reset_provider_cache()
    breaker.reset()
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    monkeypatch.setattr(settings, "anthropic_api_key", "a-key")
    monkeypatch.setattr(settings, "anthropic_processor_approved", True)
    monkeypatch.setattr(settings, "ai_failover_enabled", True)
    monkeypatch.setattr(settings, "ai_failover_model", "claude-opus-5-5")
    monkeypatch.setattr(settings, "ai_failover_breaker_minutes", 15)
    monkeypatch.setattr(settings, "ai_failover_breaker_threshold", 3)
    monkeypatch.setattr(factory, "_construct", lambda provider, model: FakeProvider(provider, model))
    monkeypatch.setattr(factory, "get_active_model", lambda: ActiveModel("gemini", "gemini-3.8-flash", "env"))
    yield
    factory.reset_provider_cache()
    breaker.reset()


@pytest.fixture
def alerts(monkeypatch):
    sent = []

    async def capture(text):
        sent.append(text)

    monkeypatch.setattr("app.notifications.send_telegram_message", capture)
    return sent


def pair():
    """(wrapper, primary fake, backup fake)."""
    wrapper = factory.create_ai_provider()
    assert isinstance(wrapper, FailoverProvider)
    return wrapper, wrapper.primary, factory._cached_provider("anthropic", "claude-opus-5-5")


def unavailable(kind="server", status=503):
    return AIUnavailableError("Przepraszamy, coś poszło nie tak.", kind=kind, status=status)


async def drain():
    """Let fire-and-forget alert tasks run."""
    await asyncio.sleep(0)
    await asyncio.sleep(0)


# ------------------------------------------------------------ when it applies


def test_wrapped_when_backup_usable():
    wrapper = factory.create_ai_provider()
    assert isinstance(wrapper, FailoverProvider)
    assert (wrapper.provider_name, wrapper.model_name) == ("gemini", "gemini-3.8-flash")
    assert wrapper.fallback_key == ("anthropic", "claude-opus-5-5")
    assert factory.create_ai_provider() is wrapper  # cached


@pytest.mark.parametrize(
    "setting, value, reason",
    [
        ("anthropic_processor_approved", False, factory.REASON_NOT_APPROVED),  # GDPR gate closed
        ("anthropic_api_key", None, factory.REASON_NO_KEY),
        ("ai_failover_enabled", False, factory.FAILOVER_OFF),
        ("ai_failover_model", "claude-unknown", factory.FAILOVER_UNKNOWN_MODEL),
        ("ai_failover_model", "gemini-3.1-pro-preview", factory.FAILOVER_SAME_PROVIDER),
    ],
)
def test_plain_provider_when_failover_cannot_apply(monkeypatch, setting, value, reason):
    monkeypatch.setattr(settings, setting, value)
    provider = factory.create_ai_provider()
    assert not isinstance(provider, FailoverProvider)
    assert provider.provider_name == "gemini"
    status = factory.failover_status(ActiveModel("gemini", "gemini-3.8-flash", "env"))
    assert status["active"] is False
    assert status["inactive_reason"] == reason


def test_gate_closed_behaves_exactly_as_before(monkeypatch):
    """No backup reachable: the primary's error reaches the caller untouched."""
    monkeypatch.setattr(settings, "anthropic_processor_approved", False)
    provider = factory.create_ai_provider()
    provider.outcomes.append(unavailable("auth", 403))
    with pytest.raises(AIUnavailableError):
        asyncio.run(provider.generate_private_task_meta("T", "C"))
    assert ("anthropic", "claude-opus-5-5") not in factory._instances


def test_claude_primary_is_not_wrapped_with_a_claude_backup(monkeypatch):
    monkeypatch.setattr(factory, "get_active_model", lambda: ActiveModel("anthropic", "claude-sonnet-5-5", "db"))
    assert not isinstance(factory.create_ai_provider(), FailoverProvider)


def test_backup_is_never_built_while_the_primary_works():
    wrapper, primary, _ = pair()
    factory._instances.pop(("anthropic", "claude-opus-5-5"))
    asyncio.run(wrapper.generate_private_task_meta("T", "C"))
    assert ("anthropic", "claude-opus-5-5") not in factory._instances


# ---------------------------------------------------------- what fails over


@pytest.mark.parametrize("kind, status", [
    ("auth", 401), ("auth", 403), ("not_found", 404), ("rate_limit", 429),
    ("server", 503), ("network", None), ("timeout", None),
])
def test_availability_errors_fail_over(kind, status, alerts):
    wrapper, primary, backup = pair()
    primary.outcomes.append(unavailable(kind, status))

    async def run():
        result = await wrapper.generate_private_task_meta("T", "C")
        await drain()
        return result

    result = asyncio.run(run())

    assert primary.calls == ["meta"] and backup.calls == ["meta"]
    assert result.meta["provider"] == "anthropic"
    assert result.meta["model"] == "claude-opus-5-5"
    assert result.meta["failover"] == {"from": "gemini/gemini-3.8-flash", "reason": kind}
    assert len(alerts) == 1 and "AI failover" in alerts[0]


@pytest.mark.parametrize(
    "error",
    [
        AIContentBlockedError("Nie udało się przetworzyć tej treści."),  # safety filter
        AIProviderError("Nie udało się odczytać odpowiedzi."),  # unreadable answer of a working call
        ValueError("parser crashed"),
    ],
)
def test_content_and_parse_errors_never_fail_over(error):
    wrapper, primary, backup = pair()
    primary.outcomes.append(error)
    with pytest.raises(type(error)):
        asyncio.run(wrapper.generate_private_task_meta("T", "C"))
    assert backup.calls == []
    assert breaker.state(("gemini", "gemini-3.8-flash"))["consecutive_failures"] == 0


def test_abuse_verdict_is_returned_not_retried():
    """A high abuse_score is a successful answer: the caller refuses it, the backup is not asked."""
    wrapper, primary, backup = pair()
    primary.outcomes.append(PrivateTaskMeta(hints=["h"], abuse_score=99, checked=True))
    result = asyncio.run(wrapper.generate_private_task_meta("T", "C"))
    assert result.abuse_score == 99
    assert backup.calls == []


def test_at_most_one_failover():
    wrapper, primary, backup = pair()
    primary.outcomes.append(unavailable())
    backup.outcomes.append(unavailable("rate_limit", 429))
    with pytest.raises(AIUnavailableError) as info:
        asyncio.run(wrapper.generate_private_task_meta("T", "C"))
    assert info.value.kind == "rate_limit"
    assert primary.calls == ["meta"] and backup.calls == ["meta"]


def test_backup_content_block_propagates():
    wrapper, primary, backup = pair()
    primary.outcomes.append(unavailable())
    backup.outcomes.append(AIContentBlockedError("blocked"))
    with pytest.raises(AIContentBlockedError):
        asyncio.run(wrapper.generate_private_task_meta("T", "C"))


def test_unbuildable_backup_reraises_the_primary_error(monkeypatch):
    wrapper, primary, _ = pair()
    factory._instances.pop(("anthropic", "claude-opus-5-5"))

    def broken(provider, model):
        if provider == "anthropic":
            raise ImportError("anthropic SDK missing")
        return FakeProvider(provider, model)

    monkeypatch.setattr(factory, "_construct", broken)
    original = unavailable("auth", 401)
    primary.outcomes.append(original)
    with pytest.raises(AIUnavailableError) as info:
        asyncio.run(wrapper.generate_private_task_meta("T", "C"))
    assert info.value is original


# ------------------------------------------------------------------ breaker


def test_permanent_error_opens_the_breaker_at_once(alerts):
    wrapper, primary, backup = pair()
    primary.outcomes.append(unavailable("auth", 403))

    async def run():
        for _ in range(3):
            await wrapper.generate_private_task_meta("T", "C")
        await drain()

    asyncio.run(run())

    assert primary.calls == ["meta"]  # later calls go straight to the backup
    assert backup.calls == ["meta"] * 3
    state = breaker.state(("gemini", "gemini-3.8-flash"))
    assert state["state"] == "open" and state["last_error"] == "auth 403"
    assert len(alerts) == 1  # one alert per opening, not per call
    assert "for 15 min" in alerts[0]


def test_breaker_open_result_is_marked():
    wrapper, primary, backup = pair()
    primary.outcomes.append(unavailable("not_found", 404))
    asyncio.run(wrapper.generate_private_task_meta("T", "C"))
    result = asyncio.run(wrapper.generate_private_task_meta("T", "C"))
    assert result.meta["failover"]["reason"] == "breaker_open"


def test_transient_errors_open_after_threshold():
    wrapper, primary, backup = pair()
    primary.outcomes.extend([unavailable(), unavailable(), unavailable()])

    async def run():
        for _ in range(4):
            await wrapper.generate_private_task_meta("T", "C")

    asyncio.run(run())

    assert primary.calls == ["meta"] * 3  # third failure opened it; the fourth call skipped the primary
    assert backup.calls == ["meta"] * 4
    assert breaker.is_open(("gemini", "gemini-3.8-flash"))


def test_success_resets_the_failure_count():
    wrapper, primary, _ = pair()
    primary.outcomes.extend([unavailable(), unavailable(), PrivateTaskMeta(checked=True), unavailable()])

    async def run():
        for _ in range(4):
            await wrapper.generate_private_task_meta("T", "C")

    asyncio.run(run())
    assert not breaker.is_open(("gemini", "gemini-3.8-flash"))
    assert breaker.state(("gemini", "gemini-3.8-flash"))["consecutive_failures"] == 1


def test_breaker_half_opens_after_the_period(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(failover.time, "monotonic", lambda: clock["now"])
    wrapper, primary, backup = pair()
    primary.outcomes.append(unavailable("auth", 401))
    asyncio.run(wrapper.generate_private_task_meta("T", "C"))
    assert breaker.is_open(("gemini", "gemini-3.8-flash"))

    clock["now"] += 15 * 60 + 1
    asyncio.run(wrapper.generate_private_task_meta("T", "C"))  # primary tried again, works
    assert primary.calls == ["meta", "meta"]
    assert breaker.state(("gemini", "gemini-3.8-flash"))["state"] == "closed"


# --------------------------------------------------------------- streaming


def test_stream_failover_restarts_cleanly():
    wrapper, primary, backup = pair()
    primary.outcomes.append(unavailable("timeout", None))
    seen: list[str] = []
    restarts: list[int] = []

    async def on_thinking(text):
        seen.append(text)

    async def on_restart():
        restarts.append(len(seen))
        seen.clear()

    async def run():
        token = failover.restart_hook.set(on_restart)
        try:
            return await wrapper.analyze_solution_stream("t.pdf", None, [], 1, on_thinking=on_thinking)
        finally:
            failover.restart_hook.reset(token)

    result = asyncio.run(run())

    assert restarts == [1]  # the primary had streamed one chunk before failing
    assert seen == ["**anthropic**"]
    assert result.scoring_meta["provider"] == "anthropic"
    assert result.scoring_meta["failover"] == {"from": "gemini/gemini-3.8-flash", "reason": "timeout"}


def test_no_restart_without_failover():
    wrapper, _, _ = pair()
    calls = []

    async def on_restart():
        calls.append(1)

    async def run():
        failover.restart_hook.set(on_restart)
        return await wrapper.analyze_solution_stream("t.pdf", None, [], 1)

    asyncio.run(run())
    assert calls == []


# ------------------------------------------------------------------ status


def test_failover_status_for_admin():
    status = factory.failover_status(ActiveModel("gemini", "gemini-3.8-flash", "env"))
    assert status["enabled"] is True
    assert status["active"] is True
    assert status["gate_open"] is True
    assert (status["provider"], status["model"], status["model_label"]) == (
        "anthropic", "claude-opus-5-5", "Claude Opus 5.5",
    )
    assert status["breaker"] == {
        "state": "closed", "open_until": None, "consecutive_failures": 0, "last_error": None,
    }
