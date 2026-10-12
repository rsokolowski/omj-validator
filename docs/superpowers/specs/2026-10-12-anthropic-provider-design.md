# Anthropic (Claude) provider and runtime AI model switch — design

Date: 2026-10-12
Status: approved in discussion, awaiting written-spec review

## Context and goal

Every AI call the running app makes goes to Gemini. `create_ai_provider()`
(`app/ai/factory.py`) is a process-wide singleton built once from
`settings.ai_provider`, and changing the model means editing `.env` and
restarting. A Claude provider existed for one day (`8000b56`, removed in
`d281f99`, 2025-12-07, Claude CLI based) and was never compared with Gemini;
every model A/B since (`docs/model-ab-2026-09-05.md`) has been Gemini vs Gemini.

This feature adds:

1. an `AnthropicProvider` implementing the whole `AIProvider` protocol,
2. a persistent, admin-editable choice of provider + model that takes effect
   without a restart,
3. provider-agnostic A/B tooling, so Claude can be measured against the
   human-graded sample before it is switched on in prod,
4. the GDPR documents and `/regulamin` updated to name Anthropic as a second,
   alternative processor.

### Decisions made

| Question | Decision |
|---|---|
| Switch granularity | One global `{provider, model}` for every call the running app makes |
| What it covers | OMJ scoring, private-task grading, private-task extraction and hints ("Moje zadania"), patterns ("Wzorce") |
| What it does not cover | Offline scripts (`populate_metadata*.py`, `fix_latex_content.py`, `review_hints.py`) |
| Model choice | Curated list only, no free text |
| Curated models | Gemini: `gemini-3.8-flash`, `gemini-3.1-pro-preview`. Claude: `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` |
| Storage | New `app_settings` table, one row `ai_model` |
| Default without a row | `AI_PROVIDER` + `GEMINI_MODEL` from the environment, exactly as today |
| API keys | Environment only (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`); never in the DB, never in the UI |
| Provider structure | Separate `AnthropicProvider` class; provider-neutral pieces extracted from `gemini.py` |
| A/B tooling | `rescore_eval.py`, `ab_compare.py` take `--provider` / `--model` |
| GDPR | Documents updated in this work; selecting Claude is blocked until `ANTHROPIC_PROCESSOR_APPROVED=true` |

## 1. Runtime configuration

### Table `app_settings`

| column | type | notes |
|---|---|---|
| `key` | `String(64)` PK | `"ai_model"` is the only key for now |
| `value` | `JSONB` | `{"provider": "anthropic", "model": "claude-opus-5-5"}` |
| `updated_at` | `DateTime(tz)` | server default `now()` |
| `updated_by` | `String` nullable | admin's e-mail; null for seeds |

Alembic migration creates the table, no seed row. `AppSettingsRepository`
in `app/db/repositories.py`: `get(key) -> Optional[dict]`,
`set(key, value, updated_by)` (upsert).

### `app/ai/config_store.py`

```python
@dataclass(frozen=True)
class ActiveModel:
    provider: str            # "gemini" | "anthropic"
    model: str
    source: str              # "db" | "env"
    updated_at: datetime | None
    updated_by: str | None

def get_active_model() -> ActiveModel      # TTL-cached, 30 s
def set_active_model(provider, model, updated_by) -> ActiveModel  # writes + drops cache
```

- `get_active_model()` reads the row through a short-lived session; on no row,
  an unknown model, or a DB error it falls back to the environment
  (`settings.ai_provider`, `settings.gemini_model`) and logs a warning — a
  broken config row must never stop grading.
- The 30 s TTL is what makes a switch visible to other workers. Prod runs one
  gunicorn worker, so in practice the change is immediate (the cache is dropped
  on write in the same process).

## 2. Model catalog — `app/ai/models_catalog.py`

Single source of truth for the dropdown, validation and cost estimates.

```python
@dataclass(frozen=True)
class ModelInfo:
    provider: str
    id: str
    label: str
    pricing: dict   # USD per 1M tokens, same shape as GEMINI_PRICING entries

CATALOG: tuple[ModelInfo, ...]
def get_model(provider, model) -> ModelInfo | None
def models_for(provider) -> list[ModelInfo]
```

| provider | id | label | input / output $/1M |
|---|---|---|---|
| gemini | `gemini-3.8-flash` | Gemini 3.8 Flash | `_FLASH_PRICING` (promo through 2026-12-31) |
| gemini | `gemini-3.1-pro-preview` | Gemini 3.1 Pro (preview) | 2.00 / 12.00, long tier 4.00 / 18.00 above 200k |
| anthropic | `claude-opus-5-5` | Claude Opus 5.5 | 4.00 / 20.00 |
| anthropic | `claude-sonnet-5-5` | Claude Sonnet 5.5 | 2.00 / 10.00 |
| anthropic | `claude-haiku-5-5` | Claude Haiku 5.5 | 0.10 / 0.50 (0.50 / 2.50 above 100k input) |

`GEMINI_PRICING` stays in `gemini.py` (the A/B scripts and older `scoring_meta`
rows reference models that are no longer selectable); the catalog's Gemini
entries point at it. Claude cache reads are priced from the same table
(`cache_read` key; 0.1x input) so the estimate is not inflated by caching.

`GEMINI_MODEL` from the environment may name a model outside the catalog
(e.g. `gemini-3.7-flash`); that keeps working as the env fallback, the admin
page shows it as "z konfiguracji serwera" and simply cannot select it again.

## 3. Factory

`create_ai_provider()` keeps its name and signature (all call sites and test
monkeypatches stay valid):

```python
_instances: dict[tuple[str, str], AIProvider] = {}

def create_ai_provider() -> AIProvider:
    active = get_active_model()
    key = (active.provider, active.model)
    if key not in _instances:
        _instances[key] = _build(active.provider, active.model)
    return _instances[key]
```

- `_build` raises `AIProviderError` when the provider's API key is missing,
  same as today for Gemini.
- Selecting Claude while `ANTHROPIC_PROCESSOR_APPROVED` is false: the factory
  logs an error and falls back to the env Gemini model rather than send data to
  an unapproved processor (defence in depth; the admin endpoint already refuses
  to save it, section 6).
- A grading run that already holds an instance finishes on it; the next call
  picks up the new one. Old instances stay cached (at most five models — no
  eviction needed).
- `GeminiProvider.__init__` and `AnthropicProvider.__init__` take `model: str`
  instead of reading `settings.gemini_model` directly.
- `warm_ai_provider()` in `app/main.py` keeps warming whatever is active.

## 4. Shared, provider-neutral pieces

Extracted from `gemini.py` so both providers send the same prompt and parse the
same shape — the precondition for a fair A/B:

| new module | moved out of `gemini.py` |
|---|---|
| `app/ai/schemas.py` | `RESPONSE_JSON_SCHEMA` and the extraction / meta / refine / suggest / link schemas |
| `app/ai/prompt_builder.py` (exists) | prompt loading (`_load_prompt`), `_student_text`, `_draft_text`, `_answers_text`, `_conversation_text` and the text assembly of each call |
| `app/ai/parsing.py` (exists) | anything left in `gemini.py` that turns raw JSON into `SubmissionResult` / private / pattern results |

What stays Gemini-only: File API upload + 24h cache, media resolution ladder,
inline-image budget, `thinking_level`, Gemini error mapping, `GEMINI_PRICING`.

The extraction is a refactor: Gemini behaviour, prompts and outputs must stay
byte-identical, verified by the existing test suite plus a new test that the
Gemini request contents for a fixed input are unchanged (snapshot taken before
the refactor).

## 5. `AnthropicProvider` — `app/ai/providers/anthropic.py`

Uses the official `anthropic` SDK (`AsyncAnthropic`), pinned in
`requirements.txt`. Configuration:

| setting | default | meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | required to build the provider |
| `ANTHROPIC_EFFORT` | `high` | `output_config.effort` for grading calls |
| `ANTHROPIC_EFFORT_AUX` | `medium` | effort for extraction, hints, patterns |
| `ANTHROPIC_TIMEOUT` | `180` | seconds; `get_timeout()` returns it |
| `ANTHROPIC_PROCESSOR_APPROVED` | `false` | GDPR gate, sections 3 and 6 |

### Request shape

- **Grading** (`analyze_solution`, `analyze_solution_stream`,
  `analyze_private_solution_stream`): one user message containing, in the same
  order as the Gemini call, the task PDF and official-solution PDF as base64
  `document` blocks (OMJ only), the student photos as base64 `image` blocks,
  then the prompt text and the fenced `<rozwiazanie_ucznia>` block from
  `prompt_builder.solution_text_block`. The instruction part goes in `system`.
- `cache_control: {"type": "ephemeral"}` on the last PDF block, so repeated
  submissions to the same task reuse the PDF prefix.
- `thinking: {"type": "adaptive", "display": "summarized"}`; streamed
  `thinking_delta` text goes to `on_thinking`, which feeds the existing
  WebSocket path (headings + optional translation) unchanged. `on_upload_complete`
  is called right before the request is sent (there is no upload step).
- Structured output through `output_config.format` with the shared JSON schema;
  the parsed JSON goes through the same `parsing.py` normalisation as Gemini.
- Streaming for all grading calls (`messages.stream`, `get_final_message()`),
  `max_tokens` 64000.
- Non-grading calls (`extract_private_tasks`, `generate_private_task_meta`,
  `refine_pattern`, `suggest_patterns`, `link_pattern_tasks`): non-streaming
  `messages.create`, `max_tokens` 16000, effort `ANTHROPIC_EFFORT_AUX`, same
  schemas.
- Refusal fallback: `betas=["server-side-fallback-2026-07-01"]`,
  `fallbacks="default"` on Opus 5.5 / Sonnet 5.5 (not Haiku, which has no
  server-side fallback). A final `stop_reason == "refusal"` raises
  `AIContentBlockedError` — the same contract as a Gemini safety block.
- Images: photos are already sanitised JPEG/PNG/WebP from `app/uploads.py`;
  HEIC is converted on upload. Images over the Messages API per-image size /
  dimension limits (take the current values from the API docs at implementation
  time) are downscaled in memory before encoding, never on disk.

### Errors

`anthropic.RateLimitError`, `APIStatusError >= 500`, `APIConnectionError`,
`APITimeoutError` -> `AIProviderError` with the same Polish user-facing
messages `GeminiProvider._friendly_error` produces; `BadRequestError` ->
`AIProviderError` with a generic message and the detail in the log.
`AuthenticationError` -> `AIProviderError("Błąd konfiguracji dostawcy AI")`.
SDK retries (default 2) stay on.

### `scoring_meta`

Both providers write `provider`, `model`, `input_tokens`, `output_tokens`,
`cache_read_tokens` (Claude) / `thoughts_tokens` (Gemini), `cost_usd`,
`api_time`, `total_time`, `thinking`. Adding `provider` to Gemini rows is the
only change on the Gemini side; rows without it are Gemini by definition.

## 6. Admin API and UI

### API (`app/main.py`, admin section)

```
GET /api/admin/ai-config
  -> {active: {provider, model, source, updated_at, updated_by},
      providers: [{id, label, configured, approved,
                   models: [{id, label}]}]}

PUT /api/admin/ai-config   body {provider, model}
  -> 200 {active: ...}
  -> 400 model not in catalog
  -> 409 provider API key not configured, or anthropic not approved (GDPR gate)
  -> 502 test call failed (message from the provider error)
```

- Both behind `_require_admin`.
- `PUT` runs a test call before saving: a new protocol method
  `async ping() -> None` on both providers sends one minimal request
  ("Odpowiedz: OK", small `max_tokens`, lowest effort) to the chosen model
  through a freshly built provider, with a 30 s timeout. Any non-error response
  counts as success (a `max_tokens` stop is fine — thinking may use the budget);
  an exception means 502 and nothing is saved.
- The change is logged at INFO (`AI model changed: gemini/gemini-3.8-flash ->
  anthropic/claude-opus-5-5 by <admin e-mail>`). It is not written to
  `admin_access_log` — that table records access to other users' data, which
  this is not; `app_settings.updated_by/updated_at` keep the last change.

### UI — `frontend/src/app/admin/settings/page.tsx`

- Link from the existing admin page header ("Ustawienia AI").
- Shows the active provider + model, its source (baza / konfiguracja serwera),
  who changed it and when.
- Provider radio + model select (models of the chosen provider). A provider
  with no key or not approved is disabled with the reason as helper text.
- "Zapisz" -> spinner "Sprawdzam model…" -> success toast or the error from
  the API. No optimistic update.
- Types in `frontend/src/lib/types/index.ts`, fetchers in
  `frontend/src/lib/api/client.ts`.

## 7. A/B tooling

- `scripts/rescore_eval.py`: `--provider {gemini,anthropic}` and `--model`
  (catalog ids, plus any id for Gemini as before); builds the provider through
  `factory._build`, so prompts and parsing are identical to prod. Token usage
  and cost come from the result's `scoring_meta` instead of monkeypatching
  `generate_content`.
- `scripts/ab_compare.py`: cost from the catalog pricing; output columns
  labelled `provider/model`.
- `docs/model-ab-playbook.md`: how to run a Claude arm; note that the A/B runs
  send prod photos to Anthropic, so they need the same GDPR approval as prod use.

## 8. GDPR documents and `/regulamin`

Wording principle: the service uses **one** AI provider at a time, chosen by the
administrator from two: Google (Gemini) or Anthropic (Claude). Both are
processors; the same data categories go to whichever is active; no account
identifiers go to either.

Facts about Anthropic used in the texts (checked 2026-10-12 against primary
sources; re-check before publishing):

- Commercial Terms (effective 2025-06-17): contracting entity for EEA customers
  is **Anthropic Ireland, Limited**; "Anthropic may not train models on
  Customer Content from Services"; the DPA is incorporated by reference.
- DPA (effective 2025-02-24): transfers outside the EEA under the **Standard
  Contractual Clauses**, Module Two (controller -> processor) and/or Module
  Three (processor -> processor); subprocessors listed at
  anthropic.com/subprocessors, 15-day objection window.
- Retention (privacy.claude.com, updated 2026-07-01): API inputs and outputs
  deleted **within 30 days**, except Files API (not used here), a separate
  agreement, Usage Policy enforcement, or legal obligation.
- EU-US Data Privacy Framework: Anthropic's participation was **not
  confirmed** — the texts rely on SCCs and the DPIA lists checking the DPF
  register as an action item.
- The app sends photos inline (base64), never through the Files API, so no
  file is stored at Anthropic beyond the 30-day log window.

### `docs/rodo/dpia.md`

- Context (sections ~1, ~2): "model AI (Google Gemini **lub** Anthropic
  Claude — jeden aktywny w danym momencie, wybierany przez administratora)".
- Processor table (~line 327): new row "Anthropic Ireland, Limited / Anthropic,
  PBC — Claude API" with the same data categories as Gemini, retention up to
  30 days, transfer basis SCCs (DPA Module 2/3); no File API.
- Data-flow diagram (~354-385): the AI arrows read
  `[Google Gemini — USA / DPF] lub [Anthropic Claude — USA / SCC]`.
- R6 (transfer to the US): add Anthropic — basis SCCs rather than an adequacy
  decision, so a transfer impact assessment note is needed; measures: no
  identifiers, inline transfer, 30-day deletion, no training; verify DPF status
  at each review. The existing "plan awaryjny" bullet is now partly met (a
  second provider exists; both are US — the EEA-provider gap stays
  [UZUPEŁNIĆ]).
- New short risk entry: **switching provider is a change of processor** —
  measure: the `ANTHROPIC_PROCESSOR_APPROVED` gate, and a switch recorded with
  who/when in `app_settings`.
- Section on the paid tier (~333-344) gets a parallel paragraph for Anthropic
  (commercial terms: no training; 30-day retention vs Gemini's 55-day abuse
  logs).

### `docs/rodo/klauzula-informacyjna-szkola.md`

- Recipients table (~line 102): add an "Anthropic (Claude API)" row, same
  structure as the Google row, 30-day retention, no training; a sentence that
  only one of the two receives a given solution.
- Transfer paragraph (~131): add SCCs as the basis for Anthropic.

### `docs/rodo/regulamin-szkola.md`

- Line ~116: "(model językowy dostarczany przez Google **lub Anthropic**)".

### `frontend/src/app/regulamin/page.tsx`

- Section 2 (~line 75) and 4 (~158): "do firmy Google **albo Anthropic**",
  "(model językowy Google Gemini **lub Anthropic Claude**)".
- Section 7: the Gemini paragraph becomes "Dostawca analizy rozwiązania (AI)"
  with two sub-items — Google (Gemini API), as today, and Anthropic (Claude
  API): no identifiers, sent inline (no stored files), deleted within 30 days,
  not used for training; one provider at a time.
- Transfer section (~508): Anthropic under SCCs.
- "Ostatnia aktualizacja" date bumped.

### `docs/rodo/README.md`

- One line in the changelog / document list noting the second provider.

The child-facing `/regulamin` text is user-facing prose: per the standing rule
it is reviewed by a separate reviewer before it ships.

## 9. Testing

Backend (pytest, existing fixtures):

- `test_ai_config_store.py`: env fallback with no row; DB row wins; unknown
  model in the row falls back; TTL cache dropped on `set`.
- `test_ai_factory.py`: instance per `(provider, model)`; switching returns the
  new instance; missing key -> `AIProviderError`; unapproved anthropic falls
  back to env Gemini.
- `test_admin_ai_config.py`: 401/403 for non-admin; 400 unknown model; 409
  missing key / unapproved; 502 when the test call fails (stub provider) and
  nothing is saved; 200 saves `updated_by`.
- `test_anthropic_provider.py`, against a stubbed `AsyncAnthropic`: request
  contents for OMJ grading (PDF blocks, image blocks, solution text block,
  cache_control, schema, effort, fallbacks only on Opus/Sonnet); private
  grading without PDFs; thinking deltas reach `on_thinking`; refusal ->
  `AIContentBlockedError`; error mapping; `scoring_meta` fields and cost.
- Gemini request snapshot test (section 4) taken before the refactor.
- `tests/test_task_content_split.py` keeps passing (no task text in fixtures —
  stubs use invented problems).

Frontend: `npm run lint` + `tsc`; the settings page is small enough that a
Playwright check in the dev stack (switch, see toast, reload, value persisted)
replaces unit tests.

Manual, with the real key: one `rescore_eval.py --provider anthropic --model
claude-opus-5-5` run on 2 submissions from the A/B sample, then a full A/B as a
separate step once the owner approves the cost.

## 10. Out of scope

- Per-feature provider choice; free-text model ids; editing API keys in the UI.
- Moving offline scripts to Claude.
- Bedrock / Vertex / Files API for Claude.
- Running the full Claude-vs-Gemini A/B (enabled by section 7, run separately).
- An EEA-hosted provider (the DPIA's [UZUPEŁNIĆ] stays).
