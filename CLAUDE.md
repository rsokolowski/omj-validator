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
│   ├── auth.py             # Session-based auth helpers
│   ├── oauth.py            # Google OAuth (Authlib)
│   ├── groups.py           # Access control (email allowlist or Google Groups)
│   ├── storage.py          # Task loading (dir scan + LRU cache)
│   ├── models.py           # Pydantic models
│   ├── progress.py         # Task progression graph logic
│   ├── db/                 # Database layer
│   │   ├── session.py      # SQLAlchemy engine, get_db dependency
│   │   ├── models.py       # ORM: UserDB, SubmissionDB
│   │   └── repositories.py # Data access layer
│   └── ai/
│       ├── protocol.py     # AIProvider interface
│       ├── factory.py      # Provider factory
│       ├── parsing.py      # JSON parsing, OMJ score normalization
│       └── providers/
│           └── gemini.py   # Gemini API integration
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
│   └── login/page.tsx               # Google OAuth login
├── components/
│   ├── layout/                      # Header, Footer, Breadcrumb
│   ├── task/                        # TaskCard, SubmitSection, HintsSection
│   ├── progress/                    # ProgressGraph, CategoryFilter
│   └── ui/                          # DifficultyStars, CategoryBadge, MathContent
└── lib/
    ├── api/client.ts                # Fetch helpers
    ├── hooks/useAuth.ts             # Auth state hook
    └── types/index.ts               # TypeScript types (match FastAPI models)
```

**API proxy**: `next.config.ts` rewrites `/api/*`, `/auth/*`, `/login/*`, `/logout`, `/pdf/*`, `/uploads/*` to FastAPI backend.

### Backend (FastAPI)

**JSON API routes** (used by Next.js frontend):
```
GET  /api/auth/me                    # Current user info
GET  /api/years                      # All years
GET  /api/years/{year}               # Etaps for year
GET  /api/years/{year}/{etap}        # Tasks for etap
GET  /api/task/{year}/{etap}/{num}   # Task detail
GET  /api/task/{year}/{etap}/{num}/history  # Submission history
GET  /api/progress/data              # Task progression data
POST /task/{year}/{etap}/{num}/submit       # Submit solution
POST /api/account/delete             # Erase own account + submissions + photos (RODO art. 17)
```

**Auth routes**:
```
GET  /login/google                   # Google OAuth redirect
GET  /auth/callback                  # OAuth callback
GET  /logout                         # Logout
```

**Static routes**:
```
GET  /pdf/{year}/{etap}/{filename}   # Serve task PDFs
GET  /uploads/{path}                 # Serve uploaded images
```

### Database (PostgreSQL)

**Tables**:
- `users` - Google OAuth users (google_sub PK, email, name)
- `submissions` - Solution submissions (user_id FK, year, etap, task_number, score, feedback)
- `deleted_account_quota` - Short-lived, pseudonymous rate-limit tombstones left by
  self-service account deletion, so erasing an account cannot reset the daily limit
- `admin_access_log` - Audit trail of admin access to other users' data (RODO art. 5(2));
  identifiers and a resource label only, never content

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
   - Images uploaded to `data/uploads/{user_id}/{year}/{etap}/{task_num}/`
   - AI analyzes task PDF + solution PDF + student images
   - Results stored in PostgreSQL `submissions` table
   - OMJ scoring: 0, 2, 5, or 6 points

3. **AI Integration**: Uses Gemini File API. Prompt in `prompts/gemini_prompt.txt`.

4. **LaTeX Rendering**: Frontend uses KaTeX via `MathContent` component.

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

# Data retention (RODO art. 5(1)(e) - storage limitation)
# 0 disables a pass; docker-compose.yml disables both for local dev.
RETENTION_SUBMISSION_MONTHS=24        # Submission row + uploaded photos
RETENTION_SCORING_THINKING_DAYS=90    # Raw AI "thinking" trace in scoring_meta
RETENTION_INACTIVE_ACCOUNT_MONTHS=36  # Accounts with no login and no submission
RETENTION_ADMIN_AUDIT_MONTHS=12       # Admin access audit trail
RETENTION_AUTO_PURGE=true             # Daily in-app run (single-worker only)

# AI
AI_PROVIDER=gemini
GEMINI_API_KEY=...                   # Required
GEMINI_MODEL=gemini-2.0-flash
GEMINI_TIMEOUT=90

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

See **[docs/production-deployment.md](docs/production-deployment.md)** for complete setup guide, operations, and troubleshooting.
