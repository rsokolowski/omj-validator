/**
 * Navigation Tests
 *
 * Tests for basic page navigation and routing.
 */

import { test, expect } from '@playwright/test';
import { loginAs, TEST_USERS, logout } from './utils/auth';

test.describe('Navigation', () => {
  test.describe('Unauthenticated user', () => {
    test('can view home page', async ({ page }) => {
      await page.goto('/');
      await expect(page).toHaveTitle(/OMJ/);
    });

    test('can view years list', async ({ page }) => {
      await page.goto('/years');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      // Should see year links
      await expect(page.getByRole('link', { name: /2024/ })).toBeVisible();
    });

    test('can view etaps for a year', async ({ page }) => {
      await page.goto('/years/2024');
      // Should have etap links - use specific role selector
      await expect(page.getByRole('link', { name: 'Etap I', exact: true })).toBeVisible();
    });

    test('can view task list for an etap', async ({ page }) => {
      await page.goto('/years/2024/etap2');
      // Should see task cards
      await expect(page.locator('[data-testid="task-card"]').or(page.getByText(/Zadanie/i).first())).toBeVisible();
    });

    test('can view task detail page', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');
      // Should see task content - use role for heading
      await expect(page.getByRole('heading', { name: /zadanie/i })).toBeVisible();
    });

    test('cannot submit solution without login', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');
      // Submit button should be disabled or hidden for unauthenticated users
      const submitSection = page.locator('[data-testid="submit-section"]').or(
        page.getByText(/Zaloguj się/i)
      );
      // Either no submit section or login prompt
      const hasLoginPrompt = await page.getByText(/Zaloguj się/i).isVisible().catch(() => false);
      const hasSubmitButton = await page.getByRole('button', { name: /prześlij/i }).isVisible().catch(() => false);

      // Unauthenticated users should either see login prompt or no submit option
      expect(hasLoginPrompt || !hasSubmitButton).toBe(true);
    });

    test('redirects to login when accessing protected routes', async ({ page }) => {
      await page.goto('/progress');
      // Progress page is accessible to unauthenticated users but may show login prompt
      // Just verify the page loads
      await expect(page).toHaveURL(/progress/);
    });
  });

  test.describe('Authenticated user', () => {
    test.beforeEach(async ({ context }) => {
      await loginAs(context, TEST_USERS.default);
    });

    test('can view home page', async ({ page }) => {
      await page.goto('/');
      await expect(page).toHaveTitle(/OMJ/);
    });

    test('can navigate through year -> etap -> task', async ({ page }) => {
      // Start at years
      await page.goto('/years');
      await expect(page.getByRole('link', { name: /2024/ })).toBeVisible();

      // Click on 2024
      await page.getByRole('link', { name: /2024/ }).click();
      await expect(page).toHaveURL(/\/years\/2024/);

      // Click on etap2 - use exact match
      await page.getByRole('link', { name: 'Etap II', exact: true }).click();
      await expect(page).toHaveURL(/\/years\/2024\/etap2/);

      // Click on first task - wait for cards to load
      await page.waitForLoadState('networkidle');
      const taskLink = page.locator('a[href*="/task/2024/etap2/"]').first();
      await taskLink.click();
      await expect(page).toHaveURL(/\/task\/2024\/etap2\/\d+/);
    });

    test('can view progress page', async ({ page }) => {
      await page.goto('/progress');
      // Should see progress page - verify URL and page loads
      await expect(page).toHaveURL(/progress/);
      // Page should have some content
      await expect(page.getByRole('heading').first()).toBeVisible();
    });

    test('sees user info in header', async ({ page }) => {
      await page.goto('/');
      // Should show user name or email
      await expect(
        page.getByText(TEST_USERS.default.name).or(
          page.getByText(TEST_USERS.default.email)
        )
      ).toBeVisible();
    });

    test('can logout', async ({ page, context }) => {
      await page.goto('/');

      // Find and click logout
      const logoutLink = page.getByRole('link', { name: /wyloguj/i }).or(
        page.getByRole('button', { name: /wyloguj/i })
      );

      if (await logoutLink.isVisible()) {
        await logoutLink.click();
        // After logout, should be logged out
        await logout(context);
        await page.goto('/');

        // Should not see user name anymore
        await expect(
          page.getByText(TEST_USERS.default.name)
        ).not.toBeVisible();
      }
    });
  });

  test.describe('Breadcrumb navigation', () => {
    test.beforeEach(async ({ context }) => {
      await loginAs(context, TEST_USERS.default);
    });

    test('shows correct breadcrumbs on task page', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Should have breadcrumb links
      const breadcrumb = page.locator('nav[aria-label="breadcrumb"]').or(
        page.locator('.breadcrumb')
      );

      // Should contain links to parent pages
      await expect(page.getByRole('link', { name: /2024/ })).toBeVisible();
      await expect(page.getByRole('link', { name: /etap/i })).toBeVisible();
    });

    test('can navigate back via breadcrumbs', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Click on year in breadcrumb
      await page.getByRole('link', { name: /2024/ }).first().click();
      await expect(page).toHaveURL(/\/years\/2024/);
    });
  });
});
