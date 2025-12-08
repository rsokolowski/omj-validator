#!/usr/bin/env python3
"""
Generate task index files for prerequisite analysis.

This script scans all task JSON files and creates index files sharded by year.
Each year gets its own file: data/task_index/2024.json, data/task_index/2023.json, etc.

Usage:
    python generate_task_index.py              # Generate index files
    python generate_task_index.py --stats      # Show statistics only
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict


def get_task_id(year: str, etap: str, number: int) -> str:
    """Generate task identifier in format: year_etap_number."""
    return f"{year}_{etap}_{number}"


def load_all_tasks(data_dir: Path) -> dict[str, dict]:
    """Load all tasks grouped by year."""
    tasks_by_year = defaultdict(dict)

    for task_path in sorted(data_dir.glob("**/task_*.json")):
        with open(task_path, 'r', encoding='utf-8') as f:
            task = json.load(f)

        # Extract year and etap from path
        parts = task_path.parts
        year = parts[-3]
        etap = parts[-2]
        number = task["number"]

        task_id = get_task_id(year, etap, number)

        tasks_by_year[year][task_id] = {
            "content": task.get("content", ""),
            "difficulty": task.get("difficulty"),
            "skills_required": task.get("skills_required", []),
            "skills_gained": task.get("skills_gained", [])
        }

    return dict(tasks_by_year)


def print_stats(tasks_by_year: dict):
    """Print statistics about the tasks."""
    total = sum(len(tasks) for tasks in tasks_by_year.values())
    print(f"Total tasks: {total}")
    print()

    print("Tasks by year:")
    for year in sorted(tasks_by_year.keys()):
        print(f"  {year}: {len(tasks_by_year[year])}")
    print()

    # By difficulty
    by_diff = defaultdict(int)
    for year, tasks in tasks_by_year.items():
        for task_id, task in tasks.items():
            diff = task.get("difficulty") or "unknown"
            by_diff[diff] += 1

    print("Tasks by difficulty:")
    for diff in sorted(by_diff.keys(), key=lambda x: (isinstance(x, str), x)):
        print(f"  {diff}: {by_diff[diff]}")
    print()

    # Skills coverage
    all_skills_gained = set()
    tasks_with_skills = 0
    for year, tasks in tasks_by_year.items():
        for task_id, task in tasks.items():
            skills = task.get("skills_gained", [])
            if skills:
                tasks_with_skills += 1
                all_skills_gained.update(skills)

    print(f"Tasks with skills_gained: {tasks_with_skills}/{total}")
    print(f"Unique skills gained: {len(all_skills_gained)}")


def main():
    parser = argparse.ArgumentParser(description="Generate task index for prerequisite analysis")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    parser.add_argument("--output-dir", type=str, default="data/task_index",
                        help="Output directory (default: data/task_index)")
    args = parser.parse_args()

    data_dir = Path(__file__).parent / "data" / "tasks"

    print("Loading all tasks...")
    tasks_by_year = load_all_tasks(data_dir)
    total = sum(len(tasks) for tasks in tasks_by_year.values())
    print(f"Loaded {total} tasks from {len(tasks_by_year)} years")
    print()

    if args.stats:
        print_stats(tasks_by_year)
        return

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save one file per year
    for year, tasks in sorted(tasks_by_year.items()):
        output_path = output_dir / f"{year}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print(f"Saved {output_path} ({len(tasks)} tasks)")

    print()
    print(f"Index files saved to: {output_dir}/")
    print()
    print_stats(tasks_by_year)


if __name__ == "__main__":
    main()
