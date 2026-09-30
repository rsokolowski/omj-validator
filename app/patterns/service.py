"""Patterns: task texts for the AI, practice candidates, graded practice results."""

import logging
import re
from datetime import datetime, time, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import storage
from ..db.models import PatternDB, PatternReviewDB, PrivateTaskDB, SubmissionDB, SubmissionStatus
from ..db.patterns import PatternRepository
from ..privacy import mask_user_id
from ..scoring import get_max_score
from . import srs

logger = logging.getLogger(__name__)

# ai_usage.kind values
KIND_REFINE = "pattern_refine"
KIND_SUGGEST = "pattern_suggest"
KIND_LINK = "pattern_link"

PATTERN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12}$")
TASK_KEY_PATTERN = re.compile(r"^(\d{4})_(etap[123])_(\d{1,2})$")

# Private tasks are graded on the 0/2/5/6 scale
PRIVATE_MAX_SCORE = 6


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


def owned_pattern_id(db: Session, user_id: str, raw: Optional[str]) -> Optional[str]:
    """``raw`` if it names one of the user's patterns, else None."""
    if not raw or not PATTERN_ID_PATTERN.match(raw):
        return None
    return raw if PatternRepository(db).get_owned(raw, user_id) is not None else None


def _last_attempts_omj(db: Session, user_id: str) -> dict[tuple[str, str, int], datetime]:
    rows = (
        db.query(SubmissionDB.year, SubmissionDB.etap, SubmissionDB.task_number, func.max(SubmissionDB.timestamp))
        .filter(SubmissionDB.user_id == user_id, SubmissionDB.private_task_id.is_(None))
        .group_by(SubmissionDB.year, SubmissionDB.etap, SubmissionDB.task_number)
        .all()
    )
    return {(y, e, n): ts for y, e, n, ts in rows}


def _last_attempts_private(db: Session, user_id: str) -> dict[str, datetime]:
    rows = (
        db.query(SubmissionDB.private_task_id, func.max(SubmissionDB.timestamp))
        .filter(SubmissionDB.user_id == user_id, SubmissionDB.private_task_id.isnot(None))
        .group_by(SubmissionDB.private_task_id)
        .all()
    )
    return dict(rows)


def _naive(ts: Optional[datetime]) -> Optional[datetime]:
    if ts is None:
        return None
    return ts.astimezone(timezone.utc).replace(tzinfo=None) if ts.tzinfo else ts


def practice_candidates(db: Session, pattern: PatternDB, user_id: str) -> list[srs.PracticeCandidate]:
    """Accepted linked tasks that still exist, with the user's last attempt."""
    omj_attempts = _last_attempts_omj(db, user_id)
    private_attempts = _last_attempts_private(db, user_id)
    candidates = []
    for link in pattern.links:
        if link.status != "accepted":
            continue
        if link.task_key:
            task = omj_task(link.task_key)
            if task is None:
                continue
            last = omj_attempts.get((task.year, task.etap, task.number))
            candidates.append(srs.PracticeCandidate(
                kind="omj", ref=link.task_key, title=task.title,
                difficulty=task.difficulty, last_attempt=_naive(last),
            ))
        else:
            task = db.get(PrivateTaskDB, link.private_task_id)
            if task is None or task.user_id != user_id:
                continue
            candidates.append(srs.PracticeCandidate(
                kind="private", ref=task.id, title=task.title,
                difficulty=task.difficulty, last_attempt=_naive(private_attempts.get(task.id)),
            ))
    return candidates


def _reviewed_on(db: Session, pattern: PatternDB, day) -> bool:
    """Did a recall card or a graded practice already move this pattern on ``day`` (Warsaw)?"""
    start = datetime.combine(day, time.min, tzinfo=srs._WARSAW).astimezone(timezone.utc).replace(tzinfo=None)
    return (
        db.query(PatternReviewDB.id)
        .filter(
            PatternReviewDB.pattern_id == pattern.id,
            PatternReviewDB.created_at >= start,
        )
        .first()
        is not None
    )


def apply_practice_result(db: Session, submission_id: str) -> None:
    """Count a graded practice submission as a review of its pattern.

    A no-op unless the submission completed, names a pattern of the same user,
    and has not been counted yet. Never raises for a missing pattern.
    """
    submission = db.get(SubmissionDB, submission_id)
    if submission is None or submission.pattern_id is None:
        return
    if submission.status != SubmissionStatus.COMPLETED or submission.score is None:
        return
    repo = PatternRepository(db)
    pattern = repo.get_owned(submission.pattern_id, submission.user_id)
    if pattern is None or pattern.archived_at is not None or repo.has_review_for_submission(submission_id):
        return
    today = srs.today_warsaw()
    if _reviewed_on(db, pattern, today):
        # A recall card and then a linked task the same afternoon is not
        # spaced repetition: the schedule moves at most once a day
        logger.info(f"Pattern {pattern.id}: already reviewed today, submission {submission_id} ignored")
        return

    max_score = PRIVATE_MAX_SCORE if submission.private_task_id else get_max_score(submission.etap)
    outcome = srs.outcome_from_grade(submission.score, max_score, submission.hints_used or 0)
    level, streak, due = srs.schedule(pattern.srs_level, pattern.srs_streak, outcome, today)
    repo.apply_review(
        pattern,
        seen_due_on=pattern.due_on,
        new_level=level,
        new_streak=streak,
        new_due=due,
        outcome=outcome,
        kind="task",
        submission_id=submission_id,
        conditional=False,
    )
    logger.info(
        f"Pattern {pattern.id} of user {mask_user_id(submission.user_id)}: practice {outcome} "
        f"(level {level}, next {due.isoformat()})"
    )


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


# Refine rounds sent back to the model (the rest only costs tokens)
HISTORY_ROUNDS_SENT = 3


def compact_history(rounds: list[dict], current_answer: Optional[str] = None) -> list[dict]:
    """Stored/client rounds -> what the model sees: chosen version, questions, answer.

    A round stores the answer sent to REQUEST it, which replied to the round
    before. So round i's questions pair with round i+1's answer, and the last
    round's questions with the answer sent now.
    """
    compacted = []
    recent = rounds[-HISTORY_ROUNDS_SENT:]
    for index, round_ in enumerate(recent):
        variants = round_.get("variants") or []
        chosen = round_.get("chosen")
        picked = variants[chosen] if isinstance(chosen, int) and 0 <= chosen < len(variants) else {}
        reply = recent[index + 1].get("answer") if index + 1 < len(recent) else current_answer
        compacted.append({
            "chosen": dict(picked),
            "questions": list(round_.get("questions") or []),
            "answer": reply,
        })
    return compacted
