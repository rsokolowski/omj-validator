"""HTTP API for private tasks ("Moje zadania").

Every route requires a signed-in user with submit rights (same audience as OMJ
grading). A task id that does not exist and one that belongs to somebody else
both answer 404, so the API never confirms that another user's task exists.

Every AI call is counted before it is made - a failed call still costs Gemini
money, so it still counts toward the daily limits.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..ai import AIContentBlockedError, AIProviderError, create_ai_provider
from ..auth import current_member_id, is_allowlisted
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
from ..db.patterns import PatternRepository
from ..patterns.service import owned_pattern_id, pattern_is_due
from ..models import (
    CreatePrivateTasksRequest,
    PrivateTaskInput,
    PrivateTaskMeta,
    UpdatePrivateTaskRequest,
)
from ..privacy import mask_user_id
from ..rate_limits import release_reserved_submission, reserve_submission, settle_refused_submission
from ..uploads import discard_uploads, save_uploaded_images, validate_image_batch, validate_submission_input
from ..websocket.handler import process_submission_background
from ..websocket.progress import progress_manager
from . import service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/private-tasks", tags=["private-tasks"])

# Grading runs as fire-and-forget tasks; keep references so they are not GC'd
_background_tasks: set[asyncio.Task] = set()

NOT_FOUND = "Nie znaleziono zadania"
REFUSED_TEXT = "Nie udało się zapisać zadania. Sprawdź, czy tekst zawiera tylko treść zadania."
# The hint call doubles as the check of the text: when it fails, nothing is saved
NOT_CHECKED_TEXT = "Nie udało się sprawdzić treści zadania. Spróbuj ponownie za chwilę."
NOT_MATH_TEXT = (
    "To nie wygląda na zadanie z matematyki. Tutaj możesz dodać tylko zadanie "
    "matematyczne - sprawdź treść i spróbuj jeszcze raz."
)


# --------------------------------------------------------------------- helpers


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
        # Drill exercise of a pattern: its level, short answer and pattern
        "exercise_level": task.exercise_level,
        "answer": task.answer,
        # is_due: a solution sent now counts as the pattern's review
        "pattern": (
            {"id": task.pattern.id, "trigger": task.pattern.trigger, "is_due": pattern_is_due(task.pattern)}
            if task.pattern_id and task.pattern is not None
            else None
        ),
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


async def _generate_meta(
    provider, user_id: str, item: PrivateTaskInput, db: Session, usage_row
) -> Optional[PrivateTaskMeta]:
    """Hints for one task, or None when the call failed or was unreadable.

    The hint call is also the abuse and "is it maths" check of the text, so
    None means the text was NOT checked - callers must not save it. A safety
    block propagates (the text is refused, not merely unchecked).
    """
    try:
        meta = await provider.generate_private_task_meta(item.title, item.content)
    except AIContentBlockedError:
        raise
    except AIProviderError as e:
        logger.warning(f"Hint generation failed for user {mask_user_id(user_id)}: {type(e).__name__}")
        service.record_failed_call(db, usage_row, e)
        return None
    except Exception as e:
        logger.exception(f"Hint generation crashed for user {mask_user_id(user_id)}: {type(e).__name__}")
        return None
    if not meta.checked:
        logger.warning(f"Unreadable hint response for user {mask_user_id(user_id)} - text not checked")
        return None
    return meta


def _refusal(meta: Optional[PrivateTaskMeta], need_hints: bool = True) -> Optional[HTTPException]:
    """Why the text must not be saved (unchecked, manipulation, not maths), or None.

    ``need_hints=False``: the hints are not going to be used (a title-only
    edit), so a checked answer without them is not a reason to refuse.
    """
    if meta is None:
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=NOT_CHECKED_TEXT)
    if _abusive(meta.abuse_score):
        return HTTPException(status_code=422, detail=REFUSED_TEXT)
    if not meta.is_math_problem:
        return HTTPException(status_code=422, detail=NOT_MATH_TEXT)
    if need_hints and not meta.hints:
        # Maths, but no hints came back: a glitch - try again
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=NOT_CHECKED_TEXT)
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
    # Extraction needs at least one photo - the shared helper no longer refuses
    # an empty batch, because a solution may now be text only.
    if not images:
        return JSONResponse(
            {"error": "Nie przesłano żadnych zdjęć"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
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
        is_allowlisted(request),
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
        service.record_failed_call(db, usage_row, e)
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
    """Generate hints for each task (the check of its text), then save them all - or none.

    A task whose text could not be checked, was flagged, or is not maths
    stops the whole batch: nothing unchecked is ever saved.
    """
    provider = create_ai_provider()
    try:
        metas = await asyncio.gather(
            *(_generate_meta(provider, user_id, item, db, row) for item, row in zip(items, usage_rows))
        )
    except AIContentBlockedError:
        raise HTTPException(status_code=422, detail=REFUSED_TEXT)
    for row, meta in zip(usage_rows, metas):
        if meta and meta.meta:  # a failed call may already carry failover cost (record_failed_call)
            row.meta = meta.meta
    db.commit()

    refusals = [r for r in (_refusal(meta) for meta in metas) if r is not None]
    if refusals:
        # A refusal over the content (422) wins over "try again" (502)
        refusal = min(refusals, key=lambda r: r.status_code)
        logger.warning(
            f"Private task text refused ({refusal.status_code}) for user {mask_user_id(user_id)}"
        )
        raise refusal

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
                category=item.category or meta.category,
                difficulty=item.difficulty or meta.difficulty,
                hints=meta.hints,
                origin="photo" if photos else "typed",
                source_images=source_images,
                extraction_meta={"hints": meta.meta} if meta.meta else None,
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
            is_allowlisted(request),
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
            submission_repo.to_pydantic(s).student_view()
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

    content_changed = "content" in fields and fields["content"] != task.content
    title_changed = "title" in fields and fields["title"] != task.title
    if content_changed or title_changed:
        # Title and statement both go into the grading prompt, so a change to
        # either gets the same check as at creation. Nothing is saved unless
        # the check succeeded - a failed call refuses the edit (try again).
        [usage_row] = service.reserve_ai_calls(
            db,
            user_id,
            KIND_REGEN,
            CREATION_KINDS,
            settings.rate_limit_private_tasks_per_user_per_day,
            is_allowlisted(request),
        )
        item = PrivateTaskInput(
            title=fields.get("title", task.title), content=fields.get("content", task.content)
        )
        try:
            meta = await _generate_meta(create_ai_provider(), user_id, item, db, usage_row)
        except AIContentBlockedError:
            raise HTTPException(status_code=422, detail=REFUSED_TEXT)
        if meta is not None:
            usage_row.meta = meta.meta or None
            db.commit()
        is_exercise = task.exercise_level is not None
        refusal = _refusal(meta, need_hints=content_changed and not is_exercise)
        if refusal is not None:
            logger.warning(
                f"Edited private task text refused ({refusal.status_code}) for user {mask_user_id(user_id)}"
            )
            raise refusal
        if content_changed and is_exercise:
            # An exercise has no hints, and its answer was for the old statement
            fields["answer"] = None
        elif content_changed:
            # The old hints no longer fit the new statement
            fields["hints"] = meta.hints

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
    if task.exercise_level is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ćwiczenie do wzorca nie ma wskazówek.")
    [usage_row] = service.reserve_ai_calls(
        db,
        user_id,
        KIND_REGEN,
        CREATION_KINDS,
        settings.rate_limit_private_tasks_per_user_per_day,
        is_allowlisted(request),
    )
    try:
        meta = await create_ai_provider().generate_private_task_meta(task.title, task.content)
    except AIProviderError as e:
        service.record_failed_call(db, usage_row, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    usage_row.meta = meta.meta or None
    db.commit()

    if _abusive(meta.abuse_score) or not meta.is_math_problem:
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
    solution_text: Optional[str] = Form(default=None),
    pattern_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Submit solution photos and/or typed text; grading runs in the background (WebSocket).

    ``pattern_id`` (one of the user's patterns) marks it as practice of that
    pattern. Hints used are tracked here, never taken from the client.
    """
    user_id = await current_member_id(request)
    task = _owned_task(db, task_id, user_id)
    # An exercise is practice of its own pattern when that pattern waits for a
    # review today; drilling on other days must not move the schedule early
    practiced_pattern_id = owned_pattern_id(db, user_id, pattern_id)
    if practiced_pattern_id is None and task.pattern is not None and pattern_is_due(task.pattern):
        practiced_pattern_id = task.pattern_id

    # Normalise the text and check there is something to grade - before any
    # file is written, so a rejected request leaves nothing to clean up.
    solution_text, input_error = validate_submission_input(images, solution_text)
    if input_error is not None:
        return input_error

    # Same daily budget as OMJ submissions - it is the same kind of Gemini call.
    # The slot is reserved before any photo is processed (see reserve_submission).
    limit_error, submission, rate_limit_headers = reserve_submission(
        db,
        user_id,
        is_allowlisted(request),
        private_task_id=task.id,
        pattern_id=practiced_pattern_id,
    )
    if limit_error is not None:
        return limit_error
    submission_id = submission.id

    saved: list[Path] = []
    try:
        saved, upload_error = await save_uploaded_images(images, service.task_dir(user_id, task.id))
        if upload_error is None:
            SubmissionRepository(db).attach_solution(
                submission,
                images=[service.relative_upload_path(p) for p in saved],
                solution_text=solution_text,
                hints_used=PrivateTaskRepository(db).take_pending_hints(task),
            )
    except BaseException:
        # Our failure (or a cancelled request), not the student's: no photo
        # stays behind and the slot is given back
        discard_uploads(saved)
        release_reserved_submission(db, submission_id)
        raise
    if upload_error is not None:
        settle_refused_submission(db, submission, upload_error)
        return upload_error
    if task.pattern is not None:
        # Drilling keeps the pattern alive for retention, even on a day it is not due
        PatternRepository(db).touch(task.pattern)

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
            solution_text=solution_text,
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
        headers=rate_limit_headers,
    )
