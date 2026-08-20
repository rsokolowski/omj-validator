"""Tests for POST /api/account/delete (RODO art. 17 - right to erasure).

This endpoint destroys a user's account, every submission and every photo, so
the guards around it are covered here: who may call it, what confirms it, and
that a caller can only ever erase themselves.
"""

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
from app.config import settings
from app.db import get_db
from app.db.models import DeletedAccountQuotaDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base
from app.db.repositories import DeletedAccountQuotaRepository
from app.models import ACCOUNT_DELETE_CONFIRMATION

USER_ID = "user-1"
USER_EMAIL = "kid@example.com"
OTHER_USER_ID = "user-2"


@pytest.fixture
def db(tmp_path, monkeypatch):
    """In-memory DB with two users, one submission each, and real upload files."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "admin_emails", None)

    # TestClient runs the app in another thread, so the in-memory DB must be
    # shared and thread-checks relaxed
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    for user_id, email in ((USER_ID, USER_EMAIL), (OTHER_USER_ID, "other@example.com")):
        session.add(UserDB(google_sub=user_id, email=email, name="Kid"))
        directory = settings.uploads_dir / user_id / "2024" / "etap1" / "1"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "page1.jpg").write_bytes(b"x" * 1024)
        session.add(
            SubmissionDB(
                id=f"sub-{user_id}",
                user_id=user_id,
                year="2024",
                etap="etap1",
                task_number=1,
                # Inside the 24h rate limit window, so the tombstone has something to carry
                timestamp=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
                status=SubmissionStatus.COMPLETED,
                images=[f"{user_id}/2024/etap1/1/page1.jpg"],
                score=5,
                feedback="ok",
            )
        )
    session.commit()

    yield session

    session.close()


@pytest.fixture
def client(db, monkeypatch):
    """TestClient authenticated as USER_ID (non-admin) unless a test says otherwise."""
    def override_get_db():
        yield db

    main.app.dependency_overrides[get_db] = override_get_db

    user = {"google_sub": USER_ID, "email": USER_EMAIL, "name": "Kid"}
    monkeypatch.setattr(main, "verify_auth", lambda request: True)
    monkeypatch.setattr(main, "get_current_user_id", lambda request: USER_ID)
    monkeypatch.setattr(main, "get_current_user", lambda request: user)

    # No context manager: startup events (DB warm-up, AI provider) must not run
    yield TestClient(main.app)

    main.app.dependency_overrides.clear()


def _signed_session_cookie(data: dict) -> str:
    """Build a cookie SessionMiddleware accepts, so a real session exists."""
    signer = TimestampSigner(str(settings.session_secret_key))
    payload = base64.b64encode(json.dumps(data).encode())
    return signer.sign(payload).decode()


def _post(client, confirmation=ACCOUNT_DELETE_CONFIRMATION):
    return client.post("/api/account/delete", json={"confirmation": confirmation})


def user_exists(db, user_id: str) -> bool:
    return db.query(UserDB).filter(UserDB.google_sub == user_id).first() is not None


class TestSuccess:
    def test_deletes_account_submissions_and_files(self, client, db):
        response = _post(client)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["deleted_submissions"] == 1
        assert body["deleted_files"] == 1

        assert not user_exists(db, USER_ID)
        assert db.query(SubmissionDB).filter(SubmissionDB.user_id == USER_ID).count() == 0
        assert not (settings.uploads_dir / USER_ID).exists()

    def test_never_touches_another_users_data(self, client, db):
        _post(client)

        assert user_exists(db, OTHER_USER_ID)
        assert db.query(SubmissionDB).filter(SubmissionDB.user_id == OTHER_USER_ID).count() == 1
        assert (settings.uploads_dir / OTHER_USER_ID / "2024" / "etap1" / "1" / "page1.jpg").exists()

    def test_session_is_invalidated(self, client, db):
        client.cookies.set(
            "session",
            _signed_session_cookie({"user": {"google_sub": USER_ID, "email": USER_EMAIL}}),
        )

        response = _post(client)

        # SessionMiddleware emits a cookie deletion when the session is cleared
        set_cookie = response.headers.get("set-cookie", "")
        assert "session=" in set_cookie
        assert "session=null" in set_cookie
        assert "expires=Thu, 01 Jan 1970" in set_cookie

    def test_body_from_another_user_is_ignored(self, client, db):
        """The erased id comes from the session, never from the request body."""
        response = client.post(
            "/api/account/delete",
            json={"confirmation": ACCOUNT_DELETE_CONFIRMATION, "user_id": OTHER_USER_ID},
        )

        assert response.status_code == 200
        assert not user_exists(db, USER_ID)
        assert user_exists(db, OTHER_USER_ID)


class TestGuards:
    @pytest.mark.parametrize(
        "confirmation",
        ["", "usuwam konto", "USUN KONTO", "tak", "USUWAM KONTA"],
    )
    def test_wrong_confirmation_is_rejected(self, client, db, confirmation):
        response = _post(client, confirmation)

        assert response.status_code == 400
        assert ACCOUNT_DELETE_CONFIRMATION in response.json()["detail"]
        assert user_exists(db, USER_ID)
        assert db.query(SubmissionDB).count() == 2

    def test_surrounding_whitespace_is_tolerated(self, client, db):
        response = _post(client, f"  {ACCOUNT_DELETE_CONFIRMATION}  ")

        assert response.status_code == 200
        assert not user_exists(db, USER_ID)

    def test_missing_body_is_rejected(self, client, db):
        response = client.post("/api/account/delete", json={})

        assert response.status_code == 422
        assert user_exists(db, USER_ID)

    def test_unauthenticated_is_rejected(self, client, db, monkeypatch):
        monkeypatch.setattr(main, "verify_auth", lambda request: False)

        response = _post(client)

        assert response.status_code == 401
        assert user_exists(db, USER_ID)

    def test_admin_cannot_delete_themselves_this_way(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "admin_emails", USER_EMAIL)

        response = _post(client)

        assert response.status_code == 403
        assert "administrator" in response.json()["detail"].lower()
        assert user_exists(db, USER_ID)
        assert (settings.uploads_dir / USER_ID).exists()

    def test_blocked_when_auth_is_disabled(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "auth_disabled", True)

        response = _post(client)

        assert response.status_code == 403
        assert user_exists(db, USER_ID)


class TestRateLimitCarryover:
    """Erasing an account must not reset the daily submission budget."""

    def test_used_quota_survives_the_deletion(self, client, db):
        _post(client)

        count, oldest = DeletedAccountQuotaRepository(db).get_user_carryover(USER_ID)

        assert count == 1
        assert oldest is not None

    def test_tombstone_holds_no_readable_identifier(self, client, db):
        _post(client)

        row = db.query(DeletedAccountQuotaDB).one()
        assert row.user_hash != USER_ID
        assert USER_ID not in row.user_hash

    def test_no_tombstone_when_nothing_was_submitted(self, client, db):
        db.query(SubmissionDB).filter(SubmissionDB.user_id == USER_ID).delete()
        db.commit()

        _post(client)

        assert db.query(DeletedAccountQuotaDB).count() == 0

    def test_rejected_deletion_records_nothing(self, client, db):
        _post(client, "nope")

        assert db.query(DeletedAccountQuotaDB).count() == 0


class TestAuthMeGate:
    """The UI only renders the delete button when the backend would accept it."""

    def test_available_for_a_normal_user(self, client, db):
        body = client.get("/api/auth/me").json()

        assert body["can_delete_account"] is True
        assert body["account_delete_confirmation"] == ACCOUNT_DELETE_CONFIRMATION

    def test_unavailable_for_admins(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "admin_emails", USER_EMAIL)

        assert client.get("/api/auth/me").json()["can_delete_account"] is False

    def test_unavailable_when_auth_is_disabled(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "auth_disabled", True)

        assert client.get("/api/auth/me").json()["can_delete_account"] is False

    def test_unavailable_when_not_logged_in(self, client, db, monkeypatch):
        monkeypatch.setattr(main, "verify_auth", lambda request: False)

        assert client.get("/api/auth/me").json()["can_delete_account"] is False


class TestCarryoverIsEnforcedOnSubmit:
    """The tombstone only matters if submit/ actually honours it.

    Scenario the feature exists for: a user burns the daily limit, deletes the
    account, signs in again with the same Google account (same sub, fresh row,
    zero submissions) and expects a fresh budget. They must not get one.
    """

    def _submit(self, client):
        return client.post(
            "/task/2024/etap1/1/submit",
            files=[("images", ("page.jpg", b"not-a-real-image", "image/jpeg"))],
        )

    def test_deleting_and_returning_does_not_reset_the_daily_limit(
        self, client, db, monkeypatch
    ):
        monkeypatch.setattr(settings, "rate_limit_submissions_per_user_per_day", 1)
        monkeypatch.setattr(settings, "public_access", True)
        monkeypatch.setattr(settings, "allowed_emails", None)
        monkeypatch.setattr(main, "_get_allowed_emails", lambda: set())

        # The fixture already gave this user one submission inside the window,
        # which is the whole daily budget.
        blocked = self._submit(client)
        assert blocked.status_code == 429

        # Erase the account, then come back as the same Google user
        assert _post(client).status_code == 200
        db.add(UserDB(google_sub=USER_ID, email=USER_EMAIL, name="Kid"))
        db.commit()

        still_blocked = self._submit(client)

        assert still_blocked.status_code == 429, (
            "deleting the account handed out a fresh daily budget"
        )

    def test_a_user_who_never_submitted_is_not_penalised(
        self, client, db, monkeypatch
    ):
        """The tombstone must not block someone with quota left."""
        monkeypatch.setattr(settings, "rate_limit_submissions_per_user_per_day", 10)
        monkeypatch.setattr(settings, "public_access", True)
        monkeypatch.setattr(settings, "allowed_emails", None)
        monkeypatch.setattr(main, "_get_allowed_emails", lambda: set())

        assert _post(client).status_code == 200
        db.add(UserDB(google_sub=USER_ID, email=USER_EMAIL, name="Kid"))
        db.commit()

        response = self._submit(client)

        # Not a 429: the request gets past the rate limit and fails later, on
        # the (deliberately invalid) image itself.
        assert response.status_code != 429


class TestRetryAfterForAReturningUser:
    """The header a user actually receives after deleting and signing back in.

    The carried-over quota is one block released at the tombstone's expires_at,
    so Retry-After has to span the rest of the window. Pointing it at the oldest
    submission behind the block produced "retry in an hour" followed by another
    429 an hour later, and again, for the whole day.
    """

    def _submit(self, client):
        return client.post(
            "/task/2024/etap1/1/submit",
            files=[("images", ("page.jpg", b"not-a-real-image", "image/jpeg"))],
        )

    def _spread_submissions(self, db, hours_ago: list[int]) -> None:
        """Replace the fixture's single submission with a spread-out set."""
        db.query(SubmissionDB).filter(SubmissionDB.user_id == USER_ID).delete()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for index, hours in enumerate(hours_ago):
            db.add(
                SubmissionDB(
                    id=f"s{index:07d}",
                    user_id=USER_ID,
                    year="2024",
                    etap="etap1",
                    task_number=1,
                    timestamp=now - timedelta(hours=hours),
                    status=SubmissionStatus.COMPLETED,
                    images=[],
                    score=5,
                    feedback="ok",
                )
            )
        db.commit()

    def test_retry_after_spans_the_rest_of_the_window(self, client, db, monkeypatch):
        # Quota spent between T-23h and T-1h, exactly the reported scenario
        self._spread_submissions(db, [23, 12, 1])
        monkeypatch.setattr(settings, "rate_limit_submissions_per_user_per_day", 3)
        monkeypatch.setattr(settings, "public_access", True)
        monkeypatch.setattr(settings, "allowed_emails", None)
        monkeypatch.setattr(main, "_get_allowed_emails", lambda: set())

        assert _post(client).status_code == 200  # delete the account
        db.add(UserDB(google_sub=USER_ID, email=USER_EMAIL, name="Kid"))
        db.commit()

        response = self._submit(client)

        assert response.status_code == 429
        retry_after = int(response.headers["Retry-After"])
        # ~23h (24h after the newest submission), not the ~1h the oldest gave
        assert retry_after > 20 * 3600, f"Retry-After was only {retry_after}s"
        assert retry_after <= 23 * 3600 + 120

    def test_retry_after_matches_the_reset_header(self, client, db, monkeypatch):
        self._spread_submissions(db, [23, 12, 1])
        monkeypatch.setattr(settings, "rate_limit_submissions_per_user_per_day", 3)
        monkeypatch.setattr(settings, "public_access", True)
        monkeypatch.setattr(main, "_get_allowed_emails", lambda: set())

        _post(client)
        db.add(UserDB(google_sub=USER_ID, email=USER_EMAIL, name="Kid"))
        db.commit()

        response = self._submit(client)

        reset_at = int(response.headers["X-RateLimit-Reset"])
        retry_after = int(response.headers["Retry-After"])
        now = int(datetime.now(timezone.utc).timestamp())
        assert abs((reset_at - now) - retry_after) <= 2

    def test_waiting_the_advertised_time_actually_unblocks(self, client, db, monkeypatch):
        """The property the old header violated: after Retry-After, no 429."""
        self._spread_submissions(db, [23, 12, 1])
        monkeypatch.setattr(settings, "rate_limit_submissions_per_user_per_day", 3)
        monkeypatch.setattr(settings, "public_access", True)
        monkeypatch.setattr(main, "_get_allowed_emails", lambda: set())

        _post(client)
        db.add(UserDB(google_sub=USER_ID, email=USER_EMAIL, name="Kid"))
        db.commit()

        blocked = self._submit(client)
        retry_after = int(blocked.headers["Retry-After"])

        # Simulate the wait by ageing the tombstone by exactly that much
        tombstone = db.query(DeletedAccountQuotaDB).one()
        tombstone.expires_at = tombstone.expires_at - timedelta(seconds=retry_after + 5)
        db.commit()

        after_waiting = self._submit(client)

        assert after_waiting.status_code != 429
