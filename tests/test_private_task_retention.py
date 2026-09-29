"""Retention and erasure for private tasks - children's data must not linger."""

import os
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models import (
    AIUsageDB,
    DeletedAccountQuotaDB,
    PrivateTaskDB,
    SubmissionDB,
    SubmissionStatus,
    UserDB,
)
from app.db.session import Base
from app.retention import (
    erase_user_data,
    purge_expired_ai_usage,
    purge_expired_private_tasks,
    run_retention,
    strip_expired_scoring_thinking,
    sweep_orphan_upload_files,
)

USER_ID = "user-1"


def naive_utc(**delta):
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(**delta)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(UserDB(google_sub=USER_ID, email="a@example.com"))
    session.commit()
    yield session
    session.close()


def write(rel: str, age_hours: float = 0) -> str:
    path = settings.uploads_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * 100)
    if age_hours:
        old = time.time() - age_hours * 3600
        os.utime(path, (old, old))
    return rel


def make_task(db, task_id, idle_days=0, with_submission=True, extraction_meta=None):
    source = write(f"{USER_ID}/private/{task_id}/source/p1.jpg", age_hours=idle_days * 24)
    task = PrivateTaskDB(
        id=task_id, user_id=USER_ID, title="T", content="Invented statement for tests.",
        hints=[], source_images=[source], origin="photo",
        extraction_meta=extraction_meta,
        created_at=naive_utc(days=-idle_days), updated_at=naive_utc(days=-idle_days),
        last_activity_at=naive_utc(days=-idle_days),
    )
    db.add(task)
    if with_submission:
        img = write(f"{USER_ID}/private/{task_id}/sol.jpg", age_hours=idle_days * 24)
        db.add(SubmissionDB(
            id=f"s{task_id[:7]}", user_id=USER_ID, private_task_id=task_id, images=[img],
            status=SubmissionStatus.COMPLETED, score=5,
            timestamp=naive_utc(days=-idle_days), created_at=naive_utc(days=-idle_days),
        ))
    db.commit()
    return task


def files():
    root = settings.uploads_dir
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


class TestPrivateTaskExpiry:
    def test_idle_task_is_deleted_with_files_and_submissions(self, db):
        make_task(db, "oldoldoldold", idle_days=25 * 31)
        make_task(db, "newnewnewnew", idle_days=1)

        report = purge_expired_private_tasks(db, months=24)

        assert report.private_tasks_deleted == 1
        assert [t.id for t in db.query(PrivateTaskDB).all()] == ["newnewnewnew"]
        assert db.query(SubmissionDB).count() == 1
        assert all("oldoldoldold" not in f for f in files())
        assert not (settings.uploads_dir / USER_ID / "private" / "oldoldoldold").exists()

    def test_dry_run_changes_nothing(self, db):
        make_task(db, "oldoldoldold", idle_days=25 * 31)
        before = files()

        report = purge_expired_private_tasks(db, months=24, dry_run=True)

        assert report.private_tasks_deleted == 1
        assert db.query(PrivateTaskDB).count() == 1
        assert files() == before

    def test_disabled_when_zero(self, db):
        make_task(db, "oldoldoldold", idle_days=25 * 31)
        assert purge_expired_private_tasks(db, months=0).private_tasks_deleted == 0
        assert db.query(PrivateTaskDB).count() == 1


class TestAIUsageExpiry:
    def test_old_rows_are_purged(self, db):
        db.add(AIUsageDB(user_id=USER_ID, kind="private_extract", created_at=naive_utc(days=-91)))
        db.add(AIUsageDB(user_id=USER_ID, kind="private_extract", created_at=naive_utc(days=-1)))
        db.commit()

        report = purge_expired_ai_usage(db, days=90)

        assert report.ai_usage_purged == 1
        assert db.query(AIUsageDB).count() == 1


class TestThinking:
    def test_thinking_stripped_from_old_extraction_meta(self, db):
        make_task(db, "oldoldoldold", idle_days=100, with_submission=False,
                  extraction_meta={"thinking": "verbatim", "model": "m"})

        strip_expired_scoring_thinking(db, days=90)

        task = db.get(PrivateTaskDB, "oldoldoldold")
        assert task.extraction_meta == {"model": "m"}


class TestOrphanSweep:
    def test_stale_draft_is_swept_fresh_draft_kept(self, db):
        make_task(db, "keepkeepkeep", idle_days=10)
        write(f"{USER_ID}/private/_drafts/{'a' * 16}/p.jpg", age_hours=30)
        write(f"{USER_ID}/private/_drafts/{'b' * 16}/p.jpg", age_hours=1)

        sweep_orphan_upload_files(db)

        left = files()
        assert f"{USER_ID}/private/_drafts/{'a' * 16}/p.jpg" not in left
        assert f"{USER_ID}/private/_drafts/{'b' * 16}/p.jpg" in left

    def test_task_source_photos_are_never_orphans(self, db):
        make_task(db, "keepkeepkeep", idle_days=10, with_submission=False)

        sweep_orphan_upload_files(db)

        assert f"{USER_ID}/private/keepkeepkeep/source/p1.jpg" in files()

    def test_sweep_runs_when_only_private_tasks_exist(self, db):
        make_task(db, "keepkeepkeep", idle_days=10, with_submission=False)
        write(f"{USER_ID}/private/_drafts/{'a' * 16}/p.jpg", age_hours=30)

        sweep_orphan_upload_files(db)

        assert all("_drafts" not in f for f in files())


class TestErasure:
    def test_account_erasure_removes_everything_private(self, db):
        make_task(db, "taskonetaskk", idle_days=1)
        write(f"{USER_ID}/private/_drafts/{'c' * 16}/p.jpg")
        db.add(AIUsageDB(user_id=USER_ID, kind="private_create"))
        db.commit()

        erase_user_data(db, USER_ID)

        assert db.query(PrivateTaskDB).count() == 0
        assert db.query(SubmissionDB).count() == 0
        assert db.query(AIUsageDB).count() == 0
        assert files() == []


def test_run_retention_includes_private_passes(db, monkeypatch):
    monkeypatch.setattr(settings, "retention_private_task_months", 24)
    monkeypatch.setattr(settings, "retention_ai_usage_days", 90)
    make_task(db, "oldoldoldold", idle_days=25 * 31)
    db.add(AIUsageDB(user_id=USER_ID, kind="private_extract", created_at=naive_utc(days=-91)))
    db.commit()

    report = run_retention(db)

    assert report.private_tasks_deleted == 1
    assert report.ai_usage_purged == 1
    assert "private tasks" in report.summary()
