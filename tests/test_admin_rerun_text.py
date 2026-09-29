"""Admin re-run of a text-only submission copies the text and no longer 409s."""

import pathlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
import app.websocket.handler as handler
from app.config import settings
from app.db import get_db
from app.db.models import SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base

USER_ID = "user-1"
TEXT = "Niech $n$ będzie liczbą całkowitą. Wtedy $n(n+1)$ jest parzyste."
FIXTURE_TASK_PDF = (
    pathlib.Path(__file__).parent / "fixtures" / "task_corpus" / "tasks" / "1999" / "etap1" / "zadania.pdf"
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "session_secret_key", "test-secret-key")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email="kid@example.com", name="Kid"))
    session.add(SubmissionDB(id="orig0001", user_id=USER_ID, year="2024", etap="etap1",
                             task_number=1, images=[], solution_text=TEXT,
                             status=SubmissionStatus.COMPLETED, score=5, feedback="ok"))
    session.add(SubmissionDB(id="empty001", user_id=USER_ID, year="2024", etap="etap1",
                             task_number=1, images=[], status=SubmissionStatus.FAILED))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def admin_client(db, monkeypatch):
    def override_get_db():
        yield db

    main.app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(main, "_require_admin", lambda request: None)

    async def no_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(main, "_record_admin_access", no_audit)
    monkeypatch.setattr(main, "get_task_pdf_path", lambda year, etap: FIXTURE_TASK_PDF)

    calls = []

    async def fake_process(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(handler, "process_submission_background", fake_process)
    yield TestClient(main.app), calls
    main.app.dependency_overrides.clear()


def test_rerun_copies_the_text(admin_client, db):
    client, calls = admin_client

    response = client.post("/api/admin/submissions/orig0001/rerun")

    assert response.status_code == 200, response.text
    new_id = response.json()["submission_id"]
    rows = db.query(SubmissionDB).filter(SubmissionDB.solution_text == TEXT).all()
    assert len(rows) == 2, "original untouched, copy created"
    copy = next(r for r in rows if r.id != "orig0001")
    assert copy.images == []
    assert copy.status == SubmissionStatus.PENDING
    assert calls[0]["solution_text"] == TEXT
    assert calls[0]["image_paths"] == []
    assert copy.id == new_id


def test_rerun_with_neither_images_nor_text_is_409(admin_client):
    client, _ = admin_client
    response = client.post("/api/admin/submissions/empty001/rerun")
    assert response.status_code == 409
    assert response.json()["detail"] == "Submission has no images or text to re-run"
