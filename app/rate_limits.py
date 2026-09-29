"""Rolling 24h rate limits for AI-backed endpoints.

Every endpoint that triggers a paid Gemini call is capped per user and
globally. Submissions are counted from the submissions table; the calls made
while creating private tasks are counted from ai_usage. Quota used by an
account that was erased is carried over (see DeletedAccountQuotaDB), so
deleting the account is never a way to reset it.
"""

from datetime import datetime as dt_datetime, timezone as dt_timezone, timedelta as dt_timedelta
from typing import Optional as OptionalType

from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .config import settings
from .db import DeletedAccountQuotaRepository, SubmissionRepository
from .db.repositories import ensure_utc
from .privacy import mask_user_id

import logging

logger = logging.getLogger(__name__)

def calculate_rate_limit_headers(
    limit: int,
    current_count: int,
    oldest_timestamp: OptionalType[dt_datetime],
    window_hours: int = 24,
) -> dict[str, str]:
    """Calculate standard rate limit headers.

    Args:
        limit: Maximum allowed requests in the window
        current_count: Current number of requests in the window
        oldest_timestamp: Timestamp of the oldest request in the window (for reset calculation)
        window_hours: Duration of the rolling window in hours

    Returns:
        Dict with standard rate limit headers:
        - X-RateLimit-Limit: Maximum requests allowed
        - X-RateLimit-Remaining: Remaining requests in current window
        - X-RateLimit-Reset: Unix timestamp when oldest request expires from window
    """
    remaining = max(0, limit - current_count)

    # Ensure timestamp is timezone-aware (using shared utility)
    oldest_timestamp = ensure_utc(oldest_timestamp)

    # Calculate reset time: when the oldest item in the window ages out
    if oldest_timestamp:
        # If we have items in window, reset when oldest expires
        reset_time = oldest_timestamp + dt_timedelta(hours=window_hours)
    else:
        # No items in window, reset is 24h from now (window is empty)
        reset_time = dt_datetime.now(dt_timezone.utc) + dt_timedelta(hours=window_hours)

    reset_unix = int(reset_time.timestamp())

    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_unix),
    }


def rate_limit_reset_anchor(
    live_timestamps: list[dt_datetime],
    carryover_blocks: list[tuple[int, dt_datetime]],
    limit: int,
    window_hours: int = 24,
) -> OptionalType[dt_datetime]:
    """Anchor to feed the header helpers when a deleted-account carryover exists.

    The helpers below all compute `anchor + window`, which normally means "the
    oldest request leaves the window". That breaks once a carryover is in play:
    the carried-over quota is one block released at its tombstone's expires_at,
    so taking the oldest submission behind it points at a moment when nothing
    frees. A user with 30 submissions between T-23h and T-1h who deletes their
    account and signs back in would be told to retry in an hour - and get 429
    again, every hour, for 22 hours.

    So the moment the caller can actually submit again is computed by replaying
    the releases in order: each live submission frees one slot at
    `timestamp + window`, each tombstone frees its whole count at `expires_at`.
    The first moment the total drops below the limit is the answer, and the
    anchor returned is that moment minus the window, so the existing
    `anchor + window` arithmetic lands exactly on it.

    Returns None when nothing is counted, which leaves the callers' "no items in
    window" behaviour untouched.
    """
    releases: list[tuple[dt_datetime, int]] = [
        (ensure_utc(ts) + dt_timedelta(hours=window_hours), 1) for ts in live_timestamps
    ]
    releases += [
        (ensure_utc(expires_at), count)
        for count, expires_at in carryover_blocks
        if expires_at and count > 0
    ]
    if not releases:
        return None

    releases.sort(key=lambda item: item[0])
    remaining = len(live_timestamps) + sum(
        count for count, expires_at in carryover_blocks if expires_at and count > 0
    )

    for when, freed in releases:
        remaining -= freed
        if remaining < limit:
            return when - dt_timedelta(hours=window_hours)

    # Below the limit only once everything has gone
    return releases[-1][0] - dt_timedelta(hours=window_hours)


def calculate_retry_after(
    oldest_timestamp: OptionalType[dt_datetime], window_hours: int = 24
) -> int:
    """Calculate Retry-After header value in seconds.

    Args:
        oldest_timestamp: Timestamp of the oldest request in the window
        window_hours: Duration of the rolling window in hours

    Returns:
        Seconds until the rate limit resets (minimum 1 second)
    """
    # Ensure timestamp is timezone-aware (using shared utility)
    oldest_timestamp = ensure_utc(oldest_timestamp)

    if oldest_timestamp:
        reset_time = oldest_timestamp + dt_timedelta(hours=window_hours)
    else:
        reset_time = dt_datetime.now(dt_timezone.utc) + dt_timedelta(hours=window_hours)

    retry_after = int((reset_time - dt_datetime.now(dt_timezone.utc)).total_seconds())
    return max(1, retry_after)


def check_submission_limits(
    db: Session,
    user_id: str,
    is_allowlisted: bool,
) -> tuple[OptionalType[JSONResponse], dict[str, str], int, OptionalType[dt_datetime]]:
    """Per-user and global daily submission limits (OMJ and private tasks alike).

    Returns (error_response_or_None, rate_limit_headers, user_count, user_anchor).
    ``user_count`` / ``user_anchor`` let the caller report the headers again
    after it has created the submission. Allowlisted users are never refused,
    but still get informational headers.
    """
    submission_repo = SubmissionRepository(db)

    # Track rate limit info for headers (even if allowlisted, for informational purposes)
    user_submission_count, user_oldest_submission = submission_repo.get_user_rate_limit_info(
        user_id, hours=24
    )

    # Quota already used by an account this person erased inside the window.
    # Without this, deleting the account would hand out a fresh daily budget -
    # see DeletedAccountQuotaDB.
    quota_repo = DeletedAccountQuotaRepository(db)
    carryover_count, carryover_expires_at = quota_repo.get_user_carryover(user_id)
    user_submission_count += carryover_count
    if carryover_count and carryover_expires_at:
        # Reset/Retry-After must point at a moment when quota actually frees;
        # the carried-over block is released in one go at expires_at, so the
        # anchor is computed from the real release schedule.
        user_oldest_submission = rate_limit_reset_anchor(
            submission_repo.get_user_submission_timestamps(user_id, hours=24),
            [(carryover_count, carryover_expires_at)],
            limit=settings.rate_limit_submissions_per_user_per_day,
            window_hours=24,
        ) or user_oldest_submission
    rate_limit_headers = calculate_rate_limit_headers(
        limit=settings.rate_limit_submissions_per_user_per_day,
        current_count=user_submission_count,
        oldest_timestamp=user_oldest_submission,
        window_hours=24,
    )

    if is_allowlisted:
        return None, rate_limit_headers, user_submission_count, user_oldest_submission

    # Check per-user submission limit
    if user_submission_count >= settings.rate_limit_submissions_per_user_per_day:
        logger.warning(
            f"User submission rate limit exceeded: {mask_user_id(user_id)} "
            f"{user_submission_count}/{settings.rate_limit_submissions_per_user_per_day}"
        )
        retry_after = calculate_retry_after(user_oldest_submission, window_hours=24)
        return (
            JSONResponse(
                {
                    "error": f"Osiągnięto dzienny limit zgłoszeń ({settings.rate_limit_submissions_per_user_per_day}). "
                    "Możesz przesłać więcej rozwiązań jutro."
                },
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={**rate_limit_headers, "Retry-After": str(retry_after)},
            ),
            rate_limit_headers,
            user_submission_count,
            user_oldest_submission,
        )

    # Check global submission limit
    global_submission_count, global_oldest_submission = submission_repo.get_global_rate_limit_info(
        hours=24
    )
    # Erased accounts also freed global quota - count it back
    carryover_blocks = quota_repo.get_global_carryover_blocks()
    global_submission_count += sum(count for count, _ in carryover_blocks)
    if carryover_blocks:
        # Same reasoning as the per-user branch above
        global_oldest_submission = rate_limit_reset_anchor(
            submission_repo.get_all_submission_timestamps(hours=24),
            carryover_blocks,
            limit=settings.rate_limit_submissions_global_per_day,
            window_hours=24,
        ) or global_oldest_submission
    if global_submission_count >= settings.rate_limit_submissions_global_per_day:
        logger.warning(
            f"Global submission rate limit exceeded: {global_submission_count}/{settings.rate_limit_submissions_global_per_day}"
        )
        global_rate_headers = calculate_rate_limit_headers(
            limit=settings.rate_limit_submissions_global_per_day,
            current_count=global_submission_count,
            oldest_timestamp=global_oldest_submission,
            window_hours=24,
        )
        retry_after = calculate_retry_after(global_oldest_submission, window_hours=24)
        return (
            JSONResponse(
                {"error": "System osiągnął dzienny limit zgłoszeń. Spróbuj ponownie później."},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={**global_rate_headers, "Retry-After": str(retry_after)},
            ),
            rate_limit_headers,
            user_submission_count,
            user_oldest_submission,
        )

    return None, rate_limit_headers, user_submission_count, user_oldest_submission
