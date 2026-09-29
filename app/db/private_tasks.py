"""Data access for private tasks ("Moje zadania") and non-submission AI usage."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import AIUsageDB, PrivateTaskDB, SubmissionDB, SubmissionStatus
from ..privacy import mask_user_id

logger = logging.getLogger(__name__)

# Fields a student may change after creation (PATCH /api/private-tasks/{id})
EDITABLE_FIELDS = {"title", "content", "source_label", "category", "difficulty", "hints"}

# ai_usage.kind values
KIND_EXTRACT = "private_extract"
KIND_CREATE = "private_create"
KIND_REGEN = "private_regen"
# Kinds counted by rate_limit_private_tasks_per_user_per_day
CREATION_KINDS = {KIND_CREATE, KIND_REGEN}


def _now() -> datetime:
    """Current UTC time as stored in the DB (timezone-naive, see models.utc_now)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_private_task_id() -> str:
    """12 URL-safe characters - unguessable, fits PrivateTaskDB.id."""
    return secrets.token_urlsafe(9)


class HintOrderError(Exception):
    """A hint was requested before the one preceding it was revealed."""


class PrivateTaskRepository:
    """CRUD for private tasks. Every read is scoped to the owner."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: str,
        *,
        title: str,
        content: str,
        source_label: Optional[str],
        category: Optional[str],
        difficulty: Optional[int],
        hints: list[str],
        origin: str,
        source_images: Optional[list[str]] = None,
        extraction_meta: Optional[dict] = None,
        task_id: Optional[str] = None,
    ) -> PrivateTaskDB:
        now = _now()
        task = PrivateTaskDB(
            id=task_id or new_private_task_id(),
            user_id=user_id,
            title=title,
            content=content,
            source_label=source_label,
            category=category,
            difficulty=difficulty,
            hints=list(hints),
            source_images=list(source_images or []),
            origin=origin,
            extraction_meta=extraction_meta,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        logger.info(f"Created private task {task.id} for user {mask_user_id(user_id)}")
        return task

    def get_owned(self, task_id: str, user_id: str) -> Optional[PrivateTaskDB]:
        """The task, or None when it does not exist OR belongs to someone else.

        Callers answer 404 in both cases so the API never confirms that another
        user's task id exists.
        """
        return (
            self.db.query(PrivateTaskDB)
            .filter(PrivateTaskDB.id == task_id, PrivateTaskDB.user_id == user_id)
            .first()
        )

    def get_by_id(self, task_id: str) -> Optional[PrivateTaskDB]:
        """Unscoped lookup - only for the background worker and admin rerun."""
        return self.db.query(PrivateTaskDB).filter(PrivateTaskDB.id == task_id).first()

    def list_for_user(
        self, user_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[dict], int]:
        """The user's tasks, most recently active first, with score summary.

        Returns ([{"task", "best_score", "attempts"}], total_count).
        """
        base = self.db.query(PrivateTaskDB).filter(PrivateTaskDB.user_id == user_id)
        total = base.count()
        tasks = (
            base.order_by(PrivateTaskDB.last_activity_at.desc(), PrivateTaskDB.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        if not tasks:
            return [], total

        ids = [t.id for t in tasks]
        attempts = dict(
            self.db.query(SubmissionDB.private_task_id, func.count(SubmissionDB.id))
            .filter(SubmissionDB.private_task_id.in_(ids))
            .group_by(SubmissionDB.private_task_id)
            .all()
        )
        best = dict(
            self.db.query(SubmissionDB.private_task_id, func.max(SubmissionDB.score))
            .filter(
                SubmissionDB.private_task_id.in_(ids),
                SubmissionDB.status == SubmissionStatus.COMPLETED,
                SubmissionDB.score.isnot(None),
            )
            .group_by(SubmissionDB.private_task_id)
            .all()
        )
        rows = [
            {"task": t, "best_score": best.get(t.id), "attempts": attempts.get(t.id, 0)}
            for t in tasks
        ]
        return rows, total

    def update_fields(self, task: PrivateTaskDB, **fields) -> PrivateTaskDB:
        unknown = set(fields) - EDITABLE_FIELDS
        if unknown:
            raise ValueError(f"Not editable: {sorted(unknown)}")
        for name, value in fields.items():
            setattr(task, name, list(value) if name == "hints" else value)
        if "hints" in fields:
            # New hints: nothing of them has been revealed yet
            task.hints_revealed = 0
        task.last_activity_at = _now()
        self.db.commit()
        self.db.refresh(task)
        return task

    def reveal_hint(self, task: PrivateTaskDB, n: int) -> str:
        """Text of hint n (1-based). Hints open strictly in order.

        Raises IndexError for a hint that does not exist and HintOrderError for
        one requested before its predecessor was ever revealed.
        """
        hints = task.hints or []
        if n < 1 or n > len(hints):
            raise IndexError(n)
        if n > (task.hints_revealed or 0) + 1:
            raise HintOrderError(n)
        task.hints_revealed = max(task.hints_revealed or 0, n)
        task.pending_hints_used = max(task.pending_hints_used or 0, n)
        self.db.commit()
        return hints[n - 1]

    def take_pending_hints(self, task: PrivateTaskDB) -> int:
        """Hints used since the last submission; resets the counter."""
        used = task.pending_hints_used or 0
        task.pending_hints_used = 0
        task.last_activity_at = _now()
        self.db.commit()
        return used

    def touch(self, task: PrivateTaskDB) -> None:
        task.last_activity_at = _now()
        self.db.commit()

    def delete(self, task: PrivateTaskDB) -> None:
        """Delete the row and (ORM cascade) its submissions. Files: the caller."""
        self.db.delete(task)
        self.db.commit()


class AIUsageRepository:
    """Content-free log of non-submission AI calls, for rate limiting."""

    def __init__(self, db: Session):
        self.db = db

    def record(self, user_id: str, kind: str, meta: Optional[dict] = None) -> AIUsageDB:
        row = AIUsageDB(user_id=user_id, kind=kind, meta=meta, created_at=_now())
        self.db.add(row)
        self.db.commit()
        return row

    def _window(self, hours: int):
        return _now() - timedelta(hours=hours)

    def user_window(
        self, user_id: str, kinds: set[str], hours: int = 24
    ) -> tuple[int, Optional[datetime]]:
        """(count, oldest) of the user's rows of these kinds inside the window."""
        count, oldest = (
            self.db.query(func.count(AIUsageDB.id), func.min(AIUsageDB.created_at))
            .filter(
                AIUsageDB.user_id == user_id,
                AIUsageDB.kind.in_(kinds),
                AIUsageDB.created_at >= self._window(hours),
            )
            .first()
        )
        return count or 0, oldest

    def global_window(self, hours: int = 24) -> tuple[int, Optional[datetime]]:
        count, oldest = (
            self.db.query(func.count(AIUsageDB.id), func.min(AIUsageDB.created_at))
            .filter(AIUsageDB.created_at >= self._window(hours))
            .first()
        )
        return count or 0, oldest

    def user_total_window(
        self, user_id: str, hours: int = 24
    ) -> tuple[int, Optional[datetime], Optional[datetime]]:
        """(count, oldest, newest) of all the user's rows - for the erasure tombstone."""
        count, oldest, newest = (
            self.db.query(
                func.count(AIUsageDB.id),
                func.min(AIUsageDB.created_at),
                func.max(AIUsageDB.created_at),
            )
            .filter(
                AIUsageDB.user_id == user_id,
                AIUsageDB.created_at >= self._window(hours),
            )
            .first()
        )
        return count or 0, oldest, newest
