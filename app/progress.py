"""
Progress tracking and recommendation engine for OMJ Validator.

Computes user progress across all tasks, determines task status
(locked/unlocked/mastered), and generates diverse recommendations.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from .storage import _load_all_tasks, get_task_key
from .models import TaskInfo, TaskStatus, GraphNode, GraphEdge, ProgressData
from .db import SubmissionRepository

logger = logging.getLogger(__name__)


def get_mastery_threshold(etap: str) -> int:
    """Get the score threshold for mastery based on etap.

    - etap2: score >= 5 (max is 6)
    - etap1: score >= 2 (max is 3)
    """
    return 5 if etap == "etap2" else 2


def compute_user_progress(user_id: Optional[str] = None, db: Optional[Session] = None) -> dict[str, int]:
    """Compute best scores for all tasks from submissions.

    Uses database query to efficiently get user's best scores.

    Args:
        user_id: Google sub of the user (required for multi-user)
        db: Database session (required for multi-user)

    Returns:
        Dict mapping task_key -> best_score
    """
    if user_id and db:
        # Use database for user-specific progress
        submission_repo = SubmissionRepository(db)
        return submission_repo.get_user_progress(user_id)
    else:
        # Return empty progress if no user (non-authenticated)
        return {}


def compute_prerequisites_met(
    all_tasks: dict[str, TaskInfo],
    progress: dict[str, int]
) -> dict[str, bool]:
    """Compute prerequisite status for all tasks efficiently with memoization.

    Uses dynamic programming approach: process tasks in dependency order,
    caching results to avoid redundant computation. O(n + e) where n is
    number of tasks and e is number of prerequisite edges.

    Args:
        all_tasks: Dict of all tasks
        progress: Dict of task_key -> best_score

    Returns:
        Dict mapping task_key -> bool (True if all prerequisites met)
    """
    # First, compute mastery status for all tasks (simple O(n))
    mastered = {}
    for key, task in all_tasks.items():
        threshold = get_mastery_threshold(task.etap)
        mastered[key] = progress.get(key, 0) >= threshold

    # Memoization cache for "all prerequisites met" status
    prereqs_met_cache: dict[str, bool] = {}

    # Track tasks being processed to detect cycles
    in_progress: set[str] = set()

    def check_prereqs_met(task_key: str) -> bool:
        """Recursively check if all prerequisites are met, with memoization."""
        # Return cached result if available
        if task_key in prereqs_met_cache:
            return prereqs_met_cache[task_key]

        # Cycle detection
        if task_key in in_progress:
            logger.warning(f"Circular dependency detected involving task {task_key}")
            return True  # Break cycle by assuming met

        task = all_tasks.get(task_key)
        if not task:
            return True  # Unknown task, assume no prerequisites

        # No prerequisites = always met
        if not task.prerequisites:
            prereqs_met_cache[task_key] = True
            return True

        in_progress.add(task_key)

        result = True
        for prereq_key in task.prerequisites:
            # Validate prerequisite key format
            parts = prereq_key.split("_")
            if len(parts) < 3 or parts[1] not in ("etap1", "etap2"):
                logger.warning(f"Invalid prerequisite key format: {prereq_key} in task {task_key}")
                continue

            # Check if prerequisite is mastered
            if not mastered.get(prereq_key, False):
                result = False
                break

            # Check if prerequisite's prerequisites are met (recursive with memo)
            if not check_prereqs_met(prereq_key):
                result = False
                break

        in_progress.discard(task_key)
        prereqs_met_cache[task_key] = result
        return result

    # Compute for all tasks
    for key in all_tasks:
        check_prereqs_met(key)

    return prereqs_met_cache


def get_task_status_batch(
    all_tasks: dict[str, TaskInfo],
    progress: dict[str, int]
) -> dict[str, TaskStatus]:
    """Compute status for all tasks efficiently in a single pass.

    More efficient than calling get_task_status() for each task individually.
    Uses memoized prerequisite computation.

    Args:
        all_tasks: Dict of all tasks
        progress: Dict of task_key -> best_score

    Returns:
        Dict mapping task_key -> TaskStatus
    """
    # Compute all prerequisite statuses in one pass (O(n + e))
    prereqs_met = compute_prerequisites_met(all_tasks, progress)

    # Compute final status for each task
    statuses = {}
    for key, task in all_tasks.items():
        threshold = get_mastery_threshold(task.etap)
        best_score = progress.get(key, 0)

        if best_score >= threshold:
            statuses[key] = TaskStatus.MASTERED
        elif prereqs_met.get(key, True):
            statuses[key] = TaskStatus.UNLOCKED
        else:
            statuses[key] = TaskStatus.LOCKED

    return statuses


def get_task_status(
    task: TaskInfo,
    progress: dict[str, int],
    all_tasks: dict[str, TaskInfo] = None,
    prereqs_met_cache: dict[str, bool] = None
) -> TaskStatus:
    """Determine if a task is locked, unlocked, or mastered.

    For batch operations, use get_task_status_batch() instead for better
    performance. This function is provided for single-task lookups.

    Args:
        task: The task to check
        progress: Dict of task_key -> best_score
        all_tasks: Dict of all tasks (for transitive dependency lookup)
        prereqs_met_cache: Optional pre-computed prerequisite status cache

    Returns:
        TaskStatus enum value
    """
    if all_tasks is None:
        all_tasks = _load_all_tasks()

    task_key = get_task_key(task.year, task.etap, task.number)
    best_score = progress.get(task_key, 0)
    threshold = get_mastery_threshold(task.etap)

    # Check if mastered
    if best_score >= threshold:
        return TaskStatus.MASTERED

    # Use cached prereqs if available, otherwise compute
    if prereqs_met_cache is not None:
        prereqs_met = prereqs_met_cache.get(task_key, True)
    else:
        prereqs_met = compute_prerequisites_met(all_tasks, progress).get(task_key, True)

    if not prereqs_met:
        return TaskStatus.LOCKED

    return TaskStatus.UNLOCKED


def build_graph_nodes(progress: dict[str, int]) -> list[GraphNode]:
    """Build graph nodes for all tasks with their status.

    Uses batch status computation for O(n + e) efficiency.

    Args:
        progress: Dict of task_key -> best_score

    Returns:
        List of GraphNode objects
    """
    all_tasks = _load_all_tasks()

    # Compute all statuses efficiently in one pass
    statuses = get_task_status_batch(all_tasks, progress)

    nodes = []
    for key, task in all_tasks.items():
        status = statuses.get(key, TaskStatus.UNLOCKED)
        node = GraphNode(
            key=key,
            year=task.year,
            etap=task.etap,
            number=task.number,
            title=task.title,
            difficulty=task.difficulty,
            categories=task.categories,
            prerequisites=task.prerequisites,
            status=status,
            best_score=progress.get(key, 0)
        )
        nodes.append(node)

    return nodes


def build_graph_edges() -> list[GraphEdge]:
    """Build edges from prerequisite relationships.

    Returns:
        List of GraphEdge objects (source=prerequisite, target=dependent)
    """
    all_tasks = _load_all_tasks()
    edges = []
    task_keys = set(all_tasks.keys())

    for key, task in all_tasks.items():
        for prereq_key in task.prerequisites:
            # Only create edge if prerequisite exists
            if prereq_key in task_keys:
                edges.append(GraphEdge(source=prereq_key, target=key))
            else:
                logger.warning(f"Task {key} has invalid prerequisite: {prereq_key}")

    return edges


def get_recommended_tasks(
    nodes: list[GraphNode],
    limit: int = 5,
    category_filter: Optional[str] = None
) -> list[GraphNode]:
    """Generate diverse task recommendations from unlocked tasks.

    Strategy:
    1. Filter to unlocked tasks only
    2. Optionally filter by category
    3. Prioritize: not yet attempted > lower difficulty > category diversity
    4. Return up to `limit` tasks

    Args:
        nodes: All graph nodes with status
        limit: Max number of recommendations
        category_filter: Optional category to filter by

    Returns:
        List of recommended GraphNode objects
    """
    # Filter to unlocked tasks
    unlocked = [n for n in nodes if n.status == TaskStatus.UNLOCKED]

    # Apply category filter if specified
    if category_filter:
        unlocked = [n for n in unlocked if category_filter in n.categories]

    if not unlocked:
        return []

    # Sort by: 1) not attempted first, 2) lower difficulty, 3) newer year
    def sort_key(node: GraphNode):
        attempted = 1 if node.best_score > 0 else 0
        difficulty = node.difficulty or 3
        year = -int(node.year) if node.year.isdigit() else 0
        return (attempted, difficulty, year)

    unlocked.sort(key=sort_key)

    # Select with category diversity
    selected = []
    used_categories = set()

    # First pass: pick one from each category
    for node in unlocked:
        if len(selected) >= limit:
            break
        node_cats = set(node.categories) if node.categories else {"uncategorized"}
        # Prefer tasks with categories we haven't used yet
        if not node_cats.intersection(used_categories):
            selected.append(node)
            used_categories.update(node_cats)

    # Second pass: fill remaining slots
    for node in unlocked:
        if len(selected) >= limit:
            break
        if node not in selected:
            selected.append(node)

    return selected[:limit]


def build_progress_data(
    user_id: Optional[str] = None,
    db: Optional[Session] = None,
    category_filter: Optional[str] = None
) -> ProgressData:
    """Build complete progress data for the progress page.

    Args:
        user_id: Google sub of the user (required for multi-user)
        db: Database session (required for multi-user)
        category_filter: Optional category to filter graph by

    Returns:
        ProgressData with nodes, edges, recommendations, and stats
    """
    progress = compute_user_progress(user_id=user_id, db=db)
    all_nodes = build_graph_nodes(progress)
    all_edges = build_graph_edges()

    # Filter nodes and edges by category if specified
    if category_filter:
        filtered_nodes = [n for n in all_nodes if category_filter in n.categories]
        filtered_keys = {n.key for n in filtered_nodes}
        filtered_edges = [
            e for e in all_edges
            if e.source in filtered_keys and e.target in filtered_keys
        ]
    else:
        filtered_nodes = all_nodes
        filtered_edges = all_edges

    # Get recommendations (from all tasks, not filtered)
    recommendations = get_recommended_tasks(all_nodes, limit=5, category_filter=category_filter)

    # Compute stats (from all tasks)
    stats = {
        "total": len(all_nodes),
        "mastered": sum(1 for n in all_nodes if n.status == TaskStatus.MASTERED),
        "unlocked": sum(1 for n in all_nodes if n.status == TaskStatus.UNLOCKED),
        "locked": sum(1 for n in all_nodes if n.status == TaskStatus.LOCKED),
    }

    return ProgressData(
        nodes=filtered_nodes,
        edges=filtered_edges,
        recommendations=recommendations,
        stats=stats
    )


def get_all_categories() -> list[str]:
    """Get list of all categories used in tasks.

    Returns:
        Sorted list of category strings
    """
    all_tasks = _load_all_tasks()
    categories = set()
    for task in all_tasks.values():
        categories.update(task.categories)
    return sorted(categories)


def get_prerequisite_statuses(
    prerequisite_keys: list[str],
    progress: dict[str, int]
) -> list["PrerequisiteStatus"]:
    """Get mastery status for each prerequisite task.

    Args:
        prerequisite_keys: List of task keys (e.g., ["2023_etap1_2"])
        progress: Dict of task_key -> best_score

    Returns:
        List of PrerequisiteStatus objects with mastery status
    """
    from .models import PrerequisiteStatus

    all_tasks = _load_all_tasks()
    statuses = []

    for prereq_key in prerequisite_keys:
        task = all_tasks.get(prereq_key)
        if not task:
            logger.warning(f"Prerequisite task not found: {prereq_key}")
            continue

        # Determine status
        threshold = get_mastery_threshold(task.etap)
        best_score = progress.get(prereq_key, 0)
        status = "mastered" if best_score >= threshold else "in_progress"

        # Build URL
        url = f"/task/{task.year}/{task.etap}/{task.number}"

        statuses.append(PrerequisiteStatus(
            key=prereq_key,
            year=task.year,
            etap=task.etap,
            number=task.number,
            title=task.title,
            status=status,
            url=url
        ))

    return statuses
