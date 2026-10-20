"""Phone reminders about due patterns (Web Push with VAPID).

The decisions are pure functions (when to run, what to say, which endpoints
we accept); ``run_reminders`` applies them to the database and ``send`` talks
to the push service. One reminder per user per Europe/Warsaw day, and only
when something is due.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Callable, Optional
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..db.models import PushSubscriptionDB, ReminderSettingsDB, utc_now
from ..db.patterns import PatternRepository
from ..patterns import srs
from ..privacy import mask_user_id

logger = logging.getLogger(__name__)

WARSAW = ZoneInfo("Europe/Warsaw")

DEFAULT_WEEKDAY_TIME = "16:30"
DEFAULT_WEEKEND_TIME = "10:00"
# A reminder the API missed (restart, outage) is still sent until this hour
LATEST_SEND = time(21, 0)
EARLIEST_SLOT = time(6, 0)
SLOT_STEP_MINUTES = 5

REVIEW_URL = "/wzorce/powtorka"
TAG = "wzorce-review"
# A reminder older than this is not worth delivering (phone off all evening)
TTL_SECONDS = 6 * 60 * 60
TRIGGER_MAX_CHARS = 80
MAX_SUBSCRIPTIONS_PER_USER = 10

# The browser picks the push service; we only ever POST to these hosts (SSRF)
_PUSH_HOSTS = {
    "fcm.googleapis.com",
    "android.googleapis.com",
    "updates.push.services.mozilla.com",
    "web.push.apple.com",
}
_PUSH_HOST_SUFFIXES = (".push.apple.com", ".notify.windows.com")
_ENDPOINT_MAX_CHARS = 1024
_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def enabled() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def valid_endpoint(endpoint: str) -> bool:
    """https on a known push service, nothing else (the server POSTs there)."""
    if not endpoint or len(endpoint) > _ENDPOINT_MAX_CHARS:
        return False
    try:
        parts = urlsplit(endpoint)
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        return False
    return host in _PUSH_HOSTS or host.endswith(_PUSH_HOST_SUFFIXES)


def valid_key(value: str) -> bool:
    return bool(value) and len(value) <= 255 and bool(_KEY_RE.match(value))


def parse_slot(value: str) -> Optional[str]:
    """"HH:MM" between 06:00 and 21:00 in 5-minute steps, else None."""
    match = _TIME_RE.match(value or "")
    if not match:
        return None
    slot = time(int(match.group(1)), int(match.group(2)))
    if not (EARLIEST_SLOT <= slot <= LATEST_SEND) or slot.minute % SLOT_STEP_MINUTES:
        return None
    return value


def slot_for(day: date, weekday_time: str, weekend_time: str) -> time:
    raw = weekend_time if day.weekday() >= 5 else weekday_time
    hours, minutes = raw.split(":")
    return time(int(hours), int(minutes))


def should_run(now_local: datetime, weekday_time: str, weekend_time: str, last_run_on: Optional[date]) -> bool:
    """Past today's slot, before LATEST_SEND, and not run yet today."""
    today = now_local.date()
    if last_run_on == today:
        return False
    now_time = now_local.time()
    return slot_for(today, weekday_time, weekend_time) <= now_time < LATEST_SEND


def waiting_phrase(count: int) -> str:
    """'1 wzorzec czeka', '3 wzorce czekają', '5 wzorców czeka' (Polish plural)."""
    if count == 1:
        return "1 wzorzec czeka"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return f"{count} wzorce czekają"
    return f"{count} wzorców czeka"


def reminder_payload(count: int, first_trigger: str) -> dict:
    trigger = " ".join((first_trigger or "").split())
    if len(trigger) > TRIGGER_MAX_CHARS:
        trigger = trigger[: TRIGGER_MAX_CHARS - 1].rstrip() + "…"
    body = f"{waiting_phrase(count)} na powtórkę."
    if trigger:
        body += f" Na początek: „{trigger}”"
    return {"title": "Powtórka wzorców", "body": body, "url": REVIEW_URL, "tag": TAG}


TEST_PAYLOAD = {
    "title": "Przypomnienia działają",
    "body": "Tak będzie wyglądać przypomnienie o powtórce wzorców.",
    "url": "/wzorce",
    "tag": "wzorce-test",
}


# ------------------------------------------------------------------ sending

OK, GONE, FAILED = "ok", "gone", "failed"


def send(subscription: PushSubscriptionDB, payload: dict) -> str:
    """POST one encrypted message to the device's push service (blocking)."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=settings.vapid_private_key,
            # A fresh dict per call: pywebpush writes "aud" and "exp" into it
            vapid_claims={"sub": settings.vapid_subject},
            ttl=TTL_SECONDS,
            timeout=10,
        )
        return OK
    except WebPushException as e:
        status_code = getattr(e.response, "status_code", None)
        if status_code in (404, 410):
            return GONE
        logger.warning(f"Web push failed: HTTP {status_code}")
        return FAILED
    except Exception as e:
        logger.warning(f"Web push failed: {type(e).__name__}")
        return FAILED


Sender = Callable[[PushSubscriptionDB, dict], str]


def deliver(db: Session, subscriptions: list[PushSubscriptionDB], payload: dict, sender: Sender) -> dict:
    """Send to every device; forget the ones the push service says are gone."""
    counts = {OK: 0, GONE: 0, FAILED: 0}
    for subscription in subscriptions:
        result = sender(subscription, payload)
        counts[result] += 1
        if result == GONE:
            db.delete(subscription)
        elif result == OK:
            subscription.last_success_at = utc_now()
    db.commit()
    return counts


# ------------------------------------------------------------------ settings / subscriptions


@dataclass
class ReminderTimes:
    weekday_time: str
    weekend_time: str
    last_run_on: Optional[date] = None


def times_for(db: Session, user_id: str) -> ReminderTimes:
    row = db.get(ReminderSettingsDB, user_id)
    if not row:
        return ReminderTimes(DEFAULT_WEEKDAY_TIME, DEFAULT_WEEKEND_TIME)
    return ReminderTimes(row.weekday_time, row.weekend_time, row.last_run_on)


def save_times(db: Session, user_id: str, weekday_time: str, weekend_time: str) -> None:
    row = db.get(ReminderSettingsDB, user_id)
    if row:
        row.weekday_time, row.weekend_time = weekday_time, weekend_time
    else:
        db.add(ReminderSettingsDB(user_id=user_id, weekday_time=weekday_time, weekend_time=weekend_time))
    db.commit()


def subscribe(db: Session, user_id: str, endpoint: str, p256dh: str, auth: str) -> None:
    """Store a device; an endpoint known for another account moves here (shared phone)."""
    row = db.query(PushSubscriptionDB).filter(PushSubscriptionDB.endpoint == endpoint).first()
    if row:
        row.user_id, row.p256dh, row.auth = user_id, p256dh, auth
    else:
        db.add(PushSubscriptionDB(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth))
    db.flush()
    # Old devices beyond the cap go first
    rows = (
        db.query(PushSubscriptionDB)
        .filter(PushSubscriptionDB.user_id == user_id)
        .order_by(PushSubscriptionDB.created_at.desc(), PushSubscriptionDB.id.desc())
        .all()
    )
    for stale in rows[MAX_SUBSCRIPTIONS_PER_USER:]:
        db.delete(stale)
    db.commit()


def unsubscribe(db: Session, user_id: str, endpoint: str) -> bool:
    deleted = (
        db.query(PushSubscriptionDB)
        .filter(PushSubscriptionDB.user_id == user_id, PushSubscriptionDB.endpoint == endpoint)
        .delete(synchronize_session=False)
    )
    db.commit()
    return bool(deleted)


def subscriptions_of(db: Session, user_id: str) -> list[PushSubscriptionDB]:
    return db.query(PushSubscriptionDB).filter(PushSubscriptionDB.user_id == user_id).all()


# ------------------------------------------------------------------ the daily run


def _claim(db: Session, user_id: str, today: date) -> bool:
    """Mark today's run as taken; False when someone else already took it."""
    claimed = db.execute(
        update(ReminderSettingsDB)
        .where(
            ReminderSettingsDB.user_id == user_id,
            or_(ReminderSettingsDB.last_run_on.is_(None), ReminderSettingsDB.last_run_on != today),
        )
        .values(last_run_on=today)
    ).rowcount
    if claimed:
        db.commit()
        return True
    if db.get(ReminderSettingsDB, user_id):
        db.rollback()
        return False
    try:
        db.add(ReminderSettingsDB(
            user_id=user_id,
            weekday_time=DEFAULT_WEEKDAY_TIME,
            weekend_time=DEFAULT_WEEKEND_TIME,
            last_run_on=today,
        ))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def run_reminders(db: Session, now: Optional[datetime] = None, sender: Sender = send) -> int:
    """Send today's reminders that are due by now; returns how many users got one."""
    now_local = (now or datetime.now(WARSAW)).astimezone(WARSAW)
    today = now_local.date()
    user_ids = [uid for (uid,) in db.query(PushSubscriptionDB.user_id).distinct().all()]
    reminded = 0
    for user_id in user_ids:
        times = times_for(db, user_id)
        if not should_run(now_local, times.weekday_time, times.weekend_time, times.last_run_on):
            continue
        if not _claim(db, user_id, today):
            continue
        due = PatternRepository(db).due(user_id, today)
        if not due:
            continue
        # The same pattern the review page opens with
        first = srs.interleave(due, key=lambda p: p.category)[0]
        payload = reminder_payload(len(due), first.trigger)
        counts = deliver(db, subscriptions_of(db, user_id), payload, sender)
        if counts[OK]:
            reminded += 1
        logger.info(
            f"Pattern reminder for {mask_user_id(user_id)}: {len(due)} due, "
            f"sent {counts[OK]}, gone {counts[GONE]}, failed {counts[FAILED]}"
        )
    return reminded
