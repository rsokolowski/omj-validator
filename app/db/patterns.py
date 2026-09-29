"""Data access for patterns ("Wzorce"): patterns, their task links and reviews."""

import logging
import secrets
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, update
from sqlalchemy.orm import Session, selectinload

from .models import PatternDB, PatternLinkDB, PatternReviewDB
from ..privacy import mask_user_id

logger = logging.getLogger(__name__)

# Fields a student may change after creation (PATCH /api/patterns/{id})
EDITABLE_FIELDS = {"trigger", "action", "example", "category", "skills", "archived_at", "refinement"}


def _now() -> datetime:
    """Current UTC time as stored in the DB (timezone-naive, see models.utc_now)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_pattern_id() -> str:
    """12 URL-safe characters - unguessable, fits PatternDB.id."""
    return secrets.token_urlsafe(9)


class PatternRepository:
    """CRUD for patterns. Every read by id is scoped to the owner."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: str,
        *,
        trigger: str,
        action: str,
        example: Optional[str],
        category: Optional[str],
        skills: list[str],
        origin: str,
        refinement: list[dict],
        due_on: date,
    ) -> PatternDB:
        now = _now()
        pattern = PatternDB(
            id=new_pattern_id(),
            user_id=user_id,
            trigger=trigger,
            action=action,
            example=example,
            category=category,
            skills=list(skills),
            origin=origin,
            refinement=list(refinement),
            srs_level=1,
            srs_streak=0,
            due_on=due_on,
            review_count=0,
            lapse_count=0,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        self.db.add(pattern)
        self.db.commit()
        self.db.refresh(pattern)
        logger.info(f"Created pattern {pattern.id} for user {mask_user_id(user_id)}")
        return pattern

    def get_owned(self, pattern_id: str, user_id: str) -> Optional[PatternDB]:
        """The pattern, or None when it does not exist OR belongs to someone else."""
        return (
            self.db.query(PatternDB)
            .filter(PatternDB.id == pattern_id, PatternDB.user_id == user_id)
            .first()
        )

    def get_by_id(self, pattern_id: str) -> Optional[PatternDB]:
        """Unscoped lookup - only for the grading worker."""
        return self.db.query(PatternDB).filter(PatternDB.id == pattern_id).first()

    def list_for_user(
        self,
        user_id: str,
        *,
        category: Optional[str] = None,
        archived: bool = False,
        task_key: Optional[str] = None,
        private_task_id: Optional[str] = None,
    ) -> list[PatternDB]:
        """The user's patterns, soonest review first.

        ``task_key`` / ``private_task_id`` keep only patterns with an accepted
        link to that task (the "Twoje wzorce z tego zadania" list).
        """
        query = self.db.query(PatternDB).filter(PatternDB.user_id == user_id)
        query = query.filter(
            PatternDB.archived_at.isnot(None) if archived else PatternDB.archived_at.is_(None)
        )
        if category:
            query = query.filter(PatternDB.category == category)
        if task_key or private_task_id:
            link = self.db.query(PatternLinkDB.pattern_id).filter(PatternLinkDB.status == "accepted")
            if task_key:
                link = link.filter(PatternLinkDB.task_key == task_key)
            else:
                link = link.filter(PatternLinkDB.private_task_id == private_task_id)
            query = query.filter(PatternDB.id.in_(link))
        return (
            query.options(selectinload(PatternDB.links))
            .order_by(PatternDB.due_on, PatternDB.created_at)
            .all()
        )

    def _due_filter(self, user_id: str, today: date):
        return (
            PatternDB.user_id == user_id,
            PatternDB.archived_at.is_(None),
            PatternDB.due_on <= today,
        )

    def due(self, user_id: str, today: date) -> list[PatternDB]:
        """Patterns to review today, most overdue first (links loaded in one query)."""
        return (
            self.db.query(PatternDB)
            .options(selectinload(PatternDB.links))
            .filter(*self._due_filter(user_id, today))
            .order_by(PatternDB.due_on, PatternDB.created_at)
            .all()
        )

    def count_due(self, user_id: str, today: date) -> int:
        """How many patterns wait for review today - one COUNT query."""
        return self.db.query(func.count(PatternDB.id)).filter(*self._due_filter(user_id, today)).scalar() or 0

    def update_fields(self, pattern: PatternDB, **fields) -> PatternDB:
        unknown = set(fields) - EDITABLE_FIELDS
        if unknown:
            raise ValueError(f"Not editable: {sorted(unknown)}")
        for name, value in fields.items():
            setattr(pattern, name, list(value) if name in ("skills", "refinement") else value)
        pattern.last_activity_at = _now()
        self.db.commit()
        self.db.refresh(pattern)
        return pattern

    # ------------------------------------------------------------------ links

    def add_link(
        self,
        pattern: PatternDB,
        *,
        task_key: Optional[str] = None,
        private_task_id: Optional[str] = None,
        role: str,
        origin: str,
        status: str,
        reason: Optional[str] = None,
    ) -> Optional[PatternLinkDB]:
        """Link a task, or None when the pattern already has a link to it."""
        existing = self.db.query(PatternLinkDB).filter(PatternLinkDB.pattern_id == pattern.id)
        if task_key is not None:
            existing = existing.filter(PatternLinkDB.task_key == task_key)
        else:
            existing = existing.filter(PatternLinkDB.private_task_id == private_task_id)
        if existing.first() is not None:
            return None
        link = PatternLinkDB(
            pattern_id=pattern.id,
            task_key=task_key,
            private_task_id=private_task_id,
            role=role,
            origin=origin,
            status=status,
            reason=reason,
            created_at=_now(),
        )
        self.db.add(link)
        pattern.last_activity_at = _now()
        self.db.commit()
        self.db.refresh(link)
        return link

    def get_link(self, pattern: PatternDB, link_id: int) -> Optional[PatternLinkDB]:
        return (
            self.db.query(PatternLinkDB)
            .filter(PatternLinkDB.id == link_id, PatternLinkDB.pattern_id == pattern.id)
            .first()
        )

    def set_link_status(self, link: PatternLinkDB, status: str) -> PatternLinkDB:
        link.status = status
        self.db.commit()
        return link

    def delete_link(self, link: PatternLinkDB) -> None:
        self.db.delete(link)
        self.db.commit()

    # ---------------------------------------------------------------- reviews

    def apply_review(
        self,
        pattern: PatternDB,
        *,
        seen_due_on: date,
        new_level: int,
        new_streak: int,
        new_due: date,
        outcome: str,
        kind: str,
        recall_text: Optional[str] = None,
        submission_id: Optional[str] = None,
        conditional: bool = True,
    ) -> Optional[PatternReviewDB]:
        """Move the pattern to its new schedule and log the review.

        ``conditional`` (recall cards): the update only lands while ``due_on``
        is still what the client saw, so a double click or a second tab counts
        once - the loser gets None and nothing is written.
        """
        now = _now()
        level_before = pattern.srs_level
        due_before = pattern.due_on
        values = {
            PatternDB.srs_level: new_level,
            PatternDB.srs_streak: new_streak,
            PatternDB.due_on: new_due,
            PatternDB.review_count: PatternDB.review_count + 1,
            PatternDB.last_reviewed_at: now,
            PatternDB.last_activity_at: now,
            PatternDB.updated_at: now,
        }
        if outcome == "fail":
            values[PatternDB.lapse_count] = PatternDB.lapse_count + 1
        statement = update(PatternDB).where(PatternDB.id == pattern.id)
        if conditional:
            statement = statement.where(PatternDB.due_on == seen_due_on)
        result = self.db.execute(statement.values(values).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            self.db.rollback()
            self.db.refresh(pattern)
            return None

        review = PatternReviewDB(
            pattern_id=pattern.id,
            user_id=pattern.user_id,
            kind=kind,
            outcome=outcome,
            recall_text=recall_text,
            submission_id=submission_id,
            level_before=level_before,
            level_after=new_level,
            due_before=due_before,
            due_after=new_due,
            created_at=now,
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(pattern)
        return review

    def has_review_for_submission(self, submission_id: str) -> bool:
        return (
            self.db.query(PatternReviewDB.id)
            .filter(PatternReviewDB.submission_id == submission_id)
            .first()
            is not None
        )

    def delete(self, pattern: PatternDB) -> None:
        """Delete the pattern with its links and reviews; submissions stay."""
        self.db.delete(pattern)
        self.db.commit()
