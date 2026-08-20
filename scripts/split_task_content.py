#!/usr/bin/env python3
"""One-shot migration: move task statements out of the tracked metadata files.

The repository tracks `data/tasks/{year}/{etap}/task_{n}.json`. Historically each
of those files carried the *statement* of the competition task ("title" and
"content"), transcribed from the OMJ PDFs. That text belongs to the organiser of
the Olimpiada Matematyczna Juniorow, not to this project, so it must not be
redistributed with the source code.

This script splits every task file in two:

  * `data/tasks/{year}/{etap}/task_{n}.json`  - metadata only (tracked, MIT)
  * `data/task_content/{year}/{etap}.json`    - statements (git-ignored)

The statement file is written and verified *before* anything is removed from the
metadata file, so the migration never destroys text that has not been saved
elsewhere yet. Re-running the script is safe: statements already present in the
generated file are kept, and metadata files that no longer carry a statement are
left alone.

Usage:
    python scripts/split_task_content.py --dry-run
    python scripts/split_task_content.py
"""

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TASKS_DATA_DIR = BASE_DIR / "data" / "tasks"
TASK_CONTENT_DIR = BASE_DIR / "data" / "task_content"

# Fields that carry OMJ-owned text and must live in the generated file only.
CONTENT_FIELDS = ("title", "content")


def iter_etaps(tasks_data_dir: Path):
    """Yield (year, etap, [task_file, ...]) for every populated etap directory."""
    if not tasks_data_dir.exists():
        return
    for year_dir in sorted(tasks_data_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        for etap_dir in sorted(year_dir.iterdir()):
            if not etap_dir.is_dir():
                continue
            task_files = sorted(etap_dir.glob("task_*.json"))
            if task_files:
                yield year_dir.name, etap_dir.name, task_files


def load_existing_content(path: Path) -> dict:
    """Load an already generated statement file, tolerating a missing one."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tasks", {})


def split_etap(year: str, etap: str, task_files: list[Path], dry_run: bool) -> tuple[int, int]:
    """Split one etap. Returns (statements_extracted, metadata_files_stripped)."""
    content_path = TASK_CONTENT_DIR / year / f"{etap}.json"
    statements = load_existing_content(content_path)

    extracted = 0
    to_strip: list[tuple[Path, dict]] = []

    for task_file in task_files:
        with open(task_file, "r", encoding="utf-8") as f:
            task = json.load(f)

        present = {k: task[k] for k in CONTENT_FIELDS if k in task}
        if not present:
            continue

        key = str(task["number"])
        statements[key] = {
            "title": present.get("title", ""),
            "content": present.get("content", ""),
        }
        extracted += 1

        stripped = {k: v for k, v in task.items() if k not in CONTENT_FIELDS}
        to_strip.append((task_file, stripped))

    if not extracted:
        return 0, 0

    if dry_run:
        return extracted, len(to_strip)

    # 1. Write the statements first and read them back, so nothing is removed
    #    from the metadata files before the text is safely on disk.
    content_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "year": year,
        "etap": etap,
        "tasks": {k: statements[k] for k in sorted(statements, key=int)},
    }
    with open(content_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    verify = load_existing_content(content_path)
    for task_file, _ in to_strip:
        with open(task_file, "r", encoding="utf-8") as f:
            number = str(json.load(f)["number"])
        if number not in verify:
            raise RuntimeError(
                f"{content_path} is missing task {number} after write - aborting "
                f"before touching {task_file}"
            )

    # 2. Only now rewrite the metadata files without the statement fields.
    for task_file, stripped in to_strip:
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(stripped, f, ensure_ascii=False, indent=2)
            f.write("\n")

    return extracted, len(to_strip)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move task statements out of the tracked metadata files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would change, write nothing"
    )
    args = parser.parse_args()

    total_extracted = 0
    total_stripped = 0
    etaps_touched = 0

    for year, etap, task_files in iter_etaps(TASKS_DATA_DIR):
        extracted, stripped = split_etap(year, etap, task_files, args.dry_run)
        if extracted:
            etaps_touched += 1
            total_extracted += extracted
            total_stripped += stripped
            print(f"  {year}/{etap}: {extracted} statements -> data/task_content/{year}/{etap}.json")

    print()
    if args.dry_run:
        print(f"[dry-run] would extract {total_extracted} statements from {etaps_touched} etaps")
    elif total_extracted:
        print(f"Extracted {total_extracted} statements from {etaps_touched} etaps")
        print(f"Stripped 'title'/'content' from {total_stripped} metadata files")
        print(f"Statements written to: {TASK_CONTENT_DIR}")
    else:
        print("Nothing to do - no metadata file carries a statement any more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
