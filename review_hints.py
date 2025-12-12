#!/usr/bin/env python3
"""
Review task hints for quality, logical consistency, and grade-appropriateness.

Uses Gemini API to analyze existing hints and regenerate them if needed.

Usage:
    python review_hints.py --year 2024 --etap etap1 --task 1    # Review specific task
    python review_hints.py --year 2024 --etap etap1              # Review all tasks in etap
    python review_hints.py --year 2024                           # Review all tasks in year
    python review_hints.py --dry-run                             # Preview without saving
    python review_hints.py --model gemini-2.5-pro                # Specific Gemini model
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Load environment variables from .env (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on environment variables

# Gemini SDK - uses same SDK as app (google-genai)
GEMINI_AVAILABLE = False
genai = None
types = None
GEMINI_PRICING = None
try:
    from google import genai
    from google.genai import types
    from app.ai.providers.gemini import GEMINI_PRICING
    GEMINI_AVAILABLE = True
except ImportError:
    pass


def fix_json_escapes(text: str) -> str:
    """
    Fix common JSON escape issues in Gemini responses.

    Gemini sometimes returns LaTeX with unescaped backslashes like \\{ instead of \\\\{
    """
    # Fix invalid escapes: \{ \} \[ \] etc. that should be \\{ \\} etc.
    # But preserve valid escapes like \n \t \"
    valid_escapes = {'n', 't', 'r', 'b', 'f', '\\', '"', '/', 'u'}

    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            next_char = text[i + 1]
            if next_char in valid_escapes:
                # Valid escape, keep as-is
                result.append(text[i:i+2])
                i += 2
            elif next_char == '\\':
                # Already escaped backslash
                result.append('\\\\')
                i += 2
            else:
                # Invalid escape - double the backslash
                result.append('\\\\')
                i += 1
        else:
            result.append(text[i])
            i += 1

    return ''.join(result)


# Valid categories for reference
VALID_CATEGORIES = [
    "algebra", "geometria", "teoria_liczb", "kombinatoryka", "logika", "arytmetyka"
]


def load_skills_description() -> str:
    """Load skills for context in the prompt."""
    skills_path = Path(__file__).parent / "data" / "skills.json"
    if not skills_path.exists():
        return ""

    with open(skills_path, 'r', encoding='utf-8') as f:
        skills_data = json.load(f)

    skills = skills_data.get("skills", {})
    skills_desc = []
    for skill_id, skill_info in skills.items():
        name = skill_info.get("name", skill_id)
        skills_desc.append(f"   - {skill_id}: {name}")

    return "\n".join(skills_desc)


SKILLS_DESCRIPTION = load_skills_description()


# Prompt for hint review
# NOTE: Prompt is structured for LLM cache efficiency - static instructions first, dynamic task data last
REVIEW_PROMPT_TEMPLATE = """Jesteś ekspertem od Olimpiady Matematycznej Juniorów (OMJ).
Twoim zadaniem jest ocena wskazówek do zadań matematycznych.

================================================================================
INSTRUKCJE ANALIZY (przeczytaj uważnie przed przystąpieniem do zadania)
================================================================================

## KROK 1: Znajdź ELEGANCKIE rozwiązanie (DUCH OJM)

OMJ ceni ELEGANCKIE, SPRYTNE rozwiązania, nie mechaniczne obliczenia.
Najpierw SAM rozwiąż zadanie, szukając NAJBARDZIEJ ELEGANCKIEGO podejścia.

HIERARCHIA PODEJŚĆ (od najlepszego do najgorszego):
1. NAJLEPSZE: Sprytna obserwacja, symetria, kluczowy wgląd geometryczny
   - Przykład: "Zauważ że trójkąty ABC i DEF są przystające, więc..."
   - Przykład: "Punkt E leży na dwusiecznej, więc jest równoodległy od..."
   - Przykład: "Obróć figurę o 90° wokół punktu P..."

2. DOBRE: Użycie znanych twierdzeń w sprytny sposób
   - Przykład: "Kąt wpisany oparty na średnicy jest prosty"
   - Przykład: "Trójkąty przystające dają równość odcinków"

3. AKCEPTOWALNE: Proste obliczenia algebraiczne z wglądem
   - Przykład: "Oznacz bok kwadratu przez a i zauważ że..."

4. DO UNIKANIA: Mechaniczne "brute force" - rachunki bez wglądu
   - Przykład: "Wprowadź układ współrzędnych, podstaw, oblicz, sprawdź"
   - To podejście jest OSTATECZNOŚCIĄ, nie pierwszym wyborem!

KLUCZOWA ZASADA: Wskazówki powinny prowadzić do rozwiązania w DUCHU OJM - takiego,
które sprawia że uczeń poczuje się SPRYTNY gdy je znajdzie, nie zmęczony rachunkami.

DOZWOLONE narzędzia (klasy 6-8, wiek 12-14 lat):
- Twierdzenie Pitagorasa, przystawanie i podobieństwo trójkątów
- Własności kątów, dwusieczne, symetrie, obroty
- Okręgi wpisane/opisane, kąty wpisane i środkowe
- Podzielność, reszty z dzielenia, NWD, NWW
- Proste równania i nierówności, układy równań liniowych
- Zasada szufladkowa, zliczanie, prosta indukcja

ZABRONIONE (uczeń tego NIE ZNA):
- Trygonometria (sin, cos, tan, ctg)
- Wzory Viète'a, wzór na pierwiastki równania kwadratowego
- Logarytmy, pochodne, całki
- Zaawansowana geometria analityczna, wektory
- Twierdzenia olimpiadowe (Ceva, Menelaus, Stewart, etc.)

## KROK 2: Oceń CZY wskazówki prowadzą do ELEGANCKIEGO rozwiązania

Dla obecnych wskazówek sprawdź:
a) Czy prowadzą do rozwiązania ELEGANCKIEGO czy MECHANICZNEGO?
b) Czy kluczowy WGLĄD/OBSERWACJA jest zasugerowany we wskazówkach?
c) Czy uczeń po przeczytaniu wskazówek poczuje się SPRYTNY czy ZMĘCZONY?

PRZYKŁADY ZŁYCH WSKAZÓWEK (prowadzą do "brute force"):
- "Wprowadź układ współrzędnych..." → mechaniczne podstawianie
- "Oblicz wszystkie długości i sprawdź czy zachodzi równość..." → rachunek bez wglądu
- "Oznacz zmienne i rozwiąż układ równań..." → algebra zamiast geometrii
- "Sprawdź kolejne przypadki dla n=1,2,3,..." → siłowe przeszukiwanie

PRZYKŁADY DOBRYCH WSKAZÓWEK (prowadzą do elegancji):
- "Poszukaj przystających lub podobnych trójkątów" → szuka struktury
- "Czy widzisz jakieś ukryte równe odcinki lub kąty?" → naprowadza na obserwację
- "Pomyśl o symetrii figury" → geometryczny wgląd
- "Co się stanie jeśli obrócisz/odbijesz część figury?" → transformacje

## KROK 3: Sprawdź czy wskazówki są SPÓJNE i PROGRESYWNE

Przejdź przez wskazówki 0→1→2→3 i sprawdź:
- Czy tworzą SPÓJNĄ ścieżkę do ELEGANCKIEGO rozwiązania?
- Czy każda wskazówka NATURALNIE prowadzi do następnej?
- Czy poziom szczegółowości rośnie: ogólne → konkretne?
- Czy NIE MA luk logicznych ani spoilerów?

## KROK 4: Decyzja

Wskazówki WYMAGAJĄ POPRAWY jeśli:
- Prowadzą do rozwiązania MECHANICZNEGO zamiast ELEGANCKIEGO
- Sugerują "brute force" (współrzędne, rachunki) zamiast WGLĄDU
- Pomijają KLUCZOWĄ obserwację która czyni rozwiązanie eleganckim
- Zawierają spoilery, luki logiczne, lub niezrozumiały język
- Używają zabronionych narzędzi

Jeśli wskazówki prowadzą do rozwiązania poprawnego ALE nieeleganckiego - POPRAW JE
tak aby prowadziły do rozwiązania w DUCHU OJM.

================================================================================
ROLE WSKAZÓWEK
================================================================================

- [0] ZROZUMIENIE: Pytania pomocnicze, sugestia rysunku, przeformułowanie problemu
      Przykład: "Narysuj dokładny rysunek i zaznacz wszystkie dane. Co dokładnie masz udowodnić?"
- [1] STRATEGIA: Ogólne podejście - szukaj symetrii, przystających trójkątów, równych odcinków
      Przykład: "Poszukaj przystających trójkątów lub wykorzystaj symetrię figury."
- [2] KIERUNEK: Naprowadź na KLUCZOWY wgląd - tę obserwację która "otwiera" rozwiązanie
      Przykład: "Zwróć uwagę na trójkąty przy wierzchołku X - co mają wspólnego?"
- [3] WSKAZÓWKA: Konkretna wskazówka wynikająca z wglądu, ale bez pełnego rozwiązania
      Przykład: "Wykorzystaj fakt, że punkt P jest równoodległy od trzech innych punktów."

================================================================================
ZASADY DLA NOWYCH WSKAZÓWEK (jeśli będziesz je pisać)
================================================================================

1. Pisz po polsku, PROSTYM językiem zrozumiałym dla 12-14 latka
2. Każda wskazówka to 1-2 zdania, max 300 znaków
3. NIE dodawaj prefiksów [0], [1] etc. - to tylko czysty tekst wskazówki
4. Używaj LaTeX dla matematyki: $x^2$, $\\sqrt{{2}}$, $\\frac{{a}}{{b}}$, $\\triangle ABC$
5. ŻADNYCH spoilerów - nie podawaj wartości liczbowych będących odpowiedzią
6. ŻADNEJ trygonometrii ani zaawansowanych narzędzi
7. Każda wskazówka MUSI logicznie prowadzić do następnej
8. Ostatnia wskazówka zostawia uczniowi pracę do wykonania (nie rozwiązuje za niego)

KLUCZOWE - DUCH OJM:
9. Wskazówki MUSZĄ prowadzić do ELEGANCKIEGO rozwiązania, nie mechanicznego
10. UNIKAJ: współrzędnych, "brute force", długich rachunków
11. PREFERUJ: symetrie, przystawanie trójkątów, kąty wpisane, sprytne obserwacje
12. Kluczowy WGLĄD powinien być zasugerowany (nie podany wprost) we wskazówce [2] lub [3]
13. Uczeń po rozwiązaniu powinien czuć się SPRYTNY, nie zmęczony

================================================================================
FORMAT ODPOWIEDZI (JSON)
================================================================================

Jeśli wskazówki są DOBRE (review_passed = true):
{{
  "review_passed": true,
  "issues": [],
  "analysis": "Szczegółowe wyjaśnienie: dlaczego wskazówki są poprawne, jak prowadzą do rozwiązania",
  "new_hints": null
}}

Jeśli wskazówki wymagają POPRAWY (review_passed = false):
{{
  "review_passed": false,
  "issues": ["Opis problemu 1", "Opis problemu 2"],
  "analysis": "Szczegółowe wyjaśnienie znalezionych problemów i dlaczego wymagają poprawy",
  "new_hints": [
    "Tekst wskazówki poziomu ZROZUMIENIE (bez prefiksu [0])",
    "Tekst wskazówki poziomu STRATEGIA (bez prefiksu [1])",
    "Tekst wskazówki poziomu KIERUNEK (bez prefiksu [2])",
    "Tekst wskazówki poziomu WSKAZÓWKA (bez prefiksu [3])"
  ]
}}

Odpowiedz TYLKO w formacie JSON.

================================================================================
ZADANIE DO ANALIZY
================================================================================

Rok: {year}, Etap: {etap}, Zadanie nr: {number}
Tytuł: {title}
Trudność: {difficulty}/5
Kategorie: {categories}
Umiejętności: {skills_required}

TREŚĆ ZADANIA:
{content}

---
OBECNE WSKAZÓWKI DO OCENY:

[0] ZROZUMIENIE:
{hint_0}

[1] STRATEGIA:
{hint_1}

[2] KIERUNEK:
{hint_2}

[3] WSKAZÓWKA:
{hint_3}

---
Przeanalizuj BARDZO DOKŁADNIE i KROK PO KROKU powyższe wskazówki.
Myśl głęboko i systematycznie. Rozważ każdy aspekt starannie.
Odpowiedz w formacie JSON.
"""


def build_json_schema_dict() -> dict:
    """Build JSON schema dict for review response."""
    return {
        "type": "object",
        "properties": {
            "review_passed": {
                "type": "boolean",
                "description": "True if existing hints are acceptable, false if they need replacement"
            },
            "issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of issues found with existing hints"
            },
            "analysis": {
                "type": "string",
                "description": "Detailed analysis of the hints"
            },
            "new_hints": {
                "type": "array",
                "items": {"type": "string"},
                "description": "New hints if review failed, empty array if passed"
            }
        },
        "required": ["review_passed", "issues", "analysis", "new_hints"]
    }


# Schema as dict for Gemini API (response_json_schema)
JSON_SCHEMA_DICT = build_json_schema_dict()

# Schema as JSON string (for reference/debugging)
JSON_SCHEMA = json.dumps(JSON_SCHEMA_DICT)


# Fallback pricing if import fails
_DEFAULT_PRICING = {"input": 0.10, "output": 0.40}


def _get_pricing(model_name: str) -> dict:
    """Get pricing for a model, with fallback."""
    if GEMINI_PRICING:
        return GEMINI_PRICING.get(model_name, GEMINI_PRICING.get("default", _DEFAULT_PRICING))
    return _DEFAULT_PRICING


class TokenTracker:
    """Track token usage and costs for Gemini API (thread-safe)."""

    # Cached tokens are charged at 10% of normal input price (90% discount)
    CACHE_DISCOUNT = 0.10

    def __init__(self, model_name: str = "default"):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cached_tokens = 0
        self.cache_hits = 0  # Number of requests with cache hits
        self.total_requests = 0
        self.model_name = model_name
        self._lock = threading.Lock()

    def add(self, input_tokens: int, output_tokens: int, cached_tokens: int = 0):
        with self._lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cached_tokens += cached_tokens
            self.total_requests += 1
            if cached_tokens > 0:
                self.cache_hits += 1

    def get_cost(self) -> float:
        """Get total cost accounting for cache discount."""
        with self._lock:
            pricing = _get_pricing(self.model_name)
            # Cached tokens are charged at reduced rate, non-cached at full rate
            non_cached_input = self.total_input_tokens - self.total_cached_tokens
            cached_cost = (self.total_cached_tokens / 1_000_000) * pricing["input"] * self.CACHE_DISCOUNT
            non_cached_cost = (non_cached_input / 1_000_000) * pricing["input"]
            output_cost = (self.total_output_tokens / 1_000_000) * pricing["output"]
            return cached_cost + non_cached_cost + output_cost

    def get_summary(self) -> str:
        with self._lock:
            pricing = _get_pricing(self.model_name)

            # Calculate costs
            non_cached_input = self.total_input_tokens - self.total_cached_tokens
            cached_cost = (self.total_cached_tokens / 1_000_000) * pricing["input"] * self.CACHE_DISCOUNT
            non_cached_cost = (non_cached_input / 1_000_000) * pricing["input"]
            input_cost = cached_cost + non_cached_cost
            output_cost = (self.total_output_tokens / 1_000_000) * pricing["output"]
            total_cost = input_cost + output_cost

            # Calculate what cost would have been without caching
            full_input_cost = (self.total_input_tokens / 1_000_000) * pricing["input"]
            cost_without_cache = full_input_cost + output_cost
            savings = cost_without_cache - total_cost

            # Cache statistics
            cache_rate = (self.total_cached_tokens / self.total_input_tokens * 100) if self.total_input_tokens > 0 else 0
            hit_rate = (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0

            lines = [
                f"Tokens: {self.total_input_tokens:,} input + {self.total_output_tokens:,} output",
                f"Cache:  {self.total_cached_tokens:,} tokens cached ({cache_rate:.1f}% of input)",
                f"        {self.cache_hits}/{self.total_requests} requests hit cache ({hit_rate:.1f}%)",
                f"Cost:   ${input_cost:.4f} (input) + ${output_cost:.4f} (output) = ${total_cost:.4f} total",
            ]

            if savings > 0:
                lines.append(f"Saved:  ${savings:.4f} from caching (would be ${cost_without_cache:.4f} without cache)")

            return "\n".join(lines)


def call_gemini(prompt: str, model_name: str, tracker: TokenTracker, client, max_retries: int = 6) -> tuple[dict | None, list[str]]:
    """
    Call Gemini API and return parsed JSON response.

    Args:
        prompt: The prompt to send
        model_name: Gemini model name
        tracker: Token tracker for cost estimation
        client: Gemini client instance
        max_retries: Number of retries on failure

    Returns: (parsed_response, output_lines) - output_lines for deferred printing
    """
    output_lines = []

    if not GEMINI_AVAILABLE:
        output_lines.append("  Error: google-genai not installed")
        return None, output_lines

    for attempt in range(max_retries):
        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=JSON_SCHEMA_DICT,
                temperature=0.3,
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )

            # Track tokens (including cached tokens for implicit caching)
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
                cached_tokens = getattr(response.usage_metadata, "cached_content_token_count", 0) or 0
                tracker.add(input_tokens, output_tokens, cached_tokens)

            response_text = response.text if hasattr(response, "text") else ""

            if not response_text:
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s...
                    output_lines.append(f"  Empty response (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                output_lines.append("  Gemini returned empty response")
                return None, output_lines

            # Parse JSON response - try direct parse first
            try:
                return json.loads(response_text), output_lines
            except json.JSONDecodeError as e:
                # Try fixing common escape issues
                fixed_text = fix_json_escapes(response_text)
                try:
                    result = json.loads(fixed_text)
                    output_lines.append(f"  (Fixed JSON escapes on attempt {attempt + 1})")
                    return result, output_lines
                except json.JSONDecodeError:
                    if attempt < max_retries - 1:
                        output_lines.append(f"  JSON parse error (attempt {attempt + 1}/{max_retries}), retrying...")
                        continue
                    output_lines.append(f"  Gemini JSON parse error: {e}")
                    output_lines.append(f"  Response: {response_text[:500]}")
                    return None, output_lines

        except Exception as e:
            error_str = str(e)
            if attempt < max_retries - 1:
                # Exponential backoff for API errors (especially 503 overload)
                delay = 2 ** attempt * 2  # 2s, 4s, 8s for API errors
                output_lines.append(f"  Gemini API error (attempt {attempt + 1}/{max_retries}): {e}, retrying in {delay}s...")
                time.sleep(delay)
                continue
            output_lines.append(f"  Gemini API error: {e}")
            return None, output_lines

    return None, output_lines


def has_hints(task: dict) -> bool:
    """Check if task has hints to review."""
    hints = task.get("hints", [])
    return isinstance(hints, list) and len(hints) == 4


class ReviewStats:
    """Statistics for the review run (thread-safe)."""

    def __init__(self, total: int = 0):
        self.total = total
        self.reviewed = 0
        self.passed = 0
        self.updated = 0
        self.failed = 0
        self.skipped = 0
        self.failed_tasks: list[str] = []
        self._lock = threading.Lock()

    def add_reviewed(self, updated: bool):
        with self._lock:
            self.reviewed += 1
            if updated:
                self.updated += 1
            else:
                self.passed += 1

    def add_failed(self, task_path: str = None):
        with self._lock:
            self.failed += 1
            if task_path:
                self.failed_tasks.append(task_path)

    def add_skipped(self):
        with self._lock:
            self.skipped += 1


def validate_gemini_response(data: dict) -> dict | None:
    """Validate Gemini's direct JSON response."""
    if not data:
        return None

    # Validate required fields
    review_passed = data.get("review_passed")
    if not isinstance(review_passed, bool):
        print(f"  Invalid review_passed: {review_passed}")
        return None

    issues = data.get("issues", [])
    if not isinstance(issues, list):
        issues = []

    analysis = data.get("analysis", "")
    if not isinstance(analysis, str):
        analysis = str(analysis)

    # Handle new_hints: empty array or null means no new hints (when review passed)
    new_hints = data.get("new_hints")
    if isinstance(new_hints, list) and len(new_hints) == 0:
        new_hints = None  # Treat empty array as null
    elif new_hints is not None:
        if not isinstance(new_hints, list) or len(new_hints) != 4:
            print(f"  Invalid new_hints: expected 4 items, got {len(new_hints) if isinstance(new_hints, list) else type(new_hints)}")
            return None
        new_hints = [str(h).strip() for h in new_hints if h]
        if len(new_hints) != 4:
            print(f"  Some new hints were empty")
            return None

    return {
        "review_passed": review_passed,
        "issues": issues,
        "analysis": analysis,
        "new_hints": new_hints
    }


def process_task(
    task_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
    gemini_model: str = "gemini-2.5-flash",
    tracker: TokenTracker | None = None,
    gemini_client=None
) -> tuple[bool, bool, list[str]]:
    """
    Process a single task file using Gemini API.

    Returns: (success, hints_updated, output_lines)
    """
    output_lines = []

    with open(task_path, 'r', encoding='utf-8') as f:
        task = json.load(f)

    # Skip if no hints to review
    if not has_hints(task):
        return True, False, output_lines

    # Extract task info from path
    parts = task_path.parts
    year = parts[-3]
    etap = parts[-2]

    hints = task.get("hints", [])

    prompt = REVIEW_PROMPT_TEMPLATE.format(
        year=year,
        etap=etap,
        number=task.get("number", "?"),
        title=task.get("title", ""),
        content=task.get("content", ""),
        difficulty=task.get("difficulty", "?"),
        categories=", ".join(task.get("categories", [])),
        skills_required=", ".join(task.get("skills_required", [])),
        hint_0=hints[0] if len(hints) > 0 else "",
        hint_1=hints[1] if len(hints) > 1 else "",
        hint_2=hints[2] if len(hints) > 2 else "",
        hint_3=hints[3] if len(hints) > 3 else "",
    )

    # Call Gemini API
    if tracker is None:
        tracker = TokenTracker(model_name=gemini_model)
    gemini_response, gemini_output = call_gemini(prompt, gemini_model, tracker, gemini_client)
    output_lines.extend(gemini_output)
    result = validate_gemini_response(gemini_response)

    if not result:
        output_lines.append("  Failed to parse response")
        return False, False, output_lines

    # Collect analysis output
    if result["review_passed"]:
        output_lines.append("  PASSED - hints are good")
        if verbose:
            output_lines.append(f"  Analysis: {result['analysis'][:200]}...")
        return True, False, output_lines
    else:
        output_lines.append(f"  NEEDS UPDATE - {len(result['issues'])} issues found")
        for i, issue in enumerate(result['issues'][:5], 1):
            output_lines.append(f"    {i}. {issue[:100]}...")

        if result["new_hints"]:
            output_lines.append("  New hints generated:")
            for i, hint in enumerate(result["new_hints"]):
                level = ["ZROZUMIENIE", "STRATEGIA", "KIERUNEK", "WSKAZÓWKA"][i]
                hint_display = hint[:80] + "..." if len(hint) > 80 else hint
                output_lines.append(f"    [{i}] {level}: {hint_display}")

            if not dry_run:
                task["hints"] = result["new_hints"]
                with open(task_path, 'w', encoding='utf-8') as f:
                    json.dump(task, f, ensure_ascii=False, indent=2)
                output_lines.append("  Saved updated hints")

            return True, True, output_lines
        else:
            output_lines.append("  ERROR: Review failed but no new hints provided")
            return False, False, output_lines


def main():
    parser = argparse.ArgumentParser(
        description="Review task hints for quality and grade-appropriateness using Gemini API"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving changes")
    parser.add_argument("--year", type=str, help="Process only specific year")
    parser.add_argument("--etap", type=str, help="Process only specific etap")
    parser.add_argument("--task", type=int, help="Process only specific task number")
    parser.add_argument("--limit", type=int, help="Limit number of tasks to process")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed analysis")
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel workers (default: 1)")
    parser.add_argument("--model", type=str, default="gemini-2.5-flash",
                        help="Gemini model to use (default: gemini-2.5-flash)")
    args = parser.parse_args()

    # Configure Gemini
    if not GEMINI_AVAILABLE:
        print("Error: google-genai not installed. Run: pip install google-genai")
        sys.exit(1)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment. Check .env file.")
        sys.exit(1)

    # Create Gemini client
    gemini_client = genai.Client(api_key=api_key)
    tracker = TokenTracker(model_name=args.model)

    pricing = _get_pricing(args.model)
    print(f"Using Gemini API: {args.model}")
    print(f"Pricing: ${pricing['input']:.2f}/1M input, ${pricing['output']:.2f}/1M output")

    if args.parallel > 1:
        print(f"Parallel workers: {args.parallel}")

    print()

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

    print(f"Reviewing hints for {len(task_files)} tasks...")
    if args.dry_run:
        print("(DRY RUN - no files will be modified)")
    print()

    stats = ReviewStats(total=len(task_files))
    print_lock = threading.Lock()
    completed_count = [0]  # Use list for mutable reference in closure

    def process_single_task(task_path: Path) -> None:
        """Process a single task (thread worker function)."""
        rel_path = task_path.relative_to(data_dir)

        # Check if task has hints
        with open(task_path, 'r', encoding='utf-8') as f:
            task = json.load(f)

        if not has_hints(task):
            with print_lock:
                completed_count[0] += 1
                print(f"[{completed_count[0]}/{len(task_files)}] {rel_path} - SKIPPED (no hints)")
            stats.add_skipped()
            return

        # Process the task (collect output for atomic printing)
        success, updated, output_lines = process_task(
            task_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
            gemini_model=args.model,
            tracker=tracker,
            gemini_client=gemini_client
        )

        # Update stats
        if success:
            stats.add_reviewed(updated)
        else:
            stats.add_failed(str(rel_path))

        # Print all output atomically with task context
        with print_lock:
            completed_count[0] += 1
            print(f"[{completed_count[0]}/{len(task_files)}] {rel_path}")
            for line in output_lines:
                print(line)
            # Show running cost estimate every 10 tasks
            if tracker and completed_count[0] % 10 == 0:
                cache_pct = (tracker.total_cached_tokens / tracker.total_input_tokens * 100) if tracker.total_input_tokens > 0 else 0
                print(f"  [Running: ${tracker.get_cost():.4f}, cache hit: {cache_pct:.1f}%]")
            print()

    # Process tasks (parallel or sequential)
    if args.parallel > 1:
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = {executor.submit(process_single_task, task_path): task_path
                       for task_path in task_files}
            for future in as_completed(futures):
                task_path = futures[future]
                try:
                    future.result()
                except Exception as e:
                    rel_path = task_path.relative_to(data_dir)
                    with print_lock:
                        print(f"Error processing {task_path}: {e}")
                    stats.add_failed(str(rel_path))
    else:
        # Sequential processing
        for task_path in task_files:
            process_single_task(task_path)

    # Print summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total tasks:     {stats.total}")
    print(f"Reviewed:        {stats.reviewed}")
    print(f"  - Passed:      {stats.passed}")
    print(f"  - Updated:     {stats.updated}")
    print(f"Failed:          {stats.failed}")
    print(f"Skipped:         {stats.skipped}")

    # Print failed tasks list for retry
    if stats.failed_tasks:
        print()
        print("Failed tasks (retry with specific flags):")
        for task_path in stats.failed_tasks:
            # Parse year/etap/task from path like "2024/etap1/task_1.json"
            parts = task_path.split("/")
            if len(parts) >= 3:
                year, etap, filename = parts[-3], parts[-2], parts[-1]
                task_num = filename.replace("task_", "").replace(".json", "")
                print(f"  --year {year} --etap {etap} --task {task_num}")
            else:
                print(f"  {task_path}")

    # Print cost summary
    if tracker:
        print()
        print("Cost Estimation:")
        print(tracker.get_summary())

    if args.dry_run and stats.updated > 0:
        print()
        print(f"Run without --dry-run to save {stats.updated} updated hints.")


if __name__ == "__main__":
    main()
