"""Authentication module using Google OAuth sessions."""

from typing import Optional

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

from .config import settings

# Session key for storing user info
SESSION_USER_KEY = "user"


def get_current_user(request: Request) -> Optional[dict]:
    """
    Get current user from session.

    Returns:
        User dict with keys: email, name, picture, is_group_member
        None if not authenticated
    """
    # Auth disabled = anonymous user with full access
    if settings.auth_disabled:
        return {
            "email": "anonymous@localhost",
            "name": "Anonymous (auth disabled)",
            "picture": None,
            "is_group_member": True,
        }

    return request.session.get(SESSION_USER_KEY)


def is_group_member(request: Request) -> bool:
    """
    Check if the current user is a member of the required group.

    Returns:
        True if user is authenticated AND is a group member
        False otherwise
    """
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
