"""Students never receive grading internals; admins still do.

Audit finding: the task detail and history endpoints returned the whole
Submission, including scoring_meta (raw model "thinking", cost, model) and the
abuse verdict (issue_type "injection", abuse_score). The private task detail
dropped scoring_meta but still sent the verdict.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
import app.private_tasks.routes as private_routes
from app.config import settings
from app.db import get_db
from app.db.models import IssueType, PrivateTaskDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base
from app.models import STUDENT_HIDDEN_SUBMISSION_FIELDS

USER_ID = "user-1"
USER_EMAIL = "kid@example.com"
ADMIN_EMAIL = "admin@example.com"
PRIVATE_ID = "privtask0001"
HIDDEN = {"scoring_meta", "issue_type", "abuse_score"}
SECRET_THINKING = "the model's private reasoning"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "session_secret_key", "test-secret-key")
    monkeypatch.setattr(settings, "admin_emails", ADMIN_EMAIL)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(id=USER_ID, google_sub=USER_ID, email=USER_EMAIL, name="Kid"))
    session.add(PrivateTaskDB(id=PRIVATE_ID, user_id=USER_ID, title="T", content="Treść",
                              hints=[], source_images=[], origin="typed"))
    flagged = dict(
        user_id=USER_ID, images=[], status=SubmissionStatus.COMPLETED, score=0,
        feedback="ok", issue_type=IssueType.INJECTION, abuse_score=97,
        scoring_meta={"thinking": SECRET_THINKING, "cost_usd": 0.01, "model": "m"},
    )
    session.add(SubmissionDB(id="omjsub01", year="2024", etap="etap1", task_number=1, **flagged))
    session.add(SubmissionDB(id="prvsub01", private_task_id=PRIVATE_ID, **flagged))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def as_user(monkeypatch):
    """Signed in as USER_ID with USER_EMAIL; tests may switch the e-mail to the admin's."""
    state = {"email": USER_EMAIL}

    def user(request):
        return {"user_id": USER_ID, "email": state["email"], "name": "Kid"}

    async def member(request):
        return True

    for module in (main, private_routes):
        monkeypatch.setattr(module, "verify_auth", lambda request: True)
        monkeypatch.setattr(module, "get_current_user_id", lambda request: USER_ID)
        monkeypatch.setattr(module, "get_current_user", user)
        monkeypatch.setattr(module, "is_group_member_async", member)
    return state


@pytest.fixture
def client(db, as_user):
    main.app.dependency_overrides[get_db] = lambda: db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def assert_student_safe(submission: dict):
    assert HIDDEN.isdisjoint(submission), sorted(HIDDEN & submission.keys())
    assert SECRET_THINKING not in str(submission)
    assert "injection" not in str(submission)


def test_hidden_fields_constant():
    assert STUDENT_HIDDEN_SUBMISSION_FIELDS == HIDDEN


@pytest.mark.parametrize("url", ["/api/task/2024/etap1/1", "/api/task/2024/etap1/1/history"])
def test_omj_endpoints_hide_internals(client, url):
    response = client.get(url)

    assert response.status_code == 200, response.text
    [submission] = response.json()["submissions"]
    assert submission["id"] == "omjsub01"
    assert submission["score"] == 0 and submission["feedback"] == "ok"
    assert_student_safe(submission)


def test_private_task_detail_hides_internals(client):
    response = client.get(f"/api/private-tasks/{PRIVATE_ID}")

    assert response.status_code == 200, response.text
    [submission] = response.json()["submissions"]
    assert_student_safe(submission)


def test_my_submissions_hides_internals(client):
    response = client.get("/api/my-submissions")

    assert response.status_code == 200, response.text
    for submission in response.json()["submissions"]:
        assert_student_safe(submission)


def test_admin_still_sees_the_verdict(client, as_user):
    as_user["email"] = ADMIN_EMAIL

    response = client.get("/api/admin/submissions")

    assert response.status_code == 200, response.text
    by_id = {s["id"]: s for s in response.json()["submissions"]}
    assert by_id["omjsub01"]["issue_type"] == "injection"
    assert by_id["omjsub01"]["abuse_score"] == 97
