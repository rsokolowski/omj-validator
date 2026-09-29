// Constants for Trener OMJ

export const APP_NAME = "Trener OMJ";
export const APP_TITLE = "Trener OMJ - Olimpiada Matematyczna Juniorów";
export const APP_DESCRIPTION =
  "Przygotuj się do Olimpiady Matematycznej Juniorów z pomocą AI. Ponad 340 zadań z 20 lat archiwum, ocena rozwiązań przez sztuczną inteligencję, wskazówki i ścieżka nauki.";
export const CONTACT_EMAIL = "omj.validator@gmail.com";
export const SITE_URL = "https://omj-validator.pl";

export const CATEGORY_NAMES: Record<string, string> = {
  algebra: "Algebra",
  geometria: "Geometria",
  teoria_liczb: "Teoria liczb",
  kombinatoryka: "Kombinatoryka",
  logika: "Logika",
  arytmetyka: "Arytmetyka",
};

export const CATEGORY_TOOLTIPS: Record<string, string> = {
  algebra: "Układy równań, tożsamości algebraiczne, nierówności",
  geometria: "Geometria płaska: trójkąty, czworokąty, okręgi",
  teoria_liczb: "Podzielność, liczby pierwsze, cyfry, równania diofantyczne",
  kombinatoryka: "Zliczanie, dowody istnienia, zasada szufladkowa",
  logika: "Ważenie, optymalizacja, teoria gier, strategia",
  arytmetyka: "Średnie, stosunki, proste obliczenia",
};

export const DIFFICULTY_LABELS: Record<number, string> = {
  1: "Bardzo łatwe - podstawowe zastosowanie wzorów",
  2: "Łatwe - wymaga prostego wglądu",
  3: "Średnie - kilka kroków rozumowania",
  4: "Trudne - wymaga znacznego wglądu",
  5: "Bardzo trudne - kreatywne podejście",
};

export const HINT_LABELS = ["Zrozumienie", "Strategia", "Kierunek", "Wskazówka"];
export const HINT_ICONS = ["💡", "🎯", "🧭", "🔑"];

export const MAX_UPLOAD_FILES = 10;
export const MAX_FILE_SIZE_MB = 10;
export const ALLOWED_FILE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
  "image/heif",
];

export const ETAP_NAMES: Record<string, string> = {
  etap1: "Etap I",
  etap2: "Etap II",
  etap3: "Etap III",
};

// Max score based on etap - etap1 has 3 points, etap2 and beyond have 6 points
export const ETAP_MAX_SCORES: Record<string, number> = {
  etap1: 3,
  etap2: 6,
  etap3: 6,
};

// `null` etap = private task, graded on the 0-6 scale
export function getMaxScore(etap: string | null | undefined): number {
  return (etap && ETAP_MAX_SCORES[etap]) || 6;
}

// Private tasks (Moje zadania) - limits mirror the backend (app/models.py)
export const PRIVATE_TITLE_MAX = 120;
export const PRIVATE_CONTENT_MIN = 20;
export const PRIVATE_CONTENT_MAX = 10000;
export const PRIVATE_SOURCE_LABEL_MAX = 120;

// Mastery thresholds - matches backend progress.py:get_mastery_threshold()
export const MASTERY_THRESHOLDS: Record<string, number> = {
  etap1: 2,
  etap2: 5,
  etap3: 5,
};

export function getMasteryThreshold(etap: string): number {
  return MASTERY_THRESHOLDS[etap] ?? 5;
}

// Curated list of 23 tasks for Etap 2 preparation
// Selection criteria: Grade 6 level tasks from past etap2 competitions,
// suitable for building foundational skills. Covers geometry, number theory, and algebra.
// Source: https://rsokolowski.github.io/omj-6klasa/raport_omj.html
// Format: {year}_etap2_{task_num}
// Edition mapping: OMJ XX=2024, XIX=2023, XVIII=2022, XVII=2021, XVI=2020,
//                  XV=2019, XIV=2018, XIII=2017, XII=2016
//                  OMG XI=2015, IX=2013, VII=2011, V=2009
export const ETAP2_PREP_TASKS: string[] = [
  // Level 1 - 17 easier tasks (grade 6 level)
  "2024_etap2_1",  // OMJ XX/1 - Prostokąt ABCD, wykaż AB≥AD
  "2022_etap2_1",  // OMJ XVIII/1 - Trójkąt ABC, wykaż AE=BE
  "2022_etap2_3",  // OMJ XVIII/3 - Wpisanie cyfry daje 6n
  "2021_etap2_2",  // OMJ XVII/2 - Dzielniki a+b+ab=n
  "2020_etap2_2",  // OMJ XVI/2 - Kwadrat ABCD, przekątna, kąt 90°
  "2020_etap2_3",  // OMJ XVI/3 - 5a+3b podzielne przez a+b
  "2018_etap2_2",  // OMJ XIV/2 - Trapez, dwusieczna, pola równe
  "2018_etap2_5",  // OMJ XIV/5 - Cyfry 1,2,9 w 3n
  "2017_etap2_3",  // OMJ XIII/3 - Układ x-yz=1, xz+y=2
  "2017_etap2_4",  // OMJ XIII/4 - Trapez ABCD, kąty równe
  "2016_etap2_2",  // OMJ XII/2 - Trapez, przekątne prostopadłe
  "2015_etap2_1",  // OMG XI/1 - Trójki a+b, b+c, c+a pierwsze
  "2015_etap2_2",  // OMG XI/2 - Równoległobok, CX=CY
  "2013_etap2_2",  // OMG IX/2 - Trapez, środki podstaw, pola
  "2011_etap2_1",  // OMG VII/1 - ab|175 i a+b=175
  "2009_etap2_2",  // OMG V/2 - Trapez, kąty 60°, BD=AE
  "2009_etap2_3",  // OMG V/3 - n²+n+1 i n²+n+3 pierwsze
  // Level 2 - 6 more challenging tasks
  "2024_etap2_2",  // OMJ XX/2 - Tablica 5×5, kolory
  "2023_etap2_1",  // OMJ XIX/1 - Iloczyny kolejne, jeden kwadrat
  "2023_etap2_3",  // OMJ XIX/3 - Trapez, AP=CD
  "2021_etap2_1",  // OMJ XVII/1 - Odcinki prostopadłe
  "2019_etap2_1",  // OMJ XV/1 - a+b, b+c, c+a kolejne
  "2019_etap2_2",  // OMJ XV/2 - Równoległobok, symetralna
];

// Curated list of tasks for Etap 1 preparation
// Selection criteria: the easiest etap1 tasks (difficulty 2 - the corpus has no
// difficulty-1 etap1 tasks), covering the basic techniques: parity, divisibility,
// digits, casework, pigeonhole, invariants, areas, simple identities and counting.
// Two difficulty-3 tasks are included on purpose because no easier task covers
// angle chasing or the triangle inequality.
// Must stay disjoint from MOCK_ETAP1_SETS so a mock set is never spoiled.
// Format: {year}_etap1_{task_num}
export const ETAP1_PREP_TASKS: string[] = [
  "2005_etap1_5",  // kombinatoryka - 121 jabłek w 15 wiadrach, difficulty 2
  "2005_etap1_7",  // geometria - B środkiem AC, policz CD, difficulty 2
  "2009_etap1_1",  // teoria_liczb - pierwsze a, b, c z a²=b²+c, difficulty 2
  "2010_etap1_1",  // algebra - symetryczny układ równań kwadratowych, difficulty 2
  "2011_etap1_1",  // algebra - czy pierwiastki mogą równać się x+y, difficulty 2
  "2011_etap1_3",  // geometria - równe pola i obwody, równe przekątne, difficulty 2
  "2012_etap1_1",  // teoria_liczb - cykl cyfr jedności potęg n, difficulty 2
  "2012_etap1_4",  // kombinatoryka - bal, szuflady, dwie równe liczby, difficulty 2
  "2013_etap1_1",  // arytmetyka - wzrost o 1,5% przy limicie 404, difficulty 2
  "2013_etap1_2",  // algebra - cztery różnice jako kolejne liczby, difficulty 2
  "2014_etap1_1",  // algebra - 50 zł na 13 monet 1/2/5, difficulty 2
  "2015_etap1_1",  // teoria_liczb - nieskończenie wiele trójek, z(y-x)=6, difficulty 2
  "2017_etap1_1",  // algebra - z dwóch zależności wynika a²+b²=c², difficulty 2
  "2018_etap1_1",  // teoria_liczb - cyfra jedności ilorazu 999^1000 przez 3, difficulty 2
  "2020_etap1_1",  // teoria_liczb - kolejne pary cyfr jako kwadraty, difficulty 2
  "2020_etap1_2",  // geometria - dwie wysokości trójkąta równoramiennego, pole, difficulty 2
  "2020_etap1_3",  // algebra - |a-b|=2|b-c|=3|c-a| wymusza równość, difficulty 2
  "2022_etap1_1",  // algebra - prostokąt 1:2 o polu równym obwodowi, difficulty 2
  "2023_etap1_4",  // teoria_liczb - pierwsza jako różnica sześcianów pierwszych, difficulty 2
  "2023_etap1_5",  // geometria - koło i pierścień o równych polach, difficulty 2
  "2024_etap1_1",  // geometria - odległości od boków kwadratu, kolejne liczby, difficulty 2
  "2025_etap1_2",  // teoria_liczb - n = 21 razy suma cyfr, 9|n, difficulty 2
  "2025_etap1_3",  // kombinatoryka - pięć osób, liczby znajomych, difficulty 2
  "2017_etap1_4",  // geometria - trapez, symetralne boków, kąty, difficulty 3 (wyjątek)
  "2025_etap1_7",  // geometria - nierówność trójkąta dla miar kątów, difficulty 3 (wyjątek)
];

// Mock practice sets - realistic exam simulations
// Tasks are NOT included in the matching prep list to avoid overlap
export interface MockSet {
  id: string;
  name: string;
  tasks: string[];
}

// Each set contains 5 tasks with typical etap2 difficulty distribution
export const MOCK_ETAP2_SETS: MockSet[] = [
  {
    id: "mock-1",
    name: "Próbny Etap 2 - I",
    tasks: [
      "2020_etap2_1",  // algebra - 2a+a²=2b+b², difficulty 3
      "2022_etap2_2",  // teoria_liczb - Liczby 2 i 5, niezmienniki, difficulty 3
      "2020_etap2_4",  // geometria - Równoległobok, dwusieczna ⊥ KL, difficulty 4
      "2016_etap2_4",  // algebra - √2±1 suma iloczynów = 199, difficulty 4
      "2020_etap2_5",  // kombinatoryka - Zdalne przyjęcie, teoria grafów, difficulty 4
    ],
  },
  {
    id: "mock-2",
    name: "Próbny Etap 2 - II",
    tasks: [
      "2017_etap2_1",  // algebra/geometria - Rozszerzenie tw. Pitagorasa, difficulty 3
      "2016_etap2_1",  // kombinatoryka - Tablica 4×4, potęgi 2, difficulty 3
      "2017_etap2_2",  // geometria - Trójkąt, środek okręgu opisanego, difficulty 3
      "2019_etap2_3",  // kombinatoryka/logika - Turniej, difficulty 4
      "2018_etap2_1",  // algebra - Nierówność x²+x ≤ y, difficulty 4
    ],
  },
];

// Each set contains 7 tasks, matching the "część zadaniowa" of the real etap 1
// (100 minutes, 3 points per task). Difficulty ramp and category mix copy the
// shape of the 2022-2025 papers; every set has difficulties 2,2,3,3,3,3,4.
export const MOCK_ETAP1_SETS: MockSet[] = [
  {
    id: "mock-etap1-1",
    name: "Zestaw 1",
    tasks: [
      "2022_etap1_2",  // arytmetyka - gdzie wstawić "=" w 1-2+3-...-100, difficulty 2
      "2019_etap1_1",  // teoria_liczb - dopisanie cyfry daje 13n, difficulty 2
      "2019_etap1_2",  // geometria - łańcuch trójkątów równoramiennych, kąty, difficulty 3
      "2016_etap1_5",  // teoria_liczb - a, b lub a+b jako różnica kwadratów, difficulty 3
      "2019_etap1_5",  // kombinatoryka - turniej 8 osób, najmniej remisów, difficulty 3
      "2018_etap1_5",  // geometria - równoległobok, AP=BD, kąt prosty, difficulty 3
      "2022_etap1_5",  // algebra - nierówność a+b+c ≥ 3abc/4, difficulty 4
    ],
  },
  {
    id: "mock-etap1-2",
    name: "Zestaw 2",
    tasks: [
      "2021_etap1_1",  // arytmetyka - średnia klasy a wynik ucznia, difficulty 2
      "2020_etap1_5",  // teoria_liczb - suma 2^1002, iloczyn 5^1002, difficulty 2
      "2020_etap1_4",  // geometria - czworokąt z kątami 120°, difficulty 3
      "2019_etap1_3",  // algebra - symetryczny układ xy(x+y)=yz(y+z)=zx(z+x), difficulty 3
      "2024_etap1_4",  // kombinatoryka - 100 kamieni, usuwanie po 25, difficulty 3
      "2021_etap1_2",  // geometria - prostokąt o stosunku √2, kąt BXD, difficulty 3
      "2015_etap1_3",  // teoria_liczb - kiedy (n⁴+4)/17 jest pierwsza, difficulty 4
    ],
  },
  {
    id: "mock-etap1-3",
    name: "Zestaw 3",
    tasks: [
      "2025_etap1_1",  // kombinatoryka - monety 2 i 5 zł, wybór 50 zł, difficulty 2
      "2024_etap1_3",  // algebra - trzy różnice bezwzględne między 1 a 2, difficulty 2
      "2023_etap1_2",  // geometria - pięć równych odcinków, miara kąta AMB, difficulty 3
      "2018_etap1_4",  // teoria_liczb - cykl reszt daje c=4, difficulty 3
      "2022_etap1_6",  // kombinatoryka - rozcięcie kwadratu na plusy i minusy, difficulty 3
      "2024_etap1_7",  // geometria - prostopadłościan, kąt BPB' prosty, difficulty 3
      "2021_etap1_7",  // teoria_liczb - cyfry, podzielność przez 7, 6|n, difficulty 4
    ],
  },
];

// Timer durations
// Etap 1 "część zadaniowa": 100 minut. Etap 2: 3 godziny.
export const ETAP1_TIMER_DURATION_MS = 100 * 60 * 1000;
export const ETAP2_TIMER_DURATION_MS = 3 * 60 * 60 * 1000;

export type MockEtap = "etap1" | "etap2";

export interface MockEtapConfig {
  label: string;
  path: string;
  timerMs: number;
  tasksPerSet: number;
  pointsPerTask: number;
  description: string;
}

export const MOCK_ETAP_CONFIG: Record<MockEtap, MockEtapConfig> = {
  etap1: {
    label: "Próbny Etap 1",
    path: "/practice/etap1",
    timerMs: ETAP1_TIMER_DURATION_MS,
    tasksPerSet: 7,
    pointsPerTask: 3,
    description: "7 zadań otwartych, 100 minut, 3 punkty za zadanie (21 punktów).",
  },
  etap2: {
    label: "Próbny Etap 2",
    path: "/practice/etap2",
    timerMs: ETAP2_TIMER_DURATION_MS,
    tasksPerSet: 5,
    pointsPerTask: 6,
    description: "5 zadań, 3 godziny, 6 punktów za zadanie (30 punktów).",
  },
};

// Czas trwania w formie tekstowej, np. "100 minut" / "3 godziny"
export const MOCK_ETAP_DURATION_LABELS: Record<MockEtap, string> = {
  etap1: "100 minut",
  etap2: "3 godziny",
};

export const MOCK_SETS: Record<MockEtap, MockSet[]> = {
  etap1: MOCK_ETAP1_SETS,
  etap2: MOCK_ETAP2_SETS,
};

export const MOCK_PREP_TASKS: Record<MockEtap, string[]> = {
  etap1: ETAP1_PREP_TASKS,
  etap2: ETAP2_PREP_TASKS,
};

// Patterns (Wzorce) - limits mirror the backend (app/models.py)
export const PATTERN_TRIGGER_MIN = 5;
export const PATTERN_TRIGGER_MAX = 300;
export const PATTERN_ACTION_MIN = 5;
export const PATTERN_ACTION_MAX = 600;
export const PATTERN_EXAMPLE_MAX = 1000;
export const PATTERN_RAW_MAX = 1000;
export const PATTERN_ANSWER_MAX = 1000;
export const RECALL_TEXT_MIN = 10;
export const RECALL_TEXT_MAX = 1000;

export const PATTERN_LEVEL_NAMES: Record<number, string> = {
  1: "Poziom 1",
  2: "Poziom 2",
  3: "Poziom 3",
  4: "Utrwalony",
};

export const PATTERN_VERDICTS: Record<string, { label: string; color: "success" | "warning" | "error" | "info" }> = {
  ok: { label: "Dobry wzorzec", color: "success" },
  za_ogolny: { label: "Za ogólny", color: "warning" },
  bledny: { label: "Coś się nie zgadza", color: "error" },
  to_nie_wzorzec: { label: "To jeszcze nie wzorzec", color: "info" },
};

export const REVIEW_OUTCOMES: Record<string, string> = {
  fail: "Nie pamiętałem",
  hard: "Z trudem",
  ok: "Pamiętałem",
};
