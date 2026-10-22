/**
 * Patterns ("Wzorce") end to end.
 *
 * The fake Gemini answers the pattern calls with invented wording (see
 * PATTERN_* in e2e/fake-gemini/server.py): a refine round with two versions,
 * two suggestions from a graded solution, a link to the first candidate OMJ
 * task in the prompt, and five exercises with answers and solutions. Grading
 * uses the default scenario (6 points).
 */

import { test, expect, Page } from '@playwright/test';
import { loginAs, TEST_USERS } from './utils/auth';
import { resetGemini } from './utils/api';
import * as path from 'path';

const SOLUTION_PHOTO = path.join(__dirname, '..', 'fixtures', 'test-solution-2.jpg');
const TYPED_CONTENT = 'Wykaż, że suma dwóch kolejnych liczb całkowitych jest nieparzysta.';

async function createTypedTask(page: Page, title: string): Promise<string> {
  const response = await page.request.post('/api/private-tasks', {
    data: { tasks: [{ title, content: TYPED_CONTENT }] },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).tasks[0].id as string;
}

/** Wait for the background batch the save started: 5 exercises on the print sheet. */
async function waitForExercises(page: Page, patternId: string, count = 5) {
  await expect.poll(async () => {
    const r = await page.request.get(`/api/patterns/${patternId}/exercises/print`);
    return (await r.json()).exercises.length as number;
  }, { timeout: 30000 }).toBe(count);
}

async function makeDue(page: Page, patternId: string) {
  expect((await page.request.post(`/api/test/patterns/${patternId}/make-due`)).ok()).toBeTruthy();
}

/** A self-rated "ok" through the API, on the exercise today's card offers. */
async function reviewOk(page: Page, patternId: string) {
  await makeDue(page, patternId);
  const card = await (await page.request.get(`/api/patterns/${patternId}/card`)).json();
  const r = await page.request.post(`/api/patterns/${patternId}/review`, {
    data: { outcome: 'ok', exercise_id: card.exercise.id, trigger_shown: false },
  });
  expect(r.ok()).toBeTruthy();
}

async function submitSolution(page: Page) {
  await page.getByLabel('Wybierz zdjęcia rozwiązania').setInputFiles(SOLUTION_PHOTO);
  await page.getByRole('button', { name: 'Prześlij rozwiązanie' }).click();
  await expect(page.getByText(/Wynik: 6 \/ 6 punktów/)).toBeVisible({ timeout: 30000 });
}

test.describe('Wzorce', () => {
  test.beforeEach(async ({ context, request, page }) => {
    await loginAs(context, TEST_USERS.default);
    await resetGemini(request);
    // Each test starts with no patterns, so today's queue is predictable
    expect((await page.request.post('/api/test/reset-user-patterns')).ok()).toBeTruthy();
  });

  test('from a graded task to a practised pattern', async ({ page }) => {
    // 1. A graded private task
    const taskId = await createTypedTask(page, 'Kolejne liczby $n$ i $n+1$');
    await page.goto(`/moje-zadania/${taskId}`);
    await submitSolution(page);
    await page.reload();

    // 2. "Podpowiedz wzorzec" - pick the first suggestion
    await page.getByRole('button', { name: 'Podpowiedz wzorzec' }).click();
    const suggestion = page.getByRole('article', { name: 'Propozycja 1' });
    await expect(suggestion).toContainText('Pytają o parzystość wyrażenia', { timeout: 30000 });
    await suggestion.getByRole('button', { name: 'Użyj' }).click();

    // 3. The editor starts from the suggestion; one refine round, pick version 2
    await expect(page).toHaveURL(/\/wzorce\/nowy\?private=/);
    await expect(page.getByLabel('Kiedy w treści widzę…')).toHaveValue(/Pytają o parzystość wyrażenia/);
    await expect(page.locator('#pattern-category')).toHaveText('Teoria liczb');
    await page.getByRole('button', { name: 'Dopracuj z AI' }).click();
    const version2 = page.getByRole('article', { name: 'Wersja 2' });
    await expect(version2).toBeVisible({ timeout: 30000 });
    await expect(page.getByText('Czy ten pomysł działa także dla trzech kolejnych liczb?')).toBeVisible();
    await version2.getByRole('button', { name: 'Wybierz' }).click();
    await expect(page.getByLabel('Kiedy w treści widzę…')).toHaveValue('W zadaniu pojawiają się kolejne liczby całkowite');

    // 4. Save - the pattern page asks the AI for OMJ tasks right away
    await page.getByRole('button', { name: 'Zapisz wzorzec' }).click();
    await expect(page).toHaveURL(/\/wzorce\/[A-Za-z0-9_-]{12}(\?nowy=1)?$/, { timeout: 30000 });
    const patternId = new URL(page.url()).pathname.split('/').pop()!;
    const proposals = page.getByTestId('link-proposals');
    await expect(proposals).toContainText('Ćwiczy ten sam pomysł z parzystością.', { timeout: 30000 });
    await proposals.getByRole('button', { name: 'Przyjmij propozycję' }).first().click();
    await expect(page.getByTestId('link-proposals')).toHaveCount(0);
    await expect(page.getByTestId('pattern-level')).toHaveText('Poziom 1');
    // Task titles with math are rendered, not shown as raw $...$
    const tasks = page.getByRole('region', { name: 'Zadania do tego wzorca' });
    await expect(tasks.locator('.katex').first()).toBeVisible();
    await expect(tasks).not.toContainText('$n$');

    // A reload does not ask the AI again (each ask uses the daily limit)
    await expect(page).toHaveURL(new RegExp(`/wzorce/${patternId}$`));
    await page.reload();
    await expect(page.getByRole('region', { name: 'Zadania do tego wzorca' })).toBeVisible();
    await page.waitForTimeout(1500);
    await expect(page.getByTestId('link-proposals')).toHaveCount(0);

    // 5. Due (e2e hook) -> the header badge and an exercise card -> solved with the wzorzec
    await waitForExercises(page, patternId);
    await makeDue(page, patternId);
    await page.goto('/wzorce');
    await expect(page.getByText('Do powtórki dziś: 1')).toBeVisible();
    await page.getByRole('link', { name: 'Zacznij' }).click();

    // Level 1: the trigger is shown above the exercise
    await expect(page.getByTestId('review-trigger')).toContainText('W zadaniu pojawiają się kolejne liczby całkowite',
      { timeout: 15000 });
    const exercise = page.getByTestId('review-exercise');
    await expect(exercise).toBeVisible();
    await page.getByRole('button', { name: 'Zadanie zrobione' }).click();
    await expect(page.getByTestId('review-answer')).toBeVisible();
    await expect(page.getByTestId('review-solution')).toBeVisible();
    await expect(page.getByTestId('review-pattern')).toBeVisible();
    await expect(page.getByText('Czy ten wzorzec był w rozwiązaniu?')).toBeVisible();
    await page.getByRole('button', { name: 'Tak, z tym wzorcem' }).click();
    await expect(page.getByText(/Poziom 1 · następna powtórka/)).toBeVisible();
    await page.getByRole('button', { name: 'Zakończ' }).click();
    await expect(page.getByText('Na dziś wszystko')).toBeVisible();

    await page.goto(`/wzorce/${patternId}`);
    await expect(page.getByTestId('review-history')).toContainText(/Ćwiczenie „.+” · Z tym wzorcem · Poziom 1/);
  });

  test('familiar wzorzec: hidden trigger, skip, peek cap, not solved', async ({ page }) => {
    const created = await page.request.post('/api/patterns', {
      data: { trigger: 'Iloczyn kolejnych liczb całkowitych', action: 'Jedna z nich jest parzysta', category: 'teoria_liczb' },
    });
    expect(created.status()).toBe(201);
    const id = (await created.json()).pattern.id as string;
    await waitForExercises(page, id);

    // Two "ok" reviews: level 1 -> level 2 (familiar)
    await reviewOk(page, id);
    await reviewOk(page, id);
    await makeDue(page, id);
    await page.goto('/wzorce/powtorka');

    // The trigger starts hidden
    const peek = page.getByRole('button', { name: 'Pokaż, kiedy stosować ten wzorzec' });
    await expect(peek).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('review-trigger')).toHaveCount(0);

    // "Zadanie jest błędne" swaps the exercise
    const exercise = page.getByTestId('review-exercise');
    const before = await exercise.innerText();
    await page.getByRole('button', { name: 'Zadanie jest błędne - pomiń' }).click();
    await expect(exercise).not.toHaveText(before);

    // Peeking, then "Tak, z tym wzorcem" is saved as "Inny sposób"
    await peek.click();
    await expect(page.getByTestId('review-trigger')).toContainText('Iloczyn kolejnych liczb całkowitych');
    await page.getByRole('button', { name: 'Zadanie zrobione' }).click();
    await page.getByRole('button', { name: 'Tak, z tym wzorcem' }).click();
    await expect(page.getByText(/Poziom 2 · następna powtórka/)).toBeVisible();

    await page.goto(`/wzorce/${id}`);
    await expect(page.getByTestId('review-history')).toContainText(/Ćwiczenie „.+” · Inny sposób · Poziom 2/);

    // "Zadanie nie zrobione": recorded at once, the wzorzec is shown, no second question
    await makeDue(page, id);
    await page.goto('/wzorce/powtorka');
    await page.getByRole('button', { name: 'Zadanie nie zrobione' }).click();
    await expect(page.getByText(/Poziom 1 · następna powtórka/)).toBeVisible();
    await expect(page.getByTestId('review-pattern')).toContainText('Jedna z nich jest parzysta');
    await expect(page.getByTestId('review-solution')).toBeVisible();
    await expect(page.getByText('Czy ten wzorzec był w rozwiązaniu?')).toHaveCount(0);

    // The printable sheet, from the wzorzec page, ends with answers and solutions
    // (the pool may have been topped up meanwhile, so no exact count)
    await page.goto(`/wzorce/${id}`);
    await page.getByRole('link', { name: 'Wydrukuj ćwiczenia' }).click();
    await expect(page.getByRole('heading', { name: /Ćwiczenia:/ })).toBeVisible();
    const answers = page.getByRole('region', { name: 'Odpowiedzi' });
    await expect(answers.getByTestId('print-solution').first()).toBeVisible();
  });

  test('another user cannot open the pattern', async ({ page, context }) => {
    const created = await page.request.post('/api/patterns', {
      data: { trigger: 'Wyzwalacz do testu dostępu', action: 'Akcja do testu dostępu' },
    });
    expect(created.status()).toBe(201);
    const id = (await created.json()).pattern.id as string;

    await context.clearCookies();
    await loginAs(context, TEST_USERS.user2);
    const response = await page.goto(`/wzorce/${id}`);
    expect(response?.status()).toBe(404);
  });
});
