"""Submitting a solution from a pattern card records the pattern (and OMJ hints used)."""

import io
import pathlib

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
import app.private_tasks.routes as private_routes
import app.websocket.handler as handler
from app import storage
from app.config import settings
from app.db import get_db
from app.db.models import PrivateTaskDB, SubmissionDB, UserDB
from app.db.patterns import PatternRepository
from app.db.session import Base
from app.models import TaskInfo, TaskPdf

USER_ID = "user-1"
OTHER_USER_ID = "user-2"
PRIVATE_ID = "privtask0001"
FIXTURE_TASK_PDF = (
    pathlib.Path(__file__).parent / "fixtures" / "task_corpus" / "tasks" / "1999" / "etap1" / "zadania.pdf"
)


def jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color=(200, 200, 200)).save(buf, "JPEG")
    return [("images", ("a.jpg", buf.getvalue(), "image/jpeg"))]


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "session_secret_key", "test-secret")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email="kid@example.com"))
    session.add(UserDB(google_sub=OTHER_USER_ID, email="other@example.com"))
    session.add(PrivateTaskDB(id=PRIVATE_ID, user_id=USER_ID, title="Wymyślone",
                              content="Wymyślone zadanie o parzystości.", hints=[],
                              source_images=[], origin="typed"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db, monkeypatch):
    main.app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(main, "get_task_pdf_path", lambda year, etap: FIXTURE_TASK_PDF)
    monkeypatch.setattr(main, "get_solution_pdf_path", lambda year, etap: None)
    user = {"google_sub": USER_ID, "email": "kid@example.com"}
    for module in (main, private_routes):
        monkeypatch.setattr(module, "verify_auth", lambda request: True)
        monkeypatch.setattr(module, "get_current_user_id", lambda request: USER_ID)
        monkeypatch.setattr(module, "get_current_user", lambda request: user)
        monkeypatch.setattr(module, "_get_allowed_emails", lambda: set())

    async def member(request):
        return True

    monkeypatch.setattr(private_routes, "is_group_member_async", member)
    task = TaskInfo(year="2024", etap="etap1", number=1, title="Zadanie 1", pdf=TaskPdf(tasks="t.pdf"),
                    hints=["a", "b", "c", "d"])
    monkeypatch.setattr(storage, "get_task", lambda y, e, n: task if (y, e, n) == ("2024", "etap1", 1) else None)

    async def no_grading(**kwargs):
        return None

    monkeypatch.setattr(handler, "process_submission_background", no_grading)
    monkeypatch.setattr(private_routes, "process_submission_background", no_grading)
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def pattern(db, user_id=USER_ID):
    from datetime import date

    return PatternRepository(db).create(
        user_id, trigger="Pytają o parzystość", action="Sprawdź sumę modulo 2", example=None,
        category=None, skills=[], origin="own", refinement=[], due_on=date(2026, 10, 2),
    )


def submitted(db, response):
    assert response.status_code == 200, response.text
    return db.get(SubmissionDB, response.json()["submission_id"])


def test_omj_submit_records_own_pattern_and_clamps_hints(client, db):
    p = pattern(db)
    r = client.post("/task/2024/etap1/1/submit", files=jpeg(), data={"pattern_id": p.id, "hints_used": "9"})
    sub = submitted(db, r)
    assert sub.pattern_id == p.id
    assert sub.hints_used == 4


def test_omj_submit_ignores_foreign_pattern(client, db):
    p = pattern(db, user_id=OTHER_USER_ID)
    sub = submitted(db, client.post("/task/2024/etap1/1/submit", files=jpeg(),
                                    data={"pattern_id": p.id, "hints_used": "-3"}))
    assert sub.pattern_id is None
    assert sub.hints_used == 0


def test_omj_submit_without_fields_unchanged(client, db):
    sub = submitted(db, client.post("/task/2024/etap1/1/submit", files=jpeg()))
    assert (sub.pattern_id, sub.hints_used) == (None, 0)


def test_private_submit_records_pattern_and_ignores_client_hints(client, db):
    p = pattern(db)
    sub = submitted(db, client.post(f"/api/private-tasks/{PRIVATE_ID}/submit", files=jpeg(),
                                    data={"pattern_id": p.id, "hints_used": "3"}))
    assert sub.pattern_id == p.id
    assert sub.hints_used == 0
