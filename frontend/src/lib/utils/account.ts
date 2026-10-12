/**
 * Client-side mirror of the account rules (app/accounts/age.py, passwords.py,
 * service.py). The server is authoritative - these only give instant feedback.
 *
 * No "@/" imports here: the node:test suite imports this file directly.
 */

export const AGE_OF_CONSENT = 16;
export const MIN_AGE = 6;
export const MAX_AGE = 100;

export const LOGIN_MIN = 3;
export const LOGIN_MAX = 32;
export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 200;
const LOGIN_RE = /^[a-z0-9][a-z0-9._-]{2,31}$/;
// Loose shape check; the backend has the final word
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const EMAIL_MAX = 254;

const WARSAW = "Europe/Warsaw";

/** The calendar year in Poland (the backend counts age in Europe/Warsaw). */
export function warsawYear(now: Date = new Date()): number {
  const year = new Intl.DateTimeFormat("en-US", { timeZone: WARSAW, year: "numeric" }).format(now);
  return Number(year);
}

/** Years offered in the select, newest first: current-6 ... current-100. */
export function birthYearOptions(year: number): number[] {
  const years: number[] = [];
  for (let y = year - MIN_AGE; y >= year - MAX_AGE; y--) years.push(y);
  return years;
}

/** The person turns 16 this calendar year - ask "Czy masz już ukończone 16 lat?". */
export function isAmbiguousBirthYear(birthYear: number, year: number): boolean {
  return year - birthYear === AGE_OF_CONSENT;
}

/**
 * Whether the person needs a parent's consent (under 16).
 * null = not decided yet (no year, or the ambiguous year without an answer).
 */
export function isUnder16(
  birthYear: number | null,
  turned16: boolean | null,
  year: number
): boolean | null {
  if (birthYear === null) return null;
  const age = year - birthYear;
  if (age > AGE_OF_CONSENT) return false;
  if (age < AGE_OF_CONSENT) return true;
  return turned16 === null ? null : !turned16;
}

export function normalizeLogin(login: string): string {
  return login.trim().toLowerCase();
}

/** Same messages as passwords.login_problem; expects a normalised login. */
export function loginProblem(login: string): string | null {
  if (login.length < LOGIN_MIN) return "Login musi mieć co najmniej 3 znaki.";
  if (login.length > LOGIN_MAX) return "Login może mieć najwyżej 32 znaki.";
  if (!LOGIN_RE.test(login)) {
    if (!/^[a-z0-9]/.test(login)) return "Login musi zaczynać się od litery lub cyfry.";
    return "Login może zawierać tylko litery bez polskich znaków, cyfry oraz . _ -";
  }
  return null;
}

/** The rules a browser can check (the common-password list stays on the server). */
export function passwordProblem(password: string, login?: string | null): string | null {
  if (password.length < PASSWORD_MIN) return "Hasło musi mieć co najmniej 8 znaków.";
  if (password.length > PASSWORD_MAX) return "Hasło może mieć najwyżej 200 znaków.";
  if (login && password.trim().toLowerCase() === normalizeLogin(login)) {
    return "Hasło nie może być takie samo jak login.";
  }
  return null;
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

/** Same messages as service.email_problem; expects a normalised address. */
export function emailProblem(email: string): string | null {
  if (!email) return "Wpisz adres e-mail.";
  if (email.length > EMAIL_MAX || !EMAIL_RE.test(email)) {
    return "To nie wygląda na adres e-mail. Sprawdź, czy nie ma literówki.";
  }
  return null;
}

/** "26 października 2026" - a day in Polish, in Polish time. */
export function formatDayPl(iso: string): string {
  const date = new Date(iso);
  if (isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("pl-PL", {
    timeZone: WARSAW,
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

/**
 * Whole seconds from `now` until `iso`, clamped to [0, max]. The clamp keeps a
 * device with a wrong clock from locking a button for longer than the server
 * ever would.
 */
export function secondsUntil(iso: string | null, now: number, max: number): number {
  if (!iso) return 0;
  const at = new Date(iso).getTime();
  if (isNaN(at)) return 0;
  return Math.min(max, Math.max(0, Math.ceil((at - now) / 1000)));
}
