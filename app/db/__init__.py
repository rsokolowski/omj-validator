"""Database package for OMJ Validator.

Provides SQLAlchemy models, session management, and repository pattern
for data access.
"""

from .session import engine, SessionLocal, get_db, init_db, Base
from .models import UserDB, SubmissionDB, SubmissionStatus
from .repositories import UserRepository, SubmissionRepository

__all__ = [
    # Session management
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    "Base",
    # Models
    "UserDB",
    "SubmissionDB",
    "SubmissionStatus",
    # Repositories
    "UserRepository",
    "SubmissionRepository",
]
