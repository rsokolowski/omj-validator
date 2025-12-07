#!/usr/bin/env python3
"""
Populate task metadata (difficulty, categories, hints) using Gemini API.

Usage:
    python populate_metadata_gemini.py              # Process all tasks
    python populate_metadata_gemini.py --dry-run    # Preview without saving
    python populate_metadata_gemini.py --limit 5    # Process only 5 tasks
    python populate_metadata_gemini.py --year 2024 --etap etap2  # Specific year/etap
"""

import json
import os
import sys
from pathlib import Path
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import google.generativeai as genai
except ImportError:
    print("Error: google-generativeai not installed. Run: pip install google-generativeai")
    sys.exit(1)

# Pricing per 1M tokens (Gemini 3 Pro, <= 200k context)
INPUT_PRICE_PER_1M = 2.00
OUTPUT_PRICE_PER_1M = 12.00

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

Odpowiedz TYLKO w formacie JSON z polami: difficulty (int 1-5), categories (lista stringów), hints (lista 4 stringów).
"""

# Token usage tracking
class TokenTracker:
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def add(self, input_tokens: int, output_tokens: int):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def get_cost(self) -> float:
        input_cost = (self.total_input_tokens / 1_000_000) * INPUT_PRICE_PER_1M
        output_cost = (self.total_output_tokens / 1_000_000) * OUTPUT_PRICE_PER_1M
        return input_cost + output_cost

    def get_summary(self) -> str:
        input_cost = (self.total_input_tokens / 1_000_000) * INPUT_PRICE_PER_1M
        output_cost = (self.total_output_tokens / 1_000_000) * OUTPUT_PRICE_PER_1M
        total_cost = input_cost + output_cost
        return (
            f"Tokens: {self.total_input_tokens:,} input + {self.total_output_tokens:,} output\n"
            f"Cost:   ${input_cost:.4f} (input) + ${output_cost:.4f} (output) = ${total_cost:.4f} total"
        )


def call_gemini(prompt: str, model_name: str, tracker: TokenTracker) -> dict | None:
    """Call Gemini API and return parsed response with token tracking."""
    try:
        model = genai.GenerativeModel(
            model_name,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.3,
            )
        )

        response = model.generate_content(prompt)

        # Track tokens
        if response.usage_metadata:
            tracker.add(
                response.usage_metadata.prompt_token_count or 0,
                response.usage_metadata.candidates_token_count or 0
            )

        # Parse JSON response
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")
            print(f"  Response: {response.text[:500]}")
            return None

    except Exception as e:
        print(f"  Gemini API error: {e}")
        return None


def validate_response(data: dict) -> dict | None:
    """Validate and normalize the response data."""
    if not data:
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


def is_fully_populated(task: dict) -> bool:
    """Check if task has all metadata populated."""
    return (
        task.get("difficulty") is not None
        and len(task.get("categories", [])) > 0
        and len(task.get("hints", [])) == 4
    )


def process_task(task_path: Path, model_name: str, tracker: TokenTracker,
                 dry_run: bool = False, force: bool = False) -> bool:
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

    response = call_gemini(prompt, model_name, tracker)
    result = validate_response(response)

    if not result:
        print(f"  Failed to get valid response")
        return False

    print(f"  -> difficulty={result['difficulty']}, categories={result['categories']}")
    print(f"     hints:")
    for i, hint in enumerate(result['hints']):
        level = ["ZROZUMIENIE", "STRATEGIA", "KIERUNEK", "WSKAZÓWKA"][i]
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
    parser = argparse.ArgumentParser(description="Populate task metadata using Gemini API")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument("--limit", type=int, help="Limit number of tasks to process")
    parser.add_argument("--year", type=str, help="Process only specific year")
    parser.add_argument("--etap", type=str, help="Process only specific etap")
    parser.add_argument("--force", action="store_true", help="Regenerate even if already populated")
    args = parser.parse_args()

    # Get API key and model from environment
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment. Check .env file.")
        sys.exit(1)

    # Configure Gemini
    genai.configure(api_key=api_key)

    print(f"Using model: {model_name}")
    print(f"Pricing: ${INPUT_PRICE_PER_1M:.2f}/1M input, ${OUTPUT_PRICE_PER_1M:.2f}/1M output")
    print()

    data_dir = Path(__file__).parent / "data" / "tasks"

    # Find all task JSON files
    task_files = sorted(data_dir.glob("**/task_*.json"))

    # Filter by year/etap if specified
    if args.year:
        task_files = [f for f in task_files if f.parts[-3] == args.year]
    if args.etap:
        task_files = [f for f in task_files if f.parts[-2] == args.etap]

    # Apply limit
    if args.limit:
        task_files = task_files[:args.limit]

    print(f"Processing {len(task_files)} tasks...")
    if args.dry_run:
        print("(DRY RUN - no files will be modified)")
    print()

    tracker = TokenTracker()
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

        if process_task(task_path, model_name, tracker, args.dry_run, args.force):
            success += 1
        else:
            failed += 1

        # Show running cost estimate every 10 tasks
        if i % 10 == 0:
            print(f"  [Running cost: ${tracker.get_cost():.4f}]")

    print()
    print("=" * 50)
    print(f"Results: Success={success}, Failed={failed}, Skipped={skipped}")
    print()
    print("Cost Estimation:")
    print(tracker.get_summary())
    print("=" * 50)


if __name__ == "__main__":
    main()
