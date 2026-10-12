"""Retention passes added with parent consent: unconfirmed accounts after 14
days, expired e-mail links, login failures and childless parent rows."""

from datetime import timedelta

import pytest

from app.config import settings
from app.db.models import EmailTokenDB, LoginFailureDB, ParentDB, UserDB
from app.retention import (
    delete_childless_parents,
    delete_unconfirmed_accounts,
    purge_expired_email_tokens,
    purge_login_failures,
    run_retention,
)

from accounts_support import *  # noqa: F401,F403 - fixtures
from accounts_support import age_tokens, consent_token, make_client, naive_now, register_login, user_by_login


@pytest.fixture
def pending_user(client, db):
    register_login(client)
    return user_by_login(db, "kuba_m")


def test_pending_account_erased_after_14_days(client, db, pending_user):
    upload = settings.uploads_dir / pending_user.id
    upload.mkdir(parents=True)
    (upload / "x.jpg").write_bytes(b"x")

    pending_user.pending_since = naive_now() - timedelta(days=13, hours=23)
    db.commit()
    assert delete_unconfirmed_accounts(db).unconfirmed_accounts_deleted == 0

    pending_user.pending_since = naive_now() - timedelta(days=14, minutes=1)
    db.commit()
    dry = delete_unconfirmed_accounts(db, dry_run=True)
    assert dry.unconfirmed_accounts_deleted == 1
    assert db.query(UserDB).count() == 1

    report = delete_unconfirmed_accounts(db)
    assert report.unconfirmed_accounts_deleted == 1
    assert db.query(UserDB).count() == 0
    # The address was mailed today: it stays for the send log, then goes
    assert db.query(ParentDB).count() == 1
    age_tokens(db, hours=25)
    assert delete_childless_parents(db).parents_deleted == 1
    assert not upload.exists()


def test_active_accounts_are_not_touched(client, db, pending_user):
    pending_user.status = "active"
    pending_user.pending_since = naive_now() - timedelta(days=30)
    db.commit()
    assert delete_unconfirmed_accounts(db).unconfirmed_accounts_deleted == 0


def test_email_tokens_kept_30_days_after_expiry(client, db, pending_user):
    tokens = db.query(EmailTokenDB).all()
    tokens[0].expires_at = naive_now() - timedelta(days=31)
    tokens[1].expires_at = naive_now() - timedelta(days=29)
    db.commit()
    assert purge_expired_email_tokens(db).email_tokens_purged == 1
    assert db.query(EmailTokenDB).count() == 1


def test_login_failures_kept_24_hours(db):
    db.add(LoginFailureDB(login="a", ip_hash="h", at=naive_now() - timedelta(hours=25)))
    db.add(LoginFailureDB(login="b", ip_hash="h", at=naive_now() - timedelta(hours=23)))
    db.commit()
    assert purge_login_failures(db).login_failures_purged == 1
    assert [row.login for row in db.query(LoginFailureDB).all()] == ["b"]


def test_parent_left_by_an_address_change_goes_after_24_hours(client, db, pending_user):
    age_tokens(db, hours=0.1)
    client.post("/api/account/parent-email", json={"parent_email": "tata@example.com"})
    assert db.query(ParentDB).count() == 2

    # Its e-mail log still counts against the limits
    assert delete_childless_parents(db).parents_deleted == 0
    age_tokens(db, hours=25)
    assert delete_childless_parents(db).parents_deleted == 1
    assert [p.email for p in db.query(ParentDB).all()] == ["tata@example.com"]


def test_full_run_includes_the_new_passes(client, db, pending_user):
    pending_user.pending_since = naive_now() - timedelta(days=15)
    db.commit()
    report = run_retention(db)
    assert report.unconfirmed_accounts_deleted == 1
    assert "without parent consent" in report.summary()
