"""The parent's side: consent page, decline, the parent page (children,
deletion, new password) and the "send me a link" form."""

from datetime import timedelta

import pytest

from app.db.models import ConsentDB, EmailTokenDB, ParentDB, SubmissionDB, SubmissionStatus, UserDB
from app.config import settings

from accounts_support import *  # noqa: F401,F403 - fixtures
from accounts_support import (
    PASSWORD,
    age_tokens,
    consent_token,
    make_client,
    manage_token,
    me,
    messages,
    naive_now,
    register_login,
    user_by_login,
)


@pytest.fixture
def pending(client, db):
    register_login(client)
    return consent_token()


class TestConsentPage:
    def test_view_shows_the_account_and_changes_nothing(self, other_client, db, pending):
        for _ in range(3):  # a mail scanner opening the link, a preview, the parent
            view = other_client.get("/api/parent/consent", params={"t": pending}).json()
        assert view["state"] == "valid"
        assert view["child"]["identifier"] == "kuba_m"
        assert view["child"]["kind"] == "login"
        assert view["summary"]["submission_retention"] == "24 miesiące"
        user = user_by_login(db, "kuba_m")
        assert user.status == "pending_parent"
        assert db.query(EmailTokenDB).filter(EmailTokenDB.used_at.isnot(None)).count() == 0

    def test_accept_activates_and_records_consent(self, client, other_client, db, pending):
        response = other_client.post("/api/parent/consent", json={"token": pending, "decision": "accept"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["result"] == "accepted"
        assert body["manage_url"].startswith("/rodzic?t=")

        user = user_by_login(db, "kuba_m")
        assert user.status == "active" and user.pending_since is None
        consent = db.query(ConsentDB).one()
        assert consent.kind == "parent" and consent.parent_id == user.parent_id
        assert consent.terms_version == settings.terms_version

        active_mail = messages(subject_contains="jest aktywne")
        assert len(active_mail) == 1 and active_mail[0]["to"] == "mama@example.com"

        # The child's pending screen sees the flip on its next poll
        assert me(client)["account"]["status"] == "active"
        # The parent's browser is not logged in as anybody
        assert me(other_client)["is_authenticated"] is False

    def test_token_is_single_use(self, other_client, db, pending):
        other_client.post("/api/parent/consent", json={"token": pending, "decision": "accept"})
        again = other_client.post("/api/parent/consent", json={"token": pending, "decision": "decline"})
        assert again.status_code == 410
        assert again.json()["state"] == "used"
        assert user_by_login(db, "kuba_m").status == "active"
        assert other_client.get("/api/parent/consent", params={"t": pending}).json()["state"] == "used"

    def test_decline_erases_the_account_and_the_parent(self, client, other_client, db, pending):
        response = other_client.post("/api/parent/consent", json={"token": pending, "decision": "decline"})
        assert response.json() == {"result": "declined"}
        assert db.query(UserDB).count() == 0
        assert db.query(ParentDB).count() == 0
        assert db.query(EmailTokenDB).count() == 0
        # The child's session dies with the account
        assert me(client)["is_authenticated"] is False

    def test_decline_keeps_a_sibling_and_the_parent(self, client, other_client, db, pending):
        sibling = make_client(db)
        register_login(sibling, login="ola_k")
        other_client.post("/api/parent/consent", json={"token": pending, "decision": "decline"})
        assert [u.login for u in db.query(UserDB).all()] == ["ola_k"]
        assert db.query(ParentDB).count() == 1

    def test_expired_token_offers_a_new_link(self, other_client, db, pending):
        for token in db.query(EmailTokenDB).all():
            token.expires_at = naive_now() - timedelta(minutes=1)
        age_tokens(db, hours=0.1)
        view = other_client.get("/api/parent/consent", params={"t": pending}).json()
        assert view["state"] == "expired" and view["can_resend"] is True
        refused = other_client.post("/api/parent/consent", json={"token": pending, "decision": "accept"})
        assert refused.status_code == 410

        resent = other_client.post("/api/parent/consent/resend", json={"token": pending})
        assert resent.status_code == 200
        fresh = consent_token()
        assert fresh != pending
        assert other_client.post("/api/parent/consent", json={"token": fresh, "decision": "accept"}).status_code == 200

    def test_unknown_token(self, other_client, db):
        view = other_client.get("/api/parent/consent", params={"t": "nonsense"}).json()
        assert view == {"state": "invalid", "child": None, "can_resend": False, "summary": view["summary"]}
        assert other_client.post("/api/parent/consent", json={"token": "x", "decision": "accept"}).status_code == 410

    def test_decision_must_be_explicit(self, other_client, db, pending):
        assert other_client.post("/api/parent/consent", json={"token": pending}).status_code == 400


def _activate(other_client, token):
    response = other_client.post("/api/parent/consent", json={"token": token, "decision": "accept"})
    return response.json()["manage_url"].split("t=", 1)[1]


class TestParentPage:
    def test_lists_all_children_of_the_address(self, client, other_client, db, pending):
        sibling = make_client(db)
        register_login(sibling, login="ola_k")
        manage = _activate(other_client, pending)
        data = other_client.get("/api/parent/children", params={"t": manage}).json()
        assert data["parent_email"] == "m***@example.com"
        assert [(c["identifier"], c["status"]) for c in data["children"]] == [
            ("kuba_m", "active"),
            ("ola_k", "pending_parent"),
        ]
        assert data["children"][1]["pending_deadline"]

    def test_manage_link_from_any_email_works(self, other_client, db, pending):
        manage = manage_token()  # the one inside the consent request
        assert other_client.get("/api/parent/children", params={"t": manage}).status_code == 200

    def test_delete_child_erases_everything(self, client, other_client, db, pending, tmp_path):
        manage = _activate(other_client, pending)
        user = user_by_login(db, "kuba_m")
        upload = settings.uploads_dir / user.id / "2024" / "etap1" / "1"
        upload.mkdir(parents=True)
        (upload / "a.jpg").write_bytes(b"x")
        db.add(SubmissionDB(id="s1", user_id=user.id, year="2024", etap="etap1", task_number=1,
                            images=[f"{user.id}/2024/etap1/1/a.jpg"], status=SubmissionStatus.COMPLETED))
        db.commit()

        response = other_client.post(f"/api/parent/children/{user.id}/delete", json={"token": manage})
        assert response.json()["deleted"] is True and response.json()["remaining"] == 0
        assert db.query(UserDB).count() == 0
        assert db.query(SubmissionDB).count() == 0
        assert db.query(ConsentDB).count() == 0
        assert db.query(ParentDB).count() == 0  # last child gone, parent row gone
        assert not (settings.uploads_dir / user.id).exists()
        assert me(client)["is_authenticated"] is False
        # The link has nothing left to show
        assert other_client.get("/api/parent/children", params={"t": manage}).status_code == 404

    def test_cannot_touch_someone_elses_child(self, other_client, db, pending):
        manage = _activate(other_client, pending)
        stranger = make_client(db)
        register_login(stranger, login="obcy", parent_email="inny@example.com")
        target = user_by_login(db, "obcy")
        assert other_client.post(f"/api/parent/children/{target.id}/delete", json={"token": manage}).status_code == 404
        assert other_client.post(
            f"/api/parent/children/{target.id}/password", json={"token": manage, "password": "nowe dobre haslo"}
        ).status_code == 404
        assert db.get(UserDB, target.id) is not None

    def test_set_password_ends_the_childs_sessions(self, client, other_client, db, pending):
        manage = _activate(other_client, pending)
        user = user_by_login(db, "kuba_m")
        assert me(client)["is_authenticated"] is True

        weak = other_client.post(f"/api/parent/children/{user.id}/password", json={"token": manage, "password": "12345678"})
        assert weak.status_code == 400

        ok = other_client.post(
            f"/api/parent/children/{user.id}/password", json={"token": manage, "password": "nowe dobre haslo"}
        )
        assert ok.json() == {"ok": True}
        assert me(client)["is_authenticated"] is False  # session_version bumped
        fresh = make_client(db)
        login = fresh.post("/api/auth/login", json={"login": "kuba_m", "password": "nowe dobre haslo"})
        assert login.status_code == 200

    def test_expired_manage_link(self, other_client, db, pending):
        manage = _activate(other_client, pending)
        for token in db.query(EmailTokenDB).all():
            token.expires_at = naive_now() - timedelta(seconds=1)
        db.commit()
        response = other_client.get("/api/parent/children", params={"t": manage})
        assert response.status_code == 410 and response.json()["state"] == "expired"


class TestRequestLink:
    def test_known_address_gets_a_link(self, other_client, db, pending):
        before = len(messages(to="mama@example.com"))
        response = other_client.post("/api/parent/request-link", json={"email": " Mama@Example.com"})
        assert response.json() == {"sent": True}
        assert len(messages(to="mama@example.com")) == before + 1
        assert messages(to="mama@example.com")[-1]["subject"].startswith("Link do strony rodzica")

    def test_unknown_address_gets_the_same_answer_and_no_mail(self, other_client, db):
        response = other_client.post("/api/parent/request-link", json={"email": "nikt@example.com"})
        assert response.json() == {"sent": True}
        assert messages() == []

    def test_three_links_per_address_per_day(self, other_client, db, pending):
        # The consent request already carried one manage link
        for _ in range(4):
            other_client.post("/api/parent/request-link", json={"email": "mama@example.com"})
        assert len(messages(subject_contains="Link do strony rodzica")) == 2


class TestPasswordReset:
    def test_reset_goes_to_the_parent_and_never_logs_in(self, client, other_client, db, pending):
        response = other_client.post("/api/auth/password-reset/request", json={"login": "KUBA_M"})
        assert response.json() == {"sent": True}
        (mail,) = messages(subject_contains="Zmiana hasła")
        assert mail["to"] == "mama@example.com"
        assert mail["subject"] == "Zmiana hasła — konto kuba_m"
        from accounts_support import token_from

        token = token_from(mail, "/reset-hasla/nowe")
        assert other_client.get("/api/auth/password-reset/check", params={"t": token}).json() == {
            "state": "valid", "login": "kuba_m"
        }
        done = other_client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "nowe dobre haslo"})
        assert done.json() == {"ok": True}
        assert me(other_client)["is_authenticated"] is False
        assert me(client)["is_authenticated"] is False  # old session rejected
        again = other_client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "inne dobre haslo"})
        assert again.status_code == 410 and again.json()["state"] == "used"

    def test_unknown_login_same_answer(self, other_client, db):
        assert other_client.post("/api/auth/password-reset/request", json={"login": "nikt"}).json() == {"sent": True}
        assert messages() == []

    def test_reset_link_expires_after_an_hour(self, other_client, db, pending):
        other_client.post("/api/auth/password-reset/request", json={"login": "kuba_m"})
        from accounts_support import token_from

        token = token_from(messages(subject_contains="Zmiana hasła")[0], "/reset-hasla/nowe")
        row = db.query(EmailTokenDB).filter(EmailTokenDB.purpose == "password_reset").one()
        assert row.expires_at - row.created_at == timedelta(hours=1)
        row.expires_at = naive_now() - timedelta(seconds=1)
        db.commit()
        response = other_client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "nowe dobre haslo"})
        assert response.status_code == 410 and response.json()["state"] == "expired"

    def test_three_resets_per_account_per_day(self, other_client, db, pending):
        for _ in range(5):
            other_client.post("/api/auth/password-reset/request", json={"login": "kuba_m"})
        assert len(messages(subject_contains="Zmiana hasła")) == 3

    def test_new_password_follows_the_rules(self, other_client, db, pending):
        other_client.post("/api/auth/password-reset/request", json={"login": "kuba_m"})
        from accounts_support import token_from

        token = token_from(messages(subject_contains="Zmiana hasła")[0], "/reset-hasla/nowe")
        response = other_client.post("/api/auth/password-reset/confirm", json={"token": token, "password": "kuba_m"})
        assert response.status_code == 400 and response.json()["field"] == "password"
        # The token is still good for a valid attempt
        assert other_client.post("/api/auth/password-reset/confirm", json={"token": token, "password": PASSWORD}).status_code == 200
