"""GET/PUT /api/admin/ai-config: the runtime provider/model switch."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.ai.config_store as config_store
import app.ai.factory as factory
import app.main as main
from app.ai.factory import AIProviderError
from app.config import settings
from app.db import get_db
from app.db.models import AppSettingDB
from app.db.session import Base

GEMINI_KEY = "gm-secret-test-key-123"
ANTHROPIC_KEY = "sk-ant-secret-test-key-456"
ADMIN_EMAIL = "admin@example.com"


class _StubProvider:
    def __init__(self, error=None):
        self.error = error

    async def ping(self):
        if self.error:
            raise self.error


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(settings, "session_secret_key", "test-secret-key")
    monkeypatch.setattr(settings, "gemini_api_key", GEMINI_KEY)
    monkeypatch.setattr(settings, "anthropic_api_key", ANTHROPIC_KEY)
    monkeypatch.setattr(settings, "anthropic_processor_approved", True)
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")
    monkeypatch.setattr(settings, "ai_provider", "gemini")

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(config_store, "SessionLocal", Session)
    config_store.invalidate_cache()

    session = Session()

    def override_get_db():
        yield session

    main.app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(main, "get_current_user", lambda request: {"email": ADMIN_EMAIL})

    ping_state = {"error": None, "calls": []}

    def fake_build(provider, model):
        ping_state["calls"].append((provider, model))
        return _StubProvider(ping_state["error"])

    monkeypatch.setattr(factory, "build_provider", fake_build)
    yield session, ping_state
    session.close()
    main.app.dependency_overrides.clear()
    config_store.invalidate_cache()


@pytest.fixture
def admin(env, monkeypatch):
    monkeypatch.setattr(main, "_require_admin", lambda request: None)
    session, ping_state = env
    return TestClient(main.app), session, ping_state


def _stored(session):
    session.expire_all()
    return session.get(AppSettingDB, config_store.AI_MODEL_KEY)


def test_non_admin_is_403(env, monkeypatch):
    monkeypatch.setattr(main, "verify_auth", lambda request: True)
    monkeypatch.setattr(main, "_is_admin", lambda request: False)
    client = TestClient(main.app)

    assert client.get("/api/admin/ai-config").status_code == 403
    response = client.put("/api/admin/ai-config", json={"provider": "gemini", "model": "gemini-3.8-flash"})
    assert response.status_code == 403
    assert _stored(env[0]) is None


def test_get_without_row_is_env_and_hides_keys(admin):
    client, _, _ = admin

    response = client.get("/api/admin/ai-config")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["active"] == {
        "provider": "gemini", "model": "gemini-3.8-flash", "model_label": "Gemini 3.8 Flash",
        "source": "env", "updated_at": None, "updated_by": None,
    }
    providers = {p["id"]: p for p in body["providers"]}
    assert list(providers) == ["gemini", "anthropic"]
    assert providers["gemini"]["label"] == "Google Gemini"
    assert providers["anthropic"]["label"] == "Anthropic Claude"
    assert providers["anthropic"]["configured"] is True
    assert providers["anthropic"]["approved"] is True
    assert {"id": "claude-opus-5-5", "label": "Claude Opus 5.5"} in providers["anthropic"]["models"]
    assert providers["gemini"]["models"][0] == {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash"}
    assert GEMINI_KEY not in response.text
    assert ANTHROPIC_KEY not in response.text


def test_get_reports_unconfigured_and_unapproved(admin, monkeypatch):
    client, _, _ = admin
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "anthropic_processor_approved", False)

    providers = {p["id"]: p for p in client.get("/api/admin/ai-config").json()["providers"]}

    assert providers["anthropic"]["configured"] is False
    assert providers["anthropic"]["approved"] is False
    assert providers["gemini"]["configured"] is True
    assert providers["gemini"]["approved"] is True


def test_get_env_model_outside_catalog_uses_raw_id(admin, monkeypatch):
    client, _, _ = admin
    monkeypatch.setattr(settings, "gemini_model", "gemini-9-experimental")

    active = client.get("/api/admin/ai-config").json()["active"]

    assert active["model"] == "gemini-9-experimental"
    assert active["model_label"] == "gemini-9-experimental"


@pytest.mark.parametrize("payload", [
    {"provider": "gemini", "model": "claude-opus-5-5"},
    {"provider": "openai", "model": "gpt-9"},
    {"provider": "anthropic", "model": "claude-unknown"},
])
def test_put_unknown_model_is_400(admin, payload):
    client, session, ping_state = admin

    response = client.put("/api/admin/ai-config", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Nieznany model."
    assert _stored(session) is None
    assert ping_state["calls"] == []


def test_put_unapproved_anthropic_is_409(admin, monkeypatch):
    client, session, ping_state = admin
    monkeypatch.setattr(settings, "anthropic_processor_approved", False)

    response = client.put("/api/admin/ai-config", json={"provider": "anthropic", "model": "claude-opus-5-5"})

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Dostawca Anthropic nie jest jeszcze zatwierdzony jako podmiot przetwarzający "
        "(ANTHROPIC_PROCESSOR_APPROVED)."
    )
    assert _stored(session) is None
    assert ping_state["calls"] == []


def test_put_without_key_is_409(admin, monkeypatch):
    client, session, ping_state = admin
    monkeypatch.setattr(settings, "anthropic_api_key", None)

    response = client.put("/api/admin/ai-config", json={"provider": "anthropic", "model": "claude-opus-5-5"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Brak klucza API dla tego dostawcy."
    assert _stored(session) is None
    assert ping_state["calls"] == []


def test_put_ping_failure_is_502(admin):
    client, session, ping_state = admin
    ping_state["error"] = AIProviderError("Model x nie odpowiada")

    response = client.put("/api/admin/ai-config", json={"provider": "anthropic", "model": "claude-opus-5-5"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Model x nie odpowiada"
    assert ping_state["calls"] == [("anthropic", "claude-opus-5-5")]
    assert _stored(session) is None
    active = client.get("/api/admin/ai-config").json()["active"]
    assert (active["provider"], active["model"], active["source"]) == ("gemini", "gemini-3.8-flash", "env")


def test_put_ping_timeout_is_502(admin, monkeypatch):
    client, session, _ = admin
    monkeypatch.setattr(main, "AI_CONFIG_PING_TIMEOUT_SECONDS", 0.01)

    class _Slow:
        async def ping(self):
            import asyncio
            await asyncio.sleep(1)

    monkeypatch.setattr(factory, "build_provider", lambda p, m: _Slow())

    response = client.put("/api/admin/ai-config", json={"provider": "anthropic", "model": "claude-opus-5-5"})

    assert response.status_code == 502
    assert _stored(session) is None


def test_put_success_stores_and_switches(admin):
    client, session, ping_state = admin

    response = client.put("/api/admin/ai-config", json={"provider": "anthropic", "model": "claude-sonnet-5-5"})

    assert response.status_code == 200, response.text
    active = response.json()["active"]
    assert active["provider"] == "anthropic"
    assert active["model"] == "claude-sonnet-5-5"
    assert active["model_label"] == "Claude Sonnet 5.5"
    assert active["source"] == "db"
    assert active["updated_by"] == ADMIN_EMAIL
    assert active["updated_at"] is not None

    row = _stored(session)
    assert row.value == {"provider": "anthropic", "model": "claude-sonnet-5-5"}
    assert row.updated_by == ADMIN_EMAIL

    body = client.get("/api/admin/ai-config").json()
    assert body["active"]["source"] == "db"
    assert body["active"]["model"] == "claude-sonnet-5-5"

    current = config_store.get_active_model()
    assert (current.provider, current.model, current.source) == ("anthropic", "claude-sonnet-5-5", "db")
    assert ANTHROPIC_KEY not in response.text
