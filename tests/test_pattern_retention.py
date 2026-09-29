"""Retention for patterns: idle patterns (with links and reviews) are deleted."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models import PatternDB, PatternLinkDB, PatternReviewDB, UserDB
from app.db.patterns import PatternRepository
from app.db.session import Base
from app.retention import erase_user_data, purge_expired_patterns, run_retention

USER_ID = "user-1"


def naive_utc(**delta):
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(**delta)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "session_secret_key", "test-secret")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email="kid@example.com"))
    session.commit()
    yield session
    session.close()


def pattern(db, idle_days):
    repo = PatternRepository(db)
    p = repo.create(USER_ID, trigger="Pytają o parzystość", action="Sprawdź sumę modulo 2",
                    example=None, category=None, skills=[], origin="own", refinement=[],
                    due_on=date(2026, 10, 1))
    repo.add_link(p, task_key="2024_etap1_1", role="source", origin="manual", status="accepted")
    repo.apply_review(p, seen_due_on=p.due_on, new_level=1, new_streak=1, new_due=date(2026, 10, 5),
                      outcome="ok", kind="recall", recall_text="parzystość sumy")
    p.last_activity_at = naive_utc(days=-idle_days)
    db.commit()
    return p.id


def test_idle_pattern_deleted_with_links_and_reviews(db):
    old = pattern(db, idle_days=25 * 31)
    fresh = pattern(db, idle_days=10)

    report = purge_expired_patterns(db, months=24)

    assert report.patterns_deleted == 1
    assert db.get(PatternDB, old) is None
    assert db.get(PatternDB, fresh) is not None
    assert db.query(PatternLinkDB).count() == 1
    assert db.query(PatternReviewDB).count() == 1


def test_disabled_with_zero(db):
    pattern(db, idle_days=2000)
    assert purge_expired_patterns(db, months=0).patterns_deleted == 0
    assert db.query(PatternDB).count() == 1


def test_dry_run_counts_but_keeps(db):
    pattern(db, idle_days=2000)
    assert purge_expired_patterns(db, months=24, dry_run=True).patterns_deleted == 1
    assert db.query(PatternDB).count() == 1


def test_run_retention_includes_patterns(db, monkeypatch):
    monkeypatch.setattr(settings, "retention_pattern_months", 24)
    pattern(db, idle_days=2000)
    report = run_retention(db)
    assert report.patterns_deleted == 1
    assert "patterns" in report.summary()


def test_account_erasure_removes_patterns(db):
    pattern(db, idle_days=1)
    erase_user_data(db, USER_ID)
    assert db.query(PatternDB).count() == 0
    assert db.query(PatternReviewDB).count() == 0
