"""Model catalog and the persisted active model (admin AI switch)."""

from datetime import datetime

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
    assert cached == pytest.approx(0.20)


def test_claude_thinking_is_inside_output_tokens():
    assert models_catalog.estimate_cost("anthropic", "claude-sonnet-5-5", 0, 1_000_000) == pytest.approx(10.00)


def test_haiku_long_context_tier():
    cost = models_catalog.estimate_cost("anthropic", "claude-haiku-5-5", 200_000, 0)
    assert cost == pytest.approx(200_000 / 1e6 * 0.50)


def test_haiku_long_tier_scales_cache_rates_from_long_input():
    read = models_catalog.estimate_cost("anthropic", "claude-haiku-5-5", 0, 0, cache_read_tokens=200_000)
    write = models_catalog.estimate_cost("anthropic", "claude-haiku-5-5", 0, 0, cache_write_tokens=200_000)
    assert read == pytest.approx(200_000 / 1e6 * 0.05)
    assert write == pytest.approx(200_000 / 1e6 * 0.625)


def test_haiku_short_tier_keeps_listed_cache_rates():
    read = models_catalog.estimate_cost("anthropic", "claude-haiku-5-5", 0, 0, cache_read_tokens=50_000)
    assert read == pytest.approx(50_000 / 1e6 * 0.01)


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


def test_set_twice_updates_the_row(session_factory):
    with session_factory() as db:
        config_store.set_active_model(db, "anthropic", "claude-opus-5-5", "a@example.com")
        row = db.get(AppSettingDB, config_store.AI_MODEL_KEY)
        row.updated_at = datetime(2020, 1, 1)
        db.commit()
        config_store.set_active_model(db, "anthropic", "claude-sonnet-5-5", "b@example.com")
    with session_factory() as db:
        rows = db.query(AppSettingDB).all()
        assert len(rows) == 1
        assert rows[0].value == {"provider": "anthropic", "model": "claude-sonnet-5-5"}
        assert rows[0].updated_by == "b@example.com"
        assert rows[0].updated_at.replace(tzinfo=None) > datetime(2020, 1, 1)


def test_env_default_is_always_gemini(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")
    monkeypatch.setattr(config_store, "_env_provider_warned", False)
    first = config_store.env_default()
    config_store.env_default()
    assert (first.provider, first.model, first.source) == ("gemini", "gemini-3.8-flash", "env")
    assert caplog.text.count("is ignored") == 1
