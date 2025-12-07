from pydantic import BaseModel, computed_field
from datetime import datetime
from typing import Optional


class TaskPdf(BaseModel):
    """PDF file paths for a task (shared across tasks in same etap)."""
    tasks: str  # Path to tasks PDF
    solutions: Optional[str] = None  # Path to solutions PDF
    statistics: Optional[str] = None  # Path to statistics PDF


class TaskInfo(BaseModel):
    year: str
    etap: str
    number: int
    title: str
    content: str
    pdf: TaskPdf
    difficulty: Optional[int] = None  # Future: 1-5 scale
    categories: list[str] = []  # Future: e.g., ["geometry", "algebra"]
    hints: list[str] = []  # Future: progressive hints

    @computed_field
    @property
    def has_solution(self) -> bool:
        return self.pdf.solutions is not None

    @computed_field
    @property
    def has_statistics(self) -> bool:
        return self.pdf.statistics is not None


class TaskStats(BaseModel):
    submission_count: int = 0
    highest_score: int = 0


class SubmissionResult(BaseModel):
    score: int
    feedback: str


class Submission(BaseModel):
    id: str
    year: str
    etap: str
    task_number: int
    timestamp: datetime
    images: list[str]  # paths to uploaded images
    score: int
    feedback: str


class LoginRequest(BaseModel):
    key: str
    remember: bool = False


class SubmitRequest(BaseModel):
    year: str
    etap: str
    task_number: int
