"""Login + password, the lockout, session lifetimes, legacy sessions and the
dev outbox."""

import time

import pytest

from app import auth
from app.config import settings
from app.db.models import LoginFailureDB, UserDB

from accounts_support import *  # noqa: F401,F403 - fixtures
from accounts_support import PASSWORD, make_client, me, register_login, signed_cookie, user_by_login


@pytest.fixture
def account(client, db):
    register_login(client)
    client.cookies.clear()
    return user_by_login(db, "kuba_m")


def login(client, password=PASSWORD, name="kuba_m", **extra):
    return client.post("/api/auth/login", json={"login": name, "password": password, **extra})


class TestLogin:
    def test_success_logs_in_and_points_to_pending_screen(self, client, account):
        response = login(client, name="  KUBA_M ")
        assert response.status_code == 200
        assert response.json() == {"redirect": "/konto/oczekuje"}
        assert me(client)["user"]["login"] == "kuba_m"

    def test_active_account_honours_safe_next(self, client, db, account):
        account.status = "active"
        account.pending_since = None
        db.commit()
        assert login(client, next="/task/2024/etap1/1").json() == {"redirect": "/task/2024/etap1/1"}
        assert login(client, next="//evil.example").json() == {"redirect": "/years"}

    def test_wrong_password_and_unknown_login_look_the_same(self, client, account):
        wrong = login(client, password="zle haslo zle")
        unknown = login(client, name="nie_ma_takiego")
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json() == {
            "detail": "Nieprawidłowy login lub hasło.",
            "code": "invalid_credentials",
        }
        assert me(client)["is_authenticated"] is False

    def test_lockout_after_five_failures_per_login(self, client, account):
        for _ in range(5):
            assert login(client, password="zle haslo zle").status_code == 401
        locked = login(client)  # even the right password
        assert locked.status_code == 429
        assert locked.json()["code"] == "login_locked"

    def test_lockout_message_same_for_unknown_login(self, client, account):
        for _ in range(5):
            login(client, name="nie_ma_takiego", password="cokolwiek tam")
        unknown = login(client, name="nie_ma_takiego", password="cokolwiek tam")
        for _ in range(5):
            login(client, password="zle haslo zle")
        known = login(client, password="zle haslo zle")
        assert unknown.status_code == known.status_code == 429
        assert unknown.json() == known.json()

    def test_lockout_per_ip(self, client, db, account):
        for i in range(20):
            login(client, name=f"zgadywany{i}", password="cokolwiek tam")
        assert login(client).status_code == 429
        assert db.query(LoginFailureDB).filter(LoginFailureDB.login == "kuba_m").count() == 0

    def test_failures_are_stored_without_the_ip(self, client, db, account):
        login(client, password="zle haslo zle")
        row = db.query(LoginFailureDB).one()
        assert row.login == "kuba_m"
        assert row.ip_hash != "testclient" and len(row.ip_hash) == 64

    def test_lockout_expires(self, client, db, account):
        from datetime import timedelta

        for _ in range(5):
            login(client, password="zle haslo zle")
        for row in db.query(LoginFailureDB).all():
            row.at -= timedelta(minutes=16)
        db.commit()
        assert login(client).status_code == 200


class TestSessionLifetime:
    def test_without_remember_me_the_session_ends_after_12_hours(self, client, account, monkeypatch):
        login(client)
        assert me(client)["is_authenticated"] is True
        real_time = time.time
        monkeypatch.setattr(auth.time, "time", lambda: real_time() + 12 * 3600 + 5)
        assert me(client)["is_authenticated"] is False

    def test_with_remember_me_it_lasts_30_days(self, client, account, monkeypatch):
        login(client, remember=True)
        real_time = time.time
        monkeypatch.setattr(auth.time, "time", lambda: real_time() + 29 * 24 * 3600)
        assert me(client)["is_authenticated"] is True


class TestLegacySession:
    def test_google_sub_session_keeps_working_and_is_rewritten(self, client, db):
        db.add(UserDB(id="111", google_sub="111", email="old@gmail.com", birth_year=2000))
        db.commit()
        client.cookies.set("session", signed_cookie({"user": {"google_sub": "111", "email": "old@gmail.com", "is_group_member": True}}))
        response = client.get("/api/auth/me")
        body = response.json()
        assert body["is_authenticated"] is True
        assert body["user"]["id"] == "111"
        assert body["user"]["is_group_member"] is True
        # Rewritten: the new cookie carries user_id
        assert "session=" in response.headers.get("set-cookie", "")

    def test_session_of_a_deleted_user_is_dropped(self, client, db):
        client.cookies.set("session", signed_cookie({"user": {"user_id": "gone", "session_version": 0}}))
        assert me(client)["is_authenticated"] is False


class TestOutbox:
    def test_404_unless_console_and_e2e(self, client, monkeypatch):
        monkeypatch.setattr(settings, "e2e_mode", False)
        assert client.get("/api/dev/outbox").status_code == 404

        monkeypatch.setattr(settings, "e2e_mode", True)
        monkeypatch.setattr(settings, "email_backend", "resend")
        assert client.get("/api/dev/outbox").status_code == 404

        monkeypatch.setattr(settings, "email_backend", "console")
        monkeypatch.setattr(settings, "auth_disabled", True)
        assert client.get("/api/dev/outbox").status_code == 404

        monkeypatch.setattr(settings, "auth_disabled", False)
        assert client.get("/api/dev/outbox").status_code == 200

    def test_lists_messages(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "e2e_mode", True)
        register_login(client)
        (message,) = client.get("/api/dev/outbox").json()["messages"]
        assert message["to"] == "mama@example.com"
        assert any("/rodzic/zgoda?t=" in link for link in message["links"])


class TestResendBackend:
    @pytest.mark.asyncio
    async def test_posts_to_resend_with_from_and_reply_to(self, monkeypatch):
        import httpx

        from app import email as email_module

        captured = {}

        def handler(request: httpx.Request):
            captured["auth"] = request.headers["authorization"]
            captured["json"] = __import__("json").loads(request.content)
            return httpx.Response(200, json={"id": "abc"})

        transport = httpx.MockTransport(handler)
        real_client = httpx.AsyncClient
        monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw))
        monkeypatch.setattr(settings, "email_backend", "resend")
        monkeypatch.setattr(settings, "resend_api_key", "re_test")
        await email_module.send_email("mama@example.com", "Temat", "<p>x</p>", "x")
        assert captured["auth"] == "Bearer re_test"
        assert captured["json"]["from"] == "OMJ Validator <noreply@omj-validator.pl>"
        assert captured["json"]["reply_to"] == "kontakt@omj-validator.pl"
        assert captured["json"]["text"] == "x"

    @pytest.mark.asyncio
    async def test_failure_raises(self, monkeypatch):
        import httpx

        from app import email as email_module

        transport = httpx.MockTransport(lambda request: httpx.Response(500))
        real_client = httpx.AsyncClient
        monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw))
        monkeypatch.setattr(settings, "email_backend", "resend")
        monkeypatch.setattr(settings, "resend_api_key", "re_test")
        with pytest.raises(email_module.EmailSendError):
            await email_module.send_email("mama@example.com", "Temat", "<p>x</p>", "x")
