/**
 * Patterns ("Wzorce") end to end.
 *
 * The fake Gemini answers the three pattern calls with invented wording (see
 * PATTERN_* in e2e/fake-gemini/server.py): a refine round with two versions,
 * two suggestions from a graded solution, and a link to the first candidate
 * OMJ task in the prompt. Grading uses the default scenario (6 points).
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

    // 5. Graded practice from the pattern page: 6/6 without hints counts as a review
    await page.getByRole('region', { name: 'Zadania do tego wzorca' })
      .getByRole('link', { name: 'Rozwiąż' }).first().click();
    await expect(page.getByTestId('practice-banner')).toBeVisible();
    await submitSolution(page);

    await page.goto(`/wzorce/${patternId}`);
    await expect(page.getByTestId('review-history')).toContainText('Zadanie · Pamiętałem · Poziom 1');

    // 6. Due again (e2e hook) -> the header badge and a recall card -> level 2
    const due = await page.request.post(`/api/test/patterns/${patternId}/make-due`);
    expect(due.ok()).toBeTruthy();
    await page.goto('/wzorce');
    await expect(page.getByText('Do powtórki dziś: 1')).toBeVisible();
    await page.getByRole('link', { name: 'Zacznij' }).click();

    await expect(page.getByText('W zadaniu pojawiają się kolejne liczby całkowite')).toBeVisible({ timeout: 15000 });
    const show = page.getByRole('button', { name: 'Pokaż', exact: true });
    await expect(show).toBeDisabled();
    await page.getByLabel('…to warto spróbować… (napisz z pamięci)').fill('Jedna z dwóch kolejnych liczb jest parzysta');
    await show.click();
    await expect(page.getByText('Zapisany wzorzec')).toBeVisible();
    await page.getByRole('button', { name: 'Pamiętałem', exact: true }).click();
    await expect(page.getByText(/Poziom 2 · następna powtórka/)).toBeVisible();
    await page.getByRole('button', { name: 'Zakończ' }).click();
    await expect(page.getByText('Na dziś wszystko')).toBeVisible();

    await page.goto(`/wzorce/${patternId}`);
    await expect(page.getByTestId('pattern-level')).toHaveText('Poziom 2');
    const history = page.getByTestId('review-history');
    await expect(history).toContainText('Przypomnienie · Pamiętałem · Poziom 2');
    await expect(history).toContainText('Zadanie · Pamiętałem · Poziom 1');
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
