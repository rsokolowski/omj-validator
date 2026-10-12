"""create_ai_provider follows the persisted active model."""

import pytest

from app.ai import config_store, factory
from app.ai.config_store import ActiveModel
from app.ai.factory import AIProviderError
from app.config import settings


class FakeProvider:
    def __init__(self, provider, model):
        self.provider_name, self.model_name = provider, model


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    factory.reset_provider_cache()
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    monkeypatch.setattr(settings, "anthropic_api_key", "a-key")
    monkeypatch.setattr(settings, "anthropic_processor_approved", True)
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")
    monkeypatch.setattr(factory, "_construct", lambda provider, model: FakeProvider(provider, model))
    yield
    factory.reset_provider_cache()


def use(monkeypatch, provider, model):
    monkeypatch.setattr(factory, "get_active_model", lambda: ActiveModel(provider, model, "db"))


def test_one_instance_per_pair(monkeypatch):
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    first = factory.create_ai_provider()
    assert factory.create_ai_provider() is first
    use(monkeypatch, "anthropic", "claude-sonnet-5-5")
    second = factory.create_ai_provider()
    assert second is not first and second.model_name == "claude-sonnet-5-5"


def test_missing_key_raises_in_build(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    with pytest.raises(AIProviderError):
        factory.build_provider("anthropic", "claude-opus-5-5")


def test_unapproved_anthropic_falls_back_to_env_gemini(monkeypatch, caplog):
    monkeypatch.setattr(settings, "anthropic_processor_approved", False)
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    provider = factory.create_ai_provider()
    assert (provider.provider_name, provider.model_name) == ("gemini", "gemini-3.8-flash")
    assert "dostawca niezatwierdzony (RODO)" in caplog.text


def test_active_provider_without_key_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    assert factory.create_ai_provider().provider_name == "gemini"


def test_env_provider_without_key_still_raises(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    use(monkeypatch, "gemini", "gemini-3.8-flash")
    with pytest.raises(AIProviderError):
        factory.create_ai_provider()


def test_unknown_provider_raises():
    with pytest.raises(AIProviderError):
        factory.build_provider("openai", "gpt")


def test_env_ai_provider_anthropic_is_ignored(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(config_store, "_env_provider_warned", False)
    monkeypatch.setattr(factory, "get_active_model", config_store.env_default)
    provider = factory.create_ai_provider()
    assert (provider.provider_name, provider.model_name) == ("gemini", "gemini-3.8-flash")
    assert "AI_PROVIDER=anthropic is ignored" in caplog.text


def test_unapproved_anthropic_row_never_constructs_anthropic(monkeypatch):
    built = []

    def record(provider, model):
        built.append(provider)
        return FakeProvider(provider, model)

    monkeypatch.setattr(factory, "_construct", record)
    monkeypatch.setattr(settings, "anthropic_processor_approved", False)
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    factory.create_ai_provider()
    factory.create_ai_provider()
    assert "anthropic" not in built and built == ["gemini"]


def test_resolve_active_reports_effective_model_and_reason(monkeypatch):
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    effective, reason = factory.resolve_active()
    assert (effective.provider, effective.model, reason) == ("anthropic", "claude-opus-5-5", None)

    monkeypatch.setattr(settings, "anthropic_processor_approved", False)
    effective, reason = factory.resolve_active()
    assert (effective.provider, effective.model, effective.source) == ("gemini", "gemini-3.8-flash", "env")
    assert reason == "dostawca niezatwierdzony (RODO)"

    monkeypatch.setattr(settings, "anthropic_api_key", None)
    assert factory.resolve_active()[1] == "brak klucza API"


def test_create_ai_provider_builds_what_resolve_active_returns(monkeypatch):
    """One resolution for grading and the admin page: the factory follows resolve_active."""
    monkeypatch.setattr(
        factory, "resolve_active", lambda: (ActiveModel("anthropic", "claude-haiku-5-5", "db"), None)
    )
    provider = factory.create_ai_provider()
    assert (provider.provider_name, provider.model_name) == ("anthropic", "claude-haiku-5-5")


def test_unusable_stored_choice_is_logged_once_per_reason(monkeypatch, caplog):
    monkeypatch.setattr(settings, "anthropic_processor_approved", False)
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    for _ in range(3):
        factory.create_ai_provider()
    assert caplog.text.count("is not usable") == 1

    monkeypatch.setattr(settings, "anthropic_api_key", None)  # a different reason is logged again
    factory.create_ai_provider()
    assert caplog.text.count("is not usable") == 2


def test_remember_seeds_the_cache(monkeypatch):
    use(monkeypatch, "anthropic", "claude-sonnet-5-5")
    pinged = FakeProvider("anthropic", "claude-sonnet-5-5")
    factory.remember("anthropic", "claude-sonnet-5-5", pinged)
    provider = factory.create_ai_provider()
    # Wrapped for failover (env Gemini backs up a Claude primary) around the pinged instance
    assert getattr(provider, "primary", provider) is pinged
