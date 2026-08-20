"""SQLAlchemy ORM models for OMJ Validator.

These models define the database schema. For API serialization,
use the Pydantic models in app/models.py.
"""

import enum
from datetime import datetime, timezone
from typing import Optional


def utc_now():
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Index,
    Enum,
    JSON,
)
from sqlalchemy.orm import relationship

from .session import Base


class SubmissionStatus(str, enum.Enum):
    """Status of a submission through the processing pipeline."""
    PENDING = "pending"          # Uploaded, awaiting processing
    PROCESSING = "processing"    # Being analyzed by AI
    COMPLETED = "completed"      # Successfully scored
    FAILED = "failed"            # Processing failed


class IssueType(str, enum.Enum):
    """Type of issue detected in a submission by abuse detection."""
    NONE = "none"              # No issues detected - normal submission
    WRONG_TASK = "wrong_task"  # Student submitted solution to different task
    INJECTION = "injection"    # Prompt injection attempt detected


class UserDB(Base):
    """User account linked to Google OAuth."""

    __tablename__ = "users"

    # Google's unique user identifier (from 'sub' claim in OAuth token)
    google_sub = Column(String(255), primary_key=True)

    # User profile info from Google
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    submissions = relationship("SubmissionDB", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class SubmissionDB(Base):
    """Student solution submission with AI scoring."""

    __tablename__ = "submissions"

    # Primary key (8-char UUID excerpt, matching existing format)
    id = Column(String(8), primary_key=True)

    # Foreign key to user
    user_id = Column(
        String(255),
        ForeignKey("users.google_sub", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Task identification
    year = Column(String(10), nullable=False)
    etap = Column(String(10), nullable=False)
    task_number = Column(Integer, nullable=False)

    # Submission data
    timestamp = Column(DateTime, nullable=False, default=utc_now)
    status = Column(
        Enum(SubmissionStatus),
        nullable=False,
        default=SubmissionStatus.COMPLETED
    )

    # Image paths stored as JSON array
    images = Column(JSON, nullable=False)

    # Scoring results (nullable for failed submissions)
    score = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Abuse detection
    issue_type = Column(
        Enum(IssueType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=IssueType.NONE,
        index=True  # For admin filtering
    )
    abuse_score = Column(Integer, nullable=False, default=0)  # 0-100 confidence

    # LLM metadata (model, tokens, cost, timing, raw response, etc.)
    scoring_meta = Column(JSON, nullable=True)

    # Row timestamp
    created_at = Column(DateTime, nullable=False, default=utc_now)

    # Relationships
    user = relationship("UserDB", back_populates="submissions")

    # Indexes for common queries
    __table_args__ = (
        # Progress queries: get user's best score per task
        Index("ix_submissions_user_task", "user_id", "year", "etap", "task_number"),
        # Task stats: get all submissions for a task
        Index("ix_submissions_task", "year", "etap", "task_number"),
    )

    def __repr__(self) -> str:
        return f"<Submission {self.id} task={self.year}/{self.etap}/{self.task_number} score={self.score}>"


class DeletedAccountQuotaDB(Base):
    """Rate-limit residue left behind when a user erases their account.

    Deleting an account removes its submissions, and the submission rows are
    what the 24h rate limits count. Without this table a user who hit the daily
    cap could delete the account, sign in again with the same Google account and
    get a fresh budget - repeatedly, until the whole global daily budget (and
    the Gemini bill that goes with it) was gone.

    So erasure leaves a tombstone: an HMAC of the Google sub (irreversible, and
    useless without the server-side salt), how many submissions were inside the
    window, and when the window ends. It carries no name, no e-mail, no readable
    identifier, and it is deleted as soon as the window closes - typically 24h.
    """

    __tablename__ = "deleted_account_quota"

    # HMAC-SHA256 of the user's google_sub, hex - see repositories.hash_user_id
    user_hash = Column(String(64), primary_key=True)

    # Submissions the deleted account made inside the rate limit window
    submission_count = Column(Integer, nullable=False, default=0)

    # Oldest counted submission, used for Retry-After / reset headers
    oldest_submission_at = Column(DateTime, nullable=True)

    # When this tombstone stops counting and may be deleted
    expires_at = Column(DateTime, nullable=False, index=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)

    def __repr__(self) -> str:
        return (
            f"<DeletedAccountQuota {self.user_hash[:8]}... "
            f"count={self.submission_count} expires={self.expires_at}>"
        )


class AdminAccessLogDB(Base):
    """Who looked at whose data in the admin panel (RODO art. 5(2)).

    An admin can read every submission, every uploaded photo and search users.
    Without a record of that there is no way to demonstrate accountability or to
    notice an admin browsing a particular child's work.

    Deliberately minimal: it stores identifiers and a resource label, never any
    content - no feedback text, no scores, no file bytes - so the audit trail
    cannot become the next place personal data leaks from. It is not exposed
    through any API; it is read directly from the database during an audit, and
    it expires like everything else (retention_admin_audit_months).
    """

    __tablename__ = "admin_access_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # The admin who looked. Staff acting in a professional capacity, and the
    # whole point of the record is that they are identifiable.
    admin_email = Column(String(255), nullable=False, index=True)

    # Whose data was looked at. NULL for listings not scoped to one user.
    # Replaced with an irreversible digest if that user later erases the account.
    subject_user_id = Column(String(255), nullable=True, index=True)

    # What was accessed, e.g. "admin_submissions_list", "upload", "user_search"
    resource = Column(String(64), nullable=False)

    # Optional identifier of the concrete object (submission id, upload path).
    # Never free-form user input - a search query would itself be personal data.
    resource_id = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)

    def __repr__(self) -> str:
        return (
            f"<AdminAccessLog {self.resource} by {self.admin_email} "
            f"at {self.created_at}>"
        )
