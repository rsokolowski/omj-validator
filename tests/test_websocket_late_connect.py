"""A client connecting after grading finished gets the result from the database.

The task page opened by "Odczytaj zadanie i oceń" connects only after a page
navigation; by then the in-memory progress entry may already be gone.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
from app.config import settings
from app.db import get_db
from app.db.models import SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", True)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    db.add(UserDB(google_sub="anonymous", email="kid@example.com", name="Kid"))
    db.add(SubmissionDB(id="aaaa0001", user_id="anonymous", year="2024", etap="etap1",
                        task_number=1, images=[], status=SubmissionStatus.COMPLETED,
                        score=5, feedback="Dobrze, brakuje sprawdzenia."))
    db.add(SubmissionDB(id="aaaa0002", user_id="anonymous", year="2024", etap="etap1",
                        task_number=1, images=[], status=SubmissionStatus.FAILED,
                        error_message="Traceback: internal detail"))
    db.commit()

    def override_get_db():
        yield db

    main.app.dependency_overrides[get_db] = override_get_db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()
    db.close()


def test_completed_submission_sends_stored_result(client):
    with client.websocket_connect("/ws/submissions/aaaa0001") as ws:
        msg = ws.receive_json()
    assert msg == {
        "type": "completed",
        "submission_id": "aaaa0001",
        "score": 5,
        "feedback": "Dobrze, brakuje sprawdzenia.",
    }


def test_failed_submission_sends_generic_error(client):
    with client.websocket_connect("/ws/submissions/aaaa0002") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "Traceback" not in msg["error"]
