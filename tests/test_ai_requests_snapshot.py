"""Snapshot of the text GeminiProvider sends for every kind of AI request.

The request text lives in app/ai/requests.py so every provider sends the same
strings. This snapshot was generated from the code BEFORE that move and pins
Gemini's requests byte for byte: a refactor must not change a single character.

Regenerate (only for a deliberate prompt change):
    UPDATE_SNAPSHOT=1 ./venv/bin/python -m pytest -q tests/test_ai_requests_snapshot.py

All inputs are invented strings, never real OMJ task statements.
"""

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("google.genai")

from app.ai.factory import AIProviderError  # noqa: E402
from app.ai.prompt_builder import build_prompt  # noqa: E402
from app.ai.providers import gemini as gemini_module  # noqa: E402
from app.ai.providers.gemini import GeminiProvider  # noqa: E402

SNAPSHOT = Path(__file__).parent / "fixtures" / "gemini_request_snapshot.json"

CANDIDATE = {"task_key": "2024_etap1_1", "difficulty": 2, "categories": ["algebra"], "hints": ["h1"]}
FAKE_SKILLS = [
    SimpleNamespace(id="skill_a", name="Umiejętność A"),
    SimpleNamespace(id="skill_b", name="Umiejętność B"),
]


class _Captured(Exception):
    """Raised by the stub client once the request has been recorded."""


def _strings(contents: list) -> list[str]:
    return [part if isinstance(part, str) else "<part>" for part in contents]


def _provider(captured: list) -> GeminiProvider:
    def generate_content(**kwargs):
        captured.append(_strings(kwargs["contents"]))
        raise _Captured()

    p = GeminiProvider.__new__(GeminiProvider)
    p._model_name = "gemini-3.8-flash"
    # Forced False (the real gemini-3.8-flash would be True): only the Gemini 3
    # branches build SDK media parts (inline bytes + per-part media_resolution)
    # and a thinking_level config. The snapshot pins request TEXT, which both
    # branches send identically; with False the photos and PDFs stay as the
    # plain placeholder strings below, so no real files or SDK types are needed.
    p._is_gemini_3 = False
    p._disable_file_cache = True
    p.provider_name = "gemini"
    p._client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=generate_content,
            generate_content_stream=generate_content,
        )
    )
    return p


def _call(coro) -> None:
    """Run a provider call whose stub client records the request and then fails."""
    with pytest.raises(AIProviderError):
        asyncio.run(coro)


def build_snapshot(monkeypatch) -> dict[str, list[str]]:
    monkeypatch.setattr(gemini_module, "get_all_skills", lambda: FAKE_SKILLS)
    captured: list = []
    p = _provider(captured)
    out: dict[str, list[str]] = {}

    _call(p.generate_private_task_meta("Tytuł", "Treść $x^2$"))
    out["private_task_meta"] = captured.pop()

    _call(
        p.refine_pattern(
            draft={"trigger": "t", "action": "a"},
            source_text="src",
            history=[
                {
                    "draft": {"raw": "r"},
                    "verdict": "ok",
                    "variants": [{"trigger": "x", "action": "y", "tasks": ["2024_etap1_1"]}],
                    "questions": ["q?"],
                    "chosen": 0,
                }
            ],
            current={"answers": [{"question": "q?", "answer": "ans"}], "message": "hej"},
            candidates=[CANDIDATE],
        )
    )
    out["refine_pattern"] = captured.pop()

    _call(p.suggest_patterns("zadanie", "ocena", None))
    out["suggest_patterns"] = captured.pop()

    _call(p.link_pattern_tasks({"trigger": "t", "action": "a"}, [CANDIDATE]))
    out["link_pattern_tasks"] = captured.pop()

    # Non-Gemini-3 path: plain strings stand in for the uploaded files.
    out["omj_grading"] = p._build_content_parts(
        build_prompt("etap2"), ["TASK", "SOL", "IMG1", "IMG2"], 3, True, 2,
        image_paths=None, solution_text="moje $a$",
    )
    # Typed text only: no official solution PDF, no photos.
    out["omj_grading_text_only"] = p._build_content_parts(
        build_prompt("etap2"), ["TASK"], 3, False, 0,
        image_paths=None, solution_text="moje $a$",
    )

    async def fake_run_stream(contents, config, on_thinking=None, on_feedback=None, start_time=None):
        captured.append(_strings(contents))
        return "", '{"score":2,"feedback":"f","issue_type":"none","abuse_score":0}', None, 0.1, 0.1

    monkeypatch.setattr(p, "_run_stream", fake_run_stream)
    asyncio.run(p.analyze_private_solution_stream("T", "C", [], solution_text="txt"))
    out["private_grading"] = captured.pop()

    # Photos: _image_parts is stubbed so no file is read; "<part>" marks each photo.
    async def fake_image_parts(image_paths):
        return [object() for _ in image_paths], []

    monkeypatch.setattr(p, "_image_parts", fake_image_parts)
    photos = [Path("a.jpg"), Path("b.jpg")]
    asyncio.run(p.analyze_private_solution_stream("T", "C", photos))
    out["private_grading_photos"] = captured.pop()

    _call(p.extract_private_tasks(photos))
    out["extract_private_tasks"] = captured.pop()

    assert not captured
    return out


def test_gemini_requests_match_snapshot(monkeypatch):
    current = build_snapshot(monkeypatch)
    if os.environ.get("UPDATE_SNAPSHOT") == "1":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert set(current) == set(expected)
    for name in expected:
        assert current[name] == expected[name], f"request text drifted: {name}"
