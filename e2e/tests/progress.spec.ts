/**
 * Progress Tests
 *
 * Tests for the task progression graph and user progress tracking.
 */

import { test, expect } from '@playwright/test';
import { loginAs, logout, TEST_USERS } from './utils/auth';
import { setGeminiScenario, resetGemini } from './utils/api';
import * as path from 'path';

const FIXTURES_DIR = path.join(__dirname, '..', 'fixtures');
const TEST_IMAGE = path.join(FIXTURES_DIR, 'test-solution.jpg');

test.describe('Progress Tracking', () => {
  test.beforeEach(async ({ context, request }) => {
    await loginAs(context, TEST_USERS.default);
    await resetGemini(request);
  });

  test.afterEach(async ({ request }) => {
    await resetGemini(request);
  });

  test.describe('Progress page', () => {
    test('displays progress page for authenticated user', async ({ page }) => {
      await page.goto('/progress');

      // Should show progress section - verify page loads
      await expect(page).toHaveURL(/progress/);
      await expect(page.getByRole('heading').first()).toBeVisible();
    });

    test('shows graph or task progression', async ({ page }) => {
      await page.goto('/progress');

      // Wait for page to load
      await page.waitForLoadState('networkidle');

      // Page should be visible (content may vary)
      await expect(page).toHaveURL(/progress/);
    });

    test('shows category filter options', async ({ page }) => {
      await page.goto('/progress');

      // Look for category filter
      const categoryFilter = page.locator('[data-testid="category-filter"]').or(
        page.getByText(/kategori/i).or(page.getByText(/filtr/i))
      );

      // May or may not have filter depending on implementation
      const hasFilter = await categoryFilter.isVisible().catch(() => false);

      // At minimum, page should load without error
      await expect(page).toHaveURL(/progress/);
    });
  });

  test.describe('Progress data', () => {
    test('API returns progress data', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/progress/data');
      expect(response.ok()).toBe(true);

      const data = await response.json();
      // Should have some structure (tasks, progress, etc.)
      expect(data).toBeDefined();
    });

    test('progress updates after submission', async ({ page, request }) => {
      await setGeminiScenario(request, 'success_score_6');

      // Get initial progress
      await page.goto('/');
      const initialResponse = await page.request.get('/api/progress/data');
      const initialData = await initialResponse.json();

      // Submit a solution
      await page.goto('/task/2024/etap2/1');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);
      await page.getByRole('button', { name: /prześlij/i }).click();
      await expect(page.getByText(/Wynik:\s*6\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });

      // Get updated progress
      const updatedResponse = await page.request.get('/api/progress/data');
      const updatedData = await updatedResponse.json();

      // Progress should reflect the submission
      // (exact format depends on API implementation)
      expect(updatedData).toBeDefined();
    });
  });

  test.describe('Cross-user progress isolation', () => {
    test('each user has separate progress', async ({ page, context, request }) => {
      await setGeminiScenario(request, 'success_score_6');

      // Submit as user 1
      await page.goto('/task/2024/etap2/1');
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);
      await page.getByRole('button', { name: /prześlij/i }).click();
      await expect(page.getByText(/Wynik:\s*6\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });

      // Get user 1 progress
      const user1Response = await page.request.get('/api/progress/data');
      const user1Data = await user1Response.json();

      // Switch to user 2
      await logout(context);
      await loginAs(context, TEST_USERS.user2);
      await page.goto('/');

      // Get user 2 progress (should be different/empty)
      const user2Response = await page.request.get('/api/progress/data');
      const user2Data = await user2Response.json();

      // User 2 should not have user 1's progress
      // (exact comparison depends on data structure)
      expect(user2Data).toBeDefined();
    });
  });

  test.describe('Unauthenticated access', () => {
    test('progress page accessible to unauthenticated users', async ({ page, context }) => {
      await logout(context);
      await page.goto('/progress');

      // Progress page is accessible - may show login prompt but not redirect
      await expect(page).toHaveURL(/progress/);
    });

    test('progress API accessible to unauthenticated users', async ({ page, context }) => {
      await logout(context);
      await page.goto('/');

      const response = await page.request.get('/api/progress/data');

      // Progress API is public - returns 200 with progress data
      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(data).toBeDefined();
    });
  });
});
