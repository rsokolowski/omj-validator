# Private Tasks ("Moje zadania") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any logged-in user add private tasks (from a photo or typed text) and get handwritten solutions to them graded on the OMJ 0/2/5/6 scale.

**Architecture:** A new `private_tasks` table owned by a user; `submissions` is generalised to reference either an OMJ task or a private task, so the existing WebSocket/grading/history/retention machinery is reused. New Gemini calls (extraction, hint generation, private grading) sit next to the untouched OMJ path. New routes live in their own FastAPI router; upload and rate-limit helpers move out of `app/main.py` into shared modules so the router does not import `main`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, google-genai 2.19, pytest; Next.js 16, React 19, MUI v7, KaTeX.

**Spec:** `docs/superpowers/specs/2026-09-29-private-tasks-design.md`

## Global Constraints

- All user-facing text in Polish; code, comments, logs in English (existing convention).
- OMJ score ladder for private grading: 0, 2, 5, 6 (etap2 ladder, `parse_ai_response(..., etap="etap2")`).
- Private task id: 12 chars from `secrets.token_urlsafe(9)`; validated by `^[A-Za-z0-9_-]{12}$`.
- Draft id: 16 hex chars; validated by `^[0-9a-f]{16}$`.
- Content 20–10 000 chars; title 1–120; source label ≤ 120; difficulty 1–5; category ∈ {algebra, geometria, teoria_liczb, kombinatoryka, logika, arytmetyka}.
- Max 8 extracted problems, max 4 hints, max 10 images per upload (existing limit).
- Upload layout: `uploads/{user}/private/{task_id}/source/*.jpg`, `uploads/{user}/private/{task_id}/{uuid12}.jpg`, `uploads/{user}/private/_drafts/{draft_id}/*.jpg`.
- Config defaults: `rate_limit_private_tasks_per_user_per_day=10`, `rate_limit_private_extracts_per_user_per_day=15`, `rate_limit_ai_usage_global_per_day=1000`, `retention_private_task_months=24`, `retention_ai_usage_days=90`, `private_abuse_threshold=70`.
- Foreign / missing private task ids answer **404**, never 403.
- Never log task content, titles or hints; ids are masked with `mask_user_id` like the rest of the app.
- No real OMJ or booklet problem text in tests, fixtures or the fake Gemini (CLAUDE.md rule).

## Refinements to the spec discovered while reading the code

Recorded here and folded back into the spec in the same commit:

1. `private_tasks.hints_revealed` (persistent high-water mark) is added next to `pending_hints_used`, so a reload shows the hints already revealed; the detail endpoint returns `hints[:hints_revealed]` and never the unrevealed ones.
2. Submit route is `POST /api/private-tasks/{id}/submit` (not `/private-task/...`) so one Next.js route handler family proxies it; submission history is returned inside the detail response instead of a separate `/history` endpoint.
3. `ai_usage.kind` ∈ {`private_extract`, `private_create`, `private_regen`}; the creation cap counts `private_create` + `private_regen`.
4. The account-deletion tombstone gets an `ai_usage_count` column so erasing an account cannot reset the new AI limits either.
5. Extraction and private grading send images inline (`Part.from_bytes`) instead of through the File API — no PDF is involved, and inline keeps the request self-contained.

## Review Focus

- Existing OMJ flows must be byte-for-byte unaffected: OMJ submit, WebSocket, progress graph, my-solutions stats, admin list and rerun — every aggregate over `submissions` must ignore or correctly label private rows.
- A photo that is not a math problem, or contains a prompt-injection attempt, must never create a task or leave files on disk.
- Draft reuse: confirming the same draft twice, or someone else's draft id, must fail (410 / 404) without copying files.
- Hint honesty: revealing hint n+2 before n+1 is refused; a re-reveal still counts toward the next submission's `hints_used`.
- Account erasure and retention must leave nothing behind for private tasks — rows, photos, drafts, `ai_usage`.

---

### Task 1: Data model, migration 006, OMJ queries exclude private rows

**Files:**
- Modify: `app/db/models.py`, `app/db/__init__.py`, `app/db/repositories.py`, `app/models.py`, `app/config.py`
- Create: `alembic/versions/006_add_private_tasks.py`
- Test: `tests/test_private_task_model.py`

**Interfaces:**
- Produces: `PrivateTaskDB`, `AIUsageDB`, `SubmissionDB.private_task_id`, `SubmissionDB.hints_used`, `DeletedAccountQuotaDB.ai_usage_count`; pydantic `Submission.year/etap/task_number: Optional`, `Submission.private_task_id: Optional[str]`, `Submission.hints_used: int = 0`.

- [ ] **Step 1: Write failing tests** (`tests/test_private_task_model.py`, in-memory SQLite like `tests/test_retention.py`):
  - `test_submission_must_reference_exactly_one_task` — inserting a submission with both OMJ fields and `private_task_id`, or with neither, raises `IntegrityError`.
  - `test_private_submission_round_trips_to_pydantic` — `SubmissionRepository.to_pydantic` of a private row gives `year is None`, `private_task_id == task.id`, `hints_used == 2`.
  - `test_omj_progress_ignores_private_submissions` — `get_user_progress` returns only OMJ keys when the user also has a completed private submission scored 6.
  - `test_task_stats_ignore_private_submissions` — `get_task_stats(user, "2024","etap1",1)` counts only the OMJ row.
  - `test_my_submissions_year_filter_excludes_private` — `get_user_submissions_paginated(year_filter="2024")` returns no private rows; without filters it returns both.
  - `test_aggregate_stats_count_private_tasks_as_attempted` — `tasks_attempted` counts distinct OMJ tasks plus distinct private tasks; `tasks_mastered` counts private best ≥ 5.
  - `test_deleting_private_task_cascades_submissions` — `db.delete(task)` removes its submissions (ORM cascade).
- [ ] **Step 2: Run** `./venv/bin/python -m pytest tests/test_private_task_model.py -q` — expect ImportError/failures.
- [ ] **Step 3: Implement**
  - `PrivateTaskDB` (`__tablename__ = "private_tasks"`) with the spec columns plus `hints_revealed Integer default 0`, `pending_hints_used Integer default 0`; relationship `submissions = relationship("SubmissionDB", back_populates="private_task", cascade="all, delete-orphan")`; `Index("ix_private_tasks_user_activity", "user_id", "last_activity_at")`.
  - `AIUsageDB` (`ai_usage`): `id` int PK, `user_id` FK CASCADE indexed, `kind String(32)`, `created_at` indexed, `meta JSON`.
  - `UserDB.private_tasks` and `UserDB.ai_usage` relationships, `cascade="all, delete-orphan"`.
  - `SubmissionDB`: `year/etap/task_number nullable=True`; `private_task_id = Column(String(12), ForeignKey("private_tasks.id", ondelete="CASCADE"), nullable=True)`; `hints_used = Column(Integer, nullable=False, default=0, server_default="0")`; `private_task = relationship("PrivateTaskDB", back_populates="submissions")`; `CheckConstraint(TASK_REF_CHECK, name="ck_submissions_task_ref")`; `Index("ix_submissions_user_private_task", "user_id", "private_task_id")`.
  - `DeletedAccountQuotaDB.ai_usage_count = Column(Integer, nullable=False, default=0, server_default="0")`.
  - Repository: add `SubmissionDB.private_task_id.is_(None)` to `get_user_submissions_for_task`, `get_user_progress`, and to `get_user_submissions_paginated` when a year/etap filter is set; `to_pydantic` passes `private_task_id`, `hints_used`; `get_user_aggregate_stats` computes `tasks_attempted` = distinct OMJ triples + distinct private ids and adds private tasks with best ≥ 5 to `tasks_mastered`.
  - Migration 006: `create_table private_tasks`, `create_table ai_usage`, `alter_column` ×3 nullable, `add_column submissions.private_task_id/hints_used`, `create_foreign_key`, `create_check_constraint`, `create_index`, `add_column deleted_account_quota.ai_usage_count`; docstring with the RODO rationale; full `downgrade()` (deletes private submissions first so the NOT NULL restore succeeds).
  - Config: the six new settings from Global Constraints with comments.
- [ ] **Step 4: Run** the new tests and the full suite — all pass.
- [ ] **Step 5: Commit** `feat(db): private tasks schema and OMJ query isolation`.

### Task 2: Repositories for private tasks and AI usage; tombstone carries AI usage

**Files:**
- Create: `app/db/private_tasks.py`
- Modify: `app/db/repositories.py` (`DeletedAccountQuotaRepository`), `app/db/__init__.py`
- Test: `tests/test_private_task_repository.py`

**Interfaces:**
- Produces:
  ```python
  class PrivateTaskRepository:
      def __init__(self, db: Session): ...
      def create(self, user_id: str, *, title: str, content: str, source_label: str | None,
                 category: str | None, difficulty: int | None, hints: list[str],
                 origin: str, extraction_meta: dict | None = None) -> PrivateTaskDB
      def get_owned(self, task_id: str, user_id: str) -> PrivateTaskDB | None
      def list_for_user(self, user_id: str, offset: int = 0, limit: int = 50) -> tuple[list[dict], int]
          # dicts: {"task": PrivateTaskDB, "best_score": int | None, "attempts": int}
      def update_fields(self, task: PrivateTaskDB, **fields) -> PrivateTaskDB   # bumps last_activity_at
      def reveal_hint(self, task: PrivateTaskDB, n: int) -> str   # raises HintOrderError / IndexError
      def take_pending_hints(self, task: PrivateTaskDB) -> int   # returns and resets, bumps activity
      def touch(self, task: PrivateTaskDB) -> None
      def delete(self, task: PrivateTaskDB) -> None
      def count_created_since(self, user_id: str, hours: int = 24) -> int
  class AIUsageRepository:
      def record(self, user_id: str, kind: str, meta: dict | None = None) -> AIUsageDB
      def user_window(self, user_id: str, kinds: set[str], hours: int = 24) -> tuple[int, datetime | None]
      def global_window(self, hours: int = 24) -> tuple[int, datetime | None]
      def user_total_window(self, user_id: str, hours: int = 24) -> tuple[int, datetime | None]
  class HintOrderError(Exception): ...
  ```
  `DeletedAccountQuotaRepository.record_deletion(..., ai_usage_count: int = 0)` and `get_user_ai_usage_carryover(user_id) -> int`.
- [ ] **Step 1: Failing tests** — create/get_owned (other user → None); list with best score and attempts; `reveal_hint(n=2)` before 1 raises `HintOrderError`; reveal 1 then 2 sets `hints_revealed=2`, `pending_hints_used=2`; re-reveal 1 keeps `pending=2`; `take_pending_hints` returns 2 then 0; `ai_usage.user_window` counts only given kinds inside 24h; tombstone with only AI usage is recorded and `get_user_ai_usage_carryover` returns it; existing behaviour of `record_deletion(submission_count=0, ai_usage_count=0)` still returns None.
- [ ] **Step 2: Run** — fail. **Step 3: Implement.** **Step 4: Run** new + `tests/test_rate_limit_tombstone.py` — pass.
- [ ] **Step 5: Commit** `feat(db): private task and AI usage repositories`.

### Task 3: Move upload and rate-limit helpers out of `app/main.py`

**Files:**
- Create: `app/uploads.py`, `app/rate_limits.py`
- Modify: `app/main.py` (imports + `submit_solution` uses the helpers)
- Test: existing `tests/test_upload_cleanup.py`, `tests/test_image_normalization.py`, `tests/test_rate_limit_*.py` must stay green.

**Interfaces:**
- Produces:
  ```python
  # app/uploads.py
  ALLOWED_IMAGE_TYPES: set[str]; MAX_IMAGES = 10
  def discard_uploads(saved_paths: list[Path], current: Path | None = None) -> None
  def normalize_uploaded_image(file_path: Path) -> Path | None
  async def save_uploaded_images(images: list[UploadFile], upload_dir: Path,
                                 normalize=None) -> tuple[list[Path], JSONResponse | None]
  # app/rate_limits.py
  def calculate_rate_limit_headers(limit, current_count, oldest_timestamp, window_hours=24) -> dict
  def rate_limit_reset_anchor(live_timestamps, carryover_blocks, limit, window_hours=24)
  def calculate_retry_after(oldest_timestamp, window_hours=24) -> int
  def is_allowlisted(request) -> bool
  def check_submission_limits(request, db, user_id) -> tuple[JSONResponse | None, dict, int, datetime | None]
  ```
  `app/main.py` keeps the old private names as aliases (`_normalize_uploaded_image = normalize_uploaded_image`, etc.). `save_uploaded_images` looks the normaliser up through a module-level hook so the existing monkeypatch of `main._normalize_uploaded_image` keeps working: main passes `normalize=lambda p: _normalize_uploaded_image(p)` resolved at call time.
- [ ] **Step 1:** Run the three existing test files — green baseline.
- [ ] **Step 2:** Move code verbatim; `submit_solution` calls `check_submission_limits` and `save_uploaded_images`.
- [ ] **Step 3:** Re-run the full suite — 0 regressions.
- [ ] **Step 4: Commit** `refactor: share upload and rate-limit helpers`.

### Task 4: AI layer — prompts, parsing, Gemini methods

**Files:**
- Create: `prompts/private_task_extract.txt`, `prompts/private_task_meta.txt`, `prompts/gemini_prompt_scoring_private.txt`, `app/ai/private_parsing.py`
- Modify: `app/ai/prompt_builder.py`, `app/ai/protocol.py`, `app/ai/providers/gemini.py`, `app/models.py`
- Test: `tests/test_private_ai.py`

**Interfaces:**
- Produces (in `app/models.py`):
  ```python
  class ExtractedProblem(BaseModel): label: str; title: str; content: str; category: Optional[str]; difficulty: Optional[int]
  class PrivateExtractionResult(BaseModel): is_math_problem: bool; abuse_score: int; problems: list[ExtractedProblem]; meta: dict = {}
  class PrivateTaskMeta(BaseModel): hints: list[str]; category: Optional[str]; difficulty: Optional[int]; abuse_score: int; meta: dict = {}
  ```
  `app/ai/private_parsing.py`: `parse_extraction_response(text) -> PrivateExtractionResult`, `parse_meta_response(text) -> PrivateTaskMeta`, `EXTRACTION_SCHEMA`, `META_SCHEMA`.
  `prompt_builder`: `build_private_scoring_prompt() -> str`, `load_private_prompt(name: str) -> str`; `validate_prompts()` also checks the three new files.
  `GeminiProvider`:
  ```python
  async def extract_private_tasks(self, image_paths: list[Path]) -> PrivateExtractionResult
  async def generate_private_task_meta(self, title: str, content: str) -> PrivateTaskMeta
  async def analyze_private_solution_stream(self, task_title: str, task_content: str,
        image_paths: list[Path], on_thinking=None, on_upload_complete=None) -> SubmissionResult
  ```
  Streaming loop factored into `_run_stream(content_parts, config, on_thinking, on_feedback) -> tuple[str, str, Any, float]` used by both `analyze_solution_stream` and the private variant; JSON calls through `_generate_json(contents, schema) -> tuple[str, dict]`.
- [ ] **Step 1: Failing tests** — parsing: valid multi-problem JSON; >8 problems truncated to 8; empty-content problem dropped; invalid category → None; difficulty 9 → 5, 0 → 1; `is_math_problem=false` → empty problems; garbage text → `is_math_problem False`; LaTeX single-backslash repair applied to content; meta: >4 hints truncated, blank hints dropped, abuse clamped 0–100. Prompts: `validate_prompts() == []`; private scoring prompt contains the base and abuse sections and the phrase "brak oficjalnego rozwiązania". Provider (stubbed client): `_generate_json` gets `response_json_schema=EXTRACTION_SCHEMA`; images sent as inline parts.
- [ ] **Step 2: Run** — fail. **Step 3: Implement.** **Step 4: Run** new tests + `tests/test_gemini_cost_and_resolution.py` — pass.
- [ ] **Step 5: Commit** `feat(ai): private task extraction, hints and grading`.

### Task 5: Background grading for private submissions

**Files:**
- Modify: `app/websocket/handler.py`
- Test: `tests/test_private_grading_handler.py`

**Interfaces:**
- `process_submission_background(..., private_task: dict | None = None)` where `private_task = {"id", "title", "content"}`; for private rows it calls `analyze_private_solution_stream`, stores `scoring_meta["task_snapshot"] = {"title","content"}`, and Telegram messages read `Task: private` (never the title).
- [ ] **Step 1: Failing test** — stub provider + SQLite `SessionLocal` monkeypatch: private submission becomes COMPLETED with score 5 and the snapshot in `scoring_meta`; provider exception → FAILED with message.
- [ ] **Step 2–4:** implement, run, pass. **Step 5: Commit** `feat: grade private submissions in the background worker`.

### Task 6: API router

**Files:**
- Create: `app/private_tasks/__init__.py`, `app/private_tasks/routes.py`, `app/private_tasks/service.py`
- Modify: `app/main.py` (`app.include_router(private_tasks_router)`), `app/models.py` (request bodies)
- Test: `tests/test_private_task_api.py`

**Interfaces:** routes exactly as the spec's API table with refinement 2; request models:
```python
class PrivateTaskInput(BaseModel): title: str; content: str; source_label: Optional[str] = None
    category: Optional[str] = None; difficulty: Optional[int] = None
class CreatePrivateTasksRequest(BaseModel): draft_id: Optional[str] = None; tasks: list[PrivateTaskInput]  # 1..8
class UpdatePrivateTaskRequest(BaseModel): all fields Optional
```
Access: `verify_auth` + `is_group_member_async` on every route (same audience as OMJ submission).
- [ ] **Step 1: Failing tests** (TestClient + signed session cookie, stub provider):
  - extract happy path returns `draft_id` + 2 problems, files under `_drafts/`, one `ai_usage` row.
  - extract non-math → 422, no files left; high abuse → 422, no files left; provider error → 502, no files left.
  - extract over daily cap → 429 with `Retry-After`.
  - create from draft copies photos into each task's `source/`, deletes the draft dir, hints stored; second confirm of same draft → 410; other user's draft → 410.
  - create typed task with 10-char content → 422; meta failure → task saved with `hints=[]`; meta abuse → 422 and nothing saved.
  - create beyond `rate_limit_private_tasks_per_user_per_day` → 429.
  - list/detail/patch/delete; other user's id → 404 for each verb; detail never contains unrevealed hints.
  - hints: `/hints/2` first → 409; `/hints/1` then `/hints/2` → 200.
  - submit: creates PENDING private submission, `hints_used` copied, `pending_hints_used` reset, counts toward the OMJ daily submission limit (30 existing OMJ submissions → 429).
  - delete removes rows and every file under `private/{task_id}`.
- [ ] **Step 2–4:** implement, run, pass. **Step 5: Commit** `feat(api): private tasks endpoints`.

### Task 7: Retention and erasure

**Files:**
- Modify: `app/retention.py`, `scripts/purge_expired_data.py` (report fields only if it prints them), `app/main.py` (startup guard lists new periods)
- Test: `tests/test_private_task_retention.py`

**Interfaces:** `purge_expired_private_tasks(db, months=None, dry_run=False) -> RetentionReport`, `purge_expired_ai_usage(db, days=None, dry_run=False)`, `delete_private_task_files(user_id, task_id, report, dry_run=False)`; `RetentionReport.private_tasks_deleted`, `ai_usage_purged`; `strip_expired_scoring_thinking` also strips `private_tasks.extraction_meta["thinking"]`; `sweep_orphan_upload_files` treats `private_tasks.source_images` as referenced and does not bail out when only private tasks exist.
- [ ] **Step 1: Failing tests** — task idle 25 months deleted with files and submissions; active task kept; dry run changes nothing; stale draft (mtime > 24h) swept, fresh draft kept; task source photos never swept; account erasure removes tasks, ai_usage rows and the whole private tree; ai_usage older than 90 days purged.
- [ ] **Step 2–4:** implement, run, pass. **Step 5: Commit** `feat(retention): expire and erase private tasks`.

### Task 8: My-solutions and admin integration

**Files:**
- Modify: `app/main.py` (`my_submissions`, `admin_submissions`, `admin_rerun_submission`), `app/models.py`
- Test: `tests/test_private_task_listing.py`

- `my_submissions` items gain `private_task_id` and use the private task title, `max_score=6`, categories `[category]`.
- `admin_submissions` items gain `private_task_id` and `task_title`; access still audited by the existing list entry.
- `admin_rerun_submission` for a private row re-grades against the stored snapshot (fallback: current task text) through `process_submission_background(private_task=...)`.
- [ ] Tests: my-submissions returns a private item linked by id; admin list labels it; rerun of a private submission creates a new private PENDING row.
- [ ] **Commit** `feat: show private submissions in my-solutions and admin`.

### Task 9: Frontend

**Files:**
- Modify: `frontend/src/lib/types/index.ts`, `frontend/src/components/task/SubmitSection.tsx` (`submitUrl?`, `maxScore?`), `frontend/src/components/task/SubmissionHistory.tsx` (nullable etap), `frontend/src/components/layout/Header.tsx`, `frontend/src/components/my-solutions/SubmissionCard.tsx`, `frontend/src/components/admin/AdminSubmissionsTable.tsx`, `frontend/src/lib/utils/constants.ts` (`getMaxScore(etap: string | null)`)
- Create: `frontend/src/lib/api/proxy.ts`; route handlers `frontend/src/app/api/private-tasks/route.ts` (GET+POST), `.../extract/route.ts`, `.../[id]/submit/route.ts` (all `maxDuration = 180`); pages `frontend/src/app/moje-zadania/page.tsx`, `.../nowe/page.tsx`, `.../[id]/page.tsx`; components in `frontend/src/components/private-tasks/`: `PrivateTaskCard.tsx`, `NewPrivateTaskForm.tsx`, `ProblemEditor.tsx`, `PrivateHintsSection.tsx`, `PrivateTaskActions.tsx`, `SourcePhotos.tsx`.
- [ ] `npm run lint` shows no new problems (baseline: 1 pre-existing error in `TimerContext.tsx`); `npx tsc --noEmit` clean; `npm run build` succeeds.
- [ ] **Commit** `feat(frontend): Moje zadania pages`.

### Task 10: Fake Gemini and e2e

**Files:**
- Modify: `e2e/fake-gemini/server.py` — route by `generationConfig.responseJsonSchema` properties: `problems` → extraction response with two invented problems; `hints` → meta response; else existing grading.
- Create: `e2e/tests/private-tasks.spec.ts` — photo with two problems → select both → two tasks; typed task; reveal hint; submit and see score over WebSocket; delete.
- [ ] Run `cd e2e && ./run-e2e.sh private-tasks` if Docker works in the environment; otherwise record that it was not run.
- [ ] **Commit** `test(e2e): private tasks flow`.

### Task 11: Documentation

**Files:** `CLAUDE.md` (routes, tables, retention env vars), `docs/database-schema.md`, `docs/rodo/dpia.md`, `.env.example`, `docker-compose.yml` (retention off locally for the new periods).
- [ ] **Commit** `docs: private tasks data, retention and DPIA`.
