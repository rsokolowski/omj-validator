"""Tests for data retention and account erasure - both destructive operations.

Retention deletes children's work and the photos of it, so the rules that keep
it safe are covered explicitly: only expired rows go, files never escape
uploads_dir, dry runs change nothing and re-runs are no-ops.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models import DeletedAccountQuotaDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base
from app.retention import (
    count_referenced_upload_paths,
    delete_inactive_accounts,
    erase_user_data,
    purge_expired_quota_tombstones,
    purge_expired_submissions,
    resolve_upload_path,
    run_retention,
    strip_expired_scoring_thinking,
    sweep_orphan_upload_files,
)

USER_ID = "user-1"
OTHER_USER_ID = "user-2"


@pytest.fixture
def db(tmp_path, monkeypatch):
    """In-memory DB plus an isolated uploads dir under tmp_path."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    session.add(UserDB(google_sub=USER_ID, email="a@example.com", name="A"))
    session.add(UserDB(google_sub=OTHER_USER_ID, email="b@example.com", name="B"))
    session.commit()

    yield session

    session.close()


def make_submission(
    db,
    submission_id: str,
    days_ago: int,
    user_id: str = USER_ID,
    image_names: tuple[str, ...] = ("page1.jpg",),
    scoring_meta: dict | None = None,
    year: str = "2024",
    etap: str = "etap1",
    task_number: int = 1,
) -> SubmissionDB:
    """Create a submission row together with real files on disk."""
    relative_paths = []
    for name in image_names:
        directory = settings.uploads_dir / user_id / year / etap / str(task_number)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes(b"x" * 1024)
        relative_paths.append(f"{user_id}/{year}/{etap}/{task_number}/{name}")

    # Columns are timezone-naive UTC (see app/db/models.utc_now)
    timestamp = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
    submission = SubmissionDB(
        id=submission_id,
        user_id=user_id,
        year=year,
        etap=etap,
        task_number=task_number,
        timestamp=timestamp,
        created_at=timestamp,
        status=SubmissionStatus.COMPLETED,
        images=relative_paths,
        score=5,
        feedback="ok",
        scoring_meta=scoring_meta,
    )
    db.add(submission)
    db.commit()
    return submission


def files_on_disk() -> list[str]:
    root = settings.uploads_dir
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


class TestPathSafety:
    def test_rejects_traversal(self, db):
        assert resolve_upload_path("../../etc/passwd") is None
        assert resolve_upload_path("user-1/../../../etc/passwd") is None

    def test_rejects_empty_and_root(self, db):
        assert resolve_upload_path("") is None
        assert resolve_upload_path(".") is None

    def test_accepts_normal_path(self, db):
        resolved = resolve_upload_path("user-1/2024/etap1/1/page1.jpg")
        assert resolved is not None
        assert resolved.is_relative_to(settings.uploads_dir.resolve())

    def test_strips_legacy_uploads_prefix(self, db):
        legacy = resolve_upload_path("uploads/user-1/2024/etap1/1/page1.jpg")
        modern = resolve_upload_path("user-1/2024/etap1/1/page1.jpg")
        assert legacy == modern

    def test_traversal_path_is_never_deleted(self, db, tmp_path):
        outsider = tmp_path / "secret.txt"
        outsider.write_text("keep me")
        submission = make_submission(db, "old00001", days_ago=1000)
        submission.images = [f"../../{outsider.name}"]
        db.commit()

        report = purge_expired_submissions(db, months=24)

        assert outsider.exists()
        assert report.files_skipped_unsafe == 1
        assert report.files_deleted == 0


class TestPurgeExpiredSubmissions:
    def test_deletes_expired_rows_and_files(self, db):
        make_submission(db, "old00001", days_ago=1000)
        make_submission(db, "new00001", days_ago=10, task_number=2)

        report = purge_expired_submissions(db, months=24)

        assert report.submissions_deleted == 1
        assert report.files_deleted == 1
        assert report.bytes_freed == 1024
        assert [s.id for s in db.query(SubmissionDB).all()] == ["new00001"]
        assert files_on_disk() == ["user-1/2024/etap1/2/page1.jpg"]

    def test_keeps_submission_just_inside_the_window(self, db):
        make_submission(db, "keep0001", days_ago=700)  # ~23 months

        report = purge_expired_submissions(db, months=24)

        assert report.submissions_deleted == 0
        assert db.query(SubmissionDB).count() == 1

    def test_removes_empty_directories(self, db):
        make_submission(db, "old00001", days_ago=1000, image_names=("a.jpg", "b.jpg"))

        report = purge_expired_submissions(db, months=24)

        assert report.files_deleted == 2
        assert report.dirs_removed > 0
        assert not (settings.uploads_dir / USER_ID).exists()

    def test_dry_run_changes_nothing(self, db):
        make_submission(db, "old00001", days_ago=1000)

        report = purge_expired_submissions(db, months=24, dry_run=True)

        assert report.dry_run is True
        assert report.submissions_deleted == 1
        assert report.files_deleted == 1
        assert db.query(SubmissionDB).count() == 1
        assert files_on_disk() == ["user-1/2024/etap1/1/page1.jpg"]

    def test_is_idempotent(self, db):
        make_submission(db, "old00001", days_ago=1000)

        first = purge_expired_submissions(db, months=24)
        second = purge_expired_submissions(db, months=24)

        assert first.submissions_deleted == 1
        assert second.submissions_deleted == 0
        assert second.files_deleted == 0

    def test_missing_files_do_not_break_the_run(self, db):
        make_submission(db, "old00001", days_ago=1000)
        (settings.uploads_dir / USER_ID / "2024" / "etap1" / "1" / "page1.jpg").unlink()

        report = purge_expired_submissions(db, months=24)

        assert report.submissions_deleted == 1
        assert report.files_missing == 1
        assert db.query(SubmissionDB).count() == 0

    @pytest.mark.parametrize("months", [0, None])
    def test_disabled_retention_is_a_no_op(self, db, months, monkeypatch):
        monkeypatch.setattr(settings, "retention_submission_months", months)
        make_submission(db, "old00001", days_ago=5000)

        report = purge_expired_submissions(db, months=months)

        assert report.submissions_deleted == 0
        assert db.query(SubmissionDB).count() == 1

    def test_batching_handles_more_rows_than_batch_size(self, db):
        for i in range(7):
            make_submission(db, f"old{i:05d}", days_ago=1000, task_number=i + 1)

        report = purge_expired_submissions(db, months=24, batch_size=2)

        assert report.submissions_deleted == 7
        assert db.query(SubmissionDB).count() == 0

    def test_dry_run_reports_beyond_one_batch(self, db):
        """A dry run deletes nothing, so it must page instead of looping on batch 1."""
        for i in range(7):
            make_submission(db, f"old{i:05d}", days_ago=1000, task_number=i + 1)

        report = purge_expired_submissions(db, months=24, batch_size=2, dry_run=True)

        assert report.submissions_deleted == 7
        assert db.query(SubmissionDB).count() == 7


class TestStripThinking:
    def test_strips_only_the_thinking_key(self, db):
        meta = {"thinking": "uczen napisal...", "model": "gemini", "cost_usd": 0.01}
        make_submission(db, "old00001", days_ago=200, scoring_meta=meta)

        report = strip_expired_scoring_thinking(db, days=90)

        assert report.thinking_stripped == 1
        stored = db.query(SubmissionDB).one().scoring_meta
        assert "thinking" not in stored
        assert stored == {"model": "gemini", "cost_usd": 0.01}

    def test_keeps_recent_thinking(self, db):
        meta = {"thinking": "swiezy slad", "model": "gemini"}
        make_submission(db, "new00001", days_ago=10, scoring_meta=meta)

        report = strip_expired_scoring_thinking(db, days=90)

        assert report.thinking_stripped == 0
        assert db.query(SubmissionDB).one().scoring_meta["thinking"] == "swiezy slad"

    def test_dry_run_changes_nothing(self, db):
        make_submission(db, "old00001", days_ago=200, scoring_meta={"thinking": "t"})

        report = strip_expired_scoring_thinking(db, days=90, dry_run=True)

        assert report.thinking_stripped == 1
        assert db.query(SubmissionDB).one().scoring_meta == {"thinking": "t"}

    def test_is_idempotent(self, db):
        make_submission(db, "old00001", days_ago=200, scoring_meta={"thinking": "t"})

        strip_expired_scoring_thinking(db, days=90)
        second = strip_expired_scoring_thinking(db, days=90)

        assert second.thinking_stripped == 0

    def test_rows_without_thinking_are_skipped(self, db):
        make_submission(db, "old00001", days_ago=200, scoring_meta={"model": "gemini"})

        report = strip_expired_scoring_thinking(db, days=90)

        assert report.thinking_stripped == 0

    @pytest.mark.parametrize("days", [0, None])
    def test_disabled_retention_is_a_no_op(self, db, days, monkeypatch):
        monkeypatch.setattr(settings, "retention_scoring_thinking_days", days)
        make_submission(db, "old00001", days_ago=5000, scoring_meta={"thinking": "t"})

        report = strip_expired_scoring_thinking(db, days=days)

        assert report.thinking_stripped == 0
        assert db.query(SubmissionDB).one().scoring_meta == {"thinking": "t"}

    def test_pages_through_more_rows_than_batch_size(self, db):
        for i in range(5):
            make_submission(
                db, f"old{i:05d}", days_ago=200, task_number=i + 1,
                scoring_meta={"thinking": "t", "model": "gemini"},
            )

        report = strip_expired_scoring_thinking(db, days=90, batch_size=2)

        assert report.thinking_stripped == 5
        assert all("thinking" not in s.scoring_meta for s in db.query(SubmissionDB).all())


class TestRunRetention:
    def test_combines_both_passes(self, db, monkeypatch):
        monkeypatch.setattr(settings, "retention_submission_months", 24)
        monkeypatch.setattr(settings, "retention_scoring_thinking_days", 90)
        make_submission(db, "old00001", days_ago=1000)
        make_submission(db, "mid00001", days_ago=200, task_number=2,
                        scoring_meta={"thinking": "t", "model": "g"})
        make_submission(db, "new00001", days_ago=5, task_number=3,
                        scoring_meta={"thinking": "t"})

        report = run_retention(db)

        assert report.submissions_deleted == 1
        assert report.thinking_stripped == 1
        assert report.files_deleted == 1
        remaining = {s.id for s in db.query(SubmissionDB).all()}
        assert remaining == {"mid00001", "new00001"}


class TestEraseUserData:
    def test_removes_user_submissions_and_files(self, db):
        make_submission(db, "sub00001", days_ago=1)
        make_submission(db, "sub00002", days_ago=2, task_number=2)
        make_submission(db, "other001", days_ago=1, user_id=OTHER_USER_ID)

        report = erase_user_data(db, USER_ID)

        assert report.submissions_deleted == 2
        assert report.files_deleted == 2
        assert db.query(UserDB).filter(UserDB.google_sub == USER_ID).first() is None
        assert [s.id for s in db.query(SubmissionDB).all()] == ["other001"]
        assert not (settings.uploads_dir / USER_ID).exists()

    def test_leaves_other_users_untouched(self, db):
        make_submission(db, "sub00001", days_ago=1)
        make_submission(db, "other001", days_ago=1, user_id=OTHER_USER_ID)

        erase_user_data(db, USER_ID)

        assert db.query(UserDB).filter(UserDB.google_sub == OTHER_USER_ID).first() is not None
        assert files_on_disk() == [f"{OTHER_USER_ID}/2024/etap1/1/page1.jpg"]

    def test_removes_orphan_files_without_a_row(self, db):
        orphan_dir = settings.uploads_dir / USER_ID / "2024" / "etap3" / "9"
        orphan_dir.mkdir(parents=True)
        (orphan_dir / "orphan.jpg").write_bytes(b"y" * 512)

        report = erase_user_data(db, USER_ID)

        assert report.files_deleted == 1
        assert not (settings.uploads_dir / USER_ID).exists()

    def test_dry_run_changes_nothing(self, db):
        make_submission(db, "sub00001", days_ago=1)

        report = erase_user_data(db, USER_ID, dry_run=True)

        assert report.submissions_deleted == 1
        assert db.query(UserDB).filter(UserDB.google_sub == USER_ID).first() is not None
        assert db.query(SubmissionDB).count() == 1
        assert files_on_disk() == ["user-1/2024/etap1/1/page1.jpg"]

    def test_rejects_unsafe_user_id(self, db, tmp_path):
        outsider = tmp_path / "secret.txt"
        outsider.write_text("keep me")

        report = erase_user_data(db, "../..")

        assert outsider.exists()
        assert report.files_skipped_unsafe == 1

    def test_user_without_submissions(self, db):
        report = erase_user_data(db, USER_ID)

        assert report.submissions_deleted == 0
        assert db.query(UserDB).filter(UserDB.google_sub == USER_ID).first() is None


class TestOrphanSweep:
    """Photos are written to disk before the submission row exists (app/main.py),
    so a failure in between leaves files nothing references. Nothing else ever
    reclaims them."""

    def _write_orphan(self, name: str = "orphan.jpg", age_days: int = 2) -> object:
        directory = settings.uploads_dir / USER_ID / "2024" / "etap1" / "9"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_bytes(b"z" * 2048)
        old = (datetime.now(timezone.utc) - timedelta(days=age_days)).timestamp()
        os.utime(path, (old, old))
        return path

    def test_deletes_unreferenced_files(self, db):
        make_submission(db, "keep0001", days_ago=1)
        orphan = self._write_orphan()

        report = sweep_orphan_upload_files(db)

        assert report.files_deleted == 1
        assert report.bytes_freed == 2048
        assert not orphan.exists()

    def test_keeps_referenced_files(self, db):
        make_submission(db, "keep0001", days_ago=400)

        report = sweep_orphan_upload_files(db)

        assert report.files_deleted == 0
        assert files_on_disk() == ["user-1/2024/etap1/1/page1.jpg"]

    def test_keeps_referenced_files_with_legacy_prefix(self, db):
        submission = make_submission(db, "keep0001", days_ago=400)
        submission.images = [f"uploads/{submission.images[0]}"]
        db.commit()

        report = sweep_orphan_upload_files(db)

        assert report.files_deleted == 0

    def test_leaves_fresh_files_alone(self, db):
        """An in-flight upload must never be deleted from under the request."""
        make_submission(db, "keep0001", days_ago=1)
        orphan = self._write_orphan(age_days=0)

        report = sweep_orphan_upload_files(db)

        assert report.files_deleted == 0
        assert orphan.exists()

    def test_dry_run_changes_nothing(self, db):
        make_submission(db, "keep0001", days_ago=1)
        orphan = self._write_orphan()

        report = sweep_orphan_upload_files(db, dry_run=True)

        assert report.files_deleted == 1
        assert orphan.exists()

    def test_refuses_to_sweep_an_empty_submissions_table(self, db):
        """An empty table usually means the DB does not match this uploads dir."""
        orphan = self._write_orphan()

        report = sweep_orphan_upload_files(db)

        assert report.files_deleted == 0
        assert orphan.exists()

    def test_is_idempotent(self, db):
        make_submission(db, "keep0001", days_ago=1)
        self._write_orphan()

        first = sweep_orphan_upload_files(db)
        second = sweep_orphan_upload_files(db)

        assert first.files_deleted == 1
        assert second.files_deleted == 0


class TestTombstonePurge:
    def _tombstone(self, db, user_hash: str, hours_until_expiry: int) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(
            DeletedAccountQuotaDB(
                user_hash=user_hash,
                submission_count=5,
                oldest_submission_at=now,
                expires_at=now + timedelta(hours=hours_until_expiry),
            )
        )
        db.commit()

    def test_removes_only_closed_windows(self, db):
        self._tombstone(db, "a" * 64, hours_until_expiry=-1)
        self._tombstone(db, "b" * 64, hours_until_expiry=5)

        report = purge_expired_quota_tombstones(db)

        assert report.tombstones_purged == 1
        assert db.query(DeletedAccountQuotaDB).count() == 1

    def test_dry_run_changes_nothing(self, db):
        self._tombstone(db, "a" * 64, hours_until_expiry=-1)

        report = purge_expired_quota_tombstones(db, dry_run=True)

        assert report.tombstones_purged == 1
        assert db.query(DeletedAccountQuotaDB).count() == 1


class TestInactiveAccounts:
    """Purging submissions alone leaves an empty account holding a child's
    Google id, e-mail and name forever."""

    def _set_last_login(self, db, user_id: str, days_ago: int) -> None:
        user = db.query(UserDB).filter(UserDB.google_sub == user_id).one()
        user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=days_ago
        )
        db.commit()

    def test_deletes_an_account_with_no_login_and_no_submissions(self, db):
        self._set_last_login(db, USER_ID, days_ago=1500)

        report = delete_inactive_accounts(db, months=36)

        assert report.accounts_deleted == 1
        assert db.query(UserDB).filter(UserDB.google_sub == USER_ID).first() is None

    def test_keeps_a_recently_logged_in_account(self, db):
        self._set_last_login(db, USER_ID, days_ago=10)

        report = delete_inactive_accounts(db, months=36)

        assert report.accounts_deleted == 0
        assert db.query(UserDB).filter(UserDB.google_sub == USER_ID).first() is not None

    def test_recent_submission_counts_as_activity(self, db):
        """A 30-day session lets a student submit without signing in again, so
        the login stamp alone would delete an active account."""
        self._set_last_login(db, USER_ID, days_ago=1500)
        make_submission(db, "recent01", days_ago=5)

        report = delete_inactive_accounts(db, months=36)

        assert report.accounts_deleted == 0
        assert db.query(UserDB).filter(UserDB.google_sub == USER_ID).first() is not None

    def test_old_submission_does_not_keep_the_account_alive(self, db):
        self._set_last_login(db, USER_ID, days_ago=1500)
        make_submission(db, "ancient1", days_ago=1400)

        report = delete_inactive_accounts(db, months=36)

        assert report.accounts_deleted == 1

    def test_deletes_the_files_too(self, db):
        self._set_last_login(db, USER_ID, days_ago=1500)
        make_submission(db, "ancient1", days_ago=1400)

        delete_inactive_accounts(db, months=36)

        assert not (settings.uploads_dir / USER_ID).exists()

    def test_skips_admin_accounts(self, db, monkeypatch):
        monkeypatch.setattr(settings, "admin_emails", "a@example.com")
        self._set_last_login(db, USER_ID, days_ago=5000)

        report = delete_inactive_accounts(db, months=36)

        assert report.accounts_deleted == 0
        assert db.query(UserDB).filter(UserDB.google_sub == USER_ID).first() is not None

    def test_skips_the_anonymous_dev_account(self, db):
        db.add(UserDB(google_sub="anonymous", email="anonymous@localhost"))
        db.commit()
        self._set_last_login(db, "anonymous", days_ago=5000)

        delete_inactive_accounts(db, months=36)

        assert db.query(UserDB).filter(UserDB.google_sub == "anonymous").first() is not None

    def test_leaves_other_accounts_alone(self, db):
        self._set_last_login(db, USER_ID, days_ago=1500)
        self._set_last_login(db, OTHER_USER_ID, days_ago=1)

        delete_inactive_accounts(db, months=36)

        assert db.query(UserDB).filter(UserDB.google_sub == OTHER_USER_ID).first() is not None

    def test_dry_run_changes_nothing(self, db):
        self._set_last_login(db, USER_ID, days_ago=1500)
        make_submission(db, "ancient1", days_ago=1400)

        report = delete_inactive_accounts(db, months=36, dry_run=True)

        assert report.accounts_deleted == 1
        assert db.query(UserDB).filter(UserDB.google_sub == USER_ID).first() is not None
        assert files_on_disk() == ["user-1/2024/etap1/1/page1.jpg"]

    @pytest.mark.parametrize("months", [0, None])
    def test_disabled_retention_is_a_no_op(self, db, months, monkeypatch):
        monkeypatch.setattr(settings, "retention_inactive_account_months", months)
        self._set_last_login(db, USER_ID, days_ago=5000)

        report = delete_inactive_accounts(db, months=months)

        assert report.accounts_deleted == 0
        assert db.query(UserDB).count() == 2

    def test_is_idempotent(self, db):
        self._set_last_login(db, USER_ID, days_ago=1500)

        first = delete_inactive_accounts(db, months=36)
        second = delete_inactive_accounts(db, months=36)

        assert first.accounts_deleted == 1
        assert second.accounts_deleted == 0


class TestPurgeScript:
    """scripts/purge_expired_data.py is the documented retention path for
    multi-worker deployments (RETENTION_AUTO_PURGE=false + cron). It once
    shipped with a NameError that only fired *after* the first passes had
    already deleted rows and files, so it gets a smoke test."""

    def _run(self, *args, db_path):
        import subprocess
        import sys
        from pathlib import Path as _Path

        repo_root = _Path(__file__).resolve().parent.parent
        env = {
            "PATH": os.environ.get("PATH", ""),
            "DATABASE_URL": f"sqlite:///{db_path}",
            "RETENTION_SUBMISSION_MONTHS": "24",
            "RETENTION_SCORING_THINKING_DAYS": "90",
            "RETENTION_INACTIVE_ACCOUNT_MONTHS": "36",
            "RETENTION_ADMIN_AUDIT_MONTHS": "12",
        }
        return subprocess.run(
            [sys.executable, str(repo_root / "scripts" / "purge_expired_data.py"), *args],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            env=env,
        )

    @pytest.fixture
    def script_db(self, tmp_path, monkeypatch):
        """A real (SQLite) database file the script can open for itself."""
        monkeypatch.setattr(settings, "data_dir", str(tmp_path))
        db_path = tmp_path / "retention.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(bind=engine)
        engine.dispose()
        return db_path

    def test_dry_run_completes_and_reports(self, script_db):
        result = self._run("--dry-run", db_path=script_db)

        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr
        assert "DRY RUN" in result.stdout
        assert "Retention:" in result.stdout

    def test_real_run_completes(self, script_db):
        result = self._run(db_path=script_db)

        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr

    def test_every_pass_is_reachable(self, script_db):
        """A missing import used to kill the run half-way through."""
        result = self._run("--dry-run", db_path=script_db)

        summary = result.stdout
        for fragment in (
            "submissions",
            "stripped thinking",
            "rate-limit tombstones",
            "inactive accounts",
            "admin audit entries",
        ):
            assert fragment in summary, f"{fragment!r} missing from:\n{summary}"


class TestSharedFilesBetweenSubmissions:
    """Admin "rerun" creates a second submission reusing the original's images
    verbatim (admin_rerun_submission in app/main.py). Expiring the original must
    not pull the photos out from under the fresh re-scored submission."""

    def _rerun_of(self, db, original: SubmissionDB, new_id: str, days_ago: int) -> SubmissionDB:
        """Mirror what admin_rerun_submission writes: same images list, new row."""
        timestamp = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
        rerun = SubmissionDB(
            id=new_id,
            user_id=original.user_id,
            year=original.year,
            etap=original.etap,
            task_number=original.task_number,
            timestamp=timestamp,
            created_at=timestamp,
            status=SubmissionStatus.COMPLETED,
            images=list(original.images),
            score=6,
            feedback="ok",
        )
        db.add(rerun)
        db.commit()
        return rerun

    def test_expired_original_does_not_delete_files_used_by_a_fresh_rerun(self, db):
        original = make_submission(db, "old00001", days_ago=1000)
        self._rerun_of(db, original, "rerun001", days_ago=1)
        shared = settings.uploads_dir / USER_ID / "2024" / "etap1" / "1" / "page1.jpg"

        report = purge_expired_submissions(db, months=24)

        assert report.submissions_deleted == 1
        assert report.files_deleted == 0, "deleted a file the rerun still needs"
        assert shared.is_file()
        assert [s.id for s in db.query(SubmissionDB).all()] == ["rerun001"]

    def test_files_go_once_the_last_referencing_row_expires(self, db):
        original = make_submission(db, "old00001", days_ago=1000)
        self._rerun_of(db, original, "rerun001", days_ago=900)
        shared = settings.uploads_dir / USER_ID / "2024" / "etap1" / "1" / "page1.jpg"

        report = purge_expired_submissions(db, months=24)

        assert report.submissions_deleted == 2
        assert report.files_deleted == 1, "shared file must be deleted exactly once"
        assert not shared.exists()
        assert db.query(SubmissionDB).count() == 0

    def test_second_run_cleans_up_after_the_rerun_expires(self, db):
        """Expiring in two passes must still end with the files gone."""
        original = make_submission(db, "old00001", days_ago=1000)
        rerun = self._rerun_of(db, original, "rerun001", days_ago=1)
        shared = settings.uploads_dir / USER_ID / "2024" / "etap1" / "1" / "page1.jpg"

        purge_expired_submissions(db, months=24)
        assert shared.is_file()

        # The rerun ages out too
        rerun.timestamp = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1000)
        db.commit()
        report = purge_expired_submissions(db, months=24)

        assert report.submissions_deleted == 1
        assert report.files_deleted == 1
        assert not shared.exists()

    def test_orphan_sweep_does_not_touch_a_shared_file(self, db):
        original = make_submission(db, "old00001", days_ago=1000)
        self._rerun_of(db, original, "rerun001", days_ago=1)
        shared = settings.uploads_dir / USER_ID / "2024" / "etap1" / "1" / "page1.jpg"

        purge_expired_submissions(db, months=24)
        sweep_orphan_upload_files(db)

        assert shared.is_file(), "sweep deleted a file the surviving rerun references"

    def test_dry_run_reports_no_deletion_for_shared_files(self, db):
        original = make_submission(db, "old00001", days_ago=1000)
        self._rerun_of(db, original, "rerun001", days_ago=1)

        report = purge_expired_submissions(db, months=24, dry_run=True)

        assert report.submissions_deleted == 1
        assert report.files_deleted == 0

    def test_reference_counts_see_every_row(self, db):
        original = make_submission(db, "old00001", days_ago=10)
        self._rerun_of(db, original, "rerun001", days_ago=1)
        shared = settings.uploads_dir / USER_ID / "2024" / "etap1" / "1" / "page1.jpg"

        counts = count_referenced_upload_paths(db)

        assert counts[shared.resolve()] == 2

    def test_unshared_files_still_go_normally(self, db):
        """Guard against the fix over-shooting into "never delete anything"."""
        make_submission(db, "old00001", days_ago=1000)
        shared = settings.uploads_dir / USER_ID / "2024" / "etap1" / "1" / "page1.jpg"

        report = purge_expired_submissions(db, months=24)

        assert report.files_deleted == 1
        assert not shared.exists()
