"""WebSocket message types for submission progress streaming."""

from pydantic import BaseModel
from typing import Literal, Optional


class StatusMessage(BaseModel):
    """Current processing status update (extracted from AI thinking)."""
    type: Literal["status"] = "status"
    submission_id: str
    message: str  # The current status heading, e.g., "Analyzing the Student's Solution"


class CompletedMessage(BaseModel):
    """Submission completed successfully."""
    type: Literal["completed"] = "completed"
    submission_id: str
    score: int
    feedback: str


class ErrorMessage(BaseModel):
    """Submission failed with error."""
    type: Literal["error"] = "error"
    submission_id: str
    error: str
