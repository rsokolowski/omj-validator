# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OMJ Validator - a web application for validating solutions to Polish Junior Mathematical Olympiad (Olimpiada Matematyczna Juniorów) competition problems. Students upload photos of their handwritten solutions, which are analyzed by AI (Gemini) against official task PDFs and scoring criteria.

## Development Commands

```bash
# Start development server (handles port cleanup, activates venv)
./start.sh

# Or manually:
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Install dependencies
pip install -r requirements.txt

# Download task PDFs from omj.edu.pl
python download_tasks.py

# Update task content with LaTeX from PDFs (uses Claude CLI)
python fix_latex_content.py 2024 etap1        # Specific year/etap
python fix_latex_content.py --all             # All tasks

# Generate/update task metadata (difficulty, categories, hints)
python populate_metadata.py                    # Uses Claude CLI
python populate_metadata.py --year 2024 --force
python populate_metadata_gemini.py             # Alternative using Gemini API
```

## Architecture

### Application Structure

```
app/
├── main.py          # FastAPI routes, image upload/processing, PDF serving
├── config.py        # Settings via pydantic-settings, all paths defined here
├── auth.py          # Session-based auth helpers (get_current_user, require_auth, etc.)
├── oauth.py         # Google OAuth configuration (Authlib)
├── groups.py        # Access control: email allowlist or Google Groups API
├── storage.py       # Task loading (dir scan + LRU cache), submissions storage
├── models.py        # Pydantic models (TaskInfo, TaskPdf, Submission, etc.)
├── progress.py      # Progression graph: task status, prerequisites, recommendations
└── ai/
    ├── protocol.py  # AIProvider Protocol defining analyze_solution interface
    ├── factory.py   # Provider factory based on AI_PROVIDER setting
    ├── parsing.py   # Shared JSON parsing, OMJ score normalization (0,2,5,6)
    └── providers/
        └── gemini.py  # Gemini API implementation with file upload/cleanup
```

### Key Data Flows

1. **Task Loading**: Per-task JSON files at `data/tasks/{year}/{etap}/task_{num}.json`. All 247 task files are scanned on startup and cached in memory.

   Task JSON structure (see [docs/task-metadata.md](docs/task-metadata.md) for full reference):
   ```json
   {
     "number": 1,
     "title": "Task title with $LaTeX$",
     "content": "Full task content with $LaTeX$ notation",
     "pdf": {"tasks": "...", "solutions": "...", "statistics": "..."},
     "difficulty": 3,           // 1-5 scale
     "categories": ["geometria", "algebra"],  // from predefined set
     "hints": ["hint1", "hint2", "hint3", "hint4"],  // 4 progressive hints
     "prerequisites": ["2023_etap1_2"]  // task keys required for progression graph
   }
   ```

   Valid categories: `algebra`, `geometria`, `teoria_liczb`, `kombinatoryka`, `logika`, `arytmetyka`

2. **Submission Flow**:
   - Images uploaded to `data/uploads/{year}/{etap}/{task_num}/`
   - AI analyzes task PDF + solution PDF + student images
   - Results stored as JSON in `data/submissions/{year}/{etap}/{task_num}/`

3. **AI Integration**: Uses Gemini File API to upload PDFs and images, then generates analysis. Prompt in `prompts/gemini_prompt.txt` defines OMJ scoring criteria (0, 2, 5, 6 points).

4. **LaTeX Rendering**: Frontend uses KaTeX to render mathematical notation. Elements with `.math-content` class are auto-rendered. Task titles and content support inline math (`$...$`) and display math (`$$...$$`).

### Configuration

Environment variables (`.env`):

**Authentication:**
- `AUTH_DISABLED` - set to `true` to disable auth (local development)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` - Google OAuth credentials
- `SESSION_SECRET_KEY` - secret for session cookies (generate with `openssl rand -hex 32`)
- `ALLOWED_EMAILS` - comma-separated list of emails with full access (can submit solutions)

**AI Provider:**
- `AI_PROVIDER` - currently only "gemini" supported
- `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_TIMEOUT`

**Other:**
- `DATA_DIR` - optional external data directory for cloud deployments

**Access Control:** Users can log in via Google OAuth. Only users in `ALLOWED_EMAILS` can submit solutions; others get read-only access (can view tasks but not submit).

### Templates

Jinja2 templates in `templates/` with `base.html` layout. Polish language throughout the UI.

Key templates:
- `base.html` - includes KaTeX CSS/JS for math rendering, user info in header
- `login.html` - Google OAuth login page
- `auth_limited.html` - shown to logged-in users without full access
- `task.html` - task detail with hints (progressive reveal), submission form
- `etap.html` - task list with difficulty stars and category badges
- `progress.html` - progression graph with Cytoscape.js visualization

Frontend assets in `static/`:
- `app.js` - KaTeX auto-rendering for `.math-content` elements, hint toggle, file upload
- `style.css` - responsive design, difficulty/category badges, hint styling
- `progress.js` - Cytoscape.js graph rendering, filtering, recommendations
- `progress.css` - progression graph page styling

## Deployment

Configured for Render (`render.yaml`) using gunicorn with uvicorn workers. Free tier has no persistent disk - submissions are ephemeral.
