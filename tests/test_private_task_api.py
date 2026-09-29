"""HTTP API for private tasks ("Moje zadania").

Covers the rules a public deployment depends on: ownership (someone else's id
is a 404), rate limits on every AI call, no files left behind by any rejected
request, drafts that can be confirmed only once, and hints that open in order.
"""

import io
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
import app.private_tasks.routes as routes
from app.ai.factory import AIProviderError
from app.config import settings
from app.db import get_db
from app.db.models import AIUsageDB, PrivateTaskDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base
from app.models import ExtractedProblem, PrivateExtractionResult, PrivateTaskMeta

USER_ID = "user-1"
OTHER_USER_ID = "user-2"
CONTENT = "Wykaż, że dla każdej liczby całkowitej $n$ liczba $n^2+n$ jest parzysta."


def jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color=(200, 200, 200)).save(buf, "JPEG")
    return buf.getvalue()


def image_part(name="page.jpg", data=None):
    return ("images", (name, data if data is not None else jpeg_bytes(), "image/jpeg"))


class StubProvider:
    def __init__(self):
        self.extraction = PrivateExtractionResult(
            is_math_problem=True,
            abuse_score=0,
            problems=[
                ExtractedProblem(label="Zadanie 1", title="Parzystość", content=CONTENT,
                                 category="teoria_liczb", difficulty=2),
                ExtractedProblem(label="Zadanie 2", title="Trójkąt",
                                 content="W trójkącie $ABC$ kąt $C$ jest prosty. Wykaż, że $AB > AC$.",
                                 category="geometria", difficulty=1),
            ],
            meta={"model": "stub"},
        )
        self.extract_error = None
        self.meta = PrivateTaskMeta(hints=["h1", "h2", "h3"], category="algebra",
                                    difficulty=3, abuse_score=0, meta={"model": "stub"})
        self.meta_error = None
        self.meta_calls = 0

    async def extract_private_tasks(self, image_paths):
        assert all(p.exists() for p in image_paths)
        if self.extract_error:
            raise self.extract_error
        return self.extraction

    async def generate_private_task_meta(self, title, content):
        self.meta_calls += 1
        if self.meta_error:
            raise self.meta_error
        return self.meta


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "session_secret_key", "test-secret")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email="kid@example.com", name="Kid"))
    session.add(UserDB(google_sub=OTHER_USER_ID, email="other@example.com", name="Other"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def provider(monkeypatch):
    stub = StubProvider()
    monkeypatch.setattr(routes, "create_ai_provider", lambda: stub)
    return stub


@pytest.fixture
def current_user(monkeypatch):
    state = {"id": USER_ID}

    def user(request):
        return {"google_sub": state["id"], "email": f"{state['id']}@example.com"}

    async def member(request):
        return True

    monkeypatch.setattr(routes, "verify_auth", lambda request: True)
    monkeypatch.setattr(routes, "get_current_user_id", lambda request: state["id"])
    monkeypatch.setattr(routes, "get_current_user", user)
    monkeypatch.setattr(routes, "is_group_member_async", member)
    monkeypatch.setattr(routes, "_get_allowed_emails", lambda: set())
    return state


@pytest.fixture
def started(monkeypatch):
    """Background grading replaced by a recorder - the worker has its own tests."""
    calls = []

    async def fake_process(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(routes, "process_submission_background", fake_process)
    return calls


@pytest.fixture
def client(db, provider, current_user, started):
    def override_get_db():
        yield db

    main.app.dependency_overrides[get_db] = override_get_db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def files_under(*parts) -> list[str]:
    root = settings.uploads_dir.joinpath(*parts)
    if not root.exists():
        return []
    return sorted(str(p.relative_to(settings.uploads_dir)) for p in root.rglob("*") if p.is_file())


def typed_task(client, **overrides):
    body = {"title": "Parzystość", "content": CONTENT, **overrides}
    response = client.post("/api/private-tasks", json={"tasks": [body]})
    assert response.status_code == 200, response.text
    return response.json()["tasks"][0]


def extract(client, n=1):
    return client.post("/api/private-tasks/extract", files=[image_part(f"p{i}.jpg") for i in range(n)])


# --------------------------------------------------------------------- extract


class TestExtract:
    def test_returns_draft_with_problems(self, client, db):
        response = extract(client)

        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data["draft_id"]) == 16
        assert [p["label"] for p in data["problems"]] == ["Zadanie 1", "Zadanie 2"]
        assert len(data["photos"]) == 1
        assert files_under(USER_ID, "private", "_drafts", data["draft_id"])
        assert db.query(AIUsageDB).filter_by(kind="private_extract").count() == 1
        assert db.query(PrivateTaskDB).count() == 0

    def test_not_a_math_problem_leaves_nothing(self, client, provider, db):
        provider.extraction = PrivateExtractionResult(is_math_problem=False, problems=[])

        response = extract(client)

        assert response.status_code == 422
        assert files_under(USER_ID) == []
        # The call was made, so it still counts
        assert db.query(AIUsageDB).count() == 1

    def test_manipulation_attempt_leaves_nothing(self, client, provider):
        provider.extraction.abuse_score = 95

        response = extract(client)

        assert response.status_code == 422
        assert files_under(USER_ID) == []

    def test_provider_error_leaves_nothing(self, client, provider):
        provider.extract_error = AIProviderError("Analiza trwa zbyt długo. Spróbuj ponownie za chwilę.")

        response = extract(client)

        assert response.status_code == 502
        assert "zbyt długo" in response.json()["detail"]
        assert files_under(USER_ID) == []

    def test_broken_image_is_refused(self, client):
        response = client.post("/api/private-tasks/extract", files=[image_part("x.jpg", b"not an image")])
        assert response.status_code == 400
        assert files_under(USER_ID) == []

    def test_daily_cap(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_private_extracts_per_user_per_day", 2)
        assert extract(client).status_code == 200
        assert extract(client).status_code == 200

        response = extract(client)

        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0

    def test_global_cap(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_ai_usage_global_per_day", 1)
        db.add(AIUsageDB(user_id=OTHER_USER_ID, kind="private_create"))
        db.commit()

        assert extract(client).status_code == 429

    def test_allowlisted_user_is_not_capped(self, client, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_private_extracts_per_user_per_day", 0)
        monkeypatch.setattr(routes, "_get_allowed_emails", lambda: {f"{USER_ID}@example.com"})
        assert extract(client).status_code == 200


# ---------------------------------------------------------------------- create


class TestCreateFromDraft:
    def test_confirm_two_problems_copies_photos_per_task(self, client, db, provider):
        draft = extract(client, n=2).json()
        problems = draft["problems"]

        response = client.post("/api/private-tasks", json={
            "draft_id": draft["draft_id"],
            "tasks": [
                {"title": p["title"], "content": p["content"], "category": p["category"],
                 "difficulty": p["difficulty"], "source_label": "Broszura 4"}
                for p in problems
            ],
        })

        assert response.status_code == 200, response.text
        tasks = response.json()["tasks"]
        assert len(tasks) == 2
        for task in tasks:
            stored = db.get(PrivateTaskDB, task["id"])
            assert stored.origin == "photo"
            assert stored.hints == ["h1", "h2", "h3"]
            # the student's category wins over the AI's suggestion
            assert stored.category in {"teoria_liczb", "geometria"}
            assert len(stored.source_images) == 2
            assert files_under(USER_ID, "private", task["id"], "source") == sorted(stored.source_images)
        # draft consumed
        assert files_under(USER_ID, "private", "_drafts") == []
        assert provider.meta_calls == 2
        assert db.query(AIUsageDB).filter_by(kind="private_create").count() == 2

    def test_draft_cannot_be_confirmed_twice(self, client):
        draft = extract(client).json()
        body = {"draft_id": draft["draft_id"], "tasks": [{"title": "T", "content": CONTENT}]}

        assert client.post("/api/private-tasks", json=body).status_code == 200
        assert client.post("/api/private-tasks", json=body).status_code == 410

    def test_other_users_draft_is_gone(self, client, current_user):
        draft = extract(client).json()
        current_user["id"] = OTHER_USER_ID

        response = client.post("/api/private-tasks", json={
            "draft_id": draft["draft_id"], "tasks": [{"title": "T", "content": CONTENT}],
        })

        assert response.status_code == 410
        assert files_under(OTHER_USER_ID) == []

    def test_expired_draft_is_gone(self, client):
        draft = extract(client).json()
        old = time.time() - 25 * 3600
        for path in settings.uploads_dir.joinpath(USER_ID, "private", "_drafts", draft["draft_id"]).rglob("*"):
            os.utime(path, (old, old))

        response = client.post("/api/private-tasks", json={
            "draft_id": draft["draft_id"], "tasks": [{"title": "T", "content": CONTENT}],
        })

        assert response.status_code == 410

    def test_malformed_draft_id(self, client):
        response = client.post("/api/private-tasks", json={
            "draft_id": "../../etc", "tasks": [{"title": "T", "content": CONTENT}],
        })
        assert response.status_code == 422


class TestCreateTyped:
    def test_typed_task_gets_ai_category_when_student_left_it_blank(self, client, db):
        task = typed_task(client)

        stored = db.get(PrivateTaskDB, task["id"])
        assert stored.origin == "typed"
        assert stored.source_images == []
        assert stored.category == "algebra"
        assert stored.difficulty == 3

    def test_too_short_content_is_refused(self, client, db):
        response = client.post("/api/private-tasks", json={"tasks": [{"title": "T", "content": "1+1"}]})
        assert response.status_code == 422
        assert db.query(PrivateTaskDB).count() == 0

    def test_unknown_category_is_refused(self, client):
        response = client.post("/api/private-tasks", json={
            "tasks": [{"title": "T", "content": CONTENT, "category": "calculus"}],
        })
        assert response.status_code == 422

    def test_hint_generation_failure_still_saves_task(self, client, provider, db):
        provider.meta_error = AIProviderError("Przepraszamy, coś poszło nie tak.")

        task = typed_task(client, category="geometria", difficulty=4)

        stored = db.get(PrivateTaskDB, task["id"])
        assert stored.hints == []
        assert stored.category == "geometria"

    def test_manipulation_in_text_saves_nothing(self, client, provider, db):
        provider.meta.abuse_score = 90

        response = client.post("/api/private-tasks", json={"tasks": [{"title": "T", "content": CONTENT}]})

        assert response.status_code == 422
        assert db.query(PrivateTaskDB).count() == 0

    def test_creation_cap_counts_the_whole_batch(self, client, monkeypatch, db):
        monkeypatch.setattr(settings, "rate_limit_private_tasks_per_user_per_day", 2)
        typed_task(client)

        response = client.post("/api/private-tasks", json={"tasks": [
            {"title": "A", "content": CONTENT}, {"title": "B", "content": CONTENT},
        ]})

        assert response.status_code == 429
        assert db.query(PrivateTaskDB).count() == 1

    def test_at_most_eight_tasks_per_request(self, client):
        response = client.post("/api/private-tasks", json={
            "tasks": [{"title": f"T{i}", "content": CONTENT} for i in range(9)],
        })
        assert response.status_code == 422


# -------------------------------------------------------- read / edit / delete


class TestOwnership:
    @pytest.mark.parametrize("method,suffix", [
        ("get", ""), ("patch", ""), ("delete", ""),
        ("post", "/hints/1"), ("post", "/regenerate-hints"),
    ])
    def test_other_users_task_is_404(self, client, current_user, method, suffix):
        task = typed_task(client)
        current_user["id"] = OTHER_USER_ID

        kwargs = {"json": {"title": "x"}} if method == "patch" else {}
        response = getattr(client, method)(f"/api/private-tasks/{task['id']}{suffix}", **kwargs)

        assert response.status_code == 404

    def test_other_users_task_submit_is_404(self, client, current_user):
        task = typed_task(client)
        current_user["id"] = OTHER_USER_ID
        response = client.post(f"/api/private-tasks/{task['id']}/submit", files=[image_part()])
        assert response.status_code == 404
        assert files_under(OTHER_USER_ID) == []

    def test_list_shows_only_own_tasks(self, client, current_user):
        typed_task(client)
        current_user["id"] = OTHER_USER_ID
        assert client.get("/api/private-tasks").json()["tasks"] == []


class TestReadEditDelete:
    def test_detail_never_contains_unrevealed_hints(self, client):
        task = typed_task(client)

        detail = client.get(f"/api/private-tasks/{task['id']}").json()

        assert detail["task"]["hints_count"] == 3
        assert detail["task"]["revealed_hints"] == []
        assert "hints" not in detail["task"]
        assert "h1" not in str(detail)

    def test_list_summarises_scores(self, client, db):
        task = typed_task(client)
        db.add(SubmissionDB(id="s1", user_id=USER_ID, private_task_id=task["id"], images=[],
                            status=SubmissionStatus.COMPLETED, score=5))
        db.commit()

        listed = client.get("/api/private-tasks").json()

        assert listed["total_count"] == 1
        assert listed["tasks"][0]["best_score"] == 5
        assert listed["tasks"][0]["attempts"] == 1
        # the list does not ship full statements
        assert "content" not in listed["tasks"][0]

    def test_patch_updates_and_validates(self, client):
        task = typed_task(client)

        ok = client.patch(f"/api/private-tasks/{task['id']}", json={"title": "Nowy", "source_label": ""})
        bad = client.patch(f"/api/private-tasks/{task['id']}", json={"difficulty": 7})

        assert ok.status_code == 200
        assert ok.json()["task"]["title"] == "Nowy"
        assert ok.json()["task"]["source_label"] is None
        assert bad.status_code == 422

    def test_delete_removes_rows_and_files(self, client, db):
        draft = extract(client).json()
        task = client.post("/api/private-tasks", json={
            "draft_id": draft["draft_id"], "tasks": [{"title": "T", "content": CONTENT}],
        }).json()["tasks"][0]
        assert client.post(f"/api/private-tasks/{task['id']}/submit", files=[image_part()]).status_code == 200
        assert files_under(USER_ID, "private", task["id"])

        response = client.delete(f"/api/private-tasks/{task['id']}")

        assert response.status_code == 200
        assert db.query(PrivateTaskDB).count() == 0
        assert db.query(SubmissionDB).count() == 0
        assert files_under(USER_ID, "private", task["id"]) == []
        assert not settings.uploads_dir.joinpath(USER_ID, "private", task["id"]).exists()


class TestHints:
    def test_hints_open_in_order(self, client):
        task = typed_task(client)

        assert client.post(f"/api/private-tasks/{task['id']}/hints/2").status_code == 409
        first = client.post(f"/api/private-tasks/{task['id']}/hints/1")
        second = client.post(f"/api/private-tasks/{task['id']}/hints/2")

        assert first.json()["hint"] == "h1"
        assert second.json()["hint"] == "h2"
        detail = client.get(f"/api/private-tasks/{task['id']}").json()
        assert detail["task"]["revealed_hints"] == ["h1", "h2"]

    def test_missing_hint_is_404(self, client):
        task = typed_task(client)
        assert client.post(f"/api/private-tasks/{task['id']}/hints/5").status_code == 404

    def test_regenerate_replaces_hints_and_counts(self, client, provider, db):
        task = typed_task(client)
        client.post(f"/api/private-tasks/{task['id']}/hints/1")
        provider.meta = PrivateTaskMeta(hints=["new1", "new2"], abuse_score=0)

        response = client.post(f"/api/private-tasks/{task['id']}/regenerate-hints")

        assert response.status_code == 200
        stored = db.get(PrivateTaskDB, task["id"])
        assert stored.hints == ["new1", "new2"]
        assert stored.hints_revealed == 0
        assert db.query(AIUsageDB).filter_by(kind="private_regen").count() == 1


# ---------------------------------------------------------------------- submit


class TestSubmit:
    def test_submit_creates_pending_private_submission(self, client, db, started):
        task = typed_task(client)
        client.post(f"/api/private-tasks/{task['id']}/hints/1")
        client.post(f"/api/private-tasks/{task['id']}/hints/2")

        response = client.post(f"/api/private-tasks/{task['id']}/submit", files=[image_part()])

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["ws_path"] == f"/ws/submissions/{data['submission_id']}"
        sub = db.get(SubmissionDB, data["submission_id"])
        assert sub.private_task_id == task["id"]
        assert sub.year is None
        assert sub.status == SubmissionStatus.PENDING
        assert sub.hints_used == 2
        assert db.get(PrivateTaskDB, task["id"]).pending_hints_used == 0
        assert files_under(USER_ID, "private", task["id"]) == sorted(sub.images)
        assert started[0]["private_task"]["content"] == CONTENT
        assert started[0]["year"] is None

    def test_submit_shares_the_daily_submission_limit(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_submissions_per_user_per_day", 1)
        task = typed_task(client)
        db.add(SubmissionDB(id="omj00001", user_id=USER_ID, year="2024", etap="etap1",
                            task_number=1, images=[]))
        db.commit()

        response = client.post(f"/api/private-tasks/{task['id']}/submit", files=[image_part()])

        assert response.status_code == 429
        assert files_under(USER_ID, "private", task["id"]) == []

    def test_submit_without_images(self, client):
        task = typed_task(client)
        response = client.post(f"/api/private-tasks/{task['id']}/submit", files=[])
        assert response.status_code in (400, 422)

    def test_submit_bumps_last_activity(self, client, db):
        task = typed_task(client)
        stored = db.get(PrivateTaskDB, task["id"])
        stored.last_activity_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=300)
        db.commit()

        client.post(f"/api/private-tasks/{task['id']}/submit", files=[image_part()])

        db.refresh(stored)
        assert stored.last_activity_at > datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)


class TestAuth:
    def test_anonymous_is_401(self, client, monkeypatch):
        monkeypatch.setattr(routes, "verify_auth", lambda request: False)
        monkeypatch.setattr(routes, "get_current_user_id", lambda request: None)
        assert client.get("/api/private-tasks").status_code == 401

    def test_non_member_is_403(self, client, monkeypatch):
        async def not_member(request):
            return False
        monkeypatch.setattr(routes, "is_group_member_async", not_member)
        assert client.get("/api/private-tasks").status_code == 403
