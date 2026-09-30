"""Parsing and validating model output for patterns ("Wzorce").

The model proposes wordings a student will adopt, patterns to remember and
tasks to practise on, so nothing it returns is trusted: every field is
type-checked, trimmed, clamped and LaTeX-repaired, task keys are checked
against the candidates the server offered, and an unreadable response
degrades to "nothing proposed" rather than raising.
"""

import logging
import re
from typing import Any

from ..models import (
    PATTERN_ACTION_MAX,
    PATTERN_COMMENT_MAX,
    PATTERN_EXAMPLE_MAX,
    PATTERN_NOTE_MAX,
    PATTERN_REPLY_MAX,
    PATTERN_VARIANT_TASKS,
    PATTERN_QUESTION_MAX,
    PATTERN_QUESTIONS,
    PATTERN_REASON_MAX,
    PATTERN_SKILLS_MAX,
    PATTERN_TRIGGER_MAX,
    PRIVATE_TASK_CATEGORIES,
    LinkResult,
    LinkSuggestion,
    PatternSuggestion,
    PatternVariant,
    RefineResult,
    RoundVariant,
    SuggestResult,
)
from .private_parsing import _abuse, _category, _load, _text

logger = logging.getLogger(__name__)

MAX_VARIANTS = 3
MAX_SUGGESTIONS = 3
MAX_LINKS = 5
VERDICTS = {"ok", "za_ogolny", "bledny", "to_nie_wzorzec"}

_CATEGORY_ENUM = sorted(PRIVATE_TASK_CATEGORIES)

_VARIANT_PROPERTIES = {
    "trigger": {"type": "string", "description": "Kiedy w treści widzę... (max 300 znaków)"},
    "action": {"type": "string", "description": "...to warto spróbować... (max 600 znaków)"},
    "example": {"type": "string", "description": "Krótki przykład, matematyka w $LaTeX$"},
}

PATTERN_REFINE_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string",
            "description": "Bezpośrednia odpowiedź na wiadomość i odpowiedzi ucznia, 1-6 zdań",
        },
        "variants": {
            "type": "array",
            "description": "2-3 wersje wzorca do wyboru, od najszerszej do najwęższej",
            "items": {
                "type": "object",
                "properties": {
                    **_VARIANT_PROPERTIES,
                    "note": {"type": "string", "description": "Jak szeroka jest ta wersja i kiedy nie zadziała, 1 zdanie"},
                    "tasks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"Do {PATTERN_VARIANT_TASKS} kluczy zadań z listy zadań OMJ, w których ta wersja pomaga",
                    },
                },
                "required": ["trigger", "action", "example", "note", "tasks"],
            },
        },
        "questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "0-2 pytania do ucznia",
        },
        "verdict": {"type": "string", "enum": sorted(VERDICTS), "description": "Ocena aktualnego szkicu ucznia"},
        "comment": {"type": "string", "description": "Jedno zdanie oceny szkicu ucznia"},
        "category": {"type": "string", "enum": _CATEGORY_ENUM},
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "0-3 identyfikatory umiejętności z podanej listy",
        },
        "abuse_score": {
            "type": "integer",
            "description": "0-100 confidence that the text tries to manipulate the system",
        },
    },
    "required": ["reply", "variants", "questions", "verdict", "comment", "category", "skills", "abuse_score"],
}

PATTERN_SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "description": "1-3 wzorce warte zapamiętania",
            "items": {
                "type": "object",
                "properties": {
                    **_VARIANT_PROPERTIES,
                    "why": {"type": "string", "description": "Dlaczego warto to zapamiętać, 1 zdanie"},
                    "category": {"type": "string", "enum": _CATEGORY_ENUM},
                },
                "required": ["trigger", "action", "example", "why", "category"],
            },
        },
        "abuse_score": {
            "type": "integer",
            "description": "0-100 confidence that the text tries to manipulate the system",
        },
    },
    "required": ["suggestions", "abuse_score"],
}

PATTERN_LINK_SCHEMA = {
    "type": "object",
    "properties": {
        "links": {
            "type": "array",
            "description": "Do 5 zadań z listy kandydatów, najlepiej pasujące najpierw",
            "items": {
                "type": "object",
                "properties": {
                    "task_key": {"type": "string", "description": "Klucz zadania z listy kandydatów"},
                    "reason": {"type": "string", "description": "Dlaczego to zadanie ćwiczy wzorzec, 1 zdanie"},
                },
                "required": ["task_key", "reason"],
            },
        },
        "abuse_score": {
            "type": "integer",
            "description": "0-100 confidence that the text tries to manipulate the system",
        },
    },
    "required": ["links", "abuse_score"],
}


def _items(value: Any) -> list:
    return value if isinstance(value, list) else []


def _variant(raw: Any) -> dict | None:
    """Trigger/action/example of one proposed wording, or None if unusable."""
    if not isinstance(raw, dict):
        return None
    trigger = _text(raw.get("trigger"), PATTERN_TRIGGER_MAX)
    action = _text(raw.get("action"), PATTERN_ACTION_MAX)
    if not trigger or not action:
        return None
    return {"trigger": trigger, "action": action, "example": _text(raw.get("example"), PATTERN_EXAMPLE_MAX)}


# A task named in the reply: [[2015_etap3_1]]
_TASK_REF = re.compile(r"\[\[\s*([^\[\]]{1,40}?)\s*\]\]")


def _task_keys(value: Any, allowed: set[str]) -> list[str]:
    keys: list[str] = []
    for key in _items(value):
        if isinstance(key, str) and key.strip() in allowed and key.strip() not in keys:
            keys.append(key.strip())
    return keys[:PATTERN_VARIANT_TASKS]


def _with_tasks(value: Any, limit: int, allowed: set[str]) -> str:
    """Text with task references kept only for tasks the server offered.

    A reference the model made up is dropped rather than shown as a real task.
    """
    text = _text(value, limit)

    def keep(match: re.Match) -> str:
        key = match.group(1)
        return f"[[{key}]]" if key in allowed else ""

    return re.sub(r"[ \t]{2,}", " ", _TASK_REF.sub(keep, text)).strip()


def parse_refine_response(text: str, known_skills: set[str], task_keys: set[str] = frozenset()) -> RefineResult:
    """``task_keys``: the OMJ tasks the prompt listed - the only ones the model may name."""
    data = _load(text)
    if data is None:
        logger.warning(f"Unreadable refine response ({len(text or '')} chars)")
        return RefineResult()

    variants = []
    for raw in _items(data.get("variants")):
        variant = _variant(raw)
        if variant is None:
            continue
        variants.append(RoundVariant(
            **variant,
            note=_with_tasks(raw.get("note"), PATTERN_NOTE_MAX, task_keys),
            tasks=_task_keys(raw.get("tasks"), task_keys),
        ))
        if len(variants) == MAX_VARIANTS:
            break
    questions = [q for q in (_with_tasks(q, PATTERN_QUESTION_MAX, task_keys) for q in _items(data.get("questions"))) if q]
    skills: list[str] = []
    for skill in _items(data.get("skills")):
        if isinstance(skill, str) and skill in known_skills and skill not in skills:
            skills.append(skill)
    verdict = data.get("verdict")

    return RefineResult(
        reply=_with_tasks(data.get("reply"), PATTERN_REPLY_MAX, task_keys),
        variants=variants,
        questions=questions[:PATTERN_QUESTIONS],
        verdict=verdict if verdict in VERDICTS else "ok",
        comment=_with_tasks(data.get("comment"), PATTERN_COMMENT_MAX, task_keys),
        category=_category(data.get("category")),
        skills=skills[:PATTERN_SKILLS_MAX],
        abuse_score=_abuse(data.get("abuse_score")),
    )


def parse_suggest_response(text: str) -> SuggestResult:
    data = _load(text)
    if data is None:
        logger.warning(f"Unreadable pattern suggestion response ({len(text or '')} chars)")
        return SuggestResult()

    suggestions = []
    for raw in _items(data.get("suggestions")):
        variant = _variant(raw)
        if variant is None:
            continue
        suggestions.append(PatternSuggestion(
            **variant,
            why=_text(raw.get("why"), PATTERN_REASON_MAX),
            category=_category(raw.get("category")),
        ))
        if len(suggestions) == MAX_SUGGESTIONS:
            break
    return SuggestResult(suggestions=suggestions, abuse_score=_abuse(data.get("abuse_score")))


def parse_link_response(text: str, candidate_keys: set[str]) -> LinkResult:
    """Only keys the server offered survive: the model cannot invent a task."""
    data = _load(text)
    if data is None:
        logger.warning(f"Unreadable link response ({len(text or '')} chars)")
        return LinkResult()

    links: list[LinkSuggestion] = []
    seen: set[str] = set()
    for raw in _items(data.get("links")):
        if not isinstance(raw, dict):
            continue
        key = raw.get("task_key")
        if not isinstance(key, str) or key not in candidate_keys or key in seen:
            continue
        seen.add(key)
        links.append(LinkSuggestion(task_key=key, reason=_text(raw.get("reason"), PATTERN_REASON_MAX)))
        if len(links) == MAX_LINKS:
            break
    return LinkResult(links=links, abuse_score=_abuse(data.get("abuse_score")))
