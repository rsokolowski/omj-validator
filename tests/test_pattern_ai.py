"""AI layer for patterns: parsing model output and building the requests.

Everything the model returns ends up in front of a student (versions to pick,
suggested patterns, why a task fits), so every field is validated and clamped.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.ai.pattern_parsing import (
    PATTERN_EXERCISES_SCHEMA,
    PATTERN_LINK_SCHEMA,
    PATTERN_REFINE_SCHEMA,
    PATTERN_SUGGEST_SCHEMA,
    parse_exercises_response,
    parse_link_response,
    parse_refine_response,
    parse_suggest_response,
)
from app.ai.prompt_builder import load_private_prompt, validate_prompts
from app.models import EXERCISE_SOLUTION_MAX

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

    def test_variant_tasks_only_from_the_offered_list(self):
        offered = {"2015_etap3_1", "2010_etap3_4"}
        raw = variant(note="Szeroka wersja", tasks=["2015_etap3_1", "2099_etap2_9", "2015_etap3_1", 7])
        [v] = parse_refine_response(refine([raw]), KNOWN_SKILLS, offered).variants
        assert v.tasks == ["2015_etap3_1"]
        assert v.note == "Szeroka wersja"

    def test_reply_drops_invented_task_references(self):
        offered = {"2015_etap3_1"}
        text = refine([variant()], reply="Zobacz [[2015_etap3_1]] oraz [[2019_etap2_5]] - tam też działa.")
        result = parse_refine_response(text, KNOWN_SKILLS, offered)
        assert result.reply == "Zobacz [[2015_etap3_1]] oraz - tam też działa."

    def test_questions_and_comment_drop_invented_task_references(self):
        text = refine([variant()], questions=["Widzisz to w [[2015_etap3_1]]? A w [[2001_etap1_1]]?"],
                      comment="Jak w [[2001_etap1_1]].")
        result = parse_refine_response(text, KNOWN_SKILLS, {"2015_etap3_1"})
        assert result.questions == ["Widzisz to w [[2015_etap3_1]]? A w ?"]
        assert result.comment == "Jak w ."

    def test_missing_reply_and_tasks_are_empty(self):
        result = parse_refine_response(refine([variant()]), KNOWN_SKILLS)
        assert result.reply == ""
        assert result.variants[0].tasks == []

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


def exercise(title="Dwie kolejne", content="Udowodnij, że $n(n+1)$ jest parzyste.", level="easy", answer="Tak",
             solution="Z wzorca: jedna z liczb $n$, $n+1$ jest parzysta."):
    return {"title": title, "content": content, "level": level, "answer": answer, "solution": solution}


class TestParseExercises:
    def test_valid(self):
        result = parse_exercises_response(json.dumps({
            "off_topic": False, "abuse_score": 3,
            "exercises": [exercise(), exercise(title="Trzy", content="Wykaż, że $6 | n^3-n$.", level="medium")],
        }))
        assert [(e.title, e.level) for e in result.exercises] == [("Dwie kolejne", "easy"), ("Trzy", "medium")]
        assert result.exercises[0].answer == "Tak"
        assert (result.off_topic, result.abuse_score) == (False, 3)

    def test_drops_invalid_and_duplicates(self):
        result = parse_exercises_response(json.dumps({
            "off_topic": False, "abuse_score": 0,
            "exercises": [
                exercise(), exercise(title="Kopia", content="  udowodnij, że $n(n+1)$   jest parzyste. "),
                exercise(title=""), exercise(content=""), "x", exercise(title="Inne", content="Oblicz $2+2$.", level="hard"),
            ],
        }))
        assert [e.title for e in result.exercises] == ["Dwie kolejne", "Inne"]
        assert result.exercises[1].level == "medium"

    def test_clamps_lengths_and_count(self):
        result = parse_exercises_response(json.dumps({
            "off_topic": False, "abuse_score": 0,
            "exercises": [exercise(title="t" * 300, content=f"Zadanie {i} " + "x" * 5000, answer="a" * 900)
                          for i in range(15)],
        }))
        assert len(result.exercises) == 10
        assert len(result.exercises[0].title) == 120
        assert len(result.exercises[0].content) == 4000
        assert len(result.exercises[0].answer) == 500

    def test_keeps_solution_and_cuts_it(self):
        result = parse_exercises_response(json.dumps({
            "off_topic": False, "abuse_score": 0,
            "exercises": [exercise(), exercise(title="Długie", content="Oblicz $3+3$.", solution="s" * 3000),
                          {k: v for k, v in exercise(title="Bez", content="Oblicz $4+4$.").items() if k != "solution"}],
        }))
        assert result.exercises[0].solution == "Z wzorca: jedna z liczb $n$, $n+1$ jest parzysta."
        assert len(result.exercises[1].solution) == EXERCISE_SOLUTION_MAX
        assert result.exercises[2].solution == ""

    def test_schema_requires_solution(self):
        item = PATTERN_EXERCISES_SCHEMA["properties"]["exercises"]["items"]
        assert "solution" in item["properties"] and "solution" in item["required"]

    def test_off_topic_and_unreadable(self):
        assert parse_exercises_response(json.dumps({"off_topic": True, "exercises": [], "abuse_score": 0})).off_topic
        result = parse_exercises_response("not json")
        assert result.exercises == [] and not result.off_topic


class TestPrompts:
    def test_all_prompt_files_present(self):
        assert validate_prompts() == []

    def test_pattern_prompts_load(self):
        assert "variants" in load_private_prompt("pattern_refine")
        assert "suggestions" in load_private_prompt("pattern_suggest")
        assert "links" in load_private_prompt("pattern_link")
        assert "exercises" in load_private_prompt("pattern_exercises")

    def test_schemas_do_not_collide_with_private_task_routing(self):
        # e2e/fake-gemini tells calls apart by these property names
        for schema in (PATTERN_REFINE_SCHEMA, PATTERN_SUGGEST_SCHEMA, PATTERN_LINK_SCHEMA, PATTERN_EXERCISES_SCHEMA):
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

        history = [{
            "answers": [], "message": "Pierwsza wiadomość", "draft": {"raw": "szkic"}, "reply": "Odpowiedź AI",
            "verdict": "za_ogolny", "comment": "c",
            "variants": [{"trigger": "Trig A", "action": "Akcja A", "note": "szeroka", "tasks": ["2024_etap1_1"]}],
            "questions": ["Pytanie AI?"], "chosen": None,
        }]
        result = asyncio.run(provider.refine_pattern(
            {"raw": "Jak jest parzystość to patrz na sumę"},
            "Treść wymyślonego zadania o żetonach.",
            history,
            {"answers": [{"question": "Pytanie AI?", "answer": "Tak, dla iloczynu"}],
             "message": "Chodzi mi o sumę wszystkich liczb"},
            [{"task_key": "2024_etap1_1", "difficulty": 2, "categories": ["logika"], "hints": ["h2"]}],
        ))

        assert len(result.variants) == 2
        call = fake.calls[0]
        assert call["config"].response_json_schema == PATTERN_REFINE_SCHEMA
        assert all(isinstance(c, str) for c in call["contents"])
        prompt = call["contents"][0]
        assert "Jak jest parzystość to patrz na sumę" in prompt
        assert "Treść wymyślonego zadania o żetonach." in prompt
        assert "Chodzi mi o sumę wszystkich liczb" in prompt
        assert "Tak, dla iloczynu" in prompt
        # The model sees its own earlier versions and reply, and the task list
        assert "Trig A" in prompt and "Odpowiedź AI" in prompt
        assert "Uczeń nie wybrał żadnej wersji" in prompt
        assert "2024_etap1_1 | trudność 2 | logika | h2" in prompt

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

    def test_exercises_fence_pattern_and_previous(self, provider):
        fake = _FakeModels(json.dumps({"off_topic": False, "exercises": [exercise()], "abuse_score": 0}))
        provider._client = SimpleNamespace(models=fake)

        result = asyncio.run(provider.generate_pattern_exercises(
            {"trigger": "Kolejne liczby", "action": "Szukaj parzystej", "example": ""},
            5,
            ["Wcześniejsze ćwiczenie o sumie."],
        ))

        assert [e.title for e in result.exercises] == ["Dwie kolejne"]
        call = fake.calls[0]
        assert call["config"].response_json_schema == PATTERN_EXERCISES_SCHEMA
        prompt = call["contents"][0]
        assert "## Liczba ćwiczeń\n5" in prompt
        assert "Wyzwalacz: Kolejne liczby" in prompt
        assert "1. Wcześniejsze ćwiczenie o sumie." in prompt
        # Pattern text and earlier exercises are both fenced (+1: the rule naming the fence)
        assert prompt.count("<<<") == 3
