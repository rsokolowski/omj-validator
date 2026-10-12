"""Authentication: sessions (Google or login + password) and the account guard."""

import time
from typing import Optional

from fastapi import Depends, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection

from .config import settings
from .db import get_db
from .db.models import UserDB, UserStatus

# Session key for storing user info
SESSION_USER_KEY = "user"

# Re-check group membership every 5 minutes (in seconds)
MEMBERSHIP_RECHECK_INTERVAL = 5 * 60


async def _refresh_group_membership_if_needed(request: Request) -> None:
    """
    Re-check group membership if the last check was too long ago.
    Updates the session with the new membership status.
    """
    user = request.session.get(SESSION_USER_KEY)
    if not user:
        return

    # Check when we last verified membership
    last_check = user.get("membership_checked_at", 0)
    now = time.time()

    if now - last_check < MEMBERSHIP_RECHECK_INTERVAL:
        return  # Recent check, no need to re-verify

    # Re-check group membership
    from .groups import check_group_membership
    email = user.get("email")
    if not email:
        return

    import logging
    logger = logging.getLogger(__name__)
    try:
        is_member = await check_group_membership(email)
        user["is_group_member"] = is_member
        user["membership_checked_at"] = now
        request.session[SESSION_USER_KEY] = user
    except Exception as e:
        # On error, keep existing membership status but don't update timestamp
        # This will cause a retry on the next request
        logger.debug(f"Group membership refresh failed, will retry: {e}")


# Session lifetimes. Starlette's cookie lives 30 days (SessionMiddleware
# max_age); a session started without "Zapamiętaj mnie" carries its own,
# shorter expiry, checked on every read.
REMEMBER_SESSION_SECONDS = 30 * 24 * 60 * 60
SHORT_SESSION_SECONDS = 12 * 60 * 60

# Registration answers stored before the Google redirect, and a Google
# identity waiting for its registration to be finished (both 30 minutes)
SESSION_PENDING_REGISTRATION_KEY = "pending_registration"
SESSION_PENDING_GOOGLE_KEY = "pending_google"
PENDING_SESSION_SECONDS = 30 * 60


def start_session(
    request: Request,
    user,
    *,
    remember: bool,
    is_group_member: bool,
    picture: Optional[str] = None,
) -> dict:
    """Log ``user`` (a UserDB row) in: replace whatever the session held."""
    now = time.time()
    request.session.clear()
    session_user = {
        "user_id": user.id,
        "session_version": user.session_version or 0,
        "expires_at": now + (REMEMBER_SESSION_SECONDS if remember else SHORT_SESSION_SECONDS),
        "email": user.email,
        "login": user.login,
        "name": user.name or user.login or "",
        "picture": picture,
        "is_group_member": is_group_member,
        "membership_checked_at": now,
    }
    request.session[SESSION_USER_KEY] = session_user
    return session_user


def get_current_user(request: Request) -> Optional[dict]:
    """
    Get current user from session.

    Returns:
        User dict with keys: user_id, session_version, expires_at, email
        (None for login accounts), login, name, picture, is_group_member.
        None if not authenticated or the session expired.

    A session started before login accounts existed carries ``google_sub``
    instead of ``user_id``. For those users ``users.id`` equals the Google
    sub, so it is read as the id and the session is rewritten in place -
    nobody is logged out by the deploy.
    """
    # Auth disabled = anonymous user with full access
    if settings.auth_disabled:
        return {
            "user_id": "anonymous",
            "email": "anonymous@localhost",
            "login": None,
            "name": "Anonymous (auth disabled)",
            "picture": None,
            "is_group_member": True,
        }

    user = request.session.get(SESSION_USER_KEY)
    if not user:
        return None

    if not user.get("user_id"):
        legacy_id = user.get("google_sub")
        if not legacy_id:
            request.session.pop(SESSION_USER_KEY, None)
            return None
        user = {key: value for key, value in user.items() if key != "google_sub"}
        user["user_id"] = legacy_id
        user.setdefault("session_version", 0)
        user.setdefault("login", None)
        user["expires_at"] = time.time() + REMEMBER_SESSION_SECONDS
        request.session[SESSION_USER_KEY] = user

    expires_at = user.get("expires_at")
    if expires_at is not None and time.time() > expires_at:
        request.session.pop(SESSION_USER_KEY, None)
        return None

    return user


def get_current_user_id(request: Request) -> Optional[str]:
    """
    Get the id (``users.id``) of the current user.

    Returns:
        User id string if authenticated, None otherwise
    """
    user = get_current_user(request)
    if user:
        return user.get("user_id")
    return None


def is_group_member(request: Request) -> bool:
    """
    Check if the current user is a member of the required group.

    Note: This is the sync version - use is_group_member_async for routes
    that can refresh membership status.

    Returns:
        True if user is authenticated AND is a group member
        False otherwise
    """
    user = get_current_user(request)
    if not user:
        return False
    return user.get("is_group_member", False)


async def is_group_member_async(request: Request) -> bool:
    """
    Check if the current user is a member of the required group.

    This async version will refresh membership status if needed (every 5 min).
    Use this in async route handlers for up-to-date membership checking.

    Returns:
        True if user is authenticated AND is a group member
        False otherwise
    """
    # First refresh membership if needed
    await _refresh_group_membership_if_needed(request)

    # Then check the (possibly updated) membership status
    user = get_current_user(request)
    if not user:
        return False
    return user.get("is_group_member", False)


def verify_auth(request: Request) -> bool:
    """
    Check if request has valid authentication.

    For backward compatibility with existing code that checks is_authenticated.
    Returns True if user is logged in (regardless of group membership).
    """
    if settings.auth_disabled:
        return True
    return get_current_user(request) is not None


def require_auth(request: Request) -> None:
    """Raise exception if not authenticated."""
    if not verify_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieautoryzowany dostęp",
        )


def require_auth_redirect(request: Request) -> Optional[RedirectResponse]:
    """Return redirect to login if not authenticated, None otherwise."""
    if not verify_auth(request):
        # Include the current URL as 'next' parameter so user returns after login
        from urllib.parse import urlencode
        next_url = str(request.url.path)
        if request.url.query:
            next_url += f"?{request.url.query}"
        login_url = f"/login?{urlencode({'next': next_url})}"
        return RedirectResponse(url=login_url, status_code=status.HTTP_303_SEE_OTHER)
    return None


def require_group_member(request: Request) -> None:
    """
    Raise exception if not authenticated or not a group member.

    Use this for routes that require full access (e.g., submitting solutions).
    """
    if not verify_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieautoryzowany dostęp",
        )

    if not is_group_member(request):
        from .config import settings
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Dostęp wymaga członkostwa w grupie {settings.google_group_email}",
        )


def require_group_member_redirect(request: Request) -> Optional[RedirectResponse]:
    """
    Return redirect if not authenticated or not a group member.

    For HTML routes - redirects to login or shows limited access page.
    """
    if not verify_auth(request):
        # Include the current URL as 'next' parameter so user returns after login
        from urllib.parse import urlencode
        next_url = str(request.url.path)
        if request.url.query:
            next_url += f"?{request.url.query}"
        login_url = f"/login?{urlencode({'next': next_url})}"
        return RedirectResponse(url=login_url, status_code=status.HTTP_303_SEE_OTHER)

    if not is_group_member(request):
        return RedirectResponse(url="/auth/limited", status_code=status.HTTP_303_SEE_OTHER)

    return None


# --- Account state (DB) and the guard on write endpoints --------------------

# Codes the frontend reacts to (403 bodies carry {"detail", "code"})
CODE_PARENT_CONSENT_PENDING = "parent_consent_pending"
CODE_PROFILE_INCOMPLETE = "profile_incomplete"

PARENT_CONSENT_PENDING_MESSAGE = (
    "Twoje konto czeka na zgodę rodzica. Do tego czasu możesz przeglądać zadania, "
    "ale nie możesz przesyłać rozwiązań ani niczego zapisywać."
)
PROFILE_INCOMPLETE_MESSAGE = "Uzupełnij rok urodzenia, żeby korzystać ze wszystkich funkcji."

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_ALLOW_INACTIVE_ATTR = "__allow_inactive_account__"


class AccountInactiveError(Exception):
    """Raised by the guard; app/main.py turns it into 403 {"detail", "code"}."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def allow_inactive_account(endpoint):
    """Mark a write endpoint a pending / incomplete account may still call.

    Put it UNDER the route decorator. Only for the account's own lifecycle:
    finishing registration, the parent e-mail, deleting the account, logging
    in and out, token-based parent pages.
    """
    setattr(endpoint, _ALLOW_INACTIVE_ATTR, True)
    return endpoint


def current_account(conn: HTTPConnection, db: Session = Depends(get_db)) -> Optional[UserDB]:
    """The signed-in user's row, or None (anonymous, dev mode, stale session).

    Runs for every request (app-level dependency). A session whose user no
    longer exists (erased by a parent, retention, self-deletion) or whose
    session_version is older than the row's (password reset) is cleared here,
    so it cannot be used for anything afterwards.
    """
    if settings.auth_disabled:
        return None
    user = get_current_user(conn)  # type: ignore[arg-type] - only .session is used
    if not user:
        return None
    row = db.get(UserDB, user["user_id"])
    if row is None or (row.session_version or 0) != (user.get("session_version") or 0):
        conn.session.pop(SESSION_USER_KEY, None)
        return None
    return row


def account_block_reason(account: Optional[UserDB]) -> Optional[AccountInactiveError]:
    """Why this account may not write, or None when it may."""
    if account is None:
        return None
    if account.birth_year is None:
        return AccountInactiveError(CODE_PROFILE_INCOMPLETE, PROFILE_INCOMPLETE_MESSAGE)
    if account.status != UserStatus.ACTIVE:
        return AccountInactiveError(CODE_PARENT_CONSENT_PENDING, PARENT_CONSENT_PENDING_MESSAGE)
    return None


def require_active_user(
    conn: HTTPConnection,
    account: Optional[UserDB] = Depends(current_account),
) -> None:
    """App-level guard: a pending or incomplete account cannot write.

    Applied to every route through ``FastAPI(dependencies=...)``, so a new
    endpoint cannot forget it. Reads (GET/HEAD/OPTIONS) and WebSockets pass;
    endpoints marked with @allow_inactive_account pass. Anonymous requests
    pass too - the endpoint's own authentication answers 401.
    """
    if conn.scope.get("type") != "http" or conn.scope.get("method") in _SAFE_METHODS:
        return
    if getattr(conn.scope.get("endpoint"), _ALLOW_INACTIVE_ATTR, False):
        return
    reason = account_block_reason(account)
    if reason is not None:
        raise reason
