# E2E Testing for OMJ Validator

Comprehensive end-to-end tests using Playwright that test the entire application stack including frontend, backend, database, and AI integration.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Playwright    │────▶│    Frontend     │────▶│     Backend     │
│    (Tests)      │     │  (Next.js)      │     │    (FastAPI)    │
│  localhost:3200 │     │  :3200 -> :3100 │     │  :8200 -> :8100 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌─────────────────┐     ┌────────▼────────┐
                        │  Fake Gemini    │◀────│   PostgreSQL    │
                        │    API Server   │     │   (Ephemeral)   │
                        │  :8080 internal │     │   :5432 internal│
                        └─────────────────┘     └─────────────────┘
```

### Components

1. **Playwright** - Test runner on host machine
2. **Frontend** (e2e-frontend) - Next.js application
3. **Backend** (e2e-api) - FastAPI server with test configuration
4. **PostgreSQL** (e2e-db) - Ephemeral database (tmpfs, no persistence)
5. **Fake Gemini** (fake-gemini) - Mock Gemini API server

## Quick Start

```bash
# Navigate to e2e directory
cd e2e

# Install dependencies
npm install
npx playwright install chromium

# Start services and run tests
./run-e2e.sh

# Or manually:
docker compose -f ../docker-compose.e2e.yml up -d --build
npm test
```

## Test Commands

```bash
# Run all tests
npm test

# Run with browser visible
npm run test:headed

# Run with Playwright UI
npm run test:ui

# Run specific test file
npx playwright test navigation

# Run specific test
npx playwright test -g "can upload a single image"

# Debug a test
npx playwright test --debug

# View test report
npm run test:report
```

## Docker Commands

```bash
# Start all e2e services
npm run docker:up
# or
docker compose -f ../docker-compose.e2e.yml up -d --build

# Stop and clean up
npm run docker:down
# or
docker compose -f ../docker-compose.e2e.yml down -v

# View logs
npm run docker:logs
# or
docker compose -f ../docker-compose.e2e.yml logs -f

# Restart services
npm run docker:restart
```

## Test Structure

```
e2e/
├── tests/
│   ├── navigation.spec.ts   # Basic navigation, unauthenticated access
│   ├── auth.spec.ts         # Authentication, sessions, user isolation
│   ├── tasks.spec.ts        # Task browsing, metadata, hints
│   ├── submission.spec.ts   # File upload, AI analysis, scoring
│   ├── websocket.spec.ts    # Real-time progress updates
│   └── utils/
│       ├── auth.ts          # Test user session creation
│       └── api.ts           # API helpers, Gemini scenario control
├── fixtures/
│   ├── test-solution.jpg    # Sample submission image
│   ├── test-solution-2.jpg  # Second sample image
│   └── blank-image.jpg      # For error testing
├── fake-gemini/
│   ├── server.py            # Fake Gemini API server
│   ├── Dockerfile
│   └── requirements.txt
├── playwright.config.ts
├── package.json
├── run-e2e.sh
└── README.md
```

## Test Scenarios

### Navigation Tests
- Unauthenticated user can browse tasks
- Authenticated user sees user info
- Breadcrumb navigation works

### Authentication Tests
- Session cookie injection
- User switching
- Group membership restrictions
- Cross-user data isolation

### Task Tests
- Years and etaps listing
- Task cards with metadata
- LaTeX rendering
- Hints reveal
- PDF links

### Submission Tests
- Single/multiple image upload
- Progress updates display
- Different score scenarios (0, 2, 5, 6 points)
- Error handling (timeout, quota, safety)
- Submission history

### WebSocket Tests
- Status message reception
- Completed message with score/feedback
- Error message handling

## Fake Gemini API

The fake Gemini server mimics the Google Gemini API and allows controlling responses for testing.

### Available Scenarios

| Scenario | Description |
|----------|-------------|
| `success_score_6` | Perfect score (6 points) |
| `success_score_5` | Good score (5 points) |
| `success_score_2` | Partial score (2 points) |
| `success_score_0` | Zero score |
| `error_timeout` | Simulates timeout |
| `error_quota` | Quota exceeded error |
| `error_safety` | Safety filter blocked |
| `error_invalid_key` | Invalid API key error |
| `slow_response` | Slow but successful (for loading state tests) |

### Controlling Scenarios

From tests:
```typescript
import { setGeminiScenario, resetGemini } from './utils/api';

// Set default scenario
await setGeminiScenario(request, 'success_score_0');

// Set task-specific scenario
await setGeminiScenario(request, 'error_timeout', '2024_etap2_1');

// Reset to defaults
await resetGemini(request);
```

Via API (for debugging):
```bash
# Set default scenario
curl -X POST "http://localhost:8080/config/scenario?scenario=success_score_0"

# Set task-specific scenario
curl -X POST "http://localhost:8080/config/scenario?scenario=error_timeout&task_key=2024_etap2_1"

# View current config
curl "http://localhost:8080/config"

# Reset
curl -X POST "http://localhost:8080/config/reset"
```

## Authentication in Tests

Tests use session cookie injection to simulate authenticated users without going through OAuth.

### Test Users

| User | Email | Group Member | Purpose |
|------|-------|--------------|---------|
| default | test-user@example.com | Yes | Standard testing |
| user2 | test-user-2@example.com | Yes | Cross-user tests |
| admin | test-admin@example.com | Yes | Admin testing |
| restricted | restricted@example.com | No | Access restriction tests |

### Usage

```typescript
import { loginAs, logout, TEST_USERS } from './utils/auth';

test.beforeEach(async ({ context }) => {
  await loginAs(context, TEST_USERS.default);
});

test('cross-user isolation', async ({ context }) => {
  await logout(context);
  await loginAs(context, TEST_USERS.user2);
  // Test as second user
});
```

## Environment Variables

### E2E Test Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `E2E_BASE_URL` | `http://localhost:3200` | Frontend URL |
| `E2E_API_URL` | `http://localhost:8200` | Backend API URL |
| `E2E_FAKE_GEMINI_URL` | `http://localhost:8080` | Fake Gemini URL |

### Fake Gemini Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FAKE_GEMINI_SCENARIO` | `success_score_6` | Default response scenario |
| `FAKE_GEMINI_DELAY_MS` | `100` | Base response delay |
| `FAKE_GEMINI_SLOW_DELAY_MS` | `5000` | Slow scenario delay |
| `FAKE_GEMINI_STREAM_DELAY_MS` | `50` | Streaming chunk delay |
| `FAKE_GEMINI_TASK_SCENARIOS` | `{}` | JSON map of task-specific scenarios |

## Troubleshooting

### Services not starting

```bash
# Check container logs
docker compose -f ../docker-compose.e2e.yml logs e2e-api
docker compose -f ../docker-compose.e2e.yml logs e2e-frontend

# Check container health
docker compose -f ../docker-compose.e2e.yml ps

# Rebuild from scratch
docker compose -f ../docker-compose.e2e.yml down -v
docker compose -f ../docker-compose.e2e.yml build --no-cache
docker compose -f ../docker-compose.e2e.yml up -d
```

### Tests timing out

```bash
# Increase timeout in playwright.config.ts
timeout: 120000,

# Run with extended timeout
npx playwright test --timeout=120000
```

### Authentication issues

The session cookie format must match the backend's `itsdangerous.TimestampSigner` format. If tests fail with 401 errors:

1. Verify `SESSION_SECRET_KEY` matches in `docker-compose.e2e.yml` and `auth.ts`
2. Check that `ALLOWED_EMAILS` includes test user emails
3. Verify cookies are being set (check browser dev tools)

### WebSocket not connecting

```bash
# Check backend WebSocket endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  http://localhost:8200/ws/submissions/test
```

## Adding New Tests

1. Create new spec file in `tests/` directory
2. Import utilities from `utils/auth.ts` and `utils/api.ts`
3. Use `test.beforeEach` to set up authentication and Gemini scenarios
4. Use `test.afterEach` to clean up Gemini state
5. Follow existing test patterns for consistency

Example:
```typescript
import { test, expect } from '@playwright/test';
import { loginAs, TEST_USERS } from './utils/auth';
import { setGeminiScenario, resetGemini } from './utils/api';

test.describe('My Feature', () => {
  test.beforeEach(async ({ context, request }) => {
    await loginAs(context, TEST_USERS.default);
    await resetGemini(request);
  });

  test('does something', async ({ page }) => {
    await page.goto('/some-page');
    await expect(page.getByText('Expected')).toBeVisible();
  });
});
```

## CI/CD Integration

For running in CI, set the environment to start services automatically:

```yaml
# GitHub Actions example
- name: Run E2E tests
  run: |
    cd e2e
    npm ci
    npx playwright install chromium
    docker compose -f ../docker-compose.e2e.yml up -d --build
    npx playwright test
    docker compose -f ../docker-compose.e2e.yml down -v
```
