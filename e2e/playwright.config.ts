import { defineConfig, devices } from '@playwright/test';

/**
 * E2E Test Configuration for OMJ Validator
 *
 * Tests run against containerized services:
 * - Frontend: http://localhost:3200
 * - Backend API: http://localhost:8200
 * - Fake Gemini: http://localhost:8080 (internal only)
 */

export default defineConfig({
  testDir: './tests',
  // Sequential execution ensures consistent fake Gemini state between tests.
  // Tests configure per-task scenarios via API, and parallel execution would cause race conditions.
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],

  use: {
    // Base URL for frontend
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3200',

    // Collect trace on first retry
    trace: 'on-first-retry',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video on failure
    video: 'on-first-retry',

    // Timeout for actions
    actionTimeout: 10000,

    // Navigation timeout
    navigationTimeout: 30000,
  },

  // Global timeout per test
  timeout: 60000,

  // Expect timeout
  expect: {
    timeout: 10000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Run docker compose before tests (optional - can also run manually)
  // Uncomment to auto-start services
  // webServer: {
  //   command: 'docker compose -f ../docker-compose.e2e.yml up -d --build && sleep 10',
  //   url: 'http://localhost:3200',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120000,
  // },
});
