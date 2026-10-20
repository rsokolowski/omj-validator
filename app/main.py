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
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from fastapi import Depends, Form
from sqlalchemy.orm import Session

from .config import settings
from .auth import (
    SESSION_PENDING_GOOGLE_KEY,
    SESSION_PENDING_REGISTRATION_KEY,
    PENDING_SESSION_SECONDS,
    AccountInactiveError,
    allow_inactive_account,
    current_account,
    require_active_user,
    safe_next_path,
    start_session,
    verify_auth,
    require_auth_redirect,
    get_current_user,
    get_current_user_id,
    is_group_member,
    is_group_member_async,
    current_member_id,
    is_allowlisted,
)
from .oauth import oauth
from .privacy import mask_email, mask_user_id
from .groups import check_group_membership, is_email_allowlisted
from .db import (
    get_db,
    UserRepository,
    SubmissionRepository,
    AdminAccessLogRepository,
)
from .db.repositories import ensure_utc

logger = logging.getLogger(__name__)

from datetime import datetime as dt_datetime, timezone as dt_timezone, timedelta as dt_timedelta
from typing import Optional as OptionalType

from .uploads import (
    HEIF_SUPPORTED,
    HEIF_EXTENSIONS,
    MAX_IMAGE_DIMENSION,
    register_heif_decoder as _register_heif_decoder,
    discard_uploads as _discard_uploads,
    unprocessable_image_message as _unprocessable_image_message,
    flatten_transparency as _flatten_transparency,
    normalize_uploaded_image,
    save_uploaded_images,
    validate_submission_input,
)
from .rate_limits import (
    calculate_rate_limit_headers as _calculate_rate_limit_headers,
    rate_limit_reset_anchor as _rate_limit_reset_anchor,
    calculate_retry_after as _calculate_retry_after,
    release_reserved_submission,
    reserve_submission,
    settle_refused_submission,
)

# Kept under its historical name: submit_solution resolves it at call time, so
# tests (and a future hotfix) can substitute the normaliser here.
_normalize_uploaded_image = normalize_uploaded_image

# Track background tasks for proper lifecycle management
_background_tasks: set[asyncio.Task] = set()
from .storage import (
    get_available_years,
    get_etaps_for_year,
    get_tasks_for_etap,
    get_task,
    get_task_pdf_path,
    get_solution_pdf_path,
    _load_all_tasks,
)
from .ai import create_ai_provider, AIProviderError
from .ai import config_store as ai_config_store
from .ai import factory as ai_factory
from .ai import models_catalog
from .models import (
    ACCOUNT_DELETE_CONFIRMATION,
    AiActiveModel,
    AiConfigResponse,
    AiConfigUpdateRequest,
    AiConfigUpdateResponse,
    AiEffectiveModel,
    AiModelOption,
    AiProviderOption,
    DeleteAccountRequest,
    DeleteAccountResponse,
    SubmissionResult,
    TaskCategory,
    TaskStatus,
)
from .progress import build_progress_data, get_all_categories, get_prerequisite_statuses, compute_user_progress
from .skills import get_skills_by_ids
from .scoring import get_max_score

# require_active_user runs for every route: an account waiting for parent
# consent (or for its year of birth) cannot write anything, and a new endpoint
# cannot forget the check. Exceptions are marked @allow_inactive_account.
app = FastAPI(
    title="OMJ Validator",
    description="Walidator rozwiązań OMJ",
    dependencies=[Depends(require_active_user)],
)


@app.exception_handler(AccountInactiveError)
async def _account_inactive_handler(request: Request, exc: AccountInactiveError):
    return JSONResponse({"detail": exc.detail, "code": exc.code}, status_code=status.HTTP_403_FORBIDDEN)


from .private_tasks import router as private_tasks_router  # noqa: E402
from .patterns.routes import router as patterns_router  # noqa: E402
from .patterns import service as pattern_service  # noqa: E402
from .accounts.routes import router as accounts_router  # noqa: E402
from .accounts import service as account_service  # noqa: E402

app.include_router(private_tasks_router)
app.include_router(patterns_router)
app.include_router(accounts_router)

# Split deployment: frontend on a different site than the API (explicit
# opt-in). FRONTEND_URL alone - production sets it for the OAuth callback while
# serving everything from one origin - does not make the cookie cross-site.
is_split_deployment = bool(settings.split_deployment and settings.frontend_url)

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

# Unsafe-method requests must come from this site (app/csrf.py). Added last,
# so it runs first: a forged request is refused before anything else runs.
from .csrf import CrossSiteRequestGuard  # noqa: E402

app.add_middleware(
    CrossSiteRequestGuard,
    trusted_origins=[settings.public_base_url, settings.frontend_url],
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
                birth_year=2000,
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
async def start_telegram_digest():
    """Anonymous submission counts to Telegram every few minutes (app/notifications.py)."""
    from .notifications import digest_loop

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    task = asyncio.create_task(digest_loop())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


# Rows younger than this at startup are left alone: during a container swap
# the old process may still be finishing them
RESTART_RELEASE_GRACE_SECONDS = 60


def release_interrupted_submissions() -> None:
    """Release gradings a restart killed (see SubmissionRepository.release_interrupted).

    The worker runs gradings as in-process asyncio tasks (production: one
    gunicorn worker), so nothing is still grading a PENDING/PROCESSING row
    after a restart. Without this they would count as in flight - and lock
    the student out - for SUBMISSION_TIMEOUT_SECONDS. Never fails startup.
    """
    from .ai.messages import GENERIC_MESSAGE
    from .db import SessionLocal
    from .retention import delete_unreferenced_uploads

    db = SessionLocal()
    try:
        released, freed = SubmissionRepository(db).release_interrupted(
            RESTART_RELEASE_GRACE_SECONDS, GENERIC_MESSAGE
        )
        if released:
            delete_unreferenced_uploads(db, freed)
            logger.info(f"Released {released} submission(s) interrupted by the restart")
    except Exception as e:
        logger.error(f"Could not release interrupted submissions: {type(e).__name__}")
    finally:
        db.close()


app.on_event("startup")(release_interrupted_submissions)


@app.on_event("startup")
def release_interrupted_exercise_batches() -> None:
    """Fail exercise batches a restart killed (see patterns.exercises)."""
    from .patterns.exercises import release_interrupted_batches

    release_interrupted_batches()


@app.on_event("startup")
def warm_ai_provider():
    """Initialize AI provider at startup to avoid latency on first request."""
    try:
        provider = create_ai_provider()
        logger.info(f"AI provider warmed up: {type(provider).__name__}")
    except Exception as e:
        logger.warning(f"Failed to warm AI provider: {e}")


def _run_retention_once() -> None:
    """One retention pass with its own DB session (blocking - run in a thread)."""
    from .db import SessionLocal
    from .retention import run_retention

    db = SessionLocal()
    try:
        run_retention(db)
    finally:
        db.close()


@app.on_event("startup")
async def start_retention_task():
    """Expire old submissions, photos and AI traces once a day.

    RODO art. 5(1)(e): nothing may be kept indefinitely. The production image
    runs a single gunicorn worker, so exactly one loop exists. If you scale to
    several workers, set RETENTION_AUTO_PURGE=false and run
    scripts/purge_expired_data.py from cron instead.
    """
    if not settings.retention_auto_purge:
        logger.info("Automatic data retention disabled (RETENTION_AUTO_PURGE=false)")
        return

    if not any(
        (
            settings.retention_submission_months,
            settings.retention_scoring_thinking_days,
            settings.retention_inactive_account_months,
            settings.retention_admin_audit_months,
            settings.retention_private_task_months,
            settings.retention_ai_usage_days,
        )
    ):
        logger.info("Automatic data retention disabled (no retention periods configured)")
        return

    async def retention_loop():
        # Let the app finish booting before touching the database
        await asyncio.sleep(120)
        while True:
            try:
                await asyncio.to_thread(_run_retention_once)
            except Exception as e:
                logger.warning(f"Data retention run failed: {type(e).__name__}: {e}")
            await asyncio.sleep(24 * 60 * 60)  # once a day

    task = asyncio.create_task(retention_loop())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


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

    # Answers from /rejestracja travel with ?register=1; a plain "Zaloguj
    # przez Google" must not pick up an abandoned registration's answers
    if request.query_params.get("register") != "1":
        request.session.pop(SESSION_PENDING_REGISTRATION_KEY, None)

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

        email = user_info["email"]
        name = user_info.get("name", "")
        picture = user_info.get("picture")
        next_url = request.session.pop("login_next", None)

        user_repo = UserRepository(db)
        existing_user = user_repo.get_by_google_sub(google_sub)

        if existing_user is None:
            return await _google_new_identity(request, db, google_sub, email, name, picture)

        # Known Google identity: refresh the profile and log in
        user_repo.update_google_profile(existing_user, email, name)

        # Check if user has full access (via public access, allowlist, or Google Groups)
        has_access = await check_group_membership(email)
        email_allowlisted = is_email_allowlisted(email)

        start_session(request, existing_user, remember=True, is_group_member=has_access, picture=picture)

        logger.info(
            f"User logged in: {mask_email(email)} "
            f"(has_access: {has_access}, allowlisted: {email_allowlisted})"
        )

        # Redirect to the original page or default to /years
        # Validate that redirect URL is a safe relative path (prevent open redirect)
        redirect_url = "/years"
        if existing_user.status != "active":
            redirect_url = "/konto/oczekuje"
        elif safe_next_path(next_url):
            redirect_url = next_url
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return RedirectResponse(
            url="/login?error=oauth_failed",
            status_code=status.HTTP_303_SEE_OTHER,
        )


async def _google_new_identity(
    request: Request, db: Session, google_sub: str, email: str, name: str, picture: OptionalType[str]
):
    """A Google identity with no account yet.

    With answers from /rejestracja in the session the account is created now;
    without them nothing is created - the identity (sub + e-mail) waits in
    the session for 10 minutes and the child finishes the registration at
    /rejestracja?google=1.
    """
    import time as _time

    from .accounts.routes import finish_google_registration

    answers = request.session.pop(SESSION_PENDING_REGISTRATION_KEY, None)
    # The ticket makes the stored answers single-use server-side: a replayed
    # copy of the session cookie falls back to answering again (+ Turnstile)
    if (
        not answers
        or _time.time() - answers.get("at", 0) > PENDING_SESSION_SECONDS
        or not account_service.redeem_registration_ticket(answers.get("ticket"))
    ):
        # Only what the registration needs, and briefly (PENDING_GOOGLE_SECONDS)
        request.session[SESSION_PENDING_GOOGLE_KEY] = {
            "sub": google_sub, "email": email, "at": _time.time()
        }
        return RedirectResponse(url="/rejestracja?google=1", status_code=status.HTTP_303_SEE_OTHER)

    parent_email = answers.get("parent_email")
    if parent_email and account_service.same_mailbox(parent_email, email):
        # The parent's address must not be the child's own Google address
        # (nor an alias of it: dots / +suffix in Gmail)
        request.session[SESSION_PENDING_GOOGLE_KEY] = {
            "sub": google_sub, "email": email, "at": _time.time()
        }
        return RedirectResponse(
            url="/rejestracja?google=1&blad=ten-sam-adres", status_code=status.HTTP_303_SEE_OTHER
        )

    # This identity comes straight from Google in this request: name and
    # picture are used for the new account, then consumed with the answers
    identity = {"sub": google_sub, "email": email, "name": name, "picture": picture}
    result = await finish_google_registration(
        request,
        db,
        identity,
        account_service.AgeAnswers(
            birth_year=answers["birth_year"],
            can_consent_alone=bool(answers.get("can_consent_alone")),
            parent_email=parent_email,
        ),
    )
    if isinstance(result, JSONResponse):
        if result.status_code == 429:
            import json as _json

            error = (
                "rate_limit_registrations_ip"
                if _json.loads(result.body).get("code") == "registration_ip_limit"
                else "rate_limit_new_users"
            )
            return RedirectResponse(url=f"/login?error={error}", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/login?error=oauth_failed", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url=result["redirect"], status_code=status.HTTP_303_SEE_OTHER)


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


@app.post("/logout")
@allow_inactive_account
async def logout(request: Request):
    """Log out (a form POST from the site; the CSRF guard refuses others)."""
    request.session.clear()
    return RedirectResponse(url="/years", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/logout")
async def logout_link(request: Request):
    """Old links and pages cached before logout became a POST. Logs out only
    a navigation started on this site or typed by the user (Sec-Fetch-Site),
    so another site cannot log anyone out with a link or an <img>."""
    if request.headers.get("sec-fetch-site", "").lower() in ("same-origin", "none"):
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
            "has_content": task_info.has_content,
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



@app.post("/task/{year}/{etap}/{num}/submit")
async def submit_solution(
    request: Request,
    year: str,
    etap: str,
    num: int,
    images: list[UploadFile] = File(default=[]),
    solution_text: OptionalType[str] = Form(default=None),
    pattern_id: OptionalType[str] = Form(None),
    hints_used: OptionalType[int] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Submit a solution for analysis (requires group membership).

    A solution is photos (``images``, drawings made in the browser arrive as
    PNG photos), a typed text (``solution_text``, plain text with $LaTeX$) or
    both - at least one of them. Returns immediately with submission_id;
    the client connects to /ws/submissions/{submission_id} for progress.

    ``pattern_id`` (one of the user's patterns) marks the solution as practice
    of that pattern; ``hints_used`` is the number of hints the task page
    revealed (OMJ hints are shown client-side), clamped to the task's hints.
    """
    # Same audience as private tasks and patterns (auth.current_member_id);
    # this legacy endpoint answers {"error"} rather than {"detail"}
    try:
        user_id = await current_member_id(request)
    except HTTPException as e:
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    # Rate limits are skipped for allowlisted users
    allowlisted = is_allowlisted(request)

    # Validate path parameters to prevent directory traversal
    if not _validate_path_params(year, etap):
        return JSONResponse(
            {"error": "Nieprawidłowe parametry"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Normalise the text and check there is something to grade - before any
    # file is written, so a rejected request leaves nothing to clean up.
    solution_text, input_error = validate_submission_input(images, solution_text)
    if input_error is not None:
        return input_error

    # Checked before anything is reserved or written
    task_pdf = get_task_pdf_path(year, etap)
    if not task_pdf or not task_pdf.exists():
        return JSONResponse(
            {"error": "Nie znaleziono pliku z zadaniami"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    from .websocket.progress import progress_manager
    from .websocket.handler import process_submission_background

    # The daily slot is taken before any photo is processed - see
    # reserve_submission. The row is PENDING from here on.
    omj = pattern_service.omj_task(f"{year}_{etap}_{num}")
    hints_available = len(omj.hints) if omj is not None else 0
    limit_error, submission, rate_limit_headers = reserve_submission(
        db,
        user_id,
        allowlisted,
        year=year,
        etap=etap,
        task_number=num,
        pattern_id=pattern_service.owned_pattern_id(db, user_id, pattern_id),
        hints_used=max(0, min(hints_used or 0, hints_available)),
    )
    if limit_error is not None:
        return limit_error
    submission_id = submission.id

    # Save uploaded images (per-user directory structure). The normaliser is
    # resolved through this module at call time - see _normalize_uploaded_image.
    upload_dir = settings.uploads_dir / user_id / year / etap / str(num)
    saved_paths: list = []
    try:
        saved_paths, upload_error = await save_uploaded_images(
            images, upload_dir, normalize=lambda p: _normalize_uploaded_image(p)
        )
        if upload_error is None:
            SubmissionRepository(db).attach_solution(
                submission,
                images=[str(p.relative_to(settings.uploads_dir)) for p in saved_paths],
                solution_text=solution_text,
            )
    except BaseException:
        # Our failure (or a cancelled request), not the student's: no photo
        # stays behind and the slot is given back
        _discard_uploads(saved_paths)
        release_reserved_submission(db, submission_id)
        raise
    if upload_error is not None:
        settle_refused_submission(db, submission, upload_error)
        return upload_error

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
            solution_text=solution_text,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    # Return immediately with submission_id and WebSocket URL
    # Include ws_url so frontend knows where to connect
    ws_path = f"/ws/submissions/{submission.id}"

    return JSONResponse(
        {
            "success": True,
            "submission_id": submission.id,
            "status": "processing",
            "message": "Rozwiązanie przesłane. Połącz się z WebSocket, aby śledzić postęp.",
            "ws_path": ws_path,
        },
        # Already counting this submission - it was reserved
        headers=rate_limit_headers,
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
    from .db.models import SubmissionStatus
    from .websocket.handler import websocket_submission_handler
    from .websocket.progress import progress_manager

    # SessionMiddleware decodes the cookie for WebSockets too, and the app-level
    # current_account dependency has already dropped a stale session (deleted
    # account, password changed), so the regular helper is the whole check.
    user_id = get_current_user_id(websocket)
    if not user_id:
        logger.warning("[WebSocket] No signed-in user in the session")

    # Verify submission exists
    submission_repo = SubmissionRepository(db)
    submission = submission_repo.get_by_id(submission_id)

    if not submission:
        await websocket.close(code=4004, reason="Submission not found")
        return

    # Verify user owns this submission (unless auth disabled)
    if not settings.auth_disabled:
        if not user_id or user_id != submission.user_id:
            logger.warning(
                f"[WebSocket] Auth failed: user_id={mask_user_id(user_id)}, "
                f"submission.user_id={mask_user_id(submission.user_id)}"
            )
            await websocket.close(code=4003, reason="Not authorized")
            return

    # Already graded: answer from the database. The in-memory progress entry
    # is dropped once a completed submission has no listener, and a client
    # that connects late (the task page after "Odczytaj zadanie i oceń")
    # would otherwise wait forever for a result that was already sent.
    if submission.status in (SubmissionStatus.COMPLETED, SubmissionStatus.FAILED):
        from .websocket.messages import CompletedMessage, ErrorMessage

        await websocket.accept()
        if submission.status == SubmissionStatus.COMPLETED:
            message = CompletedMessage(
                submission_id=submission_id,
                score=submission.score or 0,
                feedback=submission.feedback or "",
            )
        else:
            # error_message may hold a raw exception, never shown to the student
            message = ErrorMessage(
                submission_id=submission_id,
                error="Nie udało się ocenić rozwiązania. Spróbuj przesłać je ponownie.",
            )
        await websocket.send_json(message.model_dump())
        await websocket.close()
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
async def serve_upload(request: Request, path: str, db: Session = Depends(get_db)):
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

    # Resolve first, then decide ownership from the RESOLVED path. Checking
    # the raw first segment let "myid/../otherid/..." through to another
    # user's photos. Path format: {user_id}/... (OMJ or private task photos).
    uploads_root = settings.uploads_dir.resolve()
    file_path = (settings.uploads_dir / path).resolve()
    try:
        relative = file_path.relative_to(uploads_root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")
    path_parts = list(relative.parts)

    is_admin = _is_admin(request)
    if not path_parts or (path_parts[0] != user_id and not is_admin):
        raise HTTPException(status_code=403, detail="Forbidden")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Hand back the pooled connection the app-level account check still holds
    # (the same cached session): it would otherwise stay checked out while the
    # file streams, and the admin audit below takes a second one. An admin page
    # loads ~20 photos at once - 15 requests each holding one connection and
    # waiting for another exhausted the pool and all failed after 30 s.
    await asyncio.to_thread(db.close)

    # Admin looking at somebody else's photo - the widest read privilege in the
    # app, so it is audited. Own uploads are not (that is every normal request).
    # Audited here, after validation, so the table records real accesses rather
    # than 404s and rejected traversal attempts.
    if is_admin and path_parts[0] != user_id:
        # The path starts with the owner's user id, which subject_user_id
        # already carries and which must disappear when that account is erased -
        # so only the part below the user directory is stored.
        await _record_admin_access(
            request,
            resource="upload",
            subject_user_id=path_parts[0],
            resource_id="/".join(path_parts[1:])[:255],
        )

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

    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid user session",
        )

    # Delete all submissions for this user
    submission_repo = SubmissionRepository(db)
    deleted_count = submission_repo.delete_all_user_submissions(user_id)

    logger.info(
        f"E2E: Reset {deleted_count} submissions for user {mask_email(user.get('email'))}"
    )

    return {
        "success": True,
        "deleted_count": deleted_count,
        "user_email": user.get("email"),
    }


@app.post("/api/test/reset-user-patterns")
async def reset_user_patterns(request: Request, db: Session = Depends(get_db)):
    """Delete all of the current user's patterns, their exercises and exercise quota (E2E_MODE only)."""
    if not settings.e2e_mode:
        raise HTTPException(status_code=404, detail="Not found")
    user = get_current_user(request)
    if not user or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Authentication required")

    from .db.models import AIUsageDB, PatternDB
    from .patterns.exercises import delete_exercises
    from .patterns.service import KIND_EXERCISES

    patterns = db.query(PatternDB).filter(PatternDB.user_id == user["user_id"]).all()
    for pattern in patterns:
        delete_exercises(db, pattern)
        db.delete(pattern)
    # Every test saves patterns, and each save starts an exercise batch
    db.query(AIUsageDB).filter(AIUsageDB.user_id == user["user_id"], AIUsageDB.kind == KIND_EXERCISES).delete()
    db.commit()
    return {"success": True, "deleted_count": len(patterns)}


@app.post("/api/test/patterns/{pattern_id}/make-due")
async def make_pattern_due(pattern_id: str, request: Request, db: Session = Depends(get_db)):
    """Move one of the current user's patterns to today (E2E_MODE only)."""
    if not settings.e2e_mode:
        raise HTTPException(status_code=404, detail="Not found")
    user = get_current_user(request)
    if not user or not user.get("user_id"):
        raise HTTPException(status_code=401, detail="Authentication required")

    from .db.patterns import PatternRepository
    from .patterns import srs

    pattern = PatternRepository(db).get_owned(pattern_id, user["user_id"])
    if pattern is None:
        raise HTTPException(status_code=404, detail="Not found")
    pattern.due_on = srs.today_warsaw()
    db.commit()
    return {"success": True, "due_on": pattern.due_on.isoformat()}


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


def _public_user(user: OptionalType[dict]) -> OptionalType[dict]:
    """The session user as the frontend sees it (no session bookkeeping)."""
    if not user:
        return None
    return {
        "id": user.get("user_id"),
        "email": user.get("email"),
        "login": user.get("login"),
        "name": user.get("name") or user.get("login") or "",
        "picture": user.get("picture"),
        "is_group_member": bool(user.get("is_group_member")),
    }


@app.get("/api/auth/me")
async def get_current_user_api(
    request: Request,
    db: Session = Depends(get_db),
    account=Depends(current_account),
):
    """Get current user from session (for Next.js frontend).

    ``account`` tells the frontend where the account stands: active, waiting
    for a parent (``pending`` with the masked parent address and the deletion
    date), or missing its year of birth (``needs_profile``).
    """
    user = get_current_user(request)
    return {
        "user": _public_user(user),
        "account": account_service.account_summary(db, account) if account is not None else None,
        "is_authenticated": user is not None,
        "is_admin": _is_admin(request),
        # Whether POST /api/account/delete would work for this session, so the
        # UI does not offer a button that always answers 403 (dev mode, admins)
        "can_delete_account": _can_delete_account(request),
        # Single source of truth for the phrase the confirmation dialog asks for
        "account_delete_confirmation": ACCOUNT_DELETE_CONFIRMATION,
    }


@app.get("/api/years")
async def years_api(request: Request):
    """Get available years (JSON)."""
    years = get_available_years()
    user = get_current_user(request)
    return {
        "years": years,
        "user": _public_user(user),
        "is_authenticated": user is not None,
    }


@app.get("/api/sitemap-data")
async def sitemap_data_api():
    """Return all task identifiers for sitemap generation."""
    tasks = _load_all_tasks()
    years = get_available_years()
    etaps_by_year = {year: get_etaps_for_year(year) for year in years}
    return {
        "years": years,
        "etaps_by_year": etaps_by_year,
        "tasks": [
            {"year": t.year, "etap": t.etap, "number": t.number}
            for t in tasks.values()
        ],
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
        "user": _public_user(user),
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
            # None when the statement has not been generated locally - clients
            # must fall back to the task PDF, see app/storage.py.
            "content": task_info.content,
            "has_content": task_info.has_content,
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
        "user": _public_user(user),
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
        "submissions": [s.student_view() for s in submissions],
        "pdf_links": pdf_links,
        "user": _public_user(user),
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
        "submissions": [s.student_view() for s in submissions],
    }


# ==================== User Submissions (Moje rozwiązania) ====================


def _private_tasks_by_id(db: Session, submissions) -> dict:
    """Private tasks referenced by these submissions, keyed by id (one query)."""
    from .db.models import PrivateTaskDB

    ids = {s.private_task_id for s in submissions if s.private_task_id}
    if not ids:
        return {}
    return {t.id: t for t in db.query(PrivateTaskDB).filter(PrivateTaskDB.id.in_(ids)).all()}


def _get_max_score(etap: str) -> int:
    """Get max score for an etap (3 for etap1, 6 for etap2/3)."""
    return get_max_score(etap)


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

    # Private tasks referenced on this page, in one query
    private_tasks = _private_tasks_by_id(db, db_submissions)

    # Enrich submissions with task metadata
    submissions_list = []
    for sub in db_submissions:
        if sub.private_task_id:
            private_task = private_tasks.get(sub.private_task_id)
            task_title = private_task.title if private_task else "Zadanie prywatne"
            task_categories = (
                [private_task.category] if private_task and private_task.category else []
            )
        else:
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
            "private_task_id": sub.private_task_id,
            "task_title": task_title,
            "task_categories": task_categories,
            "timestamp": ensure_utc(sub.timestamp).isoformat(),
            "status": sub.status.value,
            "score": sub.score,
            "max_score": _get_max_score(sub.etap),
            "feedback": sub.feedback,
            "feedback_preview": feedback_preview,
            "error_message": sub.error_message,
            "images": sub.images or [],
            "solution_text": sub.solution_text,
        })

    return {
        "submissions": submissions_list,
        "stats": stats_dict,
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(submissions_list) < total_count,
    }


# ==================== Account Deletion (RODO art. 17) ====================


def _can_delete_account(request: Request) -> bool:
    """Whether this session may erase its own account.

    Local dev shares one "anonymous" account that is only recreated on restart,
    and admins would lock themselves out of the panel with one stray click.
    """
    if not verify_auth(request) or not get_current_user_id(request):
        return False
    if settings.auth_disabled:
        return False
    return not _is_admin(request)


@app.post("/api/account/delete", response_model=DeleteAccountResponse)
@allow_inactive_account
async def delete_my_account(
    request: Request,
    payload: DeleteAccountRequest,
    db: Session = Depends(get_db),
):
    """Permanently erase the current user's account, submissions and photos.

    RODO art. 17 (right to erasure): a user must be able to do this themselves,
    without writing to an administrator. The session is invalidated afterwards
    so the deleted account cannot keep browsing.
    """
    if not verify_auth(request):
        raise HTTPException(status_code=401, detail="Nieautoryzowany dostęp")

    # Always the *caller's own* id from the session - a user can never name
    # somebody else's account here.
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Nieautoryzowany dostęp")

    # Local dev shares one "anonymous" account that is only recreated on
    # restart; deleting it would break the whole instance.
    if settings.auth_disabled:
        raise HTTPException(
            status_code=403,
            detail="Usuwanie konta jest niedostępne, gdy uwierzytelnianie jest wyłączone (tryb deweloperski).",
        )

    # Admins would lock themselves out of the panel with one stray click, and
    # their account is not a child's account this right was written for.
    if _is_admin(request):
        raise HTTPException(
            status_code=403,
            detail="Konta administratora nie można usunąć w ten sposób. Usuń swój adres z ADMIN_EMAILS i spróbuj ponownie.",
        )

    if payload.confirmation.strip() != ACCOUNT_DELETE_CONFIRMATION:
        raise HTTPException(
            status_code=400,
            detail=f'Aby potwierdzić, wpisz dokładnie: "{ACCOUNT_DELETE_CONFIRMATION}".',
        )

    from .retention import erase_user_data

    # Carry the used quota over the deletion (keyed by the Google identity or
    # the parent's address, so registering again does not reset it)
    from .rate_limits import record_erasure_quota

    record_erasure_quota(db, user_id)

    report = erase_user_data(db, user_id)

    # Invalidate the session (clears the cookie on the response)
    request.session.clear()

    return DeleteAccountResponse(
        success=True,
        deleted_submissions=report.submissions_deleted,
        deleted_files=report.files_deleted,
    )


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
    user_email = (user.get("email") or "").lower()
    return user_email in admin_emails


def _require_admin(request: Request) -> None:
    """Raise 401/403 if not admin."""
    if not verify_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not _is_admin(request):
        raise HTTPException(status_code=403, detail="Admin access required")


def _write_admin_access(
    admin: OptionalType[dict],
    resource: str,
    subject_user_id: OptionalType[str] = None,
    resource_id: OptionalType[str] = None,
) -> None:
    """Blocking audit write on its own short-lived session.

    Deliberately NOT the request's session: the repository commits, and
    committing the request session expires every ORM object the endpoint has
    already loaded. The next attribute access on them would re-SELECT one row at
    a time (N+1), and a row deleted meanwhile would raise ObjectDeletedError -
    a 500 from a read-only admin page because of a bookkeeping write.
    """
    if not admin:
        return

    from .db import SessionLocal

    audit_db = SessionLocal()
    try:
        AdminAccessLogRepository(audit_db).record(
            admin_email=admin.get("email", ""),
            resource=resource,
            subject_user_id=subject_user_id,
            resource_id=resource_id,
            admin_user_id=admin.get("user_id"),
        )
    finally:
        audit_db.close()


async def _record_admin_access(
    request: Request,
    resource: str,
    subject_user_id: OptionalType[str] = None,
    resource_id: OptionalType[str] = None,
) -> None:
    """Write an audit entry for an admin reading somebody else's data.

    RODO art. 5(2): admin access to a child's submissions and photos has to be
    demonstrable after the fact. Access to the admin's own data is skipped -
    that is noise, not an audit event. Never raises: see the repository.

    Runs in a worker thread so the commit does not block the event loop.
    """
    await asyncio.to_thread(
        _write_admin_access,
        get_current_user(request),
        resource,
        subject_user_id,
        resource_id,
    )


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

    # One audit entry per request, not per row - the row count would only add
    # noise, and the filter already records whose data was asked for.
    await _record_admin_access(
        request,
        resource="admin_submissions_list",
        subject_user_id=user_id,
    )

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
    users_by_id = user_repo.get_by_ids(user_ids)

    private_tasks = _private_tasks_by_id(db, db_submissions)

    # Convert to response format with user info
    submissions = []
    for sub in db_submissions:
        user = users_by_id.get(sub.user_id)
        private_task = private_tasks.get(sub.private_task_id) if sub.private_task_id else None
        submissions.append({
            "id": sub.id,
            "user_id": sub.user_id,
            "user_email": (user.email or (f"login: {user.login}" if user.login else None)) if user else None,
            "user_name": user.name if user else None,
            "year": sub.year,
            "etap": sub.etap,
            "task_number": sub.task_number,
            "private_task_id": sub.private_task_id,
            "task_title": private_task.title if private_task else None,
            "timestamp": ensure_utc(sub.timestamp).isoformat(),
            "status": sub.status.value,
            "images": sub.images,
            "solution_text": sub.solution_text,
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

    # Recorded unconditionally, including zero results: an admin probing for an
    # address that is not in the database is exactly the access worth having a
    # trace of, and a gap in the trail undermines the point of the table.
    # The query itself is a fragment of somebody's e-mail, so it is NOT stored -
    # only the fact that a search happened and how many people it surfaced.
    await _record_admin_access(
        request,
        resource="admin_user_search",
        resource_id=f"{len(users)} results",
    )

    return {
        "users": [
            {
                "id": user.id,
                # Login accounts have no e-mail; the admin picker shows the login
                "email": user.email or (f"login: {user.login}" if user.login else ""),
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
        "user": _public_user(user),
        "is_authenticated": user is not None,
        "is_admin": _is_admin(request),
    }


# A real round trip to the model; longer than any sane ping, shorter than a proxy timeout.
AI_CONFIG_PING_TIMEOUT_SECONDS = 35

ANTHROPIC_NOT_APPROVED_DETAIL = (
    "Dostawca Anthropic nie jest jeszcze zatwierdzony jako podmiot przetwarzający "
    "(ANTHROPIC_PROCESSOR_APPROVED)."
)


def _active_model_out(active: "ai_config_store.ActiveModel") -> AiActiveModel:
    info = models_catalog.get_model(active.provider, active.model)
    return AiActiveModel(
        provider=active.provider,
        model=active.model,
        model_label=info.label if info else active.model,
        source=active.source,
        updated_at=ensure_utc(active.updated_at) if active.updated_at else None,
        updated_by=active.updated_by,
    )


def _effective_model_out(effective: "ai_config_store.ActiveModel") -> AiEffectiveModel:
    info = models_catalog.get_model(effective.provider, effective.model)
    return AiEffectiveModel(
        provider=effective.provider,
        model=effective.model,
        model_label=info.label if info else effective.model,
    )


@app.get("/api/admin/ai-config", response_model=AiConfigResponse)
async def admin_get_ai_config(request: Request):
    """Stored and effective AI provider/model and the selectable catalog (admin only). Never exposes keys."""
    _require_admin(request)
    active = await asyncio.to_thread(ai_config_store.get_active_model)
    effective, fallback_reason = ai_factory.resolve_active(active)
    providers = [
        AiProviderOption(
            id=provider,
            label=models_catalog.PROVIDER_LABELS[provider],
            configured=models_catalog.provider_configured(provider),
            approved=models_catalog.provider_approved(provider),
            models=[AiModelOption(id=m.id, label=m.label) for m in models_catalog.models_for(provider)],
        )
        for provider in models_catalog.PROVIDERS
    ]
    return AiConfigResponse(
        active=_active_model_out(active),
        effective=_effective_model_out(effective),
        fallback_reason=fallback_reason,
        providers=providers,
        failover=ai_factory.failover_status(effective),
    )


@app.put("/api/admin/ai-config", response_model=AiConfigUpdateResponse)
async def admin_put_ai_config(
    request: Request,
    body: AiConfigUpdateRequest,
    db: Session = Depends(get_db),
):
    """Switch the AI provider/model for new AI calls (admin only).

    Nothing is stored unless the model answers a ping, so a typo or a dead key
    can never leave grading pointed at a model that does not work.
    """
    _require_admin(request)
    provider, model = body.provider, body.model
    if models_catalog.get_model(provider, model) is None:
        raise HTTPException(status_code=400, detail="Nieznany model.")
    if not models_catalog.provider_configured(provider):
        raise HTTPException(status_code=409, detail="Brak klucza API dla tego dostawcy.")
    if not models_catalog.provider_approved(provider):
        raise HTTPException(status_code=409, detail=ANTHROPIC_NOT_APPROVED_DETAIL)

    try:
        candidate = ai_factory.build_provider(provider, model)
        await asyncio.wait_for(candidate.ping(), AI_CONFIG_PING_TIMEOUT_SECONDS)
    except AIProviderError as e:
        logger.warning(f"[AI config] Ping of {provider}/{model} failed: {type(e).__name__}")
        raise HTTPException(status_code=502, detail=str(e))
    except asyncio.TimeoutError:
        logger.warning(f"[AI config] Ping of {provider}/{model} timed out")
        raise HTTPException(
            status_code=502,
            detail=f"Model {model} nie odpowiedział w ciągu {AI_CONFIG_PING_TIMEOUT_SECONDS} s.",
        )
    except Exception as e:
        logger.error(f"[AI config] Ping of {provider}/{model} raised {type(e).__name__}")
        raise HTTPException(status_code=502, detail=f"Nie udało się sprawdzić modelu {model}.")

    old = await asyncio.to_thread(ai_config_store.get_active_model)
    user = get_current_user(request) or {}
    email = user.get("email")
    active = ai_config_store.set_active_model(db, provider, model, email)
    # The pinged client serves the first real call (no client build on the event loop)
    ai_factory.remember(provider, model, candidate)
    logger.info(f"AI model changed: {old.provider}/{old.model} -> {provider}/{model} by {mask_email(email)}")
    effective, fallback_reason = ai_factory.resolve_active(active)
    return AiConfigUpdateResponse(
        active=_active_model_out(active),
        effective=_effective_model_out(effective),
        fallback_reason=fallback_reason,
        failover=ai_factory.failover_status(effective),
    )


@app.post("/api/admin/submissions/{submission_id}/rerun")
async def admin_rerun_submission(
    request: Request,
    submission_id: str,
    db: Session = Depends(get_db),
):
    """Re-run AI scoring for an existing submission (admin only).

    Creates a new submission reusing the original's images and typed text
    and dispatches the background worker, leaving the original submission
    untouched.
    """
    _require_admin(request)

    submission_repo = SubmissionRepository(db)

    original = submission_repo.get_by_id(submission_id)
    if not original:
        raise HTTPException(status_code=404, detail="Submission not found")

    await _record_admin_access(
        request,
        resource="admin_submission_rerun",
        subject_user_id=original.user_id,
        resource_id=submission_id,
    )

    # Reconstruct absolute image paths from stored relative paths
    relative_images = original.images or []
    if not relative_images and not original.solution_text:
        raise HTTPException(
            status_code=409,
            detail="Submission has no images or text to re-run",
        )

    image_paths = [settings.uploads_dir / rel for rel in relative_images]
    missing = [str(rel) for rel, p in zip(relative_images, image_paths) if not p.exists()]
    if missing:
        raise HTTPException(
            status_code=409,
            detail=f"Image files no longer available on disk: {', '.join(missing)}",
        )

    # Private task: re-grade against the text the original was graded against
    private_task = None
    if original.private_task_id:
        snapshot = (original.scoring_meta or {}).get("task_snapshot") or {}
        task_row = original.private_task
        title = snapshot.get("title") or (task_row.title if task_row else None)
        content = snapshot.get("content") or (task_row.content if task_row else None)
        if not content:
            raise HTTPException(status_code=409, detail="Private task text no longer available")
        private_task = {"id": original.private_task_id, "title": title or "", "content": content}
    else:
        # Validate task PDF exists (same check as submit endpoint)
        task_pdf = get_task_pdf_path(original.year, original.etap)
        if not task_pdf or not task_pdf.exists():
            raise HTTPException(
                status_code=409,
                detail="Nie znaleziono pliku z zadaniami",
            )

    from .db.models import SubmissionStatus
    from .websocket.progress import progress_manager
    from .websocket.handler import process_submission_background

    new_id = str(uuid.uuid4())[:8]

    submission_repo.create(
        id=new_id,
        user_id=original.user_id,
        year=original.year,
        etap=original.etap,
        task_number=original.task_number,
        images=list(relative_images),
        solution_text=original.solution_text,
        status=SubmissionStatus.PENDING,
        private_task_id=original.private_task_id,
        hints_used=original.hints_used or 0,
    )

    # Initialize progress tracking (handler.py will set first status)
    await progress_manager.create_submission(new_id)

    # Start background task for AI processing with proper lifecycle tracking
    task = asyncio.create_task(
        process_submission_background(
            submission_id=new_id,
            user_id=original.user_id,
            year=original.year,
            etap=original.etap,
            task_number=original.task_number,
            image_paths=image_paths,
            private_task=private_task,
            solution_text=original.solution_text,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {
        "success": True,
        "submission_id": new_id,
        "status": "pending",
    }
