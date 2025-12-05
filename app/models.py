from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TaskInfo(BaseModel):
    year: str
    etap: str
    number: int
    title: str
    content: str
    has_solution: bool = False
    has_statistics: bool = False


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
