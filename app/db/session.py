"""Database session management for OMJ Validator.

Provides SQLAlchemy engine, session factory, and FastAPI dependency
for database access.
"""

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from ..config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy base class for declarative models
Base = declarative_base()

# Create PostgreSQL engine
engine = create_engine(
    settings.db_url,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,  # Verify connections before use
)


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session.

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database by creating all tables.

    This is typically called on application startup. For production,
    use Alembic migrations instead.
    """
    # Import models to ensure they're registered with Base
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialized: {settings.db_url}")
