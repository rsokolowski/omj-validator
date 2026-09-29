"""AI layer for private tasks: parsing model output and building requests.

The model output is untrusted: it decides what a student sees as their task
statement and hints, so every field is validated and clamped before use.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.ai.prompt_builder import (
    build_private_scoring_prompt,
    load_private_prompt,
    validate_prompts,
)
from app.ai.private_parsing import (
    EXTRACTION_SCHEMA,
    META_SCHEMA,
    MAX_PROBLEMS,
    parse_extraction_response,
    parse_meta_response,
)


def problem(**overrides):
    base = {
        "label": "Zadanie 1",
        "title": "Parzystość",
        "content": "Wykaż, że dla każdej liczby całkowitej $n$ liczba $n^2+n$ jest parzysta.",
        "category": "teoria_liczb",
        "difficulty": 2,
    }
    base.update(overrides)
    return base


def extraction(problems, is_math=True, abuse=0):
    return json.dumps(
        {"is_math_problem": is_math, "abuse_score": abuse, "problems": problems},
        ensure_ascii=False,
    )


class TestExtractionParsing:
    def test_valid_multi_problem_response(self):
        result = parse_extraction_response(
            extraction([problem(), problem(label="Zadanie 2", category="geometria")])
        )
        assert result.is_math_problem is True
        assert [p.label for p in result.problems] == ["Zadanie 1", "Zadanie 2"]
        assert result.problems[1].category == "geometria"

    def test_more_than_max_problems_is_truncated(self):
        result = parse_extraction_response(
            extraction([problem(label=f"Z{i}") for i in range(MAX_PROBLEMS + 3)])
        )
        assert len(result.problems) == MAX_PROBLEMS

    def test_problem_without_content_is_dropped(self):
        result = parse_extraction_response(
            extraction([problem(content="   "), problem(label="Zadanie 2")])
        )
        assert [p.label for p in result.problems] == ["Zadanie 2"]

    def test_unknown_category_becomes_none(self):
        result = parse_extraction_response(extraction([problem(category="calculus")]))
        assert result.problems[0].category is None

    @pytest.mark.parametrize("raw,expected", [(9, 5), (0, 1), (-3, 1), (3, 3), ("x", None)])
    def test_difficulty_is_clamped(self, raw, expected):
        result = parse_extraction_response(extraction([problem(difficulty=raw)]))
        assert result.problems[0].difficulty == expected

    def test_not_a_math_problem_has_no_problems(self):
        result = parse_extraction_response(extraction([problem()], is_math=False))
        assert result.is_math_problem is False
        assert result.problems == []

    def test_garbage_text_is_not_a_math_problem(self):
        result = parse_extraction_response("I cannot help with that.")
        assert result.is_math_problem is False
        assert result.problems == []

    def test_abuse_score_is_clamped(self):
        assert parse_extraction_response(extraction([problem()], abuse=250)).abuse_score == 100
        assert parse_extraction_response(extraction([problem()], abuse=-5)).abuse_score == 0

    def test_single_backslash_latex_is_repaired(self):
        # The model emitted "\frac" with ONE backslash: "\f" is a valid JSON
        # escape (form feed) and would silently eat the macro.
        raw = '{"is_math_problem": true, "abuse_score": 0, "problems": [{"label": "1", ' \
              '"title": "Ułamek", "content": "Oblicz $\\frac{1}{2} + \\frac{1}{3}$ i uzasadnij.", ' \
              '"category": "arytmetyka", "difficulty": 1}]}'
        result = parse_extraction_response(raw)
        assert "\\frac{1}{2}" in result.problems[0].content

    def test_overlong_title_is_cut_and_blank_title_gets_label(self):
        result = parse_extraction_response(
            extraction([problem(title="x" * 300), problem(title="  ", label="Zadanie 7")])
        )
        assert len(result.problems[0].title) == 120
        assert result.problems[1].title == "Zadanie 7"

    def test_json_in_code_fence(self):
        result = parse_extraction_response("```json\n" + extraction([problem()]) + "\n```")
        assert len(result.problems) == 1


class TestMetaParsing:
    def meta(self, **overrides):
        base = {
            "hints": ["Co wiesz o $n$ i $n+1$?", "Jedna z nich jest parzysta.", "Rozłóż na czynniki.", "$n^2+n = n(n+1)$"],
            "category": "teoria_liczb",
            "difficulty": 2,
            "abuse_score": 0,
        }
        base.update(overrides)
        return json.dumps(base, ensure_ascii=False)

    def test_valid_meta(self):
        result = parse_meta_response(self.meta())
        assert len(result.hints) == 4
        assert result.category == "teoria_liczb"

    def test_more_than_four_hints_truncated_and_blanks_dropped(self):
        result = parse_meta_response(self.meta(hints=["a", " ", "b", "c", "d", "e"]))
        assert result.hints == ["a", "b", "c", "d"]

    def test_non_string_hints_ignored(self):
        result = parse_meta_response(self.meta(hints=["a", 5, None, "b"]))
        assert result.hints == ["a", "b"]

    def test_garbage_gives_empty_meta(self):
        result = parse_meta_response("nope")
        assert result.hints == []
        assert result.category is None
        assert result.abuse_score == 0


class TestPrompts:
    def test_all_prompt_files_present(self):
        assert validate_prompts() == []

    def test_private_scoring_prompt_has_all_sections(self):
        prompt = build_private_scoring_prompt()
        assert "egzaminatorem" in prompt          # base
        assert "brak oficjalnego rozwiązania" in prompt.lower()  # private scoring
        assert "injection" in prompt              # abuse + JSON format

    def test_private_prompts_load(self):
        assert "problems" in load_private_prompt("extract")
        assert "hints" in load_private_prompt("meta")

    def test_unknown_private_prompt_rejected(self):
        with pytest.raises(ValueError):
            load_private_prompt("../gemini_prompt_base")


class _FakeModels:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return SimpleNamespace(text=self.text, usage_metadata=None)


@pytest.fixture
def provider(monkeypatch):
    pytest.importorskip("google.genai")
    from app.ai.providers.gemini import GeminiProvider
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    p = GeminiProvider()
    return p


class TestGeminiRequests:
    def test_extraction_sends_schema_and_inline_images(self, provider, tmp_path):
        image = tmp_path / "page.jpg"
        image.write_bytes(b"\xff\xd8\xff fake jpeg")
        fake = _FakeModels(extraction([problem()]))
        provider._client = SimpleNamespace(models=fake)

        result = asyncio.run(provider.extract_private_tasks([image]))

        assert len(result.problems) == 1
        call = fake.calls[0]
        assert call["config"].response_json_schema == EXTRACTION_SCHEMA
        parts = [c for c in call["contents"] if not isinstance(c, str)]
        assert len(parts) == 1
        assert parts[0].inline_data.data == image.read_bytes()

    def test_meta_is_text_only_with_schema(self, provider):
        fake = _FakeModels(json.dumps({"hints": ["a"], "category": None, "difficulty": 3, "abuse_score": 0}))
        provider._client = SimpleNamespace(models=fake)

        result = asyncio.run(provider.generate_private_task_meta("T", "Treść zadania do rozwiązania."))

        assert result.hints == ["a"]
        call = fake.calls[0]
        assert call["config"].response_json_schema == META_SCHEMA
        assert all(isinstance(c, str) for c in call["contents"])
        assert "Treść zadania do rozwiązania." in call["contents"][0]
