#!/usr/bin/env python3
"""
Populate task metadata (difficulty, categories, hints) using Claude CLI.

Usage:
    python populate_metadata.py              # Process all tasks
    python populate_metadata.py --dry-run    # Preview without saving
    python populate_metadata.py --limit 5    # Process only 5 tasks
"""

import json
import subprocess
import sys
from pathlib import Path
import argparse
import re

# Valid categories based on OMJ problem analysis
VALID_CATEGORIES = [
    "algebra",        # Systems of equations, algebraic identities, inequalities
    "geometria",      # Plane geometry: triangles, quadrilaterals, circles
    "teoria_liczb",   # Divisibility, primes, digits, diophantine equations
    "kombinatoryka",  # Counting, existence, pigeonhole, tournaments
    "logika",         # Weighing problems, grids, game theory, strategy
    "arytmetyka",     # Averages, ratios, basic calculations
]

PROMPT_TEMPLATE = """Przeanalizuj poniższe zadanie z Olimpiady Matematycznej Juniorów i przypisz mu:

1. **difficulty** (trudność): liczba od 1 do 5, gdzie:
   - 1 = bardzo łatwe (podstawowe zastosowanie wzorów)
   - 2 = łatwe (wymaga prostego wglądu)
   - 3 = średnie (kilka kroków rozumowania)
   - 4 = trudne (wymaga znacznego wglądu)
   - 5 = bardzo trudne (kreatywne podejście)

2. **categories** (kategorie): lista z następujących opcji:
   - algebra (układy równań, tożsamości algebraiczne, nierówności)
   - geometria (geometria płaska: trójkąty, czworokąty, okręgi)
   - teoria_liczb (podzielność, liczby pierwsze, cyfry, równania diofantyczne)
   - kombinatoryka (zliczanie, dowody istnienia, zasada szufladkowa, turnieje)
   - logika (ważenie, optymalizacja na tablicach, teoria gier, strategia)
   - arytmetyka (średnie, stosunki, proste obliczenia)

3. **hints** (wskazówki): DOKŁADNIE 4 progresywne wskazówki po polsku, które pomagają
   uczniowi samodzielnie dojść do rozwiązania. Wskazówki oparte na metodzie Pólyi:

   [0] ZROZUMIENIE - Pomóż zrozumieć/przeformułować problem:
       - Pytania pomocnicze: "Co jest dane? Czego szukamy?"
       - Sugestia narysowania diagramu lub rozważenia przykładu
       - Przeformułowanie problemu własnymi słowami
       Przykład: "Spróbuj narysować sytuację dla małych wartości n."

   [1] STRATEGIA - Zasugeruj ogólne podejście (bez szczegółów):
       - Wskaż typ rozumowania: dowód nie wprost, indukcja, przypadki
       - Zasugeruj technikę: zasada szufladkowa, niezmienniki, praca od końca
       - NIE podawaj konkretnych kroków
       Przykład: "Rozważ użycie zasady szufladkowej."

   [2] KIERUNEK - Naprowadź na kluczowy wgląd:
       - Wskaż ważną własność do zauważenia
       - Zasugeruj co warto zbadać lub policzyć
       - Zwróć uwagę na szczególny przypadek
       Przykład: "Zwróć uwagę na parzystość sumy elementów."

   [3] WSKAZÓWKA - Konkretna wskazówka (bez pełnego rozwiązania):
       - Podaj konkretny pierwszy krok lub przekształcenie
       - Wskaż kluczowe równanie lub nierówność
       - Opisz podział na przypadki
       Przykład: "Przekształć wyrażenie do postaci (a-b)² + ..."

   WAŻNE dla wskazówek:
   - Pisz po polsku, zwięźle (1-2 zdania każda)
   - Każda kolejna wskazówka bardziej szczegółowa
   - Używaj notacji LaTeX dla matematyki: $x^2$ dla inline
   - Przykłady: $\\sqrt{{2}}$, $\\frac{{a}}{{b}}$, $\\angle ABC$, $\\triangle ABC$

   ZAKAZ SPOILERÓW - TO KRYTYCZNE:
   - NIGDY nie podawaj konkretnych wartości liczbowych będących odpowiedzią
   - NIGDY nie podawaj końcowego wyniku obliczeń (np. "kąt wynosi 30°")
   - NIGDY nie przeprowadzaj pełnego rozumowania - zostaw pracę uczniowi
   - Wskazówki mają NAPROWADZAĆ, nie ROZWIĄZYWAĆ
   - Nawet ostatnia wskazówka powinna zostawić uczniowi coś do zrobienia
   - ZŁE: "Oblicz, że α = 30°, więc..."
   - DOBRE: "Spróbuj wyznaczyć miarę kąta α z układu równań"

   OGRANICZENIA MATEMATYCZNE (OMJ to olimpiada dla klas 4-8, wiek 10-14 lat):
   - ZAKAZ: trygonometria (sin, cos, tan, ctg), pochodne, całki, logarytmy
   - ZAKAZ: wzory Viète'a, wzór na pierwiastki równania kwadratowego
   - ZAKAZ: zaawansowana geometria analityczna, wektory
   - DOZWOLONE: twierdzenie Pitagorasa, podobieństwo trójkątów, pola figur
   - DOZWOLONE: własności kątów, równoległość, prostopadłość
   - DOZWOLONE: podzielność, reszty z dzielenia, NWD, NWW
   - DOZWOLONE: proste równania i nierówności, układy równań liniowych
   - DOZWOLONE: zasada szufladkowa, zliczanie, indukcja w prostej formie

Wskazówki dla oceny trudności:
- Etap 1 zwykle ma zadania o trudności 1-3
- Etap 2 zwykle ma zadania o trudności 3-5
- Zadanie może mieć więcej niż jedną kategorię jeśli łączy różne dziedziny

---
ZADANIE (rok: {year}, etap: {etap}, nr: {number}):

Tytuł: {title}

Treść: {content}
---

PRZYPOMNIENIE KRYTYCZNE przed odpowiedzią:
1. ŻADNEJ trygonometrii (sin, cos, tan) - uczeń ma 10-14 lat!
2. ŻADNYCH konkretnych wartości liczbowych w odpowiedziach (nie pisz "α = 30°" ani "α = 45° - γ")
3. Wskazówki mają NAPROWADZAĆ metodą pytań, nie wykonywać obliczeń za ucznia

Odpowiedz TYLKO w formacie JSON.
"""


JSON_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "difficulty": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5,
            "description": "Task difficulty: 1=very easy, 5=very hard"
        },
        "categories": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": VALID_CATEGORIES
            },
            "minItems": 1,
            "description": "Mathematical categories"
        },
        "hints": {
            "type": "array",
            "items": {
                "type": "string",
                "minLength": 10,
                "maxLength": 300
            },
            "minItems": 4,
            "maxItems": 4,
            "description": "4 progressive hints: [0]=understanding, [1]=strategy, [2]=direction, [3]=specific guidance"
        }
    },
    "required": ["difficulty", "categories", "hints"]
})


def call_claude(prompt: str, model: str = "opus") -> str:
    """Call Claude CLI and return the response."""
    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--output-format", "json",
                "--json-schema", JSON_SCHEMA,
                "--tools", "",  # Disable tools for simple analysis
                "--model", model
            ],
            capture_output=True,
            text=True,
            timeout=120
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


def parse_response(response: str) -> dict | None:
    """Parse Claude's JSON response."""
    if not response:
        return None

    try:
        # Claude CLI json output has structure with "structured_output" for json-schema responses
        cli_response = json.loads(response)

        # Extract the structured_output field (the actual schema-validated output)
        if "structured_output" in cli_response:
            data = cli_response["structured_output"]
        elif "result" in cli_response and isinstance(cli_response["result"], dict):
            data = cli_response["result"]
        else:
            print(f"  No structured_output in response")
            return None

        # Validate difficulty
        difficulty = data.get("difficulty")
        if not isinstance(difficulty, int) or difficulty < 1 or difficulty > 5:
            print(f"  Invalid difficulty: {difficulty}")
            return None

        # Validate categories
        categories = data.get("categories", [])
        if not isinstance(categories, list):
            categories = [categories] if categories else []

        valid_cats = [c for c in categories if c in VALID_CATEGORIES]
        if not valid_cats:
            print(f"  No valid categories in: {categories}")
            return None

        # Validate hints
        hints = data.get("hints", [])
        if not isinstance(hints, list) or len(hints) != 4:
            print(f"  Invalid hints count: {len(hints) if isinstance(hints, list) else 'not a list'}")
            return None

        # Ensure all hints are non-empty strings
        hints = [str(h).strip() for h in hints if h]
        if len(hints) != 4:
            print(f"  Some hints were empty")
            return None

        return {
            "difficulty": difficulty,
            "categories": valid_cats,
            "hints": hints
        }
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  Response was: {response[:500]}")
        return None


def is_fully_populated(task: dict) -> bool:
    """Check if task has all metadata populated."""
    return (
        task.get("difficulty") is not None
        and len(task.get("categories", [])) > 0
        and len(task.get("hints", [])) == 4
    )


def process_task(task_path: Path, dry_run: bool = False, model: str = "opus", force: bool = False) -> bool:
    """Process a single task file."""
    with open(task_path, 'r', encoding='utf-8') as f:
        task = json.load(f)

    # Skip if already fully populated (unless force)
    if is_fully_populated(task) and not force:
        return True

    # Extract task info from path
    parts = task_path.parts
    year = parts[-3]
    etap = parts[-2]

    prompt = PROMPT_TEMPLATE.format(
        year=year,
        etap=etap,
        number=task["number"],
        title=task["title"],
        content=task["content"]
    )

    response = call_claude(prompt, model=model)
    result = parse_response(response)

    if not result:
        print(f"  Failed to parse response")
        return False

    print(f"  -> difficulty={result['difficulty']}, categories={result['categories']}")
    print(f"     hints:")
    for i, hint in enumerate(result['hints']):
        level = ["ZROZUMIENIE", "STRATEGIA", "KIERUNEK", "WSKAZÓWKA"][i]
        # Truncate hint for display
        hint_display = hint[:60] + "..." if len(hint) > 60 else hint
        print(f"       [{i}] {level}: {hint_display}")

    if not dry_run:
        task["difficulty"] = result["difficulty"]
        task["categories"] = result["categories"]
        task["hints"] = result["hints"]

        with open(task_path, 'w', encoding='utf-8') as f:
            json.dump(task, f, ensure_ascii=False, indent=2)

    return True


def main():
    parser = argparse.ArgumentParser(description="Populate task metadata using Claude CLI")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--limit", type=int, help="Limit number of tasks to process")
    parser.add_argument("--year", type=str, help="Process only specific year")
    parser.add_argument("--etap", type=str, help="Process only specific etap")
    parser.add_argument("--task", type=int, help="Process only specific task number")
    parser.add_argument("--model", type=str, default="opus", help="Claude model to use (default: opus)")
    parser.add_argument("--force", action="store_true", help="Regenerate even if already populated")
    args = parser.parse_args()

    data_dir = Path(__file__).parent / "data" / "tasks"

    # Find all task JSON files
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
        rel_path = task_path.relative_to(data_dir)

        # Check if already populated
        with open(task_path, 'r', encoding='utf-8') as f:
            task = json.load(f)

        if is_fully_populated(task) and not args.force:
            print(f"[{i}/{len(task_files)}] {rel_path} - SKIPPED (already populated)")
            skipped += 1
            continue

        print(f"[{i}/{len(task_files)}] {rel_path}")

        if process_task(task_path, args.dry_run, args.model, args.force):
            success += 1
        else:
            failed += 1

    print()
    print(f"Done! Success: {success}, Failed: {failed}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
