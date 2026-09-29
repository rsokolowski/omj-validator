# Private tasks ("Moje zadania") — design

Date: 2026-09-29
Status: approved in brainstorming, awaiting written-spec review

## Context and goal

A student preparing for OMJ solves problems from many sources (IKOMJ/FKOMJ
booklets, Kangur, school sheets). Today the validator can only grade the 352
archived OMJ tasks. This feature lets any logged-in user add **private tasks**
— from a photo of the problem or typed text — and submit handwritten solutions
that are graded on the OMJ 0/2/5/6 scale, exactly like OMJ tasks.

This is sub-project 1 of 2. Sub-project 2 (user-authored patterns with LLM
refinement, spaced repetition and links to OMJ/private tasks) gets its own
spec; this design only leaves hooks for it (`hints_used`, a stable private
task id).

### Decisions made

| Question | Decision |
|---|---|
| Audience | All validator users (public feature) — limits, abuse checks, RODO from day one |
| Grading reference | Task text only; AI solves then grades; UI shows a "graded without official solution" badge |
| Task input | Photo (AI extraction) **or** typed text |
| Multiple problems in a photo | Extraction returns a list; user selects one or more; each becomes its own task |
| Hints | 3–4 progressive hints generated when the task is saved; revealed one by one; usage recorded |
| Data model | New `private_tasks` table; `submissions` generalised to reference either an OMJ task or a private task |

### Out of scope

Sharing tasks between users, patterns / spaced repetition, import from the
student's external notebook, reference-solution upload, OIJ/programming tasks.

## 1. Data model

### New table `private_tasks`

| Column | Type | Notes |
|---|---|---|
| `id` | `String(12)` PK | random, URL-safe; URL `/moje-zadania/{id}` |
| `user_id` | FK `users.google_sub`, `ondelete=CASCADE`, indexed | owner |
| `title` | `String(120)` | AI-suggested, editable |
| `content` | `Text` | task statement with `$LaTeX$`, 20–10 000 chars, user-confirmed |
| `source_label` | `String(120)`, nullable | e.g. "IKOMJ 4.3", "Kangur 2024/27" |
| `category` | `String(20)`, nullable | one of the six existing categories |
| `difficulty` | `Integer`, nullable | 1–5 |
| `hints` | `JSON` | list of 0–4 strings |
| `pending_hints_used` | `Integer`, default 0 | hints revealed since the last submission |
| `source_images` | `JSON` | relative paths, `uploads/{user}/private/{task_id}/source/*.jpg`; `[]` for typed |
| `origin` | `String(10)` | `photo` \| `typed` |
| `extraction_meta` | `JSON`, nullable | model, tokens, cost, raw thinking (thinking stripped after 90 days) |
| `created_at`, `updated_at` | `DateTime` | |
| `last_activity_at` | `DateTime`, indexed | bumped on create, edit, submission; drives retention |

`UserDB` gets a `private_tasks` relationship with `cascade="all, delete-orphan"`.

### Changes to `submissions` (Alembic `006_add_private_tasks.py`)

- Add `private_task_id String(12)` FK → `private_tasks.id`, `ondelete=CASCADE`, nullable.
- Make `year`, `etap`, `task_number` nullable.
- Check constraint `ck_submissions_task_ref`:
  `(year IS NOT NULL AND etap IS NOT NULL AND task_number IS NOT NULL AND private_task_id IS NULL) OR (year IS NULL AND etap IS NULL AND task_number IS NULL AND private_task_id IS NOT NULL)`.
- Add `hints_used Integer NOT NULL DEFAULT 0`.
- Index `ix_submissions_user_private_task (user_id, private_task_id)`.
- Solution photos for private tasks: `uploads/{user}/private/{task_id}/{uuid12}.jpg`.
- Each private submission stores a snapshot of the graded task text in
  `scoring_meta["task_snapshot"] = {title, content}` so later edits do not
  change what a past score refers to.

The migration docstring explains the RODO reasoning (children's data, retention,
cascade), following migrations 004/005. `docs/database-schema.md` is updated.

### OMJ queries must exclude private submissions

Every query that aggregates by OMJ task gets an explicit
`SubmissionDB.private_task_id.is_(None)` filter, each covered by a test:
task stats, best score per task / progress, progress graph data, admin
year/etap filters, and any `my-solutions` code path that builds OMJ task
links. Relying on NULL non-matching is not accepted.

### New table `ai_usage`

| Column | Notes |
|---|---|
| `id` | PK |
| `user_id` | FK users, `ondelete=CASCADE`, indexed |
| `kind` | `private_extract` \| `private_meta` |
| `created_at` | indexed |
| `meta` | JSON: model, tokens, cost (no content) |

Used for rate limiting non-submission AI calls. Rows older than 90 days are
purged by retention.

## 2. AI layer and flows

### New `AIProvider` methods (implemented in `GeminiProvider`)

The existing `analyze_solution*` path is untouched.

1. `extract_private_tasks(images) -> ExtractionResult`
   Non-streaming, Gemini `response_schema`:
   `{is_math_problem: bool, abuse_score: int, problems: [{label, title, content, category, difficulty}] (max 8)}`.
   Prompt: `prompts/private_task_extract.txt`.
2. `generate_private_task_meta(title, content) -> {hints: [str] (3–4), category, difficulty, abuse_score}`
   Text-only, schema-constrained. Used at confirm for every created task
   (photo and typed) and for "regenerate hints".
   Prompt: `prompts/private_task_meta.txt`.
3. `analyze_private_solution_stream(task_title, task_content, images)`
   Mirrors `analyze_solution_stream` (same streaming events and return shape
   `{score, feedback, issue_type, abuse_score}`) so `parse_ai_response`,
   OMJ score snapping, `process_submission_background`, the WebSocket
   progress protocol and result storage are reused. Prompt =
   `gemini_prompt_base.txt` + new `gemini_prompt_scoring_private.txt`
   (no official solution: solve the problem first, then grade against the
   0/2/5/6 rubric) + `gemini_prompt_abuse.txt`; built via `prompt_builder`
   and checked by `validate_prompts`.

### Create flow — photo

1. `POST /api/private-tasks/extract` with photos. Standard upload validation
   and `_normalize_uploaded_image` (EXIF strip, HEIC, size cap). Photos are
   saved under `uploads/{user}/private/_drafts/{draft_id}/`. Records
   `ai_usage(private_extract)`.
2. Response: `{draft_id, problems[]}`. Nothing is written to `private_tasks`.
   - `is_math_problem=false` or zero problems → 422 with message; draft photos discarded.
   - high `abuse_score` → 422 with message; draft photos discarded.
3. Client shows each problem as a selectable card (pre-selected if only one);
   selected cards expand into editable previews (title, content with live
   KaTeX, source label, category, difficulty).
4. `POST /api/private-tasks` with `{draft_id, tasks: [...]}`. For each task:
   create the row, **copy** the draft photos into the task's own `source/`
   folder, call `generate_private_task_meta` (records `ai_usage(private_meta)`),
   store hints. Draft folder is deleted after success.
5. Unconfirmed draft folders older than 24 h are removed by the orphan sweep.
   Confirming an expired/consumed draft → 410.

### Create flow — typed

Client-side editor with live preview → `POST /api/private-tasks` with
`{tasks: [{title, content, ...}]}` and no `draft_id` → metadata call → saved.

### Rate limits (all configurable in `app/config.py`)

- `rate_limit_private_tasks_per_user_per_day = 10` — counts created tasks.
- `rate_limit_private_extracts_per_user_per_day = 15` — counts extraction calls.
- Grading private tasks shares the existing per-user submission limit (30/day)
  and global limit, since they are `submissions` rows.
- A global daily cap on `ai_usage` rows (`rate_limit_ai_usage_global_per_day = 1000`).
- `ALLOWED_EMAILS` bypass applies as today. Deleted-account quota tombstones
  also carry the new counters.
- Values are initial placeholders to tune in production.

## 3. API and frontend

### API (auth required; ownership enforced; foreign ids → 404)

```
POST   /api/private-tasks/extract               photos -> {draft_id, problems[]}
POST   /api/private-tasks                       create from draft selections or typed -> [task]
GET    /api/private-tasks                       list (paginated): title, source_label, category,
                                                difficulty, best_score, attempts, last_activity_at
GET    /api/private-tasks/{id}                  detail, hint count but NOT hint text
PATCH  /api/private-tasks/{id}                  title, content, source_label, category, difficulty
POST   /api/private-tasks/{id}/hints/{n}        reveal hint n (only n <= revealed+1) -> text;
                                                increments pending_hints_used
POST   /api/private-tasks/{id}/regenerate-hints
DELETE /api/private-tasks/{id}                  task + submissions + all photos
GET    /api/private-tasks/{id}/history          submissions for this task
POST   /private-task/{id}/submit                solution photos -> {submission_id, ws_path}
```

On submit, `pending_hints_used` is copied to `submissions.hints_used` and
reset to 0. Private photos are served by the existing owner-checked
`/uploads/{path}` route (a test confirms another user gets 403/404).
A Next.js route handler proxy is added for the submit route
(`maxDuration=180`), mirroring the OMJ one.

### Frontend (Polish, MUI v7 + Tailwind, KaTeX via `MathContent`)

- **`/moje-zadania`** — list of task cards (title, source label, category
  badge, difficulty stars, best score, last activity) and "Dodaj zadanie".
  Header link next to "Moje rozwiązania", shown only when logged in.
- **`/moje-zadania/nowe`** — tabs *Zdjęcie* / *Wpisz*. Photo: upload → problem
  selection cards → editable previews → save. Typed: textarea + live preview.
- **`/moje-zadania/[id]`** — mirrors the OMJ task page: statement, badge
  "Zadanie prywatne · ocena bez oficjalnego rozwiązania", source label,
  category, collapsible original photos, `HintsSection` adapted to fetch
  hints one at a time, `SubmitSection` parameterised by submit URL,
  submission history. Edit / delete in a menu; delete asks for confirmation.
- **"Moje rozwiązania"** — private submissions listed with the task title,
  linking to `/moje-zadania/[id]`.
- Types added to `frontend/src/lib/types/index.ts` mirroring the Pydantic models.

## 4. Errors, privacy, testing

### Error handling

- Extraction failure (timeout, unparseable, zero problems): draft photos
  discarded via `_discard_uploads`, friendly message; the attempt still
  counts in `ai_usage`.
- Grading failure: existing FAILED submission path.
- Metadata failure at confirm: the task is still saved with `hints = []`;
  the task page offers "Wygeneruj podpowiedzi".
- Validation: content 20–10 000 chars, title ≤ 120, source label ≤ 120,
  category in the allowed set, difficulty 1–5, hints revealed in order.
- Abuse: high extraction/meta `abuse_score` rejects the request; grading
  abuse uses the existing `issue_type` flow and admin view.

### Privacy (RODO)

- Retention: a private task (row, photos, remaining submissions) is deleted
  24 months after `last_activity_at` (`RETENTION_PRIVATE_TASK_MONTHS=24`,
  `0` disables). Raw thinking in `extraction_meta` is stripped with the
  existing 90-day thinking pass. `ai_usage` rows purged after 90 days.
- `sweep_orphan_upload_files` treats `private_tasks.source_images` as
  referenced and removes stale `_drafts/` folders (> 24 h).
- Account erasure: DB cascade plus existing user upload-directory removal;
  test asserts nothing remains on disk or in any table.
- Admin viewing a private task or its submissions is logged in
  `admin_access_log`.
- Update `docs/rodo/dpia.md` (new data categories: task photos, user text,
  hint usage, `ai_usage`; Gemini processing for extraction and hint
  generation), the retention section of `CLAUDE.md`, and config docs.
- No real OMJ or booklet task text in fixtures, tests or fake-Gemini
  responses — invented problems only (CLAUDE.md rule).

### Testing

- **pytest** (in-memory SQLite per file, existing style):
  repositories CRUD and ownership (foreign id → 404); migration constraint;
  every OMJ aggregate query ignores private submissions; retention by
  `last_activity_at`; orphan sweep incl. drafts; full account erasure;
  `ai_usage` limits and allowlist bypass; sequential hint reveal and
  `hints_used` hand-over; extraction output parsing (0, 1, several problems,
  non-math); prompt validation for new prompt files.
- **Fake Gemini** (`e2e/fake-gemini/server.py`): handlers for extraction,
  metadata and private grading.
- **Playwright e2e**: photo with two problems → select both → two tasks;
  typed task; reveal a hint; submit and receive score over WebSocket;
  delete task.
- **Frontend**: `npm run lint`.
