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

    def test_login_accounts_are_keyed_by_their_own_id(self, client, db):
        from app.db.repositories import quota_identity

        register_login(client)
        user = user_by_login(db, "kuba_m")
        assert quota_identity(db, user.id) == user.id

    def test_parent_deleting_a_google_child_leaves_the_tombstone(self, other_client, db, monkeypatch):
        """Parent-page erasure records the tombstone too: the same Google
        account registering again carries the used quota."""
        from app.accounts import service as svc

        db.add(UserDB(id="c" * 32, google_sub="g-9", email="kid9@gmail.com", birth_year=2012))
        db.commit()
        child = db.get(UserDB, "c" * 32)
        parent = svc.ensure_parent(db, "mama@example.com")
        child = db.get(UserDB, "c" * 32)
        svc.set_pending(child, parent)
        db.commit()
        raw, row = svc._new_token("parent_manage", parent.id, None, svc.MANAGE_TOKEN_TTL)
        db.add(row)
        db.commit()
        _submission(db, "c" * 32, "s0000003")
        assert other_client.post(f"/api/parent/children/{'c' * 32}/delete", json={"token": raw}).json()["deleted"]
        db.add(UserDB(id="d" * 32, google_sub="g-9", email="kid9@gmail.com", birth_year=2012))
        db.commit()
        assert DeletedAccountQuotaRepository(db).get_user_carryover("d" * 32)[0] == 1

    def test_key_is_computed_once_per_repository(self, db):
        from sqlalchemy import event

        db.add(UserDB(id="e" * 32, google_sub="g-e", email="e@gmail.com", birth_year=2005))
        db.commit()
        db.expire_all()
        repo = DeletedAccountQuotaRepository(db)
        statements = []
        listener = lambda *args: statements.append(args[2])  # noqa: E731
        event.listen(db.get_bind(), "before_cursor_execute", listener)
        try:
            repo.get_user_carryover("e" * 32)
            first = len(statements)
            repo.get_user_carryover("e" * 32)
            repo.get_user_ai_usage_carryover("e" * 32)
        finally:
            event.remove(db.get_bind(), "before_cursor_execute", listener)
        user_lookups = [sql for sql in statements if "FROM users" in sql]
        assert len(user_lookups) == 1, user_lookups
        assert first >= 1


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


def _login(c, password=PASSWORD, ip="10.0.0.1"):
    return c.post(
        "/api/auth/login",
        json={"login": "kuba_m", "password": password},
        headers={"cf-connecting-ip": ip},
    )


class TestLockout:
    @pytest.fixture
    def account(self, client, db):
        register_login(client)
        client.cookies.clear()

    def test_attacker_elsewhere_cannot_lock_the_child_out(self, db, account):
        child = make_client(db)
        assert _login(child, ip="10.0.0.1").status_code == 200  # the child's device, now known
        attacker = make_client(db)
        for i in range(12):
            _login(attacker, password="zgaduje haslo", ip=f"10.9.{i}.1")
        # Unknown devices hit the per-login cap of 10 ...
        assert _login(make_client(db), ip="10.9.99.1").status_code == 429
        # ... the child's own device does not
        assert _login(child, ip="10.0.0.1").status_code == 200

    def test_shared_computer_device_a_does_not_lock_device_b(self, db, account):
        """Two devices that both signed in before: failures on one stay there."""
        device_a, device_b = make_client(db), make_client(db)
        assert _login(device_a, ip="10.5.5.5").status_code == 200
        assert _login(device_b, ip="10.5.5.5").status_code == 200  # same school network
        for _ in range(5):
            assert _login(device_a, password="zle haslo zle", ip="10.5.5.5").status_code == 401
        assert _login(device_a, ip="10.5.5.5").status_code == 429
        assert _login(device_b, ip="10.5.5.5").status_code == 200

    def test_password_change_voids_the_device_tag(self, db, account):
        device = make_client(db)
        assert _login(device).status_code == 200
        user = user_by_login(db, "kuba_m")
        service.set_password(db, user, "nowe dobre haslo")
        db.commit()
        # Old tag no longer matches: this device now counts as unknown
        for _ in range(5):
            assert _login(device, password="zle haslo zle", ip="10.3.3.3").status_code == 401
        assert _login(device, password="nowe dobre haslo", ip="10.3.3.3").status_code == 429
        # From a fresh device on another network the new password works
        assert _login(make_client(db), password="nowe dobre haslo", ip="10.4.4.4").status_code == 200

    def test_unknown_device_caps(self, db, account):
        attacker = make_client(db)
        for _ in range(5):
            assert _login(attacker, password="zgaduje haslo", ip="10.1.1.1").status_code == 401
        assert _login(attacker, ip="10.1.1.1").status_code == 429  # per (login, IP)
        assert _login(make_client(db), ip="10.1.1.2").status_code == 200  # other IP, below 10

        # 20 per IP, across logins
        guesser = make_client(db)
        for i in range(20):
            guesser.post("/api/auth/login", json={"login": f"inny{i}", "password": "cokolwiek tam"},
                         headers={"cf-connecting-ip": "10.7.7.7"})
        assert _login(guesser, ip="10.7.7.7").status_code == 429

    def test_success_clears_only_its_own_failures(self, db, account):
        from app.db.models import LoginFailureDB

        attacker = make_client(db)
        for _ in range(3):
            _login(attacker, password="zgaduje haslo", ip="10.8.8.8")
        assert _login(make_client(db), ip="10.0.0.9").status_code == 200
        assert db.query(LoginFailureDB).count() == 3

    def test_forged_or_foreign_cookie_is_ignored(self, db, account):
        device = make_client(db)
        _login(device)
        device.cookies.set(service.DEVICE_COOKIE, device.cookies.get(service.DEVICE_COOKIE) + "x")
        for _ in range(5):
            _login(device, password="zle haslo zle", ip="10.6.6.6")
        assert _login(device, ip="10.6.6.6").status_code == 429  # counted as unknown

    def test_device_cookie_is_signed_random_and_holds_no_login(self, db, account):
        response = _login(make_client(db))
        cookie = response.cookies.get(service.DEVICE_COOKIE)
        assert cookie and "kuba" not in cookie
        device = service.read_device(cookie)
        assert device.device_id and len(device.tags) == 1
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
    # At most a childless parent row is left, which retention removes
    from app.db.models import ParentDB
    from app.retention import delete_childless_parents

    assert delete_childless_parents(db).parents_deleted == 1
    assert db.query(ParentDB).filter(ParentDB.email == "tata@example.com").count() == 0


# --------------------------------------------------------------------- 1. no transaction across a send


@pytest.fixture
def send_watch(db, monkeypatch):
    """A send_email that records whether the session held a transaction."""
    from app.email import send_email as real_send

    seen = []

    async def watching(*args, **kwargs):
        seen.append({"in_transaction": db.in_transaction(), "pending": bool(db.new or db.dirty or db.deleted)})
        await real_send(*args, **kwargs)

    monkeypatch.setattr(service, "send_email", watching)
    return seen


def test_no_transaction_is_open_while_any_e_mail_is_sent(client, other_client, db, send_watch):
    register_login(client)                                             # consent (registration)
    age_tokens(db, hours=0.1)
    client.post("/api/account/consent/resend")                        # consent (resend)
    age_tokens(db, hours=0.1)
    client.post("/api/account/parent-email", json={"parent_email": "tata@example.com"})  # change
    token = consent_token("tata@example.com")
    other_client.post("/api/parent/consent", json={"token": token, "decision": "accept"})  # active
    other_client.post("/api/parent/request-link", json={"email": "tata@example.com"})     # manage
    other_client.post("/api/auth/password-reset/request", json={"login": "kuba_m"})       # reset
    assert len(send_watch) == 6, send_watch
    assert all(not call["in_transaction"] and not call["pending"] for call in send_watch), send_watch


def test_parent_row_is_committed_before_the_send(client, db, monkeypatch):
    """Concurrent requests for the same address must not wait on an
    uncommitted INSERT: the row is visible from another connection."""
    from sqlalchemy.orm import sessionmaker

    from app.db.models import ParentDB
    from app.email import send_email as real_send

    register_login(client)
    age_tokens(db, hours=0.1)
    other_session = sessionmaker(bind=db.get_bind())()
    seen = []

    async def watching(*args, **kwargs):
        seen.append(other_session.query(ParentDB).filter(ParentDB.email == "tata@example.com").count())
        await real_send(*args, **kwargs)

    monkeypatch.setattr(service, "send_email", watching)
    client.post("/api/account/parent-email", json={"parent_email": "tata@example.com"})
    other_session.close()
    assert seen == [1]


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


def test_waiting_identity_is_consumed_even_on_429(client, db, google, monkeypatch):
    """A shared computer must not hand a Google identity to the next child."""
    from app.config import settings

    client.get("/auth/callback", follow_redirects=False)
    assert client.get("/api/auth/register/state").json() == {"google": {"email": "kid@gmail.com"}}
    monkeypatch.setattr(settings, "rate_limit_new_users_per_day", 0)
    body = {"birth_year": 2005, "accept_terms": True}
    assert client.post("/api/auth/register/google", json=body).status_code == 429
    assert client.get("/api/auth/register/state").json() == {"google": None}


def test_callback_429_consumes_answers(client, db, google, monkeypatch):
    from app.config import settings

    client.post("/api/auth/register/google", json={"birth_year": 2005, "accept_terms": True})
    monkeypatch.setattr(settings, "rate_limit_new_users_per_day", 0)
    response = client.get("/auth/callback", follow_redirects=False)
    assert response.headers["location"] == "/login?error=rate_limit_new_users"
    assert db.query(UserDB).count() == 0
    assert client.get("/api/auth/register/state").json() == {"google": None}
    # The next Google sign-in starts clean: nothing is created from stale answers
    monkeypatch.setattr(settings, "rate_limit_new_users_per_day", 50)
    assert client.get("/auth/callback", follow_redirects=False).headers["location"] == "/rejestracja?google=1"
    assert db.query(UserDB).count() == 0


def test_waiting_identity_holds_only_sub_and_email_for_10_minutes(client, db, google, monkeypatch):
    import time as time_module

    from app.auth import SESSION_PENDING_GOOGLE_KEY

    client.get("/auth/callback", follow_redirects=False)
    stored = {}

    @main.app.get("/__test/pending")
    async def peek(request: __import__("fastapi").Request):  # pragma: no cover - test helper route
        stored.update(request.session.get(SESSION_PENDING_GOOGLE_KEY) or {})
        return {}

    try:
        client.get("/__test/pending")
    finally:
        main.app.router.routes.pop()
    assert set(stored) == {"sub", "email", "at"}
    real_time = time_module.time
    monkeypatch.setattr(time_module, "time", lambda: real_time() + 11 * 60)
    assert client.get("/api/auth/register/state").json() == {"google": None}


# --------------------------------------------------------------------- concurrent sends


def test_concurrent_sends_cannot_overrun_the_send_limit(client, db, monkeypatch):
    """The limit is checked before the send and logged after it; parallel
    requests must not all pass the check before the first one is logged."""
    import asyncio

    register_login(client)  # the consent e-mail already carries one manage link
    parent = user_by_login(db, "kuba_m").parent
    sent = []

    async def slow_send(to, subject, html, text):
        await asyncio.sleep(0.01)
        sent.append(to)

    monkeypatch.setattr(service, "send_email", slow_send)

    async def attempt():
        try:
            await service.send_manage_link(db, parent)
            return "sent"
        except service.EmailLimitError:
            return "limited"

    async def burst():
        return await asyncio.gather(*(attempt() for _ in range(5)))

    results = asyncio.run(burst())
    assert results.count("sent") == service.MANAGE_PER_PARENT_PER_DAY - 1
    assert len(sent) == service.MANAGE_PER_PARENT_PER_DAY - 1
