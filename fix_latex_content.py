#!/usr/bin/env python3
"""
Fix task titles and content to use proper LaTeX notation.

This script reads the tasks PDF for an etap and uses Claude to extract
properly formatted LaTeX content for each task.

Usage:
    python fix_latex_content.py 2024 etap1           # Fix specific etap
    python fix_latex_content.py 2024 etap1 --dry-run # Preview without saving
    python fix_latex_content.py --all                # Fix all etaps
"""

import json
import subprocess
import sys
from pathlib import Path
import argparse
import base64


def get_tasks_pdf_path(task_json_path: Path) -> Path | None:
    """Get the tasks PDF path from a task JSON file."""
    with open(task_json_path, 'r', encoding='utf-8') as f:
        task = json.load(f)

    pdf_rel_path = task.get("pdf", {}).get("tasks")
    if not pdf_rel_path:
        return None

    # PDF path is relative to project root
    project_root = Path(__file__).parent
    pdf_path = project_root / pdf_rel_path

    if pdf_path.exists():
        return pdf_path
    return None


def load_tasks_for_etap(year: str, etap: str) -> list[dict]:
    """Load all task JSON files for a year/etap."""
    data_dir = Path(__file__).parent / "data" / "tasks" / year / etap

    if not data_dir.exists():
        return []

    tasks = []
    for task_file in sorted(data_dir.glob("task_*.json")):
        with open(task_file, 'r', encoding='utf-8') as f:
            task = json.load(f)
            task["_file_path"] = str(task_file)
        tasks.append(task)

    return tasks


def call_claude_with_pdf(pdf_path: Path, tasks: list[dict], model: str = "opus") -> str:
    """Call Claude CLI with PDF and task data."""

    # Build the prompt
    tasks_json = json.dumps(
        [{"number": t["number"], "title": t["title"], "content": t["content"]} for t in tasks],
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""Najpierw przeczytaj plik PDF z zadaniami: {pdf_path}

Następnie zaktualizuj poniższe zadania na podstawie PDF-a. PDF jest źródłem prawdy - popraw wszelkie
nieścisłości, braki lub uproszczenia w obecnych opisach.

OBECNE ZADANIA (mogą zawierać błędy/braki - zweryfikuj z PDF):
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
                "--add-dir", str(pdf_path.parent)
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


def process_etap(year: str, etap: str, dry_run: bool = False, model: str = "opus") -> bool:
    """Process all tasks for a year/etap."""
    print(f"\nProcessing {year}/{etap}...")

    tasks = load_tasks_for_etap(year, etap)
    if not tasks:
        print(f"  No tasks found for {year}/{etap}")
        return False

    print(f"  Found {len(tasks)} tasks")

    # Get PDF path from first task
    pdf_path = get_tasks_pdf_path(Path(tasks[0]["_file_path"]))
    if not pdf_path:
        print(f"  No PDF found for {year}/{etap}")
        return False

    print(f"  Using PDF: {pdf_path.name}")

    # Call Claude
    response = call_claude_with_pdf(pdf_path, tasks, model)
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
        old_title = task["title"]
        old_content = task["content"]
        new_title = new_data["title"]
        new_content = new_data["content"]

        # Check if changed
        title_changed = old_title != new_title
        content_changed = old_content != new_content

        if title_changed or content_changed:
            print(f"\n  Task {task_num}:")
            if title_changed:
                print(f"    Title: {old_title[:50]}...")
                print(f"        -> {new_title[:50]}...")
            if content_changed:
                print(f"    Content updated (LaTeX added)")

            if not dry_run:
                task["title"] = new_title
                task["content"] = new_content

                # Remove internal field and save
                file_path = Path(task.pop("_file_path"))
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(task, f, ensure_ascii=False, indent=2)

            updated += 1

    print(f"\n  Updated {updated}/{len(tasks)} tasks")
    return True


def get_all_etaps() -> list[tuple[str, str]]:
    """Get all year/etap combinations."""
    data_dir = Path(__file__).parent / "data" / "tasks"
    etaps = []

    for year_dir in sorted(data_dir.iterdir()):
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
    parser = argparse.ArgumentParser(description="Fix task content with LaTeX notation")
    parser.add_argument("year", nargs="?", help="Year to process")
    parser.add_argument("etap", nargs="?", help="Etap to process (etap1 or etap2)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--model", default="opus", help="Claude model to use")
    parser.add_argument("--all", action="store_true", help="Process all etaps")
    args = parser.parse_args()

    if args.all:
        etaps = get_all_etaps()
        print(f"Processing {len(etaps)} etaps...")

        success = 0
        failed = 0
        for year, etap in etaps:
            if process_etap(year, etap, args.dry_run, args.model):
                success += 1
            else:
                failed += 1

        print(f"\nDone! Success: {success}, Failed: {failed}")

    elif args.year and args.etap:
        process_etap(args.year, args.etap, args.dry_run, args.model)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
