"""HTTP API for private tasks ("Moje zadania").

Every route requires a signed-in user with submit rights (same audience as OMJ
grading). A task id that does not exist and one that belongs to somebody else
both answer 404, so the API never confirms that another user's task exists.

Every AI call is counted before it is made - a failed call still costs Gemini
money, so it still counts toward the daily limits.
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..ai import AIContentBlockedError, AIProviderError, create_ai_provider
from ..auth import get_current_user, get_current_user_id, is_group_member_async, verify_auth
from ..config import settings
from ..db import get_db
from ..db.models import PrivateTaskDB, SubmissionStatus
from ..db.private_tasks import (
    CREATION_KINDS,
    KIND_CREATE,
    KIND_EXTRACT,
    KIND_REGEN,
    AIUsageRepository,
    HintOrderError,
    PrivateTaskRepository,
    new_private_task_id,
)
from ..db.repositories import SubmissionRepository, ensure_utc
from ..groups import _get_allowed_emails
from ..patterns.service import owned_pattern_id
from ..models import (
    CreatePrivateTasksRequest,
    PrivateTaskInput,
    PrivateTaskMeta,
    UpdatePrivateTaskRequest,
)
from ..privacy import mask_user_id
from ..rate_limits import calculate_rate_limit_headers, check_submission_limits
from ..uploads import discard_uploads, save_uploaded_images, validate_image_batch
from ..websocket.handler import process_submission_background
from ..websocket.progress import progress_manager
from . import service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/private-tasks", tags=["private-tasks"])

# Grading runs as fire-and-forget tasks; keep references so they are not GC'd
_background_tasks: set[asyncio.Task] = set()

NOT_FOUND = "Nie znaleziono zadania"
REFUSED_TEXT = "Nie udało się zapisać zadania. Sprawdź, czy tekst zawiera tylko treść zadania."


# --------------------------------------------------------------------- helpers


async def current_member_id(request: Request) -> str:
    """Signed-in user with submit rights, or 401/403."""
    if not verify_auth(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieautoryzowany dostęp")
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieautoryzowany dostęp")
    if not await is_group_member_async(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nie masz uprawnień do tej funkcji.",
        )
    return user_id


def _is_allowlisted(request: Request) -> bool:
    allowed = _get_allowed_emails()
    user = get_current_user(request)
    email = (user or {}).get("email", "").lower()
    return bool(allowed and email in allowed)


def _owned_task(db: Session, task_id: str, user_id: str) -> PrivateTaskDB:
    if not service.TASK_ID_PATTERN.match(task_id or ""):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    task = PrivateTaskRepository(db).get_owned(task_id, user_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return task


def _abusive(score: int) -> bool:
    return score >= settings.private_abuse_threshold


def serialize_task(task: PrivateTaskDB) -> dict:
    """Full task for its owner - revealed hints only, never the rest."""
    hints = task.hints or []
    revealed = min(task.hints_revealed or 0, len(hints))
    return {
        "id": task.id,
        "title": task.title,
        "content": task.content,
        "source_label": task.source_label,
        "category": task.category,
        "difficulty": task.difficulty,
        "origin": task.origin,
        "source_images": task.source_images or [],
        "hints_count": len(hints),
        "revealed_hints": hints[:revealed],
        "created_at": ensure_utc(task.created_at).isoformat(),
        "last_activity_at": ensure_utc(task.last_activity_at).isoformat(),
    }


def serialize_summary(row: dict) -> dict:
    task: PrivateTaskDB = row["task"]
    return {
        "id": task.id,
        "title": task.title,
        "source_label": task.source_label,
        "category": task.category,
        "difficulty": task.difficulty,
        "origin": task.origin,
        "best_score": row["best_score"],
        "attempts": row["attempts"],
        "last_activity_at": ensure_utc(task.last_activity_at).isoformat(),
    }


async def _generate_meta(provider, user_id: str, item: PrivateTaskInput) -> Optional[PrivateTaskMeta]:
    """Hints for one task, or None when the call failed (task is still saved).

    A safety block is NOT a failure to shrug off: it propagates, and the caller
    refuses to save the text, because that text was never abuse-checked.
    """
    try:
        return await provider.generate_private_task_meta(item.title, item.content)
    except AIContentBlockedError:
        raise
    except AIProviderError as e:
        logger.warning(f"Hint generation failed for user {mask_user_id(user_id)}: {e}")
        return None
    except Exception as e:  # never lose the student's task over a hint call
        logger.exception(f"Hint generation crashed for user {mask_user_id(user_id)}: {type(e).__name__}")
        return None


# --------------------------------------------------------------------- extract


@router.post("/extract")
async def extract_tasks(
    request: Request,
    images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    """Read problem statements off photos. Returns a draft; nothing is saved yet."""
    user_id = await current_member_id(request)
    batch_error = validate_image_batch(images)
    if batch_error is not None:
        return batch_error

    # Reserved before the photos are written: a refused request leaves nothing
    [usage_row] = service.reserve_ai_calls(
        db,
        user_id,
        KIND_EXTRACT,
        {KIND_EXTRACT},
        settings.rate_limit_private_extracts_per_user_per_day,
        _is_allowlisted(request),
    )

    draft_id = service.new_draft_id()
    saved, upload_error = await save_uploaded_images(images, service.draft_dir(user_id, draft_id))
    if upload_error is not None:
        service.discard_draft(user_id, draft_id)
        return upload_error

    def fail(code: int, message: str):
        discard_uploads(saved)
        service.discard_draft(user_id, draft_id)
        raise HTTPException(status_code=code, detail=message)

    try:
        result = await create_ai_provider().extract_private_tasks(saved)
    except AIProviderError as e:
        fail(status.HTTP_502_BAD_GATEWAY, str(e))
    except Exception:
        logger.exception("Private task extraction crashed")
        fail(status.HTTP_502_BAD_GATEWAY, "Przepraszamy, coś poszło nie tak. Spróbuj ponownie za chwilę.")

    usage_row.meta = result.meta or None
    db.commit()

    if _abusive(result.abuse_score):
        logger.warning(f"Extraction flagged as manipulation (score {result.abuse_score}) for user {mask_user_id(user_id)}")
        fail(
            422,
            "Nie udało się odczytać zadania. Upewnij się, że zdjęcie zawiera tylko treść zadania.",
        )
    if not result.is_math_problem or not result.problems:
        fail(
            422,
            "Na zdjęciu nie znaleziono treści zadania matematycznego. "
            "Zrób wyraźniejsze zdjęcie albo wpisz treść ręcznie.",
        )

    return {
        "draft_id": draft_id,
        "problems": [p.model_dump() for p in result.problems],
        "photos": [service.relative_upload_path(p) for p in saved],
    }


# ---------------------------------------------------------------------- create


async def _create_from_inputs(
    db: Session,
    user_id: str,
    items: list[PrivateTaskInput],
    photos: list[Path],
    usage_rows: list,
) -> list[PrivateTaskDB]:
    """Generate hints for each task, refuse manipulation, then save them all."""
    provider = create_ai_provider()
    try:
        metas = await asyncio.gather(*(_generate_meta(provider, user_id, item) for item in items))
    except AIContentBlockedError:
        raise HTTPException(status_code=422, detail=REFUSED_TEXT)
    for row, meta in zip(usage_rows, metas):
        row.meta = meta.meta if meta and meta.meta else None
    db.commit()

    if any(meta is not None and _abusive(meta.abuse_score) for meta in metas):
        logger.warning(f"Private task text flagged as manipulation for user {mask_user_id(user_id)}")
        raise HTTPException(status_code=422, detail=REFUSED_TEXT)

    repo = PrivateTaskRepository(db)
    created = []
    for item, meta in zip(items, metas):
        task_id = new_private_task_id()
        source_images = service.copy_photos_to_task(photos, user_id, task_id) if photos else []
        created.append(
            repo.create(
                user_id,
                task_id=task_id,
                title=item.title,
                content=item.content,
                source_label=item.source_label,
                category=item.category or (meta.category if meta else None),
                difficulty=item.difficulty or (meta.difficulty if meta else None),
                hints=meta.hints if meta else [],
                origin="photo" if photos else "typed",
                source_images=source_images,
                extraction_meta={"hints": meta.meta} if meta and meta.meta else None,
            )
        )
    return created


@router.post("")
async def create_tasks(
    request: Request,
    payload: CreatePrivateTasksRequest,
    db: Session = Depends(get_db),
):
    """Save confirmed drafts (photo) or typed tasks, generating hints for each."""
    user_id = await current_member_id(request)

    photos: list[Path] = []
    claimed: Optional[Path] = None
    if payload.draft_id:
        claim = service.claim_draft(user_id, payload.draft_id)
        if claim is None:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Ten szkic wygasł albo został już zapisany. Prześlij zdjęcie ponownie.",
            )
        claimed, photos = claim

    try:
        usage_rows = service.reserve_ai_calls(
            db,
            user_id,
            KIND_CREATE,
            CREATION_KINDS,
            settings.rate_limit_private_tasks_per_user_per_day,
            _is_allowlisted(request),
            cost=len(payload.tasks),
        )
        created = await _create_from_inputs(db, user_id, payload.tasks, photos, usage_rows)
    except BaseException:
        # Refused (abuse, crash, client gone): the student can confirm again
        if claimed is not None:
            service.release_draft(claimed, user_id, payload.draft_id)
        raise

    if claimed is not None:
        service.discard_claimed_draft(claimed)

    return {"tasks": [serialize_task(t) for t in created]}


# ------------------------------------------------------------ read/edit/delete


@router.get("")
async def list_tasks(
    request: Request,
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    user_id = await current_member_id(request)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    rows, total = PrivateTaskRepository(db).list_for_user(user_id, offset=offset, limit=limit)
    return {
        "tasks": [serialize_summary(row) for row in rows],
        "total_count": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(rows) < total,
    }


@router.get("/{task_id}")
async def get_task_detail(request: Request, task_id: str, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    task = _owned_task(db, task_id, user_id)

    submission_repo = SubmissionRepository(db)
    submissions = sorted(task.submissions, key=lambda s: s.timestamp, reverse=True)
    # Same stale-row cleanup the OMJ history applies
    submission_repo._mark_stale_submissions_failed(submissions)
    completed = [s.score for s in submissions if s.status == SubmissionStatus.COMPLETED and s.score is not None]

    return {
        "task": serialize_task(task),
        "submissions": [
            submission_repo.to_pydantic(s).model_dump(mode="json", exclude={"scoring_meta"})
            for s in submissions
        ],
        "stats": {
            "submission_count": len(submissions),
            "highest_score": max(completed) if completed else None,
        },
    }


@router.patch("/{task_id}")
async def update_task(
    request: Request,
    task_id: str,
    payload: UpdatePrivateTaskRequest,
    db: Session = Depends(get_db),
):
    user_id = await current_member_id(request)
    task = _owned_task(db, task_id, user_id)

    fields = payload.model_dump(exclude_unset=True)
    if "source_label" in fields:
        label = (fields["source_label"] or "").strip()
        fields["source_label"] = label or None
    for required in ("title", "content"):
        if required in fields and fields[required] is None:
            del fields[required]

    if "content" in fields and fields["content"] != task.content:
        # New text goes into the grading prompt, so it gets the same check as
        # at creation - and the old hints no longer fit it anyway.
        [usage_row] = service.reserve_ai_calls(
            db,
            user_id,
            KIND_REGEN,
            CREATION_KINDS,
            settings.rate_limit_private_tasks_per_user_per_day,
            _is_allowlisted(request),
        )
        item = PrivateTaskInput(title=fields.get("title", task.title), content=fields["content"])
        try:
            meta = await _generate_meta(create_ai_provider(), user_id, item)
        except AIContentBlockedError:
            raise HTTPException(status_code=422, detail=REFUSED_TEXT)
        if meta is not None:
            usage_row.meta = meta.meta or None
            db.commit()
            if _abusive(meta.abuse_score):
                logger.warning(f"Edited private task text flagged for user {mask_user_id(user_id)}")
                raise HTTPException(status_code=422, detail=REFUSED_TEXT)
        # Failed call: keep the edit, drop the stale hints ("Wygeneruj wskazówki")
        fields["hints"] = meta.hints if meta is not None else []

    PrivateTaskRepository(db).update_fields(task, **fields)
    return {"task": serialize_task(task)}


@router.delete("/{task_id}")
async def delete_task(request: Request, task_id: str, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    task = _owned_task(db, task_id, user_id)
    submissions = len(task.submissions)

    # Row first, files second: a failed unlink leaves orphans the retention
    # sweep removes; the other order could leave a task whose photos are gone.
    PrivateTaskRepository(db).delete(task)
    report = service.delete_task_files(task)
    logger.info(
        f"Deleted private task {task_id} of user {mask_user_id(user_id)}: "
        f"{submissions} submissions, {report.files_deleted} files"
    )
    return {"success": True, "deleted_submissions": submissions, "deleted_files": report.files_deleted}


# ----------------------------------------------------------------------- hints


@router.post("/{task_id}/hints/{n}")
async def reveal_hint(request: Request, task_id: str, n: int, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    task = _owned_task(db, task_id, user_id)
    try:
        hint = PrivateTaskRepository(db).reveal_hint(task, n)
    except IndexError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nie ma takiej wskazówki")
    except HintOrderError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Najpierw odkryj poprzednią wskazówkę.",
        )
    return {"n": n, "hint": hint, "hints_revealed": task.hints_revealed}


@router.post("/{task_id}/regenerate-hints")
async def regenerate_hints(request: Request, task_id: str, db: Session = Depends(get_db)):
    user_id = await current_member_id(request)
    task = _owned_task(db, task_id, user_id)
    [usage_row] = service.reserve_ai_calls(
        db,
        user_id,
        KIND_REGEN,
        CREATION_KINDS,
        settings.rate_limit_private_tasks_per_user_per_day,
        _is_allowlisted(request),
    )
    try:
        meta = await create_ai_provider().generate_private_task_meta(task.title, task.content)
    except AIProviderError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    usage_row.meta = meta.meta or None
    db.commit()

    if _abusive(meta.abuse_score):
        raise HTTPException(
            status_code=422,
            detail="Nie udało się wygenerować wskazówek dla tej treści.",
        )
    if not meta.hints:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Nie udało się wygenerować wskazówek. Spróbuj ponownie za chwilę.",
        )

    PrivateTaskRepository(db).update_fields(task, hints=meta.hints)
    return {"task": serialize_task(task)}


# ---------------------------------------------------------------------- submit


@router.post("/{task_id}/submit")
async def submit_private_solution(
    request: Request,
    task_id: str,
    images: list[UploadFile] = File(default=[]),
    pattern_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Submit solution photos; grading runs in the background (WebSocket).

    ``pattern_id`` (one of the user's patterns) marks it as practice of that
    pattern. Hints used are tracked here, never taken from the client.
    """
    user_id = await current_member_id(request)
    task = _owned_task(db, task_id, user_id)

    # Same daily budget as OMJ submissions - it is the same kind of Gemini call
    limit_error, _, user_count, user_oldest = check_submission_limits(
        db, user_id, _is_allowlisted(request)
    )
    if limit_error is not None:
        return limit_error

    batch_error = validate_image_batch(images)
    if batch_error is not None:
        return batch_error

    saved, upload_error = await save_uploaded_images(images, service.task_dir(user_id, task.id))
    if upload_error is not None:
        return upload_error

    repo = PrivateTaskRepository(db)
    hints_used = repo.take_pending_hints(task)

    submission_id = str(uuid.uuid4())[:8]
    SubmissionRepository(db).create(
        id=submission_id,
        user_id=user_id,
        year=None,
        etap=None,
        task_number=None,
        images=[service.relative_upload_path(p) for p in saved],
        status=SubmissionStatus.PENDING,
        private_task_id=task.id,
        hints_used=hints_used,
        pattern_id=owned_pattern_id(db, user_id, pattern_id),
    )

    await progress_manager.create_submission(submission_id)
    job = asyncio.create_task(
        process_submission_background(
            submission_id=submission_id,
            user_id=user_id,
            year=None,
            etap=None,
            task_number=None,
            image_paths=saved,
            private_task={"id": task.id, "title": task.title, "content": task.content},
        )
    )
    _background_tasks.add(job)
    job.add_done_callback(_background_tasks.discard)

    return JSONResponse(
        {
            "success": True,
            "submission_id": submission_id,
            "status": "processing",
            "message": "Rozwiązanie przesłane. Połącz się z WebSocket, aby śledzić postęp.",
            "ws_path": f"/ws/submissions/{submission_id}",
        },
        headers=calculate_rate_limit_headers(
            settings.rate_limit_submissions_per_user_per_day, user_count + 1, user_oldest
        ),
    )
