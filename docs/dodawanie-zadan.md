# Dodawanie zadań z nowego roku lub etapu

Ten dokument opisuje proces dodawania zadań z Olimpiady Matematycznej Juniorów (OMJ) lub Olimpiady Matematycznej Gimnazjalistów (OMG) do repozytorium.

## Szybki start (dla Claude)

Jeśli użytkownik wskaże Ci ten dokument i poprosi o dodanie zadań, wykonaj poniższe kroki:

```
# Przykładowe polecenia użytkownika:
# - "Dodaj zadania z etapu 1 roku 2025"
# - "Dodaj etap 3 dla wszystkich lat"
# - "Zaktualizuj zadania z 2024/etap2"
```

## Proces krok po kroku

### 1. Pobierz pliki PDF

```bash
source venv/bin/activate

# Dla konkretnego roku i etapu:
python download_tasks.py --etap <NUMER_ETAPU> --year <ROK>

# Dla wszystkich lat danego etapu:
python download_tasks.py --etap <NUMER_ETAPU>

# Dla wszystkich etapów wszystkich lat:
python download_tasks.py --all-etaps
```

**Parametry:**
- `--etap 1` - etap szkolny (7 zadań)
- `--etap 2` - etap okręgowy (5 zadań)
- `--etap 3` - finał (5 zadań)
- `--year RRRR` - rok rozpoczęcia edycji (np. 2024 dla edycji 2024/25)

**Uwaga:** Pliki PDF są pobierane do katalogu `tasks/<rok>/<etap>/`.

### 2. Utwórz pliki JSON zadań

```bash
source venv/bin/activate

# Dla konkretnego roku i etapu:
python create_tasks.py <ROK> <ETAP>

# Dla wszystkich lat danego etapu:
python create_tasks.py --etap <ETAP> --all

# Podgląd bez tworzenia plików:
python create_tasks.py <ROK> <ETAP> --dry-run
```

**Przykłady:**
```bash
python create_tasks.py 2025 etap1
python create_tasks.py --etap etap3 --all
```

Pliki JSON są tworzone w `data/tasks/<rok>/<etap>/task_<numer>.json`.

### 3. Uzupełnij treść zadań z PDF (LaTeX)

```bash
source venv/bin/activate

# Dla konkretnego roku i etapu:
python fix_latex_content.py <ROK> <ETAP>

# Dla wszystkich etapów:
python fix_latex_content.py --all

# Podgląd zmian:
python fix_latex_content.py <ROK> <ETAP> --dry-run
```

**Co robi ten skrypt:**
- Czyta PDF z zadaniami
- Wyciąga treść każdego zadania
- Formatuje matematykę w notacji LaTeX (`$...$`)
- Aktualizuje pliki JSON

**Wymaga:** Zalogowana sesja Claude CLI (`claude login`).

### 4. Zweryfikuj zasady oceniania (opcjonalnie)

Przed generowaniem metadanych warto sprawdzić, czy oficjalne zasady oceniania OMJ nie uległy zmianie.

**Źródła:**
- Strona OMJ: https://omj.edu.pl/
- Regulamin konkursu (zwykle dostępny jako PDF)
- Pliki PDF ze statystykami (zawierają informacje o punktacji)

**Co sprawdzić:**
- Skala punktowa (obecnie: 0, 2, 5, 6 punktów)
- Kryteria przyznawania punktów cząstkowych
- Zmiany w regulaminie dla nowych edycji

**Pliki do aktualizacji (jeśli zasady się zmieniły):**
- `prompts/gemini_prompt_etap1.txt` - prompt do oceniania rozwiązań etapu 1
- `prompts/gemini_prompt_etap2.txt` - prompt do oceniania rozwiązań etapu 2
- `prompts/gemini_prompt_etap3.txt` - prompt do oceniania rozwiązań etapu 3 (utwórz jeśli brak)
- `populate_metadata.py` - prompt do generowania wskazówek (PROMPT_TEMPLATE)
- `fix_latex_content.py` - prompt do ekstrakcji treści (jeśli format PDF się zmienił)

**Uwaga:** Każdy etap ma osobny prompt, ponieważ kryteria oceniania mogą się różnić.

**Przykład sprawdzenia:**
```bash
# Przeczytaj aktualne prompty
ls prompts/
cat prompts/gemini_prompt_etap1.txt
cat prompts/gemini_prompt_etap2.txt

# Porównaj z zasadami z PDF statystyk
# (otwórz PDF i sprawdź sekcję o punktacji)
```

### 5. Wygeneruj metadane (trudność, kategorie, wskazówki, umiejętności)

```bash
source venv/bin/activate

# Dla konkretnego roku i etapu:
python populate_metadata.py --year <ROK> --etap <ETAP>

# Dla wszystkich zadań bez metadanych:
python populate_metadata.py

# Wymuszenie regeneracji:
python populate_metadata.py --year <ROK> --etap <ETAP> --force
```

**Co generuje ten skrypt:**
- `difficulty` - trudność (1-5)
- `categories` - kategorie matematyczne
- `hints` - 4 progresywne wskazówki
- `skills_required` - wymagane umiejętności z `data/skills.json` (1-3)
- `skills_gained` - rozwijane umiejętności (1-2)

**Uwaga:** Pole `prerequisites` wymaga ręcznej analizy.

**Wymaga:** Zalogowana sesja Claude CLI (`claude login`).

### 6. Zweryfikuj umiejętności i rozważ nowe (automatyczne)

Skrypt `populate_metadata.py` automatycznie:
1. Przypisuje umiejętności z `data/skills.json`
2. **Sugeruje nowe umiejętności** jeśli istniejące nie pasują do zadania

**Na końcu działania skryptu** zostanie wyświetlony raport z:
- Listą sugerowanych nowych umiejętności (gotowy JSON do skopiowania)
- Listą zadań do ponownej analizy po dodaniu umiejętności

**Przykładowy raport:**
```
================================================================================
RAPORT: SUGEROWANE NOWE UMIEJĘTNOŚCI
================================================================================

SUGEROWANE UMIEJĘTNOŚCI DO DODANIA:
----------------------------------------

Skill: angle_bisector_properties
  Nazwa: Własności dwusiecznej kąta
  Kategoria: geometry
  Opis: Wykorzystanie własności dwusiecznej kąta...
  Przykłady: ['Podział kąta na połowy', 'Twierdzenie o dwusiecznej']
  Zasugerowany przez: data/tasks/2024/etap3/task_2.json

JSON do skopiowania do data/skills.json (sekcja 'skills'):
----------------------------------------
{
  "angle_bisector_properties": {
    "id": "angle_bisector_properties",
    ...
  }
}

ZADANIA DO PONOWNEJ ANALIZY:
----------------------------------------
  python populate_metadata.py --year 2024 --etap etap3 --force
================================================================================
```

**Workflow dla Claude:**
1. Uruchom `populate_metadata.py`
2. Jeśli pojawi się raport z sugestiami:
   - Skopiuj JSON do `data/skills.json` (sekcja `skills`)
   - Uruchom ponownie dla wskazanych zadań z `--force`

**Pola w pliku zadania:**
- `skills_required` - umiejętności potrzebne do rozwiązania zadania (1-3)
- `skills_gained` - umiejętności ćwiczone przez rozwiązanie (1-2)

**Struktura umiejętności w `data/skills.json`:**
```json
{
  "categories": {
    "geometry": { "name": "Geometria", "description": "..." }
  },
  "skills": {
    "angle_chasing": {
      "id": "angle_chasing",
      "name": "Obliczanie kątów",
      "category": "geometry",
      "description": "Systematyczne znajdowanie miar kątów...",
      "examples": ["Kąty w trójkątach...", "..."]
    }
  }
}
```

**Ręczne dodawanie umiejętności (jeśli potrzebne):**

Jeśli zadanie wymaga techniki, której nie ma w `data/skills.json`:
1. Dodaj nową umiejętność w sekcji `skills`
2. Przypisz ją do odpowiedniej kategorii (algebra, geometry, number_theory, combinatorics, logic, arithmetic)
3. Napisz opis zrozumiały dla uczniów klas 4-8
4. Podaj 2-3 przykłady zastosowania

### 7. Wygeneruj prerequisites (zależności między zadaniami)

Prerequisites definiują które zadania powinny być rozwiązane przed danym zadaniem.

**Krok 1: Wygeneruj indeks zadań (jednorazowo lub po dodaniu nowych zadań)**

```bash
source venv/bin/activate
python generate_task_index.py
```

Tworzy pliki indeksu w `data/task_index/` - po jednym pliku na rok.

**Krok 2: Wygeneruj prerequisites**

```bash
source venv/bin/activate

# Dla konkretnego roku i etapu:
python populate_prerequisites.py --year <ROK> --etap <ETAP>

# Dla wszystkich zadań bez prerequisites:
python populate_prerequisites.py

# Wymuszenie regeneracji:
python populate_prerequisites.py --year <ROK> --etap <ETAP> --force
```

**Co robi skrypt:**
- Czyta wszystkie pliki indeksu z `data/task_index/`
- Dla każdego zadania znajduje 0-3 bezpośrednich prerequisites
- Kryteria wyboru:
  - Zadania które rozwijają umiejętności wymagane przez analizowane zadanie
  - Trudność mniejsza lub równa
  - Bezpośrednie pomocniki (nie tranzytywne)

**Wymaga:** Zalogowana sesja Claude CLI (`claude login`).

**Uwaga:** Skrypt wymaga dostępu do plików, więc używa `--allowedTools Read,Glob`.

## Przetwarzanie równoległe (zalecane dla wielu lat)

Dla dużej liczby zadań użyj agentów do równoległego przetwarzania - **jeden agent na rok**:

```
# Schemat dla Claude:
1. Uruchom agenty w tle dla każdego roku:
   - Agent dla roku X: fix_latex_content.py + populate_metadata.py
   - Agent dla roku Y: fix_latex_content.py + populate_metadata.py
   - ...

2. Zbierz wyniki ze wszystkich agentów
```

**Przykładowe polecenie dla agenta:**
```bash
source venv/bin/activate && \
python fix_latex_content.py <ROK> <ETAP> && \
python populate_metadata.py --year <ROK> --etap <ETAP>
```

## Struktura plików

```
omj-validator/
├── tasks/                          # Pliki PDF (źródłowe)
│   └── <rok>/
│       └── <etap>/
│           ├── *-zadania.pdf       # Treści zadań
│           ├── *-rozwiazania.pdf   # Rozwiązania
│           └── *-statystyki.pdf    # Statystyki
│
├── data/tasks/                     # Pliki JSON (dane aplikacji)
│   └── <rok>/
│       └── <etap>/
│           ├── task_1.json
│           ├── task_2.json
│           └── ...
```

## Struktura pliku task_*.json

```json
{
  "number": 1,
  "title": "Tytuł zadania z $LaTeX$",
  "content": "Pełna treść zadania z $notacją$ matematyczną...",
  "pdf": {
    "tasks": "tasks/2024/etap3/20omj-3etap.pdf",
    "solutions": "tasks/2024/etap3/20omj-3r.pdf",
    "statistics": "tasks/2024/etap3/20omj-3st.pdf"
  },
  "difficulty": 4,
  "categories": ["geometria", "algebra"],
  "hints": [
    "Wskazówka 1 - ZROZUMIENIE: ...",
    "Wskazówka 2 - STRATEGIA: ...",
    "Wskazówka 3 - KIERUNEK: ...",
    "Wskazówka 4 - WSKAZÓWKA: ..."
  ],
  "prerequisites": ["2022_etap2_1"],
  "skills_required": ["angle_chasing", "isosceles_triangle"],
  "skills_gained": ["angle_chasing"]
}
```

**Pola opcjonalne:**
- `prerequisites` - lista kluczy zadań wymaganych wcześniej (format: `{rok}_etap{N}_{numer}`)
- `skills_required` - lista ID umiejętności z `data/skills.json` potrzebnych do rozwiązania
- `skills_gained` - lista ID umiejętności rozwijanych przez to zadanie

## Dostępne kategorie

Kategorie zadań są zdefiniowane w `populate_metadata.py` (VALID_CATEGORIES) i mapują się na kategorie umiejętności w `data/skills.json`:

| W zadaniach | W skills.json | Opis |
|-------------|---------------|------|
| `algebra` | `algebra` | Układy równań, tożsamości algebraiczne, nierówności |
| `geometria` | `geometry` | Geometria płaska: trójkąty, czworokąty, okręgi |
| `teoria_liczb` | `number_theory` | Podzielność, liczby pierwsze, równania diofantyczne |
| `kombinatoryka` | `combinatorics` | Zliczanie, zasada szufladkowa, turnieje |
| `logika` | `logic` | Ważenie, teoria gier, strategia |
| `arytmetyka` | `arithmetic` | Średnie, stosunki, proste obliczenia |

## Liczba zadań na etap

| Etap | Liczba zadań |
|------|--------------|
| etap1 (szkolny) | 7 |
| etap2 (okręgowy) | 5 |
| etap3 (finał) | 5 |

## Nazewnictwo plików PDF

### OMJ (od 2016, edycje XII+)
- Nowoczesne (od 2022): `20omj-1etap.pdf`, `20omj-2etap.pdf`, `20omj-3etap.pdf`
- Starsze (2016-2021): `1etap17.pdf`, `2etap18.pdf`, `3etap19.pdf`

### OMG (2005-2015, edycje I-XI)
- Format: `1etap10.pdf`, `2etap11.pdf`, `3etap12.pdf`
- Lub: `omg01_1.pdf`, `omg02_2.pdf`, `omg03_3.pdf`

## Rozwiązywanie problemów

### Brak PDF dla danego roku
Niektóre lata mogą nie mieć wszystkich plików (np. 2019/20 - COVID, brak finału).
Skrypt pominie te lata automatycznie.

### Błąd przy ekstrakcji LaTeX
Uruchom ponownie z `--dry-run` aby zobaczyć co zostanie zmienione.
W razie problemów z konkretnym zadaniem, można ręcznie edytować plik JSON.

### Regeneracja metadanych
Użyj flagi `--force` aby wymusić regenerację nawet dla zadań z istniejącymi metadanymi:
```bash
python populate_metadata.py --year 2024 --etap etap1 --force
```

## Weryfikacja

Po dodaniu zadań sprawdź:
```bash
# Liczba plików JSON
ls data/tasks/<rok>/<etap>/*.json | wc -l

# Podgląd przykładowego zadania
cat data/tasks/<rok>/<etap>/task_1.json | head -30

# Uruchom aplikację i sprawdź w przeglądarce
./start.sh
```
