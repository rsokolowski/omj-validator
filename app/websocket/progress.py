"""Progress manager for broadcasting submission updates to WebSocket clients."""

import asyncio
import logging
import re
import time
from typing import Optional
from dataclasses import dataclass, field

from fastapi import WebSocket

from .messages import (
    StatusMessage,
    CompletedMessage,
    ErrorMessage,
)
from ..translate import translate_to_polish

logger = logging.getLogger(__name__)

# Stale entry cleanup threshold (10 minutes)
_CLEANUP_TTL_SECONDS = 600

# Regex to extract **Heading** from thinking text
HEADING_PATTERN = re.compile(r'\*\*([^*]+)\*\*')


@dataclass
class SubmissionProgress:
    """Tracks progress state for a single submission."""
    submission_id: str
    websocket: Optional[WebSocket] = None
    is_connected: bool = False
    # Current status message
    current_status: str = "Przesyłanie..."
    # Accumulated thinking text (for heading extraction)
    thinking_buffer: str = ""
    # Final result (cached for late-connecting clients)
    completed: bool = False
    score: Optional[int] = None
    feedback: Optional[str] = None
    error: Optional[str] = None
    # Timestamp for TTL-based cleanup
    created_at: float = field(default_factory=time.time)


def extract_latest_heading(text: str) -> Optional[str]:
    """Extract the last **Heading** from thinking text."""
    matches = HEADING_PATTERN.findall(text)
    if matches:
        return matches[-1].strip()
    return None


class ProgressManager:
    """
    Manages WebSocket connections and broadcasts progress updates.

    Single-worker implementation using in-memory dict.
    For multi-worker, would need Redis pub/sub.
    """

    def __init__(self):
        self._submissions: dict[str, SubmissionProgress] = {}
        self._lock = asyncio.Lock()

    async def register(self, submission_id: str, websocket: WebSocket) -> SubmissionProgress:
        """
        Register a WebSocket connection for a submission.

        If submission already has accumulated progress, sends it to the client.
        """
        # Collect messages to send while holding lock
        messages_to_send = []

        async with self._lock:
            if submission_id not in self._submissions:
                self._submissions[submission_id] = SubmissionProgress(submission_id=submission_id)

            progress = self._submissions[submission_id]
            progress.websocket = websocket
            progress.is_connected = True

            # Queue current status for late-connecting client
            if progress.current_status:
                messages_to_send.append(StatusMessage(
                    submission_id=submission_id,
                    message=progress.current_status,
                ))

            if progress.completed:
                if progress.error:
                    messages_to_send.append(ErrorMessage(
                        submission_id=submission_id,
                        error=progress.error,
                    ))
                else:
                    messages_to_send.append(CompletedMessage(
                        submission_id=submission_id,
                        score=progress.score or 0,
                        feedback=progress.feedback or "",
                    ))

        # Send messages outside lock to avoid blocking
        for msg in messages_to_send:
            await self._send_safe(websocket, msg)

        return progress

    async def unregister(self, submission_id: str) -> None:
        """Mark WebSocket as disconnected (but keep progress data)."""
        async with self._lock:
            if submission_id in self._submissions:
                self._submissions[submission_id].websocket = None
                self._submissions[submission_id].is_connected = False

    async def create_submission(self, submission_id: str) -> SubmissionProgress:
        """Create a new submission entry (called from POST endpoint)."""
        async with self._lock:
            if submission_id not in self._submissions:
                self._submissions[submission_id] = SubmissionProgress(submission_id=submission_id)
            return self._submissions[submission_id]

    async def get_progress(self, submission_id: str) -> Optional[SubmissionProgress]:
        """Get progress for a submission without re-registering."""
        async with self._lock:
            return self._submissions.get(submission_id)

    async def send_status(self, submission_id: str, message: str) -> None:
        """Send a status update message."""
        async with self._lock:
            # Create entry if it doesn't exist (handles race with WebSocket connect)
            if submission_id not in self._submissions:
                self._submissions[submission_id] = SubmissionProgress(submission_id=submission_id)
            self._submissions[submission_id].current_status = message

        msg = StatusMessage(submission_id=submission_id, message=message)
        await self._broadcast(submission_id, msg)

    async def send_thinking(self, submission_id: str, chunk: str) -> None:
        """
        Process thinking text chunk and extract status heading.

        Only sends a status update if a new heading is found.
        Headings are translated from English to Polish before broadcasting.
        """
        new_heading = None
        should_broadcast = False

        async with self._lock:
            if submission_id in self._submissions:
                progress = self._submissions[submission_id]
                old_heading = extract_latest_heading(progress.thinking_buffer)
                progress.thinking_buffer += chunk
                new_heading = extract_latest_heading(progress.thinking_buffer)

                # Only update and broadcast if heading changed
                if new_heading and new_heading != old_heading:
                    should_broadcast = True

        # Translate and broadcast outside the lock to avoid blocking
        if should_broadcast and new_heading:
            # Translate heading from English to Polish (falls back to original on error)
            translated_heading = await translate_to_polish(new_heading)

            # Update stored status with translated heading
            async with self._lock:
                if submission_id in self._submissions:
                    self._submissions[submission_id].current_status = translated_heading

            msg = StatusMessage(submission_id=submission_id, message=translated_heading)
            await self._broadcast(submission_id, msg)

    async def send_completed(
        self,
        submission_id: str,
        score: int,
        feedback: str,
    ) -> None:
        """Send completion message and mark as done."""
        async with self._lock:
            if submission_id in self._submissions:
                progress = self._submissions[submission_id]
                progress.completed = True
                progress.score = score
                progress.feedback = feedback

        msg = CompletedMessage(
            submission_id=submission_id,
            score=score,
            feedback=feedback,
        )
        await self._broadcast(submission_id, msg)

    async def send_error(self, submission_id: str, error: str) -> None:
        """Send error message and mark as failed."""
        async with self._lock:
            if submission_id in self._submissions:
                progress = self._submissions[submission_id]
                progress.completed = True
                progress.error = error

        msg = ErrorMessage(submission_id=submission_id, error=error)
        await self._broadcast(submission_id, msg)

    async def cleanup(self, submission_id: str) -> None:
        """Remove submission data after client has received final state."""
        async with self._lock:
            self._submissions.pop(submission_id, None)

    async def cleanup_stale(self) -> int:
        """Remove stale entries that are completed or too old. Returns count removed."""
        now = time.time()
        to_remove = []

        async with self._lock:
            for sid, progress in self._submissions.items():
                age = now - progress.created_at
                # Remove if: completed and disconnected, or too old
                if (progress.completed and not progress.is_connected) or age > _CLEANUP_TTL_SECONDS:
                    to_remove.append(sid)

            for sid in to_remove:
                del self._submissions[sid]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} stale progress entries")

        return len(to_remove)

    async def _broadcast(self, submission_id: str, msg) -> None:
        """Send message to connected WebSocket if any."""
        # Copy websocket reference while holding lock, then release before I/O
        websocket = None
        async with self._lock:
            progress = self._submissions.get(submission_id)
            if progress and progress.is_connected and progress.websocket:
                websocket = progress.websocket
        # Send outside lock to avoid blocking other operations
        if websocket:
            await self._send_safe(websocket, msg)

    async def _send_safe(self, websocket: WebSocket, msg) -> None:
        """Send message, catching connection errors."""
        try:
            await websocket.send_json(msg.model_dump())
        except Exception as e:
            logger.debug(f"Failed to send WebSocket message: {e}")


# Global singleton instance
progress_manager = ProgressManager()
