# Task Metadata Reference

This document describes the structure and fields of task JSON files stored in `data/tasks/{year}/{etap}/task_{number}.json`.

## File Location

```
data/tasks/
├── 2024/
│   ├── etap1/
│   │   ├── task_1.json
│   │   ├── task_2.json
│   │   └── ...
│   └── etap2/
│       ├── task_1.json
│       └── ...
├── 2023/
│   └── ...
└── ...
```

## JSON Schema

```json
{
  "number": 1,
  "title": "Task title with $LaTeX$ notation",
  "content": "Full task content with $inline$ and $$display$$ math",
  "pdf": {
    "tasks": "tasks/2024/etap1/20omj-1etap.pdf",
    "solutions": "tasks/2024/etap1/20omj-1etap-r.pdf",
    "statistics": "tasks/2024/etap1/20omj-1etap-st.pdf"
  },
  "difficulty": 3,
  "categories": ["geometria", "algebra"],
  "hints": [
    "Hint 1: Understanding the problem",
    "Hint 2: Strategy suggestion",
    "Hint 3: Key direction",
    "Hint 4: Specific guidance"
  ],
  "prerequisites": ["2023_etap1_5", "2022_etap2_3"],
  "skills_required": ["angle_chasing", "isosceles_triangle"],
  "skills_gained": ["angle_chasing"]
}
```

## Field Descriptions

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `number` | `int` | Task number within the etap (1-5 typically) |
| `title` | `string` | Short task title, may contain LaTeX (`$...$`) |
| `content` | `string` | Full task statement with LaTeX notation |
| `pdf` | `object` | Paths to related PDF files (see below) |

### PDF Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tasks` | `string` | Yes | Relative path to the tasks PDF for this etap |
| `solutions` | `string` | No | Relative path to the solutions PDF |
| `statistics` | `string` | No | Relative path to the statistics PDF |

PDF paths are relative to the project root (e.g., `tasks/2024/etap2/20omj-2etap.pdf`).

### Optional Metadata Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `difficulty` | `int` | `null` | Difficulty rating from 1-5 |
| `categories` | `list[str]` | `[]` | Mathematical categories |
| `hints` | `list[str]` | `[]` | Progressive hints (4 levels) |
| `prerequisites` | `list[str]` | `[]` | Task keys that must be mastered first |
| `skills_required` | `list[str]` | `[]` | Skills needed to solve the task (1-3 IDs from `data/skills.json`) |
| `skills_gained` | `list[str]` | `[]` | Skills practiced by solving the task (1-2 IDs from `data/skills.json`) |

## Field Details

### Difficulty (1-5 scale)

| Value | Label | Description |
|-------|-------|-------------|
| 1 | Bardzo latwe | Basic formula application, straightforward |
| 2 | Latwe | Requires simple insight or one key observation |
| 3 | Srednie | Several reasoning steps, moderate complexity |
| 4 | Trudne | Requires significant insight or creative approach |
| 5 | Bardzo trudne | Olympiad-level, requires creative problem solving |

### Categories

Valid category values (defined in `app/models.py:TaskCategory`):

| Value | Polish Name | Description |
|-------|-------------|-------------|
| `algebra` | Algebra | Systems of equations, algebraic identities, inequalities |
| `geometria` | Geometria | Plane geometry: triangles, quadrilaterals, circles |
| `teoria_liczb` | Teoria liczb | Divisibility, primes, digits, Diophantine equations |
| `kombinatoryka` | Kombinatoryka | Counting, existence proofs, pigeonhole, tournaments |
| `logika` | Logika | Weighing problems, grids, game theory, strategy |
| `arytmetyka` | Arytmetyka | Averages, ratios, basic calculations |

A task may have multiple categories (e.g., `["geometria", "algebra"]`).

### Hints (4-level Polya Method)

Hints follow a progressive revelation system based on Polya's problem-solving method:

| Index | Level | Polish Name | Purpose |
|-------|-------|-------------|---------|
| 0 | Understanding | Zrozumienie | Help understand/reframe the problem |
| 1 | Strategy | Strategia | Suggest general approach or method |
| 2 | Direction | Kierunek | Point toward key insight or direction |
| 3 | Guidance | Wskazowka | Specific guidance without giving solution |

**Guidelines for writing hints:**
- Never give the final numerical answer
- Use appropriate LaTeX notation for math
- Keep each hint to 1-2 sentences
- Remember target audience is ages 10-14 (no trigonometry)

### Skills (Required and Gained)

Skills connect tasks to the skill taxonomy defined in `data/skills.json`. They enable skill-based filtering and learning path recommendations.

**skills_required:** Skills the student MUST know to solve the task (1-3 IDs).

**skills_gained:** Skills the student practices/develops by solving the task (1-2 IDs).

**Skill Categories:**
| Category | Polish Name | Description |
|----------|-------------|-------------|
| `algebra` | Algebra | Equations, identities, inequalities |
| `geometry` | Geometria | Shapes, angles, triangles, circles |
| `number_theory` | Teoria liczb | Divisibility, primes, modular arithmetic |
| `combinatorics` | Kombinatoryka | Counting, arrangements, pigeonhole |
| `logic` | Logika | Reasoning, proofs, game theory |
| `arithmetic` | Arytmetyka | Basic calculations, fractions, ratios |

**Example:**
```json
{
  "skills_required": ["angle_chasing", "isosceles_triangle"],
  "skills_gained": ["angle_chasing"]
}
```

Skills are automatically populated by `populate_metadata.py`. If a task requires a skill not in `data/skills.json`, the script suggests adding it and reports which tasks need re-analysis.

### Prerequisites (Progression Graph)

Prerequisites define task dependencies for the progression graph feature. A task is "unlocked" when all its prerequisites are "mastered".

**Task Key Format:** `{year}_{etap}_{number}`

Examples:
- `2024_etap1_3` - Year 2024, Etap I, Task 3
- `2022_etap2_1` - Year 2022, Etap II, Task 1

**Mastery Thresholds:**
- Etap I: Score >= 2 (out of 3)
- Etap II: Score >= 5 (out of 6)

**Transitive Dependencies:**

The system automatically handles transitive dependencies. You only need to specify **direct** prerequisites - the framework will resolve the full dependency chain.

For example, if:
- Task A requires Task B (`A.prerequisites = ["B"]`)
- Task B requires Task C (`B.prerequisites = ["C"]`)

Then Task A is automatically locked until both B and C are mastered. You do NOT need to list C in A's prerequisites.

**Example:**
```json
{
  "number": 5,
  "title": "Advanced geometry problem",
  "prerequisites": ["2023_etap2_1"],
  ...
}
```

This task requires mastering 2023 Etap II Task 1 (score >= 5), plus any tasks that 2023_etap2_1 depends on (transitively).

**Best Practices:**
- Only list direct prerequisites - transitive deps are resolved automatically
- Prerequisites should represent genuine skill dependencies
- Avoid circular dependencies (the system detects and warns about cycles)
- Cross-year/etap prerequisites are allowed
- Tasks with no prerequisites are "root" tasks (always unlocked)

## Example Complete Task

```json
{
  "number": 1,
  "title": "Punkt $E$ na boku $CD$ prostokata $ABCD$",
  "content": "Punkt $E$ lezy na boku $CD$ prostokata $ABCD$, przy czym\n$$\\angle DAE + \\angle EBC = \\angle ABE.$$\nWykaz, ze $AB \\geqslant AD$.",
  "pdf": {
    "tasks": "tasks/2024/etap2/20omj-2etap.pdf",
    "solutions": "tasks/2024/etap2/20omj-2r.pdf",
    "statistics": "tasks/2024/etap2/20omj-2etap-st.pdf"
  },
  "difficulty": 3,
  "categories": ["geometria"],
  "hints": [
    "Oznacz $\\angle DAE = \\alpha$, $\\angle EBC = \\beta$, $\\angle ABE = \\gamma$. Z warunku: $\\alpha + \\beta = \\gamma$. W prostokacie przy $B$: $\\gamma + \\beta = 90°$. Wyznacz stad $\\gamma$ przez $\\beta$.",
    "Oblicz kat $\\angle AEB$ w trojkacie $ABE$. Pamietaj, ze $\\angle BAE = 90° - \\alpha$ (kat prosty przy $A$ minus $\\angle DAE$). Uzyj sumy katow w trojkacie.",
    "Sprawdz, czy $\\angle AEB = \\angle ABE$. Jesli tak, to trojkat $ABE$ jest rownoramienny - ktore boki sa rowne?",
    "Skoro $AB = AE$, porownaj $AE$ z $AD$ w trojkacie prostokatnym $ADE$. Przeciwprostokatna jest zawsze nie mniejsza od przyprostokatnej."
  ],
  "prerequisites": [],
  "skills_required": ["angle_chasing", "isosceles_triangle", "right_triangle"],
  "skills_gained": ["angle_chasing"]
}
```

## Populating Metadata

### Manual Editing

Edit task JSON files directly in `data/tasks/{year}/{etap}/task_{number}.json`.

### Scripts

| Script | Purpose |
|--------|---------|
| `populate_metadata.py` | Generate difficulty, categories, hints using Claude CLI |
| `populate_metadata_gemini.py` | Alternative using Gemini API |
| `fix_latex_content.py` | Update task content with LaTeX from PDFs |

**Usage:**
```bash
# All tasks
python populate_metadata.py --all

# Specific year/etap
python populate_metadata.py 2024 etap1

# Force regenerate existing
python populate_metadata.py --year 2024 --force
```

## Validation

Task files are validated on application startup by the storage layer (`app/storage.py`). Invalid files are logged as warnings but don't prevent the app from running.

The Pydantic model `TaskInfo` in `app/models.py` defines the schema with:
- `difficulty`: Must be 1-5 if provided
- `categories`: List of strings (not validated against enum on load)
- `hints`: List of strings
- `prerequisites`: List of strings in `year_etap_number` format
- `skills_required`: List of skill IDs (validated against `data/skills.json` during population)
- `skills_gained`: List of skill IDs (validated against `data/skills.json` during population)
