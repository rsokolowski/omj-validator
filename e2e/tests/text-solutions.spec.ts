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

    // Earlier specs submit to the same task as the same user, so the history
    // may already be on screen; remember its size to find our entry later
    const history = page.getByRole('heading', { name: /Historia rozwiązań/ });
    const before = (await history.count())
      ? Number((await history.textContent())?.match(/\((\d+)\)/)?.[1] ?? 0)
      : 0;

    await page.getByLabel('Tekst rozwiązania').fill(SOLUTION);
    const preview = page.getByRole('region', { name: 'Podgląd rozwiązania' });
    await expect(preview.locator('.katex').first()).toBeVisible();
    await expect(page.getByText(/^\d+ \/ 20 000/)).toBeVisible();

    await expect(submit).toBeEnabled();
    await submit.click();
    await expect(page.getByText(/Wynik: 6 \/ 6 punktów/)).toBeVisible({ timeout: 30000 });
    // The typed text survives the result, so the student can fix it and resubmit
    await expect(page.getByLabel('Tekst rozwiązania')).toHaveValue(SOLUTION);

    // The history below refreshes with the graded submission and shows the text
    // (wait for the refetch: clicking before it would expand an older entry)
    const ours = before + 1;
    await expect(history).toHaveText(new RegExp(`\\(${ours}\\)`), { timeout: 15000 });
    await page.getByRole('button', { name: `Rozwiń szczegóły rozwiązania numer ${ours}`, exact: true }).click();
    const toggle = page.getByRole('button', { name: /Wpisany tekst rozwiązania \(\d+ znaków\)/ });
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await toggle.click();
    // Scoped to this panel: earlier submissions of the same user keep theirs in the DOM
    const panel = page.locator(`[id="${await toggle.getAttribute('aria-controls')}"]`);
    await expect(panel.getByText(/jedna z liczb/)).toBeVisible();
  });

  test('the editors never call a third-party host', async ({ page }) => {
    const external: string[] = [];
    const fonts: string[] = [];
    page.on('request', (req) => {
      const url = new URL(req.url());
      // blob:/data: URLs (the drawing's thumbnail) never leave the browser
      if (url.protocol === 'blob:' || url.protocol === 'data:') return;
      if (url.hostname !== 'localhost' && url.hostname !== '127.0.0.1') external.push(req.url());
      else if (url.pathname.startsWith('/excalidraw/fonts/')) fonts.push(url.pathname);
    });

    await page.goto('/task/2024/etap2/1');
    await page.waitForLoadState('networkidle');

    // Typing in MathLive renders glyphs (it reuses the KaTeX faces the page
    // already declares, so /mathlive/fonts is only a fallback)
    await page.getByRole('button', { name: 'Wstaw wzór' }).click();
    const field = page.locator('math-field');
    await expect(field).toBeVisible({ timeout: 15000 });
    await field.click();
    await page.keyboard.type('x');
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: 'Anuluj' }).click();

    // A text element in Excalidraw loads its hand-drawn font; exporting the
    // drawing embeds fonts into the PNG
    await page.getByRole('button', { name: 'Dodaj rysunek' }).click();
    const editor = page.locator('.excalidraw');
    await expect(editor).toBeVisible({ timeout: 20000 });
    // The radio input sits under its icon, which takes the pointer events
    await editor.getByTestId('toolbar-text').click({ force: true });
    await editor.locator('canvas').last().click({ position: { x: 300, y: 200 } });
    await page.keyboard.type('ABC');
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'Dodaj do rozwiązania' }).click();
    await expect(page.getByTestId('image-preview')).toHaveCount(1);
    await expect(page.getByText('Zdjęcia i rysunki: 1 / 10')).toBeVisible();

    await page.waitForLoadState('networkidle');
    expect(fonts.length, 'Excalidraw fonts served locally').toBeGreaterThan(0);
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
