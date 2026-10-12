// Run: node --experimental-strip-types --test src/lib/utils/__tests__/account.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  birthYearOptions,
  emailProblem,
  formatDayPl,
  isAmbiguousBirthYear,
  isUnder16,
  loginProblem,
  normalizeLogin,
  passwordProblem,
  secondsUntil,
  warsawYear,
} from "../account.ts";

test("birth years run newest first from current-6 to current-100", () => {
  const years = birthYearOptions(2026);
  assert.equal(years[0], 2020);
  assert.equal(years[years.length - 1], 1926);
  assert.equal(years.length, 95);
});

test("16 this year is ambiguous and needs the follow-up answer", () => {
  assert.equal(isAmbiguousBirthYear(2010, 2026), true);
  assert.equal(isAmbiguousBirthYear(2011, 2026), false);
  assert.equal(isUnder16(2010, null, 2026), null);
  assert.equal(isUnder16(2010, true, 2026), false);
  assert.equal(isUnder16(2010, false, 2026), true);
});

test("under 16 and 17+ need no follow-up", () => {
  assert.equal(isUnder16(2013, null, 2026), true);
  assert.equal(isUnder16(2009, null, 2026), false);
  assert.equal(isUnder16(null, null, 2026), null);
});

test("the year is counted in Polish time", () => {
  // 23:30 UTC on New Year's Eve is already 1 January in Warsaw
  assert.equal(warsawYear(new Date("2026-12-31T23:30:00Z")), 2027);
});

test("login rules match the backend messages", () => {
  assert.equal(normalizeLogin("  Kasia.B "), "kasia.b");
  assert.equal(loginProblem("kasia.b"), null);
  assert.equal(loginProblem("ab"), "Login musi mieć co najmniej 3 znaki.");
  assert.equal(loginProblem("a".repeat(33)), "Login może mieć najwyżej 32 znaki.");
  assert.equal(loginProblem("_kasia"), "Login musi zaczynać się od litery lub cyfry.");
  assert.match(loginProblem("kaśka") ?? "", /bez polskich znaków/);
});

test("password: at least 8 characters and not the login", () => {
  assert.equal(passwordProblem("zielony rower"), null);
  assert.equal(passwordProblem("krotkie"), "Hasło musi mieć co najmniej 8 znaków.");
  assert.equal(passwordProblem("Kasia123", "kasia123"), "Hasło nie może być takie samo jak login.");
});

test("e-mail shape", () => {
  assert.equal(emailProblem(""), "Wpisz adres e-mail.");
  assert.equal(emailProblem("mama@example.com"), null);
  assert.match(emailProblem("mama@example") ?? "", /literówki/);
});

test("a day in Polish, Polish time", () => {
  assert.equal(formatDayPl("2026-10-26T22:30:00Z"), "26 października 2026");
  // 23:30 UTC on 31 October is already 1 November in Warsaw (CET)
  assert.equal(formatDayPl("2026-10-31T23:30:00Z"), "1 listopada 2026");
});

test("countdown is clamped", () => {
  const now = Date.parse("2026-10-12T10:00:00Z");
  assert.equal(secondsUntil("2026-10-12T10:00:30Z", now, 60), 30);
  assert.equal(secondsUntil("2026-10-12T09:59:00Z", now, 60), 0);
  assert.equal(secondsUntil("2026-10-12T11:00:00Z", now, 60), 60);
  assert.equal(secondsUntil(null, now, 60), 0);
});
