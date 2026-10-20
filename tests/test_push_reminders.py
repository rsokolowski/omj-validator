"""Phone reminders about due patterns: the decisions, the daily run and the API."""

from datetime import date, datetime, timedelta

import pytest

from app.config import settings
from app.db.models import PatternDB, PushSubscriptionDB, ReminderSettingsDB, UserDB
from app.push import routes as push_routes
from app.push import service
from test_pattern_api import (  # noqa: F401 - fixtures
    OTHER_USER_ID,
    USER_ID,
    client,
    create,
    current_user,
    db,
    omj,
    today,
)

APPLE = "https://web.push.apple.com/QGx1c3QtYS10ZXN0LXRva2Vu"
FCM = "https://fcm.googleapis.com/fcm/send/abc123:def"
KEYS = {"p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM", "auth": "tBHItJI5svbpez7KI4CCXg"}

# 2026-10-20 is a Tuesday, 2026-10-24 a Saturday
TUESDAY = date(2026, 10, 20)
SATURDAY = date(2026, 10, 24)


def at(day: date, hh: int, mm: int) -> datetime:
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=service.WARSAW)


@pytest.fixture
def vapid(monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "BPUBLICKEY")
    monkeypatch.setattr(settings, "vapid_private_key", "private")
    push_routes._last_test.clear()


class FakeSender:
    def __init__(self, result=service.OK):
        self.result = result
        self.sent = []

    def __call__(self, subscription, payload):
        self.sent.append((subscription.endpoint, payload))
        return self.result


def add_pattern(db, user_id=USER_ID, due=TUESDAY, trigger="Iloczyn kilku kolejnych liczb", category="algebra", **kw):
    pid = f"p{len(db.query(PatternDB).all()):011d}"
    db.add(PatternDB(id=pid, user_id=user_id, trigger=trigger, action="Szukaj podzielności",
                     category=category, skills=[], origin="own", refinement=[], due_on=due, **kw))
    db.commit()
    return pid


def add_device(db, user_id=USER_ID, endpoint=APPLE):
    service.subscribe(db, user_id, endpoint, KEYS["p256dh"], KEYS["auth"])


class TestDecisions:
    @pytest.mark.parametrize("count,phrase", [
        (1, "1 wzorzec czeka"), (2, "2 wzorce czekają"), (4, "4 wzorce czekają"),
        (5, "5 wzorców czeka"), (12, "12 wzorców czeka"), (22, "22 wzorce czekają"),
        (25, "25 wzorców czeka"),
    ])
    def test_polish_plural(self, count, phrase):
        assert service.waiting_phrase(count) == phrase

    def test_payload_has_trigger_and_opens_review(self):
        payload = service.reminder_payload(3, "  Iloczyn\n kolejnych   liczb ")
        assert payload["title"] == "Powtórka wzorców"
        assert payload["body"] == "3 wzorce czekają na powtórkę. Na początek: „Iloczyn kolejnych liczb”"
        assert payload["url"] == "/wzorce/powtorka"

    def test_long_trigger_is_cut(self):
        body = service.reminder_payload(1, "x" * 200)["body"]
        assert body.endswith("…”") and len(body) < 140

    @pytest.mark.parametrize("endpoint,ok", [
        (APPLE, True), (FCM, True),
        ("https://updates.push.services.mozilla.com/wpush/v2/x", True),
        ("https://db5p.notify.windows.com/w/?token=x", True),
        ("https://api.push.apple.com/x", True),
        ("http://fcm.googleapis.com/fcm/send/x", False),
        ("https://fcm.googleapis.com:8443/x", False),
        ("https://user:pw@fcm.googleapis.com/x", False),
        ("https://evil.example/fcm.googleapis.com", False),
        ("https://fcm.googleapis.com.evil.example/x", False),
        ("https://localhost/x", False),
        ("https://169.254.169.254/latest", False),
        ("https://fcm.googleapis.com/" + "x" * 1100, False),
        ("", False),
    ])
    def test_endpoint_allowlist(self, endpoint, ok):
        assert service.valid_endpoint(endpoint) is ok

    @pytest.mark.parametrize("value,ok", [
        ("16:30", True), ("06:00", True), ("21:00", True), ("05:55", False),
        ("21:05", False), ("16:31", False), ("7:00", False), ("24:00", False), ("ab:cd", False),
    ])
    def test_slots(self, value, ok):
        assert (service.parse_slot(value) is not None) is ok

    def test_weekday_and_weekend_slots(self):
        args = (service.DEFAULT_WEEKDAY_TIME, service.DEFAULT_WEEKEND_TIME, None)
        assert not service.should_run(at(TUESDAY, 16, 29), *args)
        assert service.should_run(at(TUESDAY, 16, 30), *args)
        assert service.should_run(at(TUESDAY, 20, 59), *args)
        assert not service.should_run(at(TUESDAY, 21, 0), *args)
        assert service.should_run(at(SATURDAY, 10, 0), *args)
        assert not service.should_run(at(SATURDAY, 9, 59), *args)
        assert not service.should_run(at(TUESDAY, 17, 0), "16:30", "10:00", TUESDAY)


class TestDailyRun:
    def test_sends_once_a_day_when_due(self, db):
        add_pattern(db, due=TUESDAY - timedelta(days=2), trigger="Najstarszy")
        add_pattern(db, trigger="Drugi", category="geometria")
        add_device(db)
        sender = FakeSender()
        assert service.run_reminders(db, at(TUESDAY, 16, 31), sender) == 1
        assert sender.sent == [(APPLE, service.reminder_payload(2, "Najstarszy"))]
        assert service.run_reminders(db, at(TUESDAY, 18, 0), sender) == 0
        assert len(sender.sent) == 1
        assert db.get(PushSubscriptionDB, 1).last_success_at is not None

    def test_nothing_before_slot_and_after_latest(self, db):
        add_pattern(db)
        add_device(db)
        sender = FakeSender()
        service.run_reminders(db, at(TUESDAY, 16, 0), sender)
        service.run_reminders(db, at(TUESDAY, 21, 30), sender)
        assert sender.sent == []

    def test_nothing_when_nothing_due(self, db):
        add_pattern(db, due=TUESDAY + timedelta(days=1))
        add_pattern(db, archived_at=datetime(2026, 10, 1))
        add_device(db)
        sender = FakeSender()
        service.run_reminders(db, at(TUESDAY, 17, 0), sender)
        assert sender.sent == []
        # The day is spent: a pattern becoming due later today does not trigger a second look
        assert db.get(ReminderSettingsDB, USER_ID).last_run_on == TUESDAY

    def test_custom_times(self, db):
        add_pattern(db, due=SATURDAY)
        add_device(db)
        service.save_times(db, USER_ID, "16:30", "08:00")
        sender = FakeSender()
        service.run_reminders(db, at(SATURDAY, 8, 5), sender)
        assert len(sender.sent) == 1

    def test_users_without_devices_are_skipped(self, db):
        add_pattern(db)
        sender = FakeSender()
        service.run_reminders(db, at(TUESDAY, 17, 0), sender)
        assert sender.sent == [] and db.get(ReminderSettingsDB, USER_ID) is None

    def test_gone_device_is_forgotten(self, db):
        add_pattern(db)
        add_device(db)
        service.run_reminders(db, at(TUESDAY, 17, 0), FakeSender(service.GONE))
        assert db.query(PushSubscriptionDB).count() == 0

    def test_only_own_patterns(self, db):
        add_pattern(db, user_id=OTHER_USER_ID)
        add_device(db)
        sender = FakeSender()
        service.run_reminders(db, at(TUESDAY, 17, 0), sender)
        assert sender.sent == []


class TestSubscriptions:
    def test_shared_device_moves_to_new_account(self, db):
        add_device(db, USER_ID)
        add_device(db, OTHER_USER_ID)
        rows = db.query(PushSubscriptionDB).all()
        assert [r.user_id for r in rows] == [OTHER_USER_ID]

    def test_cap_drops_oldest(self, db):
        for i in range(service.MAX_SUBSCRIPTIONS_PER_USER + 2):
            add_device(db, endpoint=f"{FCM}{i}")
        endpoints = {r.endpoint for r in db.query(PushSubscriptionDB).all()}
        assert len(endpoints) == service.MAX_SUBSCRIPTIONS_PER_USER
        assert f"{FCM}0" not in endpoints and f"{FCM}11" in endpoints

    def test_deleted_with_account(self, db):
        add_device(db)
        service.save_times(db, USER_ID, "17:00", "10:00")
        db.delete(db.get(UserDB, USER_ID))
        db.commit()
        assert db.query(PushSubscriptionDB).count() == 0
        assert db.query(ReminderSettingsDB).count() == 0


class TestApi:
    def test_config_disabled_without_keys(self, client, monkeypatch):
        monkeypatch.setattr(settings, "vapid_public_key", None)
        body = client.get("/api/push/config").json()
        assert body["enabled"] is False and body["public_key"] is None
        assert client.post("/api/push/subscriptions", json={"endpoint": APPLE, "keys": KEYS}).status_code == 503

    def test_subscribe_settings_unsubscribe(self, client, vapid):
        body = client.get("/api/push/config").json()
        assert body == {"enabled": True, "public_key": "BPUBLICKEY", "weekday_time": "16:30",
                        "weekend_time": "10:00", "devices": 0}
        assert client.post("/api/push/subscriptions", json={"endpoint": APPLE, "keys": KEYS}).json()["devices"] == 1
        saved = client.put("/api/push/settings", json={"weekday_time": "17:15", "weekend_time": "09:00"}).json()
        assert (saved["weekday_time"], saved["weekend_time"]) == ("17:15", "09:00")
        assert client.post("/api/push/subscriptions/delete", json={"endpoint": APPLE}).json()["devices"] == 0

    def test_rejects_foreign_endpoint_and_bad_keys(self, client, vapid):
        r = client.post("/api/push/subscriptions", json={"endpoint": "https://evil.example/x", "keys": KEYS})
        assert r.status_code == 400
        r = client.post("/api/push/subscriptions", json={"endpoint": APPLE, "keys": {"p256dh": "a b", "auth": "x"}})
        assert r.status_code == 400

    def test_rejects_bad_time(self, client, vapid):
        r = client.put("/api/push/settings", json={"weekday_time": "23:00", "weekend_time": "10:00"})
        assert r.status_code == 422

    def test_cannot_unsubscribe_someone_elses_device(self, client, db, vapid):
        add_device(db, OTHER_USER_ID)
        client.post("/api/push/subscriptions/delete", json={"endpoint": APPLE})
        assert db.query(PushSubscriptionDB).count() == 1

    def test_test_notification(self, client, db, vapid, monkeypatch):
        sender = FakeSender()
        monkeypatch.setattr(service, "send", sender)
        assert client.post("/api/push/test").status_code == 409
        add_device(db)
        assert client.post("/api/push/test").json() == {"sent": 1, "failed": 0}
        assert sender.sent[0][1] == service.TEST_PAYLOAD
        assert client.post("/api/push/test").status_code == 429
