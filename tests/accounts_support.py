"""Shared fixtures for the account tests (registration, consent, parent page).

The app runs with real sessions here: SessionMiddleware sets a Secure cookie
when auth is enabled, so the TestClient talks https. E-mail goes to the
console backend's in-memory outbox; tokens are read back from the links.
"""

import contextlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main
from app import email as email_module
from app.accounts import age, routes as account_routes, service
from app.config import settings
from app.db import get_db
from app.db.models import UserDB
from app.db.session import Base

PASSWORD = "zielony rower w lesie"
THIS_YEAR = 2026


def naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "admin_emails", None)
    monkeypatch.setattr(settings, "public_access", True)
    monkeypatch.setattr(settings, "allowed_emails", None)
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr(settings, "public_base_url", "https://omj.example")
    monkeypatch.setattr(settings, "rate_limit_new_users_per_day", 50)
    monkeypatch.setattr(settings, "rate_limit_new_pending_users_per_day", 50)
    monkeypatch.setattr(settings, "rate_limit_registrations_per_ip_per_day", 30)
    monkeypatch.setattr(settings, "turnstile_secret_key", None)
    monkeypatch.setattr(settings, "turnstile_site_key", None)
    # Age arithmetic is pinned to one year so the tests do not age
    monkeypatch.setattr(age, "current_year", lambda: THIS_YEAR)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    email_module.clear_outbox()
    account_routes._availability_hits.clear()
    service._registrations_by_ip.clear()
    service._registration_tickets.clear()
    # E-mails sent after the response (parent link, password reset) use the
    # test's session too; TestClient runs background tasks before returning
    monkeypatch.setattr(account_routes, "_background_session", lambda: contextlib.nullcontext(session))
    yield session
    session.close()
    email_module.clear_outbox()


def make_client(db) -> TestClient:
    main.app.dependency_overrides[get_db] = lambda: db
    # No context manager: startup events (DB warm-up, AI provider) must not run
    return TestClient(main.app, base_url="https://testserver")


@pytest.fixture
def client(db):
    yield make_client(db)
    main.app.dependency_overrides.clear()


@pytest.fixture
def other_client(db, client):
    """A second browser (the parent's phone)."""
    return TestClient(main.app, base_url="https://testserver")


def register_login(client, login="kuba_m", birth_year=2013, parent_email="mama@example.com", **extra):
    body = {
        "birth_year": birth_year,
        "login": login,
        "password": PASSWORD,
        "parent_email": parent_email,
        **extra,
    }
    return client.post("/api/auth/register/login", json=body)


def messages(to=None, subject_contains=None):
    found = email_module.outbox()
    if to is not None:
        found = [m for m in found if m["to"] == to]
    if subject_contains is not None:
        found = [m for m in found if subject_contains in m["subject"]]
    return found


def token_from(message, path: str) -> str:
    """The ?t= token of the first link in a message pointing at ``path``."""
    for link in message["links"]:
        parsed = urlparse(link)
        if parsed.path == path:
            return parse_qs(parsed.query)["t"][0]
    raise AssertionError(f"no {path} link in {message['links']}")


def consent_token(to="mama@example.com") -> str:
    found = messages(to=to, subject_contains="Prośba o zgodę")
    assert found, "no consent e-mail"
    return token_from(found[-1], "/rodzic/zgoda")


def manage_token(to="mama@example.com") -> str:
    found = messages(to=to)
    assert found, "no e-mail"
    return token_from(found[-1], "/rodzic")


def user_by_login(db, login) -> UserDB:
    db.expire_all()
    return db.query(UserDB).filter(UserDB.login == login).one()


def age_tokens(db, hours: float) -> None:
    """Move every e-mail token's created_at back in time."""
    from app.db.models import EmailTokenDB

    for token in db.query(EmailTokenDB).all():
        token.created_at -= timedelta(hours=hours)
    db.commit()


def signed_cookie(data: dict) -> str:
    """A session cookie SessionMiddleware accepts (e.g. one from before a deploy)."""
    import base64
    import json

    from itsdangerous import TimestampSigner

    signer = TimestampSigner(str(settings.session_secret_key))
    return signer.sign(base64.b64encode(json.dumps(data).encode())).decode()


def me(client) -> dict:
    return client.get("/api/auth/me").json()


LINK_RE = re.compile(r"https?://\S+")

__all__ = [
    "PASSWORD", "THIS_YEAR", "naive_now", "db", "client", "other_client", "make_client",
    "register_login", "messages", "token_from", "consent_token", "manage_token",
    "user_by_login", "age_tokens", "me", "service", "signed_cookie",
]
