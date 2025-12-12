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
