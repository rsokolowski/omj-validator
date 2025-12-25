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
// Selection criteria: Grade 6 level tasks suitable for building foundational skills
// before attempting Etap 2. Covers geometry, number theory, and algebra.
// Source: https://rsokolowski.github.io/omj-6klasa/raport_omj.html
// Format: {year}_etap{num}_{task_num}
// Edition mapping: OMJ XX=2024, XIX=2023, XVIII=2022, XVII=2021, XVI=2020,
//                  XV=2019, XIV=2018, XIII=2017, XII=2016
//                  OMG XI=2015, IX=2013, VII=2011, V=2009
export const ETAP2_PREP_TASKS: string[] = [
  // Level 1 - 17 easy tasks (grade 6 level)
  "2024_etap1_1",  // OMJ XX/1 - Geometry
  "2022_etap1_1",  // OMJ XVIII/1 - Geometry
  "2022_etap1_3",  // OMJ XVIII/3 - Number Theory
  "2021_etap1_2",  // OMJ XVII/2 - Number Theory
  "2020_etap1_2",  // OMJ XVI/2 - Geometry
  "2020_etap1_3",  // OMJ XVI/3 - Number Theory
  "2018_etap1_2",  // OMJ XIV/2 - Geometry
  "2018_etap1_5",  // OMJ XIV/5 - Number Theory
  "2017_etap1_3",  // OMJ XIII/3 - Algebra
  "2017_etap1_4",  // OMJ XIII/4 - Geometry
  "2016_etap1_2",  // OMJ XII/2 - Geometry
  "2015_etap1_1",  // OMG XI/1 - Number Theory
  "2015_etap1_2",  // OMG XI/2 - Geometry
  "2013_etap1_2",  // OMG IX/2 - Geometry
  "2011_etap1_1",  // OMG VII/1 - Number Theory
  "2009_etap1_2",  // OMG V/2 - Geometry
  "2009_etap1_3",  // OMG V/3 - Number Theory
  // Level 2 - 6 more challenging tasks
  "2024_etap1_2",  // OMJ XX/2 - Combinatorics
  "2023_etap1_1",  // OMJ XIX/1 - Number Theory
  "2023_etap1_3",  // OMJ XIX/3 - Geometry
  "2021_etap1_1",  // OMJ XVII/1 - Geometry
  "2019_etap1_1",  // OMJ XV/1 - Algebra
  "2019_etap1_2",  // OMJ XV/2 - Geometry
];
