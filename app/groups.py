"""Access control: Email allowlist or Google Groups API membership checking."""

import asyncio
import json
import logging
import threading
from typing import Optional, Set

from cachetools import TTLCache

from .config import settings

logger = logging.getLogger(__name__)


def _get_allowed_emails() -> Set[str]:
    """Parse comma-separated ALLOWED_EMAILS into a set of lowercase emails."""
    if not settings.allowed_emails:
        return set()
    return {email.strip().lower() for email in settings.allowed_emails.split(",") if email.strip()}

# Thread-safe TTL cache for group membership (5 minute TTL, max 256 entries)
_membership_cache = TTLCache(maxsize=256, ttl=300)
_cache_lock = threading.Lock()


def _get_credentials():
    """Load service account credentials from config."""
    if not settings.google_service_account_json:
        return None

    try:
        from google.oauth2 import service_account

        SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"]

        # Support both inline JSON and file path
        if settings.google_service_account_json.strip().startswith("{"):
            creds_info = json.loads(settings.google_service_account_json)
            return service_account.Credentials.from_service_account_info(
                creds_info, scopes=SCOPES
            )
        else:
            return service_account.Credentials.from_service_account_file(
                settings.google_service_account_json, scopes=SCOPES
            )
    except Exception as e:
        logger.error(f"Failed to load service account credentials: {e}")
        return None


def _check_membership_impl(user_email: str, group_email: str) -> bool:
    """Actually check group membership via API (no caching)."""
    credentials = _get_credentials()
    if not credentials:
        logger.warning("No service account configured - cannot check group membership")
        return False

    try:
        from googleapiclient.discovery import build

        service = build("admin", "directory_v1", credentials=credentials)

        # Use hasMember API - most efficient for single membership check
        result = service.members().hasMember(
            groupKey=group_email,
            memberKey=user_email,
        ).execute()

        is_member = result.get("isMember", False)
        logger.info(f"Group membership check: {user_email[:3]}***@*** = {is_member}")
        return is_member

    except Exception as e:
        # Log the error but don't crash - default to not a member
        # Don't cache errors - they should be retried
        logger.error(f"Error checking group membership: {type(e).__name__}: {e}")
        raise  # Re-raise so we don't cache the error


def _check_membership_cached(user_email: str, group_email: str) -> bool:
    """Check group membership with TTL caching (5 minutes)."""
    cache_key = f"{user_email}:{group_email}"

    with _cache_lock:
        if cache_key in _membership_cache:
            return _membership_cache[cache_key]

    try:
        result = _check_membership_impl(user_email, group_email)
        with _cache_lock:
            _membership_cache[cache_key] = result
        return result
    except Exception:
        # On error, don't cache - return False but allow retry
        return False


async def check_group_membership(user_email: str, group_email: Optional[str] = None) -> bool:
    """
    Check if user has access (via allowlist or Google Group membership).

    Checks in order:
    1. Email allowlist (ALLOWED_EMAILS env var) - instant, no API call
    2. Google Groups API (if service account configured) - requires Domain-Wide Delegation

    Args:
        user_email: The user's email address
        group_email: The group email for API check (defaults to settings.google_group_email)

    Returns:
        True if user is allowed, False otherwise
    """
    email_lower = user_email.lower()

    # Method 1: Check email allowlist (fastest, no API needed)
    allowed_emails = _get_allowed_emails()
    if allowed_emails:
        if email_lower in allowed_emails:
            logger.info(f"Access granted via allowlist: {email_lower[:3]}***@***")
            return True
        # If allowlist is configured but user not in it, deny immediately
        # (don't fall through to Google Groups API)
        logger.info(f"Access denied - not in allowlist: {email_lower[:3]}***@***")
        return False

    # Method 2: Check Google Groups API (if service account configured)
    if settings.google_service_account_json:
        if group_email is None:
            group_email = settings.google_group_email

        # Run the sync API call in a thread pool to avoid blocking
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            _check_membership_cached,
            email_lower,
            group_email.lower(),
        )

    # No access control configured - deny by default for security
    logger.warning(
        "No access control configured (neither ALLOWED_EMAILS nor service account). "
        "Set ALLOWED_EMAILS or configure Google Groups API."
    )
    return False


def clear_membership_cache():
    """Clear the membership cache (useful for testing)."""
    with _cache_lock:
        _membership_cache.clear()
