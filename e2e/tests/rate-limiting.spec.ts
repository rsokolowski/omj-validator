/**
 * Rate Limiting Tests
 *
 * Tests for rate limiting behavior including:
 * - Per-user submission limits
 * - Global submission limits
 * - Allowlist bypass behavior
 * - Rate limit headers validation
 *
 * E2E rate limits (configured in docker-compose.e2e.yml):
 * - RATE_LIMIT_SUBMISSIONS_PER_USER_PER_DAY: 3
 * - RATE_LIMIT_SUBMISSIONS_GLOBAL_PER_DAY: 10
 * - RATE_LIMIT_NEW_USERS_PER_DAY: 3
 *
 * TEST ISOLATION:
 * Each test resets the user's submissions before running to ensure
 * a clean slate regardless of previous test runs or other test files.
 */

import { test, expect } from '@playwright/test';
import { loginAs, logout, TEST_USERS } from './utils/auth';
import {
  setGeminiScenario,
  resetGemini,
  resetUserSubmissions,
  resetAllSubmissions,
} from './utils/api';
import * as path from 'path';

// Path to test fixtures
const FIXTURES_DIR = path.join(__dirname, '..', 'fixtures');
const TEST_IMAGE = path.join(FIXTURES_DIR, 'test-solution.jpg');

// API base URL for direct API calls
const API_BASE_URL = process.env.E2E_API_URL || 'http://localhost:8200';

// E2E rate limits (must match docker-compose.e2e.yml)
const RATE_LIMIT_PER_USER = 3;

/**
 * Helper to submit a solution via API and return response with headers.
 */
async function submitSolutionApi(
  request: any,
  year: string,
  etap: string,
  num: number,
  imagePath: string
): Promise<{ status: number; headers: Record<string, string>; body: any }> {
  const fs = await import('fs');
  const imageBuffer = fs.readFileSync(imagePath);

  const response = await request.post(`${API_BASE_URL}/task/${year}/${etap}/${num}/submit`, {
    multipart: {
      images: {
        name: 'test-solution.jpg',
        mimeType: 'image/jpeg',
        buffer: imageBuffer,
      },
    },
  });

  // Get headers - Playwright returns an object with lowercase keys
  const rawHeaders = response.headers();
  const headers: Record<string, string> = {};
  for (const key of Object.keys(rawHeaders)) {
    headers[key.toLowerCase()] = rawHeaders[key];
  }

  let body;
  try {
    body = await response.json();
  } catch {
    body = await response.text();
  }

  return {
    status: response.status(),
    headers,
    body,
  };
}

/**
 * Helper to wait for submission to complete (via WebSocket or polling).
 * We just need to ensure the submission is recorded, not wait for AI analysis.
 */
async function waitForSubmissionProcessing(ms: number = 500): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

test.describe('Rate Limiting', () => {
  // Reset all submissions before running rate-limiting tests to clear the global rate limit
  test.beforeAll(async ({ browser, request }) => {
    // Need to login first since resetAllSubmissions requires authentication
    const context = await browser.newContext();
    await loginAs(context, TEST_USERS.default);
    await resetAllSubmissions(context.request);
    await context.close();
  });

  test.beforeEach(async ({ request }) => {
    // Reset fake Gemini to fast success scenario
    await resetGemini(request);
    await setGeminiScenario(request, 'success_score_6');
  });

  test.afterEach(async ({ request }) => {
    await resetGemini(request);
  });

  test.describe('Per-user submission rate limiting', () => {
    test('rate-limited user gets 429 after exceeding per-user limit', async ({ context }) => {
      // Login as rate-limited user (NOT in ALLOWED_EMAILS)
      await loginAs(context, TEST_USERS.rateLimited);
      const request = context.request;

      // Reset submissions to ensure clean slate
      await resetUserSubmissions(request);

      // Submit up to the limit (3 submissions)
      for (let i = 0; i < RATE_LIMIT_PER_USER; i++) {
        const result = await submitSolutionApi(request, '2024', 'etap2', '1', TEST_IMAGE);
        expect(result.status).toBe(200);
        expect(result.body.success).toBe(true);

        // Check rate limit headers
        expect(result.headers['x-ratelimit-limit']).toBe(String(RATE_LIMIT_PER_USER));
        expect(result.headers['x-ratelimit-remaining']).toBe(
          String(RATE_LIMIT_PER_USER - (i + 1))
        );
        expect(result.headers['x-ratelimit-reset']).toBeDefined();

        await waitForSubmissionProcessing();
      }

      // Next submission should be rate limited (429)
      const limitedResult = await submitSolutionApi(request, '2024', 'etap2', '1', TEST_IMAGE);
      expect(limitedResult.status).toBe(429);
      expect(limitedResult.body.error).toContain('limit');

      // Should have Retry-After header
      expect(limitedResult.headers['retry-after']).toBeDefined();
      expect(parseInt(limitedResult.headers['retry-after'])).toBeGreaterThan(0);

      // Rate limit headers should show 0 remaining
      expect(limitedResult.headers['x-ratelimit-remaining']).toBe('0');
    });

    test('rate limit headers show correct values on success', async ({ context }) => {
      await loginAs(context, TEST_USERS.rateLimited2);
      const request = context.request;

      // Reset submissions to ensure clean slate
      await resetUserSubmissions(request);

      // First submission
      const result1 = await submitSolutionApi(request, '2024', 'etap2', '2', TEST_IMAGE);
      expect(result1.status).toBe(200);
      expect(result1.headers['x-ratelimit-limit']).toBe(String(RATE_LIMIT_PER_USER));
      expect(result1.headers['x-ratelimit-remaining']).toBe(String(RATE_LIMIT_PER_USER - 1));

      // Parse reset timestamp
      const resetTimestamp = parseInt(result1.headers['x-ratelimit-reset']);
      expect(resetTimestamp).toBeGreaterThan(Math.floor(Date.now() / 1000));

      await waitForSubmissionProcessing();

      // Second submission
      const result2 = await submitSolutionApi(request, '2024', 'etap2', '2', TEST_IMAGE);
      expect(result2.status).toBe(200);
      expect(result2.headers['x-ratelimit-remaining']).toBe(String(RATE_LIMIT_PER_USER - 2));
    });

    test('per-user limits are independent between users', async ({ context }) => {
      // First user submits up to limit
      await loginAs(context, TEST_USERS.rateLimited3);
      let request = context.request;

      // Reset submissions to ensure clean slate
      await resetUserSubmissions(request);

      for (let i = 0; i < RATE_LIMIT_PER_USER; i++) {
        const result = await submitSolutionApi(request, '2024', 'etap2', '3', TEST_IMAGE);
        expect(result.status).toBe(200);
        await waitForSubmissionProcessing();
      }

      // First user is now rate limited
      const limitedResult = await submitSolutionApi(request, '2024', 'etap2', '3', TEST_IMAGE);
      expect(limitedResult.status).toBe(429);

      // Switch to second rate-limited user (rateLimited4)
      await logout(context);
      await loginAs(context, TEST_USERS.rateLimited4);
      request = context.request;

      // Reset submissions for second user
      await resetUserSubmissions(request);

      // Second user should NOT be rate limited (their own counter is separate)
      const result = await submitSolutionApi(request, '2024', 'etap2', '3', TEST_IMAGE);
      expect(result.status).toBe(200);
      expect(result.headers['x-ratelimit-remaining']).toBe(String(RATE_LIMIT_PER_USER - 1));
    });
  });

  test.describe('Allowlist bypass', () => {
    test('allowlisted user bypasses rate limits', async ({ context }) => {
      // Login as allowlisted user (in ALLOWED_EMAILS)
      await loginAs(context, TEST_USERS.default);
      const request = context.request;

      // Reset submissions to ensure clean slate (not required for allowlisted, but cleaner)
      await resetUserSubmissions(request);

      // Submit more than the per-user limit
      const submissionCount = RATE_LIMIT_PER_USER + 2;
      for (let i = 0; i < submissionCount; i++) {
        const result = await submitSolutionApi(request, '2024', 'etap2', '4', TEST_IMAGE);
        expect(result.status).toBe(200);
        expect(result.body.success).toBe(true);

        // Allowlisted users still get rate limit headers for informational purposes
        expect(result.headers['x-ratelimit-limit']).toBeDefined();

        await waitForSubmissionProcessing();
      }

      // All submissions should succeed (no 429)
    });

    test('rate-limited user blocked while allowlisted user continues', async ({
      context,
      browser,
    }) => {
      // First: Rate-limited user exhausts their limit
      await loginAs(context, TEST_USERS.rateLimited5);
      let request = context.request;

      // Reset submissions to ensure clean slate
      await resetUserSubmissions(request);

      for (let i = 0; i < RATE_LIMIT_PER_USER; i++) {
        await submitSolutionApi(request, '2024', 'etap2', '5', TEST_IMAGE);
        await waitForSubmissionProcessing();
      }

      // Rate-limited user is now blocked
      const blockedResult = await submitSolutionApi(request, '2024', 'etap2', '5', TEST_IMAGE);
      expect(blockedResult.status).toBe(429);

      // Create new context for allowlisted user
      const allowlistedContext = await browser.newContext();
      await loginAs(allowlistedContext, TEST_USERS.default);
      const allowlistedRequest = allowlistedContext.request;

      // Allowlisted user can still submit
      const allowedResult = await submitSolutionApi(
        allowlistedRequest,
        '2024',
        'etap2',
        '5',
        TEST_IMAGE
      );
      expect(allowedResult.status).toBe(200);

      await allowlistedContext.close();
    });
  });

  test.describe('UI rate limit feedback', () => {
    test('shows rate limit error in UI when blocked', async ({ page, context }) => {
      await loginAs(context, TEST_USERS.rateLimited6);
      const request = context.request;

      // Reset submissions to ensure clean slate
      await resetUserSubmissions(request);

      // Exhaust rate limit via API (use task 1 which exists)
      for (let i = 0; i < RATE_LIMIT_PER_USER; i++) {
        await submitSolutionApi(request, '2024', 'etap2', '1', TEST_IMAGE);
        await waitForSubmissionProcessing();
      }

      // Now try via UI (use task 1 which exists)
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Should show rate limit error message (specific Polish text to avoid matching username)
      await expect(
        page.getByText(/dzienny limit zgłoszeń/i).or(page.getByText(/Możesz przesłać więcej/i))
      ).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Rate limit error format', () => {
    test('429 response includes proper error structure', async ({ context }) => {
      await loginAs(context, TEST_USERS.rateLimited);
      const request = context.request;

      // Reset submissions and exhaust the limit
      await resetUserSubmissions(request);
      for (let i = 0; i < RATE_LIMIT_PER_USER; i++) {
        await submitSolutionApi(request, '2024', 'etap2', '1', TEST_IMAGE);
        await waitForSubmissionProcessing();
      }

      // Submit to trigger the 429 response
      const result = await submitSolutionApi(request, '2024', 'etap2', '1', TEST_IMAGE);

      expect(result.status).toBe(429);
      expect(result.body).toHaveProperty('error');
      expect(typeof result.body.error).toBe('string');
      expect(result.body.error.length).toBeGreaterThan(0);

      // Headers should be present
      expect(result.headers['x-ratelimit-limit']).toBeDefined();
      expect(result.headers['x-ratelimit-remaining']).toBe('0');
      expect(result.headers['x-ratelimit-reset']).toBeDefined();
      expect(result.headers['retry-after']).toBeDefined();
    });
  });
});
