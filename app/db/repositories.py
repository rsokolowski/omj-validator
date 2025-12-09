"""Repository pattern for data access in OMJ Validator.

Repositories abstract database operations and convert between
SQLAlchemy models and Pydantic models.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import UserDB, SubmissionDB, SubmissionStatus
from ..models import Submission, SubmissionStatus as PydanticSubmissionStatus
from ..config import settings

logger = logging.getLogger(__name__)

# Submissions older than this are considered stale and marked as failed
SUBMISSION_TIMEOUT_SECONDS = settings.gemini_timeout + 60  # AI timeout + buffer


class UserRepository:
    """Repository for user data access."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_google_sub(self, google_sub: str) -> Optional[UserDB]:
        """Get user by Google sub ID."""
        return self.db.query(UserDB).filter(UserDB.google_sub == google_sub).first()

    def get_by_email(self, email: str) -> Optional[UserDB]:
        """Get user by email address."""
        return self.db.query(UserDB).filter(UserDB.email == email).first()

    def create_or_update(
        self,
        google_sub: str,
        email: str,
        name: Optional[str] = None,
    ) -> UserDB:
        """Create a new user or update existing one.

        Called on every OAuth login to ensure user exists and
        profile info is up-to-date.
        """
        user = self.get_by_google_sub(google_sub)

        if user:
            # Update existing user
            user.email = email
            user.name = name
            user.updated_at = datetime.now(timezone.utc)
            logger.debug(f"Updated user: {email}")
        else:
            # Create new user
            user = UserDB(
                google_sub=google_sub,
                email=email,
                name=name,
            )
            self.db.add(user)
            logger.info(f"Created new user: {email}")

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, google_sub: str) -> bool:
        """Delete a user and all their submissions (cascade)."""
        user = self.get_by_google_sub(google_sub)
        if user:
            self.db.delete(user)
            self.db.commit()
            logger.info(f"Deleted user: {user.email}")
            return True
        return False

    def count_recent_users(self, hours: int = 24) -> int:
        """Count users created in the last N hours (for rate limiting)."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        return (
            self.db.query(func.count(UserDB.google_sub))
            .filter(UserDB.created_at >= threshold)
            .scalar()
        ) or 0


class SubmissionRepository:
    """Repository for submission data access."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        id: str,
        user_id: str,
        year: str,
        etap: str,
        task_number: int,
        images: list[str],
        score: Optional[int] = None,
        feedback: Optional[str] = None,
        status: SubmissionStatus = SubmissionStatus.COMPLETED,
        error_message: Optional[str] = None,
        scoring_meta: Optional[dict] = None,
    ) -> SubmissionDB:
        """Create a new submission."""
        submission = SubmissionDB(
            id=id,
            user_id=user_id,
            year=year,
            etap=etap,
            task_number=task_number,
            images=images,
            score=score,
            feedback=feedback,
            status=status,
            error_message=error_message,
            scoring_meta=scoring_meta,
        )
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        logger.debug(f"Created submission {id} for user {user_id}")
        return submission

    def get_by_id(self, submission_id: str) -> Optional[SubmissionDB]:
        """Get submission by ID."""
        return self.db.query(SubmissionDB).filter(SubmissionDB.id == submission_id).first()

    def get_user_submissions_for_task(
        self,
        user_id: str,
        year: str,
        etap: str,
        task_number: int,
    ) -> list[SubmissionDB]:
        """Get all submissions by a user for a specific task.

        Returns submissions ordered by timestamp descending (most recent first).
        Also marks stale pending/processing submissions as failed.
        """
        submissions = (
            self.db.query(SubmissionDB)
            .filter(
                SubmissionDB.user_id == user_id,
                SubmissionDB.year == year,
                SubmissionDB.etap == etap,
                SubmissionDB.task_number == task_number,
            )
            .order_by(SubmissionDB.timestamp.desc())
            .all()
        )

        # Mark stale submissions as failed
        self._mark_stale_submissions_failed(submissions)

        return submissions

    def _mark_stale_submissions_failed(self, submissions: list[SubmissionDB]) -> None:
        """Mark pending/processing submissions that are past timeout as failed."""
        now = datetime.now(timezone.utc)
        timeout_threshold = now - timedelta(seconds=SUBMISSION_TIMEOUT_SECONDS)
        updated = False

        for submission in submissions:
            if submission.status in (SubmissionStatus.PENDING, SubmissionStatus.PROCESSING):
                # Handle timezone-naive timestamps from DB
                submission_time = submission.timestamp
                if submission_time.tzinfo is None:
                    submission_time = submission_time.replace(tzinfo=timezone.utc)

                if submission_time < timeout_threshold:
                    submission.status = SubmissionStatus.FAILED
                    submission.error_message = "Przekroczono limit czasu przetwarzania. Spróbuj ponownie."
                    updated = True
                    logger.info(f"Marked stale submission {submission.id} as failed")

        if updated:
            self.db.commit()

    def get_user_progress(self, user_id: str) -> dict[str, int]:
        """Get best scores for all tasks by user.

        Returns a dict mapping task_key (e.g., "2024_etap1_3") to best score.
        Only includes tasks where the user has at least one submission.

        Uses efficient SQL aggregation instead of loading all submissions.
        """
        results = (
            self.db.query(
                SubmissionDB.year,
                SubmissionDB.etap,
                SubmissionDB.task_number,
                func.max(SubmissionDB.score).label("best_score"),
            )
            .filter(
                SubmissionDB.user_id == user_id,
                SubmissionDB.status == SubmissionStatus.COMPLETED,
                SubmissionDB.score.isnot(None),
            )
            .group_by(SubmissionDB.year, SubmissionDB.etap, SubmissionDB.task_number)
            .all()
        )

        return {
            f"{r.year}_{r.etap}_{r.task_number}": r.best_score
            for r in results
        }

    def get_task_stats(
        self,
        user_id: str,
        year: str,
        etap: str,
        task_number: int,
    ) -> tuple[int, int]:
        """Get submission count and highest score for a user's task.

        Returns (submission_count, highest_score).
        """
        submissions = self.get_user_submissions_for_task(user_id, year, etap, task_number)

        if not submissions:
            return (0, 0)

        completed = [s for s in submissions if s.status == SubmissionStatus.COMPLETED and s.score is not None]
        highest_score = max((s.score for s in completed), default=0)

        return (len(submissions), highest_score)

    def to_pydantic(self, db_submission: SubmissionDB) -> Submission:
        """Convert SQLAlchemy model to Pydantic model."""
        return Submission(
            id=db_submission.id,
            user_id=db_submission.user_id,
            year=db_submission.year,
            etap=db_submission.etap,
            task_number=db_submission.task_number,
            timestamp=db_submission.timestamp,
            status=PydanticSubmissionStatus(db_submission.status.value),
            images=db_submission.images,
            score=db_submission.score,
            feedback=db_submission.feedback,
            error_message=db_submission.error_message,
            scoring_meta=db_submission.scoring_meta,
        )

    def to_pydantic_list(self, db_submissions: list[SubmissionDB]) -> list[Submission]:
        """Convert list of SQLAlchemy models to Pydantic models."""
        return [self.to_pydantic(s) for s in db_submissions]

    def update_status(
        self,
        submission_id: str,
        status: SubmissionStatus,
        error_message: Optional[str] = None,
    ) -> Optional[SubmissionDB]:
        """Update submission status."""
        submission = self.get_by_id(submission_id)
        if not submission:
            return None
        submission.status = status
        if error_message is not None:
            submission.error_message = error_message
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def update_result(
        self,
        submission_id: str,
        score: int,
        feedback: str,
        status: SubmissionStatus = SubmissionStatus.COMPLETED,
        scoring_meta: Optional[dict] = None,
    ) -> Optional[SubmissionDB]:
        """Update submission with final results."""
        submission = self.get_by_id(submission_id)
        if not submission:
            return None
        submission.status = status
        submission.score = score
        submission.feedback = feedback
        if scoring_meta is not None:
            submission.scoring_meta = scoring_meta
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def count_user_recent_submissions(self, user_id: str, hours: int = 24) -> int:
        """Count submissions by user in the last N hours (for rate limiting)."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        return (
            self.db.query(func.count(SubmissionDB.id))
            .filter(
                SubmissionDB.user_id == user_id,
                SubmissionDB.timestamp >= threshold,
            )
            .scalar()
        ) or 0

    def count_recent_submissions(self, hours: int = 24) -> int:
        """Count all submissions in the last N hours (for rate limiting)."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        return (
            self.db.query(func.count(SubmissionDB.id))
            .filter(SubmissionDB.timestamp >= threshold)
            .scalar()
        ) or 0
