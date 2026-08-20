"""Admin access to another user's data must leave an audit trail (RODO art. 5(2)).

An admin can read every submission and every uploaded photo. Without a record
there is no way to demonstrate accountability, or to notice one child's work
being browsed repeatedly.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
from app.config import settings
from app.db import get_db
from app.db.models import AdminAccessLogDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.repositories import AdminAccessLogRepository, hash_user_id
from app.db.session import Base
from app.retention import erase_user_data, purge_expired_admin_audit

ADMIN_ID = "admin-1"
ADMIN_EMAIL = "admin@example.com"
STUDENT_ID = "student-1"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "admin_emails", ADMIN_EMAIL)
    monkeypatch.setattr(settings, "session_secret_key", "test-secret-key")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    # Audit writes must open their OWN session, exactly as in production -
    # sharing the request session here would hide the very bug this guards.
    session.audit_session_factory = session_factory

    session.add(UserDB(google_sub=ADMIN_ID, email=ADMIN_EMAIL, name="Admin"))
    session.add(UserDB(google_sub=STUDENT_ID, email="kid@example.com", name="Kid"))
    for user_id in (ADMIN_ID, STUDENT_ID):
        directory = settings.uploads_dir / user_id / "2024" / "etap1" / "1"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "page1.jpg").write_bytes(b"x" * 64)
        session.add(
            SubmissionDB(
                id=f"sub-{user_id}"[:8],
                user_id=user_id,
                year="2024",
                etap="etap1",
                task_number=1,
                timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
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
    """TestClient authenticated as the admin."""
    def override_get_db():
        yield db

    main.app.dependency_overrides[get_db] = override_get_db

    admin = {"google_sub": ADMIN_ID, "email": ADMIN_EMAIL, "name": "Admin"}
    monkeypatch.setattr(main, "verify_auth", lambda request: True)
    monkeypatch.setattr(main, "get_current_user_id", lambda request: ADMIN_ID)
    monkeypatch.setattr(main, "get_current_user", lambda request: admin)
    monkeypatch.setattr(main, "require_auth_redirect", lambda request: None)
    # Audit writes open their own session (see the db fixture)
    monkeypatch.setattr("app.db.SessionLocal", db.audit_session_factory)

    yield TestClient(main.app)

    main.app.dependency_overrides.clear()


def entries(db) -> list[AdminAccessLogDB]:
    # The audit rows were committed by a different session; end this session's
    # read transaction so the query sees them.
    db.rollback()
    return db.query(AdminAccessLogDB).order_by(AdminAccessLogDB.id).all()


class TestRepository:
    def test_records_who_whose_what_when(self, db):
        AdminAccessLogRepository(db).record(
            admin_email=ADMIN_EMAIL,
            resource="upload",
            subject_user_id=STUDENT_ID,
            resource_id="student-1/2024/etap1/1/page1.jpg",
            admin_user_id=ADMIN_ID,
        )

        entry = db.query(AdminAccessLogDB).one()
        assert entry.admin_email == ADMIN_EMAIL
        assert entry.subject_user_id == STUDENT_ID
        assert entry.resource == "upload"
        assert entry.resource_id.endswith("page1.jpg")
        assert entry.created_at is not None

    def test_skips_admins_own_data(self, db):
        AdminAccessLogRepository(db).record(
            admin_email=ADMIN_EMAIL,
            resource="upload",
            subject_user_id=ADMIN_ID,
            admin_user_id=ADMIN_ID,
        )

        assert db.query(AdminAccessLogDB).count() == 0

    def test_erasure_replaces_the_subject_with_a_digest(self, db):
        repo = AdminAccessLogRepository(db)
        repo.record(ADMIN_EMAIL, "upload", STUDENT_ID, admin_user_id=ADMIN_ID)

        updated = repo.pseudonymize_subject(STUDENT_ID)
        db.commit()

        entry = db.query(AdminAccessLogDB).one()
        assert updated == 1
        assert entry.subject_user_id == hash_user_id(STUDENT_ID)
        assert entry.resource == "upload"  # the fact of access survives


class TestEndpoints:
    def test_submissions_listing_is_audited(self, client, db):
        response = client.get("/api/admin/submissions")

        assert response.status_code == 200
        assert [e.resource for e in entries(db)] == ["admin_submissions_list"]

    def test_listing_filtered_by_user_records_the_subject(self, client, db):
        client.get(f"/api/admin/submissions?user_id={STUDENT_ID}")

        assert entries(db)[0].subject_user_id == STUDENT_ID

    def test_listing_filtered_to_own_data_is_not_audited(self, client, db):
        client.get(f"/api/admin/submissions?user_id={ADMIN_ID}")

        assert entries(db) == []

    def test_user_search_with_no_results_is_still_audited(self, client, db):
        """Regression: the entry was only written `if users:`, so an admin
        probing for an address that is not in the database - the access most
        worth a trace - left none at all."""
        response = client.get("/api/admin/users/search?q=nobody-here")

        assert response.status_code == 200
        assert response.json()["users"] == []
        entry = entries(db)[0]
        assert entry.resource == "admin_user_search"
        assert entry.resource_id == "0 results"
        assert "nobody-here" not in (entry.resource_id or "")

    def test_short_query_rejected_by_the_repo_is_still_audited(self, client, db):
        """search_by_email returns [] for <2 chars; the attempt still happened."""
        response = client.get("/api/admin/users/search?q=k")

        assert response.status_code == 200
        assert [e.resource for e in entries(db)] == ["admin_user_search"]

    def test_user_search_is_audited_without_storing_the_query(self, client, db):
        response = client.get("/api/admin/users/search?q=kid")

        assert response.status_code == 200
        entry = entries(db)[0]
        assert entry.resource == "admin_user_search"
        assert "kid" not in (entry.resource_id or "")
        assert entry.subject_user_id is None

    def test_viewing_another_users_photo_is_audited(self, client, db):
        response = client.get(f"/uploads/{STUDENT_ID}/2024/etap1/1/page1.jpg")

        assert response.status_code == 200
        entry = entries(db)[0]
        assert entry.resource == "upload"
        assert entry.subject_user_id == STUDENT_ID

    def test_resource_id_does_not_repeat_the_users_id(self, client, db):
        """subject_user_id is pseudonymized on erasure; a copy of the id inside
        resource_id would survive it and defeat the point."""
        client.get(f"/uploads/{STUDENT_ID}/2024/etap1/1/page1.jpg")

        entry = entries(db)[0]
        assert STUDENT_ID not in (entry.resource_id or "")
        assert entry.resource_id == "2024/etap1/1/page1.jpg"

    def test_missing_file_is_not_audited(self, client, db):
        """The table records real accesses, not 404s."""
        response = client.get(f"/uploads/{STUDENT_ID}/2024/etap1/1/nope.jpg")

        assert response.status_code == 404
        assert entries(db) == []

    def test_traversal_attempt_is_not_audited(self, client, db):
        response = client.get(f"/uploads/{STUDENT_ID}/../../../etc/passwd")

        assert response.status_code in (403, 404)
        assert entries(db) == []

    def test_viewing_own_photo_is_not_audited(self, client, db):
        response = client.get(f"/uploads/{ADMIN_ID}/2024/etap1/1/page1.jpg")

        assert response.status_code == 200
        assert entries(db) == []

    def test_audit_entry_holds_no_content(self, client, db):
        client.get("/api/admin/submissions")

        entry = entries(db)[0]
        columns = {c.name for c in AdminAccessLogDB.__table__.columns}
        assert columns == {
            "id",
            "admin_email",
            "subject_user_id",
            "resource",
            "resource_id",
            "created_at",
        }
        assert "ok" not in str(entry.resource_id)  # no feedback text


class TestRetention:
    def _entry(self, db, days_ago: int) -> None:
        db.add(
            AdminAccessLogDB(
                admin_email=ADMIN_EMAIL,
                subject_user_id=STUDENT_ID,
                resource="upload",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                - timedelta(days=days_ago),
            )
        )
        db.commit()

    def test_deletes_entries_past_the_period(self, db):
        self._entry(db, days_ago=800)
        self._entry(db, days_ago=10)

        report = purge_expired_admin_audit(db, months=12)

        assert report.audit_entries_purged == 1
        assert db.query(AdminAccessLogDB).count() == 1

    def test_dry_run_changes_nothing(self, db):
        self._entry(db, days_ago=800)

        report = purge_expired_admin_audit(db, months=12, dry_run=True)

        assert report.audit_entries_purged == 1
        assert db.query(AdminAccessLogDB).count() == 1

    @pytest.mark.parametrize("months", [0, None])
    def test_disabled_retention_is_a_no_op(self, db, months, monkeypatch):
        monkeypatch.setattr(settings, "retention_admin_audit_months", months)
        self._entry(db, days_ago=5000)

        report = purge_expired_admin_audit(db, months=months)

        assert report.audit_entries_purged == 0

    def test_account_erasure_pseudonymizes_the_trail(self, db):
        self._entry(db, days_ago=1)

        erase_user_data(db, STUDENT_ID)

        entry = db.query(AdminAccessLogDB).one()
        assert entry.subject_user_id == hash_user_id(STUDENT_ID)

    def test_no_column_still_holds_the_erased_id(self, db):
        """Regression: resource_id used to carry the raw sub as a path prefix."""
        db.add(
            AdminAccessLogDB(
                admin_email=ADMIN_EMAIL,
                subject_user_id=STUDENT_ID,
                resource="upload",
                resource_id="2024/etap1/1/page1.jpg",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        db.commit()

        erase_user_data(db, STUDENT_ID)

        entry = db.query(AdminAccessLogDB).one()
        assert STUDENT_ID not in str(entry.subject_user_id)
        assert STUDENT_ID not in str(entry.resource_id)


class TestAuditDoesNotDisturbTheRequestSession:
    """Regression: the audit repository commits, and it used to commit the
    session injected by Depends(get_db). That expires every ORM object the
    endpoint has already loaded, so serializing the response re-SELECTs one row
    per object (N+1) - and a row deleted meanwhile raises ObjectDeletedError,
    turning a read-only admin page into a 500."""

    def test_audit_write_does_not_commit_the_request_session(self, client, db):
        """Probe an object the endpoint never touches.

        Probing one of the returned users would not work: after a commit the
        endpoint re-loads them while serializing the response - which is the N+1
        itself - and that clears the expired flag before the test can look.
        """
        from sqlalchemy import inspect

        untouched = db.query(SubmissionDB).filter(SubmissionDB.user_id == STUDENT_ID).one()
        assert not inspect(untouched).expired

        response = client.get("/api/admin/users/search?q=kid")

        assert response.status_code == 200
        assert not inspect(untouched).expired, (
            "the audit write committed the request session"
        )

    def test_audit_write_adds_no_extra_select_on_users(self, client, db):
        """The N+1: a committed session re-SELECTs every serialized user."""
        from sqlalchemy import event

        statements: list[str] = []

        def record_sql(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", record_sql)
        try:
            response = client.get("/api/admin/users/search?q=kid")
        finally:
            event.remove(engine, "before_cursor_execute", record_sql)

        assert response.status_code == 200
        user_selects = [
            st for st in statements
            if st.lstrip().upper().startswith("SELECT") and "FROM users" in st
        ]
        assert len(user_selects) == 1, (
            f"expected one query for the user list, got {len(user_selects)}:\n"
            + "\n".join(user_selects)
        )

    def test_search_still_returns_the_user_data(self, client, db):
        """What the N+1 / ObjectDeletedError would break, end to end."""
        response = client.get("/api/admin/users/search?q=kid")

        assert response.status_code == 200
        users = response.json()["users"]
        assert [u["email"] for u in users] == ["kid@example.com"]

    def test_submissions_listing_still_serializes_after_the_audit_write(self, client, db):
        response = client.get("/api/admin/submissions")

        assert response.status_code == 200
        body = response.json()
        assert body["submissions"], "listing came back empty"
        assert all(s["user_id"] for s in body["submissions"])

    def test_audit_row_is_committed_even_though_it_uses_another_session(self, client, db):
        client.get("/api/admin/submissions")

        assert [e.resource for e in entries(db)] == ["admin_submissions_list"]
