/**
 * Private tasks ("Moje zadania") end to end.
 *
 * The fake Gemini answers extraction with two invented problems and hint
 * generation with three hints (see e2e/fake-gemini/server.py); grading uses
 * the default scenario (6 points).
 */

import { test, expect, Page } from '@playwright/test';
import { loginAs, TEST_USERS } from './utils/auth';
import { resetGemini } from './utils/api';
import * as path from 'path';

const FIXTURES_DIR = path.join(__dirname, '..', 'fixtures');
const PROBLEM_PHOTO = path.join(FIXTURES_DIR, 'test-solution.jpg');
const SOLUTION_PHOTO = path.join(FIXTURES_DIR, 'test-solution-2.jpg');

const TYPED_CONTENT = 'Wykaż, że iloczyn dwóch kolejnych liczb naturalnych $n(n+1)$ jest parzysty.';

async function createTypedTask(page: Page, title: string): Promise<string> {
  const response = await page.request.post('/api/private-tasks', {
    data: { tasks: [{ title, content: TYPED_CONTENT }] },
  });
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  return body.tasks[0].id as string;
}

test.describe('Moje zadania', () => {
  test.beforeEach(async ({ context, request }) => {
    await loginAs(context, TEST_USERS.default);
    await resetGemini(request);
  });

  test('photo with two problems: pick both and save two tasks', async ({ page }) => {
    await page.goto('/moje-zadania/nowe');
    await page.locator('input[type="file"]').setInputFiles(PROBLEM_PHOTO);
    await page.getByRole('button', { name: 'Odczytaj zadanie' }).click();

    const first = page.getByRole('checkbox', { name: /Suma dwóch kolejnych liczb/ });
    const second = page.getByRole('checkbox', { name: /Obwód kwadratu/ });
    await expect(first).toBeVisible({ timeout: 30000 });
    // Several problems found: nothing is pre-selected
    await expect(first).not.toBeChecked();
    await first.check();
    await second.check();

    // Each selected problem gets its own editor with a live preview
    await expect(page.getByLabel('Podgląd treści zadania')).toHaveCount(2);

    await page.getByRole('button', { name: 'Zapisz zadania (2)' }).click();
    await expect(page).toHaveURL(/\/moje-zadania$/, { timeout: 30000 });
    await expect(page.getByRole('link', { name: /Suma dwóch kolejnych liczb/ }).first()).toBeVisible();
    await expect(page.getByRole('link', { name: /Obwód kwadratu/ }).first()).toBeVisible();
  });

  test('typed task: reveal a hint, submit and get a score', async ({ page }) => {
    await page.goto('/moje-zadania/nowe');
    await page.getByRole('tab', { name: 'Wpisz treść' }).click();
    await page.getByLabel('Tytuł').fill('Iloczyn kolejnych liczb');
    await page.getByLabel('Treść zadania').fill(TYPED_CONTENT);
    await page.getByRole('button', { name: 'Zapisz zadanie' }).click();

    await expect(page).toHaveURL(/\/moje-zadania\/[A-Za-z0-9_-]{12}$/, { timeout: 30000 });
    await expect(page.getByText('Zadanie prywatne · ocena bez oficjalnego rozwiązania')).toBeVisible();

    await page.getByRole('button', { name: 'Pokaż wskazówkę 1' }).click();
    await expect(page.getByText('Zapisz obie liczby za pomocą jednej zmiennej.')).toBeVisible();

    await page.locator('input[type="file"]').setInputFiles(SOLUTION_PHOTO);
    await page.getByRole('button', { name: 'Prześlij rozwiązanie' }).click();
    await expect(page.getByText(/Wynik: 6 \/ 6 punktów/)).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: /Historia rozwiązań \(1\)/ })).toBeVisible({ timeout: 15000 });
  });

  test('delete removes the task', async ({ page }) => {
    const id = await createTypedTask(page, 'Do usunięcia');
    await page.goto(`/moje-zadania/${id}`);
    await page.getByRole('button', { name: 'Usuń', exact: true }).click();
    await page.getByRole('button', { name: 'Usuń na zawsze' }).click();

    await expect(page).toHaveURL(/\/moje-zadania$/, { timeout: 15000 });
    await expect(page.getByText('Do usunięcia')).toHaveCount(0);
  });

  test("another user's task is not found", async ({ page, context }) => {
    const id = await createTypedTask(page, 'Tylko moje');

    await context.clearCookies();
    await loginAs(context, TEST_USERS.user2);
    const response = await page.goto(`/moje-zadania/${id}`);

    expect(response?.status()).toBe(404);
    await expect(page.getByText('Tylko moje')).toHaveCount(0);
  });
});
