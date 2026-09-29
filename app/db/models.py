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
    CheckConstraint,
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
    private_tasks = relationship("PrivateTaskDB", back_populates="user", cascade="all, delete-orphan")
    ai_usage = relationship("AIUsageDB", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


# A submission points at exactly one task: an OMJ one or a private one
SUBMISSION_TASK_REF_CHECK = (
    "(year IS NOT NULL AND etap IS NOT NULL AND task_number IS NOT NULL "
    "AND private_task_id IS NULL) OR "
    "(year IS NULL AND etap IS NULL AND task_number IS NULL "
    "AND private_task_id IS NOT NULL)"
)


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

    # Task identification: EITHER an OMJ task (year, etap, task_number) OR a
    # private task (private_task_id) - never both, never neither. Enforced by
    # ck_submissions_task_ref, because every OMJ aggregate (progress graph,
    # stats) relies on private rows having NULL OMJ fields.
    year = Column(String(10), nullable=True)
    etap = Column(String(10), nullable=True)
    task_number = Column(Integer, nullable=True)
    private_task_id = Column(
        String(12),
        ForeignKey("private_tasks.id", ondelete="CASCADE"),
        nullable=True,
    )

    # How many hints of a private task the student had revealed before this
    # submission (0 for OMJ tasks, whose hints are revealed client-side only)
    hints_used = Column(Integer, nullable=False, default=0, server_default="0")

    # Submission data
    timestamp = Column(DateTime, nullable=False, default=utc_now)
    status = Column(
        Enum(SubmissionStatus),
        nullable=False,
        default=SubmissionStatus.COMPLETED
    )

    # Image paths stored as JSON array
    images = Column(JSON, nullable=False)
    # Typed solution: plain text with $LaTeX$ (max settings.submission_text_max_chars
    # code points). A row has images, solution_text or both; images stays NOT NULL
    # ([] for a text-only submission). Never edited after submit, so the column
    # is its own snapshot - nothing goes into scoring_meta for it.
    solution_text = Column(Text, nullable=True)

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
    private_task = relationship("PrivateTaskDB", back_populates="submissions")

    # Indexes for common queries
    __table_args__ = (
        # Progress queries: get user's best score per task
        Index("ix_submissions_user_task", "user_id", "year", "etap", "task_number"),
        # Task stats: get all submissions for a task
        Index("ix_submissions_task", "year", "etap", "task_number"),
        # Private task history
        Index("ix_submissions_user_private_task", "user_id", "private_task_id"),
        CheckConstraint(SUBMISSION_TASK_REF_CHECK, name="ck_submissions_task_ref"),
    )

    def __repr__(self) -> str:
        return f"<Submission {self.id} task={self.year}/{self.etap}/{self.task_number} score={self.score}>"


class PrivateTaskDB(Base):
    """A task a student added themselves - from a photo or typed in.

    Visible only to its owner. The statement is text the student confirmed
    (possibly after AI extraction from a photo of a booklet page), so it may be
    third-party material: it is never shared, listed or indexed, and it expires
    with retention_private_task_months after the last activity.
    """

    __tablename__ = "private_tasks"

    # secrets.token_urlsafe(9) - 12 URL-safe chars, unguessable
    id = Column(String(12), primary_key=True)

    user_id = Column(
        String(255),
        ForeignKey("users.google_sub", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String(120), nullable=False)
    content = Column(Text, nullable=False)
    source_label = Column(String(120), nullable=True)
    category = Column(String(20), nullable=True)
    difficulty = Column(Integer, nullable=True)

    # Up to 4 progressive hints. Revealed one at a time through the API so
    # "solved with a hint" can be recorded honestly.
    hints = Column(JSON, nullable=False, default=list)
    # Highest hint number ever revealed - a reload shows these again
    hints_revealed = Column(Integer, nullable=False, default=0, server_default="0")
    # Highest hint revealed since the last submission; copied onto the next
    # submission's hints_used and reset
    pending_hints_used = Column(Integer, nullable=False, default=0, server_default="0")

    # Relative paths of the original photos of the problem ([] when typed)
    source_images = Column(JSON, nullable=False, default=list)
    origin = Column(String(10), nullable=False)  # "photo" | "typed"

    # Model, tokens, cost of the extraction/hint calls. A "thinking" key, if
    # present, is stripped by retention like submissions.scoring_meta.
    extraction_meta = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    # Bumped on create, edit and every submission - drives retention
    last_activity_at = Column(DateTime, nullable=False, default=utc_now, index=True)

    user = relationship("UserDB", back_populates="private_tasks")
    submissions = relationship(
        "SubmissionDB",
        back_populates="private_task",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_private_tasks_user_activity", "user_id", "last_activity_at"),
    )

    def __repr__(self) -> str:
        return f"<PrivateTask {self.id}>"


class AIUsageDB(Base):
    """One AI call that is not a submission (task extraction, hint generation).

    Submissions are rate-limited by counting submission rows. The calls made
    while creating a private task have no such row, so without this table they
    would be unlimited - a public page that turns any photo into a Gemini call.
    Holds no content: kind, time, and model/token/cost numbers only.
    """

    __tablename__ = "ai_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String(255),
        ForeignKey("users.google_sub", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "private_extract" | "private_create" | "private_regen"
    kind = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now, index=True)
    meta = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<AIUsage {self.kind} at {self.created_at}>"


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

    # Non-submission AI calls (ai_usage rows) inside the window - same reason
    ai_usage_count = Column(Integer, nullable=False, default=0, server_default="0")

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
