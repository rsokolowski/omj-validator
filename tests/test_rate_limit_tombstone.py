"""Erasing an account must not hand out a fresh rate-limit budget.

Deleting an account removes the submission rows the 24h limits are counted
from. Without the tombstone recorded on erasure, a user who hit the daily cap
could delete, sign in again with the same Google account and submit another
full day's worth - repeatedly, until the global budget (and the Gemini bill)
was gone.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models import DeletedAccountQuotaDB
from app.db.repositories import DeletedAccountQuotaRepository, hash_user_id
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
    yield session
    session.close()


@pytest.fixture
def repo(db):
    return DeletedAccountQuotaRepository(db)


class TestHashing:
    def test_is_not_the_raw_id(self, db):
        assert hash_user_id(USER_ID) != USER_ID
        assert USER_ID not in hash_user_id(USER_ID)

    def test_is_stable_and_user_specific(self, db):
        assert hash_user_id(USER_ID) == hash_user_id(USER_ID)
        assert hash_user_id(USER_ID) != hash_user_id(OTHER_USER_ID)

    def test_depends_on_the_secret(self, db, monkeypatch):
        first = hash_user_id(USER_ID)
        monkeypatch.setattr(settings, "session_secret_key", "another-secret")
        assert hash_user_id(USER_ID) != first


class TestRecordDeletion:
    def test_carries_used_quota_over_the_deletion(self, repo):
        newest = naive_utc(hours=-3)
        repo.record_deletion(USER_ID, 30, naive_utc(hours=-5), newest)

        count, expires_at = repo.get_user_carryover(USER_ID)

        assert count == 30
        # The accessor reports when the block is RELEASED, not what it came from
        assert abs((expires_at - (newest + timedelta(hours=24))).total_seconds()) < 1

    def test_stores_no_readable_identifier(self, repo, db):
        repo.record_deletion(USER_ID, 5, naive_utc(hours=-1), naive_utc(hours=-1))

        row = db.query(DeletedAccountQuotaDB).one()
        assert row.user_hash != USER_ID
        assert USER_ID not in row.user_hash
        assert len(row.user_hash) == 64

    def test_unused_quota_stores_nothing(self, repo, db):
        assert repo.record_deletion(USER_ID, 0, None) is None
        assert db.query(DeletedAccountQuotaDB).count() == 0

    def test_repeated_deletion_accumulates(self, repo):
        repo.record_deletion(USER_ID, 20, naive_utc(hours=-2), naive_utc(hours=-2))
        repo.record_deletion(USER_ID, 10, naive_utc(hours=-1), naive_utc(hours=-1))

        count, _ = repo.get_user_carryover(USER_ID)

        assert count == 30

    def test_window_ends_24h_after_the_NEWEST_submission(self, repo, db):
        """Regression: anchoring on the oldest handed the whole block of quota
        back early. A user with submissions from T-23h to T-1h who deletes at T
        would have got all their slots at T+1h, while a surviving account keeps
        losing them until T+23h."""
        oldest = naive_utc(hours=-23)
        newest = naive_utc(hours=-1)
        repo.record_deletion(USER_ID, 30, oldest, newest)

        row = db.query(DeletedAccountQuotaDB).one()
        assert abs((row.expires_at - (newest + timedelta(hours=24))).total_seconds()) < 1
        # Definitely not the old behaviour
        assert row.expires_at > oldest + timedelta(hours=24)

    def test_reset_headers_still_point_at_the_oldest_submission(self, repo, db):
        oldest = naive_utc(hours=-23)
        repo.record_deletion(USER_ID, 30, oldest, naive_utc(hours=-1))

        assert db.query(DeletedAccountQuotaDB).one().oldest_submission_at == oldest

    def test_carryover_is_still_live_when_the_old_anchor_would_have_expired(self, repo):
        """The exact scenario: oldest at T-23h, so oldest+24h is only 1h away."""
        repo.record_deletion(USER_ID, 30, naive_utc(hours=-23), naive_utc(hours=-1))

        count, _ = repo.get_user_carryover(USER_ID)

        assert count == 30

    def test_falls_back_to_the_oldest_when_no_newest_is_given(self, repo, db):
        oldest = naive_utc(hours=-5)
        repo.record_deletion(USER_ID, 3, oldest)

        row = db.query(DeletedAccountQuotaDB).one()
        assert abs((row.expires_at - (oldest + timedelta(hours=24))).total_seconds()) < 1

    def test_accumulation_keeps_the_earliest_oldest_and_latest_expiry(self, repo, db):
        repo.record_deletion(USER_ID, 5, naive_utc(hours=-20), naive_utc(hours=-18))
        repo.record_deletion(USER_ID, 5, naive_utc(hours=-4), naive_utc(hours=-2))

        row = db.query(DeletedAccountQuotaDB).one()
        assert row.submission_count == 10
        assert abs((row.oldest_submission_at - naive_utc(hours=-20)).total_seconds()) < 2
        assert row.expires_at > naive_utc(hours=20)


class TestCarryover:
    def test_no_tombstone_means_no_carryover(self, repo):
        assert repo.get_user_carryover(USER_ID) == (0, None)

    def test_other_users_are_unaffected(self, repo):
        repo.record_deletion(USER_ID, 30, naive_utc(hours=-1), naive_utc(hours=-1))

        assert repo.get_user_carryover(OTHER_USER_ID) == (0, None)

    def test_expired_tombstone_stops_counting(self, repo, db):
        repo.record_deletion(USER_ID, 30, naive_utc(hours=-30), naive_utc(hours=-30))  # window closed

        assert repo.get_user_carryover(USER_ID) == (0, None)

    def test_global_carryover_lists_live_blocks_separately(self, repo, db):
        repo.record_deletion(USER_ID, 30, naive_utc(hours=-1), naive_utc(hours=-1))
        repo.record_deletion(OTHER_USER_ID, 12, naive_utc(hours=-2), naive_utc(hours=-2))
        repo.record_deletion("user-3", 99, naive_utc(hours=-40), naive_utc(hours=-40))  # expired

        blocks = repo.get_global_carryover_blocks()

        assert sum(count for count, _ in blocks) == 42
        # Separate blocks, because each is released at its own moment
        assert sorted(count for count, _ in blocks) == [12, 30]
        assert all(expires_at is not None for _, expires_at in blocks)

    def test_global_carryover_without_tombstones(self, repo):
        assert repo.get_global_carryover_blocks() == []


class TestPurge:
    def test_removes_only_closed_windows(self, repo, db):
        repo.record_deletion(USER_ID, 5, naive_utc(hours=-1), naive_utc(hours=-1))
        repo.record_deletion(OTHER_USER_ID, 5, naive_utc(hours=-40), naive_utc(hours=-40))

        purged = repo.purge_expired()

        assert purged == 1
        assert db.query(DeletedAccountQuotaDB).count() == 1
        assert repo.get_user_carryover(USER_ID)[0] == 5

    def test_is_idempotent(self, repo):
        repo.record_deletion(USER_ID, 5, naive_utc(hours=-40), naive_utc(hours=-40))

        assert repo.purge_expired() == 1
        assert repo.purge_expired() == 0
