import logging
import re
import uuid
from pathlib import Path

# Configure logging to show INFO level for app modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, status
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
)
from .oauth import oauth
from .groups import check_group_membership
from .db import get_db, UserRepository, SubmissionRepository

logger = logging.getLogger(__name__)
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

# Add session middleware for OAuth
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    max_age=30 * 24 * 60 * 60,  # 30 days
    https_only=not settings.auth_disabled,  # Require HTTPS in production
    same_site="lax",  # CSRF protection
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

        # Create or update user in database
        user_repo = UserRepository(db)
        user_repo.create_or_update(
            google_sub=google_sub,
            email=user_info["email"],
            name=user_info.get("name", ""),
        )

        # Check Google Group membership
        is_member = await check_group_membership(user_info["email"])

        # Get the return URL before modifying session
        next_url = request.session.pop("login_next", None)

        # Store user in session (including google_sub for user identification)
        request.session[SESSION_USER_KEY] = {
            "google_sub": google_sub,
            "email": user_info["email"],
            "name": user_info.get("name", ""),
            "picture": user_info.get("picture"),
            "is_group_member": is_member,
        }

        logger.info(
            f"User logged in: {user_info['email']} (group member: {is_member})"
        )

        # Redirect to limited access page if not a group member
        if not is_member:
            return RedirectResponse(
                url="/auth/limited", status_code=status.HTTP_303_SEE_OTHER
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
    can_view_progress = is_group_member(request)
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
    can_view_progress = is_group_member(request)

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

        return JSONResponse(progress.model_dump(mode="json"))

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
    can_see_stats = is_group_member(request)

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
    can_submit = is_group_member(request)

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

    # Load prerequisite statuses (only for group members who can see progress)
    prerequisite_statuses = []
    if can_submit and task.prerequisites and user_id:
        progress = compute_user_progress(user_id=user_id, db=db)
        prerequisite_statuses = get_prerequisite_statuses(task.prerequisites, progress)

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
    """Submit solution images for analysis (requires group membership)."""
    # Check if user is authenticated
    if not verify_auth(request):
        return JSONResponse(
            {"error": "Nieautoryzowany dostęp"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Check if user is a group member
    if not is_group_member(request):
        return JSONResponse(
            {"error": "Dostęp wymaga członkostwa w grupie omj-validator-alpha"},
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Get user ID from session
    user_id = get_current_user_id(request)
    if not user_id:
        return JSONResponse(
            {"error": "Nieautoryzowany dostęp"},
            status_code=status.HTTP_401_UNAUTHORIZED,
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

    # Get PDF paths
    task_pdf = get_task_pdf_path(year, etap)
    solution_pdf = get_solution_pdf_path(year, etap)

    if not task_pdf or not task_pdf.exists():
        return JSONResponse(
            {"error": "Nie znaleziono pliku z zadaniami"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Analyze with AI provider (etap-specific scoring: etap1=0/1/3, etap2=0/2/5/6)
    from .db.models import SubmissionStatus
    submission_id = str(uuid.uuid4())[:8]
    error_message = None
    scoring_meta = None

    try:
        provider = create_ai_provider()
        result = await provider.analyze_solution(
            task_pdf_path=task_pdf,
            solution_pdf_path=solution_pdf,
            image_paths=saved_paths,
            task_number=num,
            etap=etap,
        )
        submission_status = SubmissionStatus.COMPLETED
        scoring_meta = result.scoring_meta
    except AIProviderError as e:
        result = SubmissionResult(
            score=0,
            feedback=f"Błąd konfiguracji AI: {str(e)}",
        )
        submission_status = SubmissionStatus.FAILED
        error_message = str(e)
    except Exception as e:
        result = SubmissionResult(
            score=0,
            feedback=f"Nieoczekiwany błąd: {str(e)}",
        )
        submission_status = SubmissionStatus.FAILED
        error_message = str(e)

    # Save submission to database (store image paths relative to uploads_dir)
    submission_repo = SubmissionRepository(db)
    submission = submission_repo.create(
        id=submission_id,
        user_id=user_id,
        year=year,
        etap=etap,
        task_number=num,
        images=[str(p.relative_to(settings.uploads_dir)) for p in saved_paths],
        score=result.score,
        feedback=result.feedback,
        status=submission_status,
        error_message=error_message,
        scoring_meta=scoring_meta,
    )

    return JSONResponse(
        {
            "success": True,
            "submission_id": submission.id,
            "score": result.score,
            "feedback": result.feedback,
        }
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

    if not is_group_member(request):
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
    # Path format: {user_id}/{year}/{etap}/{task_num}/{filename}
    path_parts = path.split("/")
    if len(path_parts) < 1 or path_parts[0] != user_id:
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


# --- JSON API Endpoints for Next.js Frontend ---


@app.get("/api/auth/me")
async def get_current_user_api(request: Request):
    """Get current user from session (for Next.js frontend)."""
    user = get_current_user(request)
    return {"user": user, "is_authenticated": user is not None}


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
    can_see_stats = is_group_member(request)

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
    can_submit = is_group_member(request)

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
    if can_submit and task.prerequisites and user_id:
        progress = compute_user_progress(user_id=user_id, db=db)
        prerequisite_statuses = get_prerequisite_statuses(task.prerequisites, progress)

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
    if not is_group_member(request):
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
