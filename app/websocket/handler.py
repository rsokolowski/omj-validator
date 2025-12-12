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
from ..storage import get_task_pdf_path, get_solution_pdf_path
from .progress import progress_manager

logger = logging.getLogger(__name__)


def _format_elapsed(start_time: float) -> str:
    """Format elapsed time since start_time."""
    return f"{time.time() - start_time:.1f}s"


async def process_submission_background(
    submission_id: str,
    user_id: str,
    year: str,
    etap: str,
    task_number: int,
    image_paths: list[Path],
) -> None:
    """
    Process submission in background with progress updates.

    This function is started as an asyncio task from the submit endpoint.
    It sends progress updates via the ProgressManager.
    """
    start_time = time.time()
    image_info = ", ".join([f"{p.name}({p.stat().st_size // 1024}KB)" for p in image_paths if p.exists()])

    logger.info(
        f"[Submission {submission_id}] STARTED - "
        f"user={user_id[:8]}..., task={year}/{etap}/{task_number}, "
        f"images=[{image_info}]"
    )

    # Get a new database session for the background task
    # Use SessionLocal directly (not get_db dependency) for background tasks
    db = SessionLocal()

    try:
        submission_repo = SubmissionRepository(db)

        # Update status to PROCESSING
        logger.debug(f"[Submission {submission_id}] Updating DB status to PROCESSING")
        submission_repo.update_status(submission_id, SubmissionStatus.PROCESSING)

        # Stage 1: Uploading files
        logger.info(f"[Submission {submission_id}] Stage 1: Preparing file upload ({_format_elapsed(start_time)})")
        await progress_manager.send_status(submission_id, "Przesyłam pliki...")

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
        )

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

        submission_repo.update_status(
            submission_id,
            SubmissionStatus.FAILED,
            error_message=error_msg,
        )

        await progress_manager.send_error(submission_id, error_msg)

    except Exception as e:
        error_msg = str(e)
        total_time = time.time() - start_time
        logger.exception(
            f"[Submission {submission_id}] FAILED (Unexpected) - "
            f"error_type={type(e).__name__}, error={error_msg}, elapsed={total_time:.1f}s"
        )

        submission_repo.update_status(
            submission_id,
            SubmissionStatus.FAILED,
            error_message=error_msg,
        )

        await progress_manager.send_error(
            submission_id,
            "Przepraszamy, coś poszło nie tak. Spróbuj ponownie za chwilę.",
        )

    finally:
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
