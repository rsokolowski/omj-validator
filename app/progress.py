"""
Progress tracking and recommendation engine for OMJ Validator.

Computes user progress across all tasks, determines task status
(locked/unlocked/mastered), and generates diverse recommendations.
"""

import logging
from typing import Optional

from .storage import _load_all_tasks, get_task_key, get_task_stats
from .models import TaskInfo, TaskStatus, GraphNode, GraphEdge, ProgressData

logger = logging.getLogger(__name__)


def get_mastery_threshold(etap: str) -> int:
    """Get the score threshold for mastery based on etap.

    - etap2: score >= 5 (max is 6)
    - etap1: score >= 2 (max is 3)
    """
    return 5 if etap == "etap2" else 2


def compute_user_progress() -> dict[str, int]:
    """Compute best scores for all tasks from submissions.

    Uses get_task_stats() which efficiently reads submission files.

    Returns:
        Dict mapping task_key -> best_score
    """
    all_tasks = _load_all_tasks()
    progress = {}

    for key, task in all_tasks.items():
        stats = get_task_stats(task.year, task.etap, task.number)
        if stats.highest_score > 0:
            progress[key] = stats.highest_score

    return progress


def is_task_mastered(task_key: str, progress: dict[str, int]) -> bool:
    """Check if a task is mastered based on score threshold.

    Args:
        task_key: Task key in format year_etap_number
        progress: Dict of task_key -> best_score

    Returns:
        True if task score meets mastery threshold
    """
    parts = task_key.split("_")
    if len(parts) >= 3 and parts[1] in ("etap1", "etap2"):
        etap = parts[1]
        threshold = get_mastery_threshold(etap)
        return progress.get(task_key, 0) >= threshold
    return False


def are_prerequisites_met(
    task: TaskInfo,
    progress: dict[str, int],
    all_tasks: dict[str, TaskInfo],
    visited: set[str] = None
) -> bool:
    """Check if all prerequisites (including transitive) are mastered.

    Handles transitive dependencies: if A requires B and B requires C,
    then A requires both B and C to be mastered.

    Args:
        task: The task to check prerequisites for
        progress: Dict of task_key -> best_score
        all_tasks: Dict of all tasks for looking up transitive deps
        visited: Set of already-visited task keys (for cycle detection)

    Returns:
        True if all prerequisites (direct and transitive) are mastered
    """
    if visited is None:
        visited = set()

    task_key = get_task_key(task.year, task.etap, task.number)

    # Cycle detection
    if task_key in visited:
        logger.warning(f"Circular dependency detected involving task {task_key}")
        return True  # Break cycle by assuming met

    visited.add(task_key)

    for prereq_key in task.prerequisites:
        # Validate prerequisite key format
        parts = prereq_key.split("_")
        if len(parts) < 3 or parts[1] not in ("etap1", "etap2"):
            logger.warning(f"Invalid prerequisite key format: {prereq_key} in task {task_key}")
            continue

        # Check if direct prerequisite is mastered
        if not is_task_mastered(prereq_key, progress):
            return False

        # Check transitive prerequisites (prerequisite's prerequisites)
        prereq_task = all_tasks.get(prereq_key)
        if prereq_task and prereq_task.prerequisites:
            if not are_prerequisites_met(prereq_task, progress, all_tasks, visited.copy()):
                return False

    return True


def get_task_status(
    task: TaskInfo,
    progress: dict[str, int],
    all_tasks: dict[str, TaskInfo] = None
) -> TaskStatus:
    """Determine if a task is locked, unlocked, or mastered.

    Handles transitive dependencies automatically - only direct prerequisites
    need to be specified in task metadata.

    Args:
        task: The task to check
        progress: Dict of task_key -> best_score
        all_tasks: Dict of all tasks (for transitive dependency lookup)

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

    # Check if locked (any prerequisite or transitive prerequisite not mastered)
    if not are_prerequisites_met(task, progress, all_tasks):
        return TaskStatus.LOCKED

    return TaskStatus.UNLOCKED


def build_graph_nodes(progress: dict[str, int]) -> list[GraphNode]:
    """Build graph nodes for all tasks with their status.

    Args:
        progress: Dict of task_key -> best_score

    Returns:
        List of GraphNode objects
    """
    all_tasks = _load_all_tasks()
    nodes = []

    for key, task in all_tasks.items():
        status = get_task_status(task, progress, all_tasks)
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


def build_progress_data(category_filter: Optional[str] = None) -> ProgressData:
    """Build complete progress data for the progress page.

    Args:
        category_filter: Optional category to filter graph by

    Returns:
        ProgressData with nodes, edges, recommendations, and stats
    """
    progress = compute_user_progress()
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
