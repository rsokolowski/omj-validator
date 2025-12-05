import re
import secrets
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .auth import AUTH_COOKIE_NAME, verify_auth, require_auth_redirect, _get_session_token
from .storage import (
    load_tasks_index,
    load_tasks_data,
    get_task,
    get_task_key,
    get_task_pdf_path,
    get_solution_pdf_path,
    get_task_stats,
    load_submissions,
    create_submission,
)
from .claude_client import analyze_solution

app = FastAPI(title="OMJ Validator", description="Walidator rozwiązań OMJ")

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
    """Display login page."""
    if verify_auth(request):
        return RedirectResponse(url="/years", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    request: Request,
    key: Annotated[str, Form()],
    remember: Annotated[bool, Form()] = False,
):
    """Process login form."""
    if not secrets.compare_digest(key, settings.auth_key):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Nieprawidłowy klucz dostępu"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse(url="/years", status_code=status.HTTP_303_SEE_OTHER)

    # Set cookie with derived session token (not raw key)
    max_age = 30 * 24 * 60 * 60 if remember else None
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=_get_session_token(),
        max_age=max_age,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
async def logout():
    """Log out user."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


# --- Main Routes ---


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect to years or login."""
    if verify_auth(request):
        return RedirectResponse(url="/years", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/years", response_class=HTMLResponse)
async def years_page(request: Request):
    """Display available years."""
    redirect = require_auth_redirect(request)
    if redirect:
        return redirect

    index = load_tasks_index()
    years = sorted(index.keys(), reverse=True)

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "years": years},
    )


@app.get("/years/{year}", response_class=HTMLResponse)
async def year_detail(request: Request, year: str):
    """Display etaps for a year."""
    redirect = require_auth_redirect(request)
    if redirect:
        return redirect

    index = load_tasks_index()
    if year not in index:
        raise HTTPException(status_code=404, detail="Rok nie znaleziony")

    etaps = list(index[year].keys())

    return templates.TemplateResponse(
        "year.html",
        {"request": request, "year": year, "etaps": etaps},
    )


@app.get("/years/{year}/{etap}", response_class=HTMLResponse)
async def etap_detail(request: Request, year: str, etap: str):
    """Display tasks for a year/etap with stats."""
    redirect = require_auth_redirect(request)
    if redirect:
        return redirect

    index = load_tasks_index()
    if year not in index or etap not in index[year]:
        raise HTTPException(status_code=404, detail="Etap nie znaleziony")

    tasks_data = load_tasks_data()

    # Build task list with stats
    tasks = []
    for num in range(1, 6):  # Tasks 1-5
        key = get_task_key(year, etap, num)
        task_info = tasks_data.get(key)
        stats = get_task_stats(year, etap, num)

        tasks.append(
            {
                "number": num,
                "title": task_info.title if task_info else f"Zadanie {num}",
                "has_content": task_info is not None,
                "submission_count": stats.submission_count,
                "highest_score": stats.highest_score,
            }
        )

    return templates.TemplateResponse(
        "etap.html",
        {"request": request, "year": year, "etap": etap, "tasks": tasks},
    )


@app.get("/task/{year}/{etap}/{num}", response_class=HTMLResponse)
async def task_detail(request: Request, year: str, etap: str, num: int):
    """Display task detail with submission form."""
    redirect = require_auth_redirect(request)
    if redirect:
        return redirect

    task = get_task(year, etap, num)
    if not task:
        raise HTTPException(status_code=404, detail="Zadanie nie znalezione")

    stats = get_task_stats(year, etap, num)
    submissions = load_submissions(year, etap, num)

    return templates.TemplateResponse(
        "task.html",
        {
            "request": request,
            "task": task,
            "stats": stats,
            "submissions": submissions[:10],  # Last 10 submissions
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
    images: list[UploadFile] = File(...),
):
    """Submit solution images for analysis."""
    redirect = require_auth_redirect(request)
    if redirect:
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

        saved_paths.append(file_path)

    # Get PDF paths
    task_pdf = get_task_pdf_path(year, etap)
    solution_pdf = get_solution_pdf_path(year, etap)

    if not task_pdf or not task_pdf.exists():
        return JSONResponse(
            {"error": "Nie znaleziono pliku z zadaniami"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Analyze with Claude
    result = await analyze_solution(
        task_pdf_path=task_pdf,
        solution_pdf_path=solution_pdf,
        image_paths=saved_paths,
        task_number=num,
    )

    # Save submission
    submission = create_submission(
        year=year,
        etap=etap,
        task_number=num,
        images=[str(p.relative_to(settings.base_dir)) for p in saved_paths],
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
    """Display submission history for a task."""
    redirect = require_auth_redirect(request)
    if redirect:
        return redirect

    task = get_task(year, etap, num)
    submissions = load_submissions(year, etap, num)

    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "task": task,
            "year": year,
            "etap": etap,
            "num": num,
            "submissions": submissions,
        },
    )


# --- Static file serving for uploads ---


@app.get("/uploads/{path:path}")
async def serve_upload(request: Request, path: str):
    """Serve uploaded files (with auth check)."""
    redirect = require_auth_redirect(request)
    if redirect:
        raise HTTPException(status_code=401, detail="Unauthorized")

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
