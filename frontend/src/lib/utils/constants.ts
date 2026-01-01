// Constants for Trener OMJ

export const APP_NAME = "Trener OMJ";
export const APP_TITLE = "Trener OMJ - Olimpiada Matematyczna Juniorów";
export const APP_DESCRIPTION = "Przygotuj się do Olimpiady Matematycznej Juniorów z pomocą AI";
export const CONTACT_EMAIL = "omj.validator@gmail.com";

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

export function getMaxScore(etap: string): number {
  return ETAP_MAX_SCORES[etap] ?? 6;
}

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

// Mock Etap 2 practice sets - realistic exam simulations
// Each set contains 5 tasks with typical etap2 difficulty distribution
// Tasks are NOT included in ETAP2_PREP_TASKS to avoid overlap
export interface MockEtap2Set {
  id: string;
  name: string;
  tasks: string[];
}

export const MOCK_ETAP2_SETS: MockEtap2Set[] = [
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

// Timer duration for etap2 (3 hours in milliseconds)
export const ETAP2_TIMER_DURATION_MS = 3 * 60 * 60 * 1000;
