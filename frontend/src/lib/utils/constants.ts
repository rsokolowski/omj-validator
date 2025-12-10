// Constants for Trener OMJ

export const APP_NAME = "Trener OMJ";
export const APP_TITLE = "Trener OMJ - Olimpiada Matematyczna Juniorów";
export const APP_DESCRIPTION = "Przygotuj się do Olimpiady Matematycznej Juniorów z pomocą AI";

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
