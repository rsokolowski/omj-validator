"""Candidate OMJ tasks for linking a pattern - pure, the AI only picks among them.

The model never sees the whole task list or any statement: the server narrows
the 350+ tasks to those sharing the pattern's skills or category, and sends our
own (MIT-licensed) strategy and direction hints for each.
"""

from ..models import TaskInfo

MAX_CANDIDATES = 40


def task_key(task: TaskInfo) -> str:
    return f"{task.year}_{task.etap}_{task.number}"


def _score(task: TaskInfo, skills: set[str], category: str | None) -> int:
    shared = skills & (set(task.skills_required) | set(task.skills_gained))
    return 3 * len(shared) + (2 if category and category in task.categories else 0)


def select_candidates(
    tasks: list[TaskInfo],
    *,
    skills: list[str],
    category: str | None,
    excluded_keys: set[str],
    solved_keys: set[str],
) -> list[TaskInfo]:
    """Related tasks, unsolved first, then best match, then easiest."""
    wanted = set(skills)
    scored = []
    for task in tasks:
        key = task_key(task)
        if key in excluded_keys:
            continue
        score = _score(task, wanted, category)
        if score > 0:
            scored.append((key in solved_keys, -score, task.difficulty or 9, key, task))
    scored.sort(key=lambda row: row[:4])
    return [row[4] for row in scored[:MAX_CANDIDATES]]


def candidate_payload(task: TaskInfo) -> dict:
    """What the model sees of a candidate: no statement, hints 2-3 only."""
    return {
        "task_key": task_key(task),
        "difficulty": task.difficulty,
        "categories": list(task.categories),
        "hints": list(task.hints[1:3]),
    }
