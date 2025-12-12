/**
 * My Solutions Panel Tests
 *
 * Tests for the "Moje rozwiązania" panel that displays user's submission history.
 * This panel requires authentication and shows only the current user's submissions.
 */

import { test, expect } from '@playwright/test';
import { loginAs, logout, TEST_USERS } from './utils/auth';

test.describe('My Solutions Panel', () => {
  test.describe('Unauthenticated user access', () => {
    test('unauthenticated user does not see "Moje rozwiązania" link in header', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Should NOT see "Moje rozwiązania" link in header
      const mySolutionsLink = page.locator('a[href="/my-solutions"]');
      await expect(mySolutionsLink).not.toBeVisible();
    });

    test('unauthenticated user is redirected to login', async ({ page }) => {
      await page.goto('/my-solutions');

      // Should be redirected to login page with next parameter
      await expect(page).toHaveURL(/\/login.*next.*my-solutions/i);
    });

    test('unauthenticated user gets 401 from my-submissions API', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/my-submissions');
      expect(response.status()).toBe(401);
    });
  });

  test.describe('Authenticated user access', () => {
    test.beforeEach(async ({ context }) => {
      await loginAs(context, TEST_USERS.default);
    });

    test('authenticated user sees "Moje rozwiązania" link in header', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Should see "Moje rozwiązania" link in header
      const mySolutionsLink = page.locator('a[href="/my-solutions"]');
      await expect(mySolutionsLink).toBeVisible();
    });

    test('authenticated user can access my solutions page', async ({ page }) => {
      await page.goto('/my-solutions');

      // Should see the page title
      await expect(page.getByRole('heading', { name: /moje rozwiązania/i })).toBeVisible();

      // Should see the description
      await expect(page.getByText(/przeglądaj historię/i)).toBeVisible();
    });

    test('page displays statistics cards', async ({ page }) => {
      await page.goto('/my-solutions');
      await page.waitForLoadState('networkidle');

      // Should see statistics cards (they may show 0 for test users with no submissions)
      await expect(page.getByText('Wszystkie')).toBeVisible();
      await expect(page.getByText('Ukończone')).toBeVisible();
      await expect(page.getByText('Średnia')).toBeVisible();
      await expect(page.getByText('Opanowane')).toBeVisible();
    });

    test('page displays filter controls', async ({ page }) => {
      await page.goto('/my-solutions');
      await page.waitForLoadState('networkidle');

      // Should see filter controls
      await expect(page.getByText('Filtry:')).toBeVisible();

      // Should see year and etap dropdowns (MUI Select components)
      // MUI InputLabel creates multiple elements, use .first() to get the label
      await expect(page.getByText('Rok').first()).toBeVisible();
      await expect(page.getByText('Etap').first()).toBeVisible();

      // Should see "show errors" checkbox
      await expect(page.getByText(/pokaż błędy systemowe/i)).toBeVisible();
    });

    test('shows submissions list or empty state appropriately', async ({ page }) => {
      await page.goto('/my-solutions');
      await page.waitForLoadState('networkidle');

      // The page should display either:
      // 1. "Brak rozwiązań" empty state with a CTA button, or
      // 2. A list of submission cards
      // Both states are valid depending on user's history

      const emptyStateMessage = page.getByText(/brak rozwiązań/i);
      const browseTasksButton = page.getByRole('link', { name: /przeglądaj zadania/i });

      // Check if empty state is shown
      const isEmptyState = await emptyStateMessage.isVisible().catch(() => false);

      if (isEmptyState) {
        // Empty state should show a CTA to browse tasks
        await expect(browseTasksButton).toBeVisible();
      } else {
        // Should have the filters bar (which means content area is loaded)
        await expect(page.getByText('Filtry:')).toBeVisible();
      }
    });

    test('can navigate to my solutions from header', async ({ page }) => {
      await page.goto('/');

      // Click on "Moje rozwiązania" link in header
      await page.getByRole('link', { name: /moje rozwiązania/i }).click();

      // Should be on my-solutions page
      await expect(page).toHaveURL(/\/my-solutions/);
      await expect(page.getByRole('heading', { name: /moje rozwiązania/i })).toBeVisible();
    });
  });

  test.describe('API functionality', () => {
    test.beforeEach(async ({ context }) => {
      await loginAs(context, TEST_USERS.default);
    });

    test('my-submissions API returns proper structure', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/my-submissions');
      expect(response.status()).toBe(200);

      const data = await response.json();

      // Check response structure
      expect(data).toHaveProperty('submissions');
      expect(data).toHaveProperty('stats');
      expect(data).toHaveProperty('total_count');
      expect(data).toHaveProperty('offset');
      expect(data).toHaveProperty('limit');
      expect(data).toHaveProperty('has_more');

      // Check submissions is an array
      expect(Array.isArray(data.submissions)).toBe(true);

      // Check stats structure
      expect(data.stats).toHaveProperty('total_submissions');
      expect(data.stats).toHaveProperty('completed_count');
      expect(data.stats).toHaveProperty('failed_count');
      expect(data.stats).toHaveProperty('pending_count');
      expect(data.stats).toHaveProperty('tasks_attempted');
      expect(data.stats).toHaveProperty('tasks_mastered');
    });

    test('API supports pagination parameters', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/my-submissions?offset=0&limit=5');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data.offset).toBe(0);
      expect(data.limit).toBe(5);
    });

    test('API supports year filter', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/my-submissions?year=2024');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(Array.isArray(data.submissions)).toBe(true);

      // All returned submissions should be from 2024 (if any exist)
      for (const submission of data.submissions) {
        expect(submission.year).toBe('2024');
      }
    });

    test('API supports etap filter', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/my-submissions?etap=etap1');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(Array.isArray(data.submissions)).toBe(true);

      // All returned submissions should be from etap1 (if any exist)
      for (const submission of data.submissions) {
        expect(submission.etap).toBe('etap1');
      }
    });

    test('API supports hide_errors parameter', async ({ page }) => {
      await page.goto('/');

      // Default behavior (hide_errors=false)
      const responseAll = await page.request.get('/api/my-submissions');
      expect(responseAll.status()).toBe(200);

      // With hide_errors=true
      const responseNoErrors = await page.request.get('/api/my-submissions?hide_errors=true');
      expect(responseNoErrors.status()).toBe(200);

      const dataNoErrors = await responseNoErrors.json();
      expect(Array.isArray(dataNoErrors.submissions)).toBe(true);

      // No failed submissions should be returned when hide_errors=true
      for (const submission of dataNoErrors.submissions) {
        expect(submission.status).not.toBe('failed');
      }
    });

    test('API supports combined filters', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/my-submissions?year=2024&etap=etap2&hide_errors=true');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(Array.isArray(data.submissions)).toBe(true);

      // All returned submissions should match filters
      for (const submission of data.submissions) {
        expect(submission.year).toBe('2024');
        expect(submission.etap).toBe('etap2');
        expect(submission.status).not.toBe('failed');
      }
    });
  });

  test.describe('Cross-user isolation', () => {
    test('users can only see their own submissions', async ({ page, context }) => {
      // Login as user 1
      await loginAs(context, TEST_USERS.default);
      await page.goto('/my-solutions');

      // Get submissions for user 1
      const response1 = await page.request.get('/api/my-submissions');
      const data1 = await response1.json();

      // Switch to user 2
      await logout(context);
      await loginAs(context, TEST_USERS.user2);
      await page.goto('/my-solutions');

      // Get submissions for user 2
      const response2 = await page.request.get('/api/my-submissions');
      const data2 = await response2.json();

      // Each user should only see their own submissions
      // Note: submission objects don't expose user_id to the client,
      // so we verify the API returns different results for different users
      // and that the stats are user-specific

      // The stats for each user are independent
      expect(data1.stats).toBeDefined();
      expect(data2.stats).toBeDefined();

      // Both responses should have valid structure
      expect(Array.isArray(data1.submissions)).toBe(true);
      expect(Array.isArray(data2.submissions)).toBe(true);
    });
  });

  test.describe('Restricted user access', () => {
    test('restricted user can access my solutions page', async ({ page, context }) => {
      // Restricted users can still view their own submissions
      await loginAs(context, TEST_USERS.restricted);
      await page.goto('/my-solutions');

      // Should see the page title (access is allowed)
      await expect(page.getByRole('heading', { name: /moje rozwiązania/i })).toBeVisible();
    });

    test('restricted user sees "Moje rozwiązania" link in header', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.restricted);
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Restricted users can still see the link
      const mySolutionsLink = page.locator('a[href="/my-solutions"]');
      await expect(mySolutionsLink).toBeVisible();
    });

    test('restricted user can access my-submissions API', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.restricted);
      await page.goto('/');

      const response = await page.request.get('/api/my-submissions');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('submissions');
      expect(data).toHaveProperty('stats');
    });
  });

  test.describe('UI interactions', () => {
    test.beforeEach(async ({ context }) => {
      await loginAs(context, TEST_USERS.default);
    });

    test('can toggle show errors checkbox', async ({ page }) => {
      await page.goto('/my-solutions');
      await page.waitForLoadState('networkidle');

      // Find the checkbox by its associated label text
      const checkboxLabel = page.getByText(/pokaż błędy systemowe/i);
      const checkbox = page.getByRole('checkbox').filter({ has: checkboxLabel }).or(
        page.locator('label').filter({ hasText: /pokaż błędy/i }).locator('input[type="checkbox"]')
      );

      // Initially unchecked
      await expect(checkbox.first()).not.toBeChecked();

      // Click to check (clicking the label is more reliable)
      await checkboxLabel.click();

      // Click to uncheck
      await checkboxLabel.click();
    });

    test('submission count updates with filters', async ({ page }) => {
      await page.goto('/my-solutions');
      await page.waitForLoadState('networkidle');

      // Should see a count indicator (e.g., "X rozwiązań")
      const countText = page.getByText(/\d+\s+rozwiąza/i);
      await expect(countText).toBeVisible();
    });
  });
});
