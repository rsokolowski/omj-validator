/**
 * Authentication Tests
 *
 * Tests for authentication states and user management.
 */

import { test, expect } from '@playwright/test';
import { loginAs, logout, TEST_USERS, isLoggedIn, getCurrentUser } from './utils/auth';

test.describe('Authentication', () => {
  test.describe('Session management', () => {
    test('unauthenticated user has no session', async ({ page }) => {
      await page.goto('/');
      const loggedIn = await isLoggedIn(page);
      expect(loggedIn).toBe(false);
    });

    test('can login with test user session', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.default);
      await page.goto('/');

      const loggedIn = await isLoggedIn(page);
      expect(loggedIn).toBe(true);
    });

    test('session contains correct user info', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.default);
      await page.goto('/');

      const user = await getCurrentUser(page);
      expect(user).not.toBeNull();
      expect(user?.email).toBe(TEST_USERS.default.email);
      expect(user?.name).toBe(TEST_USERS.default.name);
    });

    test('can switch between users', async ({ page, context }) => {
      // Login as first user
      await loginAs(context, TEST_USERS.default);
      await page.goto('/');

      let user = await getCurrentUser(page);
      expect(user?.email).toBe(TEST_USERS.default.email);

      // Switch to second user
      await logout(context);
      await loginAs(context, TEST_USERS.user2);
      await page.reload();

      user = await getCurrentUser(page);
      expect(user?.email).toBe(TEST_USERS.user2.email);
    });

    test('logout clears session', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.default);
      await page.goto('/');

      expect(await isLoggedIn(page)).toBe(true);

      await logout(context);
      await page.reload();

      expect(await isLoggedIn(page)).toBe(false);
    });
  });

  test.describe('API authentication', () => {
    test('unauthenticated request to /api/auth/me returns not authenticated', async ({ page }) => {
      await page.goto('/');
      const response = await page.request.get('/api/auth/me');
      const data = await response.json();

      expect(data.is_authenticated).toBe(false);
    });

    test('authenticated request to /api/auth/me returns user info', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.default);
      await page.goto('/');

      const response = await page.request.get('/api/auth/me');
      const data = await response.json();

      expect(data.is_authenticated).toBe(true);
      expect(data.user.email).toBe(TEST_USERS.default.email);
    });

    test('API returns 403 for protected endpoints without auth', async ({ page }) => {
      // Task history requires auth
      await page.goto('/');

      const response = await page.request.get('/api/task/2024/etap2/1/history');

      // Backend returns 403 Forbidden for unauthenticated requests to protected endpoints
      expect(response.status()).toBe(403);
    });
  });

  test.describe('Group membership', () => {
    test('user with group membership can access submit', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.default);
      await page.goto('/task/2024/etap2/1');

      // Should see submit section
      const submitButton = page.getByRole('button', { name: /prześlij/i }).or(
        page.locator('[data-testid="submit-button"]')
      );
      await expect(submitButton).toBeVisible();
    });

    test('user without group membership sees restricted message', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.restricted);
      await page.goto('/task/2024/etap2/1');

      // Wait for page to load, then check state immediately (no auto-waiting)
      await page.waitForLoadState('networkidle');

      // Use count() which doesn't auto-wait - instant check
      const hasRestrictedMessage = await page.getByText(/członkostwa/i).count() > 0;
      const submitButton = page.getByRole('button', { name: /prześlij/i });
      const hasSubmitButton = await submitButton.count() > 0 && await submitButton.isEnabled({ timeout: 100 }).catch(() => false);

      // Either restricted message shown or submit button disabled/absent
      expect(hasRestrictedMessage || !hasSubmitButton).toBe(true);
    });
  });

  test.describe('Cross-user isolation', () => {
    test('user cannot see another user submission history', async ({ page, context, request }) => {
      // This test verifies that user A's submissions are not visible to user B

      // Login as user 1
      await loginAs(context, TEST_USERS.default);
      await page.goto('/task/2024/etap2/1');

      // Get submission history for user 1
      const response1 = await page.request.get('/api/task/2024/etap2/1/history');
      const history1 = await response1.json();

      // Now switch to user 2
      await logout(context);
      await loginAs(context, TEST_USERS.user2);
      await page.goto('/task/2024/etap2/1');

      // Get submission history for user 2
      const response2 = await page.request.get('/api/task/2024/etap2/1/history');
      const history2 = await response2.json();

      // Each user should only see their own submissions
      // (both might be empty for fresh test database)
      if (history1.submissions?.length > 0) {
        const user1Ids = history1.submissions.map((s: any) => s.user_id);
        expect(user1Ids.every((id: string) => id !== TEST_USERS.user2.google_sub)).toBe(true);
      }

      if (history2.submissions?.length > 0) {
        const user2Ids = history2.submissions.map((s: any) => s.user_id);
        expect(user2Ids.every((id: string) => id !== TEST_USERS.default.google_sub)).toBe(true);
      }
    });
  });
});
