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


def _fallback_title(number: int) -> str:
    """Title shown when the generated statement is unavailable."""
    return f"Zadanie {number}"


def _load_etap_statements(year: str, etap: str) -> dict[str, dict]:
    """Load the locally generated statements for one year/etap.

    The statements (title + content) are transcribed from the OMJ PDFs, belong
    to the competition organiser and are therefore NOT distributed with this
    repository - see NOTICE. They are produced by fix_latex_content.py into
    data/task_content/{year}/{etap}.json and are expected to be missing on a
    fresh checkout, which is not an error.
    """
    path = settings.task_content_path(year, etap)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load task content file {path}: {e}")
        return {}

    statements = data.get("tasks")
    if not isinstance(statements, dict):
        logger.warning(f"Task content file {path} has no 'tasks' object - ignoring")
        return {}
    return statements


@lru_cache(maxsize=1)
def _load_all_tasks() -> dict[str, TaskInfo]:
    """Scan data/tasks/{year}/{etap}/task_*.json and load all tasks (cached).

    This is the single place where the two halves of a task are joined:
    the metadata tracked in git and the statement generated locally from the
    OMJ PDF. A task without a statement still loads with all of its metadata.
    """
    tasks = {}
    tasks_dir = settings.tasks_data_dir

    if not tasks_dir.exists():
        return tasks

    missing_statements = 0

    for year_dir in sorted(tasks_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        for etap_dir in sorted(year_dir.iterdir()):
            if not etap_dir.is_dir():
                continue
            statements = _load_etap_statements(year_dir.name, etap_dir.name)
            for task_file in sorted(etap_dir.glob("task_*.json")):
                try:
                    with open(task_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    number = data["number"]
                    # A statement file must never override metadata, and metadata
                    # files are not supposed to carry a statement any more; if an
                    # old one still does, the generated file wins.
                    statement = statements.get(str(number))
                    if not isinstance(statement, dict):
                        statement = {}
                    title = statement.get("title") or data.get("title")
                    content = statement.get("content") or data.get("content")
                    if not (content or "").strip():
                        content = None
                        missing_statements += 1
                    data.pop("title", None)
                    data.pop("content", None)
                    key = get_task_key(year_dir.name, etap_dir.name, number)
                    tasks[key] = TaskInfo(
                        year=year_dir.name,
                        etap=etap_dir.name,
                        title=title or _fallback_title(number),
                        content=content,
                        **data
                    )
                except (json.JSONDecodeError, KeyError, IOError) as e:
                    logger.warning(f"Failed to load task file {task_file}: {e}")
                    continue

    if missing_statements:
        logger.info(
            f"{missing_statements}/{len(tasks)} tasks have no generated statement. "
            f"The app serves the task PDF instead. Run fix_latex_content.py to "
            f"generate them into {settings.task_content_dir}."
        )

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
