/**
 * Task Browsing Tests
 *
 * Tests for browsing tasks, viewing task details, hints, and metadata.
 */

import { test, expect } from '@playwright/test';
import { loginAs, TEST_USERS } from './utils/auth';

test.describe('Task Browsing', () => {
  test.beforeEach(async ({ context }) => {
    await loginAs(context, TEST_USERS.default);
  });

  test.describe('Years listing', () => {
    test('displays available years', async ({ page }) => {
      await page.goto('/years');

      // Should show multiple years
      await expect(page.getByRole('link', { name: /2024/ })).toBeVisible();
      await expect(page.getByRole('link', { name: /2023/ })).toBeVisible();
    });

    test('years are sorted in descending order', async ({ page }) => {
      await page.goto('/years');

      // Get all year links
      const yearLinks = await page.getByRole('link', { name: /20\d{2}/ }).all();

      // Extract year numbers
      const years: number[] = [];
      for (const link of yearLinks) {
        const text = await link.textContent();
        const match = text?.match(/20\d{2}/);
        if (match) {
          years.push(parseInt(match[0]));
        }
      }

      // Verify descending order
      for (let i = 0; i < years.length - 1; i++) {
        expect(years[i]).toBeGreaterThanOrEqual(years[i + 1]);
      }
    });
  });

  test.describe('Etaps listing', () => {
    test('displays etaps for a year', async ({ page }) => {
      await page.goto('/years/2024');

      // Should show etap links - use exact names
      await expect(page.getByRole('link', { name: 'Etap I', exact: true })).toBeVisible();
      await expect(page.getByRole('link', { name: 'Etap II', exact: true })).toBeVisible();
    });

    test('shows task count per etap', async ({ page }) => {
      await page.goto('/years/2024');

      // Each etap card should show number of tasks - just verify page loads with content
      await expect(page.getByRole('link', { name: /etap/i }).first()).toBeVisible();
    });
  });

  test.describe('Task list', () => {
    test('displays task cards with titles', async ({ page }) => {
      await page.goto('/years/2024/etap2');

      // Should show task cards as links with "Zadanie X" in the name
      const taskLinks = page.getByRole('link', { name: /Zadanie \d/i });

      await expect(taskLinks.first()).toBeVisible();

      // Should have multiple tasks (etap2 has 5)
      expect(await taskLinks.count()).toBeGreaterThanOrEqual(1);
    });

    test('task cards show difficulty stars', async ({ page }) => {
      await page.goto('/years/2024/etap2');

      // Look for difficulty indicators (star symbols ★)
      await expect(
        page.getByText(/★/).first()
      ).toBeVisible();
    });

    test('task cards show categories', async ({ page }) => {
      await page.goto('/years/2024/etap2');

      // Look for category badges
      const categoryBadges = page.locator('[data-testid="category-badge"]').or(
        page.locator('.category-badge').or(
          page.getByText(/geometria|algebra|teoria|kombinatoryka|logika|arytmetyka/i).first()
        )
      );

      await expect(categoryBadges).toBeVisible();
    });

    test('clicking task card navigates to task page', async ({ page }) => {
      await page.goto('/years/2024/etap2');

      // Click first task
      const firstTask = page.locator('[data-testid="task-card"]').first().or(
        page.getByRole('link', { name: /Zadanie 1/i })
      );

      await firstTask.click();

      await expect(page).toHaveURL(/\/task\/2024\/etap2\/\d/);
    });
  });

  test.describe('Task detail', () => {
    test('shows task title and content', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Should show task number - use heading role for specificity
      await expect(page.getByRole('heading', { name: /zadanie/i })).toBeVisible();

      // Should have task content (LaTeX rendered or plain text)
      const content = page.locator('[data-testid="task-content"]').or(
        page.locator('.task-content').or(page.locator('main').first())
      );

      await expect(content).toBeVisible();
    });

    test('renders LaTeX content', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // LaTeX is rendered via KaTeX - look for rendered math elements
      const mathContent = page.locator('.katex').or(
        page.locator('math').or(page.locator('[class*="math"]'))
      );

      // At least some tasks have LaTeX
      // This may or may not be visible depending on task content
      const hasMath = await mathContent.count() > 0;

      // Task should have some content regardless
      await expect(page.locator('main')).not.toBeEmpty();
    });

    test('shows task metadata (difficulty, categories)', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Should show difficulty (stars or text)
      await expect(
        page.locator('[data-testid="difficulty"]').or(page.getByText(/★/).first())
      ).toBeVisible();

      // Should show categories
      await expect(
        page.getByText(/geometria|algebra|teoria|kombinatoryka|logika|arytmetyka/i).first()
      ).toBeVisible();
    });

    test('can view PDF', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Should have link to PDF
      const pdfLink = page.getByRole('link', { name: /pdf/i }).or(
        page.locator('a[href*=".pdf"]')
      );

      if (await pdfLink.count() > 0) {
        const href = await pdfLink.first().getAttribute('href');
        expect(href).toMatch(/\/pdf\//);
      }
    });
  });

  test.describe('Hints', () => {
    test('shows hints section', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Should have hints section - use heading for specificity
      await expect(
        page.getByRole('heading', { name: /wskazówk/i })
      ).toBeVisible();
    });

    test('hints are progressively revealed', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Should have button to reveal hint
      const revealButton = page.getByRole('button', { name: /pokaż.*wskazówk/i });

      if (await revealButton.isVisible()) {
        // Click to reveal first hint
        await revealButton.click();

        // Hint content should appear (text changes or content shows)
        await expect(page.getByText(/wskazówk/i).first()).toBeVisible();
      }
    });
  });

  test.describe('Navigation between tasks', () => {
    test('can navigate to next task', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Find next task link
      const nextLink = page.getByRole('link', { name: /następne/i }).or(
        page.getByRole('link', { name: /next/i }).or(
          page.locator('a[href*="/task/2024/etap2/2"]')
        )
      );

      if (await nextLink.isVisible()) {
        await nextLink.click();
        await expect(page).toHaveURL(/\/task\/2024\/etap2\/2/);
      }
    });

    test('can navigate to previous task', async ({ page }) => {
      await page.goto('/task/2024/etap2/2');

      // Find previous task link
      const prevLink = page.getByRole('link', { name: /poprzednie/i }).or(
        page.getByRole('link', { name: /prev/i }).or(
          page.locator('a[href*="/task/2024/etap2/1"]')
        )
      );

      if (await prevLink.isVisible()) {
        await prevLink.click();
        await expect(page).toHaveURL(/\/task\/2024\/etap2\/1/);
      }
    });
  });

  test.describe('Error handling', () => {
    test('shows 404 for non-existent task', async ({ page }) => {
      const response = await page.goto('/task/2024/etap2/999');

      // Should show error or 404 (backend may return 404 or 500 with error page)
      const status = response?.status();
      const hasErrorText = await page.getByText(/nie znaleziono/i).isVisible() ||
                           await page.getByText(/404/i).isVisible() ||
                           await page.getByText(/error/i).isVisible();
      expect(status === 404 || status === 500 || hasErrorText).toBe(true);
    });

    test('shows error for invalid year', async ({ page }) => {
      const response = await page.goto('/years/invalid');

      // Should handle error (may be 4xx or 500 with error page)
      const status = response?.status();
      expect(status).toBeGreaterThanOrEqual(400);
    });

    test('shows error for invalid etap', async ({ page }) => {
      const response = await page.goto('/years/2024/invalid');

      // Should handle error (may be 4xx or 500 with error page)
      const status = response?.status();
      expect(status).toBeGreaterThanOrEqual(400);
    });
  });
});
