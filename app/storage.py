import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from functools import lru_cache
import uuid

from .config import settings
from .models import TaskInfo, TaskStats, Submission


@lru_cache(maxsize=1)
def load_tasks_index() -> dict:
    """Load the tasks index from JSON file (cached)."""
    with open(settings.tasks_index_path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_tasks_data_index() -> dict:
    """Load tasks data index with year/etap metadata (cached)."""
    if not settings.tasks_index_data_path.exists():
        return {}
    with open(settings.tasks_index_data_path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=32)
def _load_year_tasks_raw(year: str) -> dict:
    """Load raw tasks data for a specific year (cached)."""
    year_path = settings.tasks_year_data_path(year)
    if not year_path.exists():
        return {}
    with open(year_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_year_tasks(year: str) -> dict[str, TaskInfo]:
    """Load task content for a specific year with TaskInfo models."""
    data = _load_year_tasks_raw(year)
    result = {}
    for etap, tasks in data.items():
        for task in tasks:
            key = get_task_key(year, etap, task["number"])
            result[key] = TaskInfo(
                year=year,
                etap=etap,
                **task
            )
    return result


def load_tasks_data() -> dict[str, TaskInfo]:
    """Load all task content (for backward compatibility)."""
    index = load_tasks_data_index()
    result = {}
    for year in index.keys():
        result.update(load_year_tasks(year))
    return result


def get_task_key(year: str, etap: str, number: int) -> str:
    """Generate a unique key for a task."""
    return f"{year}_{etap}_{number}"


def get_task(year: str, etap: str, number: int) -> Optional[TaskInfo]:
    """Get a specific task by year, etap, and number."""
    tasks = load_year_tasks(year)
    key = get_task_key(year, etap, number)
    return tasks.get(key)


def get_task_pdf_path(year: str, etap: str) -> Optional[Path]:
    """Get the path to the task PDF for a given year and etap."""
    index = load_tasks_index()
    if year not in index or etap not in index[year]:
        return None
    tasks_file = index[year][etap].get("tasks")
    if not tasks_file:
        return None
    return settings.base_dir / tasks_file


def get_solution_pdf_path(year: str, etap: str) -> Optional[Path]:
    """Get the path to the solution PDF for a given year and etap."""
    index = load_tasks_index()
    if year not in index or etap not in index[year]:
        return None
    solution_file = index[year][etap].get("solutions")
    if not solution_file:
        return None
    return settings.base_dir / solution_file


def get_submissions_path(year: str, etap: str, task_number: int) -> Path:
    """Get the directory for submissions of a specific task."""
    path = settings.submissions_dir / year / etap / str(task_number)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_submission(submission: Submission) -> None:
    """Save a submission to disk."""
    path = get_submissions_path(
        submission.year, submission.etap, submission.task_number
    )
    filename = f"submission_{submission.id}.json"
    with open(path / filename, "w", encoding="utf-8") as f:
        json.dump(submission.model_dump(mode="json"), f, ensure_ascii=False, indent=2)


def load_submissions(year: str, etap: str, task_number: int) -> list[Submission]:
    """Load all submissions for a specific task, sorted by timestamp descending."""
    path = get_submissions_path(year, etap, task_number)
    submissions = []
    for file in path.glob("submission_*.json"):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
        submissions.append(Submission(**data))
    # Sort by timestamp, most recent first
    submissions.sort(key=lambda s: s.timestamp, reverse=True)
    return submissions


def get_task_stats(year: str, etap: str, task_number: int) -> TaskStats:
    """Get statistics for a specific task."""
    submissions = load_submissions(year, etap, task_number)
    if not submissions:
        return TaskStats()
    return TaskStats(
        submission_count=len(submissions),
        highest_score=max(s.score for s in submissions),
    )


def create_submission(
    year: str,
    etap: str,
    task_number: int,
    images: list[str],
    score: int,
    feedback: str,
) -> Submission:
    """Create and save a new submission."""
    submission = Submission(
        id=str(uuid.uuid4())[:8],
        year=year,
        etap=etap,
        task_number=task_number,
        timestamp=datetime.now(),
        images=images,
        score=score,
        feedback=feedback,
    )
    save_submission(submission)
    return submission
