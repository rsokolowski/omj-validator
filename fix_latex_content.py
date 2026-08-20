#!/usr/bin/env python3
"""
Generate task statements (title + content) with proper LaTeX notation.

The statement of an OMJ task belongs to the competition organiser, so it is NOT
part of this repository. This script rebuilds it locally: it reads the official
tasks PDF for an etap (downloaded by download_tasks.py) and uses Claude to
transcribe each task into LaTeX.

Input:  tasks/{year}/{etap}/*.pdf            (downloaded, git-ignored)
        data/tasks/{year}/{etap}/task_*.json (metadata, tracked in git)
Output: data/task_content/{year}/{etap}.json (git-ignored)

The application runs fine without this step - tasks then show a link to the PDF
instead of the statement (see app/storage.py).

Usage:
    python fix_latex_content.py 2024 etap1              # One etap
    python fix_latex_content.py 2024 etap1 --dry-run    # Preview without saving
    python fix_latex_content.py --all                   # All etaps (slow, ~62 calls)
    python fix_latex_content.py --all --skip-existing   # Only what is missing
"""

import json
import subprocess
import sys
from pathlib import Path
import argparse

from task_content import (
    PROJECT_ROOT,
    TASKS_DATA_DIR,
    TASK_CONTENT_DIR,
    load_statements,
    save_statements,
)


def get_tasks_pdf_path(task_meta: dict) -> Path | None:
    """Get the tasks PDF path referenced by a task metadata file."""
    pdf_rel_path = task_meta.get("pdf", {}).get("tasks")
    if not pdf_rel_path:
        return None

    # PDF path is relative to project root
    pdf_path = PROJECT_ROOT / pdf_rel_path
    return pdf_path if pdf_path.exists() else None


def load_tasks_for_etap(year: str, etap: str) -> list[dict]:
    """Load all task metadata files for a year/etap."""
    data_dir = TASKS_DATA_DIR / year / etap

    if not data_dir.exists():
        return []

    tasks = []
    for task_file in sorted(data_dir.glob("task_*.json")):
        with open(task_file, "r", encoding="utf-8") as f:
            task = json.load(f)
        tasks.append(task)

    return tasks


def call_claude_with_pdf(
    pdf_path: Path,
    tasks: list[dict],
    statements: dict[str, dict],
    model: str = "opus",
) -> str:
    """Call Claude CLI with PDF and the current (possibly empty) statements."""

    # Build the prompt. Tasks with no statement yet are sent with empty strings -
    # the PDF is the source of truth either way.
    tasks_json = json.dumps(
        [
            {
                "number": t["number"],
                "title": statements.get(str(t["number"]), {}).get("title", ""),
                "content": statements.get(str(t["number"]), {}).get("content", ""),
            }
            for t in tasks
        ],
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""Najpierw przeczytaj plik PDF z zadaniami: {pdf_path}

Następnie zaktualizuj poniższe zadania na podstawie PDF-a. PDF jest źródłem prawdy - popraw wszelkie
nieścisłości, braki lub uproszczenia w obecnych opisach. Puste pola title/content oznaczają, że treść
trzeba przepisać z PDF-a od zera.

OBECNE ZADANIA (mogą być puste lub zawierać błędy/braki - zweryfikuj z PDF):
{tasks_json}

INSTRUKCJE:
1. Użyj narzędzia Read, aby przeczytać PDF: {pdf_path}
2. PDF JEST ŹRÓDŁEM PRAWDY - jeśli obecny opis różni się od PDF-a, użyj wersji z PDF-a
3. Popraw wszelkie:
   - Brakujące fragmenty treści (obecny opis mógł pominąć szczegóły)
   - Nieprecyzyjne wyrażenia matematyczne (uproszczone przy transkrypcji)
   - Błędy w przepisaniu (literówki, złe znaki)
4. Dodaj poprawną notację LaTeX:
   - √(...) → $\\sqrt{{...}}$
   - ∠ABC → $\\angle ABC$
   - ≥, ≤, ≠ → $\\geq$, $\\leq$, $\\neq$
   - ×, ÷, · → $\\times$, $\\div$, $\\cdot$
   - ², ³, ⁿ → $^2$, $^3$, $^n$
   - Ułamki → $\\frac{{licznik}}{{mianownik}}$
   - π → $\\pi$
   - △ABC → $\\triangle ABC$
   - Odcinki/punkty w kontekście geometrycznym: $AB$, $P$
   - Zmienne i liczby w wyrażeniach: $n$, $x$, $a_1$
5. Używaj $...$ dla inline math
6. NIE zmieniaj numerów zadań
7. Tytuł powinien być krótki i opisowy (może zawierać LaTeX jeśli to formuła)
8. Treść musi być KOMPLETNA i DOKŁADNA jak w PDF

Odpowiedz TYLKO w formacie JSON: {{"tasks": [...]}} gdzie każdy element ma pola: number, title, content
"""

    json_schema = json.dumps({
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "title": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["number", "title", "content"]
                }
            }
        },
        "required": ["tasks"]
    })

    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--output-format", "json",
                "--json-schema", json_schema,
                "--allowed-tools", "Read",
                "--model", model,
                "--add-dir", str(pdf_path.parent),
                "--no-session-persistence"
            ],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            print(f"  Claude CLI error (rc={result.returncode}): {result.stderr}", file=sys.stderr)
            print(f"  stdout: {result.stdout[:500] if result.stdout else 'empty'}", file=sys.stderr)
            return ""

        if not result.stdout.strip():
            print(f"  Empty response from Claude CLI", file=sys.stderr)
            print(f"  stderr: {result.stderr}", file=sys.stderr)
            return ""

        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print("  Claude CLI timeout", file=sys.stderr)
        return ""
    except FileNotFoundError:
        print("  Claude CLI not found", file=sys.stderr)
        sys.exit(1)


def parse_response(response: str) -> list[dict] | None:
    """Parse Claude's JSON response."""
    if not response:
        return None

    try:
        cli_response = json.loads(response)

        # Extract structured output
        if "structured_output" in cli_response:
            data = cli_response["structured_output"]
        elif "result" in cli_response and isinstance(cli_response["result"], dict):
            data = cli_response["result"]
        else:
            print(f"  No structured_output in response")
            return None

        # Handle wrapper object with "tasks" field
        if isinstance(data, dict) and "tasks" in data:
            data = data["tasks"]

        if not isinstance(data, list):
            print(f"  Response is not a list: {type(data)}")
            return None

        return data
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None


def is_complete(tasks: list[dict], statements: dict[str, dict]) -> bool:
    """True when every task of the etap already has a non-empty statement."""
    for task in tasks:
        statement = statements.get(str(task["number"]))
        if not statement or not (statement.get("content") or "").strip():
            return False
    return bool(tasks)


def process_etap(
    year: str,
    etap: str,
    dry_run: bool = False,
    model: str = "opus",
    skip_existing: bool = False,
) -> bool:
    """Process all tasks for a year/etap."""
    print(f"\nProcessing {year}/{etap}...")

    tasks = load_tasks_for_etap(year, etap)
    if not tasks:
        print(f"  No tasks found for {year}/{etap}")
        return False

    statements = load_statements(year, etap)

    if skip_existing and is_complete(tasks, statements):
        print(f"  Already generated ({len(tasks)} tasks) - skipping")
        return True

    print(f"  Found {len(tasks)} tasks ({len(statements)} already have a statement)")

    # Get PDF path from first task
    pdf_path = get_tasks_pdf_path(tasks[0])
    if not pdf_path:
        print(f"  No PDF found for {year}/{etap} - run: python download_tasks.py --all-etaps")
        return False

    print(f"  Using PDF: {pdf_path.name}")

    # Call Claude
    response = call_claude_with_pdf(pdf_path, tasks, statements, model)
    result = parse_response(response)

    if not result:
        print(f"  Failed to get valid response")
        return False

    # Match results to tasks and update
    result_by_number = {r["number"]: r for r in result}

    updated = 0
    for task in tasks:
        task_num = task["number"]
        if task_num not in result_by_number:
            print(f"  Warning: No result for task {task_num}")
            continue

        new_data = result_by_number[task_num]
        current = statements.get(str(task_num), {})
        old_title = current.get("title", "")
        old_content = current.get("content", "")
        new_title = new_data["title"]
        new_content = new_data["content"]

        # Check if changed
        title_changed = old_title != new_title
        content_changed = old_content != new_content

        if title_changed or content_changed:
            print(f"\n  Task {task_num}:")
            if title_changed:
                print(f"    Title: {old_title[:50] or '(brak)'}...")
                print(f"        -> {new_title[:50]}...")
            if content_changed:
                print(f"    Content updated (LaTeX added)")

            statements[str(task_num)] = {"title": new_title, "content": new_content}
            updated += 1

    if updated and not dry_run:
        path = save_statements(year, etap, statements)
        print(f"\n  Wrote {path}")

    print(f"\n  Updated {updated}/{len(tasks)} tasks")
    return True


def get_all_etaps() -> list[tuple[str, str]]:
    """Get all year/etap combinations."""
    etaps = []

    if not TASKS_DATA_DIR.exists():
        return etaps

    for year_dir in sorted(TASKS_DATA_DIR.iterdir()):
        if not year_dir.is_dir():
            continue
        for etap_dir in sorted(year_dir.iterdir()):
            if not etap_dir.is_dir():
                continue
            # Check if has task files
            if list(etap_dir.glob("task_*.json")):
                etaps.append((year_dir.name, etap_dir.name))

    return etaps


def main():
    parser = argparse.ArgumentParser(description="Generate task statements with LaTeX notation")
    parser.add_argument("year", nargs="?", help="Year to process")
    parser.add_argument("etap", nargs="?", help="Etap to process (etap1, etap2 or etap3)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--model", default="opus", help="Claude model to use")
    parser.add_argument("--all", action="store_true", help="Process all etaps")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip etaps whose statements are already generated")
    args = parser.parse_args()

    if args.all:
        etaps = get_all_etaps()
        print(f"Processing {len(etaps)} etaps...")

        success = 0
        failed = 0
        for year, etap in etaps:
            if process_etap(year, etap, args.dry_run, args.model, args.skip_existing):
                success += 1
            else:
                failed += 1

        print(f"\nDone! Success: {success}, Failed: {failed}")
        print(f"Statements live in: {TASK_CONTENT_DIR}")

    elif args.year and args.etap:
        process_etap(args.year, args.etap, args.dry_run, args.model, args.skip_existing)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
