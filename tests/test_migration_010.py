"""Migration 010 on a real PostgreSQL with existing users.

The rename users.google_sub -> users.id must keep every id and every foreign
key. SQLite cannot show that (the other tests build the schema from the ORM),
so this runs only against a throwaway PostgreSQL named by OMJ_TEST_PG_URL,
e.g. postgresql://omj:omj@localhost:55439/omj_migtest. THE DATABASE IS WIPED.
"""

import os
import pathlib

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

PG_URL = os.environ.get("OMJ_TEST_PG_URL")
ROOT = pathlib.Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(not PG_URL, reason="OMJ_TEST_PG_URL not set")


def _alembic(monkeypatch, *args):
    from alembic import command
    from alembic.config import Config

    from app.config import settings

    monkeypatch.setattr(settings, "database_url", PG_URL)
    # No ini file: env.py would run logging.fileConfig, which disables every
    # existing logger and breaks later tests that capture log output
    config = Config()
    config.set_main_option("script_location", str(ROOT / "alembic"))
    getattr(command, args[0])(config, *args[1:])


@pytest.fixture
def engine(monkeypatch):
    engine = create_engine(PG_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    yield engine
    engine.dispose()


def test_upgrade_keeps_ids_and_foreign_keys(engine, monkeypatch):
    _alembic(monkeypatch, "upgrade", "009")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (google_sub, email, name, created_at, updated_at) VALUES "
            "('104857600000000000001', 'kid@gmail.com', 'Kid', now(), now()), "
            "('104857600000000000002', 'other@gmail.com', 'Other', now(), now())"
        ))
        conn.execute(text(
            "INSERT INTO submissions (id, user_id, year, etap, task_number, timestamp, status, images, "
            "created_at, issue_type, abuse_score, hints_used) VALUES "
            "('sub00001', '104857600000000000001', '2024', 'etap1', 1, now(), 'COMPLETED', '[]', now(), 'none', 0, 0)"
        ))
        conn.execute(text(
            "INSERT INTO ai_usage (user_id, kind, created_at) VALUES ('104857600000000000001', 'private_extract', now())"
        ))

    _alembic(monkeypatch, "upgrade", "010")

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, google_sub, email, status, session_version, birth_year, login FROM users ORDER BY id"
        )).all()
        assert rows == [
            ("104857600000000000001", "104857600000000000001", "kid@gmail.com", "active", 0, None, None),
            ("104857600000000000002", "104857600000000000002", "other@gmail.com", "active", 0, None, None),
        ]
        # Every user_id foreign key now points at users.id
        targets = conn.execute(text(
            "SELECT DISTINCT ccu.column_name FROM information_schema.referential_constraints rc "
            "JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = rc.unique_constraint_name "
            "WHERE ccu.table_name = 'users'"
        )).scalars().all()
        assert targets == ["id"]

    # The ORM works on the migrated schema: a login account with a parent
    from sqlalchemy.orm import sessionmaker

    from app.db.models import ParentDB, SubmissionDB, UserDB

    session = sessionmaker(bind=engine)()
    try:
        session.add(ParentDB(id="p" * 32, email="mama@example.com"))
        session.flush()
        session.add(UserDB(id="u" * 32, login="kuba_m", password_hash="$argon2id$x", birth_year=2013,
                           parent_id="p" * 32, status="pending_parent"))
        session.commit()
        assert session.get(SubmissionDB, "sub00001").user.email == "kid@gmail.com"

        # ensure_parent's INSERT ... ON CONFLICT DO NOTHING on PostgreSQL
        from app.accounts.service import ensure_parent

        first = ensure_parent(session, "tata@example.com")
        again = ensure_parent(session, "tata@example.com")
        assert first.id == again.id
        assert ensure_parent(session, "mama@example.com").id == "p" * 32

        # Neither Google nor login: refused by ck_users_identity
        session.add(UserDB(id="v" * 32, email="x@example.com"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # A login account without a parent: refused by ck_users_login_parent
        session.add(UserDB(id="w" * 32, login="ola_k", password_hash="$argon2id$x"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # ON DELETE CASCADE still reaches submissions through the renamed key
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE id = '104857600000000000001'"))
            assert conn.execute(text("SELECT count(*) FROM submissions")).scalar() == 0
            assert conn.execute(text("SELECT count(*) FROM ai_usage")).scalar() == 0

        # Downgrade only on a database that never used the new flows: each of
        # these alone makes it refuse
        session.query(UserDB).filter(UserDB.login.isnot(None)).delete()
        session.commit()
        refusals = [
            # first, so the cases after it are refused for their own reason
            ("a parent address", None, "DELETE FROM parents"),  # the row from above is still there
            ("a Google account with a random id",
             "INSERT INTO users (id, google_sub, email, created_at, updated_at, status, session_version) "
             "VALUES ('nnnn', 'g-new', 'new@gmail.com', now(), now(), 'active', 0)",
             "DELETE FROM users WHERE id = 'nnnn'"),
            ("a year of birth",
             "UPDATE users SET birth_year = 2005",
             "UPDATE users SET birth_year = NULL"),
            ("a pending account",
             "UPDATE users SET status = 'pending_parent'",
             "UPDATE users SET status = 'active'"),
            ("a consent record",
             "INSERT INTO consents (user_id, kind, terms_version, given_at) "
             "VALUES ('104857600000000000002', 'self', '2026-10-12', now())",
             "DELETE FROM consents"),
        ]
        for label, setup, cleanup in refusals:
            if setup:
                with engine.begin() as conn:
                    conn.execute(text(setup))
            with pytest.raises(RuntimeError, match="Cannot downgrade below 010"):
                _alembic(monkeypatch, "downgrade", "009")
            with engine.begin() as conn:
                conn.execute(text(cleanup))
    finally:
        session.close()

    # Down and up again
    _alembic(monkeypatch, "downgrade", "009")
    with engine.begin() as conn:
        assert conn.execute(text("SELECT google_sub FROM users")).scalars().all() == ["104857600000000000002"]
    _alembic(monkeypatch, "upgrade", "head")
