import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from functools import lru_cache
import uuid

from .config import settings
from .models import TaskInfo, TaskPdf, TaskStats, Submission

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_all_tasks() -> dict[str, TaskInfo]:
    """Scan data/tasks/{year}/{etap}/task_*.json and load all tasks (cached)."""
    tasks = {}
    tasks_dir = settings.tasks_data_dir

    if not tasks_dir.exists():
        return tasks

    for year_dir in sorted(tasks_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        for etap_dir in sorted(year_dir.iterdir()):
            if not etap_dir.is_dir():
                continue
            for task_file in sorted(etap_dir.glob("task_*.json")):
                try:
                    with open(task_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    key = get_task_key(year_dir.name, etap_dir.name, data["number"])
                    tasks[key] = TaskInfo(
                        year=year_dir.name,
                        etap=etap_dir.name,
                        **data
                    )
                except (json.JSONDecodeError, KeyError, IOError) as e:
                    logger.warning(f"Failed to load task file {task_file}: {e}")
                    continue

    return tasks


def clear_task_cache() -> None:
    """Clear the task cache. Call after modifying task files at runtime."""
    _load_all_tasks.cache_clear()


def get_available_years() -> list[str]:
    """Get list of available years, sorted descending."""
    tasks = _load_all_tasks()
    years = set(task.year for task in tasks.values())
    return sorted(years, reverse=True)


def get_etaps_for_year(year: str) -> list[str]:
    """Get list of etaps for a given year."""
    tasks = _load_all_tasks()
    etaps = set(task.etap for task in tasks.values() if task.year == year)
    return sorted(etaps)


def get_tasks_for_etap(year: str, etap: str) -> list[TaskInfo]:
    """Get all tasks for a given year/etap, sorted by number."""
    tasks = _load_all_tasks()
    result = [t for t in tasks.values() if t.year == year and t.etap == etap]
    return sorted(result, key=lambda t: t.number)


def get_task_key(year: str, etap: str, number: int) -> str:
    """Generate a unique key for a task."""
    return f"{year}_{etap}_{number}"


def get_task(year: str, etap: str, number: int) -> Optional[TaskInfo]:
    """Get a specific task by year, etap, and number."""
    tasks = _load_all_tasks()
    key = get_task_key(year, etap, number)
    return tasks.get(key)


def get_task_pdf_path(year: str, etap: str) -> Optional[Path]:
    """Get the path to the task PDF for a given year and etap.

    PDF paths are shared across all tasks in the same year/etap,
    so we fetch from the first task.
    """
    tasks = get_tasks_for_etap(year, etap)
    if not tasks:
        return None
    pdf_path = tasks[0].pdf.tasks
    return settings.base_dir / pdf_path


def get_solution_pdf_path(year: str, etap: str) -> Optional[Path]:
    """Get the path to the solution PDF for a given year and etap.

    PDF paths are shared across all tasks in the same year/etap,
    so we fetch from the first task.
    """
    tasks = get_tasks_for_etap(year, etap)
    if not tasks or not tasks[0].pdf.solutions:
        return None
    return settings.base_dir / tasks[0].pdf.solutions


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
