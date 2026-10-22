"""Exercise-based reviews: the card (exercise + trigger visibility), the
two-step self-rating, skipping a broken exercise and topping the pool up.

All exercise texts are invented.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.db.models import PatternDB, PatternExerciseBatchDB, PatternReviewDB, PrivateTaskDB, SubmissionDB, SubmissionStatus
from app.patterns import exercises
from test_pattern_api import (  # noqa: F401 - fixtures
    OTHER_USER_ID,
    PRIVATE_ID,
    TODAY,
    USER_ID,
    client,
    create,
    current_user,
    db,
    make_due,
    omj,
    today,
)
from test_pattern_exercises import provider, run  # noqa: F401 - fixtures


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def pattern(client, db, provider, _no_background_exercises):
    """A due pattern with its first batch (2 easy + 3 medium) generated."""
    p = create(client)
    run(*_no_background_exercises[0])
    make_due(db, p["id"])
    return p


def exercise_ids(db, pattern_id):
    rows = db.query(PrivateTaskDB).filter_by(pattern_id=pattern_id).order_by(PrivateTaskDB.created_at, PrivateTaskDB.id)
    return [t.id for t in rows]


def card(client, pattern_id):
    r = client.get(f"/api/patterns/{pattern_id}/card")
    assert r.status_code == 200, r.text
    return r.json()


def review(client, pattern_id, outcome, exercise_id=None, trigger_shown=False):
    return client.post(
        f"/api/patterns/{pattern_id}/review",
        json={"outcome": outcome, "exercise_id": exercise_id, "trigger_shown": trigger_shown},
    )


def set_level(db, pattern_id, level):
    db.get(PatternDB, pattern_id).srs_level = level
    db.commit()


def batches(db, pattern_id):
    db.expire_all()
    return db.query(PatternExerciseBatchDB).filter_by(pattern_id=pattern_id).count()


class TestCard:
    def test_level_one_offers_an_easy_exercise_with_the_trigger(self, client, db, pattern):
        data = card(client, pattern["id"])
        assert data["trigger_hidden"] is False
        ex = data["exercise"]
        assert ex["level"] == "easy"
        assert ex["id"] == exercise_ids(db, pattern["id"])[0]
        assert (ex["answer"], ex["solution"]) == ("Odpowiedź 0", "Rozwiązanie 0")
        assert ex["content"].startswith("Wymyślona treść")

    def test_level_two_hides_the_trigger(self, client, db, pattern):
        set_level(db, pattern["id"], 2)
        assert card(client, pattern["id"])["trigger_hidden"] is True

    def test_level_three_offers_medium(self, client, db, pattern):
        set_level(db, pattern["id"], 3)
        assert card(client, pattern["id"])["exercise"]["level"] == "medium"

    def test_reload_shows_the_same_exercise(self, client, pattern):
        assert card(client, pattern["id"])["exercise"]["id"] == card(client, pattern["id"])["exercise"]["id"]

    def test_not_due_is_409(self, client, db, pattern):
        make_due(db, pattern["id"], TODAY + timedelta(days=3))
        assert client.get(f"/api/patterns/{pattern['id']}/card").status_code == 409

    def test_foreign_pattern_is_404(self, client, pattern, current_user):
        current_user["id"] = OTHER_USER_ID
        assert client.get(f"/api/patterns/{pattern['id']}/card").status_code == 404

    def test_no_exercises_yet_is_a_fallback_card(self, client, db, _no_background_exercises):
        p = create(client)  # batch started, never run
        make_due(db, p["id"])
        assert card(client, p["id"]) == {"exercise": None, "trigger_hidden": False}


class TestReview:
    def test_exercise_review_is_recorded(self, client, db, pattern):
        first = card(client, pattern["id"])["exercise"]["id"]
        r = review(client, pattern["id"], "ok", first)
        assert r.status_code == 200, r.text
        assert r.json()["pattern"]["streak"] == 1
        row = db.query(PatternReviewDB).filter_by(pattern_id=pattern["id"]).one()
        assert (row.kind, row.outcome, row.private_task_id, row.trigger_shown, row.recall_text) == (
            "exercise", "ok", first, False, None)
        detail = client.get(f"/api/patterns/{pattern['id']}").json()["pattern"]
        assert detail["reviews"][0]["exercise_title"] == "Ćwiczenie 0"
        assert "exercises" not in detail and "exercise_batch" not in detail

    def test_review_keeps_the_exercise_alive_for_retention(self, client, db, pattern):
        ex = card(client, pattern["id"])["exercise"]["id"]
        db.get(PrivateTaskDB, ex).last_activity_at = _now() - timedelta(days=400)
        db.commit()
        assert review(client, pattern["id"], "ok", ex).status_code == 200
        db.expire_all()
        assert db.get(PrivateTaskDB, ex).last_activity_at > _now() - timedelta(minutes=1)

    def test_next_card_moves_on_to_an_unseen_exercise(self, client, db, pattern):
        first = card(client, pattern["id"])["exercise"]["id"]
        review(client, pattern["id"], "ok", first)
        make_due(db, pattern["id"])
        assert card(client, pattern["id"])["exercise"]["id"] == exercise_ids(db, pattern["id"])[1]

    def test_peeking_at_a_hidden_trigger_caps_ok_to_hard(self, client, db, pattern):
        set_level(db, pattern["id"], 2)
        ex = card(client, pattern["id"])["exercise"]["id"]
        assert review(client, pattern["id"], "ok", ex, trigger_shown=True).status_code == 200
        row = db.query(PatternReviewDB).filter_by(pattern_id=pattern["id"]).one()
        assert (row.outcome, row.trigger_shown) == ("hard", True)

    def test_fallback_review_is_not_capped(self, client, db, pattern):
        set_level(db, pattern["id"], 2)
        assert review(client, pattern["id"], "ok", None, trigger_shown=True).status_code == 200
        row = db.query(PatternReviewDB).filter_by(pattern_id=pattern["id"]).one()
        assert (row.kind, row.outcome, row.private_task_id, row.recall_text) == ("recall", "ok", None, None)

    def test_second_rating_same_day_is_409(self, client, db, pattern):
        ex = card(client, pattern["id"])["exercise"]["id"]
        assert review(client, pattern["id"], "hard", ex).status_code == 200
        assert review(client, pattern["id"], "ok", ex).status_code == 409

    def test_unknown_outcome_is_422(self, client, pattern):
        assert review(client, pattern["id"], "great").status_code == 422

    def test_exercise_of_another_pattern_is_404(self, client, db, pattern, _no_background_exercises):
        other = create(client, trigger="Inny wyzwalacz do testu", action="Inna akcja do testu")
        run(*_no_background_exercises[-1])
        foreign = exercise_ids(db, other["id"])[0]
        assert review(client, pattern["id"], "ok", foreign).status_code == 404

    def test_typed_private_task_is_404(self, client, pattern):
        assert review(client, pattern["id"], "ok", PRIVATE_ID).status_code == 404

    def test_rejected_exercise_is_404(self, client, db, pattern):
        ex = exercise_ids(db, pattern["id"])[0]
        assert client.post(f"/api/patterns/{pattern['id']}/exercises/{ex}/reject").status_code == 200
        assert review(client, pattern["id"], "ok", ex).status_code == 404

    def test_another_users_exercise_is_404(self, client, db, pattern, current_user):
        ex = exercise_ids(db, pattern["id"])[0]
        current_user["id"] = OTHER_USER_ID
        own = create(client, trigger="Wyzwalacz drugiego ucznia", action="Akcja drugiego ucznia")
        make_due(db, own["id"])
        assert review(client, own["id"], "ok", ex).status_code == 404


class TestReject:
    def test_rejected_exercise_is_not_offered(self, client, db, pattern):
        first = card(client, pattern["id"])["exercise"]["id"]
        r = client.post(f"/api/patterns/{pattern['id']}/exercises/{first}/reject")
        assert r.status_code == 200 and r.json() == {"success": True}
        assert db.get(PrivateTaskDB, first).rejected_at is not None
        assert card(client, pattern["id"])["exercise"]["id"] != first
        assert db.query(PatternReviewDB).count() == 0

    def test_rejecting_the_last_one_gives_a_fallback_and_a_new_batch(self, client, db, pattern):
        for ex in exercise_ids(db, pattern["id"]):
            assert client.post(f"/api/patterns/{pattern['id']}/exercises/{ex}/reject").status_code == 200
        before = batches(db, pattern["id"])
        assert card(client, pattern["id"])["exercise"] is None
        assert batches(db, pattern["id"]) == before + 1

    def test_foreign_or_unknown_is_404(self, client, db, pattern, current_user):
        ex = exercise_ids(db, pattern["id"])[0]
        assert client.post(f"/api/patterns/{pattern['id']}/exercises/{PRIVATE_ID}/reject").status_code == 404
        current_user["id"] = OTHER_USER_ID
        assert client.post(f"/api/patterns/{pattern['id']}/exercises/{ex}/reject").status_code == 404


class TestTopUp:
    def _review_n(self, client, db, pattern_id, n):
        for _ in range(n):
            make_due(db, pattern_id)
            ex = card(client, pattern_id)["exercise"]["id"]
            assert review(client, pattern_id, "hard", ex).status_code == 200
        make_due(db, pattern_id)

    def test_three_unseen_start_nothing(self, client, db, pattern):
        self._review_n(client, db, pattern["id"], 2)
        before = batches(db, pattern["id"])
        card(client, pattern["id"])
        assert batches(db, pattern["id"]) == before

    def test_two_unseen_start_one_batch(self, client, db, pattern):
        self._review_n(client, db, pattern["id"], 3)
        before = batches(db, pattern["id"])
        card(client, pattern["id"])
        assert batches(db, pattern["id"]) == before + 1
        # The batch is running: the next card does not start a second one
        card(client, pattern["id"])
        assert batches(db, pattern["id"]) == before + 1

    def test_daily_limit_still_serves_the_card(self, client, db, pattern, monkeypatch):
        self._review_n(client, db, pattern["id"], 3)
        monkeypatch.setattr(settings, "rate_limit_pattern_exercises_per_user_per_day", 0)
        before = batches(db, pattern["id"])
        assert card(client, pattern["id"])["exercise"] is not None
        assert batches(db, pattern["id"]) == before


    def test_recently_failed_batch_is_not_retried(self, client, db, pattern):
        self._review_n(client, db, pattern["id"], 3)
        latest = exercises.latest_batch(db, pattern["id"])
        latest.status, latest.error, latest.finished_at = "failed", "off_topic", _now()
        db.commit()
        before = batches(db, pattern["id"])
        card(client, pattern["id"])
        assert batches(db, pattern["id"]) == before

    def test_inactive_account_does_not_start_a_batch(self, client, db, pattern, monkeypatch):
        import app.patterns.routes as pattern_routes

        self._review_n(client, db, pattern["id"], 3)
        monkeypatch.setattr(pattern_routes, "account_may_write", lambda request: False)
        before = batches(db, pattern["id"])
        assert card(client, pattern["id"])["exercise"] is not None
        assert batches(db, pattern["id"]) == before


class TestExerciseAsLink:
    def test_exercise_cannot_be_a_source_or_link(self, client, db, pattern):
        ex = exercise_ids(db, pattern["id"])[0]
        r = client.post("/api/patterns", json={"trigger": "Wyzwalacz testowy", "action": "Akcja testowa",
                                               "source": {"private_task_id": ex}})
        assert r.status_code == 404
        assert client.post(f"/api/patterns/{pattern['id']}/links", json={"private_task_id": ex}).status_code == 404


class TestOldSystemHistory:
    def _graded(self, db, task_id, score):
        db.add(SubmissionDB(id=f"s{task_id[-7:]}", user_id=USER_ID, private_task_id=task_id, images=[],
                            status=SubmissionStatus.COMPLETED, score=score, timestamp=_now()))
        db.commit()

    def test_graded_submissions_count_as_seen(self, client, db, pattern):
        ids = exercise_ids(db, pattern["id"])
        self._graded(db, ids[0], 6)  # solved -> seen, offered last
        self._graded(db, ids[1], 0)  # failed -> after the unseen ones
        assert card(client, pattern["id"])["exercise"]["id"] == ids[2]
        for ex in ids[2:]:
            client.post(f"/api/patterns/{pattern['id']}/exercises/{ex}/reject")
        assert card(client, pattern["id"])["exercise"]["id"] == ids[1]


class TestRemoved:
    def test_old_endpoints_are_gone(self, client, pattern):
        pid = pattern["id"]
        assert client.get(f"/api/patterns/{pid}/practice").status_code in (404, 405)
        assert client.post(f"/api/patterns/{pid}/exercises").status_code in (404, 405)
        assert client.get("/api/patterns/exercise-batches/active").status_code in (404, 405)
        assert client.get("/api/patterns/exercises").status_code in (404, 405)

    def test_exercises_are_hidden_from_private_tasks(self, client, db, pattern):
        ex = exercise_ids(db, pattern["id"])[0]
        assert client.get(f"/api/private-tasks/{ex}").status_code == 404
        assert client.post(f"/api/private-tasks/{ex}/submit", data={"solution_text": "Rozwiązanie"}).status_code == 404
        assert client.patch(f"/api/private-tasks/{ex}", json={"title": "Nowy"}).status_code == 404
