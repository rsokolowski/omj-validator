"""Registration: login + password, Google (both orderings), the age step for
existing accounts, the pending screen's endpoints and the new-user limit."""

from types import SimpleNamespace

import pytest

import app.main as main
from app.auth import SESSION_PENDING_GOOGLE_KEY
from app.db.models import ConsentDB, ParentDB, UserDB

from accounts_support import *  # noqa: F401,F403 - fixtures
from accounts_support import (
    PASSWORD,
    age_tokens,
    consent_token,
    me,
    messages,
    register_login,
    signed_cookie,
    user_by_login,
)


class TestLoginRegistration:
    def test_creates_pending_account_and_logs_in(self, client, db):
        response = register_login(client)
        assert response.status_code == 200, response.text
        assert response.json() == {"redirect": "/konto/oczekuje", "email_sent": True}

        user = user_by_login(db, "kuba_m")
        assert user.status == "pending_parent"
        assert user.pending_since is not None
        assert user.email is None and user.google_sub is None
        assert user.password_hash.startswith("$argon2id$")
        assert user.parent.email == "mama@example.com"
        assert len(user.id) == 32  # uuid4().hex

        state = me(client)
        assert state["is_authenticated"] is True
        assert state["user"]["login"] == "kuba_m"
        assert state["account"]["status"] == "pending_parent"
        assert state["account"]["login_method"] == "login"
        assert state["account"]["pending"]["parent_email"] == "m***@example.com"
        assert state["account"]["pending"]["deadline"]

    def test_login_account_needs_a_parent_even_at_16_plus(self, client, db):
        register_login(client, birth_year=2000)
        assert user_by_login(db, "kuba_m").status == "pending_parent"

    def test_consent_email_names_the_login_and_nothing_else(self, client, db):
        register_login(client)
        (message,) = messages(to="mama@example.com")
        assert message["subject"] == "Prośba o zgodę — konto Twojego dziecka w serwisie Trener OMJ"
        assert "kuba_m" in message["text"]
        assert "Wyrażam zgodę" in message["html"]
        assert "Nie zgadzam się" in message["html"]
        assert 'lang="pl"' in message["html"]
        assert "https://omj.example/images/logo-email.png" in message["html"]
        assert any("/rodzic?t=" in link for link in message["links"])  # manage link

    def test_login_is_stored_lower_case_and_unique(self, client, db):
        assert register_login(client, login="Kuba_M").status_code == 200
        response = register_login(client, login="KUBA_m", parent_email="tata@example.com")
        assert response.status_code == 409
        assert response.json()["field"] == "login"

    @pytest.mark.parametrize(
        "overrides, field",
        [
            ({"login": "a"}, "login"),
            ({"password": "short"}, "password"),
            ({"password": "kuba_m"}, "password"),
            ({"password": "Password1"}, "password"),
            ({"parent_email": "nie-adres"}, "parent_email"),
            ({"birth_year": 2025}, "birth_year"),
            ({"birth_year": 2010}, "turned_16"),  # 16 this year: follow-up required
        ],
    )
    def test_validation_errors_name_the_field(self, client, db, overrides, field):
        body = {"birth_year": 2013, "login": "kuba_m", "password": PASSWORD, "parent_email": "mama@example.com"}
        body.update(overrides)
        response = client.post("/api/auth/register/login", json=body)
        assert response.status_code in (400, 409)
        assert response.json()["field"] == field
        assert db.query(UserDB).count() == 0

    def test_login_available_endpoint(self, client, db):
        register_login(client)
        assert client.get("/api/auth/login-available", params={"login": "kuba_m"}).json()["available"] is False
        free = client.get("/api/auth/login-available", params={"login": "ola_k"}).json()
        assert free == {"login": "ola_k", "valid": True, "available": True, "message": None}
        assert client.get("/api/auth/login-available", params={"login": "a"}).json()["valid"] is False

    def test_login_available_is_rate_limited(self, client, db):
        codes = [client.get("/api/auth/login-available", params={"login": "ola_k"}).status_code for _ in range(31)]
        assert codes[-1] == 429
        assert codes[0] == 200

    def test_email_failure_still_creates_account(self, client, db, monkeypatch):
        from app.accounts import service
        from app.email import EmailSendError

        async def broken(*args, **kwargs):
            raise EmailSendError("down")

        monkeypatch.setattr(service, "send_email", broken)
        response = register_login(client)
        assert response.json()["email_sent"] is False
        assert user_by_login(db, "kuba_m").status == "pending_parent"
        # No slot used: the pending screen can send right away
        assert me(client)["account"]["pending"]["last_sent_at"] is None

    def test_new_user_limit(self, client, db, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "rate_limit_new_pending_users_per_day", 1)
        assert register_login(client).status_code == 200
        response = register_login(client, login="ola_k")
        assert response.status_code == 429
        assert response.json()["code"] == "new_users_limit"


# --------------------------------------------------------------------- Google


class FakeGoogle:
    def __init__(self, sub="g-123", email="kid@gmail.com", name="Kid Kowalski"):
        self.userinfo = {"sub": sub, "email": email, "email_verified": True, "name": name}

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


class TestGoogleRegistration:
    def test_unknown_identity_creates_nothing_and_goes_to_registration(self, client, db, google):
        response = callback(client)
        assert response.status_code == 303
        assert response.headers["location"] == "/rejestracja?google=1"
        assert db.query(UserDB).count() == 0
        assert me(client)["is_authenticated"] is False
        assert client.get("/api/auth/register/state").json()["google"] == {"email": "kid@gmail.com"}

    def test_finish_after_google_under_16(self, client, db, google):
        callback(client)
        response = client.post(
            "/api/auth/register/google",
            json={"birth_year": 2013, "parent_email": "Mama@Example.com "},
        )
        assert response.status_code == 200, response.text
        assert response.json()["redirect"] == "/konto/oczekuje"
        user = db.query(UserDB).one()
        assert user.google_sub == "g-123" and user.id != "g-123"
        assert user.status == "pending_parent"
        assert user.parent.email == "mama@example.com"
        (message,) = messages(to="mama@example.com")
        # Shown with zero-width spaces so mail clients do not link it
        assert "kid@gmail.com" in message["text"].replace("\u200b", "")
        assert "Kowalski" not in message["text"] + message["html"]  # no display name
        assert me(client)["account"]["status"] == "pending_parent"

    def test_finish_after_google_16_plus_records_self_consent(self, client, db, google):
        callback(client)
        response = client.post("/api/auth/register/google", json={"birth_year": 2005, "accept_terms": True})
        assert response.json()["redirect"] == "/years"
        user = db.query(UserDB).one()
        assert user.status == "active"
        consent = db.query(ConsentDB).one()
        assert consent.kind == "self" and consent.terms_version
        assert messages() == []

    def test_16_plus_needs_the_terms_checkbox(self, client, db, google):
        callback(client)
        response = client.post("/api/auth/register/google", json={"birth_year": 2005})
        assert response.status_code == 400
        assert response.json()["field"] == "accept_terms"

    def test_parent_email_must_differ_from_childs_google_email(self, client, db, google):
        callback(client)
        response = client.post(
            "/api/auth/register/google", json={"birth_year": 2013, "parent_email": "KID@gmail.com"}
        )
        assert response.status_code == 400
        assert response.json()["field"] == "parent_email"

    def test_answers_first_then_google(self, client, db, google):
        response = client.post(
            "/api/auth/register/google", json={"birth_year": 2010, "turned_16": False, "parent_email": "tata@example.com"}
        )
        assert response.json() == {"action": "google", "redirect": "/login/google?register=1"}
        assert db.query(UserDB).count() == 0

        response = callback(client)
        assert response.headers["location"] == "/konto/oczekuje"
        user = db.query(UserDB).one()
        assert user.birth_year == 2010 and user.status == "pending_parent"
        assert messages(to="tata@example.com")

    def test_answers_first_with_own_address_as_parent(self, client, db, google):
        client.post("/api/auth/register/google", json={"birth_year": 2013, "parent_email": "kid@gmail.com"})
        response = callback(client)
        assert response.headers["location"] == "/rejestracja?google=1&blad=ten-sam-adres"
        assert db.query(UserDB).count() == 0

    def test_known_identity_just_logs_in(self, client, db, google):
        db.add(UserDB(id="g-123", google_sub="g-123", email="kid@gmail.com", birth_year=2005))
        db.commit()
        response = callback(client)
        assert response.headers["location"] == "/years"
        assert me(client)["user"]["id"] == "g-123"

    def test_pending_google_expires_after_30_minutes(self, client, db, google, monkeypatch):
        import time as time_module

        callback(client)
        real_time = time_module.time
        monkeypatch.setattr(time_module, "time", lambda: real_time() + 31 * 60)
        assert client.get("/api/auth/register/state").json()["google"] == None

    def test_new_user_limit_applies_to_google(self, client, db, google, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "rate_limit_new_users_per_day", 0)
        callback(client)
        response = client.post("/api/auth/register/google", json={"birth_year": 2005, "accept_terms": True})
        assert response.status_code == 429
        assert db.query(UserDB).count() == 0

    def test_plain_google_login_drops_stale_answers(self, client, db, google, monkeypatch):
        client.post("/api/auth/register/google", json={"birth_year": 2005, "accept_terms": True})
        monkeypatch.setattr(main.settings, "google_client_id", "id")

        async def fake_redirect(request, uri):
            from fastapi.responses import RedirectResponse

            return RedirectResponse("https://accounts.google.com/")

        google.authorize_redirect = fake_redirect
        client.get("/login/google", follow_redirects=False)  # no ?register=1
        response = callback(client)
        assert response.headers["location"] == "/rejestracja?google=1"
        assert db.query(UserDB).count() == 0


# --------------------------------------------------------------------- existing accounts


@pytest.fixture
def legacy_user(db):
    db.add(UserDB(id="111", google_sub="111", email="old@gmail.com", name="Old"))
    db.commit()


def login_legacy(client):
    """A session cookie from before this feature: only google_sub."""
    client.cookies.set("session", signed_cookie({"user": {"google_sub": "111", "email": "old@gmail.com", "is_group_member": True}}))


class TestExistingAccounts:
    def test_legacy_session_is_accepted_and_needs_profile(self, client, db, legacy_user):
        login_legacy(client)
        state = me(client)
        assert state["is_authenticated"] is True
        assert state["user"]["id"] == "111"
        assert state["account"]["needs_profile"] is True

    def test_writes_refused_until_profile_done(self, client, db, legacy_user):
        login_legacy(client)
        response = client.post("/api/patterns", json={})
        assert response.status_code == 403
        assert response.json()["code"] == "profile_incomplete"

    def test_16_plus_finishes_with_self_consent(self, client, db, legacy_user):
        login_legacy(client)
        response = client.post("/api/auth/profile", json={"birth_year": 2008, "accept_terms": True})
        assert response.json()["redirect"] == "/years"
        user = db.get(UserDB, "111")
        db.refresh(user)
        assert user.birth_year == 2008 and user.status == "active"
        assert db.query(ConsentDB).one().kind == "self"
        assert me(client)["account"]["needs_profile"] is False

    def test_under_16_goes_pending_and_keeps_data(self, client, db, legacy_user):
        login_legacy(client)
        response = client.post("/api/auth/profile", json={"birth_year": 2013, "parent_email": "mama@example.com"})
        assert response.json() == {"redirect": "/konto/oczekuje", "email_sent": True}
        user = db.get(UserDB, "111")
        db.refresh(user)
        assert user.status == "pending_parent" and user.pending_since is not None
        assert messages(to="mama@example.com")

    def test_profile_cannot_be_redone(self, client, db, legacy_user):
        login_legacy(client)
        client.post("/api/auth/profile", json={"birth_year": 2008, "accept_terms": True})
        response = client.post("/api/auth/profile", json={"birth_year": 2013, "parent_email": "x@example.com"})
        assert response.status_code == 409


# --------------------------------------------------------------------- pending screen


class TestPendingScreen:
    def test_resend_has_a_cooldown_and_a_daily_cap(self, client, db):
        register_login(client)
        first = client.post("/api/account/consent/resend")
        assert first.status_code == 429 and first.json()["code"] == "email_cooldown"
        assert int(first.headers["Retry-After"]) <= 60

        age_tokens(db, hours=0.1)
        assert client.post("/api/account/consent/resend").status_code == 200
        age_tokens(db, hours=0.1)
        assert client.post("/api/account/consent/resend").status_code == 200
        age_tokens(db, hours=0.1)
        capped = client.post("/api/account/consent/resend")
        assert capped.status_code == 429
        assert capped.json()["detail"] == "Wysłaliśmy już kilka wiadomości. Spróbuj jutro."
        assert len(messages(subject_contains="Prośba o zgodę")) == 3

    def test_five_per_parent_address_per_day(self, client, db, other_client):
        from accounts_support import make_client

        for i in range(5):
            c = make_client(db)
            assert register_login(c, login=f"dziecko{i}").json()["email_sent"] is True
        response = register_login(make_client(db), login="dziecko5")
        assert response.json()["email_sent"] is False

    def test_failed_send_does_not_use_a_slot(self, client, db, monkeypatch):
        from app.accounts import service
        from app.email import EmailSendError, send_email

        register_login(client)
        age_tokens(db, hours=0.1)
        state = {"down": True}

        async def flaky(*args, **kwargs):
            if state["down"]:
                raise EmailSendError("down")
            await send_email(*args, **kwargs)

        monkeypatch.setattr(service, "send_email", flaky)
        for _ in range(3):
            response = client.post("/api/account/consent/resend")
            assert response.status_code == 502
            assert response.json()["detail"] == "Nie udało się wysłać wiadomości. Spróbuj za chwilę."
        state["down"] = False
        # Still 2 left today (1 used at registration, the failures used none)
        assert client.post("/api/account/consent/resend").status_code == 200
        age_tokens(db, hours=0.1)
        assert client.post("/api/account/consent/resend").status_code == 200

    def test_change_parent_email_invalidates_old_links(self, client, db):
        register_login(client)
        old_token = consent_token("mama@example.com")
        age_tokens(db, hours=0.1)
        response = client.post("/api/account/parent-email", json={"parent_email": "tata@example.com"})
        assert response.status_code == 200, response.text
        assert response.json()["account"]["pending"]["parent_email"] == "t***@example.com"
        assert messages(to="tata@example.com")
        view = client.post("/api/parent/consent/view", json={"token": old_token}).json()
        assert view["state"] == "expired"
        assert view["can_resend"] is False  # the old address cannot pull a new link

    def test_change_parent_email_keeps_the_14_day_clock(self, client, db):
        register_login(client)
        before = user_by_login(db, "kuba_m").pending_since
        age_tokens(db, hours=0.1)
        client.post("/api/account/parent-email", json={"parent_email": "tata@example.com"})
        assert user_by_login(db, "kuba_m").pending_since == before

    def test_change_parent_email_counts_against_the_same_limit(self, client, db):
        register_login(client)
        for address in ("a@example.com", "b@example.com"):
            age_tokens(db, hours=0.1)
            assert client.post("/api/account/parent-email", json={"parent_email": address}).status_code == 200
        age_tokens(db, hours=0.1)
        response = client.post("/api/account/parent-email", json={"parent_email": "c@example.com"})
        assert response.status_code == 429
        assert user_by_login(db, "kuba_m").parent.email == "b@example.com"

    def test_pending_endpoints_refuse_active_accounts(self, client, db):
        db.add(UserDB(id="a1", google_sub="a1", email="a@gmail.com", birth_year=2000))
        db.commit()
        client.cookies.set("session", signed_cookie({"user": {"user_id": "a1", "session_version": 0}}))
        assert client.post("/api/account/consent/resend").status_code == 409
        assert db.query(ParentDB).count() == 0


@pytest.mark.parametrize("next_url, expected", [("/task/2024/etap1/1", "/task/2024/etap1/1"), ("/\\evil.com", "/years"), ("//evil.com", "/years"), ("/%5Cevil.com", "/years")])
def test_google_callback_next_is_a_same_site_path(client, db, google, monkeypatch, next_url, expected):
    from fastapi.responses import RedirectResponse

    db.add(UserDB(id="g-123", google_sub="g-123", email="kid@gmail.com", birth_year=2005))
    db.commit()
    monkeypatch.setattr(main.settings, "google_client_id", "id")

    async def fake_redirect(request, uri):
        return RedirectResponse("https://accounts.google.com/")

    google.authorize_redirect = fake_redirect
    client.get("/login/google", params={"next": next_url}, follow_redirects=False)
    assert callback(client).headers["location"] == expected
