"""Drill exercises for a pattern: the background batch, its API and what it touches.

All exercise texts are invented.
"""

import asyncio
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest

from app.ai.factory import AIContentBlockedError, AIProviderError
from app.config import settings
from app.db.models import (
    AIUsageDB,
    PatternDB,
    PatternExerciseBatchDB,
    PatternLinkDB,
    PrivateTaskDB,
)
from app.models import ExerciseItem, ExercisesResult
from app.patterns import exercises
from test_pattern_api import (  # noqa: F401 - fixtures
    OTHER_USER_ID,
    PRIVATE_ID,
    USER_ID,
    client,
    create,
    current_user,
    db,
    omj,
    today,
)


def items(n=5, prefix="Ćwiczenie"):
    return [
        ExerciseItem(title=f"{prefix} {i}", content=f"Wymyślona treść {prefix} {i}: wykaż, że $n(n+1)$ jest parzyste.",
                     level="easy" if i < 2 else "medium", answer=f"Odpowiedź {i}", solution=f"Rozwiązanie {i}")
        for i in range(n)
    ]


class StubProvider:
    def __init__(self):
        self.result = ExercisesResult(exercises=items(), meta={"model": "stub", "estimated_cost": 0.01})
        self.error = None
        self.calls = []
        self.before_return = None

    async def generate_pattern_exercises(self, pattern, count, previous):
        self.calls.append((pattern, count, previous))
        if self.before_return:
            self.before_return()
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def provider(monkeypatch, db):
    stub = StubProvider()
    monkeypatch.setattr(exercises, "create_ai_provider", lambda: stub)
    monkeypatch.setattr(exercises, "session_factory", lambda: db)
    return stub


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run(batch_id, usage_id=None):
    asyncio.run(exercises.run_batch(batch_id, usage_id))


def batch_of(db, pattern_id):
    db.expire_all()
    return exercises.latest_batch(db, pattern_id)


def start_another(db, p):
    """What a review card does when the pool runs low."""
    exercises.start_batch(db, db.get(PatternDB, p["id"]), USER_ID, False)


def created_pattern(client, db, **overrides):
    """A saved pattern and the batch its creation started (not run yet)."""
    p = create(client, **overrides)
    return p, batch_of(db, p["id"])


class TestModel:
    def test_exercise_columns_round_trip(self, db):
        db.add(PatternDB(id="pattern00001", user_id=USER_ID, trigger="t", action="a", skills=[], origin="own",
                         refinement=[], due_on=datetime(2026, 10, 2).date()))
        db.add(PrivateTaskDB(id="exercise0001", user_id=USER_ID, title="T", content="C", hints=[],
                             source_images=[], origin="exercise", pattern_id="pattern00001",
                             exercise_level="easy", answer="42"))
        db.add(PatternExerciseBatchDB(id="batch0000001", pattern_id="pattern00001", user_id=USER_ID,
                                      status="running", requested=5))
        db.commit()
        db.expire_all()
        task = db.get(PrivateTaskDB, "exercise0001")
        assert (task.pattern_id, task.exercise_level, task.answer) == ("pattern00001", "easy", "42")
        assert (task.solution, task.rejected_at) == (None, None)
        batch = db.get(PatternExerciseBatchDB, "batch0000001")
        assert (batch.created_count, batch.acknowledged) == (0, False)


class TestRunBatch:
    def test_done_saves_exercises_as_linked_private_tasks(self, client, db, provider, _no_background_exercises):
        p, batch = created_pattern(client, db)
        [(batch_id, usage_id)] = _no_background_exercises
        assert batch.id == batch_id and batch.status == "running"

        run(batch_id, usage_id)

        batch = batch_of(db, p["id"])
        assert (batch.status, batch.created_count, batch.error) == ("done", 5, None)
        tasks = db.query(PrivateTaskDB).filter_by(pattern_id=p["id"]).order_by(PrivateTaskDB.created_at).all()
        assert [t.exercise_level for t in tasks] == ["easy", "easy", "medium", "medium", "medium"]
        assert all(t.origin == "exercise" and t.hints == [] and t.difficulty is None for t in tasks)
        assert {t.category for t in tasks} == {"kombinatoryka"}
        assert tasks[0].answer == "Odpowiedź 0"
        assert tasks[0].solution == "Rozwiązanie 0"
        links = db.query(PatternLinkDB).filter_by(pattern_id=p["id"], origin="exercise").all()
        assert {l.private_task_id for l in links} == {t.id for t in tasks}
        assert {(l.role, l.status) for l in links} == {("practice", "accepted")}
        # The usage row got the call's meta (spend cap)
        assert db.get(AIUsageDB, usage_id).meta["model"] == "stub"
        pattern_sent, count, previous = provider.calls[0]
        assert count == 5 and previous == []
        assert pattern_sent["trigger"] == p["trigger"]

    def test_second_batch_is_told_the_earlier_exercises(self, client, db, provider, _no_background_exercises):
        p, _ = created_pattern(client, db)
        run(*_no_background_exercises[0])
        provider.result = ExercisesResult(exercises=items(prefix="Nowe"))

        start_another(db, p)
        run(*_no_background_exercises[1])

        previous = provider.calls[1][2]
        assert len(previous) == 5 and previous[0].startswith("Wymyślona treść Ćwiczenie 0")
        assert db.query(PrivateTaskDB).filter_by(pattern_id=p["id"]).count() == 10

    @pytest.mark.parametrize("result, error", [
        (ExercisesResult(off_topic=True), "off_topic"),
        (ExercisesResult(exercises=items(), abuse_score=90), "refused"),
        (ExercisesResult(), "empty"),
    ])
    def test_refusals_save_nothing(self, client, db, provider, _no_background_exercises, result, error):
        p, _ = created_pattern(client, db)
        provider.result = result
        run(*_no_background_exercises[0])
        batch = batch_of(db, p["id"])
        assert (batch.status, batch.error) == ("failed", error)
        assert db.query(PrivateTaskDB).filter_by(pattern_id=p["id"]).count() == 0

    @pytest.mark.parametrize("err, code", [
        (AIProviderError("down"), "ai_error"),
        (AIContentBlockedError("blocked"), "refused"),
        (RuntimeError("bug"), "ai_error"),
    ])
    def test_errors_fail_the_batch(self, client, db, provider, _no_background_exercises, err, code):
        p, _ = created_pattern(client, db)
        provider.error = err
        run(*_no_background_exercises[0])
        assert batch_of(db, p["id"]).error == code

    def test_pattern_deleted_during_the_call(self, client, db, provider, _no_background_exercises):
        p, _ = created_pattern(client, db)
        provider.before_return = lambda: client.delete(f"/api/patterns/{p['id']}")
        run(*_no_background_exercises[0])
        assert db.query(PrivateTaskDB).filter(PrivateTaskDB.pattern_id.isnot(None)).count() == 0
        assert db.query(PrivateTaskDB).filter_by(origin="exercise").count() == 0
        assert db.query(PatternExerciseBatchDB).count() == 0

    def test_error_after_pattern_deleted_is_quiet(self, client, db, provider, _no_background_exercises, caplog):
        p, _ = created_pattern(client, db)

        def delete_then_fail():
            client.delete(f"/api/patterns/{p['id']}")
            provider.error = AIProviderError("down")

        provider.before_return = delete_then_fail
        run(*_no_background_exercises[0])
        assert "crashed" not in caplog.text
        assert db.query(PatternExerciseBatchDB).count() == 0

    def test_expired_batch_is_not_overwritten(self, client, db, provider, _no_background_exercises):
        p, batch = created_pattern(client, db)

        def expire_then_off_topic():
            b = db.get(PatternExerciseBatchDB, batch.id)
            b.status, b.error = "failed", "interrupted"
            db.commit()
            provider.result = ExercisesResult(off_topic=True)

        provider.before_return = expire_then_off_topic
        run(*_no_background_exercises[0])
        assert batch_of(db, p["id"]).error == "interrupted"

    def test_previous_statements_are_shortened(self, client, db, provider, _no_background_exercises):
        p, _ = created_pattern(client, db)
        provider.result = ExercisesResult(exercises=[ExerciseItem(title="Długie", content="x " * 1000)])
        run(*_no_background_exercises[0])
        start_another(db, p)
        run(*_no_background_exercises[1])
        [previous] = provider.calls[1][2]
        assert len(previous) == exercises.PREVIOUS_CHARS

    def test_settled_batch_is_not_run_again(self, client, db, provider, _no_background_exercises):
        p, batch = created_pattern(client, db)
        batch.status = "failed"
        db.commit()
        run(*_no_background_exercises[0])
        assert provider.calls == []


class TestStale:
    def test_old_running_batch_expires(self, client, db, _no_background_exercises):
        p, batch = created_pattern(client, db)
        batch.created_at = _now() - timedelta(minutes=11)
        db.commit()
        assert exercises.expire_stale(db, user_id=USER_ID) == 1
        assert (batch_of(db, p["id"]).status, batch_of(db, p["id"]).error) == ("failed", "interrupted")

    def test_restart_releases_batches_older_than_grace(self, client, db, monkeypatch):
        p, _ = created_pattern(client, db)
        monkeypatch.setattr(exercises, "SessionLocal", lambda: db)
        exercises.release_interrupted_batches()
        batch = batch_of(db, p["id"])
        assert batch.status == "running"  # younger than the grace period
        batch.created_at = _now() - timedelta(minutes=2)
        db.commit()
        exercises.release_interrupted_batches()
        assert batch_of(db, p["id"]).status == "failed"


class TestApi:
    def test_create_starts_a_batch(self, client, db):
        p = create(client)
        assert batch_of(db, p["id"]).status == "running"
        assert "exercise_batch" not in p and "exercises" not in p

    def test_limit_at_create_keeps_the_pattern(self, client, db, monkeypatch, _no_background_exercises):
        monkeypatch.setattr(settings, "rate_limit_pattern_exercises_per_user_per_day", 0)
        p = create(client)
        assert db.get(PatternDB, p["id"]) is not None
        assert _no_background_exercises == []
        assert batch_of(db, p["id"]) is None

    def test_one_running_batch_per_pattern(self, client, db):
        from fastapi import HTTPException

        p = create(client)
        with pytest.raises(HTTPException) as e:
            start_another(db, p)
        assert e.value.status_code == 409

    def test_exercises_stay_out_of_links_and_the_own_list(self, client, db, provider, _no_background_exercises):
        p = create(client)
        run(*_no_background_exercises[0])
        detail = client.get(f"/api/patterns/{p['id']}").json()["pattern"]
        assert detail["links"] == [] and detail["links_count"] == 0
        own = client.get("/api/private-tasks").json()
        assert [t["id"] for t in own["tasks"]] == [PRIVATE_ID]

    def test_deleting_the_pattern_deletes_exercises_and_files(
        self, client, db, provider, _no_background_exercises, monkeypatch
    ):
        p = create(client)
        run(*_no_background_exercises[0])
        ids = {t.id for t in db.query(PrivateTaskDB).filter_by(pattern_id=p["id"])}
        removed = []
        from app.private_tasks import service as private_service
        monkeypatch.setattr(private_service, "delete_task_files",
                            lambda task: removed.append(task.id) or SimpleNamespace(files_deleted=1))

        r = client.delete(f"/api/patterns/{p['id']}")

        assert r.json()["deleted_exercises"] == 5
        assert set(removed) == ids
        db.expire_all()
        assert db.query(PrivateTaskDB).filter(PrivateTaskDB.id.in_(ids)).count() == 0
        assert db.get(PrivateTaskDB, PRIVATE_ID) is not None


class TestPrint:
    def test_print_has_statements_and_answers(self, client, db, provider, _no_background_exercises, current_user):
        p = create(client)
        run(*_no_background_exercises[0])
        data = client.get(f"/api/patterns/{p['id']}/exercises/print").json()
        assert data["pattern"]["trigger"] == p["trigger"]
        assert len(data["exercises"]) == 5
        assert data["exercises"][0]["content"].startswith("Wymyślona treść")
        assert data["exercises"][0]["answer"] == "Odpowiedź 0"
        assert data["exercises"][0]["solution"] == "Rozwiązanie 0"
        current_user["id"] = OTHER_USER_ID
        assert client.get(f"/api/patterns/{p['id']}/exercises/print").status_code == 404


class TestRetention:
    def test_purged_pattern_takes_its_exercises(self, client, db, provider, _no_background_exercises, monkeypatch):
        from app import retention

        p = create(client)
        run(*_no_background_exercises[0])
        db.get(PatternDB, p["id"]).last_activity_at = _now() - timedelta(days=800)
        db.commit()
        removed = []
        monkeypatch.setattr(retention, "delete_private_task_files",
                            lambda user_id, task_id, report, dry_run=False: removed.append(task_id))

        report = retention.purge_expired_patterns(db, months=24)

        assert (report.patterns_deleted, report.private_tasks_deleted) == (1, 5)
        assert len(removed) == 5
        assert db.query(PrivateTaskDB).filter_by(origin="exercise").count() == 0
        assert db.get(PrivateTaskDB, PRIVATE_ID) is not None
