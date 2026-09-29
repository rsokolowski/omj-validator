/**
 * Typed solutions: text only, no photos, graded over the WebSocket. The
 * problem text is invented (never OMJ material).
 */

import { test, expect } from '@playwright/test';
import { loginAs, TEST_USERS } from './utils/auth';
import { resetGemini } from './utils/api';

const SOLUTION =
  'Niech $n$ będzie liczbą całkowitą. Wtedy $n(n+1)$ jest parzyste, bo jedna z liczb $n$, $n+1$ jest parzysta.\n$$n^2 + n = n(n+1)$$';

test.describe('Typed solutions', () => {
  test.beforeEach(async ({ context, request }) => {
    await loginAs(context, TEST_USERS.default);
    await resetGemini(request);
  });

  test.afterEach(async ({ request }) => {
    await resetGemini(request);
  });

  test('text only is submitted and graded', async ({ page }) => {
    await page.goto('/task/2024/etap2/1');
    await page.waitForLoadState('networkidle');

    const submit = page.getByRole('button', { name: /prześlij rozwiązanie/i });
    await expect(submit).toBeDisabled();

    await page.getByLabel('Tekst rozwiązania').fill(SOLUTION);
    const preview = page.getByRole('region', { name: 'Podgląd rozwiązania' });
    await expect(preview.locator('.katex').first()).toBeVisible();
    await expect(page.getByText(/^\d+ \/ 20 000/)).toBeVisible();

    await expect(submit).toBeEnabled();
    await submit.click();
    await expect(page.getByText(/Wynik: 6 \/ 6 punktów/)).toBeVisible({ timeout: 30000 });
  });

  test('the editors never call a third-party host', async ({ page }) => {
    const external: string[] = [];
    page.on('request', (req) => {
      const host = new URL(req.url()).hostname;
      if (host !== 'localhost' && host !== '127.0.0.1') external.push(req.url());
    });

    await page.goto('/task/2024/etap2/1');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: 'Wstaw wzór' }).click();
    await expect(page.locator('math-field')).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Anuluj' }).click();

    await page.getByRole('button', { name: 'Dodaj rysunek' }).click();
    await expect(page.locator('.excalidraw')).toBeVisible({ timeout: 20000 });
    await page.getByRole('button', { name: 'Anuluj' }).click();

    await page.waitForLoadState('networkidle');
    expect(external, 'requests to third-party hosts').toEqual([]);
  });

  test('the drawing editor offers no way off the page', async ({ page }) => {
    await page.goto('/task/2024/etap2/1');
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: 'Dodaj rysunek' }).click();
    const editor = page.locator('.excalidraw');
    await expect(editor).toBeVisible({ timeout: 20000 });

    // Library browser and help dialog (docs, blog, YouTube) are not offered
    await expect(editor.locator('.default-sidebar-trigger')).toBeHidden();
    await expect(editor.locator('.help-icon')).toBeHidden();

    // The main menu keeps only on-page items - no GitHub / Discord / X links
    await editor.locator('.main-menu-trigger').click();
    await expect(editor.locator('.dropdown-menu')).toBeVisible();
    await expect(editor.locator('a[href^="http"]')).toHaveCount(0);
    await page.keyboard.press('Escape');

    // Web embeds and the Mermaid dialog are gone, drawing tools stay
    await editor.locator('.App-toolbar__extra-tools-trigger').click();
    await expect(editor.getByTestId('toolbar-laser')).toBeVisible();
    await expect(editor.getByTestId('toolbar-embeddable')).toHaveCount(2);
    for (const item of await editor.getByTestId('toolbar-embeddable').all()) {
      await expect(item).toBeHidden();
    }
    await page.keyboard.press('Escape');

    // The "?" shortcut must not open the help dialog either
    await editor.locator('canvas').last().click({ position: { x: 300, y: 200 } });
    await page.keyboard.press('Shift+?');
    await expect(editor.locator('.HelpDialog')).toHaveCount(0);
  });
});
