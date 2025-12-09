/**
 * API utilities for E2E tests.
 *
 * Provides helpers for interacting with the backend API and fake Gemini server.
 */

import { APIRequestContext } from '@playwright/test';

// API endpoints
const API_BASE_URL = process.env.E2E_API_URL || 'http://localhost:8200';
const FAKE_GEMINI_URL = process.env.E2E_FAKE_GEMINI_URL || 'http://localhost:8080';

export type GeminiScenario =
  | 'success_score_6'
  | 'success_score_5'
  | 'success_score_2'
  | 'success_score_0'
  | 'error_timeout'
  | 'error_quota'
  | 'error_safety'
  | 'error_invalid_key'
  | 'slow_response';

/**
 * Set the fake Gemini server scenario.
 */
export async function setGeminiScenario(
  request: APIRequestContext,
  scenario: GeminiScenario,
  taskKey?: string
): Promise<void> {
  const params = new URLSearchParams();
  params.set('scenario', scenario);
  if (taskKey) {
    params.set('task_key', taskKey);
  }

  const response = await request.post(`${FAKE_GEMINI_URL}/config/scenario?${params.toString()}`);
  if (!response.ok()) {
    throw new Error(`Failed to set Gemini scenario: ${await response.text()}`);
  }
}

/**
 * Clear a task-specific Gemini scenario.
 */
export async function clearGeminiTaskScenario(
  request: APIRequestContext,
  taskKey: string
): Promise<void> {
  const response = await request.delete(`${FAKE_GEMINI_URL}/config/scenario/${taskKey}`);
  if (!response.ok()) {
    throw new Error(`Failed to clear Gemini scenario: ${await response.text()}`);
  }
}

/**
 * Reset the fake Gemini server to default configuration.
 */
export async function resetGemini(request: APIRequestContext): Promise<void> {
  const response = await request.post(`${FAKE_GEMINI_URL}/config/reset`);
  if (!response.ok()) {
    throw new Error(`Failed to reset Gemini: ${await response.text()}`);
  }
}

/**
 * Get current fake Gemini configuration.
 */
export async function getGeminiConfig(request: APIRequestContext): Promise<{
  default_scenario: string;
  task_scenarios: Record<string, string>;
  stored_files_count: number;
}> {
  const response = await request.get(`${FAKE_GEMINI_URL}/config`);
  if (!response.ok()) {
    throw new Error(`Failed to get Gemini config: ${await response.text()}`);
  }
  return response.json();
}

/**
 * Wait for the backend API to be healthy.
 */
export async function waitForApi(
  request: APIRequestContext,
  timeoutMs: number = 30000
): Promise<boolean> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    try {
      const response = await request.get(`${API_BASE_URL}/health`);
      if (response.ok()) {
        return true;
      }
    } catch {
      // Continue waiting
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  return false;
}

/**
 * Wait for the fake Gemini server to be healthy.
 */
export async function waitForFakeGemini(
  request: APIRequestContext,
  timeoutMs: number = 30000
): Promise<boolean> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    try {
      const response = await request.get(`${FAKE_GEMINI_URL}/health`);
      if (response.ok()) {
        return true;
      }
    } catch {
      // Continue waiting
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  return false;
}

/**
 * Create a test user in the database via direct API call.
 */
export async function ensureTestUser(
  request: APIRequestContext,
  user: { google_sub: string; email: string; name: string }
): Promise<void> {
  // The user will be created automatically when they first access the API
  // with a valid session cookie. This function is a placeholder for future
  // direct database seeding if needed.
}

/**
 * Get available years from the API.
 */
export async function getYears(request: APIRequestContext): Promise<string[]> {
  const response = await request.get(`${API_BASE_URL}/api/years`);
  if (!response.ok()) {
    throw new Error(`Failed to get years: ${await response.text()}`);
  }
  const data = await response.json();
  return data.years || [];
}

/**
 * Get tasks for a specific year and etap.
 */
export async function getTasks(
  request: APIRequestContext,
  year: string,
  etap: string
): Promise<any[]> {
  const response = await request.get(`${API_BASE_URL}/api/years/${year}/${etap}`);
  if (!response.ok()) {
    throw new Error(`Failed to get tasks: ${await response.text()}`);
  }
  const data = await response.json();
  return data.tasks || [];
}

/**
 * Get task detail.
 */
export async function getTask(
  request: APIRequestContext,
  year: string,
  etap: string,
  num: number
): Promise<any> {
  const response = await request.get(`${API_BASE_URL}/api/task/${year}/${etap}/${num}`);
  if (!response.ok()) {
    throw new Error(`Failed to get task: ${await response.text()}`);
  }
  return response.json();
}
