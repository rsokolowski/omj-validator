#!/usr/bin/env python3
"""Migrate tasks.json to year-based structure with index."""

import json
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).parent.parent
OLD_TASKS_PATH = BASE_DIR / "data" / "tasks.json"
NEW_TASKS_DIR = BASE_DIR / "data" / "tasks"


def migrate():
    # Load old data
    with open(OLD_TASKS_PATH, "r", encoding="utf-8") as f:
        old_data = json.load(f)

    print(f"Loaded {len(old_data)} tasks from tasks.json")

    # Group by year and etap
    years_data = defaultdict(lambda: defaultdict(list))

    for key, task in old_data.items():
        year = task["year"]
        etap = task["etap"]
        # Store task without redundant year/etap fields
        task_entry = {
            "number": task["number"],
            "title": task["title"],
            "content": task["content"],
            "has_solution": task.get("has_solution", False),
        }
        if task.get("has_statistics"):
            task_entry["has_statistics"] = True
        years_data[year][etap].append(task_entry)

    # Sort tasks by number within each etap
    for year in years_data:
        for etap in years_data[year]:
            years_data[year][etap].sort(key=lambda t: t["number"])

    # Create index and year files
    NEW_TASKS_DIR.mkdir(parents=True, exist_ok=True)

    index = {}
    for year in sorted(years_data.keys()):
        year_data = dict(years_data[year])

        # Build index entry
        index[year] = {}
        for etap, tasks in year_data.items():
            index[year][etap] = {"count": len(tasks)}

        # Write year file
        year_file = NEW_TASKS_DIR / f"{year}.json"
        with open(year_file, "w", encoding="utf-8") as f:
            json.dump(year_data, f, ensure_ascii=False, indent=2)
        print(f"Created {year_file.name} with {sum(len(t) for t in year_data.values())} tasks")

    # Write index
    index_file = NEW_TASKS_DIR / "index.json"
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"Created index.json with {len(index)} years")

    print("\nMigration complete!")
    print(f"You can now delete {OLD_TASKS_PATH} after verifying the new structure works.")


if __name__ == "__main__":
    migrate()
