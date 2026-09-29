"""HTTP API for patterns ("Wzorce"): CRUD, links, queue, recall reviews, practice.

The AI endpoints have their own file (test_pattern_ai_api.py).
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
import app.private_tasks.routes as private_routes
from app import storage
from app.config import settings
from app.db import get_db
from app.db.models import PatternDB, PrivateTaskDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base
from app.models import TaskInfo, TaskPdf
from app.patterns import srs

USER_ID = "user-1"
OTHER_USER_ID = "user-2"
TODAY = date(2026, 10, 1)
PRIVATE_ID = "privtask0001"
FOREIGN_PRIVATE_ID = "privtask0002"

OMJ_TASKS = {
    ("2024", "etap1", 1): TaskInfo(year="2024", etap="etap1", number=1, title="Zadanie 1",
                                   pdf=TaskPdf(tasks="t.pdf"), difficulty=2, categories=["logika"]),
    ("2024", "etap2", 3): TaskInfo(year="2024", etap="etap2", number=3, title="Zadanie 3",
                                   pdf=TaskPdf(tasks="t.pdf"), difficulty=4, categories=["algebra"]),
}


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(settings, "session_secret_key", "test-secret")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email="kid@example.com"))
    session.add(UserDB(google_sub=OTHER_USER_ID, email="other@example.com"))
    for task_id, owner in ((PRIVATE_ID, USER_ID), (FOREIGN_PRIVATE_ID, OTHER_USER_ID)):
        session.add(PrivateTaskDB(id=task_id, user_id=owner, title="Wymyślone",
                                  content="Wymyślone zadanie o parzystości.", hints=[],
                                  source_images=[], origin="typed", difficulty=2))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def today(monkeypatch):
    state = {"today": TODAY}
    monkeypatch.setattr(srs, "today_warsaw", lambda: state["today"])
    return state


@pytest.fixture
def omj(monkeypatch):
    tasks = dict(OMJ_TASKS)
    monkeypatch.setattr(storage, "get_task", lambda y, e, n: tasks.get((y, e, n)))
    return tasks


@pytest.fixture
def current_user(monkeypatch):
    state = {"id": USER_ID}

    async def member(request):
        return True

    monkeypatch.setattr(private_routes, "verify_auth", lambda request: True)
    monkeypatch.setattr(private_routes, "get_current_user_id", lambda request: state["id"])
    monkeypatch.setattr(private_routes, "get_current_user",
                        lambda request: {"google_sub": state["id"], "email": f"{state['id']}@example.com"})
    monkeypatch.setattr(private_routes, "is_group_member_async", member)
    monkeypatch.setattr(private_routes, "_get_allowed_emails", lambda: set())
    return state


@pytest.fixture
def client(db, current_user, today, omj):
    main.app.dependency_overrides[get_db] = lambda: db
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def create(client, **overrides):
    body = {
        "trigger": "Pytają, czy da się dojść do pewnego stanu",
        "action": "Szukaj niezmiennika, np. parzystości sumy",
        "category": "kombinatoryka",
    }
    body.update(overrides)
    response = client.post("/api/patterns", json=body)
    assert response.status_code == 201, response.text
    return response.json()["pattern"]


def make_due(db, pattern_id, due=TODAY):
    db.get(PatternDB, pattern_id).due_on = due
    db.commit()


class TestCreate:
    def test_create_with_omj_source(self, client):
        p = create(client, source={"task_key": "2024_etap1_1"})
        assert p["level"] == 1
        assert p["due_on"] == (TODAY + timedelta(days=1)).isoformat()
        detail = client.get(f"/api/patterns/{p['id']}").json()["pattern"]
        [link] = detail["links"]
        assert (link["role"], link["status"], link["task_key"], link["available"]) == (
            "source", "accepted", "2024_etap1_1", True)
        assert link["url"] == "/task/2024/etap1/1"

    def test_create_with_own_private_source(self, client):
        p = create(client, source={"private_task_id": PRIVATE_ID})
        link = client.get(f"/api/patterns/{p['id']}").json()["pattern"]["links"][0]
        assert link["url"] == f"/moje-zadania/{PRIVATE_ID}"

    def test_foreign_private_source_is_404(self, client):
        r = client.post("/api/patterns", json={"trigger": "Wyzwalacz testowy", "action": "Akcja testowa",
                                               "source": {"private_task_id": FOREIGN_PRIVATE_ID}})
        assert r.status_code == 404

    def test_unknown_task_key_is_404(self, client):
        r = client.post("/api/patterns", json={"trigger": "Wyzwalacz testowy", "action": "Akcja testowa",
                                               "source": {"task_key": "1990_etap1_9"}})
        assert r.status_code == 404

    def test_validation(self, client):
        assert client.post("/api/patterns", json={"trigger": "ab", "action": "Akcja testowa"}).status_code == 422
        r = client.post("/api/patterns", json={"trigger": "Wyzwalacz", "action": "Akcja", "category": "calculus"})
        assert r.status_code == 422

    def test_unknown_skills_dropped(self, client):
        from app.skills import get_all_skills

        real = get_all_skills()[0].id
        p = create(client, skills=[real, "made_up"])
        assert p["skills"] == [real]


class TestReadAndEdit:
    def test_other_users_pattern_is_404(self, client, current_user):
        p = create(client)
        current_user["id"] = OTHER_USER_ID
        assert client.get(f"/api/patterns/{p['id']}").status_code == 404
        assert client.patch(f"/api/patterns/{p['id']}", json={"trigger": "Cudzy wyzwalacz"}).status_code == 404
        assert client.delete(f"/api/patterns/{p['id']}").status_code == 404

    def test_list_filters_by_task(self, client):
        linked = create(client, source={"task_key": "2024_etap1_1"})
        create(client)
        listed = client.get("/api/patterns", params={"task_key": "2024_etap1_1"}).json()["patterns"]
        assert [p["id"] for p in listed] == [linked["id"]]
        assert len(client.get("/api/patterns").json()["patterns"]) == 2

    def test_patch_fields_and_rounds(self, client):
        p = create(client)
        round_ = {"draft": {"raw": "szkic"}, "variants": [{"trigger": "W1 wyzwalacz", "action": "A1 akcja"}],
                  "questions": [], "verdict": "ok", "comment": "", "chosen": 0}
        for _ in range(11):
            r = client.patch(f"/api/patterns/{p['id']}", json={"append_round": round_})
            assert r.status_code == 200
        r = client.patch(f"/api/patterns/{p['id']}", json={"action": "Nowa akcja do wypróbowania"})
        body = r.json()["pattern"]
        assert body["action"] == "Nowa akcja do wypróbowania"
        detail = client.get(f"/api/patterns/{p['id']}").json()["pattern"]
        assert len(detail["refinement"]) == 10

    def test_archive_removes_from_queue(self, client, db):
        p = create(client)
        make_due(db, p["id"])
        assert client.get("/api/patterns/queue").json()["due_total"] == 1
        client.patch(f"/api/patterns/{p['id']}", json={"archived": True})
        assert client.get("/api/patterns/queue").json()["due_total"] == 0
        assert [x["id"] for x in client.get("/api/patterns", params={"archived": True}).json()["patterns"]] == [p["id"]]

    def test_delete_keeps_submissions(self, client, db):
        p = create(client)
        db.add(SubmissionDB(id="sub00001", user_id=USER_ID, year="2024", etap="etap1", task_number=1,
                            images=[], status=SubmissionStatus.COMPLETED, score=3, pattern_id=p["id"]))
        db.commit()
        assert client.delete(f"/api/patterns/{p['id']}").status_code == 200
        assert client.get(f"/api/patterns/{p['id']}").status_code == 404
        db.expire_all()
        assert db.get(SubmissionDB, "sub00001").pattern_id is None


class TestQueue:
    def test_interleaves_categories(self, client, db):
        ids = []
        for category, days in (("algebra", 3), ("algebra", 2), ("geometria", 1)):
            p = create(client, category=category)
            make_due(db, p["id"], TODAY - timedelta(days=days))
            ids.append(p["id"])
        create(client)  # not due
        body = client.get("/api/patterns/queue").json()
        assert body["due_total"] == 3
        assert [p["id"] for p in body["items"]] == [ids[0], ids[2], ids[1]]

    def test_limit(self, client, db):
        for _ in range(3):
            make_due(db, create(client)["id"])
        body = client.get("/api/patterns/queue", params={"limit": 2}).json()
        assert len(body["items"]) == 2
        assert body["due_total"] == 3


class TestReview:
    def test_not_due_is_409(self, client):
        p = create(client)
        r = client.post(f"/api/patterns/{p['id']}/review",
                        json={"recall_text": "Szukam niezmiennika", "outcome": "ok"})
        assert r.status_code == 409

    def test_due_review_advances(self, client, db):
        p = create(client)
        make_due(db, p["id"])
        r = client.post(f"/api/patterns/{p['id']}/review",
                        json={"recall_text": "Szukam niezmiennika", "outcome": "ok"})
        assert r.status_code == 200
        body = r.json()["pattern"]
        assert (body["level"], body["streak"], body["due_on"]) == (1, 1, (TODAY + timedelta(days=4)).isoformat())
        review = client.get(f"/api/patterns/{p['id']}").json()["pattern"]["reviews"][0]
        assert (review["kind"], review["outcome"], review["recall_text"]) == ("recall", "ok", "Szukam niezmiennika")

    def test_second_review_same_day_is_409(self, client, db):
        p = create(client)
        make_due(db, p["id"])
        body = {"recall_text": "Szukam niezmiennika", "outcome": "hard"}
        assert client.post(f"/api/patterns/{p['id']}/review", json=body).status_code == 200
        # "hard" at level 1 streak 0 schedules tomorrow - still not due today
        assert client.post(f"/api/patterns/{p['id']}/review", json=body).status_code == 409

    def test_lost_race_is_409(self, client, db, monkeypatch):
        from app.db.patterns import PatternRepository

        p = create(client)
        make_due(db, p["id"])
        monkeypatch.setattr(PatternRepository, "apply_review", lambda self, *a, **k: None)
        r = client.post(f"/api/patterns/{p['id']}/review",
                        json={"recall_text": "Szukam niezmiennika", "outcome": "ok"})
        assert r.status_code == 409

    def test_archived_is_409(self, client, db):
        p = create(client)
        make_due(db, p["id"])
        client.patch(f"/api/patterns/{p['id']}", json={"archived": True})
        r = client.post(f"/api/patterns/{p['id']}/review",
                        json={"recall_text": "Szukam niezmiennika", "outcome": "ok"})
        assert r.status_code == 409

    def test_recall_text_too_short(self, client, db):
        p = create(client)
        make_due(db, p["id"])
        r = client.post(f"/api/patterns/{p['id']}/review", json={"recall_text": "krótko", "outcome": "ok"})
        assert r.status_code == 422


class TestLinks:
    def test_manual_links(self, client):
        p = create(client)
        r = client.post(f"/api/patterns/{p['id']}/links", json={"task_key": "2024_etap2_3"})
        assert r.status_code == 201
        assert r.json()["link"]["status"] == "accepted"
        assert client.post(f"/api/patterns/{p['id']}/links", json={"task_key": "2024_etap2_3"}).status_code == 409
        assert client.post(f"/api/patterns/{p['id']}/links", json={"private_task_id": PRIVATE_ID}).status_code == 201
        assert client.post(f"/api/patterns/{p['id']}/links",
                           json={"private_task_id": FOREIGN_PRIVATE_ID}).status_code == 404
        assert client.post(f"/api/patterns/{p['id']}/links", json={"task_key": "1990_etap1_1"}).status_code == 404
        assert client.post(f"/api/patterns/{p['id']}/links", json={}).status_code == 422

    def test_status_and_delete(self, client):
        p = create(client)
        link = client.post(f"/api/patterns/{p['id']}/links", json={"task_key": "2024_etap2_3"}).json()["link"]
        r = client.patch(f"/api/patterns/{p['id']}/links/{link['id']}", json={"status": "rejected"})
        assert r.json()["link"]["status"] == "rejected"
        assert client.delete(f"/api/patterns/{p['id']}/links/{link['id']}").status_code == 200
        assert client.delete(f"/api/patterns/{p['id']}/links/{link['id']}").status_code == 404

    def test_other_users_link_is_404(self, client, current_user):
        p = create(client)
        link = client.post(f"/api/patterns/{p['id']}/links", json={"task_key": "2024_etap2_3"}).json()["link"]
        other = None
        current_user["id"] = OTHER_USER_ID
        other = create(client)
        r = client.patch(f"/api/patterns/{other['id']}/links/{link['id']}", json={"status": "rejected"})
        assert r.status_code == 404


class TestPractice:
    def test_level_one_first_review_offers_nothing(self, client):
        p = create(client, source={"task_key": "2024_etap1_1"})
        assert client.get(f"/api/patterns/{p['id']}/practice").json() == {"task": None}

    def test_maintenance_offers_never_attempted_task(self, client, db):
        p = create(client, source={"task_key": "2024_etap1_1"})
        db.get(PatternDB, p["id"]).srs_level = 4
        db.commit()
        task = client.get(f"/api/patterns/{p['id']}/practice").json()["task"]
        assert task == {"kind": "omj", "ref": "2024_etap1_1", "title": "Zadanie 1",
                        "url": "/task/2024/etap1/1"}

    def test_every_third_review_offers_private_task(self, client, db):
        p = create(client, source={"private_task_id": PRIVATE_ID})
        db.get(PatternDB, p["id"]).review_count = 2
        db.commit()
        task = client.get(f"/api/patterns/{p['id']}/practice").json()["task"]
        assert (task["kind"], task["url"]) == ("private", f"/moje-zadania/{PRIVATE_ID}")

    def test_vanished_omj_task(self, client, db, omj):
        p = create(client, source={"task_key": "2024_etap1_1"})
        db.get(PatternDB, p["id"]).srs_level = 4
        db.commit()
        del omj[("2024", "etap1", 1)]
        detail = client.get(f"/api/patterns/{p['id']}").json()["pattern"]
        assert detail["links"][0]["available"] is False
        assert client.get(f"/api/patterns/{p['id']}/practice").json() == {"task": None}


class TestE2EEndpoints:
    def test_hidden_outside_e2e_mode(self, client, monkeypatch):
        monkeypatch.setattr(settings, "e2e_mode", False)
        p = create(client)
        assert client.post(f"/api/test/patterns/{p['id']}/make-due").status_code == 404
        assert client.post("/api/test/reset-user-patterns").status_code == 404

    def test_make_due_only_for_own_pattern(self, client, db, monkeypatch, current_user):
        import app.main as app_main

        monkeypatch.setattr(settings, "e2e_mode", True)
        monkeypatch.setattr(app_main, "get_current_user",
                            lambda request: {"google_sub": current_user["id"]})
        p = create(client)
        assert client.post(f"/api/patterns/{p['id']}/review",
                           json={"recall_text": "Szukam niezmiennika", "outcome": "ok"}).status_code == 409
        assert client.post(f"/api/test/patterns/{p['id']}/make-due").status_code == 200
        assert client.get(f"/api/patterns/{p['id']}").json()["pattern"]["is_due"] is True
        current_user["id"] = OTHER_USER_ID
        assert client.post(f"/api/test/patterns/{p['id']}/make-due").status_code == 404
        current_user["id"] = USER_ID
        assert client.post("/api/test/reset-user-patterns").json()["deleted_count"] == 1


class TestLongRefineSessions:
    ROUND = {"draft": {"raw": "szkic"}, "variants": [{"trigger": "W1 wyzwalacz", "action": "A1 akcja"}],
             "questions": [], "verdict": "ok", "comment": "", "chosen": 0}

    def test_create_keeps_the_last_rounds_instead_of_refusing(self, client):
        rounds = [dict(self.ROUND, comment=f"r{i}") for i in range(12)]
        p = create(client, refinement=rounds)
        stored = client.get(f"/api/patterns/{p['id']}").json()["pattern"]["refinement"]
        assert [r["comment"] for r in stored] == [f"r{i}" for i in range(2, 12)]


class TestRefineSavedPattern:
    def test_picked_round_fills_missing_category_and_skills(self, client):
        from app.skills import get_all_skills

        skill = get_all_skills()[0].id
        p = create(client, category=None)
        round_ = {"draft": {"raw": "szkic"}, "variants": [{"trigger": "W1 wyzwalacz", "action": "A1 akcja"}],
                  "questions": [], "verdict": "ok", "comment": "", "chosen": 0,
                  "category": "teoria_liczb", "skills": [skill, "made_up"]}
        body = client.patch(f"/api/patterns/{p['id']}", json={"append_round": round_}).json()["pattern"]
        assert body["category"] == "teoria_liczb"
        assert body["skills"] == [skill]

    def test_picked_round_keeps_existing_category(self, client):
        p = create(client, category="algebra")
        round_ = {"draft": {"raw": "szkic"}, "variants": [{"trigger": "W1 wyzwalacz", "action": "A1 akcja"}],
                  "chosen": 0, "category": "teoria_liczb", "skills": []}
        body = client.patch(f"/api/patterns/{p['id']}", json={"append_round": round_}).json()["pattern"]
        assert body["category"] == "algebra"
