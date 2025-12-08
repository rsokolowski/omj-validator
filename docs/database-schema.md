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
| `year` | VARCHAR(10) | NOT NULL | Competition year (e.g., "2024") |
| `etap` | VARCHAR(10) | NOT NULL | Competition stage ("etap1" or "etap2") |
| `task_number` | INTEGER | NOT NULL | Task number (1-6) |
| `timestamp` | TIMESTAMP | NOT NULL | Submission time (UTC) |
| `status` | ENUM | NOT NULL | Processing status (see below) |
| `images` | JSON | NOT NULL | Array of uploaded image paths |
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

**Foreign Keys:**
- `user_id` → `users.google_sub` with `ON DELETE CASCADE`

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
└─────────────────────┘       │ timestamp               │
                              │ status                  │
                              │ images                  │
                              │ score                   │
                              │ feedback                │
                              │ error_message           │
                              │ scoring_meta            │
                              │ created_at              │
                              └─────────────────────────┘
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

# Production (Render, etc.)
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

Default (if not set): `postgresql://omj:omj@localhost:5433/omj`
