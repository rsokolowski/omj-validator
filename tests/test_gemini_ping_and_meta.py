"""GeminiProvider.ping() and the usage keys in OMJ streaming scoring_meta."""

import asyncio
from types import SimpleNamespace

import pytest

from app.ai.factory import AIProviderError
from app.ai.providers.gemini import GeminiProvider


def bare_provider(generate=None) -> GeminiProvider:
    """A provider without a network client or API key."""
    p = GeminiProvider.__new__(GeminiProvider)
    p._model_name = "gemini-3.8-flash"
    p._is_gemini_3 = True
    p._disable_file_cache = False
    p._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    return p


def test_ping_success_returns_none():
    calls = []
    p = bare_provider(lambda **kwargs: calls.append(kwargs) or SimpleNamespace(text="OK"))
    assert asyncio.run(p.ping()) is None
    assert calls[0]["model"] == "gemini-3.8-flash"


def test_ping_failure_raises_provider_error():
    def fail(**kwargs):
        raise RuntimeError("401 bad key")

    with pytest.raises(AIProviderError):
        asyncio.run(bare_provider(fail).ping())


def test_stream_scoring_meta_carries_provider_and_usage(monkeypatch, tmp_path):
    p = bare_provider()
    usage = SimpleNamespace(prompt_token_count=1000, candidates_token_count=200, thoughts_token_count=50)

    async def upload(*args):
        return [], False

    async def run_stream(*args):
        return "myśli", '{"score": 5, "feedback": "Dobrze."}', usage, 1.5, 2.0

    async def cleanup(*args, **kwargs):
        return None

    monkeypatch.setattr(p, "_upload_files", upload, raising=False)
    monkeypatch.setattr(p, "_build_content_parts", lambda *a, **k: [], raising=False)
    monkeypatch.setattr(p, "_load_prompt", lambda etap: "prompt", raising=False)
    monkeypatch.setattr(p, "_run_stream", run_stream, raising=False)
    monkeypatch.setattr(p, "_cleanup_files", cleanup, raising=False)

    result = asyncio.run(p.analyze_solution_stream(tmp_path / "t.pdf", None, [], 1, etap="etap2"))

    meta = result.scoring_meta
    assert meta["provider"] == "gemini"
    assert meta["model"] == "gemini-3.8-flash"
    assert meta["estimated_cost"] > 0
    assert (meta["input_tokens"], meta["output_tokens"], meta["thoughts_tokens"]) == (1000, 200, 50)
    assert meta["thinking"] == "myśli"
    assert (meta["api_time"], meta["total_time"]) == (1.5, 2.0)
