"""Repositories behind private tasks: ownership, hint bookkeeping, AI usage."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models import AIUsageDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.private_tasks import (
    AIUsageRepository,
    HintOrderError,
    PrivateTaskRepository,
)
from app.db.repositories import DeletedAccountQuotaRepository
from app.db.session import Base

USER_ID = "user-1"
OTHER_USER_ID = "user-2"


def naive_utc(**delta) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(**delta)


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(settings, "session_secret_key", "test-secret-key")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email="a@example.com"))
    session.add(UserDB(google_sub=OTHER_USER_ID, email="b@example.com"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def repo(db):
    return PrivateTaskRepository(db)


def create(repo, user_id=USER_ID, hints=("h1", "h2", "h3")):
    return repo.create(
        user_id,
        title="Invented task",
        content="Show that n^2 + n is always even.",
        source_label="Kartka 3",
        category="teoria_liczb",
        difficulty=2,
        hints=list(hints),
        origin="typed",
    )


class TestOwnership:
    def test_create_assigns_a_12_char_id(self, repo):
        task = create(repo)
        assert len(task.id) == 12
        assert task.hints == ["h1", "h2", "h3"]

    def test_get_owned_returns_own_task(self, repo):
        task = create(repo)
        assert repo.get_owned(task.id, USER_ID).id == task.id

    def test_get_owned_hides_other_users_task(self, repo):
        task = create(repo)
        assert repo.get_owned(task.id, OTHER_USER_ID) is None

    def test_get_owned_unknown_id(self, repo):
        assert repo.get_owned("nope", USER_ID) is None


class TestListing:
    def test_list_reports_best_score_and_attempts(self, db, repo):
        task = create(repo)
        other = create(repo)
        for sid, score, status in (
            ("s1", 2, SubmissionStatus.COMPLETED),
            ("s2", 5, SubmissionStatus.COMPLETED),
            ("s3", None, SubmissionStatus.FAILED),
        ):
            db.add(SubmissionDB(id=sid, user_id=USER_ID, private_task_id=task.id,
                                images=[], status=status, score=score))
        db.commit()

        rows, total = repo.list_for_user(USER_ID)

        assert total == 2
        by_id = {row["task"].id: row for row in rows}
        assert by_id[task.id]["best_score"] == 5
        assert by_id[task.id]["attempts"] == 3
        assert by_id[other.id]["best_score"] is None
        assert by_id[other.id]["attempts"] == 0

    def test_list_is_scoped_to_the_user(self, repo):
        create(repo, user_id=OTHER_USER_ID)
        rows, total = repo.list_for_user(USER_ID)
        assert (rows, total) == ([], 0)

    def test_list_orders_by_last_activity(self, db, repo):
        old = create(repo)
        new = create(repo)
        old.last_activity_at = naive_utc(days=-3)
        db.commit()
        rows, _ = repo.list_for_user(USER_ID)
        assert [row["task"].id for row in rows] == [new.id, old.id]


class TestHints:
    def test_hints_must_be_revealed_in_order(self, repo):
        task = create(repo)
        with pytest.raises(HintOrderError):
            repo.reveal_hint(task, 2)

    def test_reveal_returns_text_and_tracks_counts(self, repo):
        task = create(repo)
        assert repo.reveal_hint(task, 1) == "h1"
        assert repo.reveal_hint(task, 2) == "h2"
        assert task.hints_revealed == 2
        assert task.pending_hints_used == 2

    def test_rereveal_does_not_lower_pending(self, repo):
        task = create(repo)
        repo.reveal_hint(task, 1)
        repo.reveal_hint(task, 2)
        repo.take_pending_hints(task)
        repo.reveal_hint(task, 1)
        assert task.hints_revealed == 2
        assert task.pending_hints_used == 1

    def test_reveal_out_of_range(self, repo):
        task = create(repo, hints=("only",))
        repo.reveal_hint(task, 1)
        with pytest.raises(IndexError):
            repo.reveal_hint(task, 2)
        with pytest.raises(IndexError):
            repo.reveal_hint(task, 0)

    def test_take_pending_returns_and_resets(self, repo):
        task = create(repo)
        repo.reveal_hint(task, 1)
        repo.reveal_hint(task, 2)
        assert repo.take_pending_hints(task) == 2
        assert repo.take_pending_hints(task) == 0


class TestUpdates:
    def test_update_fields_bumps_activity(self, db, repo):
        task = create(repo)
        task.last_activity_at = naive_utc(days=-100)
        db.commit()

        repo.update_fields(task, title="New title", difficulty=4)

        assert task.title == "New title"
        assert task.difficulty == 4
        assert task.last_activity_at > naive_utc(minutes=-1)

    def test_update_fields_rejects_unknown_field(self, repo):
        task = create(repo)
        with pytest.raises(ValueError):
            repo.update_fields(task, user_id=OTHER_USER_ID)

    def test_delete_removes_task_and_submissions(self, db, repo):
        task = create(repo)
        db.add(SubmissionDB(id="s1", user_id=USER_ID, private_task_id=task.id, images=[]))
        db.commit()

        repo.delete(task)

        assert repo.get_owned(task.id, USER_ID) is None
        assert db.query(SubmissionDB).count() == 0


class TestAIUsage:
    def test_user_window_counts_only_given_kinds_inside_window(self, db):
        usage = AIUsageRepository(db)
        usage.record(USER_ID, "private_extract")
        usage.record(USER_ID, "private_create")
        usage.record(USER_ID, "private_regen")
        usage.record(OTHER_USER_ID, "private_create")
        db.add(AIUsageDB(user_id=USER_ID, kind="private_create", created_at=naive_utc(hours=-25)))
        db.commit()

        count, oldest = usage.user_window(USER_ID, {"private_create", "private_regen"})

        assert count == 2
        assert oldest is not None

    def test_global_window_counts_everything(self, db):
        usage = AIUsageRepository(db)
        usage.record(USER_ID, "private_extract")
        usage.record(OTHER_USER_ID, "private_create")
        assert usage.global_window()[0] == 2

    def test_user_total_window(self, db):
        usage = AIUsageRepository(db)
        usage.record(USER_ID, "private_extract", meta={"model": "m"})
        usage.record(USER_ID, "private_create")
        count, oldest, newest = usage.user_total_window(USER_ID)
        assert count == 2
        assert oldest <= newest


class TestTombstoneCarriesAIUsage:
    def test_ai_usage_alone_leaves_a_tombstone(self, db):
        quota = DeletedAccountQuotaRepository(db)
        tombstone = quota.record_deletion(
            USER_ID, 0, None, None, ai_usage_count=4,
            ai_usage_newest_at=naive_utc(hours=-1),
        )
        assert tombstone is not None
        assert quota.get_user_ai_usage_carryover(USER_ID) == 4
        # Submissions carryover is unaffected
        assert quota.get_user_carryover(USER_ID)[0] == 0

    def test_nothing_used_records_nothing(self, db):
        quota = DeletedAccountQuotaRepository(db)
        assert quota.record_deletion(USER_ID, 0, None, None, ai_usage_count=0) is None
        assert quota.get_user_ai_usage_carryover(USER_ID) == 0

    def test_ai_usage_accumulates_across_deletions(self, db):
        quota = DeletedAccountQuotaRepository(db)
        quota.record_deletion(USER_ID, 1, naive_utc(hours=-2), naive_utc(hours=-2), ai_usage_count=2)
        quota.record_deletion(USER_ID, 0, None, None, ai_usage_count=3)
        assert quota.get_user_ai_usage_carryover(USER_ID) == 5
