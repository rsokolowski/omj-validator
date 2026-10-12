"""AnthropicProvider request shape, stream handling, errors and image limits.

Every test swaps the SDK client for a fake that records the request kwargs and
returns canned SimpleNamespace objects - no network. Inputs are invented
strings, never real OMJ task statements.
"""

import asyncio
import base64
import copy
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from PIL import Image

from app.ai import requests as ai_requests
from app.ai.factory import AIContentBlockedError, AIProviderError
from app.ai.models_catalog import estimate_cost
from app.ai.pattern_parsing import PATTERN_LINK_SCHEMA
from app.ai.private_parsing import META_SCHEMA
from app.ai.prompt_builder import CLOSING_LINE, build_prompt, solution_text_block
from app.ai.providers import anthropic as anthropic_module
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.schemas import RESPONSE_JSON_SCHEMA
from app.config import settings

TASK_PDF = Path(__file__).parent / "fixtures" / "task_corpus" / "tasks" / "1999" / "etap1" / "zadania.pdf"
GRADE_JSON = '{"score": 5, "feedback": "Dobrze.", "issue_type": "none", "abuse_score": 0}'


# --------------------------------------------------------------- fakes


def usage(**overrides):
    base = dict(input_tokens=1000, output_tokens=200, cache_read_input_tokens=300, cache_creation_input_tokens=400)
    base.update(overrides)
    return SimpleNamespace(**base)


def message(text=GRADE_JSON, stop_reason="end_turn", model="claude-opus-5-5", thinking="", **extra):
    content = []
    if thinking:
        content.append(SimpleNamespace(type="thinking", thinking=thinking))
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, stop_details=None, model=model, usage=usage(), **extra
    )


def delta(kind, value):
    field = "thinking" if kind == "thinking_delta" else "text"
    return SimpleNamespace(type="content_block_delta", index=0, delta=SimpleNamespace(type=kind, **{field: value}))


class FakeStream:
    def __init__(self, events, final, error=None, delay=0.0):
        self._events, self._final, self._error, self._delay = events, final, error, delay
        self.request_id = "req_stream"

    async def __aenter__(self):
        if self._error is not None:
            raise self._error
        if self._delay:
            await asyncio.sleep(self._delay)
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        async def gen():
            for event in self._events:
                yield event

        return gen()

    async def get_final_message(self):
        return self._final


class FakeMessages:
    """client.messages / client.beta.messages; records (path, kwargs)."""

    def __init__(self, path, log, script):
        self._path, self._log, self._script = path, log, script

    def stream(self, **kwargs):
        self._log.append((self._path, "stream", kwargs))
        return FakeStream(
            self._script.get("events", []),
            self._script.get("final", message()),
            self._script.get("error"),
            self._script.get("delay", 0.0),
        )

    async def create(self, **kwargs):
        self._log.append((self._path, "create", kwargs))
        if self._script.get("error") is not None:
            raise self._script["error"]
        return self._script.get("final", message())


def fake_client(log, **script):
    return SimpleNamespace(
        messages=FakeMessages("messages", log, script),
        beta=SimpleNamespace(messages=FakeMessages("beta", log, script)),
    )


@pytest.fixture
def make_provider(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test-not-a-key")
    monkeypatch.setattr(settings, "anthropic_effort", "high")
    monkeypatch.setattr(settings, "anthropic_effort_aux", "medium")

    def make(model="claude-opus-5-5", **script):
        log: list = []
        p = AnthropicProvider(model)
        p._client = fake_client(log, **script)
        return p, log

    return make


def png(path: Path, size=(40, 30), color=(200, 10, 10)) -> Path:
    Image.new("RGB", size, color).save(path)  # format follows the suffix
    return path


def blocks_of(kwargs) -> list:
    [msg] = kwargs["messages"]
    assert msg["role"] == "user"
    return msg["content"]


def walk_objects(schema):
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            yield schema
        for value in schema.values():
            yield from walk_objects(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from walk_objects(value)


# ------------------------------------------------------------ OMJ grading


def test_omj_stream_request_shape_opus(make_provider, tmp_path):
    p, log = make_provider("claude-opus-5-5")
    photos = [png(tmp_path / "a.png"), png(tmp_path / "b.png")]

    asyncio.run(p.analyze_solution_stream(TASK_PDF, TASK_PDF, photos, 3, etap="etap2", solution_text="moje $a$"))

    [(path, kind, kwargs)] = log
    assert (path, kind) == ("beta", "stream")
    blocks = blocks_of(kwargs)
    assert [b["type"] for b in blocks] == ["text", "document", "document", "image", "image", "text", "text"]
    assert blocks[0]["text"] == ai_requests.omj_grading_text(build_prompt("etap2"), 3, True, 2, True)
    assert blocks[5]["text"] == solution_text_block("moje $a$")
    assert blocks[6]["text"] == CLOSING_LINE
    assert blocks[1]["source"]["media_type"] == "application/pdf"
    assert base64.standard_b64decode(blocks[1]["source"]["data"]) == TASK_PDF.read_bytes()
    # No prompt-cache breakpoint (per-task text leads the prefix; misses cost 1.25x)
    assert not any("cache_control" in b for b in blocks)
    assert blocks[3]["source"]["media_type"] == "image/png"
    # Small photos within the limits are sent byte for byte
    assert base64.standard_b64decode(blocks[3]["source"]["data"]) == photos[0].read_bytes()

    assert kwargs["model"] == "claude-opus-5-5"
    assert kwargs["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert kwargs["output_config"]["effort"] == "high"
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert kwargs["fallbacks"] == "default"
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert "system" not in kwargs


def test_omj_stream_haiku_has_no_fallbacks_and_no_cache_control(make_provider):
    p, log = make_provider("claude-haiku-5-5", final=message(model="claude-haiku-5-5"))

    asyncio.run(p.analyze_solution_stream(TASK_PDF, None, [], 2, etap="etap1", solution_text="x"))

    [(path, kind, kwargs)] = log
    assert (path, kind) == ("messages", "stream")
    assert "fallbacks" not in kwargs and "betas" not in kwargs
    blocks = blocks_of(kwargs)
    assert [b["type"] for b in blocks] == ["text", "document", "text", "text"]
    assert not any("cache_control" in b for b in blocks)
    assert blocks[0]["text"] == ai_requests.omj_grading_text(build_prompt("etap1"), 2, False, 0, True)


def test_omj_stream_thinking_reaches_callbacks_and_meta(make_provider):
    events = [
        SimpleNamespace(type="message_start"),
        delta("thinking_delta", "Najpierw "),
        SimpleNamespace(type="thinking", thinking="Najpierw "),  # SDK helper event - ignored
        delta("thinking_delta", "sprawdzam."),
        delta("text_delta", GRADE_JSON[:10]),
        delta("text_delta", GRADE_JSON[10:]),
    ]
    p, _ = make_provider(events=events, final=message(thinking="Najpierw sprawdzam."))
    thoughts, feedback, order = [], [], []

    async def on_thinking(chunk):
        thoughts.append(chunk)

    async def on_upload_complete():
        order.append("upload")

    def on_feedback(chunk):  # sync callbacks are accepted too
        feedback.append(chunk)

    result = asyncio.run(
        p.analyze_solution_stream(
            TASK_PDF, None, [], 1, etap="etap2",
            on_thinking=on_thinking, on_feedback=on_feedback, on_upload_complete=on_upload_complete,
            solution_text="x",
        )
    )

    assert thoughts == ["Najpierw ", "sprawdzam."]
    assert "".join(feedback) == GRADE_JSON
    assert order == ["upload"]
    assert result.score == 5
    assert result.feedback == "Dobrze."
    meta = result.scoring_meta
    assert meta["provider"] == "anthropic"
    assert meta["model"] == "claude-opus-5-5"
    assert (meta["input_tokens"], meta["output_tokens"]) == (1000, 200)
    assert (meta["cache_read_tokens"], meta["cache_write_tokens"], meta["thoughts_tokens"]) == (300, 400, 0)
    assert meta["estimated_cost"] == pytest.approx((1000 * 4 + 200 * 20 + 300 * 0.2 + 400 * 5) / 1e6)
    assert meta["thinking"] == "Najpierw sprawdzam."
    assert "api_time" in meta and "total_time" in meta
    assert "cost_usd" not in meta


def test_analyze_solution_non_stream_wraps_the_stream(make_provider):
    p, log = make_provider()
    result = asyncio.run(p.analyze_solution(TASK_PDF, None, [], 1, etap="etap2", solution_text="x"))
    assert result.score == 5
    assert log[0][1] == "stream"


# --------------------------------------------------------- private grading


def test_private_grading_labels_photos_and_has_no_documents(make_provider, tmp_path):
    p, log = make_provider()
    photos = [png(tmp_path / "a.png"), png(tmp_path / "b.jpg")]

    result = asyncio.run(p.analyze_private_solution_stream("Tytuł", "Treść", photos, solution_text="t"))

    blocks = blocks_of(log[0][2])
    assert [b["type"] for b in blocks] == ["text", "text", "image", "text", "image", "text", "text"]
    assert blocks[0]["text"] == ai_requests.private_grading_text("Tytuł", "Treść", 2, True)
    assert blocks[1]["text"] == ai_requests.photo_label(1)
    assert blocks[3]["text"] == ai_requests.photo_label(2)
    assert blocks[4]["source"]["media_type"] == "image/jpeg"
    assert blocks[5]["text"] == solution_text_block("t")
    assert blocks[6]["text"] == CLOSING_LINE
    assert not any("cache_control" in b for b in blocks)
    assert result.scoring_meta["provider"] == "anthropic"


# ------------------------------------------------------- stop reasons


def test_refusal_on_grading_is_content_blocked(make_provider):
    p, _ = make_provider(final=message(text=None, stop_reason="refusal"))
    with pytest.raises(AIContentBlockedError):
        asyncio.run(p.analyze_solution_stream(TASK_PDF, None, [], 1, solution_text="x"))


def test_refusal_on_aux_call_is_content_blocked(make_provider):
    p, log = make_provider(final=message(text=None, stop_reason="refusal"))
    with pytest.raises(AIContentBlockedError):
        asyncio.run(p.generate_private_task_meta("Tytuł", "Treść"))
    assert log[0][1] == "create"


def test_max_tokens_with_empty_text_is_provider_error(make_provider):
    p, _ = make_provider(final=message(text="", stop_reason="max_tokens"))
    with pytest.raises(AIProviderError) as info:
        asyncio.run(p.analyze_solution_stream(TASK_PDF, None, [], 1, solution_text="x"))
    assert not isinstance(info.value, AIContentBlockedError)
    assert str(info.value) == "Nie udało się odczytać rozwiązania. Spróbuj ponownie."


def test_max_tokens_with_truncated_json_on_aux_is_provider_error(make_provider):
    p, _ = make_provider(final=message(text='{"hints": ["a', stop_reason="max_tokens"))
    with pytest.raises(AIProviderError):
        asyncio.run(p.generate_private_task_meta("Tytuł", "Treść"))


def test_fallback_served_response_is_recorded(make_provider):
    final = message(model="claude-opus-5")
    final.content.insert(0, SimpleNamespace(type="fallback"))
    final.usage.iterations = [SimpleNamespace(type="message"), SimpleNamespace(type="fallback_message")]
    p, _ = make_provider(final=final)
    result = asyncio.run(p.analyze_solution_stream(TASK_PDF, None, [], 1, solution_text="x"))
    assert result.score == 5
    assert result.scoring_meta["model"] == "claude-opus-5-5"
    assert result.scoring_meta["served_by"] == "claude-opus-5"
    # served_by outside the catalog: priced at the requested model's rates
    assert result.scoring_meta["estimated_cost"] == pytest.approx(
        estimate_cost("anthropic", "claude-opus-5-5", 1000, 200, cache_read_tokens=300, cache_write_tokens=400)
    )


def test_fallback_served_by_catalog_model_is_priced_at_its_rates(make_provider):
    final = message(model="claude-sonnet-5-5")
    final.usage.iterations = [SimpleNamespace(type="message"), SimpleNamespace(type="fallback_message")]
    p, _ = make_provider(final=final)
    result = asyncio.run(p.analyze_solution_stream(TASK_PDF, None, [], 1, solution_text="x"))
    assert result.scoring_meta["served_by"] == "claude-sonnet-5-5"
    expected = estimate_cost("anthropic", "claude-sonnet-5-5", 1000, 200, cache_read_tokens=300, cache_write_tokens=400)
    assert expected == pytest.approx(0.00503)  # (1000*2 + 200*10 + 300*0.10 + 400*2.50) / 1M
    assert result.scoring_meta["estimated_cost"] == pytest.approx(expected)

def test_no_served_by_without_fallback_iteration(make_provider):
    # Model name differences alone do not mean a fallback ran
    final = message(model="claude-opus-5-5-20261001")
    final.usage.iterations = [SimpleNamespace(type="message")]
    p, _ = make_provider(final=final)
    result = asyncio.run(p.analyze_solution_stream(TASK_PDF, None, [], 1, solution_text="x"))
    assert "served_by" not in result.scoring_meta


# ------------------------------------------------------------- errors


def _response(status):
    return httpx2.Response(status, request=httpx2.Request("POST", "https://api.example.invalid/v1/messages"))


@pytest.mark.parametrize(
    "error, expected",
    [
        (lambda: anthropic.RateLimitError(message="x", response=_response(429), body=None),
         "System jest obecnie przeciążony. Spróbuj ponownie za kilka minut."),
        (lambda: anthropic.APIStatusError(message="x", response=_response(529), body=None),
         "System jest obecnie przeciążony. Spróbuj ponownie za kilka minut."),
        (lambda: anthropic.InternalServerError(message="x", response=_response(500), body=None),
         "System jest obecnie przeciążony. Spróbuj ponownie za kilka minut."),
        (lambda: anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x.invalid")),
         "System jest obecnie przeciążony. Spróbuj ponownie za kilka minut."),
        (lambda: anthropic.APITimeoutError(request=httpx2.Request("POST", "https://x.invalid")),
         "Analiza trwa zbyt długo. Spróbuj ponownie za chwilę."),
        (lambda: anthropic.AuthenticationError(message="x", response=_response(401), body=None),
         "Przepraszamy, wystąpił problem techniczny. Spróbuj ponownie później."),
        (lambda: anthropic.PermissionDeniedError(message="x", response=_response(403), body=None),
         "Przepraszamy, wystąpił problem techniczny. Spróbuj ponownie później."),
        (lambda: anthropic.BadRequestError(message="x", response=_response(400), body=None),
         "Przepraszamy, coś poszło nie tak. Spróbuj ponownie za chwilę."),
    ],
)
def test_errors_map_to_friendly_messages(make_provider, error, expected):
    p, _ = make_provider(error=error())
    with pytest.raises(AIProviderError) as stream_info:
        asyncio.run(p.analyze_solution_stream(TASK_PDF, None, [], 1, solution_text="x"))
    assert str(stream_info.value) == expected
    with pytest.raises(AIProviderError) as aux_info:
        asyncio.run(p.link_pattern_tasks({"trigger": "t", "action": "a"}, []))
    assert str(aux_info.value) == expected


def test_stream_timeout_is_enforced(make_provider, monkeypatch):
    p, _ = make_provider(delay=5.0)
    monkeypatch.setattr(p, "get_timeout", lambda: 0.05)
    with pytest.raises(AIProviderError) as info:
        asyncio.run(p.analyze_solution_stream(TASK_PDF, None, [], 1, solution_text="x"))
    assert str(info.value) == "Analiza trwa zbyt długo. Spróbuj ponownie za chwilę."


def test_get_timeout_reads_settings(make_provider, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_timeout", 123)
    p, _ = make_provider()
    assert p.get_timeout() == 123


# ------------------------------------------------------------- images


def test_oversized_photo_is_downscaled_in_memory(make_provider, tmp_path):
    big = tmp_path / "big.png"
    # 2400x800 noise: ~5.8 MB raw PNG, ~7.7 MB base64 - over the 5 MB per-image limit
    noise = Image.frombytes("RGB", (2400, 800), os.urandom(2400 * 800 * 3))
    noise.save(big, "PNG", compress_level=0)
    assert big.stat().st_size > 5 * 1024 * 1024
    before = set(tmp_path.iterdir())
    p, log = make_provider()

    asyncio.run(p.analyze_private_solution_stream("T", "C", [big]))

    image = next(b for b in blocks_of(log[0][2]) if b["type"] == "image")
    assert image["source"]["media_type"] == "image/jpeg"
    assert len(image["source"]["data"]) <= 5 * 1024 * 1024
    with Image.open(io.BytesIO(base64.standard_b64decode(image["source"]["data"]))) as sent:
        assert max(sent.size) <= 2000
        assert sent.size[0] > sent.size[1]  # aspect kept
    assert set(tmp_path.iterdir()) == before  # nothing written to disk


def test_photo_over_dimension_limit_is_downscaled(make_provider, tmp_path):
    tall = png(tmp_path / "tall.webp", size=(100, 9000))
    p, log = make_provider()
    asyncio.run(p.extract_private_tasks([tall]))
    image = next(b for b in blocks_of(log[0][2]) if b["type"] == "image")
    with Image.open(io.BytesIO(base64.standard_b64decode(image["source"]["data"]))) as sent:
        assert max(sent.size) <= 2000


def test_unknown_suffix_is_reencoded_to_jpeg(make_provider, tmp_path):
    odd = tmp_path / "photo.bmp"
    Image.new("RGBA", (30, 20), (0, 0, 0, 0)).save(odd, "BMP")
    p, log = make_provider()
    asyncio.run(p.extract_private_tasks([odd]))
    image = next(b for b in blocks_of(log[0][2]) if b["type"] == "image")
    assert image["source"]["media_type"] == "image/jpeg"
    with Image.open(io.BytesIO(base64.standard_b64decode(image["source"]["data"]))) as sent:
        assert sent.format == "JPEG"


# --------------------------------------------------------- aux calls


def test_meta_sends_shared_text_and_parses(make_provider):
    meta_json = json.dumps({"hints": ["a", "b", "c"], "category": "algebra", "difficulty": 2, "abuse_score": 0})
    p, log = make_provider(final=message(text=meta_json))

    result = asyncio.run(p.generate_private_task_meta("Tytuł", "Treść $x$"))

    [(path, kind, kwargs)] = log
    assert (path, kind) == ("beta", "create")
    assert blocks_of(kwargs) == [{"type": "text", "text": ai_requests.meta_text("Tytuł", "Treść $x$")}]
    assert kwargs["output_config"]["effort"] == "medium"
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["max_tokens"] == 16000
    assert result.hints == ["a", "b", "c"]
    assert result.category == "algebra"
    assert result.meta["provider"] == "anthropic"


def test_link_sends_shared_text_and_parses(make_provider):
    candidates = [{"task_key": "2024_etap1_1", "difficulty": 2, "categories": ["algebra"], "hints": ["h"]}]
    link_json = json.dumps({"links": [{"task_key": "2024_etap1_1", "reason": "r"}], "abuse_score": 0})
    p, log = make_provider("claude-haiku-5-5", final=message(text=link_json))

    result = asyncio.run(p.link_pattern_tasks({"trigger": "t", "action": "a"}, candidates))

    [(path, kind, kwargs)] = log
    assert (path, kind) == ("messages", "create")
    assert blocks_of(kwargs) == [
        {"type": "text", "text": ai_requests.link_text({"trigger": "t", "action": "a"}, candidates)}
    ]
    assert [link.task_key for link in result.links] == ["2024_etap1_1"]


def test_extraction_sends_instruction_then_photos(make_provider, tmp_path):
    photos = [png(tmp_path / "a.png"), png(tmp_path / "b.png")]
    p, log = make_provider(final=message(text='{"is_math_problem": false, "abuse_score": 0, "problems": []}'))
    result = asyncio.run(p.extract_private_tasks(photos))
    blocks = blocks_of(log[0][2])
    assert [b["type"] for b in blocks] == ["text", "image", "image"]
    assert blocks[0]["text"] == ai_requests.extract_text()
    assert result.is_math_problem is False


def test_structured_output_schema_is_strict_and_shared_schemas_untouched(make_provider):
    snapshot = copy.deepcopy((RESPONSE_JSON_SCHEMA, META_SCHEMA, PATTERN_LINK_SCHEMA))
    p, grading_log = make_provider()
    asyncio.run(p.analyze_solution_stream(TASK_PDF, None, [], 1, solution_text="x"))
    p, meta_log = make_provider(final=message(text='{"hints": [], "category": "algebra", "difficulty": 1, "abuse_score": 0}'))
    asyncio.run(p.generate_private_task_meta("T", "C"))
    p, link_log = make_provider(final=message(text='{"links": [], "abuse_score": 0}'))
    asyncio.run(p.link_pattern_tasks({"trigger": "t", "action": "a"}, []))
    log = grading_log + meta_log + link_log
    assert len(log) == 3

    for _, _, kwargs in log:
        schema = kwargs["output_config"]["format"]["schema"]
        objects = list(walk_objects(schema))
        assert objects
        assert all(obj.get("additionalProperties") is False for obj in objects)
    assert (RESPONSE_JSON_SCHEMA, META_SCHEMA, PATTERN_LINK_SCHEMA) == snapshot
    assert not any("additionalProperties" in obj for obj in walk_objects(RESPONSE_JSON_SCHEMA))


# --------------------------------------------------------------- ping


@pytest.mark.parametrize("model, path", [
    ("claude-opus-5-5", "beta"),
    ("claude-sonnet-5-5", "beta"),
    ("claude-haiku-5-5", "messages"),
])
def test_ping_uses_the_grading_request_shape(make_provider, model, path):
    p, log = make_provider(model, final=message(text='{"ok": true}', model=model))
    assert asyncio.run(p.ping()) is None
    [(sent_path, kind, kwargs)] = log
    assert (sent_path, kind) == (path, "create")
    grading = p._request([anthropic_module._text_block("x")], anthropic_module.GRADING_SCHEMA, "high", grading=True)
    # Same builder as grading: every option except content, schema, effort and max_tokens
    for key in ("model", "thinking", "betas", "fallbacks"):
        assert kwargs.get(key) == grading.get(key), key
    assert kwargs["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert kwargs["max_tokens"] == anthropic_module.PING_MAX_TOKENS
    assert kwargs["output_config"] == {
        "format": {"type": "json_schema", "schema": anthropic_module.PING_SCHEMA},
        "effort": "low",
    }
    assert anthropic_module.PING_SCHEMA["additionalProperties"] is False
    assert blocks_of(kwargs) == [{"type": "text", "text": anthropic_module.PING_PROMPT}]


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal", "end_turn"])
def test_ping_any_stop_reason_is_success(make_provider, stop_reason):
    p, _ = make_provider(final=message(text="", stop_reason=stop_reason))
    assert asyncio.run(p.ping()) is None


@pytest.mark.parametrize("error, expected", [
    (anthropic.AuthenticationError(message="x", response=_response(401), body=None), "401 Unauthorized"),
    (
        anthropic.RateLimitError(
            message="secret body", response=_response(429),
            body={"type": "error", "error": {"type": "rate_limit_error", "message": "secret body"}},
        ),
        "429 rate_limit_error",
    ),
    (anthropic.InternalServerError(message="secret body", response=_response(503), body=None), "503 Service Unavailable"),
    (asyncio.TimeoutError(), "TimeoutError"),
])
def test_ping_failure_names_status_not_body(make_provider, error, expected):
    p, _ = make_provider(error=error)
    with pytest.raises(AIProviderError) as info:
        asyncio.run(p.ping())
    assert str(info.value) == f"Model claude-opus-5-5 nie odpowiada: {expected}"
    assert "secret" not in str(info.value)


def test_provider_identity_and_lazy_export(make_provider):
    p, _ = make_provider("claude-sonnet-5-5")
    assert p.provider_name == "anthropic"
    assert p.model_name == "claude-sonnet-5-5"
    from app.ai import providers

    assert providers.AnthropicProvider is AnthropicProvider
    assert anthropic_module.AnthropicProvider is AnthropicProvider


def test_missing_key_refuses_to_build(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    with pytest.raises(ValueError):
        AnthropicProvider("claude-opus-5-5")


# ------------------------------------------------------ request budget


def gradient(path: Path, size=(2000, 1500)) -> Path:
    """A smooth JPEG within the per-image limits (sent untouched unless the budget bites)."""
    img = Image.linear_gradient("L").resize(size).convert("RGB")
    img.save(path, "JPEG", quality=95)
    return path


def sent_images(kwargs) -> list:
    out = []
    for block in blocks_of(kwargs):
        if block["type"] == "image":
            with Image.open(io.BytesIO(base64.standard_b64decode(block["source"]["data"]))) as img:
                out.append((block["source"]["media_type"], img.size, len(block["source"]["data"])))
    return out


def request_bytes(kwargs) -> int:
    return sum(anthropic_module._block_size(b) for b in blocks_of(kwargs))


def test_photos_fitting_the_budget_are_untouched(make_provider, tmp_path):
    photos = [gradient(tmp_path / f"{i}.jpg") for i in range(3)]
    p, log = make_provider()
    asyncio.run(p.analyze_solution_stream(TASK_PDF, TASK_PDF, photos, 1, solution_text="x"))
    images = blocks_of(log[0][2])
    sent = [b for b in images if b["type"] == "image"]
    assert [base64.standard_b64decode(b["source"]["data"]) for b in sent] == [ph.read_bytes() for ph in photos]


def test_request_over_budget_shrinks_photos_step_by_step(make_provider, tmp_path, monkeypatch):
    photos = [gradient(tmp_path / f"{i}.jpg") for i in range(10)]  # a "large set"
    p, probe = make_provider()
    asyncio.run(p.analyze_solution_stream(TASK_PDF, TASK_PDF, photos, 1, solution_text="x"))
    full = request_bytes(probe[0][2])
    # Budget just below the untouched request: the first shrink step (1600 px, q80) must fit
    monkeypatch.setattr(anthropic_module, "REQUEST_BUDGET_BYTES", full - 1)
    p, log = make_provider()

    asyncio.run(p.analyze_solution_stream(TASK_PDF, TASK_PDF, photos, 1, solution_text="x"))

    kwargs = log[0][2]
    assert request_bytes(kwargs) <= full - 1
    sent = sent_images(kwargs)
    assert len(sent) == 10
    assert all(media == "image/jpeg" and max(size) == 1600 for media, size, _ in sent)
    assert [b["type"] for b in blocks_of(kwargs)][:3] == ["text", "document", "document"]


def test_request_over_budget_after_all_steps_is_friendly_error(make_provider, tmp_path, monkeypatch):
    photos = [gradient(tmp_path / f"{i}.jpg") for i in range(3)]
    smallest = sum(
        anthropic_module._block_size(anthropic_module._image_block(ph, anthropic_module.REQUEST_SHRINK_STEPS[-1]))
        for ph in photos
    )
    calls = {
        "omj": lambda p: p.analyze_solution_stream(TASK_PDF, None, photos, 1),
        "private": lambda p: p.analyze_private_solution_stream("T", "C", photos),
        "extract": lambda p: p.extract_private_tasks(photos),
    }
    # Pass 1 (budget untouched): the bytes of everything but the photos, per call
    real_photo_blocks = anthropic_module._photo_blocks
    other: dict = {}

    def spy(image_paths, other_bytes):
        other[current] = other_bytes
        return real_photo_blocks(image_paths, other_bytes)

    monkeypatch.setattr(anthropic_module, "_photo_blocks", spy)
    for current, call in calls.items():
        p, _ = make_provider()
        asyncio.run(call(p))
    monkeypatch.setattr(anthropic_module, "_photo_blocks", real_photo_blocks)

    shrinks = []
    real_image_block = anthropic_module._image_block
    monkeypatch.setattr(
        anthropic_module, "_image_block", lambda path, shrink=None: shrinks.append(shrink) or real_image_block(path, shrink)
    )
    for name, call in calls.items():
        # PDF + text fit; even the smallest photos do not - so every shrink step must run first
        budget = other[name] + smallest // 2
        assert other[name] < budget < other[name] + smallest
        monkeypatch.setattr(anthropic_module, "REQUEST_BUDGET_BYTES", budget)
        shrinks.clear()
        p, log = make_provider()
        with pytest.raises(AIProviderError) as info:
            asyncio.run(call(p))
        assert str(info.value) == "Przesłane zdjęcia są zbyt duże. Spróbuj wysłać mniej zdjęć."
        assert shrinks == [None] * 3 + [step for step in anthropic_module.REQUEST_SHRINK_STEPS for _ in range(3)]
        assert log == []  # nothing was sent


# -------------------------------------------------------------- patterns


def test_refine_sends_shared_text_and_parses(make_provider, monkeypatch):
    skills = [SimpleNamespace(id="skill_a", name="Umiejętność A")]
    monkeypatch.setattr(anthropic_module, "get_all_skills", lambda: skills)
    candidates = [{"task_key": "2024_etap1_1", "difficulty": 2, "categories": ["algebra"], "hints": ["h"]}]
    args = dict(
        draft={"trigger": "t", "action": "a"},
        source_text="src",
        history=[],
        current={"answers": [], "message": "hej"},
        candidates=candidates,
    )
    refine_json = json.dumps({
        "reply": "Odpowiedź.",
        "variants": [
            {"trigger": "w1", "action": "a1", "example": "e", "note": "n", "tasks": ["2024_etap1_1", "9999_etap1_1"]},
            {"trigger": "w2", "action": "a2", "example": "e", "note": "n", "tasks": []},
        ],
        "questions": ["Pytanie?"],
        "verdict": "ok",
        "comment": "c",
        "category": "algebra",
        "skills": ["skill_a", "unknown"],
        "abuse_score": 0,
    })
    p, log = make_provider(final=message(text=refine_json))

    result = asyncio.run(p.refine_pattern(**args))

    assert blocks_of(log[0][2]) == [
        {"type": "text", "text": ai_requests.refine_text(
            args["draft"], args["source_text"], args["history"], args["current"], candidates, skills
        )}
    ]
    assert log[0][2]["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert result.reply == "Odpowiedź."
    # Shared parser: unknown task keys and skills are dropped
    assert result.variants[0].tasks == ["2024_etap1_1"]
    assert result.skills == ["skill_a"]
    assert result.meta["provider"] == "anthropic"


def test_suggest_sends_shared_text_and_parses(make_provider):
    suggest_json = json.dumps({
        "suggestions": [{"trigger": "t", "action": "a", "example": "e", "why": "w", "category": "algebra"}],
        "abuse_score": 0,
    })
    p, log = make_provider(final=message(text=suggest_json))

    result = asyncio.run(p.suggest_patterns("zadanie", "ocena", None))

    assert blocks_of(log[0][2]) == [{"type": "text", "text": ai_requests.suggest_text("zadanie", "ocena", None)}]
    assert [(s.trigger, s.action, s.category) for s in result.suggestions] == [("t", "a", "algebra")]
    assert result.meta["provider"] == "anthropic"
