"""Gemini: safety settings on every call, blocks surface as AIContentBlockedError,
availability errors as AIUnavailableError (the only ones that may fail over)."""

import asyncio
import logging
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app.ai.factory import AIContentBlockedError, AIProviderError, AIUnavailableError
from app.ai.providers import gemini as gemini_module
from app.ai.providers.gemini import GeminiProvider, block_reason, classify_unavailable, map_error


def bare_provider(generate=None, stream=None, delete=None) -> GeminiProvider:
    p = GeminiProvider.__new__(GeminiProvider)
    p._model_name = "gemini-3.8-flash"
    p._is_gemini_3 = False
    p._disable_file_cache = True
    p._client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate, generate_content_stream=stream),
        files=SimpleNamespace(delete=delete),
    )
    return p


def thresholds(config) -> dict:
    return {s.category: s.threshold for s in config.safety_settings}


EXPECTED = {
    types.HarmCategory.HARM_CATEGORY_HARASSMENT: types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}


# ----------------------------------------------------------- safety settings


def test_config_always_carries_the_safety_settings():
    config = GeminiProvider._config(response_mime_type="application/json")
    assert thresholds(config) == EXPECTED
    assert config.response_mime_type == "application/json"


def test_aux_call_sends_safety_settings():
    sent = []

    def generate(**kwargs):
        sent.append(kwargs["config"])
        return SimpleNamespace(text='{"links": [], "abuse_score": 0}', candidates=[], usage_metadata=None)

    asyncio.run(bare_provider(generate).link_pattern_tasks({"trigger": "t", "action": "a"}, []))
    assert thresholds(sent[0]) == EXPECTED


def test_every_generate_config_in_the_provider_goes_through_config():
    """No call site may build a GenerateContentConfig without the safety settings."""
    import inspect

    source = inspect.getsource(gemini_module)
    assert source.count("types.GenerateContentConfig(") == 1
    assert "types.GenerateContentConfig(safety_settings=safety_settings()" in source


# ---------------------------------------------------------------- blocks


def response(block=None, finish=None, text=""):
    candidates = [SimpleNamespace(finish_reason=finish)] if finish is not None else []
    return SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason=block) if block is not None else None,
        candidates=candidates,
        text=text,
        usage_metadata=None,
    )


@pytest.mark.parametrize(
    "resp, expected",
    [
        (response(block=types.BlockedReason.SAFETY), "prompt:SAFETY"),
        (response(block=types.BlockedReason.PROHIBITED_CONTENT), "prompt:PROHIBITED_CONTENT"),
        (response(block="OTHER"), "prompt:OTHER"),
        (response(block=types.BlockedReason.BLOCKED_REASON_UNSPECIFIED, text="{}"), None),
        (response(finish=types.FinishReason.SAFETY), "finish:SAFETY"),
        (response(finish=types.FinishReason.IMAGE_SAFETY), "finish:IMAGE_SAFETY"),
        (response(finish="BLOCKLIST"), "finish:BLOCKLIST"),
        (response(finish=types.FinishReason.STOP, text="{}"), None),
        (response(finish=types.FinishReason.RECITATION), None),
    ],
)
def test_block_reason(resp, expected):
    assert block_reason(resp) == expected


def test_prompt_level_block_on_aux_call_is_content_blocked():
    """No candidates + block_reason used to parse as "" -> abuse 0, empty hints, saved unchecked."""
    p = bare_provider(lambda **kwargs: response(block=types.BlockedReason.SAFETY))
    with pytest.raises(AIContentBlockedError):
        asyncio.run(p.generate_private_task_meta("Tytuł", "Treść"))


def test_empty_aux_answer_is_an_error_not_an_empty_result():
    p = bare_provider(lambda **kwargs: response(finish=types.FinishReason.STOP, text=""))
    with pytest.raises(AIProviderError) as info:
        asyncio.run(p.generate_private_task_meta("Tytuł", "Treść"))
    assert not isinstance(info.value, (AIContentBlockedError, AIUnavailableError))


def test_non_stream_grading_block_is_content_blocked(monkeypatch, tmp_path):
    p = bare_provider(lambda **kwargs: response(block=types.BlockedReason.SAFETY))

    async def upload(*args):
        return [], False

    async def cleanup(*args, **kwargs):
        return None

    monkeypatch.setattr(p, "_upload_files", upload, raising=False)
    monkeypatch.setattr(p, "_build_content_parts", lambda *a, **k: [], raising=False)
    monkeypatch.setattr(p, "_cleanup_files", cleanup, raising=False)
    with pytest.raises(AIContentBlockedError):
        asyncio.run(p.analyze_solution(tmp_path / "t.pdf", None, [], 1))


def chunk(text="", thought=False, block=None, finish=None):
    parts = [SimpleNamespace(text=text, thought=thought)] if text else []
    candidates = []
    if parts or finish is not None:
        candidates = [SimpleNamespace(content=SimpleNamespace(parts=parts) if parts else None, finish_reason=finish)]
    return SimpleNamespace(
        candidates=candidates,
        prompt_feedback=SimpleNamespace(block_reason=block) if block is not None else None,
        usage_metadata=None,
    )


@pytest.mark.parametrize(
    "chunks",
    [
        [chunk(block=types.BlockedReason.SAFETY)],  # prompt blocked: the only chunk, no candidates
        [chunk("myślę", thought=True), chunk(finish=types.FinishReason.SAFETY)],  # stopped mid-answer
    ],
)
def test_stream_block_is_content_blocked(chunks):
    p = bare_provider(stream=lambda **kwargs: iter(chunks))
    config = GeminiProvider._config()
    with pytest.raises(AIContentBlockedError):
        asyncio.run(p._run_stream(["x"], config))


def test_private_grading_stream_block_is_content_blocked(monkeypatch):
    p = bare_provider(stream=lambda **kwargs: iter([chunk(block="PROHIBITED_CONTENT")]))
    monkeypatch.setattr(p, "_get_media_resolution", lambda *a: None, raising=False)
    with pytest.raises(AIContentBlockedError):
        asyncio.run(p.analyze_private_solution_stream("T", "Treść", [], solution_text="x"))


# --------------------------------------------------------------- errors


def client_error(code, status, message="body"):
    cls = genai_errors.ServerError if code >= 500 else genai_errors.ClientError
    return cls(code, {"error": {"code": code, "status": status, "message": message}})


@pytest.mark.parametrize(
    "error, kind, permanent",
    [
        (client_error(401, "UNAUTHENTICATED"), "auth", True),
        (client_error(403, "PERMISSION_DENIED", "Your API key was reported as leaked"), "auth", True),
        (client_error(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key."), "auth", True),
        (client_error(400, "FAILED_PRECONDITION", "User location is not supported"), "auth", True),
        (client_error(400, "FAILED_PRECONDITION", "Gemini API free tier is not available in your country. "
                      "Please enable billing on your project in Google AI Studio."), "auth", True),
        (client_error(400, "FAILED_PRECONDITION", "Billing account is disabled"), "auth", True),
        (client_error(404, "NOT_FOUND", "models/gemini-9 is not found"), "not_found", True),
        (client_error(429, "RESOURCE_EXHAUSTED"), "rate_limit", False),
        (client_error(502, "BAD_GATEWAY"), "server", False),
        (client_error(503, "UNAVAILABLE"), "server", False),
        (client_error(504, "DEADLINE_EXCEEDED"), "server", False),
        (httpx.ConnectError("refused"), "network", False),
        (httpx.ConnectTimeout("no route"), "network", False),
    ],
)
def test_availability_errors_are_classified(error, kind, permanent):
    unavailable = classify_unavailable(error)
    assert isinstance(unavailable, AIUnavailableError)
    assert unavailable.kind == kind
    assert unavailable.permanent is permanent
    assert unavailable.fails_over is True
    assert "body" not in str(unavailable)


@pytest.mark.parametrize(
    "error, kind",
    [
        # A student can cause these with what they send (huge input, endless
        # thinking, an input the model chokes on): breaker only, fail closed
        (client_error(500, "INTERNAL", "An internal error has occurred"), "internal"),
        (httpx.ReadTimeout("slow"), "timeout"),
        (asyncio.TimeoutError(), "timeout"),
        (httpx.RemoteProtocolError("server disconnected"), "connection_lost"),
        (httpx.ReadError("reset"), "connection_lost"),
        (ConnectionResetError("reset"), "connection_lost"),
    ],
)
def test_content_dependent_failures_never_fail_over(error, kind):
    unavailable = classify_unavailable(error)
    assert unavailable.kind == kind
    assert unavailable.fails_over is False


@pytest.mark.parametrize(
    "error",
    [
        client_error(400, "INVALID_ARGUMENT", "Request contains an invalid argument."),
        client_error(400, "INVALID_ARGUMENT", "The input token count exceeds the maximum"),  # oversized input
        client_error(400, "INVALID_ARGUMENT", "Unable to process input image. echo: API key"),  # key text not at start
        client_error(413, "PAYLOAD_TOO_LARGE"),
        # A File API upload not processed yet: transient, not a dead key
        client_error(400, "FAILED_PRECONDITION",
                     "The File abc123 is not in an ACTIVE state and usage is not allowed."),
        client_error(400, "FAILED_PRECONDITION", "Precondition check failed."),
        ValueError("schema mismatch"),
        RuntimeError("Response was blocked due to SAFETY"),
        RuntimeError("You exceeded your current quota"),  # text match is not trusted to fail over
    ],
)
def test_other_errors_are_not_availability(error):
    assert classify_unavailable(error) is None
    assert not isinstance(map_error(error, "msg"), AIUnavailableError)


@pytest.mark.parametrize(
    "resp",
    [
        response(block=types.BlockedReason.SAFETY),  # prompt-level block, no candidates
        response(block="OTHER"),
        response(finish=types.FinishReason.SAFETY),
        response(finish=types.FinishReason.RECITATION),  # no text, not a safety finish
        response(finish=types.FinishReason.OTHER),
        response(),  # no candidates at all, no block reason
    ],
)
def test_blocked_or_empty_answers_never_look_like_an_outage(resp):
    """Nothing a student can provoke in the ANSWER may become an availability error."""
    p = bare_provider(lambda **kwargs: resp)
    with pytest.raises(AIProviderError) as info:
        asyncio.run(p.generate_private_task_meta("Tytuł", "Treść"))
    assert not isinstance(info.value, AIUnavailableError)


def test_safety_text_maps_to_content_blocked_but_a_dead_key_does_not():
    assert isinstance(map_error(RuntimeError("blocked: SAFETY"), "msg"), AIContentBlockedError)
    dead_key = map_error(client_error(403, "PERMISSION_DENIED", "Requests from this key are blocked."), "msg")
    assert isinstance(dead_key, AIUnavailableError) and dead_key.kind == "auth"


def test_stream_error_is_classified(monkeypatch):
    def stream(**kwargs):
        raise client_error(503, "UNAVAILABLE")

    p = bare_provider(stream=stream)
    monkeypatch.setattr(p, "_get_media_resolution", lambda *a: None, raising=False)
    with pytest.raises(AIUnavailableError) as info:
        asyncio.run(p.analyze_private_solution_stream("T", "Treść", [], solution_text="x"))
    assert info.value.kind == "server"


def test_stream_timeout_is_unavailable(monkeypatch):
    import time as time_module

    def stream(**kwargs):
        time_module.sleep(0.3)
        return iter([])

    p = bare_provider(stream=stream)
    monkeypatch.setattr(p, "get_timeout", lambda: 0.05)
    with pytest.raises(AIUnavailableError) as info:
        asyncio.run(p._run_stream(["x"], GeminiProvider._config()))
    assert info.value.kind == "timeout"


# --------------------------------------------------------------- cleanup


def test_cleanup_failure_is_logged_without_failing(caplog):
    def delete(name):
        raise client_error(500, "INTERNAL", "secret body")

    p = bare_provider(delete=delete)
    with caplog.at_level(logging.WARNING, logger="app.ai.providers.gemini"):
        asyncio.run(p._cleanup_files([SimpleNamespace(name="files/abc123")], skip_cached=False))
    assert "Could not delete files/abc123: ServerError 500 INTERNAL" in caplog.text
    assert "secret" not in caplog.text


# --------------------------------------------------------------- File API state


class _ProcessingFiles:
    def __init__(self, states):
        self.states = list(states)
        self.gets = 0

    def upload(self, file):
        return SimpleNamespace(name="files/x", state=SimpleNamespace(name=self.states.pop(0)))

    def get(self, name):
        self.gets += 1
        return SimpleNamespace(name=name, state=SimpleNamespace(name=self.states.pop(0)))


def _upload_with(monkeypatch, tmp_path, files):
    import app.ai.providers.gemini as gemini

    monkeypatch.setattr(gemini, "FILE_ACTIVE_POLL_SECONDS", 0)
    p = object.__new__(GeminiProvider)
    p._client = SimpleNamespace(files=files)
    photo = tmp_path / "a.jpg"
    photo.write_bytes(b"x")
    return asyncio.run(p._upload_file(photo, use_cache=False))


def test_upload_waits_for_a_processing_file_to_become_active(monkeypatch, tmp_path):
    files = _ProcessingFiles(["PROCESSING", "PROCESSING", "ACTIVE"])
    uploaded = _upload_with(monkeypatch, tmp_path, files)
    assert uploaded.state.name == "ACTIVE"
    assert files.gets == 2


def test_upload_of_an_active_file_does_not_poll(monkeypatch, tmp_path):
    files = _ProcessingFiles(["ACTIVE"])
    _upload_with(monkeypatch, tmp_path, files)
    assert files.gets == 0


def test_upload_polling_is_bounded(monkeypatch, tmp_path):
    import app.ai.providers.gemini as gemini

    monkeypatch.setattr(gemini, "FILE_ACTIVE_TIMEOUT_SECONDS", 0)
    files = _ProcessingFiles(["PROCESSING"])
    assert _upload_with(monkeypatch, tmp_path, files).state.name == "PROCESSING"
    assert files.gets == 0


def test_failed_file_processing_is_an_ordinary_error(monkeypatch, tmp_path):
    files = _ProcessingFiles(["PROCESSING", "FAILED"])
    with pytest.raises(AIProviderError) as excinfo:
        _upload_with(monkeypatch, tmp_path, files)
    assert not isinstance(excinfo.value, AIUnavailableError)
