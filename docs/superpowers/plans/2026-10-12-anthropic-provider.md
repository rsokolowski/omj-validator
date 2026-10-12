# Anthropic Provider and Runtime AI Model Switch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude as a second AI provider for every in-app AI call, selected (provider + model) by an admin at runtime and persisted in the DB, with provider-agnostic A/B tooling and updated GDPR documents.

**Architecture:** A model catalog + `app_settings` row decide the active `{provider, model}`; `create_ai_provider()` caches one instance per pair. Provider-neutral request text moves out of `gemini.py` into `app/ai/requests.py`, so `GeminiProvider` and the new `AnthropicProvider` send identical prompts. Admin `GET/PUT /api/admin/ai-config` + `/admin/settings` page; save requires a successful `ping()`.

**Tech Stack:** FastAPI, SQLAlchemy + Alembic (Postgres prod, SQLite in tests), `anthropic==1.13.0` (`AsyncAnthropic`), `google-genai==2.19.0`, Next.js 16 / React 19 / MUI v7, pytest.

**Spec:** `docs/superpowers/specs/2026-10-12-anthropic-provider-design.md`

## Global Constraints

- Tests: `./venv/bin/python -m pytest -q` (SQLite, no Docker needed). Baseline 638 passed. Every task ends with the full suite green.
- Frontend checks: `cd frontend && npm run lint && npx tsc --noEmit`.
- Never commit `tasks/` or `data/task_content/`; fixtures use invented problems only.
- `.env` is git-ignored and already holds `ANTHROPIC_API_KEY`; `Settings` forbids unknown keys, so Task 1 must declare the field before anything loads settings with that `.env`.
- Curated models exactly: gemini `gemini-3.8-flash`, `gemini-3.1-pro-preview`; anthropic `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`.
- API keys never stored in the DB or returned by any endpoint.
- Gemini behaviour must not change except `scoring_meta` gaining `provider`/`model`/token fields on OMJ streaming.
- User-facing strings are Polish; code/comments English, matching surrounding style.
- No state-writing git commands except the commit at the end of each task, on branch `feat/anthropic-provider`.

## Review Focus

1. Active row names a model no longer in the catalog (or a provider without key) → grading must keep working on the env fallback, never 500. (Task 2 tests.)
2. Admin selects Claude while `ANTHROPIC_PROCESSOR_APPROVED=false` → PUT 409, and even a hand-inserted DB row must not route student data to Anthropic. (Tasks 2, 5.)
3. Claude returns `stop_reason == "refusal"` or `max_tokens` with no JSON → `AIContentBlockedError` / friendly `AIProviderError`, never a raw SDK exception or a 0-score stored as success. (Task 4.)
4. Large photo batches (10 × 10 MB) → images downscaled/re-encoded in memory under the per-image limit; request does not 413. (Task 4.)
5. Refactor drift: Gemini prompts after the extraction differ by one character → A/B no longer fair. Snapshot test pins them. (Task 3.)

---

### Task 1: Settings, model catalog, `app_settings` table, config store

**Files:**
- Modify: `app/config.py` (after the Gemini block)
- Create: `app/ai/models_catalog.py`
- Modify: `app/db/models.py` (new `AppSettingDB`)
- Create: `alembic/versions/009_add_app_settings.py`
- Modify: `app/db/repositories.py` (new `AppSettingsRepository`)
- Create: `app/ai/config_store.py`
- Modify: `requirements.txt` (`anthropic==1.13.0`), install into venv
- Test: `tests/test_ai_catalog_and_config_store.py`

**Interfaces — Produces:**
- `settings.anthropic_api_key: Optional[str]`, `anthropic_effort: str = "high"`, `anthropic_effort_aux: str = "medium"`, `anthropic_timeout: int = 180`, `anthropic_processor_approved: bool = False`, `anthropic_api_base_url: Optional[str] = None`
- `models_catalog.ModelInfo(provider, id, label, pricing)`, `CATALOG`, `PROVIDERS = ("gemini", "anthropic")`, `PROVIDER_LABELS`, `get_model(provider, model) -> ModelInfo | None`, `models_for(provider) -> list[ModelInfo]`, `estimate_cost(provider, model, input_tokens, output_tokens, thoughts_tokens=0, cache_read_tokens=0, cache_write_tokens=0) -> float`, `provider_configured(provider) -> bool`, `provider_approved(provider) -> bool`
- `config_store.ActiveModel(provider, model, source, updated_at, updated_by)`, `get_active_model() -> ActiveModel`, `set_active_model(db, provider, model, updated_by) -> ActiveModel`, `invalidate_cache() -> None`, `env_default() -> ActiveModel`
- `AppSettingsRepository(db).get(key) -> Optional[AppSettingDB]`, `.set(key, value: dict, updated_by) -> AppSettingDB`

- [ ] **Step 1: Branch, dependency**

```bash
git checkout -b feat/anthropic-provider
echo 'anthropic==1.13.0  # Claude provider (app/ai/providers/anthropic.py)' >> requirements.txt
./venv/bin/pip install anthropic==1.13.0
```

- [ ] **Step 2: Settings fields** in `app/config.py`, directly after `gemini_disable_file_cache`:

```python
    # Anthropic (Claude) API Configuration - selectable in /admin/settings
    anthropic_api_key: Optional[str] = None
    anthropic_api_base_url: Optional[str] = None  # Custom endpoint for testing
    anthropic_effort: str = "high"        # output_config.effort for grading
    anthropic_effort_aux: str = "medium"  # extraction, hints, patterns
    anthropic_timeout: int = 180
    # GDPR gate: Anthropic is a processor only once the DPIA/regulamin cover it
    # and the owner has signed off. False keeps every request on Gemini.
    anthropic_processor_approved: bool = False
```

- [ ] **Step 3: Failing tests** `tests/test_ai_catalog_and_config_store.py`:

```python
"""Model catalog and the persisted active model (admin AI switch)."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai import config_store, models_catalog
from app.config import settings
from app.db.models import AppSettingDB
from app.db.session import Base


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(config_store, "SessionLocal", factory)
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")
    config_store.invalidate_cache()
    yield factory
    config_store.invalidate_cache()


def test_catalog_is_exactly_the_curated_list():
    ids = [(m.provider, m.id) for m in models_catalog.CATALOG]
    assert ids == [
        ("gemini", "gemini-3.8-flash"),
        ("gemini", "gemini-3.1-pro-preview"),
        ("anthropic", "claude-opus-5-5"),
        ("anthropic", "claude-sonnet-5-5"),
        ("anthropic", "claude-haiku-5-5"),
    ]


def test_claude_cost_counts_cache_reads_cheaper():
    full = models_catalog.estimate_cost("anthropic", "claude-opus-5-5", 1_000_000, 0)
    cached = models_catalog.estimate_cost("anthropic", "claude-opus-5-5", 0, 0, cache_read_tokens=1_000_000)
    assert full == pytest.approx(4.00)
    assert cached == pytest.approx(0.40)


def test_claude_thinking_is_inside_output_tokens():
    assert models_catalog.estimate_cost("anthropic", "claude-sonnet-5-5", 0, 1_000_000) == pytest.approx(10.00)


def test_haiku_long_context_tier():
    cost = models_catalog.estimate_cost("anthropic", "claude-haiku-5-5", 200_000, 0)
    assert cost == pytest.approx(200_000 / 1e6 * 0.50)


def test_gemini_cost_delegates_to_gemini_pricing():
    from app.ai.providers.gemini import estimate_cost as gemini_cost
    assert models_catalog.estimate_cost("gemini", "gemini-3.8-flash", 1000, 2000, 300) == pytest.approx(
        gemini_cost("gemini-3.8-flash", 1000, 2000, 300)
    )


def test_env_fallback_without_row(session_factory):
    active = config_store.get_active_model()
    assert (active.provider, active.model, active.source) == ("gemini", "gemini-3.8-flash", "env")


def test_db_row_wins(session_factory):
    with session_factory() as db:
        config_store.set_active_model(db, "anthropic", "claude-opus-5-5", "admin@example.com")
    active = config_store.get_active_model()
    assert (active.provider, active.model, active.source, active.updated_by) == (
        "anthropic", "claude-opus-5-5", "db", "admin@example.com",
    )


def test_unknown_model_in_row_falls_back_to_env(session_factory, caplog):
    with session_factory() as db:
        db.add(AppSettingDB(key="ai_model", value={"provider": "gemini", "model": "gemini-1.0-old"}))
        db.commit()
    active = config_store.get_active_model()
    assert active.source == "env"
    assert "gemini-1.0-old" in caplog.text


def test_db_error_falls_back_to_env(monkeypatch):
    def broken():
        raise RuntimeError("db down")
    monkeypatch.setattr(config_store, "SessionLocal", broken)
    config_store.invalidate_cache()
    assert config_store.get_active_model().source == "env"
    config_store.invalidate_cache()


def test_cache_is_dropped_on_set(session_factory):
    assert config_store.get_active_model().provider == "gemini"
    with session_factory() as db:
        config_store.set_active_model(db, "gemini", "gemini-3.1-pro-preview", "a@example.com")
    assert config_store.get_active_model().model == "gemini-3.1-pro-preview"


def test_set_rejects_models_outside_catalog(session_factory):
    with session_factory() as db, pytest.raises(ValueError):
        config_store.set_active_model(db, "anthropic", "claude-3-opus", "a@example.com")
```

- [ ] **Step 4: Run** `./venv/bin/python -m pytest tests/test_ai_catalog_and_config_store.py -q` → fails on imports.

- [ ] **Step 5: `app/ai/models_catalog.py`**

```python
"""The AI models an admin may select, with prices for cost estimates.

Single source of truth for /admin/settings, validation of the persisted choice
and the cost figures in scoring_meta and the A/B scripts. Gemini prices stay in
GEMINI_PRICING (older models there are still referenced by stored rows and the
eval scripts); Claude prices live here.
"""

from dataclasses import dataclass, field
from typing import Optional

from ..config import settings

PROVIDERS = ("gemini", "anthropic")
PROVIDER_LABELS = {"gemini": "Google Gemini", "anthropic": "Anthropic Claude"}


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    id: str
    label: str
    # USD per 1M tokens. Claude: "input", "output", "cache_read", "cache_write",
    # optional "long_threshold"/"long_input"/"long_output". Gemini entries are
    # empty - estimate_cost delegates to GEMINI_PRICING.
    pricing: dict = field(default_factory=dict)


# Claude prices: platform.claude.com pricing, checked 2026-10-12.
# Thinking tokens are part of output_tokens in the Messages API usage.
CATALOG: tuple[ModelInfo, ...] = (
    ModelInfo("gemini", "gemini-3.8-flash", "Gemini 3.8 Flash"),
    ModelInfo("gemini", "gemini-3.1-pro-preview", "Gemini 3.1 Pro (preview)"),
    ModelInfo("anthropic", "claude-opus-5-5", "Claude Opus 5.5",
              {"input": 4.00, "output": 20.00, "cache_read": 0.40, "cache_write": 5.00}),
    ModelInfo("anthropic", "claude-sonnet-5-5", "Claude Sonnet 5.5",
              {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50}),
    ModelInfo("anthropic", "claude-haiku-5-5", "Claude Haiku 5.5",
              {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125,
               "long_threshold": 100_000, "long_input": 0.50, "long_output": 2.50}),
)


def get_model(provider: str, model: str) -> Optional[ModelInfo]:
    return next((m for m in CATALOG if m.provider == provider and m.id == model), None)


def models_for(provider: str) -> list[ModelInfo]:
    return [m for m in CATALOG if m.provider == provider]


def provider_configured(provider: str) -> bool:
    """The provider's API key is set (the key itself never leaves the server)."""
    if provider == "gemini":
        return bool(settings.gemini_api_key)
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    return False


def provider_approved(provider: str) -> bool:
    """GDPR gate: may student data be sent to this provider at all."""
    if provider == "anthropic":
        return settings.anthropic_processor_approved
    return provider == "gemini"


def estimate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    thoughts_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Estimated USD cost of one call. Logging/meta only, never billing."""
    if provider == "gemini":
        from .providers.gemini import estimate_cost as gemini_cost
        return gemini_cost(model, input_tokens, output_tokens, thoughts_tokens)

    info = get_model(provider, model)
    if info is None:
        return 0.0
    p = info.pricing
    prompt_tokens = input_tokens + cache_read_tokens + cache_write_tokens
    threshold = p.get("long_threshold")
    long = bool(threshold and prompt_tokens > threshold)
    in_rate = p.get("long_input", p["input"]) if long else p["input"]
    out_rate = p.get("long_output", p["output"]) if long else p["output"]
    return (
        input_tokens * in_rate
        + output_tokens * out_rate
        + cache_read_tokens * p.get("cache_read", in_rate)
        + cache_write_tokens * p.get("cache_write", in_rate)
    ) / 1_000_000
```

(Verify the Claude cache_write / Haiku cache prices against the claude-api skill's pricing or https://platform.claude.com/docs/en/about-claude/pricing at implementation time; adjust the numbers, not the shape.)

- [ ] **Step 6: ORM + migration.** In `app/db/models.py` (after `AdminAccessLogDB`, use the module's existing `JSON`, `Column`, `String`, `DateTime`, `func` imports):

```python
class AppSettingDB(Base):
    """Runtime settings an admin can change without a deploy.

    Only "ai_model" ({"provider", "model"}) today. Secrets never go here - API
    keys stay in the environment.
    """

    __tablename__ = "app_settings"

    key = Column(String(64), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by = Column(String, nullable=True)
```

`alembic/versions/009_add_app_settings.py` (revision `"009"`, down `"008"`, docstring in the style of 008): `op.create_table("app_settings", sa.Column("key", sa.String(64), primary_key=True), sa.Column("value", sa.JSON(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_by", sa.String(), nullable=True))`; downgrade drops it.

- [ ] **Step 7: Repository** in `app/db/repositories.py`:

```python
class AppSettingsRepository:
    """Key/value runtime settings (app_settings)."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, key: str) -> Optional[AppSettingDB]:
        return self.db.get(AppSettingDB, key)

    def set(self, key: str, value: dict, updated_by: Optional[str]) -> AppSettingDB:
        row = self.get(key)
        if row is None:
            row = AppSettingDB(key=key, value=value, updated_by=updated_by)
            self.db.add(row)
        else:
            row.value = value
            row.updated_by = updated_by
            row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row
```

Export it from `app/db/__init__.py` if that module re-exports repositories (follow existing pattern).

- [ ] **Step 8: `app/ai/config_store.py`**

```python
"""The active AI provider + model: app_settings row, else the environment.

Read on every create_ai_provider() call, so it is cached for a few seconds;
a write drops the cache in this process and other workers see it within
CACHE_TTL_SECONDS. A missing, unknown or unreadable row falls back to the
environment - a bad config row must never stop grading.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..db.repositories import AppSettingsRepository
from ..db.session import SessionLocal
from .models_catalog import get_model

logger = logging.getLogger(__name__)

AI_MODEL_KEY = "ai_model"
CACHE_TTL_SECONDS = 30


@dataclass(frozen=True)
class ActiveModel:
    provider: str
    model: str
    source: str  # "db" | "env"
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


_lock = threading.Lock()
_cached: Optional[tuple[float, ActiveModel]] = None


def env_default() -> ActiveModel:
    provider = settings.ai_provider.lower()
    model = settings.gemini_model if provider == "gemini" else ""
    return ActiveModel(provider=provider, model=model, source="env")


def invalidate_cache() -> None:
    global _cached
    with _lock:
        _cached = None


def _read() -> ActiveModel:
    try:
        with SessionLocal() as db:
            row = AppSettingsRepository(db).get(AI_MODEL_KEY)
            if row is None:
                return env_default()
            provider = (row.value or {}).get("provider")
            model = (row.value or {}).get("model")
            if get_model(provider, model) is None:
                logger.warning(f"[AI config] Stored model {provider}/{model} is not in the catalog - using env")
                return env_default()
            return ActiveModel(provider, model, "db", row.updated_at, row.updated_by)
    except Exception as e:
        logger.error(f"[AI config] Could not read active model ({type(e).__name__}: {e}) - using env")
        return env_default()


def get_active_model() -> ActiveModel:
    global _cached
    now = time.monotonic()
    with _lock:
        if _cached and now - _cached[0] < CACHE_TTL_SECONDS:
            return _cached[1]
    active = _read()
    with _lock:
        _cached = (now, active)
    return active


def set_active_model(db: Session, provider: str, model: str, updated_by: Optional[str]) -> ActiveModel:
    if get_model(provider, model) is None:
        raise ValueError(f"{provider}/{model} is not a selectable model")
    row = AppSettingsRepository(db).set(AI_MODEL_KEY, {"provider": provider, "model": model}, updated_by)
    invalidate_cache()
    return ActiveModel(provider, model, "db", row.updated_at, row.updated_by)
```

(If `SessionLocal` is named differently in `app/db/session.py`, use the real name and update the test's monkeypatch target.)

- [ ] **Step 9: Run** the new test file, then the full suite → all pass (the `.env` key is now a declared field).

- [ ] **Step 10: Commit** `feat(ai): model catalog and persisted active model (app_settings)`.

---

### Task 2: Factory per (provider, model), provider model argument, `ping()`, provider in `scoring_meta`

**Files:**
- Modify: `app/ai/factory.py`, `app/ai/protocol.py`, `app/ai/providers/gemini.py`, `app/ai/providers/__init__.py`
- Test: `tests/test_ai_factory.py`; adjust `tests/test_gemini_cost_and_resolution.py` only if constructor change requires it

**Interfaces:**
- Consumes: Task 1 `get_active_model`, `env_default`, `provider_configured`, `provider_approved`, `get_model`
- Produces: `factory.build_provider(provider: str, model: str) -> AIProvider` (no cache; raises `AIProviderError`), `factory.create_ai_provider()` (unchanged signature), `factory.reset_provider_cache()`; `GeminiProvider(model: Optional[str] = None)`; protocol method `async def ping(self) -> None`; attributes `provider_name: str` and `model_name: str` on every provider. Task 4 registers `"anthropic"` in `build_provider` by importing `AnthropicProvider(model)`.

- [ ] **Step 1: Failing tests** `tests/test_ai_factory.py`:

```python
"""create_ai_provider follows the persisted active model."""

import pytest

from app.ai import config_store, factory
from app.ai.config_store import ActiveModel
from app.ai.factory import AIProviderError
from app.config import settings


class FakeProvider:
    def __init__(self, provider, model):
        self.provider_name, self.model_name = provider, model


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    factory.reset_provider_cache()
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    monkeypatch.setattr(settings, "anthropic_api_key", "a-key")
    monkeypatch.setattr(settings, "anthropic_processor_approved", True)
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")
    monkeypatch.setattr(factory, "_construct", lambda provider, model: FakeProvider(provider, model))
    yield
    factory.reset_provider_cache()


def use(monkeypatch, provider, model):
    monkeypatch.setattr(factory, "get_active_model", lambda: ActiveModel(provider, model, "db"))


def test_one_instance_per_pair(monkeypatch):
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    first = factory.create_ai_provider()
    assert factory.create_ai_provider() is first
    use(monkeypatch, "anthropic", "claude-sonnet-5-5")
    second = factory.create_ai_provider()
    assert second is not first and second.model_name == "claude-sonnet-5-5"


def test_missing_key_raises_in_build(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    with pytest.raises(AIProviderError):
        factory.build_provider("anthropic", "claude-opus-5-5")


def test_unapproved_anthropic_falls_back_to_env_gemini(monkeypatch, caplog):
    monkeypatch.setattr(settings, "anthropic_processor_approved", False)
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    provider = factory.create_ai_provider()
    assert (provider.provider_name, provider.model_name) == ("gemini", "gemini-3.8-flash")
    assert "not approved" in caplog.text


def test_active_provider_without_key_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    use(monkeypatch, "anthropic", "claude-opus-5-5")
    assert factory.create_ai_provider().provider_name == "gemini"


def test_env_provider_without_key_still_raises(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    use(monkeypatch, "gemini", "gemini-3.8-flash")
    with pytest.raises(AIProviderError):
        factory.create_ai_provider()


def test_unknown_provider_raises():
    with pytest.raises(AIProviderError):
        factory.build_provider("openai", "gpt")
```

- [ ] **Step 2: Run** → fail.

- [ ] **Step 3: Rewrite `app/ai/factory.py`** (keep the two exception classes and their docstrings at the top unchanged):

```python
_instances: dict[tuple[str, str], "AIProvider"] = {}
_instances_lock = threading.Lock()


def reset_provider_cache() -> None:
    with _instances_lock:
        _instances.clear()


def _construct(provider: str, model: str) -> "AIProvider":
    if provider == "gemini":
        from .providers.gemini import GeminiProvider
        return GeminiProvider(model)
    if provider == "anthropic":
        from .providers.anthropic import AnthropicProvider
        return AnthropicProvider(model)
    raise AIProviderError(f"Unknown AI provider: {provider}. Supported providers: gemini, anthropic")


def build_provider(provider: str, model: str) -> "AIProvider":
    """A fresh, uncached provider for (provider, model). Used by ping and scripts."""
    from .models_catalog import provider_configured
    if provider not in ("gemini", "anthropic"):
        raise AIProviderError(f"Unknown AI provider: {provider}. Supported providers: gemini, anthropic")
    if not provider_configured(provider):
        raise AIProviderError(
            f"{provider.upper()}_API_KEY is required for provider {provider}. Set it in your .env file."
        )
    return _construct(provider, model)


def _usable(provider: str) -> bool:
    from .models_catalog import provider_approved, provider_configured
    return provider_configured(provider) and provider_approved(provider)


def create_ai_provider() -> "AIProvider":
    """The provider for the active model (app_settings row, else env), cached per pair.

    A run already holding an instance finishes on it; the next call picks up a
    switch. An active choice that cannot be used (no key, or Anthropic not yet
    approved as a processor) falls back to the environment default rather than
    stopping grading - or sending data to an unapproved processor.
    """
    active = get_active_model()
    provider, model = active.provider, active.model
    if active.source == "db" and not _usable(provider):
        logger.error(
            f"[AI] Active model {provider}/{model} is not usable "
            f"({'not approved' if provider_configured(provider) else 'no API key'}) - using env default"
        )
        fallback = env_default()
        provider, model = fallback.provider, fallback.model
    key = (provider, model)
    with _instances_lock:
        instance = _instances.get(key)
    if instance is None:
        instance = build_provider(provider, model)
        with _instances_lock:
            instance = _instances.setdefault(key, instance)
    return instance
```

Module imports: `import logging, threading`; `from .config_store import env_default, get_active_model`; `from .models_catalog import provider_configured`; `logger = logging.getLogger(__name__)`. Watch for a circular import: `config_store` imports `models_catalog` which imports `config` only — fine; `gemini.py` imports `factory` for the exception classes, so `factory` must not import `providers.*` at module level (keep lazy imports as above).

- [ ] **Step 4: `GeminiProvider` changes** (`app/ai/providers/gemini.py`):
  - `def __init__(self, model: Optional[str] = None):` and `self._model_name = model or settings.gemini_model`; add `self.provider_name = "gemini"` and a `model_name` property returning `self._model_name`.
  - `_usage_meta` adds `"provider": "gemini"`.
  - `analyze_solution_stream`: replace the three `scoring_meta` assignments with
    ```python
    result.scoring_meta = {
        **(result.scoring_meta or {}),
        **self._usage_meta(usage_metadata, start_time),
        "thinking": thinking_text,
        "api_time": api_time,
        "total_time": total_time,
    }
    ```
  - Add:
    ```python
    async def ping(self) -> None:
        """One tiny call proving key + model work (admin switch). Raises AIProviderError."""
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.models.generate_content,
                    model=self._model_name,
                    contents=["Odpowiedz jednym słowem: OK"],
                ),
                timeout=30,
            )
        except Exception as e:
            logger.error(f"[Gemini ping] {type(e).__name__}: {e}")
            raise AIProviderError(f"Model {self._model_name} nie odpowiada: {type(e).__name__}")
    ```
- [ ] **Step 5: Protocol** (`app/ai/protocol.py`): add `provider_name: str`, `model_name: str` annotations and `async def ping(self) -> None: """Minimal request to verify key + model; raises AIProviderError."""`. Also add `analyze_solution_stream` to the protocol with Gemini's exact signature (the worker already calls it).

- [ ] **Step 6: Run** new tests + full suite. Grep tests for `GeminiProvider()` and `_provider_instance` and adapt any that break (they should not: the default argument keeps `GeminiProvider()` valid).

- [ ] **Step 7: Commit** `feat(ai): provider per active model, ping(), provider in scoring_meta`.

---

### Task 3: Provider-neutral request text (`app/ai/requests.py`) with a Gemini snapshot

**Files:**
- Create: `app/ai/requests.py`
- Modify: `app/ai/providers/gemini.py`
- Test: `tests/test_ai_requests_snapshot.py`, `tests/fixtures/gemini_request_snapshot.json` (generated in Step 1 from the CURRENT code, committed)

**Interfaces — Produces** (pure functions, no SDK types; Task 4 uses all of them):

```python
def omj_grading_text(prompt_text: str, task_number: int, has_solution_pdf: bool,
                     num_images: int, has_text: bool) -> str
    # the full_prompt string Gemini puts first today (headers, "Znajdź 'Zadanie N.'",
    # the official-solution header if any, "### Rozwiązanie ucznia:", shape line,
    # "Zdjęcie i:" lines)
def private_grading_text(task_title: str, task_content: str, num_images: int, has_text: bool) -> str
def photo_label(index: int) -> str            # "Zdjęcie {index}:"
def extract_text() -> str                      # load_private_prompt("extract")
def meta_text(title: str, content: str) -> str
def refine_text(draft, source_text, history, current, candidates, skills) -> str
def suggest_text(task_text: str, feedback: str, draft: Optional[str]) -> str
def link_text(pattern: dict, candidates: list[dict]) -> str
def student_text(text) -> str; draft_text(draft) -> str; answers_text(pairs) -> str; conversation_text(history) -> str
```

`refine_text` takes `skills` (list of objects with `.id`, `.name`) so the caller still owns `get_all_skills()` (it needs the ids for parsing).

- [ ] **Step 1: Snapshot BEFORE refactoring.** Write `tests/test_ai_requests_snapshot.py` that builds, with a `GeminiProvider` whose `_client` is a stub (construct via `GeminiProvider.__new__` + set `_model_name="gemini-3.8-flash"`, `_is_gemini_3=False`, `_disable_file_cache=True`, `provider_name="gemini"`), and captures the `contents` argument passed to `generate_content` / `generate_content_stream` for:
  - `generate_private_task_meta("Tytuł", "Treść $x^2$")`
  - `refine_pattern(draft={"trigger": "t", "action": "a"}, source_text="src", history=[{"draft": {"raw": "r"}, "verdict": "ok", "variants": [{"trigger": "x", "action": "y", "tasks": ["2024_etap1_1"]}], "questions": ["q?"], "chosen": 0}], current={"answers": [{"question": "q?", "answer": "ans"}], "message": "hej"}, candidates=[{"task_key": "2024_etap1_1", "difficulty": 2, "categories": ["algebra"], "hints": ["h1"]}])`
  - `suggest_patterns("zadanie", "ocena", None)`, `link_pattern_tasks({"trigger": "t", "action": "a"}, [same candidate])`
  - `_build_content_parts(build_prompt("etap2"), ["TASK", "SOL", "IMG1", "IMG2"], 3, True, 2, image_paths=None, solution_text="moje $a$")` (non-Gemini-3 path, plain strings stand in for files)
  - `analyze_private_solution_stream("T", "C", [], solution_text="txt")` with `_run_stream` patched to capture contents and return `("", '{"score":2,"feedback":"f","issue_type":"none","abuse_score":0}', None, 0.1, 0.1)`.
  Strings only (replace non-str parts by `"<part>"`). Stub `get_all_skills` to two fixed fake skills. Generate `tests/fixtures/gemini_request_snapshot.json` from the current code (a `--update` helper guarded by env `UPDATE_SNAPSHOT=1`), run the test → PASS on unchanged code. Commit the snapshot with the test.

- [ ] **Step 2: Create `app/ai/requests.py`** by moving, verbatim, the string-building code out of `gemini.py`: `_student_text`, `_draft_text`, `_answers_text`, `_conversation_text`, the f-strings in `generate_private_task_meta`, `refine_pattern`, `suggest_patterns`, `link_pattern_tasks`, `analyze_private_solution_stream` (the `prompt` variable) and the `full_prompt` assembly of `_build_content_parts`. Module docstring: "Provider-neutral text of every AI request. Both providers send exactly these strings, so an A/B compares models, not prompts."

- [ ] **Step 3: Make `gemini.py` call `requests.*`.** `_build_content_parts` keeps its signature and part-ordering logic but obtains `full_prompt` from `omj_grading_text(prompt_text, task_number, has_solution_pdf, num_images, bool(solution_text))`. Keep `GeminiProvider._student_text` etc. as thin aliases only if a test references them (grep `tests/` first; prefer updating tests to `requests.*`).

- [ ] **Step 4: Run** snapshot test + full suite → PASS, with the snapshot file untouched (`git diff --exit-code tests/fixtures/gemini_request_snapshot.json`).

- [ ] **Step 5: Commit** `refactor(ai): provider-neutral request text, pinned by a Gemini snapshot`.

---

### Task 4: `AnthropicProvider`

**Files:**
- Create: `app/ai/providers/anthropic.py`
- Modify: `app/ai/providers/__init__.py` (export lazily, like Gemini)
- Test: `tests/test_anthropic_provider.py`

**Interfaces:**
- Consumes: Task 3 `requests.*`; Task 2 protocol (`ping`, `provider_name`, `model_name`); `prompt_builder.build_prompt`, `build_private_scoring_prompt`, `solution_text_block`, `CLOSING_LINE`; `parsing.parse_ai_response`; `private_parsing` / `pattern_parsing` parse functions and schemas; `RESPONSE_JSON_SCHEMA` (import from `gemini.py` is fine, or move it to `app/ai/schemas.py` and import from both — preferred); `models_catalog.estimate_cost`; `factory.AIProviderError`, `AIContentBlockedError`.
- Produces: `AnthropicProvider(model: str)` implementing the full protocol incl. `analyze_solution_stream(..., on_thinking, on_feedback, on_upload_complete, solution_text)`.

Before writing code, read the claude-api skill files `python/claude-api/README.md`, `python/claude-api/streaming.md`, `python/claude-api/tool-use.md` (structured outputs section) and `shared/model-migration.md` → refusal / fallbacks section, for exact SDK call shapes. Do not guess SDK signatures.

**Behaviour (spec §5):**
- Client: `anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, base_url=settings.anthropic_api_base_url or None, timeout=settings.anthropic_timeout)`.
- `system=` the instruction text is NOT split out; to keep parity with Gemini, all text goes in the single user message in Gemini's order. (Spec said system; parity wins — note it in the module docstring.)
- OMJ grading content blocks, in order: `text(omj_grading_text(...))`, `document(task_pdf base64)`, `document(solution_pdf base64, cache_control ephemeral)` if present (else `cache_control` on the task PDF), then for each photo `image(base64)`, then `text(solution_text_block(...))` if typed, then `text(CLOSING_LINE)`.
- Private grading: `text(private_grading_text(...))`, then per photo `text(photo_label(i))` + `image`, then solution block, closing line.
- Extraction: `text(extract_text())` + images. Meta/refine/suggest/link: single text block from `requests.*`.
- Structured output: `output_config={"format": {"type": "json_schema", "schema": SCHEMA}, "effort": effort}` — check exact key names in the skill docs; schemas must have `additionalProperties: false` on every object for structured outputs — if the shared schemas lack it, produce a strict copy with a helper `_strict(schema)` that recursively adds `additionalProperties: False` (do not mutate the shared dicts Gemini uses).
- Thinking: `thinking={"type": "adaptive", "display": "summarized"}` on grading; on aux calls omit `display` (no streaming consumer).
- Fallbacks: for `claude-opus-5-5` and `claude-sonnet-5-5` use the beta path `client.beta.messages.stream/create(..., betas=["server-side-fallback-2026-07-01"], fallbacks="default")`; Haiku uses the non-beta path without fallbacks.
- Streaming grading: `async with client.(beta.)messages.stream(...) as stream:` iterate events; `content_block_delta` with `delta.type == "thinking_delta"` → append + `await on_thinking(delta.thinking)`; `text_delta` → append to feedback (+ `on_feedback` if given); `final = await stream.get_final_message()`. Enforce `get_timeout()` with `asyncio.wait_for` around the whole stream consumer.
- Stop reasons: `refusal` → `AIContentBlockedError("Nie udało się przetworzyć rozwiązania. Upewnij się, że zawiera tylko treść zadania lub rozwiązanie.")`; `max_tokens` with empty/unparseable text → `AIProviderError("Nie udało się odczytać rozwiązania. Spróbuj ponownie.")`.
- Text extraction: concatenate `block.text` of `text` blocks in `final.content` (ignore `thinking`, `fallback` blocks).
- Images: read bytes; media type from suffix (`.jpg/.jpeg` → `image/jpeg`, `.png`, `.webp`; anything else → re-encode to JPEG via Pillow). If the image exceeds the API per-image limits (look up current limits in the skill docs / API docs; at time of writing 5 MB and 8000 px per side, and long side > 1568 px is downscaled server-side anyway), re-encode in memory with Pillow: longest side ≤ 2000 px, JPEG quality 85, until ≤ 5 MB. Never write to disk.
- PDFs: base64 of file bytes; `media_type="application/pdf"`.
- `scoring_meta` / `meta` (`_usage_meta(final, started)`): `provider="anthropic"`, `model`, `input_tokens`, `output_tokens`, `cache_read_tokens` (`usage.cache_read_input_tokens or 0`), `cache_write_tokens` (`usage.cache_creation_input_tokens or 0`), `thoughts_tokens=0`, `estimated_cost` from `models_catalog.estimate_cost`, `api_time`. Grading adds `thinking`, `api_time`, `total_time` exactly like Gemini.
- Error mapping (`_friendly_error`): `asyncio.TimeoutError`/`anthropic.APITimeoutError` → "Analiza trwa zbyt długo. Spróbuj ponownie za chwilę."; `RateLimitError`, `APIStatusError` with status 529/≥500, `APIConnectionError` → "System jest obecnie przeciążony. Spróbuj ponownie za kilka minut."; `AuthenticationError`/`PermissionDeniedError` → "Przepraszamy, wystąpił problem techniczny. Spróbuj ponownie później."; else → "Przepraszamy, coś poszło nie tak. Spróbuj ponownie za chwilę.". Log type, status and `request_id` (never content).
- `ping()`: non-streaming `messages.create(model, max_tokens=64, messages=[{"role":"user","content":"Odpowiedz jednym słowem: OK"}], output_config={"effort": "low"})` within 30 s; any exception → `AIProviderError(f"Model {model} nie odpowiada: {type}")`.
- `get_timeout()` → `settings.anthropic_timeout`.
- Logging like Gemini's: model, etap, task, image count, text length, timings, tokens, cost — never student content.

- [ ] **Step 1: Failing tests** `tests/test_anthropic_provider.py`. Use a fake async client object assigned to `provider._client` that records kwargs and returns canned objects (`types.SimpleNamespace`) — no network. Cover:
  1. OMJ stream request: blocks order/types exactly `[text, document, document, image, image, text(solution block), text(CLOSING_LINE)]`, first text equals `requests.omj_grading_text(build_prompt("etap2"), 3, True, 2, True)`, `cache_control` on the last document, `thinking.display == "summarized"`, effort `settings.anthropic_effort`, `fallbacks == "default"` for opus, absent for haiku. Use `tests/fixtures/task_corpus/tasks/1999/etap1/zadania.pdf` as the PDF and tiny PNGs written to `tmp_path` with Pillow.
  2. Thinking deltas reach `on_thinking` in order; result score/feedback parsed; `scoring_meta` has provider/model/tokens/cost/thinking.
  3. Private grading has no document blocks and labels each photo.
  4. `stop_reason="refusal"` → `AIContentBlockedError`; on aux call too.
  5. `max_tokens` with empty text → `AIProviderError`.
  6. Error mapping: fake raising `anthropic.RateLimitError` (construct via `anthropic.RateLimitError(message="x", response=httpx2.Response(429, request=httpx2.Request("POST", "https://x")), body=None)` — check the SDK's constructor; if awkward, raise `anthropic.APIConnectionError(request=...)`) → friendly message.
  7. 6000×4000 PNG over the limit → sent image decodes to ≤ 2000 px long side and ≤ 5 MB.
  8. `generate_private_task_meta` / `link_pattern_tasks` send the same text as `requests.meta_text` / `requests.link_text` and parse through the shared parsers.
  9. Structured-output schema sent has `additionalProperties: False` on every object and the shared Gemini schema dict is not mutated.
  10. `ping()` success and failure.
- [ ] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** file + full suite → pass.
- [ ] **Step 5: Real smoke (manual, needs key, costs cents):** `./venv/bin/python -c "import asyncio; from app.ai.factory import build_provider; asyncio.run(build_provider('anthropic','claude-haiku-5-5').ping()); print('ok')"`. If the key is rejected (`AuthenticationError`), record it and continue — the key format `sk-ant-usr-` may not be a Messages API key; report to the owner at the end.
- [ ] **Step 6: Commit** `feat(ai): Anthropic (Claude) provider`.

---

### Task 5: Admin API `GET/PUT /api/admin/ai-config`

**Files:**
- Modify: `app/main.py` (admin section, after `/api/admin/me`)
- Modify: `app/models.py` (request/response models)
- Test: `tests/test_admin_ai_config.py`

**Interfaces:**
- Consumes: Tasks 1-2.
- Produces (frontend contract, Task 6):

```json
GET /api/admin/ai-config
{
  "active": {"provider": "gemini", "model": "gemini-3.8-flash", "model_label": "Gemini 3.8 Flash",
             "source": "env", "updated_at": null, "updated_by": null},
  "providers": [
    {"id": "gemini", "label": "Google Gemini", "configured": true, "approved": true,
     "models": [{"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash"}, {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro (preview)"}]},
    {"id": "anthropic", "label": "Anthropic Claude", "configured": true, "approved": false,
     "models": [...]}
  ]
}
PUT /api/admin/ai-config  {"provider": "anthropic", "model": "claude-opus-5-5"}
200 -> {"active": {...}}   400 unknown model   409 not configured / not approved   502 ping failed
```
`model_label` is the catalog label, or the raw id when the env model is outside the catalog. `detail` strings are Polish: 400 "Nieznany model.", 409 "Brak klucza API dla tego dostawcy." / "Dostawca Anthropic nie jest jeszcze zatwierdzony jako podmiot przetwarzający (ANTHROPIC_PROCESSOR_APPROVED).", 502 the `AIProviderError` message.

- [ ] **Step 1: Failing tests** (pattern: `tests/test_admin_rerun_text.py` — SQLite `StaticPool`, `dependency_overrides[get_db]`, monkeypatched `_require_admin`; patch `config_store.SessionLocal` to the same sessionmaker, `factory.build_provider` to a stub with async `ping`; patch `main.get_current_user` to return `{"email": "admin@example.com"}`):
  1. non-admin → 403 for GET and PUT (don't patch `_require_admin`; patch `_is_admin` False and `verify_auth` True).
  2. GET with no row → `source == "env"`, both providers listed, keys never present in the JSON (`"key" not in response.text.lower()` for the setting values — assert the raw key string from settings is absent).
  3. PUT unknown model → 400, nothing stored.
  4. PUT anthropic with `anthropic_processor_approved=False` → 409, nothing stored; with no key → 409.
  5. PUT with ping raising `AIProviderError("Model x nie odpowiada")` → 502, nothing stored, active unchanged.
  6. PUT success → 200, row stored with `updated_by == "admin@example.com"`, subsequent GET shows `source == "db"`, and `create_ai_provider` would now build that pair (assert `config_store.get_active_model()`).
- [ ] **Step 2: Run** → fail. **Step 3: Implement** two endpoints; the PUT order is: `_require_admin` → catalog check (400) → configured/approved (409) → `await asyncio.wait_for(build_provider(p, m).ping(), 35)` (502 on `AIProviderError`/timeout) → `set_active_model(db, ...)` → log INFO `AI model changed: {old.provider}/{old.model} -> {p}/{m} by {email}` → response. **Step 4: Run** → pass. **Step 5: Commit** `feat(admin): AI provider/model switch API`.

---

### Task 6: Admin UI `/admin/settings`

**Files:**
- Create: `frontend/src/app/admin/settings/page.tsx` (server component: auth check like `admin/submissions/page.tsx`, renders the client form)
- Create: `frontend/src/components/admin/AiConfigForm.tsx` (client component)
- Modify: `frontend/src/lib/types/index.ts` (`AiConfigResponse`, `AiProviderOption`, `AiActiveModel`), `frontend/src/lib/api/client.ts` (`getAiConfig()`, `putAiConfig(provider, model)` using the existing fetch helpers and `APIError`)
- Modify: `frontend/src/app/admin/submissions/page.tsx` — a link/button "Ustawienia AI" to `/admin/settings` in the page header area (and vice versa "Zgłoszenia").

**Behaviour:** shows "Aktywny model: {model_label} ({provider label})", source chip ("baza" / "konfiguracja serwera"), "Zmienione {date pl-PL} przez {updated_by}" when present. `RadioGroup` of providers; disabled with helper text "Brak klucza API" / "Niezatwierdzony (RODO)" when `!configured` / `!approved`. `Select` of that provider's models. "Zapisz" disabled when unchanged; while saving shows `CircularProgress` + "Sprawdzam model…"; on 200 replace state from response + success `Alert` "Zapisano. Nowe oceny będą wykonywane modelem …"; on error show `Alert severity="error"` with `detail`. No optimistic update.

- [ ] Steps: implement → `npm run lint && npx tsc --noEmit` → manual check in dev stack (Task 9) → commit `feat(admin): AI settings page`.

---

### Task 7: Provider-agnostic A/B tooling

**Files:** `scripts/rescore_eval.py`, `scripts/ab_compare.py`, `docs/model-ab-playbook.md`

- [ ] `rescore_eval.py`: add `--provider {gemini,anthropic}` (default `gemini`) and keep `--model`; build via `factory.build_provider(args.provider, args.model)` (Gemini keeps accepting any model id: for gemini call `GeminiProvider(args.model)` directly so non-catalog ids work). Drop the `generate_content` monkeypatch; read tokens/cost from `result.scoring_meta` (both providers now fill it via `analyze_solution_stream` — switch the script to the stream method with `on_thinking=None`). Output rows gain `"provider"`.
- [ ] `ab_compare.py`: cost via `models_catalog.estimate_cost(row.get("provider", "gemini"), model, ...)` or directly from the row's `estimated_cost` when present; label arms `provider/model`.
- [ ] Playbook: section "Claude arm" — command line, `ANTHROPIC_API_KEY` needed, note that running it sends prod photos to Anthropic and needs `ANTHROPIC_PROCESSOR_APPROVED` sign-off first; cost hint.
- [ ] Verify: `./venv/bin/python scripts/rescore_eval.py --help` and `ab_compare.py --help` run; if the sample files exist locally run `ab_compare.py` on an existing Gemini result to prove backward compatibility. Commit `feat(scripts): provider-agnostic model A/B`.

---

### Task 8: GDPR documents and `/regulamin`

**Files:** `docs/rodo/dpia.md`, `docs/rodo/klauzula-informacyjna-szkola.md`, `docs/rodo/regulamin-szkola.md`, `docs/rodo/README.md`, `frontend/src/app/regulamin/page.tsx`

Follow spec §8 exactly, including the verified facts list (Anthropic Ireland, Limited for EEA; no training on Customer Content; DPA with SCCs Module 2/3; API inputs/outputs deleted within 30 days except UP enforcement / law; DPF participation not confirmed → action item; inline transfer, no Files API). Polish, same register and formatting as surrounding text; child-facing `/regulamin` in the same simple "Ty" voice. Bump "Ostatnia aktualizacja" dates to 2026-10-12. Do not invent facts beyond that list; where an operator decision is needed use the existing `[UZUPEŁNIĆ: …]` convention.

- [ ] Edit → `npm run lint` (regulamin is TSX) → a separate reviewer reads the `/regulamin` diff (standing rule for child-facing prose) → commit `docs(rodo): Anthropic as an alternative AI processor`.

---

### Task 9: Wiring, docs, end-to-end verification

**Files:** `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.e2e.yml` (no change unless env list is explicit), `.env.example`, `.env.prod.example`, `CLAUDE.md`, `README.md`

- [ ] Pass `ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}`, `ANTHROPIC_EFFORT`, `ANTHROPIC_EFFORT_AUX`, `ANTHROPIC_TIMEOUT`, `ANTHROPIC_PROCESSOR_APPROVED: ${ANTHROPIC_PROCESSOR_APPROVED:-false}` in both compose files' api env. Dev compose: `ANTHROPIC_PROCESSOR_APPROVED: ${ANTHROPIC_PROCESSOR_APPROVED:-true}` is NOT allowed — keep `false` default everywhere; developers set it in `.env`.
- [ ] `.env.example` / `.env.prod.example`: commented block for the new variables. README table: `AI_PROVIDER` row says the runtime choice lives in /admin/settings. CLAUDE.md: tables list (`app_settings`), routes (`/api/admin/ai-config`), structure (`providers/anthropic.py`, `models_catalog.py`, `config_store.py`, `requests.py`), config block.
- [ ] Full backend suite; frontend lint + tsc + `npm test`.
- [ ] `./start.sh --build` (dev stack, AUTH_DISABLED); `alembic upgrade head` runs in the container; with Playwright: open `/admin/settings` (dev user must be admin — set `ADMIN_EMAILS` to the dev user's email in `.env` if needed), switch to `gemini-3.1-pro-preview`, see success, reload, value persisted; switch back to `gemini-3.8-flash`. If `ANTHROPIC_PROCESSOR_APPROVED=true` in local `.env` and the key works: switch to `claude-haiku-5-5`, submit one typed-text solution to an OMJ task (invented text, no task content committed) and watch the WebSocket thinking stream + final score; then switch back.
- [ ] Commit `chore: wire Anthropic settings into compose, env examples and docs`.

---

## Finish

- `/code-review` (high) on `main...feat/anthropic-provider`, fix findings, polish wave.
- Merge to `main` locally. **Do not** run `build-and-push.sh` / `deploy.sh` — stop before prod deploy as instructed.
