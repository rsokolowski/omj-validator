"""Model output gates: abuse score on grading, "is it maths" on hints, off-topic on refine."""

import json

import pytest

from app.ai.parsing import INJECTION_FEEDBACK, WRONG_TASK_FEEDBACK, parse_ai_response
from app.ai.pattern_parsing import PATTERN_REFINE_SCHEMA, parse_refine_response
from app.ai.private_parsing import META_SCHEMA, parse_meta_response
from app.config import settings
from app.models import IssueType


def grade(issue_type="none", abuse_score=0, score=6):
    return json.dumps({"score": score, "feedback": "Świetnie.", "issue_type": issue_type, "abuse_score": abuse_score})


# --------------------------------------------------------------- grading


@pytest.mark.parametrize("abuse", [70, 85, 100])
def test_high_abuse_score_forces_zero_whatever_issue_type(abuse, monkeypatch):
    monkeypatch.setattr(settings, "private_abuse_threshold", 70)
    result = parse_ai_response(grade("none", abuse, 6), etap="etap2")
    assert result.score == 0
    assert result.feedback == INJECTION_FEEDBACK
    assert result.issue_type == IssueType.INJECTION
    assert result.abuse_score == abuse


def test_below_threshold_is_graded_normally(monkeypatch):
    monkeypatch.setattr(settings, "private_abuse_threshold", 70)
    result = parse_ai_response(grade("none", 69, 6), etap="etap2")
    assert result.score == 6
    assert result.issue_type == IssueType.NONE


def test_wrong_task_keeps_its_helpful_message_at_high_confidence(monkeypatch):
    """abuse_score is the detection confidence for wrong_task, not manipulation."""
    monkeypatch.setattr(settings, "private_abuse_threshold", 70)
    result = parse_ai_response(grade("wrong_task", 90, 6), etap="etap2")
    assert result.score == 0
    assert result.feedback == WRONG_TASK_FEEDBACK
    assert result.issue_type == IssueType.WRONG_TASK


def test_injection_at_low_confidence_is_still_injection():
    result = parse_ai_response(grade("injection", 10, 6), etap="etap2")
    assert result.score == 0 and result.feedback == INJECTION_FEEDBACK


# ----------------------------------------------------------------- hints


def test_meta_schema_asks_whether_it_is_maths():
    assert "is_math_problem" in META_SCHEMA["required"]


def test_meta_parse_marks_a_read_response_checked():
    meta = parse_meta_response(json.dumps({
        "is_math_problem": True, "hints": ["a", "b"], "category": "algebra", "difficulty": 2, "abuse_score": 0,
    }))
    assert meta.checked is True and meta.is_math_problem is True and meta.hints == ["a", "b"]


@pytest.mark.parametrize("text", ["", "not json", "[]"])
def test_unreadable_meta_is_not_checked(text):
    meta = parse_meta_response(text)
    assert meta.checked is False
    assert meta.hints == []


def test_not_maths_drops_any_hints():
    meta = parse_meta_response(json.dumps({"is_math_problem": False, "hints": ["x"], "abuse_score": 0}))
    assert meta.checked is True
    assert meta.is_math_problem is False
    assert meta.hints == []


def test_without_the_flag_empty_hints_mean_not_maths():
    meta = parse_meta_response(json.dumps({"hints": [], "abuse_score": 0}))
    assert meta.is_math_problem is False


def test_flag_true_without_hints_is_a_glitch_not_a_refusal():
    meta = parse_meta_response(json.dumps({"is_math_problem": True, "hints": [], "abuse_score": 0}))
    assert meta.is_math_problem is True and meta.hints == []


# ---------------------------------------------------------------- refine


def test_refine_schema_has_off_topic():
    assert "off_topic" in PATTERN_REFINE_SCHEMA["required"]
    assert PATTERN_REFINE_SCHEMA["properties"]["off_topic"]["type"] == "boolean"


@pytest.mark.parametrize("value, expected", [(True, True), (False, False), ("true", False), (None, False)])
def test_refine_off_topic_parsed_strictly(value, expected):
    result = parse_refine_response(json.dumps({"reply": "r", "variants": [], "off_topic": value}), set())
    assert result.off_topic is expected


def test_refine_prompt_limits_the_conversation_to_maths():
    from app.ai.prompt_builder import load_private_prompt

    prompt = load_private_prompt("pattern_refine")
    assert "WYŁĄCZNIE o matematyce" in prompt
    assert '"off_topic": true' in prompt
