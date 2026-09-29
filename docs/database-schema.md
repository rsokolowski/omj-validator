# Database Schema

OMJ Validator uses PostgreSQL for persistent storage of users and submissions.

## Tables

### users

Stores user accounts linked to Google OAuth.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `google_sub` | VARCHAR(255) | PRIMARY KEY | Google's unique user identifier (from OAuth `sub` claim) |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | User's email address |
| `name` | VARCHAR(255) | NULL | User's display name |
| `created_at` | TIMESTAMP | NOT NULL | Account creation time (UTC) |
| `updated_at` | TIMESTAMP | NOT NULL | Last profile update time (UTC) |

**Indexes:**
- `ix_users_email` - UNIQUE index on `email`
- `ix_users_created_at` - Index on `created_at`

### submissions

Stores student solution submissions with AI scoring results.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | VARCHAR(8) | PRIMARY KEY | Short UUID (8 characters) |
| `user_id` | VARCHAR(255) | NOT NULL, FK → users.google_sub | Submitting user |
| `year` | VARCHAR(10) | NULL | Competition year (e.g., "2024"); NULL for a private task |
| `etap` | VARCHAR(10) | NULL | Competition stage ("etap1" or "etap2"); NULL for a private task |
| `task_number` | INTEGER | NULL | Task number (1-6); NULL for a private task |
| `private_task_id` | VARCHAR(12) | NULL, FK → private_tasks.id | Set instead of the OMJ fields for a private task |
| `hints_used` | INTEGER | NOT NULL, default 0 | Private task hints revealed before this submission |
| `timestamp` | TIMESTAMP | NOT NULL | Submission time (UTC) |
| `status` | ENUM | NOT NULL | Processing status (see below) |
| `images` | JSON | NOT NULL | Array of uploaded image paths |
| `solution_text` | TEXT | NULL | Typed solution text with `$LaTeX$`; NULL when the student sent photos only. Immutable after submit |
| `score` | INTEGER | NULL | AI-assigned score (0, 2, 5, or 6) |
| `feedback` | TEXT | NULL | AI-generated feedback text |
| `error_message` | TEXT | NULL | Error details if processing failed |
| `scoring_meta` | JSON | NULL | LLM metadata (model, tokens, timing, etc.) |
| `created_at` | TIMESTAMP | NOT NULL | Row creation time (UTC) |

**Status enum values:**
- `pending` - Uploaded, awaiting processing
- `processing` - Being analyzed by AI
- `completed` - Successfully scored
- `failed` - Processing failed

**Indexes:**
- `ix_submissions_user_id` - Index on `user_id` for user's submissions
- `ix_submissions_user_task` - Composite index on `(user_id, year, etap, task_number)` for progress queries
- `ix_submissions_task` - Composite index on `(year, etap, task_number)` for task statistics

- `ix_submissions_user_private_task` - Composite index on `(user_id, private_task_id)`

**Check constraint** `ck_submissions_task_ref`: either all of `year`, `etap`,
`task_number` are set and `private_task_id` is NULL (OMJ task), or all three are
NULL and `private_task_id` is set (private task). Every OMJ aggregate (progress,
stats) additionally filters `private_task_id IS NULL` explicitly.

**Foreign Keys:**
- `user_id` → `users.google_sub` with `ON DELETE CASCADE`
- `private_task_id` → `private_tasks.id` with `ON DELETE CASCADE`

### private_tasks

Tasks a student added themselves ("Moje zadania"), from a photo or typed in.
Visible only to the owner. Expire `RETENTION_PRIVATE_TASK_MONTHS` after
`last_activity_at`.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | VARCHAR(12) | PRIMARY KEY | `secrets.token_urlsafe(9)` |
| `user_id` | VARCHAR(255) | NOT NULL, FK → users.google_sub (CASCADE) | Owner |
| `title` | VARCHAR(120) | NOT NULL | Title |
| `content` | TEXT | NOT NULL | Statement with `$LaTeX$`, 20–10 000 chars |
| `source_label` | VARCHAR(120) | NULL | e.g. "IKOMJ 4.3" |
| `category` | VARCHAR(20) | NULL | One of the six task categories |
| `difficulty` | INTEGER | NULL | 1–5 |
| `hints` | JSON | NOT NULL | 0–4 progressive hints |
| `hints_revealed` | INTEGER | NOT NULL, default 0 | Highest hint ever revealed |
| `pending_hints_used` | INTEGER | NOT NULL, default 0 | Highest hint revealed since the last submission |
| `source_images` | JSON | NOT NULL | Photos of the problem (`{user}/private/{id}/source/...`) |
| `origin` | VARCHAR(10) | NOT NULL | `photo` or `typed` |
| `extraction_meta` | JSON | NULL | Model / tokens / cost of the creation calls |
| `created_at`, `updated_at` | TIMESTAMP | NOT NULL | |
| `last_activity_at` | TIMESTAMP | NOT NULL, indexed | Create, edit or submission - drives retention |

### ai_usage

One content-free row per non-submission AI call, for the daily limits.
Expires after `RETENTION_AI_USAGE_DAYS`.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | |
| `user_id` | VARCHAR(255) | NOT NULL, FK → users.google_sub (CASCADE) | Caller |
| `kind` | VARCHAR(32) | NOT NULL | `private_extract`, `private_create`, `private_regen` |
| `created_at` | TIMESTAMP | NOT NULL, indexed | |
| `meta` | JSON | NULL | Model, tokens, cost |

`deleted_account_quota` also carries `ai_usage_count` (migration 006), so
erasing an account does not reset these limits either.

## Entity Relationship Diagram

```
┌─────────────────────┐       ┌─────────────────────────┐
│       users         │       │      submissions        │
├─────────────────────┤       ├─────────────────────────┤
│ google_sub (PK)     │──────<│ user_id (FK)            │
│ email               │       │ id (PK)                 │
│ name                │       │ year                    │
│ created_at          │       │ etap                    │
│ updated_at          │       │ task_number             │
└─────────────────────┘       │ private_task_id (FK) ───┼──> private_tasks.id
          │                   │ hints_used              │
          │                   │ timestamp               │
                              │ status                  │
                              │ images                  │
                              │ score                   │
                              │ feedback                │
                              │ error_message           │
                              │ scoring_meta            │
          │                   │ created_at              │
          │                   └─────────────────────────┘
          │
          ├──< private_tasks (user_id)   id, title, content, hints, source_images, ...
          └──< ai_usage (user_id)        kind, created_at, meta
```

## Migrations

Database migrations are managed with Alembic. Migration files are in `alembic/versions/`.

```bash
# Apply all migrations
alembic upgrade head

# Create new migration
alembic revision -m "description"

# Rollback one migration
alembic downgrade -1
```

## Configuration

Set `DATABASE_URL` environment variable:

```bash
# Local development (Docker)
DATABASE_URL=postgresql://omj:omj@localhost:5433/omj

# Production
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

Default (if not set): `postgresql://omj:omj@localhost:5433/omj`
