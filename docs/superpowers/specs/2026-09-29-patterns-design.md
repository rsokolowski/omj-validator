# Patterns ("Wzorce") — design

Status: approved in conversation 2026-09-29 (sub-project 2 of the notebook ideas;
sub-project 1 was private tasks, `2026-09-29-private-tasks-design.md`).

## Context and goal

A student keeps a paper/HTML notebook where, for each solved problem, he writes a
*trigger* ("kiedy w treści widzę ___, to warto spróbować ___") and a *key idea*,
and reviews them with a hand-rolled spaced-repetition scheme. Those notes are
really **problem-solving patterns** trapped inside individual task entries.

This feature makes patterns first-class objects in the validator:

1. The student writes a pattern (usually right after solving a task) or asks the
   AI to suggest one from his graded solution.
2. He refines it in **guided rounds** with the AI: each round offers 2–3
   rephrasings to pick from, a verdict, and 0–2 questions back.
3. The AI links the pattern to **OMJ tasks** that exercise it; he accepts or
   rejects each suggestion. Private tasks ("Moje zadania") can be linked too.
4. He **practises** patterns with spaced repetition: quick self-rated recall
   cards by default, and periodically a graded linked task whose score feeds
   the schedule.

Success = the student reuses patterns on new problems, not just memorises their
wording. Hence recall + graded application.

### Decisions made

| Question | Decision |
|---|---|
| Audience | All validator users (public feature): limits, abuse checks, RODO from day one |
| What is practice | **Mix**: recall cards by default; a graded linked task every few reviews / on demand; its result counts as a review |
| Refinement | **Guided rounds** (structured JSON per round), not free chat |
| OMJ links | AI suggests 3–5 from a server-side prefiltered candidate list; student confirms |
| Entry points | "Zapisz wzorzec" on every task page (pre-linked) + a `/wzorce` page |
| AI-suggested patterns | Yes, **on request** ("Podpowiedz wzorzec") after grading; grading prompt untouched |
| Recall grading | Student self-rates (3 buttons), no AI call |
| Architecture | Dedicated `app/patterns/` module mirroring `app/private_tasks/` |
| Visibility | Private to the owner; no sharing |

### Out of scope

- Sharing patterns between students, a curated global pattern catalogue.
- Competition-stage-date boosts (the notebook's "7 days before each stage").
- Reviewing whole tasks with spaced repetition (a generic card engine).
- Free-form chat.
- OIJ / programming content from the notebook.

## 1. Data model (Alembic `007_add_patterns.py`)

### New table `patterns`

| Column | Type | Notes |
|---|---|---|
| `id` | String(12) PK | `secrets.token_urlsafe(9)`, like private tasks |
| `user_id` | FK users.google_sub, CASCADE, indexed | owner |
| `trigger` | Text, not null | 5–300 chars — "Kiedy w treści widzę…" |
| `action` | Text, not null | 5–600 chars — "…to warto spróbować…" |
| `example` | Text, null | ≤1000 chars, may contain `$LaTeX$` |
| `category` | String(20), null | one of the 6 task categories |
| `skills` | JSON list[str], default [] | ≤3 ids from `data/skills.json` (set by the refine round, editable) |
| `origin` | String(16) | `own` \| `ai_suggested` |
| `refinement` | JSON list, default [] | ≤10 rounds (see §2), oldest dropped first |
| `srs_level` | SmallInteger, default 1 | 1, 2, 3, 4 (= maintenance) |
| `srs_streak` | SmallInteger, default 0 | 0 or 1 successes in a row at this level |
| `due_on` | Date, indexed | next review date (Europe/Warsaw calendar day) |
| `review_count` | Integer, default 0 | |
| `lapse_count` | Integer, default 0 | number of `fail` outcomes |
| `last_reviewed_at` | DateTime, null | |
| `archived_at` | DateTime, null | paused; excluded from the queue |
| `created_at`, `updated_at`, `last_activity_at` | DateTime | `last_activity_at` drives retention |

Index `(user_id, due_on)` for the queue.

### New table `pattern_links`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `pattern_id` | FK patterns.id, CASCADE, indexed | |
| `task_key` | String(32), null | OMJ key `"{year}_{etap}_{num}"` |
| `private_task_id` | FK private_tasks.id, CASCADE, null | must belong to the same user (checked in code) |
| `role` | String(10) | `source` \| `practice` |
| `origin` | String(8) | `ai` \| `manual` |
| `status` | String(10) | `suggested` \| `accepted` \| `rejected` |
| `reason` | Text, null | AI's one-line "why this task", ≤300 chars |
| `created_at` | DateTime | |

- Check constraint `ck_pattern_links_ref`: exactly one of `task_key`, `private_task_id` is set.
- Unique `(pattern_id, task_key)` and `(pattern_id, private_task_id)`.
- Rejected rows are kept so the AI never re-suggests them; they are hidden in the UI.
- A `source` link is created `accepted`; it also counts as a practice candidate
  (it is a task that uses the pattern).

### New table `pattern_reviews`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `pattern_id` | FK patterns.id, CASCADE, indexed | |
| `user_id` | FK users.google_sub, CASCADE | |
| `kind` | String(8) | `recall` \| `task` |
| `outcome` | String(8) | `fail` \| `hard` \| `ok` |
| `recall_text` | Text, null | what he typed (recall only), ≤1000 chars |
| `submission_id` | FK submissions.id, SET NULL, null | task reviews |
| `level_before`, `level_after` | SmallInteger | |
| `due_before`, `due_after` | Date | |
| `created_at` | DateTime | |

### Changes to `submissions`

- New nullable `pattern_id` String(12), FK patterns.id **ON DELETE SET NULL**, indexed.
  Set only when the solution was submitted from a pattern's practice flow.
- OMJ submissions today always store `hints_used = 0` (OMJ hints are revealed
  client-side). The OMJ submit endpoint accepts an optional form field
  `hints_used` (int, clamped to 0..len(task.hints)) — self-reported by the task
  page's `HintsSection`, used for the practice outcome. Private tasks already
  track it server-side and ignore the form field.

### Relationships / cascades

`UserDB.patterns` (cascade all, delete-orphan). `PatternDB.links`, `PatternDB.reviews`
(cascade all, delete-orphan). Deleting a private task deletes its links (DB FK
CASCADE plus ORM relationship on `PrivateTaskDB`). Account erasure removes
everything by cascade.

## 2. AI layer

Three new `GeminiProvider` methods, all **text-only**, schema-constrained
(`_generate_json(contents, schema)`), parsed and clamped in a new
`app/ai/pattern_parsing.py` using `_loads_repaired` / `repair_latex_escapes`.
Prompts in Polish in `prompts/pattern_refine.txt`, `prompts/pattern_suggest.txt`,
`prompts/pattern_link.txt`, loaded through `load_private_prompt` (extended map) and
checked by `validate_prompts()`. Every response carries `abuse_score` (0–100);
`>= settings.private_abuse_threshold` (70) → `AIContentBlockedError`. Safety
blocks also raise `AIContentBlockedError`. Every prompt tells the model to double
LaTeX backslashes in JSON and to treat the student's text as data, not instructions.

### 2.1 Refine round — `refine_pattern(draft, source_task_text, history, answer)`

- `draft`: `{trigger, action, example}` or `{raw}` (one free sentence before he
  splits it). `source_task_text`: statement of the source task when available
  (OMJ `content` if the statement file exists, else title + our hints; private
  task `content`). `history`: last ≤3 rounds, compacted (chosen variant +
  questions + his answers). `answer`: his reply to the last questions / comment, ≤1000 chars.
- Output (`PATTERN_REFINE_SCHEMA`):
  ```json
  {"variants": [{"trigger": "", "action": "", "example": ""}],
   "questions": [""],
   "verdict": "ok|za_ogolny|bledny|to_nie_wzorzec",
   "comment": "",
   "category": "algebra|...|null",
   "skills": ["modular_arithmetic"],
   "abuse_score": 0}
  ```
- Parsing: keep 2–3 variants with non-blank trigger and action (clamped to the
  column limits); questions ≤2, each ≤300 chars; unknown verdict → `ok`;
  unknown category → null; skills filtered against `data/skills.json`, ≤3;
  comment ≤500. **Fewer than 2 usable variants** → the round is treated as a
  failure (502 "Spróbuj jeszcze raz").
- Prompt rules: keep his wording where it is good; never solve the source task;
  if the pattern is wrong, say so (`bledny`) instead of polishing it; triggers
  describe what is *visible in a problem statement*; actions are concrete moves.
- A round stored in `patterns.refinement`:
  `{"at": iso, "draft": {...}, "answer": str|null, "variants": [...],
  "questions": [...], "verdict": str, "comment": str, "chosen": int|null}`.

### 2.2 Suggest from a solution — `suggest_patterns(task_text, feedback, draft)`

- Input: task text (as above; for OMJ also the official solution is **not** sent),
  the graded submission's `feedback`, and the draft he typed (may be empty).
  No photos.
- Output (`PATTERN_SUGGEST_SCHEMA`):
  `{"suggestions": [{"trigger","action","example","why"}], "abuse_score": 0}`;
  1–3 kept; `why` ≤300 chars. Zero usable → 502.
- An accepted suggestion becomes the editor's draft with `origin = ai_suggested`;
  from there it goes through normal refine rounds.

### 2.3 Link OMJ tasks — `link_pattern_tasks(pattern, candidates)`

- **Server-side candidate selection** (`app/patterns/linking.py`, pure given inputs):
  1. all loaded OMJ tasks (`storage._load_all_tasks()` values);
  2. drop tasks already linked to the pattern (any status, incl. rejected);
  3. score each: +3 per skill shared with `pattern.skills` (`skills_required` ∪
     `skills_gained`), +2 if it shares `pattern.category`; drop score 0;
  4. order: tasks the user has **no completed submission** for first, then by
     score desc, then difficulty asc; take 40.
- Sent per candidate: `task_key`, `difficulty`, `categories`, and our hints 2–3
  (strategy/direction; MIT metadata). No statements.
- Output (`PATTERN_LINK_SCHEMA`): `{"links": [{"task_key","reason"}], "abuse_score": 0}`;
  keys not in the candidate set dropped; ≤5 kept; duplicates dropped; `reason` ≤300.
- Stored as `pattern_links(role=practice, origin=ai, status=suggested)`.
- Empty candidate list → no AI call, no usage, returns `[]`.

### Rate limits (`app/config.py`, env-overridable)

| Setting | Default | `ai_usage.kind` |
|---|---|---|
| `rate_limit_pattern_refines_per_user_per_day` | 30 | `pattern_refine` |
| `rate_limit_pattern_suggests_per_user_per_day` | 10 | `pattern_suggest` |
| `rate_limit_pattern_links_per_user_per_day` | 10 | `pattern_link` |

Each uses `service.reserve_ai_calls` (insert, then count, release + 429 if over);
all count toward `rate_limit_ai_usage_global_per_day`; allowlisted users bypass
the per-user limits. As for private tasks, a call that was made still counts
when it fails or is refused (it still cost Gemini money); only a reservation
refused by the limit itself is released. Recall reviews make no AI calls.

## 3. Spaced repetition (`app/patterns/srs.py`, pure)

```
INTERVALS = {1: (1, 4), 2: (7, 14), 3: (30, 90)}
MAINTENANCE = 4; MAINTENANCE_DAYS = 180

schedule(level, streak, outcome, today) -> (level, streak, due_on)
```

- New pattern: level 1, streak 0, `due_on = today + 1`.
- `ok`: streak 0 → streak 1, `due = today + INTERVALS[level][1]`.
  streak 1 → level + 1 (3 → 4), streak 0, `due = today + first interval of new level`
  (level 4: 180). At level 4 `ok` → stays 4, `due = today + 180`.
- `hard`: level and streak unchanged, `due = today + INTERVALS[level][streak]`
  (level 4: 180).
- `fail`: level 4 → 2, 3 → 2, 2 → 1, 1 → 1; streak 0;
  `due = today + INTERVALS[new_level][0]`; `lapse_count += 1`.
- "today" = current date in `Europe/Warsaw` (`zoneinfo`).

### Grade → outcome (`outcome_from_grade(score, max_score, hints_used)`)

"Solved" = `score >= 5` on the 6-point scale, `score == 3` on the etap1 scale
(max 3). Private tasks use the 6-point scale.

| Result | Outcome |
|---|---|
| solved, `hints_used == 0` | `ok` |
| solved with hints, or partial (score > 0 but not solved) | `hard` |
| score 0 | `fail` |

A graded practice task counts **whenever it happens** (even before `due_on`).
Failed gradings (status FAILED) do not count. A submission applies at most once
(a `pattern_reviews` row with that `submission_id` already existing → no-op).

### Practice offer (`choose_practice(pattern, links, attempts, today)`)

- Offered when `review_count % 3 == 2` or `srs_level == 4`, and the pattern has
  an accepted link (practice or source) whose task has **no submission by this
  user in the last 30 days**.
- Pick: a never-attempted task first (OMJ before private, then difficulty asc),
  else the one whose last attempt is oldest.
- The card always lets him decline ("Wolę szybką powtórkę") and the pattern
  page lets him pick any linked task at any time.

### Queue (`GET /api/patterns/queue`)

- `due_on <= today`, `archived_at IS NULL`, owner only.
- Order: most overdue first (`due_on` asc, then `created_at`), then **interleave
  categories**: greedy — take the next item whose category differs from the
  previous one, else the next item.
- Returns the first `limit` (default 10, ≤50) plus `due_total`.
- A recall review is accepted only when due: `POST /review` on a not-due or
  archived pattern → 409. The update is conditional
  (`UPDATE ... WHERE id=:id AND due_on=:seen_due_on`), so a double click counts once.

## 4. API and frontend

### API — `app/patterns/routes.py`, prefix `/api/patterns`

Auth + group membership as private tasks (`current_member_id`); someone else's
id → 404.

| Method & path | Purpose |
|---|---|
| `POST /refine` | Body `{draft, source: {task_key}\|{private_task_id}\|null, history, answer, pattern_id?}` → round. Stateless before saving; with `pattern_id` (owned) the source and history come from the stored pattern. |
| `POST /suggest` | Body `{submission_id, draft?}`; submission must be the user's own and COMPLETED → `{suggestions}` |
| `POST ""` | Create `{trigger, action, example?, category?, skills?, origin, source?, refinement?}` → pattern (201). Creates the `source` link. Does **not** call the AI. |
| `GET ""` | List `?category=&archived=&task_key=&private_task_id=` with link counts (the last two: patterns linked to that task, any role, accepted) |
| `GET /queue` | `{items, due_total}` |
| `GET /{id}` | Detail + links (with task titles; unknown OMJ keys flagged `available: false`) + last 20 reviews |
| `PATCH /{id}` | Edit fields; `append_round` (a round from `/refine` with `chosen`); `archived: bool`. Editing trigger/action does not reset the schedule. |
| `DELETE /{id}` | Pattern + links + reviews (submissions keep their row, `pattern_id` → NULL) |
| `POST /{id}/suggest-links` | AI link suggestion (§2.3) → new suggested links |
| `POST /{id}/links` | Manual link `{task_key}` (must exist) or `{private_task_id}` (owned), `role=practice`, `accepted` |
| `PATCH /{id}/links/{link_id}` | `{status: accepted\|rejected}` |
| `DELETE /{id}/links/{link_id}` | Remove |
| `POST /{id}/review` | `{recall_text (10..1000 chars), outcome}` → updated schedule; 409 when not due |
| `GET /{id}/practice` | `{task: {kind: omj\|private, key/id, title}}` or `{task: null}` |

Submit endpoints: `POST /task/{y}/{e}/{n}/submit` and
`POST /api/private-tasks/{id}/submit` take an optional form field `pattern_id`;
it is stored only if the pattern belongs to the submitting user (otherwise
silently ignored). OMJ submit also takes `hints_used` (see §1).

Worker hook: `app/websocket/handler.py`, after marking a submission COMPLETED,
calls `app.patterns.service.apply_practice_result(db, submission)` inside
`try/except` — any error is logged and never affects grading. It computes the
outcome (§3), applies `schedule`, writes a `task` review, bumps
`last_activity_at`.

Request/response models in `app/models.py` (`PatternDraft`, `PatternCreate`,
`PatternUpdate`, `RefineRequest`, `RefineRound`, `ReviewRequest`, ...) with the
length limits of §1.

### Frontend (Polish, MUI v7 + Tailwind, `MathContent` for every text)

- Header: "Wzorce" link (when authenticated and a member) with a badge = `due_total`.
- `/wzorce`: banner "Do powtórki dziś: N → Zacznij", list of patterns (trigger,
  category badge, level chip "Poziom 1/2/3/Utrwalony", next date), filters,
  "Nowy wzorzec".
- `/wzorce/nowy?task=KEY|private=ID`: `PatternEditor` (trigger / action / example)
  + `RefinePanel`: each round shows variant cards (with "Wybierz" → loads it into
  the editor), verdict chip + comment, questions + an answer field, "Kolejna
  runda". Save → pattern page, which immediately calls `suggest-links`.
- `/wzorce/[id]`: pattern, "Dopracuj z AI" (a round on the stored pattern),
  links grouped (Źródło / Do ćwiczeń / Propozycje AI with reason + ✓/✕),
  "Znajdź więcej zadań", "Dodaj zadanie" (OMJ key picker from year/etap/number
  or a private task select), review history, "Wstrzymaj/Wznów", "Usuń".
- `/wzorce/powtorka`: one card at a time from the queue.
  - Recall: shows the trigger; textarea (≥10 chars) → "Pokaż" → his text beside
    the saved action/example → "Nie pamiętałem / Z trudem / Pamiętałem".
  - If `/practice` returns a task: "Rozwiąż zadanie" (→ task page with
    `?wzorzec=ID`) or "Wolę szybką powtórkę" (→ recall card).
  - End: "Na dziś wszystko".
- Task pages (OMJ `task/[year]/[etap]/[num]` and `moje-zadania/[id]`):
  - with `?wzorzec=ID`: banner "Ćwiczysz wzorzec: <trigger>"; `SubmitSection`
    sends `pattern_id` (and OMJ `hints_used` from `HintsSection`).
  - under a completed submission: `SavePatternBox` — "Zapisz wzorzec" (opens
    `/wzorce/nowy` pre-linked) and "Podpowiedz wzorzec" (calls `/suggest`,
    shows suggestion cards, "Użyj" → `/wzorce/nowy` with the draft).
  - "Twoje wzorce z tego zadania" list (patterns with a link to the task).
- Next.js route handlers under `src/app/api/patterns/` proxy to FastAPI
  (`proxyToBackend`; `maxDuration` 120 for AI routes).

## 5. Errors, privacy, testing

### Error handling

| Situation | Response |
|---|---|
| AI error / timeout / unusable output | 502 Polish message (the call still counts) |
| Abuse score ≥ 70 or safety block | 422 "Tej treści nie możemy przetworzyć." (counts) |
| Per-user or global limit | 429 + `Retry-After` / rate-limit headers |
| Review of a not-due / archived pattern, or lost race | 409 |
| Someone else's pattern / link / private task / submission | 404 |
| Unknown OMJ key on manual link | 404 |
| Foreign `pattern_id` on submit | ignored, submission proceeds |
| `apply_practice_result` raises | logged, grading unaffected |
| Linked OMJ task no longer loaded | shown as "zadanie niedostępne", never raises |

### Privacy (RODO)

- New personal-data categories: pattern text, refine history (includes AI
  output and his answers), typed recall answers, review log.
- Sent to Gemini: pattern drafts, his answers, source task text, grading feedback.
  No photos, no identifiers.
- Retention: `retention_pattern_months = 24` (env `RETENTION_PATTERN_MONTHS`),
  counted from `patterns.last_activity_at` (bumped by edits, rounds, reviews,
  practice results); purge deletes pattern + links + reviews. `0` disables
  (dev/e2e compose files).
- Account erasure: cascades. `ai_usage` stays content-free (three new kinds).
- Update `docs/rodo/dpia.md` (tables, Gemini transfer, retention row, risk entry),
  `/regulamin` privacy page (new section, LAST_UPDATED), `CLAUDE.md`,
  `docs/database-schema.md`, `.env.example`, compose files.

### Testing

- `tests/test_pattern_srs.py`: table of level × streak × outcome; promotion after
  two `ok`; demotion from maintenance; `hard` keeps state; grade → outcome for
  both scales and hints; queue interleaving; practice choice (30-day rule,
  never-attempted first).
- `tests/test_pattern_repository.py`: ownership, link check constraint and
  uniqueness, cascades (pattern delete, private task delete, user delete,
  `submissions.pattern_id` → NULL), conditional review update.
- `tests/test_pattern_ai.py`: parsing/clamping for the three schemas, too-few
  variants, invented task keys dropped, abuse score, LaTeX repair, requests are
  text-only with the right schema, prompt files present.
- `tests/test_pattern_linking.py`: candidate selection and ordering.
- `tests/test_pattern_api.py`: every route, 404 on foreign ids, 409 early review,
  racing limit reservations, `pattern_id`/`hints_used` on both submit endpoints,
  worker hook (applies once; failure does not break grading).
- `tests/test_pattern_retention.py`: purge by `last_activity_at`.
- e2e `e2e/tests/patterns.spec.ts` with fake-Gemini responses for the three new
  schemas (invented problems only): grade a task → "Podpowiedz wzorzec" → use a
  suggestion → refine round → save → accept AI links → review card (pattern
  made due via a test-only endpoint) → graded practice changes the level.
