"""AI layer for patterns: parsing model output and building the requests.

Everything the model returns ends up in front of a student (versions to pick,
suggested patterns, why a task fits), so every field is validated and clamped.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.ai.pattern_parsing import (
    PATTERN_LINK_SCHEMA,
    PATTERN_REFINE_SCHEMA,
    PATTERN_SUGGEST_SCHEMA,
    parse_link_response,
    parse_refine_response,
    parse_suggest_response,
)
from app.ai.prompt_builder import load_private_prompt, validate_prompts

KNOWN_SKILLS = {"parity", "modular_arithmetic", "invariants", "pigeonhole"}


def variant(**overrides):
    base = {
        "trigger": "Pytają, czy da się dojść do pewnego stanu",
        "action": "Szukaj niezmiennika, np. parzystości sumy",
        "example": "Suma $a+b$ nie zmienia parzystości",
    }
    base.update(overrides)
    return base


def refine(variants, **overrides):
    base = {
        "variants": variants,
        "questions": ["Czy to działa też dla iloczynu?"],
        "verdict": "ok",
        "comment": "Dobry wzorzec.",
        "category": "kombinatoryka",
        "skills": ["parity"],
        "abuse_score": 0,
    }
    base.update(overrides)
    return json.dumps(base, ensure_ascii=False)


class TestRefineParsing:
    def test_valid_round(self):
        result = parse_refine_response(refine([variant(), variant(action="Inna akcja do wypróbowania")]), KNOWN_SKILLS)
        assert len(result.variants) == 2
        assert result.questions == ["Czy to działa też dla iloczynu?"]
        assert result.verdict == "ok"
        assert result.category == "kombinatoryka"
        assert result.skills == ["parity"]

    def test_more_than_three_variants_truncated(self):
        result = parse_refine_response(refine([variant() for _ in range(5)]), KNOWN_SKILLS)
        assert len(result.variants) == 3

    def test_variant_without_action_dropped(self):
        result = parse_refine_response(refine([variant(action="  "), variant()]), KNOWN_SKILLS)
        assert len(result.variants) == 1

    def test_overlong_fields_are_cut(self):
        result = parse_refine_response(
            refine([variant(trigger="x" * 500, action="y" * 900, example="z" * 2000)]), KNOWN_SKILLS
        )
        v = result.variants[0]
        assert (len(v.trigger), len(v.action), len(v.example)) == (300, 600, 1000)

    def test_questions_limited_to_two_and_cut(self):
        result = parse_refine_response(
            refine([variant()], questions=["a" * 400, "b", "c", 5]), KNOWN_SKILLS
        )
        assert result.questions == ["a" * 300, "b"]

    def test_unknown_verdict_and_category(self):
        result = parse_refine_response(refine([variant()], verdict="great", category="calculus"), KNOWN_SKILLS)
        assert result.verdict == "ok"
        assert result.category is None

    def test_known_verdicts_kept(self):
        for verdict in ("za_ogolny", "bledny", "to_nie_wzorzec"):
            assert parse_refine_response(refine([variant()], verdict=verdict), KNOWN_SKILLS).verdict == verdict

    def test_skills_filtered_and_limited(self):
        result = parse_refine_response(
            refine([variant()], skills=["parity", "made_up", "invariants", "pigeonhole", "modular_arithmetic"]),
            KNOWN_SKILLS,
        )
        assert result.skills == ["parity", "invariants", "pigeonhole"]

    def test_abuse_clamped(self):
        assert parse_refine_response(refine([variant()], abuse_score=300), KNOWN_SKILLS).abuse_score == 100

    def test_single_backslash_latex_repaired(self):
        raw = (
            '{"variants": [{"trigger": "Ułamki", "action": "Sprowadź do wspólnego mianownika", '
            '"example": "$\\frac{1}{2}+\\frac{1}{3}$"}], "questions": [], "verdict": "ok", '
            '"comment": "", "category": null, "skills": [], "abuse_score": 0}'
        )
        result = parse_refine_response(raw, KNOWN_SKILLS)
        assert "\\frac{1}{2}" in result.variants[0].example

    def test_garbage_gives_no_variants(self):
        result = parse_refine_response("Nie mogę pomóc.", KNOWN_SKILLS)
        assert result.variants == []
        assert result.abuse_score == 0


class TestSuggestParsing:
    def suggest(self, suggestions, abuse=0):
        return json.dumps({"suggestions": suggestions, "abuse_score": abuse}, ensure_ascii=False)

    def test_valid(self):
        result = parse_suggest_response(self.suggest([{**variant(), "why": "Pojawia się często.", "category": "algebra"}]))
        assert result.suggestions[0].why == "Pojawia się często."
        assert result.suggestions[0].category == "algebra"

    def test_suggestion_unknown_category_dropped(self):
        result = parse_suggest_response(self.suggest([{**variant(), "category": "chemia"}]))
        assert result.suggestions[0].category is None

    def test_truncated_and_blank_dropped(self):
        items = [{**variant(), "why": "w" * 400}] * 4 + [{**variant(trigger=""), "why": ""}]
        result = parse_suggest_response(self.suggest(items))
        assert len(result.suggestions) == 3
        assert len(result.suggestions[0].why) == 300

    def test_garbage(self):
        assert parse_suggest_response("{").suggestions == []


class TestLinkParsing:
    def link(self, links, abuse=0):
        return json.dumps({"links": links, "abuse_score": abuse}, ensure_ascii=False)

    def test_keys_outside_candidates_and_duplicates_dropped(self):
        result = parse_link_response(
            self.link([
                {"task_key": "2024_etap1_1", "reason": "Parzystość."},
                {"task_key": "1999_etap9_9", "reason": "Wymyślone."},
                {"task_key": "2024_etap1_1", "reason": "Znowu."},
            ]),
            {"2024_etap1_1", "2023_etap2_3"},
        )
        assert [(l.task_key, l.reason) for l in result.links] == [("2024_etap1_1", "Parzystość.")]

    def test_at_most_five_and_reason_cut(self):
        keys = {f"2024_etap1_{i}" for i in range(1, 9)}
        result = parse_link_response(
            self.link([{"task_key": k, "reason": "r" * 400} for k in sorted(keys)]), keys
        )
        assert len(result.links) == 5
        assert len(result.links[0].reason) == 300


class TestPrompts:
    def test_all_prompt_files_present(self):
        assert validate_prompts() == []

    def test_pattern_prompts_load(self):
        assert "variants" in load_private_prompt("pattern_refine")
        assert "suggestions" in load_private_prompt("pattern_suggest")
        assert "links" in load_private_prompt("pattern_link")

    def test_schemas_do_not_collide_with_private_task_routing(self):
        # e2e/fake-gemini tells calls apart by these property names
        for schema in (PATTERN_REFINE_SCHEMA, PATTERN_SUGGEST_SCHEMA, PATTERN_LINK_SCHEMA):
            properties = json.dumps(schema)
            assert '"hints"' not in properties
            assert "is_math_problem" not in properties


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
    return GeminiProvider()


class TestGeminiRequests:
    def test_refine_sends_text_only_with_schema(self, provider):
        fake = _FakeModels(refine([variant(), variant()]))
        provider._client = SimpleNamespace(models=fake)

        result = asyncio.run(provider.refine_pattern(
            {"raw": "Jak jest parzystość to patrz na sumę"},
            "Treść wymyślonego zadania o żetonach.",
            [{"chosen": {"trigger": "t", "action": "a"}, "questions": ["q?"], "answer": "tak"}],
            "Chodzi mi o sumę wszystkich liczb",
        ))

        assert len(result.variants) == 2
        call = fake.calls[0]
        assert call["config"].response_json_schema == PATTERN_REFINE_SCHEMA
        assert all(isinstance(c, str) for c in call["contents"])
        prompt = call["contents"][0]
        assert "Jak jest parzystość to patrz na sumę" in prompt
        assert "Treść wymyślonego zadania o żetonach." in prompt
        assert "Chodzi mi o sumę wszystkich liczb" in prompt

    def test_suggest_sends_feedback(self, provider):
        fake = _FakeModels(json.dumps({"suggestions": [{**variant(), "why": "w"}], "abuse_score": 0}))
        provider._client = SimpleNamespace(models=fake)

        result = asyncio.run(provider.suggest_patterns("Treść zadania.", "Uczeń użył parzystości.", None))

        assert len(result.suggestions) == 1
        call = fake.calls[0]
        assert call["config"].response_json_schema == PATTERN_SUGGEST_SCHEMA
        assert "Uczeń użył parzystości." in call["contents"][0]

    def test_link_lists_candidates(self, provider):
        fake = _FakeModels(json.dumps({"links": [{"task_key": "2024_etap1_1", "reason": "r"}], "abuse_score": 0}))
        provider._client = SimpleNamespace(models=fake)
        candidates = [
            {"task_key": "2024_etap1_1", "difficulty": 2, "categories": ["logika"], "hints": ["h2", "h3"]},
            {"task_key": "2023_etap2_3", "difficulty": 4, "categories": ["algebra"], "hints": ["x", "y"]},
        ]

        result = asyncio.run(provider.link_pattern_tasks(
            {"trigger": "t", "action": "a", "example": ""}, candidates
        ))

        assert [l.task_key for l in result.links] == ["2024_etap1_1"]
        call = fake.calls[0]
        assert call["config"].response_json_schema == PATTERN_LINK_SCHEMA
        assert "2023_etap2_3" in call["contents"][0]
