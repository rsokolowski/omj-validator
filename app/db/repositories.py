"""Repository pattern for data access in OMJ Validator.

Repositories abstract database operations and convert between
SQLAlchemy models and Pydantic models.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import AdminAccessLogDB, DeletedAccountQuotaDB, UserDB, SubmissionDB, SubmissionStatus, IssueType
from ..models import Submission, SubmissionStatus as PydanticSubmissionStatus, IssueType as PydanticIssueType
from ..config import settings
from ..privacy import mask_email, mask_user_id


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has UTC timezone for proper frontend localization.

    PostgreSQL DateTime columns without timezone=True return naive datetimes.
    JavaScript interprets ISO strings without timezone as local time, so we
    must explicitly add UTC timezone before serialization.

    Note: This codebase stores all timestamps as UTC (using utc_now() default).
    Naive datetimes are assumed to be UTC and get the UTC timezone attached.
    Already timezone-aware datetimes are returned unchanged.

    Args:
        dt: A datetime object (may be naive, timezone-aware, or None)

    Returns:
        A timezone-aware datetime in UTC, or None if input was None
    """
    if dt is None:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

logger = logging.getLogger(__name__)

# Submissions older than this are considered stale and marked as failed
SUBMISSION_TIMEOUT_SECONDS = settings.gemini_timeout + 60  # AI timeout + buffer


def hash_user_id(user_id: str) -> str:
    """Irreversible, salted digest of a Google sub.

    Used for the rate-limit tombstone left behind by account erasure: it must be
    possible to recognise the same person coming back within the window, but the
    stored value must not identify anyone on its own. HMAC (not a plain hash)
    so that guessing candidate ids cannot reproduce the digest without the
    server-side key.
    """
    key = (settings.session_secret_key or "").encode("utf-8")
    return hmac.new(key, user_id.encode("utf-8"), hashlib.sha256).hexdigest()


class AdminAccessLogRepository:
    """Audit trail of admin access to other users' data (see AdminAccessLogDB)."""

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        admin_email: str,
        resource: str,
        subject_user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        admin_user_id: Optional[str] = None,
    ) -> Optional[AdminAccessLogDB]:
        """Record one admin access. Returns None when nothing was recorded.

        An admin looking at their own submissions is noise, not an audit event,
        so it is skipped. Failures are swallowed and logged: an audit write must
        never break the page an admin is trying to open.
        """
        if subject_user_id and admin_user_id and subject_user_id == admin_user_id:
            return None

        try:
            entry = AdminAccessLogDB(
                admin_email=admin_email,
                subject_user_id=subject_user_id,
                resource=resource,
                resource_id=resource_id,
            )
            self.db.add(entry)
            self.db.commit()
            return entry
        except Exception as e:
            self.db.rollback()
            logger.warning(f"Admin access audit write failed: {type(e).__name__}: {e}")
            return None

    def pseudonymize_subject(self, user_id: str) -> int:
        """Replace a subject's raw id with an irreversible digest.

        Called when that user erases their account: the accountability record of
        "an admin looked at somebody's data" survives, but the identifier of the
        erased account does not. Returns the number of rows updated.
        """
        return (
            self.db.query(AdminAccessLogDB)
            .filter(AdminAccessLogDB.subject_user_id == user_id)
            .update({AdminAccessLogDB.subject_user_id: hash_user_id(user_id)})
        )


class DeletedAccountQuotaRepository:
    """Rate-limit tombstones for erased accounts (see DeletedAccountQuotaDB)."""

    def __init__(self, db: Session):
        self.db = db

    def record_deletion(
        self,
        user_id: str,
        submission_count: int,
        oldest_submission_at: Optional[datetime],
        newest_submission_at: Optional[datetime] = None,
        window_hours: int = 24,
    ) -> Optional[DeletedAccountQuotaDB]:
        """Remember how much quota an erased account had already used.

        No-op when the account made no submissions inside the window - there is
        nothing to carry over and no reason to store anything.

        Expiry is anchored on the NEWEST submission, not the oldest. The whole
        count is carried as one block, so anchoring it on the oldest would hand
        every slot back at once well before a surviving account would have got
        them: 30 submissions spread across the window, oldest at T-23h, would
        release all 30 at T+1h instead of trickling out until T+24h. Anchoring
        on the newest errs the other way - conservative, which is the right
        direction for an abuse guard.

        oldest_submission_at is still stored, because that is what the reset /
        Retry-After headers should point at (when the FIRST slot frees up).
        """
        if submission_count <= 0:
            return None

        now = datetime.now(timezone.utc)
        anchor = ensure_utc(newest_submission_at) or ensure_utc(oldest_submission_at) or now
        expires_at = (anchor + timedelta(hours=window_hours)).replace(tzinfo=None)
        user_hash = hash_user_id(user_id)

        tombstone = (
            self.db.query(DeletedAccountQuotaDB)
            .filter(DeletedAccountQuotaDB.user_hash == user_hash)
            .first()
        )
        if tombstone:
            # Same person deleting again inside the window - quota accumulates
            tombstone.submission_count += submission_count
            if tombstone.expires_at < expires_at:
                tombstone.expires_at = expires_at
            # Reset headers should still point at the earliest counted submission
            new_oldest = ensure_utc(oldest_submission_at)
            if new_oldest is not None:
                naive_oldest = new_oldest.replace(tzinfo=None)
                if tombstone.oldest_submission_at is None or naive_oldest < tombstone.oldest_submission_at:
                    tombstone.oldest_submission_at = naive_oldest
        else:
            tombstone = DeletedAccountQuotaDB(
                user_hash=user_hash,
                submission_count=submission_count,
                oldest_submission_at=(
                    ensure_utc(oldest_submission_at).replace(tzinfo=None)
                    if oldest_submission_at
                    else None
                ),
                expires_at=expires_at,
            )
            self.db.add(tombstone)

        self.db.commit()
        logger.info(
            f"Recorded rate-limit tombstone for erased account "
            f"({submission_count} submissions, expires {expires_at})"
        )
        return tombstone

    def get_user_carryover(self, user_id: str) -> tuple[int, Optional[datetime]]:
        """(count, expires_at) still counting against a returning user.

        The second element is when the carried-over quota is released, NOT the
        oldest submission behind it. The whole count is one block that expires
        at once (see record_deletion), so expires_at is the only moment at which
        anything actually frees up - which is what Retry-After has to report.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        tombstone = (
            self.db.query(DeletedAccountQuotaDB)
            .filter(
                DeletedAccountQuotaDB.user_hash == hash_user_id(user_id),
                DeletedAccountQuotaDB.expires_at > now,
            )
            .first()
        )
        if not tombstone:
            return 0, None
        return tombstone.submission_count, tombstone.expires_at

    def get_global_carryover_blocks(self) -> list[tuple[int, datetime]]:
        """Every live tombstone as a (count, expires_at) block.

        Kept as separate blocks rather than one sum, because each is released at
        its own moment and the reset calculation needs them individually.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = (
            self.db.query(
                DeletedAccountQuotaDB.submission_count,
                DeletedAccountQuotaDB.expires_at,
            )
            .filter(DeletedAccountQuotaDB.expires_at > now)
            .all()
        )
        return [(int(count or 0), expires_at) for count, expires_at in rows]

    def purge_expired(self) -> int:
        """Delete tombstones whose window has closed. Returns how many went."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        count = (
            self.db.query(DeletedAccountQuotaDB)
            .filter(DeletedAccountQuotaDB.expires_at <= now)
            .delete()
        )
        if count:
            self.db.commit()
            logger.debug(f"Purged {count} expired rate-limit tombstones")
        return count


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
            logger.debug(f"Updated user: {mask_email(email)}")
        else:
            # Create new user
            user = UserDB(
                google_sub=google_sub,
                email=email,
                name=name,
            )
            self.db.add(user)
            logger.info(f"Created new user: {mask_email(email)}")

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, google_sub: str) -> bool:
        """Delete a user and all their submissions (cascade)."""
        user = self.get_by_google_sub(google_sub)
        if user:
            self.db.delete(user)
            self.db.commit()
            logger.info(f"Deleted user: {mask_email(user.email)}")
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
        issue_type: IssueType = IssueType.NONE,
        abuse_score: int = 0,
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
            issue_type=issue_type,
            abuse_score=abuse_score,
            scoring_meta=scoring_meta,
        )
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        logger.debug(
            f"Created submission {id} for user {mask_user_id(user_id)} "
            f"(issue_type={issue_type.value})"
        )
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
            timestamp=ensure_utc(db_submission.timestamp),
            status=PydanticSubmissionStatus(db_submission.status.value),
            images=db_submission.images,
            score=db_submission.score,
            feedback=db_submission.feedback,
            error_message=db_submission.error_message,
            issue_type=PydanticIssueType(db_submission.issue_type.value),
            abuse_score=db_submission.abuse_score,
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
        issue_type: IssueType = IssueType.NONE,
        abuse_score: int = 0,
        scoring_meta: Optional[dict] = None,
    ) -> Optional[SubmissionDB]:
        """Update submission with final results."""
        submission = self.get_by_id(submission_id)
        if not submission:
            return None
        submission.status = status
        submission.score = score
        submission.feedback = feedback
        submission.issue_type = issue_type
        submission.abuse_score = abuse_score
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

    def get_user_submission_timestamps(
        self, user_id: str, hours: int = 24
    ) -> list[datetime]:
        """Ascending timestamps of a user's submissions inside the window.

        Only needed when a deleted-account carryover is in play, so the ordinary
        submit path never pays for it.
        """
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = (
            self.db.query(SubmissionDB.timestamp)
            .filter(
                SubmissionDB.user_id == user_id,
                SubmissionDB.timestamp >= threshold,
            )
            .order_by(SubmissionDB.timestamp)
            .all()
        )
        return [row[0] for row in rows]

    def get_all_submission_timestamps(self, hours: int = 24) -> list[datetime]:
        """Ascending timestamps of all submissions inside the window."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = (
            self.db.query(SubmissionDB.timestamp)
            .filter(SubmissionDB.timestamp >= threshold)
            .order_by(SubmissionDB.timestamp)
            .all()
        )
        return [row[0] for row in rows]

    def get_user_rate_limit_window(
        self, user_id: str, hours: int = 24
    ) -> tuple[int, Optional[datetime], Optional[datetime]]:
        """(count, oldest, newest) submission timestamps inside the window.

        Like get_user_rate_limit_info, but also returns the newest timestamp -
        needed when erasing an account, because that is when the last of the
        carried-over quota would have aged out had the account survived.
        """
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = (
            self.db.query(
                func.count(SubmissionDB.id),
                func.min(SubmissionDB.timestamp),
                func.max(SubmissionDB.timestamp),
            )
            .filter(
                SubmissionDB.user_id == user_id,
                SubmissionDB.timestamp >= threshold,
            )
            .first()
        )
        return (result[0] or 0), result[1], result[2]

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
        logger.info(f"Deleted {count} submissions for user {mask_user_id(user_id)}")
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
        issue_type_filter: Optional[str] = None,
    ) -> tuple[list[SubmissionDB], int]:
        """Get all submissions with pagination and filters.

        Used for admin panel to view all submissions across users.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            user_id_filter: Filter by user_id (exact match)
            status_filter: Filter by status (pending/processing/completed/failed)
            issue_type_filter: Filter by issue_type (none/wrong_task/injection)

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

        if issue_type_filter:
            try:
                issue_type_enum = IssueType(issue_type_filter)
                query = query.filter(SubmissionDB.issue_type == issue_type_enum)
            except ValueError:
                # Invalid issue_type, ignore filter but log for debugging
                logger.debug(f"Invalid issue_type filter ignored: {issue_type_filter}")

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
