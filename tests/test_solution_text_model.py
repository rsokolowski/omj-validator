"""submissions.solution_text: the typed solution lives on the row, never on disk.

A row has images, solution_text or both. images stays NOT NULL ([] for a
text-only submission), so every existing file-walking code path keeps working.
"""

import importlib.util
import pathlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.models import SubmissionDB, SubmissionStatus, UserDB
from app.db.repositories import SubmissionRepository
from app.db.session import Base
from app.models import Submission
from app.retention import erase_user_data, purge_expired_submissions

USER_ID = "user-1"
TEXT = "Niech $n$ będzie liczbą całkowitą. Wtedy $n(n+1)$ jest parzyste."


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email="kid@example.com", name="Kid"))
    session.commit()
    yield session
    session.close()


def test_migration_007_follows_006():
    path = pathlib.Path(__file__).parent.parent / "alembic" / "versions" / "007_add_solution_text.py"
    spec = importlib.util.spec_from_file_location("m007", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "007"
    assert module.down_revision == "006"


def test_column_is_nullable_text():
    column = SubmissionDB.__table__.c.solution_text
    assert column.nullable is True
    assert str(column.type).upper() == "TEXT"


def test_repository_stores_text_only_submission(db):
    repo = SubmissionRepository(db)
    repo.create(
        id="txt00001", user_id=USER_ID, year="2024", etap="etap1", task_number=1,
        images=[], status=SubmissionStatus.PENDING, solution_text=TEXT,
    )
    row = db.get(SubmissionDB, "txt00001")
    assert row.images == []
    assert row.solution_text == TEXT

    api = repo.to_pydantic(row)
    assert isinstance(api, Submission)
    assert api.solution_text == TEXT
    assert api.model_dump(mode="json")["solution_text"] == TEXT


def test_default_is_none(db):
    repo = SubmissionRepository(db)
    repo.create(id="img00001", user_id=USER_ID, year="2024", etap="etap1",
                task_number=1, images=["u/2024/etap1/1/a.jpg"])
    assert db.get(SubmissionDB, "img00001").solution_text is None
    assert Submission.model_fields["solution_text"].default is None


def _old_text_only_row(db, submission_id="old00001"):
    stamp = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=800)
    db.add(SubmissionDB(
        id=submission_id, user_id=USER_ID, year="2024", etap="etap1", task_number=1,
        timestamp=stamp, created_at=stamp, status=SubmissionStatus.COMPLETED,
        images=[], solution_text=TEXT, score=5, feedback="ok",
    ))
    db.commit()


def test_retention_purges_a_text_only_submission(db):
    _old_text_only_row(db)
    report = purge_expired_submissions(db, months=24)
    assert report.submissions_deleted == 1
    assert db.query(SubmissionDB).count() == 0


def test_erasure_removes_a_text_only_submission(db):
    _old_text_only_row(db)
    report = erase_user_data(db, USER_ID)
    assert report.submissions_deleted == 1
    assert db.query(SubmissionDB).count() == 0
    assert db.query(UserDB).count() == 0
