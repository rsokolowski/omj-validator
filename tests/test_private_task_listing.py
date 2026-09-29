"""Private submissions in "Moje rozwiązania" and in the admin panel."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
from app.config import settings
from app.db import get_db
from app.db.models import PrivateTaskDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base

ADMIN_ID = "admin-1"
ADMIN_EMAIL = "admin@example.com"
STUDENT_ID = "student-1"
TASK_ID = "abcdefghijkl"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "admin_emails", ADMIN_EMAIL)
    monkeypatch.setattr(settings, "session_secret_key", "test-secret-key")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    session.audit_session_factory = factory
    session.add(UserDB(google_sub=ADMIN_ID, email=ADMIN_EMAIL, name="Admin"))
    session.add(UserDB(google_sub=STUDENT_ID, email="kid@example.com", name="Kid"))
    session.add(PrivateTaskDB(id=TASK_ID, user_id=STUDENT_ID, title="Moje zadanie",
                              content="Wymyślona treść zadania do testów.", hints=[],
                              source_images=[], origin="typed", category="algebra"))
    photo = settings.uploads_dir / STUDENT_ID / "private" / TASK_ID / "sol.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"x")
    session.add(SubmissionDB(
        id="prv00001", user_id=STUDENT_ID, private_task_id=TASK_ID,
        images=[f"{STUDENT_ID}/private/{TASK_ID}/sol.jpg"],
        status=SubmissionStatus.COMPLETED, score=5, feedback="ok",
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        scoring_meta={"task_snapshot": {"title": "Stary tytuł", "content": "Stara treść zadania."}},
    ))
    session.add(SubmissionDB(
        id="omj00001", user_id=STUDENT_ID, year="2024", etap="etap1", task_number=1,
        images=[], status=SubmissionStatus.COMPLETED, score=3, feedback="ok",
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    session.commit()
    yield session
    session.close()


def make_client(db, monkeypatch, user_id, email):
    def override_get_db():
        yield db

    main.app.dependency_overrides[get_db] = override_get_db
    user = {"google_sub": user_id, "email": email}
    monkeypatch.setattr(main, "verify_auth", lambda request: True)
    monkeypatch.setattr(main, "get_current_user_id", lambda request: user_id)
    monkeypatch.setattr(main, "get_current_user", lambda request: user)
    monkeypatch.setattr("app.db.SessionLocal", db.audit_session_factory)
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    main.app.dependency_overrides.clear()


def test_my_submissions_lists_private_submission_with_task_title(db, monkeypatch):
    client = make_client(db, monkeypatch, STUDENT_ID, "kid@example.com")

    data = client.get("/api/my-submissions").json()

    by_id = {s["id"]: s for s in data["submissions"]}
    private = by_id["prv00001"]
    assert private["private_task_id"] == TASK_ID
    assert private["task_title"] == "Moje zadanie"
    assert private["max_score"] == 6
    assert private["task_categories"] == ["algebra"]
    assert private["year"] is None
    assert by_id["omj00001"]["private_task_id"] is None
    assert data["stats"]["tasks_attempted"] == 2


def test_my_submissions_etap_filter_hides_private(db, monkeypatch):
    client = make_client(db, monkeypatch, STUDENT_ID, "kid@example.com")
    data = client.get("/api/my-submissions?etap=etap1").json()
    assert [s["id"] for s in data["submissions"]] == ["omj00001"]


def test_admin_list_labels_private_submission(db, monkeypatch):
    client = make_client(db, monkeypatch, ADMIN_ID, ADMIN_EMAIL)

    data = client.get("/api/admin/submissions").json()

    private = next(s for s in data["submissions"] if s["id"] == "prv00001")
    assert private["private_task_id"] == TASK_ID
    assert private["task_title"] == "Moje zadanie"


def test_admin_rerun_of_private_submission_grades_the_snapshot(db, monkeypatch):
    client = make_client(db, monkeypatch, ADMIN_ID, ADMIN_EMAIL)
    started = []

    async def fake_process(**kwargs):
        started.append(kwargs)

    monkeypatch.setattr("app.websocket.handler.process_submission_background", fake_process)

    response = client.post("/api/admin/submissions/prv00001/rerun")

    assert response.status_code == 200, response.text
    new = db.get(SubmissionDB, response.json()["submission_id"])
    assert new.private_task_id == TASK_ID
    assert new.year is None
    assert new.status == SubmissionStatus.PENDING
    assert started[0]["private_task"] == {
        "id": TASK_ID, "title": "Stary tytuł", "content": "Stara treść zadania.",
    }
