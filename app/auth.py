import secrets
import hashlib
import hmac

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

from .config import settings

AUTH_COOKIE_NAME = "omj_auth"
# Session token is derived from auth_key - changes when key changes
_SESSION_TOKEN = None


def _get_session_token() -> str:
    """Get or create a session token derived from the auth key."""
    global _SESSION_TOKEN
    if _SESSION_TOKEN is None:
        # Derive a fixed session token from the auth key
        _SESSION_TOKEN = hashlib.sha256(
            f"omj_session_{settings.auth_key}".encode()
        ).hexdigest()
    return _SESSION_TOKEN


def verify_auth(request: Request) -> bool:
    """Check if request has valid authentication."""
    expected_token = _get_session_token()

    # Check cookie (contains derived token, not raw key)
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_token and hmac.compare_digest(cookie_token, expected_token):
        return True

    # Check header (for API calls) - accepts raw key for backward compat
    header_token = request.headers.get("X-Auth-Token")
    if header_token and secrets.compare_digest(header_token, settings.auth_key):
        return True

    return False


def require_auth(request: Request) -> None:
    """Raise exception if not authenticated."""
    if not verify_auth(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieautoryzowany dostęp",
        )


def require_auth_redirect(request: Request) -> RedirectResponse | None:
    """Return redirect to login if not authenticated, None otherwise."""
    if not verify_auth(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return None
