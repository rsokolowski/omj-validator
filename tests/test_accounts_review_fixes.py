"""Fixes from the branch review: quota tombstone identity, token transport,
reset-link invalidation, the per-device lockout, the parent-address change
on a failed send, and the Google registration keeping its state on errors."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute

import app.main as main
from app.accounts import service
from app.db.models import EmailTokenDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.repositories import DeletedAccountQuotaRepository
from app.email import EmailSendError

from accounts_support import *  # noqa: F401,F403 - fixtures
from accounts_support import (
    PASSWORD,
    age_tokens,
    consent_token,
    make_client,
    me,
    messages,
    register_login,
    token_from,
    user_by_login,
)


def _submission(db, user_id, sid):
    db.add(SubmissionDB(id=sid, user_id=user_id, year="2024", etap="etap1", task_number=1, images=[],
                        status=SubmissionStatus.COMPLETED, score=6,
                        timestamp=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)))
    db.commit()


# --------------------------------------------------------------------- 1. tombstone identity


class TestQuotaTombstone:
    def test_new_google_account_is_keyed_by_google_sub(self, db):
        from app.rate_limits import record_erasure_quota
        from app.retention import erase_user_data

        db.add(UserDB(id="a" * 32, google_sub="g-1", email="kid@gmail.com", birth_year=2005))
        db.commit()
        _submission(db, "a" * 32, "s0000001")
        record_erasure_quota(db, "a" * 32)
        erase_user_data(db, "a" * 32)

        # Registered again with the same Google account: a new random id
        db.add(UserDB(id="b" * 32, google_sub="g-1", email="kid@gmail.com", birth_year=2005))
        db.commit()
        count, _ = DeletedAccountQuotaRepository(db).get_user_carryover("b" * 32)
        assert count == 1

    def test_old_accounts_keep_their_key(self, db):
        from app.db.repositories import hash_user_id, quota_identity

        db.add(UserDB(id="104857", google_sub="104857", email="old@gmail.com", birth_year=2005))
        db.commit()
        assert quota_identity(db, "104857") == "104857"
        assert hash_user_id(quota_identity(db, "104857")) == hash_user_id("104857")

    def test_login_accounts_are_keyed_by_the_parent_address(self, client, db):
        from app.rate_limits import record_erasure_quota
        from app.retention import erase_user_data

        register_login(client)
        first = user_by_login(db, "kuba_m")
        first_id = first.id
        _submission(db, first_id, "s0000002")
        record_erasure_quota(db, first_id)
        erase_user_data(db, first_id)

        register_login(make_client(db), login="kuba_nowy")
        again = user_by_login(db, "kuba_nowy")
        count, _ = DeletedAccountQuotaRepository(db).get_user_carryover(again.id)
        assert count == 1

    def test_parent_deleting_the_child_leaves_the_tombstone_too(self, client, other_client, db):
        register_login(client)
        user = user_by_login(db, "kuba_m")
        token = consent_token()
        manage = other_client.post("/api/parent/consent", json={"token": token, "decision": "accept"}).json()["manage_url"].split("t=")[1]
        _submission(db, user.id, "s0000003")
        other_client.post(f"/api/parent/children/{user.id}/delete", json={"token": manage})
        register_login(make_client(db), login="kuba_nowy")
        assert DeletedAccountQuotaRepository(db).get_user_carryover(user_by_login(db, "kuba_nowy").id)[0] == 1


# --------------------------------------------------------------------- 3. tokens never in API query strings


def _api_routes(routes):
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from _api_routes(route.original_router.routes)


def test_no_api_route_reads_a_token_from_the_query_string():
    offenders = [
        route.path
        for route in _api_routes(main.app.routes)
        for param in route.dependant.query_params
        if param.name in {"t", "token"}
    ]
    assert offenders == []


@pytest.mark.parametrize("path", ["/api/parent/consent?t=x", "/api/parent/children?t=x", "/api/auth/password-reset/check?t=x"])
def test_old_get_lookups_are_gone(client, path):
    assert client.get(path).status_code in (404, 405)


def test_e_mail_links_point_at_pages_not_the_api(client, db):
    register_login(client)
    for link in messages()[0]["links"]:
        assert "/api/" not in link


# --------------------------------------------------------------------- 5. reset links


def test_new_password_spends_every_other_reset_link(client, other_client, db):
    register_login(client)
    for _ in range(2):
        other_client.post("/api/auth/password-reset/request", json={"login": "kuba_m"})
    first, second = [token_from(m, "/reset-hasla/nowe") for m in messages(subject_contains="Zmiana hasła")]
    assert other_client.post("/api/auth/password-reset/confirm", json={"token": second, "password": "nowe dobre haslo"}).json() == {"ok": True}
    stale = other_client.post("/api/auth/password-reset/confirm", json={"token": first, "password": "inne dobre haslo"})
    assert stale.status_code == 410 and stale.json()["state"] == "used"

    # The parent page path spends them as well
    other_client.post("/api/auth/password-reset/request", json={"login": "kuba_m"})
    third = token_from(messages(subject_contains="Zmiana hasła")[-1], "/reset-hasla/nowe")
    user = user_by_login(db, "kuba_m")
    service.set_password(db, user, "jeszcze inne haslo")
    db.commit()
    assert other_client.post("/api/auth/password-reset/check", json={"token": third}).json()["state"] == "used"


# --------------------------------------------------------------------- 6. lockout


def _login(c, password=PASSWORD, ip=None):
    headers = {"cf-connecting-ip": ip} if ip else {}
    return c.post("/api/auth/login", json={"login": "kuba_m", "password": password}, headers=headers)


class TestLockout:
    @pytest.fixture
    def account(self, client, db):
        register_login(client)
        client.cookies.clear()

    def test_attacker_elsewhere_cannot_lock_the_child_out(self, db, account):
        child = make_client(db)
        assert _login(child, ip="10.0.0.1").status_code == 200  # the child's device, remembered
        attacker = make_client(db)
        for i in range(40):
            _login(attacker, password="zgaduje haslo", ip=f"10.9.{i}.1")
        # The attacker is throttled ...
        assert _login(attacker, password="zgaduje haslo", ip="10.9.99.1").status_code == 429
        # ... the child on their own device is not
        assert _login(child, ip="10.0.0.1").status_code == 200

    def test_same_ip_lockout_after_five(self, db, account):
        attacker = make_client(db)
        for _ in range(5):
            assert _login(attacker, password="zgaduje haslo", ip="10.1.1.1").status_code == 401
        assert _login(attacker, ip="10.1.1.1").status_code == 429
        # A different IP is still fine (below the global throttle)
        assert _login(make_client(db), ip="10.1.1.2").status_code == 200

    def test_device_cookie_holds_no_login(self, db, account):
        child = make_client(db)
        response = _login(child, ip="10.0.0.1")
        cookie = response.cookies.get(service.DEVICE_COOKIE)
        assert cookie and "kuba" not in cookie
        assert "httponly" in response.headers["set-cookie"].lower()

    def test_messages_stay_generic(self, db, account):
        attacker = make_client(db)
        wrong = _login(attacker, password="zgaduje haslo", ip="10.2.2.2")
        assert wrong.json()["detail"] == "Nieprawidłowy login lub hasło."


# --------------------------------------------------------------------- 7. parent address change


def test_failed_send_leaves_the_old_parent_and_links(client, db, monkeypatch):
    register_login(client)
    old_token = consent_token("mama@example.com")
    before = user_by_login(db, "kuba_m").parent_id
    age_tokens(db, hours=0.1)

    async def broken(*args, **kwargs):
        raise EmailSendError("down")

    monkeypatch.setattr(service, "send_email", broken)
    response = client.post("/api/account/parent-email", json={"parent_email": "tata@example.com"})
    assert response.status_code == 502
    assert user_by_login(db, "kuba_m").parent_id == before
    assert me(client)["account"]["pending"]["parent_email"] == "m***@example.com"
    view = client.post("/api/parent/consent/view", json={"token": old_token}).json()
    assert view["state"] == "valid"
    from app.db.models import ParentDB

    assert db.query(ParentDB).filter(ParentDB.email == "tata@example.com").count() == 0


# --------------------------------------------------------------------- 8. Google registration state


class FakeGoogle:
    async def authorize_access_token(self, request):
        return {"userinfo": {"sub": "g-77", "email": "kid@gmail.com", "email_verified": True, "name": "Kid"}}


@pytest.fixture
def google(monkeypatch):
    monkeypatch.setattr(main, "oauth", SimpleNamespace(google=FakeGoogle()))

    async def member(email):
        return True

    monkeypatch.setattr(main, "check_group_membership", member)


def test_new_user_limit_keeps_the_waiting_identity(client, db, google, monkeypatch):
    from app.config import settings

    client.get("/auth/callback", follow_redirects=False)
    monkeypatch.setattr(settings, "rate_limit_new_users_per_day", 0)
    body = {"birth_year": 2005, "accept_terms": True}
    assert client.post("/api/auth/register/google", json=body).status_code == 429
    # Still waiting - the child can retry without going back to Google
    assert client.get("/api/auth/register/state").json() == {"google": {"email": "kid@gmail.com"}}
    monkeypatch.setattr(settings, "rate_limit_new_users_per_day", 50)
    assert client.post("/api/auth/register/google", json=body).json()["action"] == "done"
    assert client.get("/api/auth/register/state").json() == {"google": None}


def test_callback_429_keeps_answers_and_identity(client, db, google, monkeypatch):
    from app.config import settings

    client.post("/api/auth/register/google", json={"birth_year": 2005, "accept_terms": True})
    monkeypatch.setattr(settings, "rate_limit_new_users_per_day", 0)
    response = client.get("/auth/callback", follow_redirects=False)
    assert response.headers["location"] == "/login?error=rate_limit_new_users"
    assert db.query(UserDB).count() == 0
    assert client.get("/api/auth/register/state").json() == {"google": {"email": "kid@gmail.com"}}
