/**
 * Submission utility functions for E2E tests.
 */

import { Page, expect } from '@playwright/test';

/**
 * Helper to upload files and submit.
 * Handles the React state update race condition by waiting for proper element states.
 *
 * @param page - Playwright page object
 * @param files - Single file path or array of file paths to upload
 * @param options - Optional configuration
 * @param options.skipSubmit - If true, only upload files without clicking submit
 */
export async function uploadAndSubmit(
  page: Page,
  files: string | string[],
  options?: { skipSubmit?: boolean }
) {
  await page.waitForLoadState('networkidle');

  const fileInput = page.locator('input[type="file"]');
  await expect(fileInput).toBeAttached({ timeout: 10000 });
  await fileInput.setInputFiles(files);

  if (!options?.skipSubmit) {
    const submitButton = page.getByRole('button', { name: /prześlij/i });
    await expect(submitButton).toBeEnabled({ timeout: 5000 });
    await submitButton.click();
  }
}
