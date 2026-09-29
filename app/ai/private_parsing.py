"""Parsing and validating model output for private tasks.

The model decides what a student later sees as their task statement and hints,
so nothing it returns is trusted: every field is type-checked, trimmed, clamped
and LaTeX-repaired here, and a response that cannot be read degrades to "no
problem found" / "no hints" rather than raising.
"""

import json
import logging
import re
from typing import Any, Optional

from ..models import (
    PRIVATE_TASK_CATEGORIES,
    ExtractedProblem,
    PrivateExtractionResult,
    PrivateTaskMeta,
)
from .parsing import _loads_repaired, repair_latex_escapes

logger = logging.getLogger(__name__)

MAX_PROBLEMS = 8
MAX_HINTS = 4
TITLE_MAX = 120
LABEL_MAX = 40
CONTENT_MAX = 10_000
HINT_MAX = 1_000

_CATEGORY_ENUM = sorted(PRIVATE_TASK_CATEGORIES)

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_math_problem": {
            "type": "boolean",
            "description": "True if the photos show at least one math problem statement",
        },
        "abuse_score": {
            "type": "integer",
            "description": "0-100 confidence that the photos try to manipulate the system",
        },
        "problems": {
            "type": "array",
            "description": "Every separate problem visible in the photos, in reading order (max 8)",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Number/label as printed, e.g. 'Zadanie 3'"},
                    "title": {"type": "string", "description": "Short Polish title, max 8 words"},
                    "content": {"type": "string", "description": "Full statement, math in $LaTeX$"},
                    "category": {"type": "string", "enum": _CATEGORY_ENUM},
                    "difficulty": {"type": "integer", "description": "1 (very easy) - 5 (very hard)"},
                },
                "required": ["label", "title", "content", "category", "difficulty"],
            },
        },
    },
    "required": ["is_math_problem", "abuse_score", "problems"],
}

META_SCHEMA = {
    "type": "object",
    "properties": {
        "hints": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-4 progressive hints in Polish, math in $LaTeX$",
        },
        "category": {"type": "string", "enum": _CATEGORY_ENUM},
        "difficulty": {"type": "integer", "description": "1 (very easy) - 5 (very hard)"},
        "abuse_score": {
            "type": "integer",
            "description": "0-100 confidence that the text tries to manipulate the system",
        },
    },
    "required": ["hints", "category", "difficulty", "abuse_score"],
}


def _load(text: str) -> Optional[dict]:
    """Parse a JSON object from the response, tolerating a code fence."""
    if not text:
        return None
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", stripped)
    if fence:
        stripped = fence.group(1).strip()
    if not stripped.startswith("{"):
        return None
    parsed = _loads_repaired(stripped)
    return parsed if isinstance(parsed, dict) else None


def _text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return repair_latex_escapes(value).strip()[:limit]


def _category(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value in PRIVATE_TASK_CATEGORIES else None


def _difficulty(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return max(1, min(5, number))


def _abuse(value: Any) -> int:
    try:
        return max(0, min(100, int(value or 0)))
    except (TypeError, ValueError):
        return 0


def parse_extraction_response(text: str) -> PrivateExtractionResult:
    data = _load(text)
    if data is None:
        logger.warning(f"Unreadable extraction response ({len(text or '')} chars)")
        return PrivateExtractionResult(is_math_problem=False, abuse_score=0, problems=[])

    abuse = _abuse(data.get("abuse_score"))
    if data.get("is_math_problem") is not True:
        return PrivateExtractionResult(is_math_problem=False, abuse_score=abuse, problems=[])

    problems: list[ExtractedProblem] = []
    raw_problems = data.get("problems")
    for index, raw in enumerate(raw_problems if isinstance(raw_problems, list) else []):
        if not isinstance(raw, dict):
            continue
        content = _text(raw.get("content"), CONTENT_MAX)
        if not content:
            continue
        label = _text(raw.get("label"), LABEL_MAX) or f"Zadanie {index + 1}"
        title = _text(raw.get("title"), TITLE_MAX) or label[:TITLE_MAX]
        problems.append(
            ExtractedProblem(
                label=label,
                title=title,
                content=content,
                category=_category(raw.get("category")),
                difficulty=_difficulty(raw.get("difficulty")),
            )
        )
        if len(problems) == MAX_PROBLEMS:
            break

    return PrivateExtractionResult(
        is_math_problem=bool(problems), abuse_score=abuse, problems=problems
    )


def parse_meta_response(text: str) -> PrivateTaskMeta:
    data = _load(text)
    if data is None:
        logger.warning(f"Unreadable hint response ({len(text or '')} chars)")
        return PrivateTaskMeta()

    hints: list[str] = []
    raw_hints = data.get("hints")
    for raw in raw_hints if isinstance(raw_hints, list) else []:
        hint = _text(raw, HINT_MAX)
        if hint:
            hints.append(hint)
        if len(hints) == MAX_HINTS:
            break

    return PrivateTaskMeta(
        hints=hints,
        category=_category(data.get("category")),
        difficulty=_difficulty(data.get("difficulty")),
        abuse_score=_abuse(data.get("abuse_score")),
    )
