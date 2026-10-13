# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OMJ Validator - a web application for validating solutions to Polish Junior Mathematical Olympiad (Olimpiada Matematyczna Juniorów) competition problems. Students upload photos of their handwritten solutions, which are analyzed by AI (Gemini) against official task PDFs and scoring criteria.

**Architecture**: Monorepo with Next.js frontend and FastAPI backend, deployed as separate services.

## Important Rules

**NEVER discard uncommitted changes without explicit user permission.** Do not run commands like `git checkout <file>`, `git restore <file>`, or `git reset --hard` on files with uncommitted changes unless the user explicitly asks you to discard those changes. Always ask first if you see uncommitted changes that seem unrelated to the current task.

**NEVER commit OMJ competition material.** The task PDFs (`tasks/`) and the task statements transcribed from them (`data/task_content/`) belong to Stowarzyszenie na rzecz Edukacji Matematycznej, not to this project. Both are git-ignored and must stay that way - never `git add -f` them, never paste a task statement into a tracked file, and never add `title`/`content` back into `data/tasks/**/task_*.json`. What IS ours and stays MIT-licensed: the code and the generated task metadata (difficulty, categories, hints, prerequisites, skills). See [NOTICE](NOTICE); `tests/test_task_content_split.py` guards the rule.

## Development Commands

```bash
# Start full development environment (PostgreSQL + backend + frontend via Docker)
./start.sh

# Start only backend (PostgreSQL + FastAPI on port 8000)
./start.sh --backend-only

# Start only frontend (Next.js on port 3000, requires backend running)
./start.sh --frontend-only

# Force rebuild of Docker images
./start.sh --build

# Stop all services
docker compose down

# Stop and delete all data (including database)
docker compose down -v

# View logs
docker compose logs -f            # All services
docker compose logs -f api        # Backend only
docker compose logs -f frontend   # Frontend only

# Download task PDFs from omj.edu.pl (run outside Docker; idempotent)
# Required on a fresh clone - the PDFs are not in the repository.
python download_tasks.py --all-etaps          # Everything (~170 PDFs, ~80 MB)
python download_tasks.py --year 2026          # One edition
python download_tasks.py --all-etaps --force  # Re-download existing files

# Generate task statements (title + content) from the PDFs (uses Claude CLI).
# Optional - without it the app shows metadata plus a link to the task PDF.
# Writes data/task_content/{year}/{etap}.json, which is git-ignored.
python fix_latex_content.py 2024 etap1        # Specific year/etap
python fix_latex_content.py --all --skip-existing   # Only what is missing

# One-shot: move statements out of tracked metadata files (already applied)
python scripts/split_task_content.py --dry-run

# Generate/update task metadata (difficulty, categories, hints)
python populate_metadata.py                    # Uses Claude CLI
python populate_metadata.py --year 2024 --force
python populate_metadata_gemini.py             # Alternative using Gemini API

# Delete data past its retention period (RODO art. 5(1)(e))
./venv/bin/python scripts/purge_expired_data.py --dry-run   # report only
./venv/bin/python scripts/purge_expired_data.py             # actually delete
```

**Note**: Development uses Docker Compose for the full stack. Google OAuth is disabled by default (`AUTH_DISABLED=true`) since it requires an external URL for callbacks.

```bash
# Render every e-mail template with sample data -> tmp/email-previews/*.html
./venv/bin/python scripts/render_email_previews.py
```

## Architecture

### Project Structure

```
omj-validator/
├── frontend/                # Next.js 16 frontend (TypeScript, React 19)
│   ├── src/
│   │   ├── app/            # Next.js App Router pages
│   │   ├── components/     # React components
│   │   └── lib/            # API client, hooks, types, utils
│   ├── next.config.ts      # API proxy rewrites to FastAPI
│   └── package.json
├── app/                     # FastAPI backend (Python)
│   ├── main.py             # Routes (JSON APIs + legacy HTML)
│   ├── config.py           # Pydantic settings
│   ├── auth.py             # Sessions, current_account, require_active_user (app-level guard)
│   ├── oauth.py            # Google OAuth (Authlib)
│   ├── accounts/           # Registration, login/password, age step, parent consent, parent page, reset
│   │   ├── routes.py       # /api/auth/*, /api/account/*, /api/parent/*, /api/dev/outbox
│   │   ├── service.py      # Users, parents, consents, e-mailed tokens, e-mail limits, login lockout
│   │   ├── age.py          # Year-of-birth arithmetic (16 this year -> follow-up question)
│   │   └── passwords.py    # Login/password rules, argon2id, data/common-passwords.txt
│   ├── email/              # send_email (console | resend) + Jinja templates in templates/email/
│   ├── groups.py           # Access control (email allowlist or Google Groups)
│   ├── storage.py          # Task loading (dir scan + LRU cache)
│   ├── models.py           # Pydantic models
│   ├── progress.py         # Task progression graph logic
│   ├── uploads.py          # Photo saving + sanitizing (EXIF/GPS strip), shared by all uploads
│   ├── rate_limits.py      # Rolling 24h limits (submissions; AI calls via ai_usage)
│   ├── retention.py        # Data retention + account erasure (RODO)
│   ├── private_tasks/      # "Moje zadania": router (routes.py) + files/limits (service.py)
│   ├── patterns/           # "Wzorce": routes, service, srs.py (scheduling), linking.py
│   ├── db/                 # Database layer
│   │   ├── session.py      # SQLAlchemy engine, get_db dependency
│   │   ├── models.py       # ORM: UserDB, SubmissionDB, PrivateTaskDB, AIUsageDB, ...
│   │   ├── repositories.py # Data access layer
│   │   └── private_tasks.py # PrivateTaskRepository, AIUsageRepository
│   └── ai/
│       ├── protocol.py     # AIProvider interface
│       ├── factory.py      # Provider factory: active model -> cached provider (+ GDPR approval gate),
│       │                   # error classes (AIContentBlockedError, AIUnavailableError, AISpendLimitError)
│       ├── failover.py     # FailoverProvider + circuit breaker (backup model on availability errors)
│       ├── spend.py        # Daily AI spend cap (AI_DAILY_SPEND_LIMIT_USD)
│       ├── models_catalog.py # Selectable models per provider, prices, estimate_cost
│       ├── config_store.py # Active provider/model: app_settings row, else env default
│       ├── requests.py     # Provider-neutral request text (prompt parity across providers)
│       ├── schemas.py      # Provider-neutral JSON schemas for grading responses
│       ├── parsing.py      # JSON parsing, OMJ score normalization
│       ├── private_parsing.py # Validation of extraction / hint responses
│       └── providers/
│           ├── gemini.py   # Gemini API integration
│           └── anthropic.py # Claude (Anthropic Messages API) integration
├── data/                    # Runtime data
│   ├── tasks/              # Task metadata JSON files (tracked, MIT)
│   ├── task_content/       # Task statements from the PDFs (git-ignored, generated)
│   └── uploads/            # User-submitted images
├── tasks/                   # Downloaded task PDFs 2005-2025 (git-ignored)
├── task_content.py          # Statement file access for the root-level scripts
├── NOTICE                   # What the MIT licence covers and what it does not
├── alembic/                # Database migrations
├── prompts/                # AI prompts for analysis
├── docker-compose.yml      # Development Docker Compose (full stack)
├── docker-compose.prod.yml # Production Docker Compose
├── Dockerfile              # Production backend Dockerfile
├── Dockerfile.dev          # Development backend Dockerfile (hot-reload)
└── start.sh                # Development startup script
```

### Frontend (Next.js)

**Tech stack**: Next.js 16, React 19, TypeScript, Material-UI v7, Tailwind CSS, KaTeX, Cytoscape.js, SWR

**Key directories**:
```
frontend/src/
├── app/                              # App Router pages
│   ├── layout.tsx                    # Root layout with MUI ThemeProvider
│   ├── years/page.tsx               # List all years
│   ├── years/[year]/page.tsx        # List etaps for year
│   ├── years/[year]/[etap]/page.tsx # Task list for etap
│   ├── task/[year]/[etap]/[num]/page.tsx  # Task detail with submission
│   ├── progress/page.tsx            # Task progression graph
│   ├── admin/                       # Admin: submissions, settings (AI provider/model switch)
│   ├── moje-zadania/                # Private tasks: list, nowe (add), [id] (task)
│   ├── wzorce/                      # Patterns: list, nowy, [id], powtorka (review)
│   ├── login/page.tsx               # Google button + login/password form
│   ├── rejestracja/                 # Registration stepper (year of birth, method, parent e-mail)
│   ├── konto/oczekuje, konto/uzupelnij  # Waiting for parent consent; year of birth for old accounts
│   ├── rodzic/, rodzic/zgoda/       # Parent page (token from e-mail) and the consent page
│   └── reset-hasla/, reset-hasla/nowe/  # Password reset (link goes to the parent)
├── components/
│   ├── layout/                      # Header, Footer, Breadcrumb
│   ├── task/                        # TaskCard, SubmitSection, SolutionTextEditor, FormulaDialog (MathLive), DrawingDialog (Excalidraw), HintsSection
│   ├── progress/                    # ProgressGraph, CategoryFilter
│   ├── private-tasks/               # NewPrivateTaskForm, ProblemEditor, hints, actions
│   └── ui/                          # DifficultyStars, CategoryBadge, MathContent
└── lib/
    ├── api/client.ts                # Fetch helpers
    ├── hooks/useAuth.ts             # Auth state hook
    └── types/index.ts               # TypeScript types (match FastAPI models)
```

**Security headers**: CSP, HSTS, X-Frame-Options, nosniff and Permissions-Policy are set by
`nginx.prod.conf` (production only); a new third-party origin in the frontend needs a CSP change
there. Unsafe-method requests from another origin are refused by `app/csrf.py`.

**API proxy**: `next.config.ts` rewrites `/api/*`, `/auth/*`, `/login/*`, `/logout`, `/pdf/*`, `/uploads/*` to FastAPI backend.

### Backend (FastAPI)

**JSON API routes** (used by Next.js frontend):
```
GET  /api/auth/me                    # Current user + account {status, needs_profile, login_method, pending}
GET  /api/years                      # All years
GET  /api/years/{year}               # Etaps for year
GET  /api/years/{year}/{etap}        # Tasks for etap
GET  /api/task/{year}/{etap}/{num}   # Task detail
GET  /api/task/{year}/{etap}/{num}/history  # Submission history
GET  /api/progress/data              # Task progression data
POST /task/{year}/{etap}/{num}/submit       # Submit solution: images (photos/drawings) and/or solution_text
POST /api/account/delete             # Erase own account + submissions + photos (RODO art. 17)

# Accounts (app/accounts/routes.py). Every write route of the app runs require_active_user:
# a pending_parent account or one without birth_year gets 403 {detail, code} unless the
# endpoint is marked @allow_inactive_account (tests/test_accounts_guard.py lists them)
POST /api/auth/login                 # login + password (+ remember); lockout 5 per (login, known device | IP); unknown devices also 20/IP, 10/login per 15 min (signed omj_device cookie)
GET  /api/auth/login-available       # "Ten login jest zajęty" check (rate-limited)
POST /api/auth/register/login        # Login account: always pending_parent, consent e-mail to parent; new logins have no dots
POST /api/auth/register/google       # Answers before Google (-> /login/google?register=1) or after (pending_google)
                                     # Both registrations: Turnstile token (turnstile_token) + 30 accounts/IP/24 h (in memory)
GET  /api/auth/register/state        # Google identity waiting for registration (10 min, consumed on use) + turnstile_site_key
POST /api/auth/profile               # Year of birth for accounts created before the age step
POST /api/account/consent/resend     # Pending screen: resend (60 s cooldown, 3/account, 5/parent per 24 h)
POST /api/account/parent-email       # Pending screen: change the parent address (old links expire)
POST /api/parent/consent/view        # Consent page data (token in the body - never in a query string)
POST /api/parent/consent             # {token, decision: accept|decline}; decline erases the account
POST /api/parent/consent/resend      # New link from an expired one (account still pending)
POST /api/parent/children            # Parent page: children of this parent address
POST /api/parent/children/{id}/delete|password  # Erase a child / set a new password (bumps session_version)
POST /api/parent/request-link        # E-mail a parent-page link (same answer for unknown addresses)
POST /api/auth/password-reset/request|check|confirm  # Reset link goes to the parent
GET  /api/dev/outbox                 # Console-backend e-mails; only E2E_MODE + EMAIL_BACKEND=console + auth on

# Private tasks ("Moje zadania") - owner only, someone else's id is a 404
POST   /api/private-tasks/extract            # Photos -> draft {draft_id, problems[]} (AI)
POST   /api/private-tasks                    # Create from draft selection or typed text (AI hints)
GET    /api/private-tasks                    # List own tasks
GET    /api/private-tasks/{id}               # Detail + history; only revealed hints
PATCH  /api/private-tasks/{id}               # Edit
DELETE /api/private-tasks/{id}               # Task + submissions + photos
POST   /api/private-tasks/{id}/hints/{n}     # Reveal hint n (in order)
POST   /api/private-tasks/{id}/regenerate-hints
POST   /api/private-tasks/{id}/submit        # Solution photos and/or solution_text -> grading over the WebSocket

# Patterns ("Wzorce") - owner only, someone else's id is a 404
POST   /api/patterns/refine                  # Guided refine round (AI): 2-3 versions, verdict, questions
POST   /api/patterns/suggest                 # Patterns worth remembering from a graded submission (AI)
POST   /api/patterns                         # Save (+ source task link, round history)
GET    /api/patterns                         # List (?category, archived, task_key, private_task_id)
GET    /api/patterns/queue                   # Due today, categories interleaved
GET    /api/patterns/{id}                    # Detail + links + reviews
PATCH  /api/patterns/{id}                    # Edit, append a round, pause/resume
DELETE /api/patterns/{id}
POST   /api/patterns/{id}/suggest-links      # AI picks OMJ tasks from server-chosen candidates
POST   /api/patterns/{id}/links              # Link a task by hand; PATCH/DELETE .../links/{link_id}
POST   /api/patterns/{id}/review             # Self-rated recall card (409 unless due)
GET    /api/patterns/{id}/practice           # Linked task to solve instead of a recall card

# Admin (ADMIN_EMAILS only)
GET    /api/admin/ai-config                  # Active provider/model, catalog, per-provider key/approval state, failover/breaker
PUT    /api/admin/ai-config                  # Switch provider/model (pings the model first; 502 if it fails)
```

**Auth routes**:
```
GET  /login/google                   # Google OAuth redirect (?register=1 keeps the registration answers)
GET  /auth/callback                  # OAuth callback: known sub -> login; unknown -> create from
                                     # pending_registration, else pending_google + /rejestracja?google=1
POST /logout                         # Logout (form POST); GET /logout logs out only same-origin navigations
```

**Static routes**:
```
GET  /pdf/{year}/{etap}/{filename}   # Serve task PDFs
GET  /uploads/{path}                 # Serve uploaded images
```

### Database (PostgreSQL)

**Tables**:
- `users` - Accounts: `id` PK (equals the Google sub for accounts created before 2026-10-12,
  when the column was renamed from `google_sub`; uuid4 hex for new ones), `google_sub` (Google
  identity, NULL for login accounts), `email`/`name` (Google only), `login` + `password_hash`
  (argon2id) for children without e-mail, `birth_year` (NULL = not asked yet), `status`
  (`active` / `pending_parent`), `pending_since`, `parent_id`, `session_version`.
  Every `user_id` FK points at `users.id`; use `google_sub` only for the Google identity.
- `parents` - Parent e-mail addresses (shared by siblings), deleted with the last child
- `consents` - Proof of consent: `self` (16+) or `parent`, terms_version, given_at (no IP)
- `email_tokens` - SHA-256 of links e-mailed to parents (consent 14 d, password_reset 1 h,
  parent_manage 30 d); also the send log for the e-mail rate limits, so erasing an account
  only nulls `user_id` (FK SET NULL) and a childless parent row waits 24 h
- `login_failures` - Failed password logins (login, HMAC of IP), 24 h
- `submissions` - Solution submissions (user_id FK, year, etap, task_number, score, feedback)
- `deleted_account_quota` - Short-lived, pseudonymous rate-limit tombstones left by
  self-service account deletion, so erasing an account cannot reset the daily limit
- `admin_access_log` - Audit trail of admin access to other users' data (RODO art. 5(2));
  identifiers and a resource label only, never content
- `private_tasks` - Tasks a student added from a photo or typed text; owner-only.
  `submissions` reference EITHER an OMJ task (`year`, `etap`, `task_number`) OR a
  private task (`private_task_id`) - check constraint `ck_submissions_task_ref`.
  Any new OMJ aggregate over `submissions` must filter `private_task_id IS NULL`.
- `ai_usage` - Content-free log of non-submission AI calls (extraction, hints, patterns), for rate limits
- `app_settings` - Key/value runtime settings; holds the active AI provider + model chosen in
  `/admin/settings` (no row = env default, Gemini `GEMINI_MODEL`)
- `patterns`, `pattern_links`, `pattern_reviews` - Student-written problem-solving patterns
  ("Wzorce") with spaced repetition, linked tasks and a review log; owner-only.
  `submissions.pattern_id` (SET NULL) marks a solution submitted as practice of a pattern.

**Local**: PostgreSQL 16 via Docker on port 5433 (`postgresql://omj:omj@localhost:5433/omj`)

**Migrations**: Alembic in `alembic/versions/`

### Key Data Flows

1. **Task Loading**: a task is assembled from two halves, joined in exactly one
   place - `_load_all_tasks()` in `app/storage.py`. All 352 tasks are scanned on
   startup and cached.

   **Half one - metadata**, `data/tasks/{year}/{etap}/task_{num}.json`, tracked in git:
   ```json
   {
     "number": 1,
     "pdf": {"tasks": "...", "solutions": "...", "statistics": "..."},
     "difficulty": 3,
     "categories": ["geometria", "algebra"],
     "hints": ["hint1", "hint2", "hint3", "hint4"],
     "prerequisites": ["2023_etap1_2"],
     "skills_required": [], "skills_gained": []
   }
   ```

   **Half two - statement**, `data/task_content/{year}/{etap}.json`, git-ignored,
   generated by `fix_latex_content.py`, one file per etap:
   ```json
   {
     "year": "2024",
     "etap": "etap1",
     "tasks": {"1": {"title": "Title with $LaTeX$", "content": "Full text with $LaTeX$"}}
   }
   ```

   **Degradation when the statement is missing** (the normal state of a fresh
   clone): the task still loads with all of its metadata, `content` is `None`,
   `has_content` is `false` and `title` falls back to `"Zadanie {number}"`, so
   every consumer of `title` (progress graph, submission history, notifications)
   keeps working. Clients must render a link to the task PDF instead of the
   statement. This is never an error and must not raise.

   Valid categories: `algebra`, `geometria`, `teoria_liczb`, `kombinatoryka`, `logika`, `arytmetyka`

2. **Submission Flow**:
   - A solution is photos (`images`; drawings made in the browser arrive as PNG photos),
     a typed text (`solution_text`: plain text + `$LaTeX$`, at most `SUBMISSION_TEXT_MAX_CHARS`
     code points) or both - `app/uploads.py::validate_submission_input` decides before any
     file is written. Photos go to `data/uploads/{user_id}/{year}/{etap}/{task_num}/`; the
     text is stored on `submissions.solution_text` (no file, immutable after submit)
   - AI analyzes task PDF + solution PDF + student images + the typed text, which is sent
     after the photos as a fenced `<rozwiazanie_ucznia_{nonce}>` block (random suffix per request)
     (`app/ai/prompt_builder.py::solution_text_block`); logs and Telegram carry its length only
   - Results stored in PostgreSQL `submissions` table
   - OMJ scoring: 0, 2, 5, or 6 points

3. **AI Integration**: One provider at a time - Gemini (File API) or Claude (Anthropic Messages
   API, PDFs and photos inline) - chosen by an admin in `/admin/settings` from
   `app/ai/models_catalog.py`; `create_ai_provider()` reads the choice (`app_settings`, else env)
   on every call, so a switch applies to the next request without a restart. Claude is usable
   only with `ANTHROPIC_API_KEY` and `ANTHROPIC_PROCESSOR_APPROVED=true` (GDPR gate); an
   unusable choice falls back to the env Gemini default. Both providers send the same text
   (`app/ai/requests.py`), so `scripts/rescore_eval.py --provider` A/Bs compare models, not
   prompts (`docs/model-ab-playbook.md`). Prompts in `prompts/` (see `app/ai/prompt_builder.py`).
   **Rollback**: `ANTHROPIC_PROCESSOR_APPROVED=false` + api restart forces Gemini whatever the
   stored row says. Switching back in the UI needs a successful Gemini ping (a Google 503/429
   blocks it - then use the env flag).

   **Failover** (`app/ai/failover.py`): `create_ai_provider()` wraps the active provider in a
   `FailoverProvider` when the backup - `AI_FAILOVER_MODEL` (default `claude-opus-5-5`), or the
   env Gemini default when the active model is itself Claude - passes the SAME gates (key;
   for Anthropic `ANTHROPIC_PROCESSOR_APPROVED`); otherwise the plain provider, exactly as
   before. Fail closed: only an `AIUnavailableError` a student cannot provoke (401/403, 404,
   429, 502/503/504/529, connection never established) fails a call over, once; never a
   content block, abuse verdict, empty/unreadable answer or other 400. Timeouts, 500 and
   dropped connections (content can cause them) never fail the call over - they only feed
   the breaker. A streaming grading restarts on the backup through the worker's
   `restart_hook`. In-process circuit breaker: key/model errors open it at once, transient
   ones after `AI_FAILOVER_BREAKER_THRESHOLD` in a row across requests (a success resets),
   for `AI_FAILOVER_BREAKER_MINUTES`; a Telegram alert per opening (error class only).
   scoring_meta / ai_usage.meta name the provider/model that answered plus `failover:
   {from, reason}`; `/admin/settings` shows backup, gate and breaker state. Scripts that call
   `build_provider()` (A/B, rescore) never fail over.

   **Safeguards**: Gemini gets `safety_settings` on every call (harassment, hate, sexual: LOW+;
   dangerous: MEDIUM+; grading calls take harassment from MEDIUM - feedback on mistakes rates LOW); a prompt-level `block_reason` or a safety `finish_reason` is
   `AIContentBlockedError`. Student text in prompts is fenced (`student_text()` `<<<NONCE ...
   NONCE>>>`, `<rozwiazanie_ucznia_NONCE>`) with a random per-request suffix, and look-alikes
   of a fence (any case/spacing, HTML entities, fullwidth, diacritics, zero-width) are removed
   from the text sent (`prompt_builder.neutralise`). Snapshot tests patch `fence_nonce`. A grading `abuse_score >= PRIVATE_ABUSE_THRESHOLD` scores 0
   whatever `issue_type` says. Private-task text is saved only after a successful hint call
   that found it to be maths and not manipulation (create and edit). Pattern refine is
   maths-only (`off_topic` -> fixed decline, no round). `AI_DAILY_SPEND_LIMIT_USD` caps the
   estimated 24 h spend (`app/ai/spend.py`: recorded `estimated_cost` + the active model's
   nominal-call price for calls in flight + a failed-over primary's estimate; checked in the grading worker and `reserve_ai_calls`, 429 for aux calls);
   `AI_GRADING_MAX_CONCURRENT` caps parallel gradings (the rest wait as "pending").

4. **Private tasks ("Moje zadania")**: photo -> `extract_private_tasks` (schema-constrained,
   inline images) -> draft photos in `uploads/{user}/private/_drafts/{id}/` -> student picks
   and edits problems -> `generate_private_task_meta` (hints) -> `private_tasks` row with its
   own copy of the photos in `uploads/{user}/private/{task_id}/source/`. Grading uses
   `analyze_private_solution_stream` (task text instead of PDFs, no official solution,
   prompt `gemini_prompt_scoring_private.txt`) through the same background worker and
   WebSocket; the graded text is kept in `scoring_meta["task_snapshot"]`. Never commit real
   task statements in fixtures - the fake Gemini uses invented problems.

5. **Patterns ("Wzorce")**: the student writes "kiedy w treści widzę X, to warto spróbować Y"
   (or asks `suggest_patterns` for ideas from a graded solution), refines it in guided rounds
   (`refine_pattern`, schema-constrained, 2-3 versions to pick from), and `link_pattern_tasks`
   picks OMJ tasks from candidates `app/patterns/linking.py` chose (skills/category; the model
   never sees statements). Reviews: self-rated recall cards, and graded practice - a submission
   carrying `pattern_id` is turned into a review by `apply_practice_result` in the grading
   worker. Scheduling is pure (`app/patterns/srs.py`): levels 1-3 with intervals (1,4),
   (7,14), (30,90) days, then 180-day maintenance.

6. **LaTeX Rendering**: Frontend uses KaTeX via `MathContent` component, which HTML-escapes
   all non-math text (private task statements are user/AI controlled). `npm test` covers it.
   The typed-solution editor (`SolutionTextEditor`) previews through the same component with `indexMath` for click-to-edit; MathLive and Excalidraw fonts are copied into `frontend/public/{mathlive,excalidraw}` (git-ignored) by `frontend/scripts/copy-editor-assets.mjs` on install/dev/build - nothing is fetched from a CDN.

### Configuration

**Backend environment variables** (`.env`):

```bash
# Authentication (disabled by default for local dev)
AUTH_DISABLED=true
SESSION_SECRET_KEY=dev-secret-key-change-in-production

# Google OAuth (optional for local dev, required for production)
# GOOGLE_CLIENT_ID=...
# GOOGLE_CLIENT_SECRET=...

# Access control
# PUBLIC_ACCESS=true  # Allow all authenticated users to submit (with rate limits)
# ALLOWED_EMAILS=user1@gmail.com,user2@example.com  # Rate limit bypass when PUBLIC_ACCESS=true
# OR (when PUBLIC_ACCESS=false, only these users get full access)
# GOOGLE_GROUP_EMAIL=your-group@googlegroups.com
# GOOGLE_SERVICE_ACCOUNT_JSON={...}

# Transactional e-mail (parent consent, password reset, parent links)
EMAIL_BACKEND=console                 # "console" (logs + in-memory outbox) or "resend"
# RESEND_API_KEY=re_...               # required with resend (prod compose refuses to start without it)
# EMAIL_FROM=Trener OMJ <noreply@omj-validator.pl>
# EMAIL_REPLY_TO=kontakt@omj-validator.pl
# PUBLIC_BASE_URL=https://omj-validator.pl   # absolute links + e-mail logo
# TERMS_VERSION=2026-10-13            # stored with each consent; bump with LAST_UPDATED in /regulamin

# Data retention (RODO art. 5(1)(e) - storage limitation)
# 0 disables a pass; docker-compose.yml disables both for local dev.
# Fixed in app/retention.py (not configurable): pending_parent accounts 14 days,
# email_tokens 30 days after expiry, login_failures 24 h, childless parents.
RETENTION_SUBMISSION_MONTHS=24        # Submission row + uploaded photos + typed text
RETENTION_SCORING_THINKING_DAYS=90    # Raw AI "thinking" trace in scoring_meta
RETENTION_INACTIVE_ACCOUNT_MONTHS=36  # Accounts with no login and no submission
RETENTION_ADMIN_AUDIT_MONTHS=12       # Admin access audit trail
RETENTION_PRIVATE_TASK_MONTHS=24      # Private tasks, counted from last activity
RETENTION_AI_USAGE_DAYS=90            # ai_usage rows (rate limiting only)
RETENTION_PATTERN_MONTHS=24           # Patterns, counted from last activity
RETENTION_AUTO_PURGE=true             # Daily in-app run (single-worker only)

# Submissions (OMJ + private): the row is reserved before photos are processed;
# cheap checks (bytes, header pixels, decoder) run on the whole batch first and free
# it; a refusal once decoding started keeps it as FAILED (still counts)
# RATE_LIMIT_SUBMISSIONS_IN_FLIGHT_PER_USER=2  # pending/processing at once

# Registration abuse limits. New accounts are capped per 24 h in two pools:
# no parent needed (Google 16+) and parent-consent accounts (login, under-16 Google)
# RATE_LIMIT_NEW_USERS_PER_DAY=50
# RATE_LIMIT_NEW_PENDING_USERS_PER_DAY=50
# RATE_LIMIT_REGISTRATIONS_PER_IP_PER_DAY=30   # school NAT: a whole class
# TURNSTILE_SITE_KEY=...      # Cloudflare Turnstile; unset secret = off (dev, e2e)
# TURNSTILE_SECRET_KEY=...    # test keys: 1x00000000000000000000AA / 1x0000000000000000000000000000000AA
# SPLIT_DEPLOYMENT=false      # true only if the frontend is on another site: SameSite=None + CORS

# Private task limits (grading shares the submission limits)
# RATE_LIMIT_PRIVATE_TASKS_PER_USER_PER_DAY=10
# RATE_LIMIT_PRIVATE_EXTRACTS_PER_USER_PER_DAY=15
# RATE_LIMIT_AI_USAGE_GLOBAL_PER_DAY=1000
# RATE_LIMIT_PATTERN_REFINES_PER_USER_PER_DAY=30
# RATE_LIMIT_PATTERN_SUGGESTS_PER_USER_PER_DAY=10
# RATE_LIMIT_PATTERN_LINKS_PER_USER_PER_DAY=10

# Typed solutions: cap in code points, mirrored in frontend/src/lib/utils/constants.ts
# SUBMISSION_TEXT_MAX_CHARS=20000

# AI - the active provider/model is chosen at runtime in /admin/settings (app_settings);
# the env below is only the default until an admin saves a choice.
AI_PROVIDER=gemini                   # Only "gemini"; anything else is ignored with a warning
GEMINI_API_KEY=...                   # Required
GEMINI_MODEL=gemini-3.8-flash        # Default model when no app_settings row exists
GEMINI_TIMEOUT=90

# Anthropic (Claude) - optional, selectable in /admin/settings
# ANTHROPIC_API_KEY=...
# ANTHROPIC_EFFORT=high               # grading
# ANTHROPIC_EFFORT_AUX=medium         # extraction, hints, patterns
# ANTHROPIC_TIMEOUT=180
# ANTHROPIC_PROCESSOR_APPROVED=false  # GDPR gate: true only after Anthropic is signed off as a processor

# Failover to a backup model when the active provider is unavailable (through the gate above only)
# AI_FAILOVER_ENABLED=true
# AI_FAILOVER_MODEL=claude-opus-5-5   # from app/ai/models_catalog.py, another provider
# AI_FAILOVER_BREAKER_MINUTES=15      # breaker open time (all calls -> backup)
# AI_FAILOVER_BREAKER_THRESHOLD=3     # transient errors in a row that open it

# Global brakes
# AI_DAILY_SPEND_LIMIT_USD=25         # estimated USD per rolling 24 h, 0 = off; Telegram at 80%/100%
# AI_GRADING_MAX_CONCURRENT=4         # gradings calling the model at once
# AI_GRADING_QUEUE_TIMEOUT=300        # max wait for a slot (s), then "przeciążony"

# Note: DATABASE_URL is set in docker-compose.yml for container networking
```

**Frontend environment**: Set in `docker-compose.yml` (`FASTAPI_URL=http://api:8000`).

## Deployment

### Local Development

```bash
./start.sh  # Starts all services via Docker Compose
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Database: localhost:5433

All services run in Docker with hot-reload enabled. Code changes in `app/` and `frontend/src/` are automatically picked up.

### Production (NUC Server)

Deployed on a local Intel NUC server with Docker Compose and Cloudflare Tunnel.

**Domain**: https://omj-validator.pl

**Server**: Local NUC, connection details configured in `deploy.sh`

**Deployment workflow** (build locally, pull on server):
```bash
# One-time setup: login to GitHub Container Registry
# 1. Create PAT at https://github.com/settings/tokens with 'write:packages' scope
# 2. Login: echo YOUR_PAT | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Build and push images from local machine
./build-and-push.sh

# Deploy to server (pulls images from ghcr.io)
./deploy.sh

# Or build and deploy in one command
./build-and-push.sh && ./deploy.sh
```

**Where the tasks come from in production**: the OMJ PDFs and the generated
statements are not in the repository, so they are **baked into the API image at
build time** from the working copy of the machine running `build-and-push.sh`.
That machine must have run `python download_tasks.py --all-etaps` (and, for the
statements, `python fix_latex_content.py --all --skip-existing`) first;
`build-and-push.sh` refuses to build the API image when `tasks/` is empty and
warns when `data/task_content/` is. The server itself pulls a finished image and
needs nothing extra. Consequence: **the published image contains OMJ material, so
the ghcr.io package must not be public.** The alternative - bind-mounting
`./tasks` and `./data/task_content` from the server in `docker-compose.prod.yml`
- would require putting the corpus on the NUC and is not what the current
deployment does.

**Useful commands**:
```bash
./deploy.sh --status        # Check container status
./deploy.sh --logs api      # View API logs
./deploy.sh --ssh           # SSH into server
```

