"""Registration abuse (security audit 2026-10): per-IP and split global caps,
Turnstile, dot-free logins that mail clients cannot link, Gmail aliases of the
child's own address, and answers that do not reveal whether an account exists."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

import app.main as main
from app.accounts import turnstile
from app.config import settings
from app.db.models import ParentDB, UserDB
from app.accounts.routes import _background_session as real_background_session
from app.email.templates import nolink, render

from accounts_support import *  # noqa: F401,F403 - fixtures
from accounts_support import (
    PASSWORD,
    consent_token,
    messages,
    register_login,
    service,
)


class FakeGoogle:
    def __init__(self, sub="g-123", email="jan.kowalski@gmail.com"):
        self.userinfo = {"sub": sub, "email": email, "email_verified": True, "name": "Jan"}

    async def authorize_access_token(self, request):
        return {"userinfo": self.userinfo}


@pytest.fixture
def google(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(main, "oauth", SimpleNamespace(google=fake))

    async def member(email):
        return True

    monkeypatch.setattr(main, "check_group_membership", member)
    return fake


def callback(client):
    return client.get("/auth/callback", follow_redirects=False)


def from_ip(ip: str) -> dict:
    return {"cf-connecting-ip": ip}


# --------------------------------------------------------------------- logins without dots


class TestDotFreeLogins:
    def test_new_login_with_a_dot_is_refused(self, client, db):
        response = register_login(client, login="www.scam-site.com")
        assert response.status_code == 400
        assert response.json()["field"] == "login"
        assert "_ i -" in response.json()["detail"]
        assert db.query(UserDB).count() == 0
        assert messages() == []

    def test_availability_check_refuses_dots(self, client, db):
        body = client.get("/api/auth/login-available", params={"login": "kuba.m"}).json()
        assert body["valid"] is False

    def test_existing_dotted_login_still_signs_in(self, client, db):
        parent = service.ensure_parent(db, "mama@example.com")
        user = service.create_login_user(
            db, login="kuba.m", password=PASSWORD, birth_year=2013, parent_email=parent.email
        )
        user.status = "active"
        db.commit()
        response = client.post("/api/auth/login", json={"login": "kuba.m", "password": PASSWORD})
        assert response.status_code == 200, response.text

    def test_dotted_login_is_not_linkable_in_emails(self, db):
        html, text = render(
            "password_reset", subject="s", login="www.scam-site.com", reset_url="https://x/r",
            manage_url="https://x/m",
        )
        for body in (html, text):
            assert "www.scam-site.com" not in body
            assert "www.​scam-site.​com" in body
        html, text = render(
            "consent_request", subject="s", child_identifier_label="Login dziecka",
            child_identifier="www.scam-site.com", consent_url="https://x/c", decline_url="https://x/d",
            manage_url="https://x/m", submission_retention="24 miesiące",
            inactive_retention="36 miesięcy", deadline="1 stycznia 2027",
        )
        assert "www.scam-site.com" not in html + text

    def test_nolink_output_is_still_escaped(self):
        html, _ = render(
            "password_reset", subject="s", login="<b>x</b>", reset_url="https://x/r",
            manage_url="https://x/m",
        )
        assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html

    def test_nolink(self):
        assert nolink("kid@gmail.com") == "kid@​gmail.​com"
        assert nolink("kuba_m") == "kuba_m"


# --------------------------------------------------------------------- Gmail aliases


class TestMailboxKey:
    @pytest.mark.parametrize(
        "a, b",
        [
            ("jan.kowalski@gmail.com", "jankowalski@gmail.com"),
            ("Jan.Kowalski@Gmail.com", "j.a.n.k.o.w.a.l.s.k.i+mama@googlemail.com"),
            ("jan+rodzic@example.com", "JAN@example.com"),
        ],
    )
    def test_same_mailbox(self, a, b):
        assert service.same_mailbox(a, b)

    @pytest.mark.parametrize(
        "a, b",
        [
            ("jan.kowalski@example.com", "jankowalski@example.com"),  # dots only matter at Gmail
            ("jan@gmail.com", "jan@example.com"),
            ("", ""),
            (None, "jan@gmail.com"),
        ],
    )
    def test_different_mailbox(self, a, b):
        assert not service.same_mailbox(a, b)


class TestSelfConsentViaAlias:
    @pytest.mark.parametrize(
        "alias", ["jankowalski@gmail.com", "jan.kowalski+mama@gmail.com", "Jan.Kowalski@googlemail.com"]
    )
    def test_after_google(self, client, db, google, alias):
        callback(client)
        response = client.post("/api/auth/register/google", json={"birth_year": 2013, "parent_email": alias})
        assert response.status_code == 400
        assert response.json()["field"] == "parent_email"
        assert db.query(UserDB).count() == 0
        assert messages() == []

    def test_before_google(self, client, db, google):
        response = client.post(
            "/api/auth/register/google",
            json={"birth_year": 2013, "parent_email": "jan.kowalski+mama@gmail.com"},
        )
        assert response.json()["action"] == "google"  # the identity is not known yet
        response = callback(client)
        assert response.headers["location"] == "/rejestracja?google=1&blad=ten-sam-adres"
        assert db.query(UserDB).count() == 0
        assert messages() == []

    def test_a_real_parent_address_passes(self, client, db, google):
        callback(client)
        response = client.post(
            "/api/auth/register/google", json={"birth_year": 2013, "parent_email": "mama.kowalska@gmail.com"}
        )
        assert response.status_code == 200, response.text


# --------------------------------------------------------------------- global caps


class TestSeparateGlobalCaps:
    def test_pending_flood_does_not_block_16_plus_google(self, client, db, google, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_new_pending_users_per_day", 2)
        monkeypatch.setattr(settings, "rate_limit_new_users_per_day", 2)
        assert register_login(client, login="bot_1", parent_email="a@example.com").status_code == 200
        client.cookies.clear()
        assert register_login(client, login="bot_2", parent_email="b@example.com").status_code == 200
        client.cookies.clear()
        response = register_login(client, login="bot_3", parent_email="c@example.com")
        assert response.status_code == 429 and response.json()["code"] == "new_users_limit"
        client.cookies.clear()

        callback(client)
        response = client.post("/api/auth/register/google", json={"birth_year": 2005, "accept_terms": True})
        assert response.status_code == 200, response.text
        assert db.query(UserDB).filter(UserDB.google_sub == "g-123").one().status == "active"

    def test_under_16_google_counts_as_pending(self, client, db, google, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_new_pending_users_per_day", 0)
        callback(client)
        response = client.post("/api/auth/register/google", json={"birth_year": 2013, "parent_email": "mama@example.com"})
        assert response.status_code == 429

    def test_full_active_pool_does_not_block_login_accounts(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_new_users_per_day", 0)
        assert register_login(client).status_code == 200


# --------------------------------------------------------------------- per-IP limit


class TestPerIpLimit:
    def test_limit_per_ip(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_registrations_per_ip_per_day", 2)
        for n in (1, 2):
            response = client.post(
                "/api/auth/register/login",
                headers=from_ip("203.0.113.7"),
                json={"birth_year": 2013, "login": f"kid_{n}", "password": PASSWORD, "parent_email": f"p{n}@example.com"},
            )
            assert response.status_code == 200, response.text
            client.cookies.clear()
        body = {"birth_year": 2013, "login": "kid_3", "password": PASSWORD, "parent_email": "p3@example.com"}
        response = client.post("/api/auth/register/login", headers=from_ip("203.0.113.7"), json=body)
        assert response.status_code == 429
        assert response.json()["code"] == "registration_ip_limit"
        assert len(messages()) == 2
        # Another network is not affected
        assert client.post("/api/auth/register/login", headers=from_ip("198.51.100.1"), json=body).status_code == 200

    def test_ip_is_stored_only_as_hmac(self, client, db):
        register_login(client)
        assert "127.0.0.1" not in json.dumps(list(service._registrations_by_ip))
        assert "testclient" not in json.dumps(list(service._registrations_by_ip))

    def test_google_after_redirect_counts(self, client, db, google, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_registrations_per_ip_per_day", 1)
        register_login(client)
        client.cookies.clear()
        # Before the redirect: refused right away, nothing stored
        response = client.post("/api/auth/register/google", json={"birth_year": 2005, "accept_terms": True})
        assert response.status_code == 429
        # Callback from an earlier, accepted answer: refused at creation
        monkeypatch.setattr(settings, "rate_limit_registrations_per_ip_per_day", 2)
        client.post("/api/auth/register/google", json={"birth_year": 2005, "accept_terms": True})
        monkeypatch.setattr(settings, "rate_limit_registrations_per_ip_per_day", 1)
        response = callback(client)
        assert response.headers["location"] == "/login?error=rate_limit_registrations_ip"
        assert db.query(UserDB).filter(UserDB.google_sub.isnot(None)).count() == 0

    def test_allowlisted_google_address_bypasses(self, client, db, google, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_registrations_per_ip_per_day", 0)
        monkeypatch.setattr(settings, "allowed_emails", "jan.kowalski@gmail.com")
        callback(client)
        response = client.post("/api/auth/register/google", json={"birth_year": 2005, "accept_terms": True})
        assert response.status_code == 200, response.text

    def test_failed_registrations_do_not_use_slots(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "rate_limit_registrations_per_ip_per_day", 1)
        assert register_login(client, login="ab").status_code == 400
        assert register_login(client, parent_email="nie-adres").status_code == 400
        assert register_login(client).status_code == 200

    def test_slots_expire_after_24_hours(self, monkeypatch):
        service._registrations_by_ip.clear()
        monkeypatch.setattr(settings, "rate_limit_registrations_per_ip_per_day", 1)
        assert service.take_registration_slot("ip-a")
        assert not service.take_registration_slot("ip-a")
        service._registrations_by_ip["ip-a"] = [service.now() - service.REGISTRATION_IP_WINDOW]
        assert service.take_registration_slot("ip-a")
        service._registrations_by_ip.clear()


# --------------------------------------------------------------------- Turnstile


def siteverify(handler):
    """Install a fake Cloudflare siteverify; records the form posts."""
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == turnstile.SITEVERIFY_URL
        form = dict(httpx.QueryParams(request.content.decode()))
        calls.append(form)
        return handler(form)

    return calls, httpx.MockTransport(respond)


def cloudflare_test_keys(form: dict) -> httpx.Response:
    """Behaves like Cloudflare does for its documented test secrets."""
    if form["secret"] == turnstile.TEST_SECRET_PASS:
        return httpx.Response(200, json={"success": True, "error-codes": [], "action": "register"})
    return httpx.Response(200, json={"success": False, "error-codes": ["invalid-input-response"]})


@pytest.fixture
def turnstile_on(monkeypatch):
    monkeypatch.setattr(settings, "turnstile_site_key", turnstile.TEST_SITE_KEY)
    monkeypatch.setattr(settings, "turnstile_secret_key", turnstile.TEST_SECRET_PASS)
    calls, transport = siteverify(cloudflare_test_keys)
    monkeypatch.setattr(turnstile, "_transport", transport)
    return calls


class TestTurnstile:
    def test_site_key_is_exposed_only_when_enabled(self, client, db, monkeypatch):
        assert client.get("/api/auth/register/state").json()["turnstile_site_key"] is None
        monkeypatch.setattr(settings, "turnstile_site_key", turnstile.TEST_SITE_KEY)
        assert client.get("/api/auth/register/state").json()["turnstile_site_key"] is None
        monkeypatch.setattr(settings, "turnstile_secret_key", turnstile.TEST_SECRET_PASS)
        assert client.get("/api/auth/register/state").json()["turnstile_site_key"] == turnstile.TEST_SITE_KEY

    def test_disabled_without_secret(self, client, db):
        assert register_login(client).status_code == 200

    def test_login_registration_needs_a_token(self, client, db, turnstile_on):
        response = register_login(client)
        assert response.status_code == 400
        assert response.json()["code"] == "turnstile_failed"
        assert db.query(UserDB).count() == 0
        assert messages() == []
        assert turnstile_on == []  # no token: Cloudflare is not even asked

    def test_login_registration_with_a_valid_token(self, client, db, turnstile_on):
        response = register_login(client, turnstile_token="XXXX.DUMMY.TOKEN.XXXX")
        assert response.status_code == 200, response.text
        (call,) = turnstile_on
        assert call["secret"] == turnstile.TEST_SECRET_PASS
        assert call["response"] == "XXXX.DUMMY.TOKEN.XXXX"
        assert "remoteip" not in call  # nothing about the child goes to Cloudflare

    def test_rejected_token(self, client, db, turnstile_on, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", turnstile.TEST_SECRET_FAIL)
        response = register_login(client, turnstile_token="XXXX.DUMMY.TOKEN.XXXX")
        assert response.status_code == 400 and response.json()["code"] == "turnstile_failed"
        assert db.query(UserDB).count() == 0 and messages() == []

    def test_field_errors_come_first_and_do_not_spend_the_token(self, client, db, turnstile_on):
        response = register_login(client, login="a.b", turnstile_token="XXXX.DUMMY.TOKEN.XXXX")
        assert response.json()["field"] == "login"
        assert turnstile_on == []

    def test_a_token_for_another_action_is_refused(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", turnstile.TEST_SECRET_PASS)
        _, transport = siteverify(lambda form: httpx.Response(200, json={"success": True, "action": "login"}))
        monkeypatch.setattr(turnstile, "_transport", transport)
        assert register_login(client, turnstile_token="t").json()["code"] == "turnstile_failed"

    @pytest.mark.parametrize(
        "failure",
        [
            lambda request: (_ for _ in ()).throw(httpx.ConnectTimeout("slow")),
            lambda request: httpx.Response(502, text="<html>bad gateway</html>"),
        ],
    )
    def test_cloudflare_unreachable_fails_closed(self, client, db, monkeypatch, failure):
        monkeypatch.setattr(settings, "turnstile_secret_key", turnstile.TEST_SECRET_PASS)
        monkeypatch.setattr(turnstile, "_transport", httpx.MockTransport(failure))
        response = register_login(client, turnstile_token="t")
        assert response.status_code == 400
        assert db.query(UserDB).count() == 0

    def test_google_before_redirect_needs_a_token(self, client, db, google, turnstile_on):
        response = client.post("/api/auth/register/google", json={"birth_year": 2013, "parent_email": "mama@example.com"})
        assert response.json()["code"] == "turnstile_failed"
        # No answers stored, so the callback creates nothing
        assert callback(client).headers["location"] == "/rejestracja?google=1"
        assert db.query(UserDB).count() == 0 and messages() == []

    def test_google_before_redirect_with_token(self, client, db, google, turnstile_on):
        body = {"birth_year": 2013, "parent_email": "mama@example.com", "turnstile_token": "t"}
        assert client.post("/api/auth/register/google", json=body).json()["action"] == "google"
        assert callback(client).headers["location"] == "/konto/oczekuje"
        assert consent_token()

    def test_google_after_redirect_needs_a_token(self, client, db, google, turnstile_on):
        callback(client)
        body = {"birth_year": 2005, "accept_terms": True}
        assert client.post("/api/auth/register/google", json=body).json()["code"] == "turnstile_failed"
        assert db.query(UserDB).count() == 0
        body["turnstile_token"] = "t"
        assert client.post("/api/auth/register/google", json=body).status_code == 200

    def test_real_verify_disabled_returns_true(self, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", None)
        assert asyncio.run(turnstile.verify(None)) is True

    def test_oversized_token_is_not_sent(self, monkeypatch):
        monkeypatch.setattr(settings, "turnstile_secret_key", turnstile.TEST_SECRET_PASS)
        calls, transport = siteverify(cloudflare_test_keys)
        monkeypatch.setattr(turnstile, "_transport", transport)
        assert asyncio.run(turnstile.verify("x" * (turnstile.TOKEN_MAX + 1))) is False
        assert calls == []


# --------------------------------------------------------------------- no existence oracle


class TestSameAnswerWhetherOrNotAccountExists:
    def _broken_provider(self, monkeypatch):
        from app.email import EmailSendError

        attempts = []

        async def broken(*args, **kwargs):
            attempts.append(args[0])
            raise EmailSendError("down")

        monkeypatch.setattr(service, "send_email", broken)
        return attempts

    def test_password_reset_provider_failure_is_not_revealed(self, client, other_client, db, monkeypatch):
        register_login(client)
        attempts = self._broken_provider(monkeypatch)
        known = other_client.post("/api/auth/password-reset/request", json={"login": "kuba_m"})
        unknown = other_client.post("/api/auth/password-reset/request", json={"login": "nikt"})
        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json() == {"sent": True}
        assert attempts == ["mama@example.com"]  # the send was attempted, after the response

    def test_password_reset_sent_in_the_background(self, client, other_client, db):
        register_login(client)
        other_client.post("/api/auth/password-reset/request", json={"login": "kuba_m"})
        assert messages(to="mama@example.com", subject_contains="Zmiana hasła")

    def test_parent_link_provider_failure_is_not_revealed(self, client, other_client, db, monkeypatch):
        register_login(client)
        attempts = self._broken_provider(monkeypatch)
        known = other_client.post("/api/parent/request-link", json={"email": "mama@example.com"})
        unknown = other_client.post("/api/parent/request-link", json={"email": "nikt@example.com"})
        assert known.json() == unknown.json() == {"sent": True}
        assert attempts == ["mama@example.com"]

    @pytest.mark.parametrize(
        "handler, model, body",
        [
            ("parent_request_link", "ParentLinkRequest", {"email": "mama@example.com"}),
            ("password_reset_request", "ResetRequest", {"login": "kuba_m"}),
        ],
    )
    def test_handler_returns_before_any_lookup_or_send(self, client, db, monkeypatch, handler, model, body):
        """The handler itself neither queries nor sends: both happen in a
        background task, after the response has gone out."""
        from fastapi import BackgroundTasks

        from app.accounts import routes as account_routes

        register_login(client)
        sent = []

        async def record(to, *args, **kwargs):
            sent.append(to)

        monkeypatch.setattr(service, "send_email", record)
        handler = getattr(account_routes, handler)
        model = getattr(account_routes, model)
        background = BackgroundTasks()
        result = asyncio.run(handler(model(**body), background))
        assert result == {"sent": True}
        assert sent == []
        assert len(background.tasks) == 1
        asyncio.run(background())
        assert sent == ["mama@example.com"]

    def test_background_session_is_its_own_and_closed(self, monkeypatch):
        from app.accounts import routes as account_routes

        closed = []

        class FakeSession:
            def close(self):
                closed.append(True)

        monkeypatch.setattr(account_routes, "SessionLocal", FakeSession)
        with real_background_session() as session:
            assert isinstance(session, FakeSession)
        assert closed == [True]
