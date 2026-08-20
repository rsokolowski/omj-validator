"""Data retention: expire old submissions, their photos and raw AI traces.

RODO art. 5(1)(e) (storage limitation): personal data of children may not be
kept longer than necessary. Nothing in this app expires on its own, so this
module is the single place that removes it:

  * whole submissions (DB row + uploaded photos) older than
    ``settings.retention_submission_months``;
  * the raw model "thinking" trace inside ``scoring_meta``, which reproduces the
    student's handwritten work verbatim, after
    ``settings.retention_scoring_thinking_days`` - much sooner, because it is
    only useful for short-term debugging.

It is also the place that erases a single account on request (RODO art. 17),
because the ORM cascade removes the rows but never touches the files on disk.

Everything here is idempotent: re-running it finds nothing left to do, and a
run interrupted half-way is simply completed by the next one.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import settings
from .db.models import AdminAccessLogDB, DeletedAccountQuotaDB, SubmissionDB, UserDB
from .privacy import mask_user_id

logger = logging.getLogger(__name__)

# Key inside scoring_meta holding the verbatim reasoning trace
THINKING_KEY = "thinking"

# Average days per month - retention periods are coarse, no need for calendar math
DAYS_PER_MONTH = 30.44

# Grace period before an unreferenced upload counts as an orphan. Must comfortably
# exceed the time between writing the files and inserting the submission row.
ORPHAN_GRACE_HOURS = 24

# A user id is a Google 'sub' (digits) or "anonymous" in dev. Anything with a
# path separator or a dot segment must never reach a filesystem path.
_SAFE_USER_ID = re.compile(r"^[A-Za-z0-9_@.-]+$")


@dataclass
class RetentionReport:
    """Counters for one retention run (or one account erasure)."""

    submissions_deleted: int = 0
    thinking_stripped: int = 0
    tombstones_purged: int = 0
    accounts_deleted: int = 0
    audit_entries_purged: int = 0
    files_deleted: int = 0
    files_missing: int = 0  # already gone - fine, keeps the run idempotent
    files_skipped_unsafe: int = 0  # path escaped uploads_dir - never touched
    dirs_removed: int = 0
    bytes_freed: int = 0
    dry_run: bool = False
    # Paths already counted in this report. A dry run removes nothing, so the
    # same file can be visited twice (once via a submission's images, once via
    # the user's upload tree) - without this it would be counted twice.
    _counted_paths: set = field(default_factory=set, repr=False)

    def merge(self, other: "RetentionReport") -> "RetentionReport":
        """Add another report's counters into this one."""
        self.submissions_deleted += other.submissions_deleted
        self.thinking_stripped += other.thinking_stripped
        self.tombstones_purged += other.tombstones_purged
        self.accounts_deleted += other.accounts_deleted
        self.audit_entries_purged += other.audit_entries_purged
        self.files_deleted += other.files_deleted
        self.files_missing += other.files_missing
        self.files_skipped_unsafe += other.files_skipped_unsafe
        self.dirs_removed += other.dirs_removed
        self.bytes_freed += other.bytes_freed
        self._counted_paths |= other._counted_paths
        return self

    @property
    def megabytes_freed(self) -> float:
        return round(self.bytes_freed / (1024 * 1024), 2)

    def summary(self) -> str:
        prefix = "[DRY RUN] would delete" if self.dry_run else "deleted"
        return (
            f"Retention: {prefix} {self.submissions_deleted} submissions, "
            f"{self.files_deleted} files ({self.megabytes_freed} MB), "
            f"{self.dirs_removed} empty dirs; "
            f"stripped thinking from {self.thinking_stripped} submissions, "
            f"purged {self.tombstones_purged} rate-limit tombstones, "
            f"deleted {self.accounts_deleted} inactive accounts, "
            f"purged {self.audit_entries_purged} admin audit entries "
            f"(missing files: {self.files_missing}, unsafe paths skipped: "
            f"{self.files_skipped_unsafe})"
        )


# --- Path safety -------------------------------------------------------------


def resolve_upload_path(relative_path: str) -> Optional[Path]:
    """Resolve an ``images`` entry to an absolute path inside ``uploads_dir``.

    Returns None when the path escapes the uploads directory. Mirrors the check
    done by the ``/uploads/{path}`` route in app/main.py - deletion must never
    be looser than serving.
    """
    if not relative_path:
        return None

    # Legacy rows stored paths with an 'uploads/' prefix (see serve_upload)
    if relative_path.startswith("uploads/"):
        relative_path = relative_path[len("uploads/"):]

    uploads_root = settings.uploads_dir.resolve()
    candidate = (settings.uploads_dir / relative_path).resolve()
    try:
        candidate.relative_to(uploads_root)
    except ValueError:
        return None
    if candidate == uploads_root:
        return None
    return candidate


def _prune_empty_parents(start: Path, report: RetentionReport, dry_run: bool) -> None:
    """Remove now-empty directories, walking up but never past uploads_dir."""
    uploads_root = settings.uploads_dir.resolve()
    current = start
    while current != uploads_root and uploads_root in current.parents:
        try:
            if any(current.iterdir()):
                return
        except OSError:
            return

        if dry_run:
            # Nothing was actually unlinked, so we cannot tell what *would*
            # become empty; only count directories that are already empty and
            # stop - the parent still contains this one.
            report.dirs_removed += 1
            return

        try:
            current.rmdir()
        except OSError:
            return
        report.dirs_removed += 1
        current = current.parent


def delete_upload_files(
    relative_paths: Iterable[str],
    report: RetentionReport,
    dry_run: bool = False,
) -> None:
    """Delete uploaded files by their submission-relative paths.

    Unsafe paths are counted and skipped, missing files are counted as already
    gone. Empty directories left behind are pruned so no orphans remain.
    """
    touched_dirs: set[Path] = set()

    for relative_path in relative_paths or []:
        path = resolve_upload_path(relative_path)
        if path is None:
            report.files_skipped_unsafe += 1
            logger.warning(f"Retention: refusing unsafe upload path {relative_path!r}")
            continue

        if path in report._counted_paths:
            continue

        if not path.is_file():
            report.files_missing += 1
            continue

        try:
            size = path.stat().st_size
        except OSError:
            size = 0

        if not dry_run:
            try:
                path.unlink()
            except OSError as e:
                logger.warning(f"Retention: could not delete {path}: {e}")
                continue

        report.files_deleted += 1
        report.bytes_freed += size
        report._counted_paths.add(path)
        touched_dirs.add(path.parent)

    for directory in sorted(touched_dirs, key=lambda p: len(p.parts), reverse=True):
        _prune_empty_parents(directory, report, dry_run)


def delete_user_upload_tree(user_id: str, report: RetentionReport, dry_run: bool = False) -> None:
    """Delete every file under ``uploads_dir/{user_id}``, then the directory.

    Used when erasing an account: it also catches files left behind by
    submissions whose DB row never got written.
    """
    if not _SAFE_USER_ID.match(user_id or ""):
        report.files_skipped_unsafe += 1
        logger.warning("Retention: refusing unsafe user id for upload tree deletion")
        return

    user_dir = resolve_upload_path(user_id)
    if user_dir is None or not user_dir.is_dir():
        return

    for path in sorted(user_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_file() or path.is_symlink():
            if path in report._counted_paths:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            if not dry_run:
                try:
                    path.unlink()
                except OSError as e:
                    logger.warning(f"Retention: could not delete {path}: {e}")
                    continue
            report.files_deleted += 1
            report.bytes_freed += size
            report._counted_paths.add(path)
        elif path.is_dir():
            if not dry_run:
                try:
                    path.rmdir()
                except OSError:
                    continue
            report.dirs_removed += 1

    if not dry_run:
        try:
            user_dir.rmdir()
            report.dirs_removed += 1
        except OSError as e:
            logger.warning(f"Retention: could not remove user upload dir {user_dir}: {e}")
    else:
        report.dirs_removed += 1


# --- Retention passes --------------------------------------------------------


def _cutoff_from_months(months: Optional[int]) -> Optional[datetime]:
    if not months or months <= 0:
        return None
    return datetime.now(timezone.utc) - timedelta(days=months * DAYS_PER_MONTH)


def _cutoff_from_days(days: Optional[int]) -> Optional[datetime]:
    if not days or days <= 0:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def count_referenced_upload_paths(db: Session) -> dict[Path, int]:
    """Map every upload path to the number of submission rows referencing it.

    Files are NOT owned by a single submission: admin "rerun" creates a second
    submission that reuses the original's ``images`` list verbatim
    (see admin_rerun_submission in app/main.py). Deleting the expired original's
    files would therefore pull the photos out from under the fresh re-scored
    submission - /uploads would start 404ing and the next rerun would fail with
    "Image files no longer available on disk".

    Same scan sweep_orphan_upload_files does, but keeping the counts so a purge
    can tell "last reference" from "still shared".
    """
    counts: dict[Path, int] = {}
    for (images,) in db.query(SubmissionDB.images).all():
        for relative_path in images or []:
            path = resolve_upload_path(relative_path)
            if path is not None:
                counts[path] = counts.get(path, 0) + 1
    return counts


def _unreferenced_after_delete(
    relative_paths: list[str],
    reference_counts: dict[Path, int],
) -> list[str]:
    """Drop this row's claim on its files; return the ones nothing else claims.

    Unresolvable (unsafe) paths are passed through so delete_upload_files keeps
    counting them as refused rather than silently swallowing them.
    """
    deletable: list[str] = []
    for relative_path in relative_paths:
        path = resolve_upload_path(relative_path)
        if path is None:
            deletable.append(relative_path)
            continue
        remaining = reference_counts.get(path, 1) - 1
        reference_counts[path] = remaining
        if remaining <= 0:
            deletable.append(relative_path)
    return deletable


def purge_expired_submissions(
    db: Session,
    months: Optional[int] = None,
    dry_run: bool = False,
    batch_size: int = 200,
) -> RetentionReport:
    """Delete submissions (rows + photos) older than the retention period.

    Files are removed before the row so an interrupted run leaves at worst a row
    whose files are already gone; the next run finishes the job.
    """
    report = RetentionReport(dry_run=dry_run)
    months = settings.retention_submission_months if months is None else months
    cutoff = _cutoff_from_months(months)
    if cutoff is None:
        logger.info("Retention: submission expiry disabled (retention_submission_months unset/0)")
        return report

    # Column is timezone-naive UTC (see db/models.utc_now)
    naive_cutoff = cutoff.replace(tzinfo=None)

    # Which files are still referenced by *another* submission (typically an
    # admin rerun sharing the original's photos). Decremented as rows go, so a
    # file is only unlinked when its last referencing row is deleted.
    reference_counts = count_referenced_upload_paths(db)

    # A real run deletes the rows it just read, so the next query returns the
    # following batch. A dry run deletes nothing, so it has to page forward.
    offset = 0
    while True:
        batch = (
            db.query(SubmissionDB)
            .filter(SubmissionDB.timestamp < naive_cutoff)
            .order_by(SubmissionDB.timestamp)
            .offset(offset)
            .limit(batch_size)
            .all()
        )
        if not batch:
            break

        for submission in batch:
            delete_upload_files(
                _unreferenced_after_delete(submission.images or [], reference_counts),
                report,
                dry_run=dry_run,
            )
            if not dry_run:
                db.delete(submission)
            report.submissions_deleted += 1

        if dry_run:
            offset += len(batch)
        else:
            db.commit()

    return report


def strip_expired_scoring_thinking(
    db: Session,
    days: Optional[int] = None,
    dry_run: bool = False,
    batch_size: int = 200,
) -> RetentionReport:
    """Remove the verbatim ``thinking`` trace from old submissions' scoring_meta.

    Keeps the rest of scoring_meta (model, tokens, cost, timings) - that part is
    non-personal and needed for cost accounting.
    """
    report = RetentionReport(dry_run=dry_run)
    days = settings.retention_scoring_thinking_days if days is None else days
    cutoff = _cutoff_from_days(days)
    if cutoff is None:
        logger.info(
            "Retention: thinking-trace expiry disabled "
            "(retention_scoring_thinking_days unset/0)"
        )
        return report

    naive_cutoff = cutoff.replace(tzinfo=None)
    offset = 0

    while True:
        batch = (
            db.query(SubmissionDB)
            .filter(
                SubmissionDB.timestamp < naive_cutoff,
                SubmissionDB.scoring_meta.isnot(None),
            )
            .order_by(SubmissionDB.timestamp)
            .offset(offset)
            .limit(batch_size)
            .all()
        )
        if not batch:
            break

        changed_in_batch = 0
        for submission in batch:
            meta = submission.scoring_meta
            if not isinstance(meta, dict) or THINKING_KEY not in meta:
                continue
            report.thinking_stripped += 1
            changed_in_batch += 1
            if not dry_run:
                # Reassign: SQLAlchemy does not track in-place edits of JSON
                stripped = {k: v for k, v in meta.items() if k != THINKING_KEY}
                submission.scoring_meta = stripped

        if not dry_run and changed_in_batch:
            db.commit()

        # Rows keep matching the filter (scoring_meta stays non-NULL), so always
        # page forward instead of re-querying from the start.
        offset += len(batch)

    return report


def sweep_orphan_upload_files(
    db: Session,
    grace_hours: int = ORPHAN_GRACE_HOURS,
    dry_run: bool = False,
) -> RetentionReport:
    """Delete upload files that no submission row references any more.

    The submit endpoint writes the photos to disk *before* it inserts the row,
    so a failure in between leaves a child's work on disk with nothing pointing
    at it - invisible to every other pass and therefore kept forever. Files
    newer than ``grace_hours`` are left alone so an in-flight upload is never
    deleted from under the request that is still writing it.
    """
    report = RetentionReport(dry_run=dry_run)

    uploads_root = settings.uploads_dir.resolve()
    if not uploads_root.is_dir():
        return report

    # Safety net: an empty submissions table usually means the DB is not the one
    # that belongs to this uploads dir (wrong DATABASE_URL / DATA_DIR). Sweeping
    # then would delete every photo we have, so refuse instead.
    if db.query(SubmissionDB.id).limit(1).first() is None:
        logger.info("Retention: no submissions in DB, skipping orphan sweep")
        return report

    referenced: set[Path] = set()
    for (images,) in db.query(SubmissionDB.images).all():
        for relative_path in images or []:
            path = resolve_upload_path(relative_path)
            if path is not None:
                referenced.add(path)

    cutoff = datetime.now(timezone.utc).timestamp() - grace_hours * 3600
    orphans: list[str] = []
    for path in uploads_root.rglob("*"):
        if not path.is_file():
            continue
        if path in referenced:
            continue
        try:
            if path.stat().st_mtime > cutoff:
                continue  # too fresh - may belong to a submission being created
        except OSError:
            continue
        orphans.append(str(path.relative_to(uploads_root)))

    if orphans:
        logger.info(f"Retention: found {len(orphans)} orphaned upload files")
    delete_upload_files(orphans, report, dry_run=dry_run)
    return report


def purge_expired_quota_tombstones(db: Session, dry_run: bool = False) -> RetentionReport:
    """Drop rate-limit tombstones whose 24h window has closed.

    They are pseudonymous but still residue of an erased account, so they must
    not outlive the window they exist for.
    """
    report = RetentionReport(dry_run=dry_run)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    query = db.query(DeletedAccountQuotaDB).filter(
        DeletedAccountQuotaDB.expires_at <= now
    )
    if dry_run:
        report.tombstones_purged = query.count()
        return report

    report.tombstones_purged = query.delete()
    if report.tombstones_purged:
        db.commit()
    return report


def purge_expired_admin_audit(
    db: Session,
    months: Optional[int] = None,
    dry_run: bool = False,
) -> RetentionReport:
    """Delete admin access audit entries past their retention period."""
    report = RetentionReport(dry_run=dry_run)
    months = settings.retention_admin_audit_months if months is None else months
    cutoff = _cutoff_from_months(months)
    if cutoff is None:
        logger.info("Retention: admin audit expiry disabled")
        return report

    query = db.query(AdminAccessLogDB).filter(
        AdminAccessLogDB.created_at < cutoff.replace(tzinfo=None)
    )
    if dry_run:
        report.audit_entries_purged = query.count()
        return report

    report.audit_entries_purged = query.delete()
    if report.audit_entries_purged:
        db.commit()
    return report


def delete_inactive_accounts(
    db: Session,
    months: Optional[int] = None,
    dry_run: bool = False,
    limit: int = 500,
) -> RetentionReport:
    """Delete accounts with no sign-in and no submission for the whole period.

    Purging submissions is not enough on its own: an emptied account still holds
    a child's Google id, e-mail and name indefinitely.

    "Activity" is the later of UserDB.updated_at (refreshed by
    UserRepository.create_or_update on every OAuth login) and the newest
    submission timestamp. The login stamp alone would be misleading, because a
    session lasts 30 days and a student can keep submitting without signing in
    again.

    Skips the "anonymous" dev account and anyone listed in ADMIN_EMAILS - losing
    an operator account to inactivity would be a self-inflicted outage.

    ``limit`` caps how many accounts one run erases. Each erasure is its own
    transaction plus a directory walk, so the first run after enabling retention
    on an old database could otherwise take hours; the remainder is picked up by
    the next daily run.
    """
    report = RetentionReport(dry_run=dry_run)
    months = settings.retention_inactive_account_months if months is None else months
    cutoff = _cutoff_from_months(months)
    if cutoff is None:
        logger.info("Retention: inactive account expiry disabled")
        return report

    naive_cutoff = cutoff.replace(tzinfo=None)

    admin_emails = {
        e.strip().lower()
        for e in (settings.admin_emails or "").split(",")
        if e.strip()
    }

    last_submission = (
        db.query(
            SubmissionDB.user_id.label("user_id"),
            func.max(SubmissionDB.timestamp).label("last_submission_at"),
        )
        .group_by(SubmissionDB.user_id)
        .subquery()
    )

    candidates = (
        db.query(UserDB)
        .outerjoin(last_submission, UserDB.google_sub == last_submission.c.user_id)
        .filter(
            UserDB.updated_at < naive_cutoff,
            (last_submission.c.last_submission_at.is_(None))
            | (last_submission.c.last_submission_at < naive_cutoff),
        )
        .order_by(UserDB.updated_at)
        .limit(limit)
        .all()
    )

    for user in candidates:
        if user.google_sub == "anonymous":
            continue
        if (user.email or "").lower() in admin_emails:
            continue

        if dry_run:
            # Count the files without touching them or the row
            report.merge(erase_user_data(db, user.google_sub, dry_run=True))
            report.accounts_deleted += 1
            # erase_user_data counts submissions too; that is what we want in
            # the combined report, but the account itself is the headline number
            continue

        logger.info(
            f"Retention: deleting inactive account {mask_user_id(user.google_sub)} "
            f"(last activity before {naive_cutoff})"
        )
        report.merge(erase_user_data(db, user.google_sub))
        report.accounts_deleted += 1

    return report


def run_retention(db: Session, dry_run: bool = False) -> RetentionReport:
    """Run every retention pass and return the combined report."""
    report = RetentionReport(dry_run=dry_run)
    report.merge(purge_expired_submissions(db, dry_run=dry_run))
    report.merge(strip_expired_scoring_thinking(db, dry_run=dry_run))
    # After the purge, so files freed above are not re-scanned as orphans
    report.merge(sweep_orphan_upload_files(db, dry_run=dry_run))
    report.merge(purge_expired_quota_tombstones(db, dry_run=dry_run))
    report.merge(purge_expired_admin_audit(db, dry_run=dry_run))
    # Last: it deletes whole accounts, so it should see the state the passes
    # above left behind rather than racing them
    report.merge(delete_inactive_accounts(db, dry_run=dry_run))
    report.dry_run = dry_run
    logger.info(report.summary())
    return report


# --- Right to erasure (RODO art. 17) ----------------------------------------


def erase_user_data(db: Session, user_id: str, dry_run: bool = False) -> RetentionReport:
    """Delete a user, all their submissions and all their uploaded photos.

    ``UserDB.submissions`` cascades, so the rows go with the user - but the ORM
    knows nothing about the filesystem, so the photos have to be removed here.
    """
    report = RetentionReport(dry_run=dry_run)

    submissions = (
        db.query(SubmissionDB).filter(SubmissionDB.user_id == user_id).all()
    )
    # Read the paths out before the rows are gone
    image_paths = [path for s in submissions for path in (s.images or [])]
    report.submissions_deleted = len(submissions)

    # Rows first, files second. If the commit fails the user keeps a consistent
    # account; if the unlinking fails afterwards the leftovers are picked up by
    # sweep_orphan_upload_files on the next retention run. The other order would
    # leave a live account whose photos are gone and nothing to repair it.
    if not dry_run:
        # Keep the accountability record that an admin looked at this data, but
        # not the identifier of the account that no longer exists.
        from .db.repositories import AdminAccessLogRepository

        AdminAccessLogRepository(db).pseudonymize_subject(user_id)

        user = db.query(UserDB).filter(UserDB.google_sub == user_id).first()
        if user:
            db.delete(user)  # cascade removes submissions
        else:
            # No user row (should not happen) - remove the submissions directly
            for submission in submissions:
                db.delete(submission)
        db.commit()

    delete_upload_files(image_paths, report, dry_run=dry_run)

    # Also sweep the user's upload directory: catches files whose submission row
    # was never created (failed upload) and leaves no orphans behind.
    delete_user_upload_tree(user_id, report, dry_run=dry_run)

    logger.info(
        f"Account erasure for user {mask_user_id(user_id)}: "
        f"{report.submissions_deleted} submissions, {report.files_deleted} files "
        f"({report.megabytes_freed} MB){' [DRY RUN]' if dry_run else ''}"
    )
    return report
