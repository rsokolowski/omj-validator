# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OMJ Validator - a web application for validating solutions to Polish Junior Mathematical Olympiad (Olimpiada Matematyczna Juniorów) competition problems. Students upload photos of their handwritten solutions, which are analyzed by AI (Gemini) against official task PDFs and scoring criteria.

**Architecture**: Monorepo with Next.js frontend and FastAPI backend, deployed as separate services.

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

# Download task PDFs from omj.edu.pl (run outside Docker)
python download_tasks.py

# Update task content with LaTeX from PDFs (uses Claude CLI)
python fix_latex_content.py 2024 etap1        # Specific year/etap
python fix_latex_content.py --all             # All tasks

# Generate/update task metadata (difficulty, categories, hints)
python populate_metadata.py                    # Uses Claude CLI
python populate_metadata.py --year 2024 --force
python populate_metadata_gemini.py             # Alternative using Gemini API
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
│   ├── tasks/              # Task metadata JSON files
│   └── uploads/            # User-submitted images
├── tasks/                   # Downloaded task PDFs (2005-2025)
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

**Local**: PostgreSQL 16 via Docker on port 5433 (`postgresql://omj:omj@localhost:5433/omj`)

**Migrations**: Alembic in `alembic/versions/`

### Key Data Flows

1. **Task Loading**: Per-task JSON files at `data/tasks/{year}/{etap}/task_{num}.json`. All 247 task files scanned on startup and cached.

   Task JSON structure:
   ```json
   {
     "number": 1,
     "title": "Task title with $LaTeX$",
     "content": "Full task content with $LaTeX$ notation",
     "pdf": {"tasks": "...", "solutions": "...", "statistics": "..."},
     "difficulty": 3,
     "categories": ["geometria", "algebra"],
     "hints": ["hint1", "hint2", "hint3", "hint4"],
     "prerequisites": ["2023_etap1_2"]
   }
   ```

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

# Access control (choose one)
# ALLOWED_EMAILS=user1@gmail.com,user2@example.com
# OR
# GOOGLE_GROUP_EMAIL=your-group@googlegroups.com
# GOOGLE_SERVICE_ACCOUNT_JSON={...}

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

### Production (GCP VM)

Deployed on GCP Compute Engine VM with Docker Compose and Nginx reverse proxy.

**Domain**: https://omj-validator.duckdns.org

**Quick deploy** (from local machine):
```bash
gcloud compute ssh omj-validator --command="cd ~/omj-validator && git pull && sudo docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build"
```

**View logs**:
```bash
gcloud compute ssh omj-validator --command="sudo docker logs omj-api --tail=100"
```

See **[docs/production-deployment.md](docs/production-deployment.md)** for complete setup guide, operations, and troubleshooting.
