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

from .config import settings
from .auth import (
    SESSION_USER_KEY,
    verify_auth,
    require_auth_redirect,
    get_current_user,
    is_group_member,
)
from .oauth import oauth
from .groups import check_group_membership

logger = logging.getLogger(__name__)
from .storage import (
    get_available_years,
    get_etaps_for_year,
    get_tasks_for_etap,
    get_task,
    get_task_pdf_path,
    get_solution_pdf_path,
    get_task_stats,
    load_submissions,
    create_submission,
)
from .ai import create_ai_provider, AIProviderError
from .models import SubmissionResult

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


# --- Authentication Routes ---


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
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
        },
    )


@app.get("/login/google")
async def google_login(request: Request):
    """Initiate Google OAuth flow."""
    if not settings.google_client_id:
        return RedirectResponse(
            url="/login?error=oauth_not_configured",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    redirect_uri = request.url_for("google_auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/callback")
async def google_auth_callback(request: Request):
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

        # Check Google Group membership
        is_member = await check_group_membership(user_info["email"])

        # Store user in session
        request.session[SESSION_USER_KEY] = {
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

        return RedirectResponse(url="/years", status_code=status.HTTP_303_SEE_OTHER)

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


@app.get("/years/{year}/{etap}", response_class=HTMLResponse)
async def etap_detail(request: Request, year: str, etap: str):
    """Display tasks for a year/etap (public). Stats shown only to group members."""
    etap_tasks = get_tasks_for_etap(year, etap)
    if not etap_tasks:
        raise HTTPException(status_code=404, detail="Etap nie znaleziony")

    user = get_current_user(request)
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
        if can_see_stats:
            stats = get_task_stats(year, etap, task_info.number)
            task_data["submission_count"] = stats.submission_count
            task_data["highest_score"] = stats.highest_score
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
async def task_detail(request: Request, year: str, etap: str, num: int):
    """Display task detail (public). Submission form, stats, and history only for group members."""
    task = get_task(year, etap, num)
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie nie znalezione")

    user = get_current_user(request)
    can_submit = is_group_member(request)

    # Stats and submissions only for group members
    stats = None
    submissions = []
    if can_submit:
        stats = get_task_stats(year, etap, num)
        submissions = load_submissions(year, etap, num)[:10]

    # Get PDF paths for links
    task_pdf = get_task_pdf_path(year, etap)
    solution_pdf = get_solution_pdf_path(year, etap)

    pdf_links = {}
    if task_pdf and task_pdf.exists():
        pdf_links["tasks"] = f"/pdf/{year}/{etap}/{task_pdf.name}"
    if solution_pdf and solution_pdf.exists():
        pdf_links["solutions"] = f"/pdf/{year}/{etap}/{solution_pdf.name}"

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

    # Save uploaded images
    upload_dir = settings.uploads_dir / year / etap / str(num)
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
    try:
        provider = create_ai_provider()
        result = await provider.analyze_solution(
            task_pdf_path=task_pdf,
            solution_pdf_path=solution_pdf,
            image_paths=saved_paths,
            task_number=num,
            etap=etap,
        )
    except AIProviderError as e:
        result = SubmissionResult(
            score=0,
            feedback=f"Błąd konfiguracji AI: {str(e)}",
        )
    except Exception as e:
        result = SubmissionResult(
            score=0,
            feedback=f"Nieoczekiwany błąd: {str(e)}",
        )

    # Save submission (store image paths relative to uploads_dir for clean URLs)
    submission = create_submission(
        year=year,
        etap=etap,
        task_number=num,
        images=[str(p.relative_to(settings.uploads_dir)) for p in saved_paths],
        score=result.score,
        feedback=result.feedback,
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
async def task_history(request: Request, year: str, etap: str, num: int):
    """Display submission history for a task (requires group membership)."""
    # Require group membership to view history
    if not verify_auth(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not is_group_member(request):
        return RedirectResponse(url="/auth/limited", status_code=status.HTTP_303_SEE_OTHER)

    task = get_task(year, etap, num)
    submissions = load_submissions(year, etap, num)
    user = get_current_user(request)

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
    """Serve uploaded files (with auth check)."""
    redirect = require_auth_redirect(request)
    if redirect:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Handle legacy paths that include 'uploads/' prefix (from old submissions)
    if path.startswith("uploads/"):
        path = path[8:]  # Strip 'uploads/' prefix

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
