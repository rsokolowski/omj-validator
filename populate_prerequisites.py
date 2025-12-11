#!/usr/bin/env python3
"""
Populate task prerequisites using Claude CLI.

This script analyzes each task in context of all other tasks and identifies
direct prerequisite tasks that would help a student prepare for the current task.

Prerequisites are selected based on:
- Skills gained that match skills required by the current task
- Similar or lower difficulty
- Direct helpers only (not transitive dependencies)

Usage:
    python populate_prerequisites.py                          # Process all tasks without prerequisites
    python populate_prerequisites.py --year 2024 --etap etap3 # Process specific year/etap
    python populate_prerequisites.py --force                  # Regenerate all prerequisites
    python populate_prerequisites.py --dry-run                # Preview without saving
"""

import json
import subprocess
import sys
from pathlib import Path
import argparse


INDEX_DIR = Path(__file__).parent / "data" / "task_index"


def get_task_id(year: str, etap: str, number: int) -> str:
    """Generate task identifier."""
    return f"{year}_{etap}_{number}"


def get_all_task_ids() -> set[str]:
    """Get all task IDs from index files."""
    task_ids = set()
    for index_file in INDEX_DIR.glob("*.json"):
        with open(index_file, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
            task_ids.update(tasks.keys())
    return task_ids


def get_index_files_list() -> str:
    """Get formatted list of index files for the prompt."""
    files = sorted(INDEX_DIR.glob("*.json"))
    return "\n".join(f"  - {f}" for f in files)


def build_prompt(task_id: str, task_data: dict, index_dir: Path) -> str:
    """
    Build the prompt for Claude.
    Static instructions first, dynamic task data at the end (for caching).
    """
    index_files = get_index_files_list()

    return f"""Jesteś ekspertem od Olimpiady Matematycznej Juniorów (OMJ).
Twoim zadaniem jest analiza zadania i wskazanie 0-3 zadań prerequisite,
które pomogą uczniowi przygotować się do rozwiązania danego zadania.

## INDEKS ZADAŃ

Przeczytaj pliki indeksu z katalogu {index_dir.absolute()}/
Każdy plik zawiera zadania z danego roku w formacie JSON:
{index_files}

Każde zadanie w indeksie ma:
- content: pełna treść zadania
- difficulty: trudność (1-5, gdzie 5 to najtrudniejsze)
- skills_required: umiejętności wymagane do rozwiązania
- skills_gained: umiejętności rozwijane przez rozwiązanie

Klucz zadania ma format: rok_etap_numer (np. "2024_etap3_1")

## KRYTERIA WYBORU PREREQUISITES

1. **Bezpośrednie pomocniki**: Wybierz zadania, które BEZPOŚREDNIO przygotowują do rozwiązania
   analizowanego zadania. NIE wybieraj zadań, które są pomocne pośrednio (przez inne zadania).

2. **Rozwijane umiejętności**: Priorytetowo wybieraj zadania, których skills_gained
   pokrywają się ze skills_required analizowanego zadania.

3. **Trudność**: Preferuj zadania o trudności MNIEJSZEJ LUB RÓWNEJ analizowanemu zadaniu.
   Prerequisite nie powinno być trudniejsze niż zadanie docelowe.

4. **Różnorodność**: Jeśli wybierasz więcej niż 1 prerequisite, staraj się pokryć
   różne aspekty/umiejętności potrzebne do rozwiązania zadania.

5. **Jakość ponad ilość**: Lepiej wybrać 1 trafne prerequisite niż 3 słabe.
   Jeśli zadanie jest proste lub nie wymaga specjalnych przygotowań, zwróć pustą listę.

6. **Brak cykli**: NIE wybieraj zadania, które analizujesz, jako swojego prerequisite.

## PROCES

1. Przeczytaj wszystkie pliki indeksu z {index_dir.absolute()}/
2. Przeanalizuj zadanie poniżej
3. Znajdź zadania które najlepiej przygotują ucznia
4. Zwróć listę 0-3 identyfikatorów zadań

## FORMAT ODPOWIEDZI

Odpowiedz TYLKO w formacie JSON z listą identyfikatorów zadań (0-3 elementy):
{{"prerequisites": ["2023_etap1_5", "2022_etap2_3"]}}

Jeśli brak odpowiednich prerequisites, zwróć pustą listę:
{{"prerequisites": []}}

---

## ZADANIE DO ANALIZY

Identyfikator: {task_id}
Tytuł: {task_data.get('title', 'Brak tytułu')}
Trudność: {task_data.get('difficulty', 'nieznana')}
Kategorie: {task_data.get('categories', [])}
Wymagane umiejętności: {task_data.get('skills_required', [])}
Rozwijane umiejętności: {task_data.get('skills_gained', [])}

Treść:
{task_data.get('content', 'Brak treści')}

---

Przeczytaj pliki indeksu i wskaż 0-3 bezpośrednich prerequisites.
"""


def build_json_schema() -> str:
    """Build JSON schema for Claude output (simplified - no enum)."""
    schema = {
        "type": "object",
        "properties": {
            "prerequisites": {
                "type": "array",
                "items": {
                    "type": "string",
                    "pattern": "^[0-9]{4}_etap[1-3]_[0-9]+$"
                },
                "minItems": 0,
                "maxItems": 3,
                "description": "List of 0-3 prerequisite task IDs in format: year_etap_number"
            }
        },
        "required": ["prerequisites"]
    }
    return json.dumps(schema)


def call_claude(prompt: str, json_schema: str, model: str = "opus") -> str:
    """Call Claude CLI with read permissions and return the response."""
    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--output-format", "json",
                "--json-schema", json_schema,
                "--allowedTools", "Read,Glob",  # Allow reading files
                "--model", model,
                "--no-session-persistence"
            ],
            capture_output=True,
            text=True,
            timeout=300  # Longer timeout for reading files
        )
        if result.returncode != 0:
            print(f"  Claude CLI error: {result.stderr}", file=sys.stderr)
            return ""
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print("  Claude CLI timeout", file=sys.stderr)
        return ""
    except FileNotFoundError:
        print("  Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code", file=sys.stderr)
        sys.exit(1)


def parse_response(response: str, current_task_id: str, all_task_ids: set) -> list[str] | None:
    """Parse Claude's JSON response."""
    if not response:
        return None

    try:
        cli_response = json.loads(response)

        # Extract structured_output
        if "structured_output" in cli_response:
            data = cli_response["structured_output"]
        elif "result" in cli_response and isinstance(cli_response["result"], dict):
            data = cli_response["result"]
        else:
            print(f"  No structured_output in response")
            return None

        prerequisites = data.get("prerequisites", [])

        # Validate
        if not isinstance(prerequisites, list):
            return None

        # Filter: only valid task IDs, not self-referencing
        valid_prereqs = [
            p for p in prerequisites
            if p in all_task_ids and p != current_task_id
        ]

        # Warn about invalid IDs
        invalid = [p for p in prerequisites if p not in all_task_ids]
        if invalid:
            print(f"  Warning: invalid task IDs ignored: {invalid}")

        # Limit to 3
        return valid_prereqs[:3]

    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None


def has_prerequisites(task: dict) -> bool:
    """Check if task already has prerequisites defined."""
    prereqs = task.get("prerequisites", [])
    return isinstance(prereqs, list) and len(prereqs) > 0


def process_task(
    task_path: Path,
    task_id: str,
    json_schema: str,
    all_task_ids: set,
    dry_run: bool = False,
    model: str = "opus"
) -> bool:
    """Process a single task file."""
    # Load task data
    with open(task_path, 'r', encoding='utf-8') as f:
        task_data = json.load(f)

    # Build prompt
    prompt = build_prompt(task_id, task_data, INDEX_DIR)

    # Call Claude
    response = call_claude(prompt, json_schema, model)
    prerequisites = parse_response(response, task_id, all_task_ids)

    if prerequisites is None:
        print(f"  Failed to parse response")
        return False

    print(f"  -> prerequisites: {prerequisites if prerequisites else '(none)'}")

    if not dry_run:
        # Update prerequisites
        task_data["prerequisites"] = prerequisites

        # Save
        with open(task_path, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, ensure_ascii=False, indent=2)

    return True


def main():
    parser = argparse.ArgumentParser(description="Populate task prerequisites using Claude CLI")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--limit", type=int, help="Limit number of tasks to process")
    parser.add_argument("--year", type=str, help="Process only specific year")
    parser.add_argument("--etap", type=str, help="Process only specific etap")
    parser.add_argument("--task", type=int, help="Process only specific task number")
    parser.add_argument("--model", type=str, default="opus", help="Claude model (default: opus)")
    parser.add_argument("--force", action="store_true", help="Regenerate even if prerequisites exist")
    args = parser.parse_args()

    # Check index files exist
    if not INDEX_DIR.exists() or not any(INDEX_DIR.glob("*.json")):
        print(f"Error: Task index not found at {INDEX_DIR}")
        print("Run 'python generate_task_index.py' first to create it.")
        sys.exit(1)

    # Get all task IDs for validation
    print("Loading task IDs from index...")
    all_task_ids = get_all_task_ids()
    print(f"Found {len(all_task_ids)} tasks in index")
    print()

    # Build JSON schema
    json_schema = build_json_schema()

    # Find all task JSON files
    data_dir = Path(__file__).parent / "data" / "tasks"
    task_files = sorted(data_dir.glob("**/task_*.json"))

    # Filter by year/etap/task if specified
    if args.year:
        task_files = [f for f in task_files if f.parts[-3] == args.year]
    if args.etap:
        task_files = [f for f in task_files if f.parts[-2] == args.etap]
    if args.task:
        task_files = [f for f in task_files if f.name == f"task_{args.task}.json"]

    # Apply limit
    if args.limit:
        task_files = task_files[:args.limit]

    print(f"Processing {len(task_files)} tasks...")
    if args.dry_run:
        print("(DRY RUN - no files will be modified)")
    print()

    success = 0
    failed = 0
    skipped = 0

    for i, task_path in enumerate(task_files, 1):
        # Build task ID from path
        parts = task_path.parts
        year = parts[-3]
        etap = parts[-2]
        number = int(task_path.stem.split("_")[1])
        task_id = get_task_id(year, etap, number)

        # Check if already has prerequisites
        with open(task_path, 'r', encoding='utf-8') as f:
            task = json.load(f)

        if has_prerequisites(task) and not args.force:
            print(f"[{i}/{len(task_files)}] {task_id} - SKIPPED (has prerequisites)")
            skipped += 1
            continue

        print(f"[{i}/{len(task_files)}] {task_id}")

        if process_task(
            task_path, task_id, json_schema, all_task_ids,
            args.dry_run, args.model
        ):
            success += 1
        else:
            failed += 1

    print()
    print(f"Done! Success: {success}, Failed: {failed}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
