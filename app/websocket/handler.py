"""WebSocket handler and background processing for submissions."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..config import settings
from ..db.session import SessionLocal
from ..db.models import SubmissionStatus, IssueType
from ..db.repositories import SubmissionRepository
from ..ai import create_ai_provider, AIProviderError
from ..ai.factory import AISpendLimitError
from ..ai.failover import failure_meta, restart_hook
from ..ai.messages import GENERIC_MESSAGE, OVERLOADED_MESSAGE
from ..ai.spend import check_spend_limit
from ..privacy import mask_user_id
from ..storage import get_task_pdf_path, get_solution_pdf_path
from ..notifications import (
    record_completed,
    record_failed,
    record_started,
)
from .progress import progress_manager

logger = logging.getLogger(__name__)


def _format_elapsed(start_time: float) -> str:
    """Format elapsed time since start_time."""
    return f"{time.time() - start_time:.1f}s"


QUEUE_STATUS = "Czekam w kolejce..."
UNEXPECTED_ERROR_MESSAGE = GENERIC_MESSAGE
QUEUE_TIMEOUT_MESSAGE = OVERLOADED_MESSAGE

# (event loop, semaphore, limit): at most AI_GRADING_MAX_CONCURRENT gradings
# call the model at once; the rest wait with status PENDING. Bound to the
# running loop (asyncio primitives are per loop; tests start a loop per run).
_grading_slots: Optional[tuple[asyncio.AbstractEventLoop, asyncio.Semaphore, int]] = None


def _grading_semaphore() -> asyncio.Semaphore:
    global _grading_slots
    loop = asyncio.get_running_loop()
    limit = max(1, settings.ai_grading_max_concurrent)
    if _grading_slots is None or _grading_slots[0] is not loop or _grading_slots[2] != limit:
        _grading_slots = (loop, asyncio.Semaphore(limit), limit)
    return _grading_slots[1]


class _QueueTimeout(AIProviderError):
    """No grading slot freed up within ai_grading_queue_timeout."""


def _release_reason(error: Exception) -> str:
    """scoring_meta["quota_released"] for a refusal before any AI call."""
    if isinstance(error, _QueueTimeout):
        return "queue_timeout"
    if isinstance(error, AISpendLimitError):
        return "spend_limit"
    return "before_ai"


async def _record_failure(
    db: Session, submission_id: str, ai_called: bool, error: Exception, message: str
) -> None:
    """FAILED row + WebSocket error for a grading that did not finish. Never raises.

    The session may be mid-failure (the unexpected path): rolled back first,
    and a failing write is logged - the student still gets the message.
    Before any AI call the slot is released and the never-graded photos are
    deleted (release_quota); after one, the row keeps counting and carries
    the failed-over primary's estimated cost (failover.failure_meta).
    """
    try:
        db.rollback()
        repo = SubmissionRepository(db)
        if ai_called:
            repo.update_status(
                submission_id, SubmissionStatus.FAILED, error_message=message,
                scoring_meta_update=failure_meta(error),
            )
        else:
            freed = repo.release_quota(submission_id, _release_reason(error), message)
            if freed:
                from ..retention import delete_unreferenced_uploads

                delete_unreferenced_uploads(db, freed)
    except Exception as write_error:
        logger.error(
            f"[Submission {submission_id}] Could not record the failure: {type(write_error).__name__}"
        )
        try:
            db.rollback()
        except Exception:
            pass
    try:
        await progress_manager.send_error(submission_id, message)
    except Exception as send_error:
        logger.warning(f"[Submission {submission_id}] Could not send the error: {type(send_error).__name__}")


async def process_submission_background(
    submission_id: str,
    user_id: str,
    year: Optional[str],
    etap: Optional[str],
    task_number: Optional[int],
    image_paths: list[Path],
    private_task: Optional[dict] = None,
    solution_text: Optional[str] = None,
) -> None:
    """
    Process submission in background with progress updates.

    This function is started as an asyncio task from the submit endpoint.
    It sends progress updates via the ProgressManager.

    ``private_task`` ({"id", "title", "content"}) switches to grading against a
    private task's text; year/etap/task_number are then None. The text graded
    against is stored in scoring_meta["task_snapshot"], so a later edit of the
    task cannot change what an old score refers to.

    ``solution_text`` is the typed solution (already normalised by the
    endpoint); it is passed to the provider untouched and never logged - only
    its length.
    """
    if private_task is not None:
        # Notifications and logs identify the task only as "private" - its title
        # and statement are the student's content (see app/notifications.py).
        year, etap, task_number = "private", "-", 0
    start_time = time.time()
    image_info = ", ".join([f"{p.name}({p.stat().st_size // 1024}KB)" for p in image_paths if p.exists()])

    logger.info(
        f"[Submission {submission_id}] STARTED - "
        f"user={mask_user_id(user_id)}, task={year}/{etap}/{task_number}, "
        f"images=[{image_info}], text_chars={len(solution_text or '')}"
    )

    # Get a new database session for the background task
    # Use SessionLocal directly (not get_db dependency) for background tasks
    db = SessionLocal()
    semaphore = _grading_semaphore()
    slot_taken = False
    hook_token = None
    # Until the analyze call starts nothing has been sent to an AI: a failure
    # up to there (queue, spend cap, provider construction) is ours and gives
    # the student's daily slot back
    ai_called = False

    # NOTE: Telegram notifications deliberately carry no user name or e-mail -
    # see the privacy note in app/notifications.py before changing this.
    try:
        submission_repo = SubmissionRepository(db)

        # Global cap on gradings running at once: a burst must not fan out
        # unbounded AI calls. Waiting jobs stay PENDING.
        if semaphore.locked():
            logger.info(f"[Submission {submission_id}] Waiting for a grading slot")
            await progress_manager.send_status(submission_id, QUEUE_STATUS)
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=settings.ai_grading_queue_timeout)
        except asyncio.TimeoutError:
            raise _QueueTimeout(QUEUE_TIMEOUT_MESSAGE)
        slot_taken = True

        # Update status to PROCESSING
        logger.debug(f"[Submission {submission_id}] Updating DB status to PROCESSING")
        submission_repo.update_status(submission_id, SubmissionStatus.PROCESSING)

        # Counted in the anonymous Telegram digest (see app/notifications.py)
        record_started()

        # Stage 1: Uploading files
        logger.info(f"[Submission {submission_id}] Stage 1: Preparing file upload ({_format_elapsed(start_time)})")
        await progress_manager.send_status(
            submission_id, "Przesyłam pliki..." if image_paths else "Przesyłam rozwiązanie..."
        )

        if private_task is None:
            # Get PDF paths
            task_pdf = get_task_pdf_path(year, etap)
            solution_pdf = get_solution_pdf_path(year, etap)

            if not task_pdf or not task_pdf.exists():
                logger.error(f"[Submission {submission_id}] Task PDF not found: {task_pdf}")
                raise AIProviderError("Nie znaleziono pliku z zadaniami")

            logger.debug(
                f"[Submission {submission_id}] PDFs: task={task_pdf.name}, "
                f"solution={solution_pdf.name if solution_pdf and solution_pdf.exists() else 'N/A'}"
            )

        # Global daily spend cap - before any AI call is made
        check_spend_limit(db)
        # End the read transaction: the connection must not sit "idle in
        # transaction" for the whole (minutes-long) model call
        db.commit()

        # Create AI provider and analyze with streaming
        logger.info(f"[Submission {submission_id}] Stage 2: Creating AI provider ({_format_elapsed(start_time)})")
        provider = create_ai_provider()

        # Define callback for when file upload completes
        async def on_upload_complete():
            logger.debug(f"[Submission {submission_id}] File upload complete, starting AI analysis ({_format_elapsed(start_time)})")
            await progress_manager.send_status(submission_id, "Analizuję rozwiązanie...")

        # Define callback for streaming thinking (extracts headings)
        thinking_chunks = 0

        async def on_thinking(chunk: str):
            nonlocal thinking_chunks
            thinking_chunks += 1
            if thinking_chunks == 1:
                logger.debug(f"[Submission {submission_id}] First thinking chunk received ({_format_elapsed(start_time)})")
            await progress_manager.send_thinking(submission_id, chunk)

        # Failover restarts a grading on the backup provider: drop the
        # primary's partial progress, the student sees the analysis go on.
        async def on_restart():
            nonlocal thinking_chunks
            logger.info(f"[Submission {submission_id}] Restarting on the backup AI provider ({_format_elapsed(start_time)})")
            thinking_chunks = 0
            await progress_manager.reset_thinking(submission_id)
            await progress_manager.send_status(submission_id, "Analizuję rozwiązanie...")

        hook_token = restart_hook.set(on_restart)
        ai_called = True

        if private_task is None:
            logger.info(f"[Submission {submission_id}] Calling analyze_solution_stream ({_format_elapsed(start_time)})")
            result = await provider.analyze_solution_stream(
                task_pdf_path=task_pdf,
                solution_pdf_path=solution_pdf,
                image_paths=image_paths,
                task_number=task_number,
                etap=etap,
                on_thinking=on_thinking,
                on_feedback=None,  # We don't stream feedback anymore
                on_upload_complete=on_upload_complete,
                solution_text=solution_text,
            )
        else:
            logger.info(f"[Submission {submission_id}] Calling analyze_private_solution_stream ({_format_elapsed(start_time)})")
            result = await provider.analyze_private_solution_stream(
                task_title=private_task["title"],
                task_content=private_task["content"],
                image_paths=image_paths,
                on_thinking=on_thinking,
                on_upload_complete=on_upload_complete,
                solution_text=solution_text,
            )
            result.scoring_meta = {
                **(result.scoring_meta or {}),
                "task_snapshot": {
                    "title": private_task["title"],
                    "content": private_task["content"],
                },
            }

        logger.info(
            f"[Submission {submission_id}] AI analysis complete ({_format_elapsed(start_time)}) - "
            f"score={result.score}, thinking_chunks={thinking_chunks}, "
            f"feedback_len={len(result.feedback) if result.feedback else 0}"
        )

        # Stage 3: Finalizing
        logger.info(f"[Submission {submission_id}] Stage 3: Finalizing ({_format_elapsed(start_time)})")
        await progress_manager.send_status(submission_id, "Finalizowanie...")

        # Update database with results
        logger.debug(f"[Submission {submission_id}] Updating DB with results")
        submission_repo.update_result(
            submission_id=submission_id,
            score=result.score,
            feedback=result.feedback,
            status=SubmissionStatus.COMPLETED,
            issue_type=IssueType(result.issue_type.value),
            abuse_score=result.abuse_score,
            scoring_meta=result.scoring_meta,
        )

        # Send completion
        await progress_manager.send_completed(
            submission_id,
            score=result.score,
            feedback=result.feedback,
        )

        record_completed()

        total_time = time.time() - start_time
        logger.info(
            f"[Submission {submission_id}] COMPLETED - "
            f"score={result.score}, total_time={total_time:.1f}s"
        )

    except AIProviderError as e:
        error_msg = str(e)
        total_time = time.time() - start_time
        logger.error(
            f"[Submission {submission_id}] FAILED (AIProviderError) - "
            f"error={error_msg}, elapsed={total_time:.1f}s"
        )

        await _record_failure(db, submission_id, ai_called, e, error_msg)

        record_failed(e)

    except Exception as e:
        error_msg = str(e)
        total_time = time.time() - start_time
        logger.exception(
            f"[Submission {submission_id}] FAILED (Unexpected) - "
            f"error_type={type(e).__name__}, error={error_msg}, elapsed={total_time:.1f}s"
        )

        # The student sees error_message in their history: never the raw
        # exception text (it can quote model output or internals) - logs only.
        await _record_failure(db, submission_id, ai_called, e, UNEXPECTED_ERROR_MESSAGE)

        record_failed(e)

    finally:
        if hook_token is not None:
            restart_hook.reset(hook_token)
        if slot_taken:
            semaphore.release()
        # Close the database session
        total_time = time.time() - start_time
        logger.debug(f"[Submission {submission_id}] Cleanup: closing DB session (total={total_time:.1f}s)")
        try:
            db.close()
        except Exception as e:
            logger.warning(f"[Submission {submission_id}] Error closing DB session: {e}")


async def websocket_submission_handler(
    websocket: WebSocket,
    submission_id: str,
    user_id: str,
) -> None:
    """
    Handle WebSocket connection for submission progress.

    Args:
        websocket: The WebSocket connection
        submission_id: The submission ID to track
        user_id: The user ID (for authorization)
    """
    await websocket.accept()
    should_cleanup = False

    try:
        # Register this WebSocket for the submission
        progress = await progress_manager.register(submission_id, websocket)

        # If submission is already completed, we've already sent the result
        # Just wait for client to close or disconnect
        if progress.completed:
            # Keep connection open briefly for client to receive final state
            await asyncio.sleep(1)
            should_cleanup = True  # Clean up completed submissions
            return

        # Wait for messages (client can send "ping" to keep alive)
        while True:
            try:
                # Wait for any message with timeout
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=300,  # 5 minute timeout
                )

                # Handle ping/pong
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                # Check if submission completed while waiting
                current_progress = await progress_manager.get_progress(submission_id)
                if current_progress and current_progress.completed:
                    should_cleanup = True
                    break

            except asyncio.TimeoutError:
                # Send ping to check if client is still there
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"[WebSocket] Client disconnected for submission {submission_id}")

    except Exception as e:
        logger.error(f"[WebSocket] Error for submission {submission_id}: {e}")

    finally:
        await progress_manager.unregister(submission_id)
        # Clean up progress data if submission is completed and client disconnected
        if should_cleanup:
            await progress_manager.cleanup(submission_id)
