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

    def get_rate_limit_info(self, hours: int = 24) -> tuple[int, Optional[datetime]]:
        """Get rate limit info: (count, oldest_timestamp) for new users.

        Returns:
            Tuple of (count of recent users, timestamp of oldest user in window).
            The oldest timestamp can be used to calculate when the rate limit resets.
        """
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = (
            self.db.query(
                func.count(UserDB.google_sub),
                func.min(UserDB.created_at),
            )
            .filter(UserDB.created_at >= threshold)
            .first()
        )
        count = result[0] or 0
        oldest = result[1]
        return count, oldest

    def search_by_email(self, query: str, limit: int = 10) -> list[UserDB]:
        """Search users by email prefix (case-insensitive).

        Used for admin panel autocomplete.

        Args:
            query: Search query (prefix match, minimum 2 characters)
            limit: Maximum number of results

        Returns:
            List of matching users ordered by email.
        """
        # Require minimum 2 characters to prevent scanning all users
        if not query or len(query) < 2:
            return []
        return (
            self.db.query(UserDB)
            .filter(UserDB.email.ilike(f"{query}%"))
            .order_by(UserDB.email)
            .limit(limit)
            .all()
        )

    def get_all(self) -> list[UserDB]:
        """Get all users ordered by email.

        Used for admin panel user filter dropdown.
        """
        return self.db.query(UserDB).order_by(UserDB.email).all()

    def get_by_google_subs(self, google_subs: list[str]) -> dict[str, UserDB]:
        """Get multiple users by Google sub IDs in a single query.

        Args:
            google_subs: List of Google sub IDs

        Returns:
            Dict mapping google_sub to UserDB
        """
        if not google_subs:
            return {}
        users = (
            self.db.query(UserDB)
            .filter(UserDB.google_sub.in_(google_subs))
            .all()
        )
        return {user.google_sub: user for user in users}


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

    def get_user_rate_limit_info(
        self, user_id: str, hours: int = 24
    ) -> tuple[int, Optional[datetime]]:
        """Get rate limit info: (count, oldest_timestamp) for user submissions.

        Returns:
            Tuple of (count of recent submissions, timestamp of oldest submission in window).
            The oldest timestamp can be used to calculate when the rate limit resets.
        """
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = (
            self.db.query(
                func.count(SubmissionDB.id),
                func.min(SubmissionDB.timestamp),
            )
            .filter(
                SubmissionDB.user_id == user_id,
                SubmissionDB.timestamp >= threshold,
            )
            .first()
        )
        count = result[0] or 0
        oldest = result[1]
        return count, oldest

    def count_recent_submissions(self, hours: int = 24) -> int:
        """Count all submissions in the last N hours (for rate limiting)."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        return (
            self.db.query(func.count(SubmissionDB.id))
            .filter(SubmissionDB.timestamp >= threshold)
            .scalar()
        ) or 0

    def get_global_rate_limit_info(self, hours: int = 24) -> tuple[int, Optional[datetime]]:
        """Get rate limit info: (count, oldest_timestamp) for all submissions.

        Returns:
            Tuple of (count of recent submissions, timestamp of oldest submission in window).
            The oldest timestamp can be used to calculate when the rate limit resets.
        """
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = (
            self.db.query(
                func.count(SubmissionDB.id),
                func.min(SubmissionDB.timestamp),
            )
            .filter(SubmissionDB.timestamp >= threshold)
            .first()
        )
        count = result[0] or 0
        oldest = result[1]
        return count, oldest

    def delete_all_user_submissions(self, user_id: str) -> int:
        """Delete all submissions for a user.

        Used for E2E testing to reset rate limits.

        Returns:
            Number of submissions deleted.
        """
        count = (
            self.db.query(SubmissionDB)
            .filter(SubmissionDB.user_id == user_id)
            .delete()
        )
        self.db.commit()
        logger.info(f"Deleted {count} submissions for user {user_id}")
        return count

    def delete_all_submissions(self) -> int:
        """Delete all submissions.

        Used for E2E testing to reset the global rate limit.

        Returns:
            Number of submissions deleted.
        """
        count = self.db.query(SubmissionDB).delete()
        self.db.commit()
        logger.info(f"Deleted all {count} submissions")
        return count

    def get_all_submissions_paginated(
        self,
        offset: int = 0,
        limit: int = 20,
        user_id_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> tuple[list[SubmissionDB], int]:
        """Get all submissions with pagination and filters.

        Used for admin panel to view all submissions across users.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            user_id_filter: Filter by user_id (exact match)
            status_filter: Filter by status (pending/processing/completed/failed)

        Returns:
            Tuple of (submissions list, total count matching filters).
        """
        query = self.db.query(SubmissionDB)

        # Apply filters
        if user_id_filter:
            query = query.filter(SubmissionDB.user_id == user_id_filter)

        if status_filter:
            try:
                status_enum = SubmissionStatus(status_filter)
                query = query.filter(SubmissionDB.status == status_enum)
            except ValueError:
                # Invalid status, ignore filter
                pass

        # Get total count before pagination
        total_count = query.count()

        # Apply ordering and pagination
        submissions = (
            query
            .order_by(SubmissionDB.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return submissions, total_count

    def get_user_submissions_paginated(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
        year_filter: Optional[str] = None,
        etap_filter: Optional[str] = None,
        hide_errors: bool = False,
    ) -> tuple[list[SubmissionDB], int]:
        """Get user's submissions with pagination and filters.

        Used for "Moje rozwiązania" (My Solutions) panel.

        Args:
            user_id: User's Google sub
            offset: Number of records to skip
            limit: Maximum number of records to return
            year_filter: Filter by year (e.g., "2024")
            etap_filter: Filter by etap (etap1/etap2/etap3)
            hide_errors: If True, exclude failed submissions (default False)

        Returns:
            Tuple of (submissions list, total count matching filters).
        """
        query = self.db.query(SubmissionDB).filter(SubmissionDB.user_id == user_id)

        # Apply filters
        if year_filter:
            query = query.filter(SubmissionDB.year == year_filter)

        if etap_filter:
            query = query.filter(SubmissionDB.etap == etap_filter)

        if hide_errors:
            query = query.filter(SubmissionDB.status != SubmissionStatus.FAILED)

        # Get total count before pagination
        total_count = query.count()

        # Apply ordering and pagination
        submissions = (
            query
            .order_by(SubmissionDB.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return submissions, total_count

    def get_user_aggregate_stats(self, user_id: str) -> dict:
        """Get aggregate statistics for a user's submissions.

        Used for "Moje rozwiązania" dashboard stats cards.

        Args:
            user_id: User's Google sub

        Returns:
            Dictionary with:
            - total_submissions: Total number of submissions
            - completed_count: Number of completed submissions
            - failed_count: Number of failed submissions
            - pending_count: Number of pending/processing submissions
            - avg_score: Average score of completed submissions (None if no completed)
            - best_score: Highest score achieved (None if no completed)
            - tasks_attempted: Number of unique tasks attempted
            - tasks_mastered: Number of unique tasks with best_score >= mastery threshold
        """
        # Count by status
        status_counts = (
            self.db.query(
                SubmissionDB.status,
                func.count(SubmissionDB.id).label("count")
            )
            .filter(SubmissionDB.user_id == user_id)
            .group_by(SubmissionDB.status)
            .all()
        )

        status_map = {row.status: row.count for row in status_counts}
        total = sum(status_map.values())
        completed = status_map.get(SubmissionStatus.COMPLETED, 0)
        failed = status_map.get(SubmissionStatus.FAILED, 0)
        pending = (
            status_map.get(SubmissionStatus.PENDING, 0) +
            status_map.get(SubmissionStatus.PROCESSING, 0)
        )

        # Score stats (only for completed submissions with score)
        score_stats = (
            self.db.query(
                func.avg(SubmissionDB.score).label("avg_score"),
                func.max(SubmissionDB.score).label("best_score")
            )
            .filter(
                SubmissionDB.user_id == user_id,
                SubmissionDB.status == SubmissionStatus.COMPLETED,
                SubmissionDB.score.isnot(None)
            )
            .first()
        )

        avg_score = round(score_stats.avg_score, 2) if score_stats.avg_score else None
        best_score = score_stats.best_score

        # Unique tasks attempted (any status)
        tasks_attempted = (
            self.db.query(SubmissionDB.year, SubmissionDB.etap, SubmissionDB.task_number)
            .filter(SubmissionDB.user_id == user_id)
            .distinct()
            .count()
        )

        # Tasks mastered: best score >= mastery threshold per task
        # etap1: mastery = 2, etap2/etap3: mastery = 5
        # We use get_user_progress() which already calculates best scores
        user_progress = self.get_user_progress(user_id)
        tasks_mastered = 0
        for task_key, best in user_progress.items():
            # task_key format: "2024_etap1_3"
            parts = task_key.split("_")
            if len(parts) >= 2:
                etap = parts[1]
                # Mastery threshold: 2 for etap1, 5 for etap2/3
                threshold = 2 if etap == "etap1" else 5
                if best >= threshold:
                    tasks_mastered += 1

        return {
            "total_submissions": total,
            "completed_count": completed,
            "failed_count": failed,
            "pending_count": pending,
            "avg_score": avg_score,
            "best_score": best_score,
            "tasks_attempted": tasks_attempted,
            "tasks_mastered": tasks_mastered,
        }
