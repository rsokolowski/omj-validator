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


# Refine rounds list tasks as evidence that a version applies. With a category
# or skills known the list is narrowed like for linking; before that (a first
# round with nothing but the student's sentence) every task goes in, with a
# single hint to keep the prompt small.
MAX_REFINE_CANDIDATES = 60


def refine_candidates(tasks: list[TaskInfo], *, skills: list[str], category: str | None) -> list[TaskInfo]:
    wanted = set(skills)
    if not wanted and not category:
        return sorted(tasks, key=task_key)
    scored = [(_score(t, wanted, category), t) for t in tasks]
    scored = [row for row in scored if row[0] > 0]
    # Most tasks of a category tie; the cut must not keep only the oldest
    # editions, so ties go round-robin over the years, newest year first
    scored.sort(key=lambda row: (-row[0], -int(row[1].year), row[1].etap, row[1].number))
    seen: dict[tuple[int, str], int] = {}
    ranked = []
    for score, task in scored:
        turn = seen.get((score, task.year), 0)
        seen[(score, task.year)] = turn + 1
        ranked.append((-score, turn, -int(task.year), task.etap, task.number, task))
    ranked.sort(key=lambda row: row[:5])
    return [row[5] for row in ranked[:MAX_REFINE_CANDIDATES]]


def refine_payload(task: TaskInfo, *, narrowed: bool) -> dict:
    """Like ``candidate_payload``; one hint when the whole task list is sent."""
    return {
        "task_key": task_key(task),
        "difficulty": task.difficulty,
        "categories": list(task.categories),
        "hints": list(task.hints[1:3] if narrowed else task.hints[2:3]),
    }
