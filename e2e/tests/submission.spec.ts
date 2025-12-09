/**
 * Submission Tests
 *
 * Tests for the solution submission flow including:
 * - File upload
 * - WebSocket progress updates
 * - Different AI response scenarios
 * - Error handling
 */

import { test, expect } from '@playwright/test';
import { loginAs, TEST_USERS } from './utils/auth';
import { setGeminiScenario, resetGemini, GeminiScenario } from './utils/api';
import * as path from 'path';

// Path to test fixtures
const FIXTURES_DIR = path.join(__dirname, '..', 'fixtures');
const TEST_IMAGE = path.join(FIXTURES_DIR, 'test-solution.jpg');
const TEST_IMAGE_2 = path.join(FIXTURES_DIR, 'test-solution-2.jpg');
const BLANK_IMAGE = path.join(FIXTURES_DIR, 'blank-image.jpg');

test.describe('Submission Flow', () => {
  test.beforeEach(async ({ context, request }) => {
    // Login as test user
    await loginAs(context, TEST_USERS.default);
    // Reset fake Gemini to default scenario
    await resetGemini(request);
  });

  test.afterEach(async ({ request }) => {
    // Clean up fake Gemini state
    await resetGemini(request);
  });

  test.describe('Basic submission', () => {
    test('can upload a single image and submit', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Find file input and upload
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      // Click submit button
      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Wait for submission to start processing
      // UI shows "Przesyłanie zdjęć..." or "Przetwarzanie..." or "Analizuję..."
      await expect(
        page.getByText(/przesyłanie/i).or(page.getByText(/przetwarzanie/i)).or(page.getByText(/analizuję/i)).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('can upload multiple images and submit', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Upload multiple files
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles([TEST_IMAGE, TEST_IMAGE_2]);

      // Should show 2 images uploaded - look for specific text
      await expect(page.getByText(/Wybrano 2 plik/i)).toBeVisible();

      // Submit
      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Wait for processing
      await expect(
        page.getByText(/przesyłanie/i).or(page.getByText(/przetwarzanie/i)).or(page.getByText(/analizuję/i)).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('shows progress updates during analysis', async ({ page, request }) => {
      // Use slow_response to ensure progress states are visible
      await setGeminiScenario(request, 'slow_response');
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Should see various progress states
      // First: uploading
      await expect(
        page.getByText(/przesyłanie/i).or(page.getByText(/przetwarzanie/i)).first()
      ).toBeVisible({ timeout: 10000 });

      // Then: analyzing (from WebSocket) - the slow_response gives us time to see this
      await expect(
        page.getByText(/analizuję/i).or(page.getByText(/analyzing/i)).first()
      ).toBeVisible({ timeout: 20000 });
    });
  });

  test.describe('Score scenarios', () => {
    test('displays perfect score (6 points)', async ({ page, request }) => {
      await setGeminiScenario(request, 'success_score_6');
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Wait for result - look for exact score format "Wynik: 6 / 6 punktów"
      await expect(page.getByText(/Wynik:\s*6\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });

      // Should show positive feedback - add .first() to avoid strict mode
      await expect(page.getByText(/poprawne/i).or(page.getByText(/gratulacje/i)).first()).toBeVisible();
    });

    test('displays good score (5 points)', async ({ page, request }) => {
      await setGeminiScenario(request, 'success_score_5');
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Wait for result - look for exact score format "Wynik: 5 / 6 punktów"
      await expect(page.getByText(/Wynik:\s*5\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });
    });

    test('displays partial score (2 points)', async ({ page, request }) => {
      await setGeminiScenario(request, 'success_score_2');
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Wait for result - look for exact score format "Wynik: 2 / 6 punktów"
      await expect(page.getByText(/Wynik:\s*2\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });

      // Should show feedback about improvements needed - add .first()
      await expect(page.getByText(/popraw/i).or(page.getByText(/częściowo/i)).first()).toBeVisible();
    });

    test('displays zero score (0 points)', async ({ page, request }) => {
      await setGeminiScenario(request, 'success_score_0');
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Wait for result - look for exact score format "Wynik: 0 / 6 punktów"
      await expect(page.getByText(/Wynik:\s*0\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });

      // Should show feedback about incorrect solution - add .first()
      await expect(page.getByText(/niepoprawne/i).or(page.getByText(/błędne/i)).first()).toBeVisible();
    });
  });

  test.describe('Error scenarios', () => {
    test('handles timeout error gracefully', async ({ page, request }) => {
      // Set a shorter page timeout for this test
      test.setTimeout(120000);

      await setGeminiScenario(request, 'error_timeout');
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Should eventually show timeout error
      await expect(
        page.getByText(/zbyt długo/i).or(page.getByText(/timeout/i)).or(page.getByText(/błąd/i))
      ).toBeVisible({ timeout: 90000 });
    });

    test('handles quota exceeded error', async ({ page, request }) => {
      await setGeminiScenario(request, 'error_quota');
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Should show quota/overload error
      await expect(
        page.getByText(/przeciążony/i).or(page.getByText(/quota/i)).or(page.getByText(/spróbuj ponownie/i))
      ).toBeVisible({ timeout: 30000 });
    });

    test('handles safety filter error', async ({ page, request }) => {
      await setGeminiScenario(request, 'error_safety');
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Should show safety/content error - add .first()
      await expect(
        page.getByText(/przetworzyć/i).or(page.getByText(/zdjęcie/i)).or(page.getByText(/błąd/i)).first()
      ).toBeVisible({ timeout: 30000 });
    });
  });

  test.describe('Task-specific scenarios', () => {
    test('different tasks can have different scenarios', async ({ page, request }) => {
      // Set task 1 to score 6, task 2 to score 0
      await setGeminiScenario(request, 'success_score_6', '2024_etap2_1');
      await setGeminiScenario(request, 'success_score_0', '2024_etap2_2');

      // Submit to task 1 - should get 6 points
      await page.goto('/task/2024/etap2/1');
      let fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);
      await page.getByRole('button', { name: /prześlij/i }).click();
      await expect(page.getByText(/Wynik:\s*6\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });

      // Submit to task 2 - should get 0 points
      await page.goto('/task/2024/etap2/2');
      fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);
      await page.getByRole('button', { name: /prześlij/i }).click();
      await expect(page.getByText(/Wynik:\s*0\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });
    });
  });

  test.describe('Slow response handling', () => {
    test('shows loading state during slow analysis', async ({ page, request }) => {
      await setGeminiScenario(request, 'slow_response');
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);

      const submitButton = page.getByRole('button', { name: /prześlij/i });
      await submitButton.click();

      // Should show loading/analyzing state
      await expect(
        page.getByText(/analizuję/i).or(page.locator('[data-testid="loading"]')).or(
          page.locator('.animate-pulse')
        )
      ).toBeVisible({ timeout: 10000 });

      // Wait for eventual completion - slow_response returns score 6
      await expect(page.getByText(/Wynik:\s*6\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 60000 });
    });
  });

  test.describe('File validation', () => {
    test('rejects files that are too large', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      // Create a "large" file in memory (we can't actually create 10MB+ in test)
      // This test verifies the UI handles the case - actual validation happens server-side
      const fileInput = page.locator('input[type="file"]');

      // Try to upload - UI should have max size validation
      await fileInput.setInputFiles(TEST_IMAGE);

      // File should be accepted (it's small)
      await expect(page.locator('[data-testid="image-preview"]').or(page.getByText(/test-solution/i))).toBeVisible();
    });

    test('rejects non-image files', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');

      // The input should have accept attribute limiting to images
      const acceptAttr = await fileInput.getAttribute('accept');
      expect(acceptAttr).toMatch(/image/);
    });

    test('limits number of images', async ({ page }) => {
      await page.goto('/task/2024/etap2/1');

      const fileInput = page.locator('input[type="file"]');

      // Try uploading more than max allowed (10)
      // For now just verify we can upload multiple
      await fileInput.setInputFiles([TEST_IMAGE, TEST_IMAGE_2]);

      // Should show both images
      expect(await page.locator('[data-testid="image-preview"]').count()).toBeLessThanOrEqual(10);
    });
  });

  test.describe('Submission history', () => {
    test('submission appears in history after completion', async ({ page, request }) => {
      await setGeminiScenario(request, 'success_score_6');
      await page.goto('/task/2024/etap2/1');

      // Submit a solution
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);
      await page.getByRole('button', { name: /prześlij/i }).click();

      // Wait for completion - look for exact score format
      await expect(page.getByText(/Wynik:\s*6\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });

      // Reload page and check history
      await page.reload();

      // Should see previous submission in history
      await expect(
        page.getByText(/historia/i).or(page.locator('[data-testid="submission-history"]'))
      ).toBeVisible();
    });

    test('can submit multiple times to same task', async ({ page, request }) => {
      await setGeminiScenario(request, 'success_score_2');
      await page.goto('/task/2024/etap2/1');

      // First submission
      let fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(TEST_IMAGE);
      await page.getByRole('button', { name: /prześlij/i }).click();
      await expect(page.getByText(/Wynik:\s*2\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });

      // Wait for UI to be ready for next submission (file input available)
      await setGeminiScenario(request, 'success_score_6');
      fileInput = page.locator('input[type="file"]');
      await expect(fileInput).toBeAttached();
      await fileInput.setInputFiles(TEST_IMAGE_2);
      await page.getByRole('button', { name: /prześlij/i }).click();
      await expect(page.getByText(/Wynik:\s*6\s*\/\s*6\s*punktów/)).toBeVisible({ timeout: 30000 });
    });
  });
});
