"""Delete data past its retention period (RODO art. 5(1)(e) - storage limitation).

Removes expired submissions together with the photos of the student's work,
strips the verbatim AI "thinking" trace from older submissions, deletes upload
files that no submission references any more, expires the admin access audit
trail and deletes accounts that have been inactive for too long. Periods come
from settings (RETENTION_SUBMISSION_MONTHS, RETENTION_SCORING_THINKING_DAYS);
0 or unset disables that pass, which is what local dev wants.

Safe to run repeatedly and safe to interrupt - every pass is idempotent.

Usage:
    ./venv/bin/python scripts/purge_expired_data.py --dry-run
    ./venv/bin/python scripts/purge_expired_data.py
    ./venv/bin/python scripts/purge_expired_data.py --submission-months 12 \
        --thinking-days 30
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.retention import (  # noqa: E402
    ORPHAN_GRACE_HOURS,
    RetentionReport,
    delete_inactive_accounts,
    purge_expired_admin_audit,
    purge_expired_quota_tombstones,
    purge_expired_submissions,
    strip_expired_scoring_thinking,
    sweep_orphan_upload_files,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge data past its retention period")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be deleted; change nothing",
    )
    parser.add_argument(
        "--submission-months",
        type=int,
        default=None,
        help="Override RETENTION_SUBMISSION_MONTHS (0 = skip this pass)",
    )
    parser.add_argument(
        "--thinking-days",
        type=int,
        default=None,
        help="Override RETENTION_SCORING_THINKING_DAYS (0 = skip this pass)",
    )
    parser.add_argument(
        "--inactive-account-months",
        type=int,
        default=None,
        help="Override RETENTION_INACTIVE_ACCOUNT_MONTHS (0 = skip this pass)",
    )
    parser.add_argument(
        "--admin-audit-months",
        type=int,
        default=None,
        help="Override RETENTION_ADMIN_AUDIT_MONTHS (0 = skip this pass)",
    )
    parser.add_argument(
        "--max-accounts",
        type=int,
        default=500,
        help="Cap on inactive accounts erased in one run (rest go next run)",
    )
    parser.add_argument(
        "--skip-orphan-sweep",
        action="store_true",
        help="Do not look for upload files no submission references any more",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    months = (
        settings.retention_submission_months
        if args.submission_months is None
        else args.submission_months
    )
    thinking_days = (
        settings.retention_scoring_thinking_days
        if args.thinking_days is None
        else args.thinking_days
    )
    inactive_months = (
        settings.retention_inactive_account_months
        if args.inactive_account_months is None
        else args.inactive_account_months
    )
    audit_months = (
        settings.retention_admin_audit_months
        if args.admin_audit_months is None
        else args.admin_audit_months
    )

    print(
        f"Retention periods: submissions={months or 'disabled'} months, "
        f"thinking trace={thinking_days or 'disabled'} days, "
        f"inactive accounts={inactive_months or 'disabled'} months, "
        f"admin audit={audit_months or 'disabled'} months"
    )
    print(f"Uploads dir: {settings.uploads_dir}")
    if args.dry_run:
        print("DRY RUN - nothing will be deleted\n")

    db = SessionLocal()
    try:
        report = RetentionReport(dry_run=args.dry_run)
        report.merge(
            purge_expired_submissions(db, months=months, dry_run=args.dry_run)
        )
        report.merge(
            strip_expired_scoring_thinking(db, days=thinking_days, dry_run=args.dry_run)
        )
        report.merge(purge_expired_quota_tombstones(db, dry_run=args.dry_run))
        report.merge(
            purge_expired_admin_audit(db, months=audit_months, dry_run=args.dry_run)
        )
        if not args.skip_orphan_sweep:
            report.merge(
                sweep_orphan_upload_files(
                    db, grace_hours=ORPHAN_GRACE_HOURS, dry_run=args.dry_run
                )
            )
        # Last: deletes whole accounts, so it sees what the passes above left
        report.merge(
            delete_inactive_accounts(
                db,
                months=inactive_months,
                dry_run=args.dry_run,
                limit=args.max_accounts,
            )
        )
    finally:
        db.close()

    print()
    print(report.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
