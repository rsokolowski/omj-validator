#!/usr/bin/env python3
"""
Create initial task JSON files for a given etap.

This script creates placeholder task JSON files that can then be populated
using fix_latex_content.py.

Usage:
    python create_tasks.py 2024 etap3           # Create tasks for specific year/etap
    python create_tasks.py --etap 3 --all       # Create tasks for all years with etap3 PDFs
"""

import json
import argparse
from pathlib import Path

# Task counts per etap (standard for OMJ/OMG)
TASK_COUNTS = {
    "etap1": 7,  # First stage: 7 tasks
    "etap2": 5,  # Second stage: 5 tasks
    "etap3": 5,  # Finals: 5 tasks
}


def get_pdf_paths(year: str, etap: str) -> dict:
    """Get PDF paths for a year/etap."""
    tasks_dir = Path("tasks") / year / etap
    if not tasks_dir.exists():
        return {}

    pdfs = {"tasks": None, "solutions": None, "statistics": None}

    for pdf in tasks_dir.glob("*.pdf"):
        name = pdf.name.lower()
        # Skip generic statistics files
        if name in ("staty_3etap.pdf", "staty_3etap_viii.pdf"):
            continue

        if "st" in name or "staty" in name or "final_" in name:
            if pdfs["statistics"] is None:
                pdfs["statistics"] = f"tasks/{year}/{etap}/{pdf.name}"
        elif "r.pdf" in name or "-r." in name or "rr.pdf" in name:
            if pdfs["solutions"] is None:
                pdfs["solutions"] = f"tasks/{year}/{etap}/{pdf.name}"
        else:
            if pdfs["tasks"] is None:
                pdfs["tasks"] = f"tasks/{year}/{etap}/{pdf.name}"

    return {k: v for k, v in pdfs.items() if v is not None}


def create_task_files(year: str, etap: str, task_count: int, dry_run: bool = False) -> int:
    """Create task JSON files for a year/etap."""
    data_dir = Path("data") / "tasks" / year / etap
    pdf_paths = get_pdf_paths(year, etap)

    if not pdf_paths.get("tasks"):
        print(f"  No tasks PDF found for {year}/{etap}")
        return 0

    if not dry_run:
        data_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    for task_num in range(1, task_count + 1):
        task_file = data_dir / f"task_{task_num}.json"

        if task_file.exists():
            print(f"  task_{task_num}.json already exists, skipping")
            continue

        task = {
            "number": task_num,
            "title": f"Zadanie {task_num}",
            "content": "Treść zadania do uzupełnienia.",
            "pdf": pdf_paths,
            "difficulty": None,
            "categories": [],
            "hints": [],
        }

        if not dry_run:
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task, f, ensure_ascii=False, indent=2)

        print(f"  Created task_{task_num}.json")
        created += 1

    return created


def get_years_with_etap(etap: str) -> list[str]:
    """Get all years that have PDFs for the given etap."""
    tasks_dir = Path("tasks")
    years = []

    for year_dir in sorted(tasks_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        etap_dir = year_dir / etap
        if etap_dir.exists() and list(etap_dir.glob("*.pdf")):
            # Check if there's a tasks PDF (not just statistics)
            pdfs = get_pdf_paths(year_dir.name, etap)
            if pdfs.get("tasks"):
                years.append(year_dir.name)

    return years


def main():
    parser = argparse.ArgumentParser(description="Create initial task JSON files")
    parser.add_argument("year", nargs="?", help="Year to process")
    parser.add_argument("etap", nargs="?", help="Etap to process (etap1, etap2, etap3)")
    parser.add_argument("--etap", dest="etap_flag", help="Etap to process with --all")
    parser.add_argument("--all", action="store_true", help="Process all years with PDFs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating files")
    args = parser.parse_args()

    # Allow --etap flag to override positional etap
    if args.etap_flag:
        args.etap = args.etap_flag

    if args.all and args.etap:
        # Process all years for specified etap
        etap = args.etap
        years = get_years_with_etap(etap)
        print(f"Creating tasks for {len(years)} years with {etap} PDFs...")

        total_created = 0
        for year in years:
            print(f"\n{year}/{etap}:")
            task_count = TASK_COUNTS.get(etap, 5)
            created = create_task_files(year, etap, task_count, args.dry_run)
            total_created += created

        print(f"\nTotal tasks created: {total_created}")

    elif args.year and args.etap:
        # Process specific year/etap
        task_count = TASK_COUNTS.get(args.etap, 5)
        print(f"Creating {task_count} tasks for {args.year}/{args.etap}...")
        create_task_files(args.year, args.etap, task_count, args.dry_run)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
