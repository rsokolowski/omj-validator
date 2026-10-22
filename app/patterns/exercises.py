"""Drill exercises for a pattern ("Ćwiczenia do wzorca"), generated in the background.

A batch is one model call that writes EXERCISES_PER_BATCH short exercises
drilling the pattern, from a near-direct application to ones where the trigger
is a little hidden. Each exercise is saved as a private task that remembers its
pattern (``pattern_id``, ``exercise_level``, ``answer``, ``solution``) and is
linked to it (``pattern_links.origin == "exercise"``). The review card offers
them one per review (``service.exercise_states``) and starts a new batch when
few unseen ones are left (``maybe_top_up``); they are never shown as tasks.

The call runs as an in-process asyncio task with its own DB session (the API
runs a single worker, like grading). A ``pattern_exercise_batches`` row tells
what is going on: ``running``, then ``done`` or ``failed``. A batch a
restart killed is failed at startup; one stuck longer than STALE_AFTER is
failed when somebody looks at it.
"""

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..ai import AIContentBlockedError, AIProviderError, create_ai_provider
from ..config import settings
from ..db import SessionLocal
from ..db.models import (
    AIUsageDB,
    PatternDB,
    PatternExerciseBatchDB,
    PatternLinkDB,
    PrivateTaskDB,
)
from ..db.private_tasks import PrivateTaskRepository
from ..models import EXERCISES_PER_BATCH
from ..privacy import mask_user_id
from ..private_tasks import service as private_service
from .service import KIND_EXERCISES

logger = logging.getLogger(__name__)

RUNNING, DONE, FAILED = "running", "done", "failed"
LINK_ORIGIN = "exercise"
TASK_ORIGIN = "exercise"

# A batch still running after this is treated as lost (the call itself times
# out long before: provider timeout, at most twice with failover)
STALE_AFTER = timedelta(minutes=10)
# Batches younger than this at startup may still belong to the old process
RESTART_GRACE = timedelta(seconds=60)
# A review card starts a new batch once this few unseen exercises are left
TOP_UP_AT = 2
# Earlier exercises sent so a new batch does not repeat them - shortened: the
# model only needs to recognise them, and the prompt must not grow per batch
PREVIOUS_SENT = 30
PREVIOUS_CHARS = 200

ALREADY_RUNNING = "Ćwiczenia do tego wzorca już się układają. Poczekaj chwilę."
ERROR_MESSAGES = {
    "off_topic": (
        "Nie udało się ułożyć ćwiczeń do tego wzorca - sprawdź, czy opisuje "
        "matematyczny sposób rozwiązywania."
    ),
    "refused": "Nie udało się ułożyć ćwiczeń do tego wzorca.",
}
GENERIC_ERROR = "Nie udało się ułożyć ćwiczeń. Spróbuj ponownie."

# Tests swap these: the session the runner opens, and how it is scheduled
session_factory = SessionLocal
_background: set[asyncio.Task] = set()


def spawn(coro) -> None:
    """Run ``coro`` in the background, keeping a reference so it is not GC'd."""
    task = asyncio.get_running_loop().create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _shortened(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= PREVIOUS_CHARS else text[: PREVIOUS_CHARS - 1] + "…"


# ---------------------------------------------------------------- reading


def expire_stale(db: Session, *, user_id: Optional[str] = None, older_than: timedelta = STALE_AFTER) -> int:
    """Fail running batches started before ``older_than`` ago; returns how many."""
    query = db.query(PatternExerciseBatchDB).filter(
        PatternExerciseBatchDB.status == RUNNING,
        PatternExerciseBatchDB.created_at < _now() - older_than,
    )
    if user_id is not None:
        query = query.filter(PatternExerciseBatchDB.user_id == user_id)
    stale = query.all()
    for batch in stale:
        batch.status, batch.error, batch.finished_at = FAILED, "interrupted", _now()
    if stale:
        db.commit()
    return len(stale)


def latest_batch(db: Session, pattern_id: str) -> Optional[PatternExerciseBatchDB]:
    return (
        db.query(PatternExerciseBatchDB)
        .filter(PatternExerciseBatchDB.pattern_id == pattern_id)
        .order_by(PatternExerciseBatchDB.created_at.desc())
        .first()
    )


# ---------------------------------------------------------------- starting


def start_batch(db: Session, pattern: PatternDB, user_id: str, is_allowlisted: bool) -> PatternExerciseBatchDB:
    """Reserve the call and start a batch in the background.

    Raises 409 while another batch of this pattern runs and 429 at a limit
    (nothing is reserved then).
    """
    expire_stale(db, user_id=user_id)
    running = (
        db.query(PatternExerciseBatchDB.id)
        .filter(PatternExerciseBatchDB.pattern_id == pattern.id, PatternExerciseBatchDB.status == RUNNING)
        .first()
    )
    if running is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ALREADY_RUNNING)
    [usage_row] = private_service.reserve_ai_calls(
        db,
        user_id,
        KIND_EXERCISES,
        {KIND_EXERCISES},
        settings.rate_limit_pattern_exercises_per_user_per_day,
        is_allowlisted,
    )
    batch = PatternExerciseBatchDB(
        id=secrets.token_urlsafe(9),
        pattern_id=pattern.id,
        user_id=user_id,
        status=RUNNING,
        requested=EXERCISES_PER_BATCH,
        created_count=0,
        acknowledged=False,
        created_at=_now(),
    )
    db.add(batch)
    db.commit()
    spawn(run_batch(batch.id, usage_row.id))
    logger.info(f"Exercise batch {batch.id} started for pattern {pattern.id} of user {mask_user_id(user_id)}")
    return batch


def maybe_top_up(db: Session, pattern: PatternDB, unseen: int, is_allowlisted: bool) -> None:
    """Start a batch when the pattern is running out of unseen exercises.

    Quiet: a batch already running, a daily limit or any other failure only
    leaves the pool as it is - the review card is served either way.
    """
    if unseen > TOP_UP_AT:
        return
    try:
        start_batch(db, pattern, pattern.user_id, is_allowlisted)
    except HTTPException as e:
        logger.info(f"Pattern {pattern.id}: no top-up batch ({e.status_code})")
    except Exception as e:
        logger.exception(f"Pattern {pattern.id}: top-up batch not started ({type(e).__name__})")
        db.rollback()


# ---------------------------------------------------------------- running


def _finish(db: Session, batch_id: str, error: str) -> None:
    """Fail the batch - unless it is gone (pattern deleted) or already settled (expired)."""
    db.expire_all()
    batch = db.get(PatternExerciseBatchDB, batch_id)
    if batch is None or batch.status != RUNNING:
        logger.info(f"Exercise batch {batch_id}: gone or already settled, '{error}' not recorded")
        return
    batch.status, batch.error, batch.finished_at = FAILED, error, _now()
    db.commit()
    logger.info(f"Exercise batch {batch_id} failed: {error}")


async def run_batch(batch_id: str, usage_id: Optional[int]) -> None:
    """Generate and save one batch. Never raises: every outcome ends on the batch row."""
    db = session_factory()
    try:
        await _run(db, batch_id, usage_id)
    except Exception as e:
        logger.exception(f"Exercise batch {batch_id} crashed: {type(e).__name__}")
        try:
            db.rollback()
            _finish(db, batch_id, "ai_error")
        except Exception:
            db.rollback()
    finally:
        db.close()


async def _run(db: Session, batch_id: str, usage_id: Optional[int]) -> None:
    batch = db.get(PatternExerciseBatchDB, batch_id)
    if batch is None or batch.status != RUNNING:
        return
    pattern = db.get(PatternDB, batch.pattern_id)
    if pattern is None:
        _finish(db, batch_id, "pattern_deleted")
        return
    previous = [
        _shortened(content)
        for (content,) in db.query(PrivateTaskDB.content)
        .filter(PrivateTaskDB.pattern_id == pattern.id, PrivateTaskDB.user_id == batch.user_id)
        .order_by(PrivateTaskDB.created_at.desc())
        .limit(PREVIOUS_SENT)
        .all()
    ][::-1]
    pattern_text = {"trigger": pattern.trigger, "action": pattern.action, "example": pattern.example or ""}
    requested = batch.requested
    usage_row = db.get(AIUsageDB, usage_id) if usage_id is not None else None
    # The model call can take a minute: no transaction stays open meanwhile
    db.commit()

    try:
        result = await create_ai_provider().generate_pattern_exercises(pattern_text, requested, previous)
    except AIContentBlockedError:
        _finish(db, batch_id, "refused")
        return
    except AIProviderError as e:
        private_service.record_failed_call(db, usage_row, e)
        logger.warning(f"Exercise batch {batch_id}: {type(e).__name__}")
        _finish(db, batch_id, "ai_error")
        return
    if usage_row is not None:
        usage_row.meta = result.meta or None
        db.commit()

    if result.abuse_score >= settings.private_abuse_threshold:
        logger.warning(f"Exercise batch {batch_id}: pattern text flagged as manipulation")
        _finish(db, batch_id, "refused")
        return
    if result.off_topic:
        _finish(db, batch_id, "off_topic")
        return
    items = result.exercises[:requested]
    if not items:
        _finish(db, batch_id, "empty")
        return

    # The pattern (and with it this batch) may have been deleted during the call
    db.expire_all()
    batch = db.get(PatternExerciseBatchDB, batch_id)
    pattern = db.get(PatternDB, batch.pattern_id) if batch is not None else None
    if batch is None or pattern is None or batch.status != RUNNING:
        logger.info(f"Exercise batch {batch_id}: pattern gone or batch settled, nothing saved")
        return

    now = _now()
    repo = PrivateTaskRepository(db)
    tasks = [
        repo.create(
            batch.user_id,
            title=item.title,
            content=item.content,
            source_label=None,
            category=pattern.category,
            difficulty=None,
            hints=[],
            origin=TASK_ORIGIN,
            extraction_meta=None,
            pattern_id=pattern.id,
            exercise_level=item.level,
            answer=item.answer or None,
            solution=item.solution or None,
            commit=False,
        )
        for item in items
    ]
    db.flush()
    for task in tasks:
        db.add(PatternLinkDB(
            pattern_id=pattern.id,
            private_task_id=task.id,
            role="practice",
            origin=LINK_ORIGIN,
            status="accepted",
            created_at=now,
        ))
    pattern.last_activity_at = now
    batch.status, batch.created_count, batch.finished_at = DONE, len(tasks), now
    db.commit()
    logger.info(f"Exercise batch {batch_id}: {len(tasks)} exercises for pattern {pattern.id}")


# ---------------------------------------------------------------- deleting


def delete_exercises(db: Session, pattern: PatternDB) -> tuple[int, int]:
    """Delete the pattern's exercises: rows (with submissions) and upload folders.

    Commits. Returns (exercises, files deleted). Rows first, files second - a
    failed unlink leaves orphans the retention sweep removes.
    """
    tasks = db.query(PrivateTaskDB).filter(PrivateTaskDB.pattern_id == pattern.id).all()
    for task in tasks:
        db.delete(task)
    db.commit()
    files = 0
    for task in tasks:
        files += private_service.delete_task_files(task).files_deleted
    return len(tasks), files


def release_interrupted_batches() -> None:
    """Startup: fail batches a restart killed (they ran in the old process). Never raises."""
    db = SessionLocal()
    try:
        released = expire_stale(db, older_than=RESTART_GRACE)
        if released:
            logger.info(f"Failed {released} exercise batch(es) interrupted by the restart")
    except Exception as e:
        logger.error(f"Could not release interrupted exercise batches: {type(e).__name__}")
        db.rollback()
    finally:
        db.close()
