"""Filesystem layout, drafts and AI rate limits for private tasks."""

import logging
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db.models import PrivateTaskDB
from ..db.private_tasks import AIUsageRepository
from ..db.repositories import DeletedAccountQuotaRepository
from ..rate_limits import calculate_rate_limit_headers, calculate_retry_after
from ..retention import (
    PRIVATE_DRAFTS_DIR,
    PRIVATE_UPLOAD_DIR,
    RetentionReport,
    delete_private_task_files,
)

logger = logging.getLogger(__name__)

TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{12}$")
DRAFT_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
# An unconfirmed draft is usable this long; the orphan sweep removes it after
# the same period (retention.ORPHAN_GRACE_HOURS)
DRAFT_TTL_SECONDS = 24 * 3600


def new_draft_id() -> str:
    return uuid.uuid4().hex[:16]


def private_root(user_id: str) -> Path:
    return settings.uploads_dir / user_id / PRIVATE_UPLOAD_DIR


def task_dir(user_id: str, task_id: str) -> Path:
    return private_root(user_id) / task_id


def draft_dir(user_id: str, draft_id: str) -> Path:
    return private_root(user_id) / PRIVATE_DRAFTS_DIR / draft_id


def relative_upload_path(path: Path) -> str:
    return str(path.relative_to(settings.uploads_dir))


def draft_photos(user_id: str, draft_id: str) -> Optional[list[Path]]:
    """Photos of a usable draft, or None when it is missing, empty or expired.

    The draft lives under the caller's own upload directory, so another user's
    draft id simply does not exist for them.
    """
    if not DRAFT_ID_PATTERN.match(draft_id or ""):
        return None
    directory = draft_dir(user_id, draft_id)
    if not directory.is_dir():
        return None
    photos = sorted(p for p in directory.iterdir() if p.is_file())
    if not photos:
        return None
    newest = max(p.stat().st_mtime for p in photos)
    if time.time() - newest > DRAFT_TTL_SECONDS:
        return None
    return photos


def claim_draft(user_id: str, draft_id: str) -> Optional[tuple[Path, list[Path]]]:
    """Take a usable draft for exclusive use: (claimed_dir, photos) or None.

    The claim is an atomic rename, so of two requests confirming the same draft
    exactly one gets it - the other sees it gone (410) instead of copying photos
    out from under the winner. A crash leaves the claimed directory under
    _drafts/, where the orphan sweep removes it like any stale draft.
    """
    if draft_photos(user_id, draft_id) is None:
        return None
    source = draft_dir(user_id, draft_id)
    claimed = source.with_name(f"{draft_id}.claimed-{uuid.uuid4().hex[:8]}")
    try:
        source.rename(claimed)
    except OSError:
        return None  # someone else claimed it first
    return claimed, sorted(p for p in claimed.iterdir() if p.is_file())


def release_draft(claimed: Path, user_id: str, draft_id: str) -> None:
    """Give a claimed draft back after a refused confirmation (student may retry)."""
    try:
        claimed.rename(draft_dir(user_id, draft_id))
    except OSError:
        shutil.rmtree(claimed, ignore_errors=True)


def discard_claimed_draft(claimed: Path) -> None:
    shutil.rmtree(claimed, ignore_errors=True)


def discard_draft(user_id: str, draft_id: str) -> None:
    if not DRAFT_ID_PATTERN.match(draft_id or ""):
        return
    shutil.rmtree(draft_dir(user_id, draft_id), ignore_errors=True)


def copy_photos_to_task(photos: list[Path], user_id: str, task_id: str) -> list[str]:
    """Give a task its own copy of the problem photos (relative paths).

    Copies, not links: deleting one task created from a multi-problem photo must
    never take the photos of its siblings with it.
    """
    target = task_dir(user_id, task_id) / "source"
    target.mkdir(parents=True, exist_ok=True)
    stored = []
    for photo in photos:
        destination = target / photo.name
        shutil.copyfile(photo, destination)
        stored.append(relative_upload_path(destination))
    return stored


def delete_task_files(task: PrivateTaskDB) -> RetentionReport:
    report = RetentionReport()
    delete_private_task_files(task.user_id, task.id, report)
    return report


def check_ai_limit(
    db: Session,
    user_id: str,
    kinds: set[str],
    per_user_limit: int,
    is_allowlisted: bool,
    cost: int = 1,
) -> None:
    """Raise 429 when ``cost`` more AI calls of ``kinds`` would exceed a limit.

    Counts the user's calls of these kinds in the last 24h plus AI usage carried
    over from an erased account, and every user's calls against the global cap.
    Allowlisted users are never limited.
    """
    if is_allowlisted:
        return

    usage = AIUsageRepository(db)
    count, oldest = usage.user_window(user_id, kinds)
    count += DeletedAccountQuotaRepository(db).get_user_ai_usage_carryover(user_id)
    if count + cost > per_user_limit:
        logger.warning(f"Private task AI limit reached ({count}/{per_user_limit}, kinds={sorted(kinds)})")
        headers = calculate_rate_limit_headers(per_user_limit, count, oldest)
        headers["Retry-After"] = str(calculate_retry_after(oldest))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Osiągnięto dzienny limit ({per_user_limit}). "
                "Spróbuj ponownie jutro."
            ),
            headers=headers,
        )

    global_count, global_oldest = usage.global_window()
    global_limit = settings.rate_limit_ai_usage_global_per_day
    if global_count + cost > global_limit:
        logger.warning(f"Global private task AI limit reached ({global_count}/{global_limit})")
        headers = calculate_rate_limit_headers(global_limit, global_count, global_oldest)
        headers["Retry-After"] = str(calculate_retry_after(global_oldest))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="System osiągnął dzienny limit. Spróbuj ponownie później.",
            headers=headers,
        )
