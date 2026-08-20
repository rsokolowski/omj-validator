#!/usr/bin/env python3
"""Access to the locally generated task statements.

The statement of an OMJ task (its title and its full text) is competition
material owned by the organiser, so it is not part of this repository. It is
generated locally from the official PDFs by fix_latex_content.py and stored,
one file per etap, in:

    data/task_content/{year}/{etap}.json

    {
      "year": "2024",
      "etap": "etap1",
      "tasks": {
        "1": {"title": "...", "content": "..."},
        "2": {"title": "...", "content": "..."}
      }
    }

The tracked metadata files (data/tasks/{year}/{etap}/task_{n}.json) hold only
this project's own work: difficulty, categories, hints, prerequisites, skills
and the PDF paths.

This module is for the maintenance scripts at the repository root. The web
application does the same join in app/storage.py, which cannot import from here
because only the app/ package is copied into the Docker image.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TASKS_DATA_DIR = PROJECT_ROOT / "data" / "tasks"
TASK_CONTENT_DIR = PROJECT_ROOT / "data" / "task_content"

EMPTY_STATEMENT = {"title": "", "content": ""}


def content_path(year: str, etap: str) -> Path:
    """Path to the generated statement file for a year/etap."""
    return TASK_CONTENT_DIR / year / f"{etap}.json"


def load_statements(year: str, etap: str) -> dict[str, dict]:
    """Load generated statements for a year/etap, keyed by task number as str.

    Returns an empty dict when the file has not been generated - that is the
    normal state of a fresh checkout, not an error.
    """
    path = content_path(year, etap)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: cannot read {path}: {e}", file=sys.stderr)
        return {}
    statements = data.get("tasks")
    return statements if isinstance(statements, dict) else {}


def save_statements(year: str, etap: str, statements: dict[str, dict]) -> Path:
    """Write the statement file for a year/etap, sorted by task number."""
    path = content_path(year, etap)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "year": year,
        "etap": etap,
        "tasks": {k: statements[k] for k in sorted(statements, key=int)},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def statement_for(year: str, etap: str, number: int) -> dict:
    """Statement of a single task, or empty strings when not generated."""
    return load_statements(year, etap).get(str(number), dict(EMPTY_STATEMENT))


def statement_for_task_path(task_path: Path, number: int) -> dict:
    """Statement for a task addressed by its metadata file path.

    Expects the data/tasks/{year}/{etap}/task_{n}.json layout.
    """
    parts = Path(task_path).parts
    return statement_for(parts[-3], parts[-2], number)


def missing_statement_message(year: str, etap: str) -> str:
    """Uniform hint printed by scripts that need a statement and found none."""
    return (
        f"No generated statement for {year}/{etap}. Run:\n"
        f"    python download_tasks.py --all-etaps --year {year}\n"
        f"    python fix_latex_content.py {year} {etap}"
    )
