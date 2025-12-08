#!/usr/bin/env python3
"""
Populate task metadata (difficulty, categories, hints, skills) using Claude CLI.

Usage:
    python populate_metadata.py              # Process all tasks
    python populate_metadata.py --dry-run    # Preview without saving
    python populate_metadata.py --limit 5    # Process only 5 tasks

If a task requires skills not in data/skills.json, the script will collect
suggestions for new skills and report them at the end for review.
"""

import json
import subprocess
import sys
from pathlib import Path
import argparse
import re
from dataclasses import dataclass, field

# Valid categories based on OMJ problem analysis
VALID_CATEGORIES = [
    "algebra",        # Systems of equations, algebraic identities, inequalities
    "geometria",      # Plane geometry: triangles, quadrilaterals, circles
    "teoria_liczb",   # Divisibility, primes, digits, diophantine equations
    "kombinatoryka",  # Counting, existence, pigeonhole, tournaments
    "logika",         # Weighing problems, grids, game theory, strategy
    "arytmetyka",     # Averages, ratios, basic calculations
]


def load_skills() -> tuple[list[str], str]:
    """Load available skills from data/skills.json."""
    skills_path = Path(__file__).parent / "data" / "skills.json"
    if not skills_path.exists():
        return [], ""

    with open(skills_path, 'r', encoding='utf-8') as f:
        skills_data = json.load(f)

    skills = skills_data.get("skills", {})
    skill_ids = list(skills.keys())

    # Build skills description for prompt
    skills_desc = []
    for skill_id, skill_info in skills.items():
        name = skill_info.get("name", skill_id)
        desc = skill_info.get("description", "")[:100]
        skills_desc.append(f"   - {skill_id}: {name} - {desc}")

    return skill_ids, "\n".join(skills_desc)


VALID_SKILLS, SKILLS_DESCRIPTION = load_skills()


@dataclass
class SkillSuggestion:
    """A suggested new skill that should be added to skills.json."""
    id: str
    name: str
    category: str  # One of: algebra, geometry, number_theory, combinatorics, logic, arithmetic
    description: str
    examples: list[str]
    suggested_by_task: str  # Task path that suggested this skill


@dataclass
class ProcessingReport:
    """Collects results from processing for final report."""
    suggested_skills: list[SkillSuggestion] = field(default_factory=list)
    tasks_needing_reanalysis: list[str] = field(default_factory=list)

    def add_suggestion(self, suggestion: SkillSuggestion):
        # Avoid duplicates by skill id
        if not any(s.id == suggestion.id for s in self.suggested_skills):
            self.suggested_skills.append(suggestion)

    def has_suggestions(self) -> bool:
        return len(self.suggested_skills) > 0 or len(self.tasks_needing_reanalysis) > 0


# Global report instance
processing_report = ProcessingReport()


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

   JĘZYK DOSTOSOWANY DO WIEKU (klasy 4-8, wiek 10-14 lat):
   - UNIKAJ zaawansowanej terminologii: "Małe Twierdzenie Fermata", "rząd elementu",
     "kongruencja", "homomorfizm", "bijekcja", "kombinacja liniowa"
   - ZAMIAST tego używaj prostych opisów: "reszta z dzielenia", "dzieli się bez reszty",
     "parzyste/nieparzyste", "przyporządkowanie jeden-do-jeden"
   - Jeśli musisz użyć zaawansowanego pojęcia, WYTŁUMACZ je prostymi słowami
   - Pisz tak, jakbyś tłumaczył starszemu uczniowi szkoły podstawowej
   - DOBRE: "Znajdź najmniejszą potęgę $a$, która daje resztę 1 przy dzieleniu przez $p$"
   - ZŁE: "Wyznacz rząd elementu $a$ w grupie $\\mathbb{{Z}}_p^*$"

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

4. **skills_required** (wymagane umiejętności): lista ID umiejętności z poniższego zestawu,
   które uczeń MUSI znać aby rozwiązać zadanie. Wybierz 1-3 najbardziej istotne.

5. **skills_gained** (rozwijane umiejętności): lista ID umiejętności, które uczeń
   ćwiczy/rozwija rozwiązując to zadanie. Zazwyczaj 1-2 umiejętności.

   DOSTĘPNE UMIEJĘTNOŚCI (wybieraj TYLKO z tej listy):
{skills_list}

6. **suggested_skill** (opcjonalnie): Jeśli zadanie wymaga umiejętności, której NIE MA
   na powyższej liście, zaproponuj JEDNĄ nową umiejętność. Wypełnij TYLKO jeśli
   istniejące umiejętności naprawdę nie pasują do zadania.

   Format sugerowanej umiejętności:
   - id: krótki identyfikator w snake_case (np. "angle_bisector_properties")
   - name: nazwa po polsku (np. "Własności dwusiecznej kąta")
   - category: jedna z: algebra, geometry, number_theory, combinatorics, logic, arithmetic
   - description: opis dla uczniów klas 4-8 (2-3 zdania)
   - examples: lista 2-3 przykładów zastosowania

   WAŻNE: Jeśli sugerujesz nową umiejętność, nadal wypełnij skills_required i
   skills_gained najlepszymi dopasowaniami z istniejącej listy. Sugerowana
   umiejętność zostanie dodana później i zadanie będzie ponownie przeanalizowane.

Wskazówki dla oceny trudności:
- Etap 1 zwykle ma zadania o trudności 1-3
- Etap 2 zwykle ma zadania o trudności 3-5
- Etap 3 zwykle ma zadania o trudności 4-5
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
4. PROSTYM JĘZYKIEM - unikaj terminów jak "Twierdzenie Fermata", "rząd elementu", "kongruencja"
   Zamiast tego opisuj własnymi słowami co uczeń ma zrobić (np. "sprawdź reszty z dzielenia")

Odpowiedz TYLKO w formacie JSON.
"""


SKILL_CATEGORIES = ["algebra", "geometry", "number_theory", "combinatorics", "logic", "arithmetic"]


def build_json_schema() -> str:
    """Build JSON schema including valid skills."""
    schema = {
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
            },
            "skills_required": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": VALID_SKILLS if VALID_SKILLS else ["placeholder"]
                },
                "minItems": 1,
                "maxItems": 3,
                "description": "Skills required to solve this task (1-3)"
            },
            "skills_gained": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": VALID_SKILLS if VALID_SKILLS else ["placeholder"]
                },
                "minItems": 1,
                "maxItems": 2,
                "description": "Skills practiced/developed by solving this task (1-2)"
            },
            "suggested_skill": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "pattern": "^[a-z_]+$"},
                    "name": {"type": "string"},
                    "category": {"type": "string", "enum": SKILL_CATEGORIES},
                    "description": {"type": "string"},
                    "examples": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 3
                    }
                },
                "required": ["id", "name", "category", "description", "examples"],
                "description": "Optional: suggest a new skill if existing ones don't fit"
            }
        },
        "required": ["difficulty", "categories", "hints", "skills_required", "skills_gained"]
    }
    return json.dumps(schema)


JSON_SCHEMA = build_json_schema()


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


def parse_response(response: str, task_path: str = "") -> dict | None:
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

        # Validate skills_required
        skills_required = data.get("skills_required", [])
        if not isinstance(skills_required, list):
            skills_required = [skills_required] if skills_required else []
        valid_skills_req = [s for s in skills_required if s in VALID_SKILLS]
        invalid_skills_req = [s for s in skills_required if s not in VALID_SKILLS]
        if invalid_skills_req:
            print(f"  ⚠️  Dropped invalid skills_required: {invalid_skills_req}")

        # Validate skills_gained
        skills_gained = data.get("skills_gained", [])
        if not isinstance(skills_gained, list):
            skills_gained = [skills_gained] if skills_gained else []
        valid_skills_gained = [s for s in skills_gained if s in VALID_SKILLS]
        invalid_skills_gained = [s for s in skills_gained if s not in VALID_SKILLS]
        if invalid_skills_gained:
            print(f"  ⚠️  Dropped invalid skills_gained: {invalid_skills_gained}")

        # Handle suggested_skill (optional)
        suggested_skill = data.get("suggested_skill")
        if suggested_skill and isinstance(suggested_skill, dict):
            skill_id = suggested_skill.get("id", "")
            skill_name = suggested_skill.get("name", "")
            skill_category = suggested_skill.get("category", "")
            skill_desc = suggested_skill.get("description", "")
            skill_examples = suggested_skill.get("examples", [])

            # Validate the suggestion
            if (skill_id and skill_name and skill_category in SKILL_CATEGORIES
                    and skill_desc and len(skill_examples) >= 2):
                suggestion = SkillSuggestion(
                    id=skill_id,
                    name=skill_name,
                    category=skill_category,
                    description=skill_desc,
                    examples=skill_examples,
                    suggested_by_task=task_path
                )
                processing_report.add_suggestion(suggestion)
                processing_report.tasks_needing_reanalysis.append(task_path)
                print(f"  ⚠️  Suggested new skill: {skill_id} ({skill_name})")

        return {
            "difficulty": difficulty,
            "categories": valid_cats,
            "hints": hints,
            "skills_required": valid_skills_req,
            "skills_gained": valid_skills_gained
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
        and len(task.get("skills_required", [])) > 0
        and len(task.get("skills_gained", [])) > 0
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
        content=task["content"],
        skills_list=SKILLS_DESCRIPTION
    )

    response = call_claude(prompt, model=model)
    result = parse_response(response, task_path=str(task_path))

    if not result:
        print(f"  Failed to parse response")
        return False

    print(f"  -> difficulty={result['difficulty']}, categories={result['categories']}")
    print(f"     skills_required={result['skills_required']}")
    print(f"     skills_gained={result['skills_gained']}")
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
        task["skills_required"] = result["skills_required"]
        task["skills_gained"] = result["skills_gained"]

        with open(task_path, 'w', encoding='utf-8') as f:
            json.dump(task, f, ensure_ascii=False, indent=2)

    return True


def main():
    global processing_report
    processing_report = ProcessingReport()  # Reset for each run

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

    # Print skills report if there are suggestions
    print_skills_report()


def print_skills_report():
    """Print report of suggested new skills for Claude to review."""
    if not processing_report.has_suggestions():
        return

    print()
    print("=" * 80)
    print("RAPORT: SUGEROWANE NOWE UMIEJĘTNOŚCI")
    print("=" * 80)
    print()
    print("Poniższe umiejętności zostały zasugerowane jako brakujące w data/skills.json.")
    print("Przeanalizuj je i zdecyduj, czy dodać do pliku skills.json.")
    print()

    if processing_report.suggested_skills:
        print("SUGEROWANE UMIEJĘTNOŚCI DO DODANIA:")
        print("-" * 40)
        print()

        # Print in JSON format ready to copy
        skills_json = {}
        for suggestion in processing_report.suggested_skills:
            skills_json[suggestion.id] = {
                "id": suggestion.id,
                "name": suggestion.name,
                "category": suggestion.category,
                "description": suggestion.description,
                "examples": suggestion.examples
            }
            print(f"Skill: {suggestion.id}")
            print(f"  Nazwa: {suggestion.name}")
            print(f"  Kategoria: {suggestion.category}")
            print(f"  Opis: {suggestion.description}")
            print(f"  Przykłady: {suggestion.examples}")
            print(f"  Zasugerowany przez: {suggestion.suggested_by_task}")
            print()

        print()
        print("JSON do skopiowania do data/skills.json (sekcja 'skills'):")
        print("-" * 40)
        print(json.dumps(skills_json, ensure_ascii=False, indent=2))
        print()

    if processing_report.tasks_needing_reanalysis:
        print("ZADANIA DO PONOWNEJ ANALIZY:")
        print("-" * 40)
        print("Po dodaniu nowych umiejętności uruchom ponownie dla tych zadań:")
        print()

        # Group by year/etap for cleaner output
        tasks_by_location = {}
        for task_path in processing_report.tasks_needing_reanalysis:
            # Extract year/etap from path
            parts = Path(task_path).parts
            year_etap = f"{parts[-3]}/{parts[-2]}"
            if year_etap not in tasks_by_location:
                tasks_by_location[year_etap] = []
            tasks_by_location[year_etap].append(parts[-1])

        for location, tasks in sorted(tasks_by_location.items()):
            year, etap = location.split("/")
            task_nums = [t.replace("task_", "").replace(".json", "") for t in tasks]
            print(f"  python populate_metadata.py --year {year} --etap {etap} --force")

        print()
        print("Lub uruchom dla wszystkich naraz:")
        years = set(Path(t).parts[-3] for t in processing_report.tasks_needing_reanalysis)
        etaps = set(Path(t).parts[-2] for t in processing_report.tasks_needing_reanalysis)
        if len(years) == 1 and len(etaps) == 1:
            print(f"  python populate_metadata.py --year {list(years)[0]} --etap {list(etaps)[0]} --force")
        else:
            print("  # Wiele lat/etapów - uruchom osobno dla każdej kombinacji powyżej")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
