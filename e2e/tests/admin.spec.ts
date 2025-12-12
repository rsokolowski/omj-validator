/**
 * Admin Panel Tests
 *
 * Tests for admin panel access control and functionality.
 * Admin access is controlled by ADMIN_EMAILS environment variable.
 */

import { test, expect } from '@playwright/test';
import { loginAs, logout, TEST_USERS } from './utils/auth';

test.describe('Admin Panel', () => {
  test.describe('Admin user access', () => {
    test.beforeEach(async ({ context }) => {
      await loginAs(context, TEST_USERS.admin);
    });

    test('admin sees admin link in header', async ({ page }) => {
      await page.goto('/');

      // Admin should see the Admin link in the header pointing to admin submissions
      const adminLink = page.locator('a[href="/admin/submissions"]');
      await expect(adminLink).toBeVisible();
    });

    test('admin can access admin submissions page', async ({ page }) => {
      await page.goto('/admin/submissions');

      // Should see the admin page title (in Polish)
      await expect(page.getByRole('heading', { name: /panel administratora/i })).toBeVisible();

      // Should see the description (in Polish)
      await expect(page.getByText(/przeglądaj i filtruj rozwiązania/i)).toBeVisible();
    });

    test('admin can view submissions table', async ({ page }) => {
      await page.goto('/admin/submissions');

      // Wait for page to load
      await page.waitForLoadState('networkidle');

      // Should see the filter section with status filter (MUI Select)
      await expect(page.getByText('Status').first()).toBeVisible();

      // Should see the submissions count text (use first() to handle multiple matches)
      await expect(page.getByText(/\d+ submission.*found/i).first()).toBeVisible();
    });

    test('admin can access admin API endpoint', async ({ page }) => {
      await page.goto('/');

      // Test /api/admin/me endpoint
      const meResponse = await page.request.get('/api/admin/me');
      expect(meResponse.status()).toBe(200);

      const meData = await meResponse.json();
      expect(meData.is_authenticated).toBe(true);
      expect(meData.is_admin).toBe(true);
      expect(meData.user.email).toBe(TEST_USERS.admin.email);
    });

    test('admin can fetch submissions via API', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/admin/submissions');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('submissions');
      expect(data).toHaveProperty('total_count');
      expect(data).toHaveProperty('has_more');
      expect(Array.isArray(data.submissions)).toBe(true);
    });

    test('admin can filter submissions by status via API', async ({ page }) => {
      await page.goto('/');

      // Test filtering via API directly - more reliable than UI interaction
      const response = await page.request.get('/api/admin/submissions?status=completed');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('submissions');
      expect(Array.isArray(data.submissions)).toBe(true);

      // All returned submissions should have completed status (if any exist)
      for (const submission of data.submissions) {
        expect(submission.status).toBe('completed');
      }
    });

    test('admin can search users via API', async ({ page }) => {
      await page.goto('/');

      // Search for test users (should find test-user@example.com)
      const response = await page.request.get('/api/admin/users/search?q=test-user');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('users');
      expect(Array.isArray(data.users)).toBe(true);
    });
  });

  test.describe('Non-admin user access', () => {
    test.beforeEach(async ({ context }) => {
      await loginAs(context, TEST_USERS.default);
    });

    test('non-admin does not see admin link in header', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Non-admin should NOT see the Admin chip in the header
      const adminChip = page.locator('a[href="/admin/submissions"]');
      await expect(adminChip).not.toBeVisible();
    });

    test('non-admin sees access denied on admin page', async ({ page }) => {
      await page.goto('/admin/submissions');

      // Should see the access denied message (in Polish)
      await expect(page.getByText(/brak dostępu/i)).toBeVisible();
      await expect(page.getByText(/nie masz uprawnień/i)).toBeVisible();
    });

    test('non-admin API check returns is_admin false', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/admin/me');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data.is_authenticated).toBe(true);
      expect(data.is_admin).toBe(false);
    });

    test('non-admin gets 403 from admin submissions API', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/admin/submissions');
      expect(response.status()).toBe(403);
    });

    test('non-admin gets 403 from admin user search API', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/admin/users/search?q=test');
      expect(response.status()).toBe(403);
    });
  });

  test.describe('Unauthenticated user access', () => {
    test('unauthenticated user does not see admin link', async ({ page }) => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Unauthenticated user should NOT see the Admin chip
      const adminChip = page.locator('a[href="/admin/submissions"]');
      await expect(adminChip).not.toBeVisible();
    });

    test('unauthenticated user is redirected to login from admin page', async ({ page }) => {
      await page.goto('/admin/submissions');

      // Should be redirected to login page with next parameter
      await expect(page).toHaveURL(/\/login.*next.*admin/i);
    });

    test('unauthenticated API check returns not authenticated', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/admin/me');
      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data.is_authenticated).toBe(false);
      expect(data.is_admin).toBe(false);
    });

    test('unauthenticated user gets 401 from admin submissions API', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/admin/submissions');
      // Backend returns 401 for unauthenticated requests
      expect(response.status()).toBe(401);
    });

    test('unauthenticated user gets 401 from admin user search API', async ({ page }) => {
      await page.goto('/');

      const response = await page.request.get('/api/admin/users/search?q=test');
      expect(response.status()).toBe(401);
    });
  });

  test.describe('Admin panel navigation', () => {
    test('admin can navigate to admin panel from header', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.admin);
      await page.goto('/');

      // Click on admin link in header
      await page.getByRole('link', { name: /admin/i }).click();

      // Should be on admin page
      await expect(page).toHaveURL(/\/admin\/submissions/);
      await expect(page.getByRole('heading', { name: /panel administratora/i })).toBeVisible();
    });

    test('switching from admin to non-admin user hides admin link', async ({ page, context }) => {
      // Login as admin
      await loginAs(context, TEST_USERS.admin);
      await page.goto('/');

      // Admin chip should be visible
      await expect(page.locator('a[href="/admin/submissions"]')).toBeVisible();

      // Switch to non-admin user
      await logout(context);
      await loginAs(context, TEST_USERS.default);
      await page.reload();

      // Admin chip should not be visible
      await expect(page.locator('a[href="/admin/submissions"]')).not.toBeVisible();
    });
  });

  test.describe('Restricted user access', () => {
    test('restricted user cannot access admin panel', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.restricted);
      await page.goto('/admin/submissions');

      // Should see access denied (in Polish)
      await expect(page.getByText(/brak dostępu/i)).toBeVisible();
    });

    test('restricted user does not see admin link in header', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.restricted);
      await page.goto('/');
      await page.waitForLoadState('networkidle');

      // Should not see admin link
      const adminChip = page.locator('a[href="/admin/submissions"]');
      await expect(adminChip).not.toBeVisible();
    });
  });
});
