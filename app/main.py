import logging
import re
import uuid
from pathlib import Path

# Configure logging to show INFO level for app modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)

import asyncio
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from fastapi import Depends
from sqlalchemy.orm import Session

from .config import settings
from .auth import (
    SESSION_USER_KEY,
    verify_auth,
    require_auth_redirect,
    get_current_user,
    get_current_user_id,
    is_group_member,
    is_group_member_async,
)
from .oauth import oauth
from .groups import check_group_membership, _get_allowed_emails
from .db import get_db, UserRepository, SubmissionRepository

logger = logging.getLogger(__name__)

# Track background tasks for proper lifecycle management
_background_tasks: set[asyncio.Task] = set()
from .storage import (
    get_available_years,
    get_etaps_for_year,
    get_tasks_for_etap,
    get_task,
    get_task_pdf_path,
    get_solution_pdf_path,
)
from .ai import create_ai_provider, AIProviderError
from .models import SubmissionResult, TaskCategory, TaskStatus
from .progress import build_progress_data, get_all_categories, get_prerequisite_statuses, compute_user_progress
from .skills import get_skills_by_ids

app = FastAPI(title="OMJ Validator", description="Walidator rozwiązań OMJ")

# Determine if we're in split deployment mode (frontend on different domain)
is_split_deployment = bool(settings.frontend_url)

# Add CORS middleware for split deployment (frontend on different domain)
if is_split_deployment:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

# Add session middleware for OAuth
# In split deployment, we need SameSite=None to allow cross-domain cookies
# SameSite=None requires Secure=True (https_only), which is enforced here
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    max_age=30 * 24 * 60 * 60,  # 30 days
    https_only=is_split_deployment or not settings.auth_disabled,  # HTTPS required for SameSite=None
    same_site="none" if is_split_deployment else "lax",  # Cross-domain requires "none"
)

# Mount static files
app.mount("/static", StaticFiles(directory=settings.base_dir / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=settings.base_dir / "templates")


# Custom template filter: escape HTML but preserve newlines
def nl2br_safe(value: str) -> str:
    """Escape HTML and convert newlines to <br> tags."""
    from markupsafe import Markup, escape
    escaped = escape(value)
    return Markup(str(escaped).replace("\n", "<br>\n"))


templates.env.filters["nl2br_safe"] = nl2br_safe


# Custom template filter: convert number to Roman numerals
def to_roman(num: int) -> str:
    """Convert an integer to Roman numerals."""
    if not isinstance(num, int) or num < 1:
        return str(num)

    roman_numerals = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")
    ]

    result = ""
    for arabic, roman in roman_numerals:
        count, num = divmod(num, arabic)
        result += roman * count
    return result


templates.env.filters["roman"] = to_roman


# --- Rate Limit Headers ---

from datetime import datetime as dt_datetime, timezone as dt_timezone, timedelta as dt_timedelta
from typing import Optional as OptionalType


def _ensure_timezone_aware(timestamp: OptionalType[dt_datetime]) -> OptionalType[dt_datetime]:
    """Ensure datetime is timezone-aware (UTC)."""
    if timestamp is None:
        return None
    if timestamp.tzinfo is None:
        # Naive datetime - assume it's UTC
        return timestamp.replace(tzinfo=dt_timezone.utc)
    return timestamp


def _calculate_rate_limit_headers(
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

    # Ensure timestamp is timezone-aware
    oldest_timestamp = _ensure_timezone_aware(oldest_timestamp)

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


def _calculate_retry_after(
    oldest_timestamp: OptionalType[dt_datetime], window_hours: int = 24
) -> int:
    """Calculate Retry-After header value in seconds.

    Args:
        oldest_timestamp: Timestamp of the oldest request in the window
        window_hours: Duration of the rolling window in hours

    Returns:
        Seconds until the rate limit resets (minimum 1 second)
    """
    # Ensure timestamp is timezone-aware
    oldest_timestamp = _ensure_timezone_aware(oldest_timestamp)

    if oldest_timestamp:
        reset_time = oldest_timestamp + dt_timedelta(hours=window_hours)
    else:
        reset_time = dt_datetime.now(dt_timezone.utc) + dt_timedelta(hours=window_hours)

    retry_after = int((reset_time - dt_datetime.now(dt_timezone.utc)).total_seconds())
    return max(1, retry_after)


# --- Startup Events ---

@app.on_event("startup")
def create_anonymous_user_if_needed():
    """Create anonymous user for local development when auth is disabled."""
    if not settings.auth_disabled:
        return

    from .db import SessionLocal, UserRepository

    db = SessionLocal()
    try:
        user_repo = UserRepository(db)
        existing = user_repo.get_by_google_sub("anonymous")
        if not existing:
            user_repo.create_or_update(
                google_sub="anonymous",
                email="anonymous@localhost",
                name="Anonymous (auth disabled)",
            )
            logger.info("Created anonymous user for local development")
    finally:
        db.close()


@app.on_event("startup")
async def start_cleanup_task():
    """Start periodic cleanup of stale progress entries."""
    from .websocket.progress import progress_manager

    async def cleanup_loop():
        while True:
            await asyncio.sleep(300)  # Run every 5 minutes
            try:
                await progress_manager.cleanup_stale()
            except Exception as e:
                logger.warning(f"Progress cleanup error: {e}")

    task = asyncio.create_task(cleanup_loop())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@app.on_event("startup")
def warm_ai_provider():
    """Initialize AI provider at startup to avoid latency on first request."""
    try:
        provider = create_ai_provider()
        logger.info(f"AI provider warmed up: {type(provider).__name__}")
    except Exception as e:
        logger.warning(f"Failed to warm AI provider: {e}")


# --- Authentication Routes ---


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = None):
    """Display login page with Google OAuth option."""
    if verify_auth(request):
        return RedirectResponse(url="/years", status_code=status.HTTP_303_SEE_OTHER)

    error_msg = None
    error_code = request.query_params.get("error")
    if error_code == "oauth_failed":
        error_msg = "Wystąpił błąd podczas logowania przez Google. Spróbuj ponownie."
    elif error_code == "oauth_not_configured":
        error_msg = "Logowanie przez Google nie jest skonfigurowane."
    elif error_code == "rate_limit_new_users":
        error_msg = "Osiągnięto dzienny limit nowych użytkowników. Spróbuj ponownie później."

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error_msg,
            "oauth_available": bool(settings.google_client_id),
            "next_url": next,
        },
    )


@app.get("/login/google")
async def google_login(request: Request, next: str = None):
    """Initiate Google OAuth flow."""
    if not settings.google_client_id:
        return RedirectResponse(
            url="/login?error=oauth_not_configured",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Store the return URL in session for after login
    if next:
        request.session["login_next"] = next

    # Use frontend URL for callback if configured (for separate frontend deployment)
    if settings.frontend_url:
        redirect_uri = f"{settings.frontend_url}/auth/callback"
    else:
        redirect_uri = request.url_for("google_auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def google_auth_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")

        if not user_info or "email" not in user_info:
            logger.error("OAuth callback: missing user info")
            return RedirectResponse(
                url="/login?error=oauth_failed",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        # Verify email is verified (defense in depth)
        if not user_info.get("email_verified", False):
            logger.error("OAuth callback: email not verified")
            return RedirectResponse(
                url="/login?error=oauth_failed",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        # Extract Google's unique user identifier
        google_sub = user_info.get("sub")
        if not google_sub:
            logger.error("OAuth callback: missing sub claim")
            return RedirectResponse(
                url="/login?error=oauth_failed",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        # Check rate limit for NEW user registrations
        user_repo = UserRepository(db)
        existing_user = user_repo.get_by_google_sub(google_sub)

        if not existing_user:
            # New user - check if they're in the allowlist (bypass rate limit)
            allowed_emails = _get_allowed_emails()
            user_email_lower = user_info["email"].lower()
            is_allowlisted = allowed_emails and user_email_lower in allowed_emails

            if not is_allowlisted:
                # Check rate limit for new users
                recent_users = user_repo.count_recent_users(hours=24)
                if recent_users >= settings.rate_limit_new_users_per_day:
                    logger.warning(
                        f"New user rate limit exceeded: {recent_users}/{settings.rate_limit_new_users_per_day} "
                        f"(blocked: {user_info['email'][:3]}***@***)"
                    )
                    return RedirectResponse(
                        url="/login?error=rate_limit_new_users",
                        status_code=status.HTTP_303_SEE_OTHER,
                    )

        # Create or update user in database
        user_repo.create_or_update(
            google_sub=google_sub,
            email=user_info["email"],
            name=user_info.get("name", ""),
        )

        # Check if user has full access (via public access, allowlist, or Google Groups)
        has_access = await check_group_membership(user_info["email"])

        # Check allowlist separately for logging (used for rate limit bypass)
        allowed_emails = _get_allowed_emails()
        is_allowlisted = allowed_emails and user_info["email"].lower() in allowed_emails

        # Get the return URL before modifying session
        next_url = request.session.pop("login_next", None)

        # Store user in session (including google_sub for user identification)
        import time
        request.session[SESSION_USER_KEY] = {
            "google_sub": google_sub,
            "email": user_info["email"],
            "name": user_info.get("name", ""),
            "picture": user_info.get("picture"),
            "is_group_member": has_access,
            "membership_checked_at": time.time(),  # Track when we last checked membership
        }

        logger.info(
            f"User logged in: {user_info['email']} (has_access: {has_access}, allowlisted: {is_allowlisted})"
        )

        # Redirect to the original page or default to /years
        # Validate that redirect URL is a safe relative path (prevent open redirect)
        redirect_url = "/years"
        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            redirect_url = next_url
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return RedirectResponse(
            url="/login?error=oauth_failed",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@app.get("/auth/limited", response_class=HTMLResponse)
async def auth_limited_page(request: Request):
    """Show limited access page for users not in the required group."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # If user is actually a group member, redirect to main page
    if user.get("is_group_member"):
        return RedirectResponse(url="/years", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "auth_limited.html",
        {"request": request, "user": user, "is_authenticated": True},
    )


@app.get("/logout")
async def logout(request: Request):
    """Log out user by clearing session."""
    request.session.clear()
    return RedirectResponse(url="/years", status_code=status.HTTP_303_SEE_OTHER)


# --- Main Routes ---


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect to years page."""
    return RedirectResponse(url="/years", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/years", response_class=HTMLResponse)
async def years_page(request: Request):
    """Display available years (public)."""
    years = get_available_years()
    user = get_current_user(request)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "years": years,
            "is_authenticated": user is not None,
            "user": user,
        },
    )


@app.get("/years/{year}", response_class=HTMLResponse)
async def year_detail(request: Request, year: str):
    """Display etaps for a year (public)."""
    etaps = get_etaps_for_year(year)
    if not etaps:
        raise HTTPException(status_code=404, detail="Rok nie znaleziony")

    user = get_current_user(request)

    return templates.TemplateResponse(
        "year.html",
        {
            "request": request,
            "year": year,
            "etaps": etaps,
            "is_authenticated": user is not None,
            "user": user,
        },
    )


# --- Progress Routes ---


@app.get("/progress", response_class=HTMLResponse)
async def progress_page(request: Request):
    """Display progression graph page (public view, progress shown to group members)."""
    user = get_current_user(request)
    # Use async version to refresh membership status if needed
    can_view_progress = await is_group_member_async(request)
    categories = get_all_categories()

    return templates.TemplateResponse(
        "progress.html",
        {
            "request": request,
            "is_authenticated": user is not None,
            "can_view_progress": can_view_progress,
            "user": user,
            "categories": categories,
        },
    )


@app.get("/api/progress/data")
async def progress_data(request: Request, category: str = None, db: Session = Depends(get_db)):
    """Get progression graph data as JSON.

    Query params:
        category: Optional category filter (algebra, geometria, etc.)

    Returns JSON with nodes, edges, recommendations, and stats.
    Progress tracking requires group membership; others see all tasks as unlocked.
    """
    user = get_current_user(request)
    user_id = get_current_user_id(request)
    # Use async version to refresh membership status if needed
    can_view_progress = await is_group_member_async(request)

    # Validate category if provided
    valid_categories = [c.value for c in TaskCategory]
    if category and category not in valid_categories:
        return JSONResponse(
            {"error": f"Nieprawidłowa kategoria. Dozwolone: {', '.join(valid_categories)}"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Build progress data (progress tracking only for group members)
        if can_view_progress and user_id:
            progress = build_progress_data(user_id=user_id, db=db, category_filter=category)
        else:
            # For non-members, show all tasks as unlocked (no personal progress)
            progress = build_progress_data(user_id=None, db=db, category_filter=category)
            # Override status to unlocked for all nodes (they can browse but not see progress)
            for node in progress.nodes:
                node.status = TaskStatus.UNLOCKED
                node.best_score = 0
            progress.stats = {
                "total": len(progress.nodes),
                "mastered": 0,
                "unlocked": len(progress.nodes),
                "locked": 0,
            }
            progress.recommendations = []

        return JSONResponse({
            **progress.model_dump(mode="json"),
            "user": user,
            "is_authenticated": user is not None,
        })

    except Exception as e:
        logger.error(f"Error building progress data: {e}")
        return JSONResponse(
            {"error": "Błąd podczas ładowania danych postępów"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@app.get("/years/{year}/{etap}", response_class=HTMLResponse)
async def etap_detail(request: Request, year: str, etap: str, db: Session = Depends(get_db)):
    """Display tasks for a year/etap (public). Stats shown only to group members."""
    etap_tasks = get_tasks_for_etap(year, etap)
    if not etap_tasks:
        raise HTTPException(status_code=404, detail="Etap nie znaleziony")

    user = get_current_user(request)
    user_id = get_current_user_id(request)
    # Use async version to refresh membership status if needed
    can_see_stats = await is_group_member_async(request)

    # Build task list - stats only for group members
    tasks = []
    for task_info in etap_tasks:
        task_data = {
            "number": task_info.number,
            "title": task_info.title,
            "has_content": True,
            "difficulty": task_info.difficulty,
            "categories": task_info.categories,
            "submission_count": 0,
            "highest_score": None,
        }
        if can_see_stats and user_id:
            submission_repo = SubmissionRepository(db)
            count, highest = submission_repo.get_task_stats(user_id, year, etap, task_info.number)
            task_data["submission_count"] = count
            task_data["highest_score"] = highest if highest > 0 else None
        tasks.append(task_data)

    return templates.TemplateResponse(
        "etap.html",
        {
            "request": request,
            "year": year,
            "etap": etap,
            "tasks": tasks,
            "is_authenticated": user is not None,
            "user": user,
        },
    )


@app.get("/task/{year}/{etap}/{num}", response_class=HTMLResponse)
async def task_detail(request: Request, year: str, etap: str, num: int, db: Session = Depends(get_db)):
    """Display task detail (public). Submission form, stats, and history only for group members."""
    task = get_task(year, etap, num)
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie nie znalezione")

    user = get_current_user(request)
    user_id = get_current_user_id(request)
    # Use async version to refresh membership status if needed
    can_submit = await is_group_member_async(request)

    # Stats and submissions only for group members
    stats = None
    submissions = []
    if can_submit and user_id:
        submission_repo = SubmissionRepository(db)
        count, highest = submission_repo.get_task_stats(user_id, year, etap, num)
        stats = {"submission_count": count, "highest_score": highest}
        db_submissions = submission_repo.get_user_submissions_for_task(user_id, year, etap, num)
        submissions = submission_repo.to_pydantic_list(db_submissions[:10])

    # Get PDF paths for links
    task_pdf = get_task_pdf_path(year, etap)
    solution_pdf = get_solution_pdf_path(year, etap)

    pdf_links = {}
    if task_pdf and task_pdf.exists():
        pdf_links["tasks"] = f"/pdf/{year}/{etap}/{task_pdf.name}"
    if solution_pdf and solution_pdf.exists():
        pdf_links["solutions"] = f"/pdf/{year}/{etap}/{solution_pdf.name}"

    # Load skills data
    skills_required = get_skills_by_ids(task.skills_required)
    skills_gained = get_skills_by_ids(task.skills_gained)

    # Load prerequisite statuses
    prerequisite_statuses = []
    if task.prerequisites:
        if can_submit and user_id:
            progress = compute_user_progress(user_id=user_id, db=db)
            prerequisite_statuses = get_prerequisite_statuses(task.prerequisites, progress)
        else:
            # Show prerequisites without status for unauthenticated users
            prerequisite_statuses = get_prerequisite_statuses(task.prerequisites, None)

    return templates.TemplateResponse(
        "task.html",
        {
            "request": request,
            "task": task,
            "stats": stats,
            "submissions": submissions,
            "pdf_links": pdf_links,
            "is_authenticated": user is not None,
            "can_submit": can_submit,
            "user": user,
            "skills_required": skills_required,
            "skills_gained": skills_gained,
            "prerequisite_statuses": prerequisite_statuses,
        },
    )


def _validate_path_params(year: str, etap: str) -> bool:
    """Validate year and etap to prevent path traversal."""
    return bool(re.match(r"^\d{4}$", year) and re.match(r"^[a-zA-Z0-9_-]+$", etap))


# Max image dimensions for AI API compatibility
MAX_IMAGE_DIMENSION = 2048


def _resize_image_if_needed(file_path: Path) -> None:
    """Resize image if it exceeds maximum dimensions."""
    try:
        with Image.open(file_path) as img:
            # Check if resizing is needed
            if img.width <= MAX_IMAGE_DIMENSION and img.height <= MAX_IMAGE_DIMENSION:
                return

            # Calculate new dimensions preserving aspect ratio
            ratio = min(MAX_IMAGE_DIMENSION / img.width, MAX_IMAGE_DIMENSION / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))

            # Resize and save
            resized = img.resize(new_size, Image.Resampling.LANCZOS)

            # Handle EXIF orientation
            if hasattr(img, '_getexif') and img._getexif():
                from PIL import ExifTags
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == 'Orientation':
                        break
                exif = img._getexif()
                if exif and orientation in exif:
                    # Apply orientation correction
                    if exif[orientation] == 3:
                        resized = resized.rotate(180, expand=True)
                    elif exif[orientation] == 6:
                        resized = resized.rotate(270, expand=True)
                    elif exif[orientation] == 8:
                        resized = resized.rotate(90, expand=True)

            # Save as JPEG for consistency
            resized_path = file_path.with_suffix('.jpg')
            resized.convert('RGB').save(resized_path, 'JPEG', quality=85)

            # Remove original if different
            if resized_path != file_path:
                file_path.unlink(missing_ok=True)

    except Exception:
        # If resize fails, keep original - AI will report the error
        pass


@app.post("/task/{year}/{etap}/{num}/submit")
async def submit_solution(
    request: Request,
    year: str,
    etap: str,
    num: int,
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Submit solution images for analysis (requires group membership).

    Returns immediately with submission_id. Client should connect to
    WebSocket at /ws/submissions/{submission_id} for progress updates.
    """
    # Check if user is authenticated
    if not verify_auth(request):
        return JSONResponse(
            {"error": "Nieautoryzowany dostęp"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Get user ID from session
    user_id = get_current_user_id(request)
    if not user_id:
        return JSONResponse(
            {"error": "Nieautoryzowany dostęp"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Check rate limits (skip for allowlisted users)
    allowed_emails = _get_allowed_emails()
    user = get_current_user(request)
    user_email_lower = user.get("email", "").lower() if user else ""
    is_allowlisted = allowed_emails and user_email_lower in allowed_emails

    # Create repository once for rate limit checks and later submission creation
    submission_repo = SubmissionRepository(db)

    # Track rate limit info for headers (even if allowlisted, for informational purposes)
    user_submission_count, user_oldest_submission = submission_repo.get_user_rate_limit_info(
        user_id, hours=24
    )
    rate_limit_headers = _calculate_rate_limit_headers(
        limit=settings.rate_limit_submissions_per_user_per_day,
        current_count=user_submission_count,
        oldest_timestamp=user_oldest_submission,
        window_hours=24,
    )

    if not is_allowlisted:
        # Check per-user submission limit
        if user_submission_count >= settings.rate_limit_submissions_per_user_per_day:
            logger.warning(
                f"User submission rate limit exceeded: {user_id[:8]}... "
                f"{user_submission_count}/{settings.rate_limit_submissions_per_user_per_day}"
            )
            retry_after = _calculate_retry_after(user_oldest_submission, window_hours=24)
            return JSONResponse(
                {
                    "error": f"Osiągnięto dzienny limit zgłoszeń ({settings.rate_limit_submissions_per_user_per_day}). "
                    "Możesz przesłać więcej rozwiązań jutro."
                },
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={**rate_limit_headers, "Retry-After": str(retry_after)},
            )

        # Check global submission limit
        global_submission_count, global_oldest_submission = submission_repo.get_global_rate_limit_info(
            hours=24
        )
        if global_submission_count >= settings.rate_limit_submissions_global_per_day:
            logger.warning(
                f"Global submission rate limit exceeded: {global_submission_count}/{settings.rate_limit_submissions_global_per_day}"
            )
            global_rate_headers = _calculate_rate_limit_headers(
                limit=settings.rate_limit_submissions_global_per_day,
                current_count=global_submission_count,
                oldest_timestamp=global_oldest_submission,
                window_hours=24,
            )
            retry_after = _calculate_retry_after(global_oldest_submission, window_hours=24)
            return JSONResponse(
                {"error": "System osiągnął dzienny limit zgłoszeń. Spróbuj ponownie później."},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={**global_rate_headers, "Retry-After": str(retry_after)},
            )

    # Validate path parameters to prevent directory traversal
    if not _validate_path_params(year, etap):
        return JSONResponse(
            {"error": "Nieprawidłowe parametry"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not images:
        return JSONResponse(
            {"error": "Nie przesłano żadnych zdjęć"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Limit number of images
    MAX_IMAGES = 10
    if len(images) > MAX_IMAGES:
        return JSONResponse(
            {"error": f"Maksymalnie {MAX_IMAGES} zdjęć na raz"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Validate file types
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/heic"}
    for img in images:
        if img.content_type not in allowed_types:
            return JSONResponse(
                {"error": f"Niedozwolony typ pliku: {img.content_type}"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    # Save uploaded images (per-user directory structure)
    upload_dir = settings.uploads_dir / user_id / year / etap / str(num)
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    max_size = settings.upload_max_size_mb * 1024 * 1024
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".heic"}

    for img in images:
        # Validate and normalize extension
        ext = Path(img.filename).suffix.lower() if img.filename else ".jpg"
        if ext not in allowed_extensions:
            ext = ".jpg"  # Default to jpg for safety

        filename = f"{uuid.uuid4().hex[:12]}{ext}"
        file_path = upload_dir / filename

        # Read file in chunks with size limit check
        total_size = 0
        CHUNK_SIZE = 64 * 1024  # 64KB chunks
        try:
            with open(file_path, "wb") as f:
                while True:
                    chunk = await img.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > max_size:
                        f.close()
                        file_path.unlink(missing_ok=True)
                        return JSONResponse(
                            {"error": f"Plik {img.filename} jest za duży (max {settings.upload_max_size_mb}MB)"},
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )
                    f.write(chunk)
        except Exception:
            file_path.unlink(missing_ok=True)
            raise

        # Resize if too large for AI API
        _resize_image_if_needed(file_path)

        # Update path if extension changed (e.g., PNG -> JPG after resize)
        if not file_path.exists():
            file_path = file_path.with_suffix('.jpg')

        saved_paths.append(file_path)

    # Get PDF paths - validate early
    task_pdf = get_task_pdf_path(year, etap)
    if not task_pdf or not task_pdf.exists():
        return JSONResponse(
            {"error": "Nie znaleziono pliku z zadaniami"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Create submission record with PENDING status
    from .db.models import SubmissionStatus
    from .websocket.progress import progress_manager
    from .websocket.handler import process_submission_background

    submission_id = str(uuid.uuid4())[:8]

    submission = submission_repo.create(
        id=submission_id,
        user_id=user_id,
        year=year,
        etap=etap,
        task_number=num,
        images=[str(p.relative_to(settings.uploads_dir)) for p in saved_paths],
        status=SubmissionStatus.PENDING,
    )

    # Initialize progress tracking (handler.py will set first status)
    await progress_manager.create_submission(submission_id)

    # Start background task for AI processing with proper lifecycle tracking
    task = asyncio.create_task(
        process_submission_background(
            submission_id=submission_id,
            user_id=user_id,
            year=year,
            etap=etap,
            task_number=num,
            image_paths=saved_paths,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    # Return immediately with submission_id and WebSocket URL
    # Include ws_url so frontend knows where to connect
    ws_path = f"/ws/submissions/{submission.id}"

    # Update rate limit headers to reflect this new submission
    # (increment count by 1 since we just created a submission)
    updated_rate_limit_headers = _calculate_rate_limit_headers(
        limit=settings.rate_limit_submissions_per_user_per_day,
        current_count=user_submission_count + 1,
        oldest_timestamp=user_oldest_submission,
        window_hours=24,
    )

    return JSONResponse(
        {
            "success": True,
            "submission_id": submission.id,
            "status": "processing",
            "message": "Rozwiązanie przesłane. Połącz się z WebSocket, aby śledzić postęp.",
            "ws_path": ws_path,
        },
        headers=updated_rate_limit_headers,
    )


@app.websocket("/ws/submissions/{submission_id}")
async def websocket_submission_progress(
    websocket: WebSocket,
    submission_id: str,
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time submission progress.

    Connect after calling POST /task/{year}/{etap}/{num}/submit.
    Receives progress updates as JSON messages.
    """
    from itsdangerous import TimestampSigner
    import base64
    import json
    from .websocket.handler import websocket_submission_handler
    from .websocket.progress import progress_manager

    # Get user from session cookie
    # WebSocket connections include cookies automatically
    user_id = None

    if settings.auth_disabled:
        user_id = "anonymous"
    else:
        try:
            # Decode session cookie using same method as SessionMiddleware
            session_cookie = websocket.cookies.get("session")
            if session_cookie:
                # Starlette SessionMiddleware uses TimestampSigner + base64 + JSON
                signer = TimestampSigner(settings.session_secret_key)
                # max_age matches the middleware config (30 days)
                data = signer.unsign(session_cookie, max_age=30 * 24 * 60 * 60)
                session_data = json.loads(base64.b64decode(data))
                user = session_data.get(SESSION_USER_KEY)
                if user:
                    user_id = user.get("google_sub")
                    logger.info(f"[WebSocket] Session decoded, user_id={user_id[:8]}...")
                else:
                    logger.warning(f"[WebSocket] No user in session data")
            else:
                logger.warning(f"[WebSocket] No session cookie found. Cookies: {list(websocket.cookies.keys())}")
        except Exception as e:
            logger.warning(f"[WebSocket] Session decode failed: {e}")

    # Verify submission exists
    submission_repo = SubmissionRepository(db)
    submission = submission_repo.get_by_id(submission_id)

    if not submission:
        await websocket.close(code=4004, reason="Submission not found")
        return

    # Verify user owns this submission (unless auth disabled)
    if not settings.auth_disabled:
        if not user_id or user_id != submission.user_id:
            logger.warning(f"[WebSocket] Auth failed: user_id={user_id}, submission.user_id={submission.user_id[:8] if submission.user_id else None}...")
            await websocket.close(code=4003, reason="Not authorized")
            return

    # Handle the WebSocket connection
    await websocket_submission_handler(
        websocket=websocket,
        submission_id=submission_id,
        user_id=submission.user_id,
    )


@app.get("/task/{year}/{etap}/{num}/history", response_class=HTMLResponse)
async def task_history(request: Request, year: str, etap: str, num: int, db: Session = Depends(get_db)):
    """Display submission history for a task (requires group membership)."""
    # Require group membership to view history
    if not verify_auth(request):
        from urllib.parse import urlencode
        next_url = str(request.url.path)
        login_url = f"/login?{urlencode({'next': next_url})}"
        return RedirectResponse(url=login_url, status_code=status.HTTP_303_SEE_OTHER)

    if not await is_group_member_async(request):
        return RedirectResponse(url="/auth/limited", status_code=status.HTTP_303_SEE_OTHER)

    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    task = get_task(year, etap, num)
    user = get_current_user(request)

    # Load submissions for current user only
    submission_repo = SubmissionRepository(db)
    db_submissions = submission_repo.get_user_submissions_for_task(user_id, year, etap, num)
    submissions = submission_repo.to_pydantic_list(db_submissions)

    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "task": task,
            "year": year,
            "etap": etap,
            "num": num,
            "submissions": submissions,
            "is_authenticated": True,
            "user": user,
        },
    )


# --- Static file serving for PDFs ---


@app.get("/pdf/{year}/{etap}/{filename}")
async def serve_pdf(request: Request, year: str, etap: str, filename: str):
    """Serve task/solution PDF files (public)."""
    # Validate parameters
    if not _validate_path_params(year, etap):
        raise HTTPException(status_code=400, detail="Invalid parameters")

    # Only allow .pdf files
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type")

    file_path = settings.tasks_dir / year / etap / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")

    # Ensure path doesn't escape tasks dir
    try:
        file_path.resolve().relative_to(settings.tasks_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

    from fastapi.responses import FileResponse

    return FileResponse(file_path, media_type="application/pdf")


# --- Static file serving for uploads ---


@app.get("/uploads/{path:path}")
async def serve_upload(request: Request, path: str):
    """Serve uploaded files (with auth check and user ownership verification)."""
    redirect = require_auth_redirect(request)
    if redirect:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Handle legacy paths that include 'uploads/' prefix (from old submissions)
    if path.startswith("uploads/"):
        path = path[8:]  # Strip 'uploads/' prefix

    # Verify path starts with user's ID (user can only access their own uploads)
    # Admin users can access any user's uploads
    # Path format: {user_id}/{year}/{etap}/{task_num}/{filename}
    path_parts = path.split("/")
    is_admin = _is_admin(request)
    if len(path_parts) < 1 or (path_parts[0] != user_id and not is_admin):
        raise HTTPException(status_code=403, detail="Forbidden")

    file_path = settings.uploads_dir / path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Ensure path doesn't escape uploads dir
    try:
        file_path.resolve().relative_to(settings.uploads_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

    from fastapi.responses import FileResponse

    return FileResponse(file_path)


# --- Health Check ---


@app.get("/health")
async def health_check():
    """Health check endpoint for deployment platforms."""
    return {"status": "ok"}


# --- E2E Test Utility Endpoints ---
# These endpoints are only available when E2E_MODE=true


@app.post("/api/test/reset-user-submissions")
async def reset_user_submissions(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Reset (delete) all submissions for the current user.
    Only available in E2E testing mode.
    """
    if not settings.e2e_mode:
        raise HTTPException(
            status_code=404,
            detail="Not found",
        )

    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    user_id = user.get("google_sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid user session",
        )

    # Delete all submissions for this user
    submission_repo = SubmissionRepository(db)
    deleted_count = submission_repo.delete_all_user_submissions(user_id)

    logger.info(f"E2E: Reset {deleted_count} submissions for user {user.get('email')}")

    return {
        "success": True,
        "deleted_count": deleted_count,
        "user_email": user.get("email"),
    }


@app.post("/api/test/reset-all-submissions")
async def reset_all_submissions(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Reset (delete) all submissions in the database.
    Only available in E2E testing mode.
    Used to reset the global rate limit between test suites.
    """
    if not settings.e2e_mode:
        raise HTTPException(
            status_code=404,
            detail="Not found",
        )

    # Require authentication for defense in depth
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    # Delete all submissions
    submission_repo = SubmissionRepository(db)
    deleted_count = submission_repo.delete_all_submissions()

    logger.info(f"E2E: Reset all {deleted_count} submissions")

    return {
        "success": True,
        "deleted_count": deleted_count,
    }


# --- JSON API Endpoints for Next.js Frontend ---


@app.get("/api/auth/me")
async def get_current_user_api(request: Request):
    """Get current user from session (for Next.js frontend)."""
    user = get_current_user(request)
    return {
        "user": user,
        "is_authenticated": user is not None,
        "is_admin": _is_admin(request),
    }


@app.get("/api/years")
async def years_api(request: Request):
    """Get available years (JSON)."""
    years = get_available_years()
    user = get_current_user(request)
    return {
        "years": years,
        "user": user,
        "is_authenticated": user is not None,
    }


@app.get("/api/years/{year}")
async def year_detail_api(request: Request, year: str):
    """Get etaps for a year (JSON)."""
    etaps = get_etaps_for_year(year)
    if not etaps:
        raise HTTPException(status_code=404, detail="Year not found")

    user = get_current_user(request)
    return {
        "year": year,
        "etaps": etaps,
        "user": user,
        "is_authenticated": user is not None,
    }


@app.get("/api/years/{year}/{etap}")
async def etap_detail_api(
    request: Request,
    year: str,
    etap: str,
    db: Session = Depends(get_db)
):
    """Get tasks for an etap (JSON)."""
    etap_tasks = get_tasks_for_etap(year, etap)
    if not etap_tasks:
        raise HTTPException(status_code=404, detail="Etap not found")

    user = get_current_user(request)
    user_id = get_current_user_id(request)
    can_see_stats = await is_group_member_async(request)

    tasks = []
    for task_info in etap_tasks:
        task_data = {
            "year": task_info.year,
            "etap": task_info.etap,
            "number": task_info.number,
            "title": task_info.title,
            "content": task_info.content,
            "pdf": task_info.pdf.model_dump() if task_info.pdf else None,
            "difficulty": task_info.difficulty,
            "categories": task_info.categories,
            "hints": task_info.hints,
            "prerequisites": task_info.prerequisites,
            "skills_required": task_info.skills_required,
            "skills_gained": task_info.skills_gained,
            "submission_count": 0,
            "highest_score": None,
        }
        if can_see_stats and user_id:
            submission_repo = SubmissionRepository(db)
            count, highest = submission_repo.get_task_stats(user_id, year, etap, task_info.number)
            task_data["submission_count"] = count
            task_data["highest_score"] = highest if highest > 0 else None
        tasks.append(task_data)

    return {
        "year": year,
        "etap": etap,
        "tasks": tasks,
        "user": user,
        "is_authenticated": user is not None,
    }


@app.get("/api/task/{year}/{etap}/{num}")
async def task_detail_api(
    request: Request,
    year: str,
    etap: str,
    num: int,
    db: Session = Depends(get_db)
):
    """Get task detail (JSON)."""
    task = get_task(year, etap, num)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    user = get_current_user(request)
    user_id = get_current_user_id(request)
    can_submit = await is_group_member_async(request)

    stats = None
    submissions = []
    if can_submit and user_id:
        submission_repo = SubmissionRepository(db)
        count, highest = submission_repo.get_task_stats(user_id, year, etap, num)
        stats = {"submission_count": count, "highest_score": highest}
        db_submissions = submission_repo.get_user_submissions_for_task(user_id, year, etap, num)
        submissions = submission_repo.to_pydantic_list(db_submissions[:10])

    task_pdf = get_task_pdf_path(year, etap)
    solution_pdf = get_solution_pdf_path(year, etap)

    pdf_links = {}
    if task_pdf and task_pdf.exists():
        pdf_links["tasks"] = f"/pdf/{year}/{etap}/{task_pdf.name}"
    if solution_pdf and solution_pdf.exists():
        pdf_links["solutions"] = f"/pdf/{year}/{etap}/{solution_pdf.name}"

    skills_required = get_skills_by_ids(task.skills_required)
    skills_gained = get_skills_by_ids(task.skills_gained)

    prerequisite_statuses = []
    if task.prerequisites:
        if can_submit and user_id:
            progress = compute_user_progress(user_id=user_id, db=db)
            prerequisite_statuses = get_prerequisite_statuses(task.prerequisites, progress)
        else:
            # Show prerequisites without status for unauthenticated users
            prerequisite_statuses = get_prerequisite_statuses(task.prerequisites, None)

    return {
        "task": task.model_dump(mode="json"),
        "stats": stats,
        "submissions": [s.model_dump(mode="json") for s in submissions],
        "pdf_links": pdf_links,
        "user": user,
        "is_authenticated": user is not None,
        "can_submit": can_submit,
        "skills_required": [s.model_dump(mode="json") for s in skills_required],
        "skills_gained": [s.model_dump(mode="json") for s in skills_gained],
        "prerequisite_statuses": [p.model_dump(mode="json") for p in prerequisite_statuses],
    }


@app.get("/api/task/{year}/{etap}/{num}/history")
async def task_history_api(
    request: Request,
    year: str,
    etap: str,
    num: int,
    db: Session = Depends(get_db)
):
    """Get submission history for a task (JSON)."""
    if not await is_group_member_async(request):
        raise HTTPException(status_code=403, detail="Forbidden")

    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    task = get_task(year, etap, num)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    submission_repo = SubmissionRepository(db)
    db_submissions = submission_repo.get_user_submissions_for_task(user_id, year, etap, num)
    submissions = submission_repo.to_pydantic_list(db_submissions)

    return {
        "task": task.model_dump(mode="json"),
        "submissions": [s.model_dump(mode="json") for s in submissions],
    }


# ==================== User Submissions (Moje rozwiązania) ====================


def _get_max_score(etap: str) -> int:
    """Get max score for an etap (3 for etap1, 6 for etap2/3)."""
    return 3 if etap == "etap1" else 6


@app.get("/api/my-submissions")
async def my_submissions(
    request: Request,
    offset: int = 0,
    limit: int = 20,
    year: OptionalType[str] = None,
    etap: OptionalType[str] = None,
    hide_errors: bool = False,
    db: Session = Depends(get_db)
):
    """Get current user's submissions with pagination, filters, and aggregate stats.

    Used by "Moje rozwiązania" (My Solutions) panel.
    """
    # Require authenticated user (group membership not required for viewing own submissions)
    if not verify_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Cap limit to prevent abuse
    limit = min(limit, 100)

    submission_repo = SubmissionRepository(db)

    # Get paginated submissions
    db_submissions, total_count = submission_repo.get_user_submissions_paginated(
        user_id=user_id,
        offset=offset,
        limit=limit,
        year_filter=year,
        etap_filter=etap,
        hide_errors=hide_errors,
    )

    # Get aggregate stats (only on first page to avoid recalculating)
    if offset == 0:
        stats_dict = submission_repo.get_user_aggregate_stats(user_id)
    else:
        # Return minimal stats for subsequent pages
        stats_dict = {
            "total_submissions": total_count,
            "completed_count": 0,
            "failed_count": 0,
            "pending_count": 0,
            "avg_score": None,
            "best_score": None,
            "tasks_attempted": 0,
            "tasks_mastered": 0,
        }

    # Enrich submissions with task metadata
    submissions_list = []
    for sub in db_submissions:
        # Get task info for title and categories
        task = get_task(sub.year, sub.etap, sub.task_number)
        task_title = task.title if task else f"Zadanie {sub.task_number}"
        task_categories = task.categories if task else []

        # Create feedback preview (first 150 chars)
        feedback_preview = None
        if sub.feedback:
            feedback_preview = sub.feedback[:150] + "..." if len(sub.feedback) > 150 else sub.feedback

        submissions_list.append({
            "id": sub.id,
            "year": sub.year,
            "etap": sub.etap,
            "task_number": sub.task_number,
            "task_title": task_title,
            "task_categories": task_categories,
            "timestamp": sub.timestamp.isoformat(),
            "status": sub.status.value,
            "score": sub.score,
            "max_score": _get_max_score(sub.etap),
            "feedback": sub.feedback,
            "feedback_preview": feedback_preview,
            "error_message": sub.error_message,
            "images": sub.images or [],
        })

    return {
        "submissions": submissions_list,
        "stats": stats_dict,
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(submissions_list) < total_count,
    }


# ==================== Admin API Endpoints ====================


def _is_admin(request: Request) -> bool:
    """Check if the current user is an admin."""
    user = get_current_user(request)
    if not user:
        return False

    admin_emails_str = settings.admin_emails
    if not admin_emails_str:
        return False

    admin_emails = {e.strip().lower() for e in admin_emails_str.split(",") if e.strip()}
    user_email = user.get("email", "").lower()
    return user_email in admin_emails


def _require_admin(request: Request) -> None:
    """Raise 401/403 if not admin."""
    if not verify_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not _is_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")


@app.get("/api/admin/submissions")
async def admin_submissions(
    request: Request,
    offset: int = 0,
    limit: int = 20,
    user_id: OptionalType[str] = None,
    status: OptionalType[str] = None,
    issue_type: OptionalType[str] = None,
    db: Session = Depends(get_db)
):
    """Get all submissions with pagination and filters (admin only)."""
    _require_admin(request)

    # Cap limit to prevent abuse
    limit = min(limit, 100)

    submission_repo = SubmissionRepository(db)
    user_repo = UserRepository(db)

    # Get paginated submissions
    db_submissions, total_count = submission_repo.get_all_submissions_paginated(
        offset=offset,
        limit=limit,
        user_id_filter=user_id,
        status_filter=status,
        issue_type_filter=issue_type,
    )

    # Batch fetch all users in a single query to avoid N+1
    user_ids = list(set(sub.user_id for sub in db_submissions))
    users_by_id = user_repo.get_by_google_subs(user_ids)

    # Convert to response format with user info
    submissions = []
    for sub in db_submissions:
        user = users_by_id.get(sub.user_id)
        submissions.append({
            "id": sub.id,
            "user_id": sub.user_id,
            "user_email": user.email if user else None,
            "user_name": user.name if user else None,
            "year": sub.year,
            "etap": sub.etap,
            "task_number": sub.task_number,
            "timestamp": sub.timestamp.isoformat(),
            "status": sub.status.value,
            "images": sub.images,
            "score": sub.score,
            "feedback": sub.feedback,
            "error_message": sub.error_message,
            "issue_type": sub.issue_type.value,
            "abuse_score": sub.abuse_score,
        })

    return {
        "submissions": submissions,
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(submissions) < total_count,
    }


@app.get("/api/admin/users/search")
async def admin_users_search(
    request: Request,
    q: str = "",
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Search users by email for autocomplete (admin only)."""
    _require_admin(request)

    # Cap limit to prevent abuse
    limit = min(limit, 50)

    user_repo = UserRepository(db)
    users = user_repo.search_by_email(q, limit=limit)

    return {
        "users": [
            {
                "google_sub": user.google_sub,
                "email": user.email,
                "name": user.name,
            }
            for user in users
        ]
    }


@app.get("/api/admin/me")
async def admin_me(request: Request):
    """Check if current user is admin."""
    user = get_current_user(request)
    return {
        "user": user,
        "is_authenticated": user is not None,
        "is_admin": _is_admin(request),
    }
