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
