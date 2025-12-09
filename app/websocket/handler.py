"""WebSocket handler and background processing for submissions."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..config import settings
from ..db.session import SessionLocal
from ..db.models import SubmissionStatus
from ..db.repositories import SubmissionRepository
from ..ai import create_ai_provider, AIProviderError
from ..storage import get_task_pdf_path, get_solution_pdf_path
from .progress import progress_manager

logger = logging.getLogger(__name__)


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
    # Get a new database session for the background task
    # Use SessionLocal directly (not get_db dependency) for background tasks
    db = SessionLocal()

    try:
        submission_repo = SubmissionRepository(db)

        # Update status to PROCESSING
        submission_repo.update_status(submission_id, SubmissionStatus.PROCESSING)

        # Stage 1: Uploading files
        await progress_manager.send_status(submission_id, "Przesyłam pliki...")

        # Get PDF paths
        task_pdf = get_task_pdf_path(year, etap)
        solution_pdf = get_solution_pdf_path(year, etap)

        if not task_pdf or not task_pdf.exists():
            raise AIProviderError("Nie znaleziono pliku z zadaniami")

        # Create AI provider and analyze with streaming
        provider = create_ai_provider()

        # Define callback for when file upload completes
        async def on_upload_complete():
            await progress_manager.send_status(submission_id, "Analizuję rozwiązanie...")

        # Define callback for streaming thinking (extracts headings)
        async def on_thinking(chunk: str):
            await progress_manager.send_thinking(submission_id, chunk)

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

        # Stage 3: Finalizing
        await progress_manager.send_status(submission_id, "Finalizowanie...")

        # Update database with results
        submission_repo.update_result(
            submission_id=submission_id,
            score=result.score,
            feedback=result.feedback,
            status=SubmissionStatus.COMPLETED,
            scoring_meta=result.scoring_meta,
        )

        # Send completion
        await progress_manager.send_completed(
            submission_id,
            score=result.score,
            feedback=result.feedback,
        )

        logger.info(f"[Submission {submission_id}] Completed with score {result.score}")

    except AIProviderError as e:
        error_msg = str(e)
        logger.error(f"[Submission {submission_id}] AI error: {error_msg}")

        submission_repo.update_status(
            submission_id,
            SubmissionStatus.FAILED,
            error_message=error_msg,
        )

        await progress_manager.send_error(submission_id, error_msg)

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"[Submission {submission_id}] Unexpected error: {error_msg}")

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
        try:
            db.close()
        except Exception:
            pass


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
