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
```

## Architecture

### Application Structure

```
app/
├── main.py          # FastAPI routes, image upload/processing, PDF serving
├── config.py        # Settings via pydantic-settings, all paths defined here
├── auth.py          # Cookie-based auth with derived session tokens
├── storage.py       # Task loading (dir scan + LRU cache), submissions storage
├── models.py        # Pydantic models (TaskInfo, TaskPdf, Submission, etc.)
└── ai/
    ├── protocol.py  # AIProvider Protocol defining analyze_solution interface
    ├── factory.py   # Provider factory based on AI_PROVIDER setting
    ├── parsing.py   # Shared JSON parsing, OMJ score normalization (0,2,5,6)
    └── providers/
        └── gemini.py  # Gemini API implementation with file upload/cleanup
```

### Key Data Flows

1. **Task Loading**: Per-task JSON files at `data/tasks/{year}/{etap}/task_{num}.json`. Each file contains task metadata (title, content), PDF paths, and extensibility fields (difficulty, categories, hints). All ~247 task files are scanned on startup and cached in memory.

2. **Submission Flow**:
   - Images uploaded to `data/uploads/{year}/{etap}/{task_num}/`
   - AI analyzes task PDF + solution PDF + student images
   - Results stored as JSON in `data/submissions/{year}/{etap}/{task_num}/`

3. **AI Integration**: Uses Gemini File API to upload PDFs and images, then generates analysis. Prompt in `prompts/gemini_prompt.txt` defines OMJ scoring criteria (0, 2, 5, 6 points).

### Configuration

Environment variables (`.env`):
- `AUTH_KEY` - authentication secret
- `AI_PROVIDER` - currently only "gemini" supported
- `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_TIMEOUT`
- `DATA_DIR` - optional external data directory for cloud deployments

### Templates

Jinja2 templates in `templates/` with `base.html` layout. Polish language throughout the UI.

## Deployment

Configured for Render (`render.yaml`) using gunicorn with uvicorn workers. Free tier has no persistent disk - submissions are ephemeral.
