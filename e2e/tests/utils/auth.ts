/**
 * Authentication utilities for E2E tests.
 *
 * Creates session cookies to simulate authenticated users without going through OAuth.
 * Uses the same session format as the backend (itsdangerous TimestampSigner).
 */

import { BrowserContext, Page } from '@playwright/test';
import * as crypto from 'crypto';

// IMPORTANT: SESSION_SECRET_KEY must match SESSION_SECRET_KEY in docker-compose.e2e.yml exactly
// If they don't match, session cookies will be rejected as invalid signatures
const SESSION_SECRET_KEY = process.env.E2E_SESSION_SECRET || 'e2e-test-secret-key-for-session-signing-32bytes';
const SESSION_COOKIE_NAME = 'session';

// Test users
export interface TestUser {
  google_sub: string;
  email: string;
  name: string;
  picture: string | null;
  is_group_member: boolean;
}

export const TEST_USERS = {
  // Standard test user with full access
  default: {
    google_sub: 'test-user-sub-123',
    email: 'test-user@example.com',
    name: 'Test User',
    picture: null,
    is_group_member: true,
  } as TestUser,

  // Second test user for cross-user tests
  user2: {
    google_sub: 'test-user-sub-456',
    email: 'test-user-2@example.com',
    name: 'Test User 2',
    picture: null,
    is_group_member: true,
  } as TestUser,

  // Admin user
  admin: {
    google_sub: 'test-admin-sub-789',
    email: 'test-admin@example.com',
    name: 'Test Admin',
    picture: null,
    is_group_member: true,
  } as TestUser,

  // User without group membership (can log in but restricted access)
  restricted: {
    google_sub: 'test-restricted-sub-000',
    email: 'restricted@example.com',
    name: 'Restricted User',
    picture: null,
    is_group_member: false,
  } as TestUser,

  // User subject to rate limits (NOT in ALLOWED_EMAILS)
  // Use for testing rate limiting behavior
  rateLimited: {
    google_sub: 'test-ratelimit-sub-111',
    email: 'ratelimited@example.com',
    name: 'Rate Limited User',
    picture: null,
    is_group_member: true,
  } as TestUser,

  // Second rate-limited user for cross-user rate limit tests
  rateLimited2: {
    google_sub: 'test-ratelimit-sub-222',
    email: 'ratelimited2@example.com',
    name: 'Rate Limited User 2',
    picture: null,
    is_group_member: true,
  } as TestUser,

  // Additional rate-limited users for isolated tests
  rateLimited3: {
    google_sub: 'test-ratelimit-sub-333',
    email: 'ratelimited3@example.com',
    name: 'Rate Limited User 3',
    picture: null,
    is_group_member: true,
  } as TestUser,

  rateLimited4: {
    google_sub: 'test-ratelimit-sub-444',
    email: 'ratelimited4@example.com',
    name: 'Rate Limited User 4',
    picture: null,
    is_group_member: true,
  } as TestUser,

  rateLimited5: {
    google_sub: 'test-ratelimit-sub-555',
    email: 'ratelimited5@example.com',
    name: 'Rate Limited User 5',
    picture: null,
    is_group_member: true,
  } as TestUser,

  rateLimited6: {
    google_sub: 'test-ratelimit-sub-666',
    email: 'ratelimited6@example.com',
    name: 'Rate Limited User 6',
    picture: null,
    is_group_member: true,
  } as TestUser,
};

/**
 * Encode timestamp as itsdangerous does (base64 of packed big-endian uint32).
 */
function encodeTimestamp(timestamp: number): string {
  // Pack as big-endian unsigned 32-bit integer
  const buffer = Buffer.alloc(4);
  buffer.writeUInt32BE(timestamp, 0);
  // URL-safe base64 encode
  return buffer
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/**
 * Create HMAC signature compatible with itsdangerous.
 *
 * itsdangerous uses HMAC-SHA1 with a derived key using "django-concat" method:
 * key = SHA1(salt + "signer" + secret_key)
 * where salt = "itsdangerous.Signer"
 */
function createSignature(data: string, secret: string): string {
  // django-concat key derivation: SHA1(salt + "signer" + secret_key)
  const derivedKey = crypto
    .createHash('sha1')
    .update('itsdangerous.Signersigner' + secret)
    .digest();

  // Create signature of the data
  const signature = crypto
    .createHmac('sha1', derivedKey)
    .update(data)
    .digest('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');

  return signature;
}

/**
 * Create a signed session cookie value.
 *
 * Implements the same signing algorithm as itsdangerous.TimestampSigner:
 * 1. Serialize session data as JSON
 * 2. Base64 encode the JSON
 * 3. Create timestamp in base62 (Unix time)
 * 4. Sign: HMAC-SHA1(derived_key, base64_data + "." + timestamp)
 * 5. Return: base64_data.timestamp.signature
 */
function createSessionCookie(user: TestUser): string {
  // Session data structure (matches Starlette SessionMiddleware)
  const sessionData = {
    user: {
      ...user,
      membership_checked_at: Math.floor(Date.now() / 1000),
    },
  };

  // URL-safe base64 encode the session JSON (matching Starlette's approach)
  // Starlette uses base64.urlsafe_b64encode which replaces + with - and / with _
  const jsonData = JSON.stringify(sessionData);
  const base64Data = Buffer.from(jsonData)
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');

  // Timestamp encoded as itsdangerous does (base64 of packed uint32)
  const timestamp = Math.floor(Date.now() / 1000);
  const timestampEncoded = encodeTimestamp(timestamp);

  // Create the data to sign (data.timestamp)
  const dataToSign = `${base64Data}.${timestampEncoded}`;

  // Create signature
  const signature = createSignature(dataToSign, SESSION_SECRET_KEY);

  // Final cookie value: data.timestamp.signature
  return `${base64Data}.${timestampEncoded}.${signature}`;
}

/**
 * Login as a test user by setting the session cookie.
 */
export async function loginAs(
  context: BrowserContext,
  user: TestUser = TEST_USERS.default
): Promise<void> {
  const cookieValue = createSessionCookie(user);

  await context.addCookies([
    {
      name: SESSION_COOKIE_NAME,
      value: cookieValue,
      domain: 'localhost',
      path: '/',
      httpOnly: true,
      secure: false,
      sameSite: 'Lax',
    },
  ]);
}

/**
 * Login as a test user on a specific page.
 */
export async function loginAsOnPage(
  page: Page,
  user: TestUser = TEST_USERS.default
): Promise<void> {
  await loginAs(page.context(), user);
}

/**
 * Logout by clearing the session cookie.
 */
export async function logout(context: BrowserContext): Promise<void> {
  await context.clearCookies();
}

/**
 * Check if user is logged in.
 */
export async function isLoggedIn(page: Page): Promise<boolean> {
  try {
    const response = await page.request.get('/api/auth/me');
    const data = await response.json();
    return data.is_authenticated === true;
  } catch {
    return false;
  }
}

/**
 * Get current user info.
 */
export async function getCurrentUser(page: Page): Promise<TestUser | null> {
  try {
    const response = await page.request.get('/api/auth/me');
    const data = await response.json();
    if (data.is_authenticated && data.user) {
      return data.user as TestUser;
    }
    return null;
  } catch {
    return null;
  }
}
