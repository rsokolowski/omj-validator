"""Patterns: task texts for the AI and the exercises a review card offers."""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from .. import storage
from ..db.models import PatternDB, PatternReviewDB, PrivateTaskDB, SubmissionDB, SubmissionStatus
from . import srs

logger = logging.getLogger(__name__)

# ai_usage.kind values
KIND_REFINE = "pattern_refine"
KIND_SUGGEST = "pattern_suggest"
KIND_LINK = "pattern_link"
KIND_EXERCISES = "pattern_exercises"

# private_tasks.origin of a generated exercise
EXERCISE_ORIGIN = "exercise"

PATTERN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12}$")
TASK_KEY_PATTERN = re.compile(r"^(\d{4})_(etap[123])_(\d{1,2})$")


def parse_task_key(key: Optional[str]) -> Optional[tuple[str, str, int]]:
    match = TASK_KEY_PATTERN.match(key or "")
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def omj_task(key: Optional[str]):
    """The loaded OMJ task for a key, or None (unknown or malformed key)."""
    parsed = parse_task_key(key)
    return storage.get_task(*parsed) if parsed else None


def omj_task_text(key: str) -> Optional[str]:
    """Statement for the AI; title + our hints when the statement is not generated."""
    task = omj_task(key)
    if task is None:
        return None
    if task.content:
        return f"{task.title}\n\n{task.content}"
    hints = "\n".join(f"- {h}" for h in task.hints)
    return f"{task.title} (treść niedostępna, wskazówki do zadania:)\n{hints}"


def private_task_text(task: PrivateTaskDB) -> str:
    return f"{task.title}\n\n{task.content}"


def pattern_is_due(pattern: PatternDB) -> bool:
    """Waits for a review today (and is not paused)."""
    return pattern.archived_at is None and pattern.due_on <= srs.today_warsaw()


def usable_exercises(db: Session, pattern: PatternDB) -> list[PrivateTaskDB]:
    """The pattern's usable exercises (not marked broken), oldest first."""
    return (
        db.query(PrivateTaskDB)
        .filter(
            PrivateTaskDB.pattern_id == pattern.id,
            PrivateTaskDB.user_id == pattern.user_id,
            PrivateTaskDB.origin == EXERCISE_ORIGIN,
            PrivateTaskDB.rejected_at.is_(None),
        )
        .order_by(PrivateTaskDB.created_at, PrivateTaskDB.id)
        .all()
    )


def exercise_states(db: Session, pattern: PatternDB) -> tuple[list[PrivateTaskDB], list[srs.ExerciseState]]:
    """Usable exercises and how each was last reviewed.

    History comes from exercise reviews; an exercise graded before reviews
    became self-rated (2026-10-22) counts by its latest graded submission:
    0 points is a failure, anything else a success.
    """
    tasks = usable_exercises(db, pattern)
    if not tasks:
        return [], []
    ids = [t.id for t in tasks]
    last: dict[str, tuple[str, datetime]] = {}
    for task_id, outcome, created_at in (
        db.query(SubmissionDB.private_task_id, SubmissionDB.score, SubmissionDB.timestamp)
        .filter(
            SubmissionDB.private_task_id.in_(ids),
            SubmissionDB.status == SubmissionStatus.COMPLETED,
            SubmissionDB.score.isnot(None),
        )
        .order_by(SubmissionDB.timestamp)
    ):
        last[task_id] = ("fail" if outcome <= 0 else "ok", _naive(created_at))
    for task_id, outcome, created_at in (
        db.query(PatternReviewDB.private_task_id, PatternReviewDB.outcome, PatternReviewDB.created_at)
        .filter(PatternReviewDB.pattern_id == pattern.id, PatternReviewDB.private_task_id.in_(ids))
        .order_by(PatternReviewDB.id)
    ):
        last[task_id] = (outcome, created_at)
    states = [
        srs.ExerciseState(
            id=t.id,
            level=t.exercise_level or "medium",
            created_at=t.created_at,
            last_outcome=last.get(t.id, (None, None))[0],
            last_reviewed_at=last.get(t.id, (None, None))[1],
        )
        for t in tasks
    ]
    return tasks, states


def owned_exercise(db: Session, pattern: PatternDB, exercise_id: Optional[str]) -> Optional[PrivateTaskDB]:
    """A usable exercise of ``pattern``, or None (unknown, foreign, broken, not an exercise)."""
    if not exercise_id:
        return None
    task = db.get(PrivateTaskDB, exercise_id)
    if (
        task is None
        or task.pattern_id != pattern.id
        or task.user_id != pattern.user_id
        or task.origin != EXERCISE_ORIGIN
        or task.rejected_at is not None
    ):
        return None
    return task


def _naive(ts: Optional[datetime]) -> Optional[datetime]:
    if ts is None:
        return None
    return ts.astimezone(timezone.utc).replace(tzinfo=None) if ts.tzinfo else ts


def all_omj_tasks() -> list:
    """Every loaded OMJ task (metadata; statements may be missing)."""
    return list(storage._load_all_tasks().values())


def solved_omj_keys(db: Session, user_id: str) -> set[str]:
    """OMJ task keys the user has a graded submission for."""
    rows = (
        db.query(SubmissionDB.year, SubmissionDB.etap, SubmissionDB.task_number)
        .filter(
            SubmissionDB.user_id == user_id,
            SubmissionDB.private_task_id.is_(None),
            SubmissionDB.status == SubmissionStatus.COMPLETED,
        )
        .distinct()
        .all()
    )
    return {f"{y}_{e}_{n}" for y, e, n in rows}


# Refine rounds sent back to the model; a session keeps at most PATTERN_ROUNDS_MAX
HISTORY_ROUNDS_SENT = 8


def round_answers(questions: list[str], answers: list, legacy_answer: Optional[str] = None) -> list[dict]:
    """Questions paired with the student's answers; unanswered ones are left out.

    Rounds stored before answers were split carry one ``answer`` for all the
    questions - it is then paired with the questions as a whole.
    """
    pairs = []
    for index, question in enumerate(questions):
        answer = answers[index] if index < len(answers) else None
        if answer and answer.strip():
            pairs.append({"question": question, "answer": answer.strip()})
    if not pairs and legacy_answer and legacy_answer.strip() and questions:
        pairs.append({"question": " / ".join(questions), "answer": legacy_answer.strip()})
    return pairs


def compact_history(rounds: list[dict]) -> list[dict]:
    """Stored/client rounds -> the conversation so far, as the model sees it.

    Each turn is what the student sent (answers to the previous round's
    questions, a message, the draft if it changed) and what the AI answered
    (reply, verdict, the versions it offered, questions), then which version
    the student picked. The model needs its own versions to know what
    "wersja 2" means.
    """
    turns = []
    start = max(0, len(rounds) - HISTORY_ROUNDS_SENT)
    previous_draft = rounds[start - 1].get("draft") if start > 0 else None
    for index in range(start, len(rounds)):
        round_ = rounds[index]
        before = rounds[index - 1] if index > 0 else {}
        has_split = bool(round_.get("answers")) or round_.get("message") is not None
        legacy = None if has_split else round_.get("answer")
        answers = round_answers(list(before.get("questions") or []), list(round_.get("answers") or []), legacy)
        message = round_.get("message")
        if legacy and not before.get("questions"):
            message = legacy
        draft = round_.get("draft") or {}
        turns.append({
            "answers": answers,
            "message": (message or "").strip() or None,
            "draft": draft if draft != previous_draft else None,
            "reply": round_.get("reply") or "",
            "verdict": round_.get("verdict") or "ok",
            "comment": round_.get("comment") or "",
            "variants": [
                {k: v.get(k) for k in ("trigger", "action", "note", "tasks")}
                for v in (round_.get("variants") or [])
            ],
            "questions": list(round_.get("questions") or []),
            "chosen": round_.get("chosen"),
        })
        previous_draft = draft
    return turns
