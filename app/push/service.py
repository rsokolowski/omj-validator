"""Phone reminders about due patterns (Web Push with VAPID).

The decisions are pure functions (when to run, what to say, which endpoints
we accept); ``run_reminders`` applies them to the database and ``send`` talks
to the push service. One reminder per user per Europe/Warsaw day, and only
when something is due.
"""

import base64
import binascii
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
from ..db.models import PatternDB, PushSubscriptionDB, ReminderSettingsDB, UserDB, UserStatus, utc_now
from ..patterns import srs
from ..privacy import mask_user_id

logger = logging.getLogger(__name__)

WARSAW = ZoneInfo("Europe/Warsaw")

DEFAULT_WEEKDAY_TIME = "16:30"
DEFAULT_WEEKEND_TIME = "10:00"
# A reminder the API missed (restart, outage, push service error) is still
# sent until LATEST_SEND; the latest slot a user may pick is LATEST_SLOT
LATEST_SLOT = time(21, 0)
LATEST_SEND = time(21, 30)
EARLIEST_SLOT = time(6, 0)
SLOT_STEP_MINUTES = 5

REVIEW_URL = "/wzorce/powtorka"
TAG = "wzorce-review"
# A reminder older than this is not worth delivering (phone off all evening);
# never kept past QUIET_FROM, so a phone back online at night stays quiet
TTL_SECONDS = 6 * 60 * 60
QUIET_FROM = time(22, 0)
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


def _b64url_bytes(value: str) -> Optional[bytes]:
    if not value or len(value) > 255 or not _KEY_RE.match(value):
        return None
    bare = value.rstrip("=")
    try:
        return base64.urlsafe_b64decode(bare + "=" * (-len(bare) % 4))
    except (binascii.Error, ValueError):
        return None


def valid_keys(p256dh: str, auth: str) -> bool:
    """An uncompressed P-256 point (65 bytes, 0x04...) and a 16-byte auth secret."""
    point, secret = _b64url_bytes(p256dh), _b64url_bytes(auth)
    return bool(point) and len(point) == 65 and point[0] == 4 and bool(secret) and len(secret) == 16


def parse_slot(value: str) -> Optional[str]:
    """"HH:MM" between 06:00 and 21:00 in 5-minute steps, else None."""
    match = _TIME_RE.match(value or "")
    if not match:
        return None
    slot = time(int(match.group(1)), int(match.group(2)))
    if not (EARLIEST_SLOT <= slot <= LATEST_SLOT) or slot.minute % SLOT_STEP_MINUTES:
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


def ttl_seconds(now_local: datetime) -> int:
    """TTL_SECONDS, but expiring by QUIET_FROM the same evening."""
    quiet = datetime.combine(now_local.date(), QUIET_FROM, tzinfo=now_local.tzinfo)
    return max(60, min(TTL_SECONDS, int((quiet - now_local).total_seconds())))


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


def _no_redirect_session():
    """The allowlist checks only the endpoint: a 3xx must not take the server elsewhere."""
    import requests

    session = requests.Session()
    session.max_redirects = 0
    return session


def send(subscription: PushSubscriptionDB, payload: dict) -> str:
    """POST one encrypted message to the device's push service (blocking)."""
    from pywebpush import WebPushException, webpush

    session = _no_redirect_session()
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
            ttl=ttl_seconds(datetime.now(WARSAW)),
            timeout=10,
            requests_session=session,
        )
        return OK
    except WebPushException as e:
        status_code = getattr(e.response, "status_code", None)
        if status_code in (404, 410):
            return GONE
        logger.warning(f"Web push failed: HTTP {status_code}")
        return FAILED
    except Exception as e:  # includes TooManyRedirects for any 3xx
        logger.warning(f"Web push failed: {type(e).__name__}")
        return FAILED
    finally:
        session.close()


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


class EndpointTaken(Exception):
    """The endpoint belongs to another account and the keys do not prove it is this device."""


def subscribe(db: Session, user_id: str, endpoint: str, p256dh: str, auth: str) -> None:
    """Store a device for the account's current session.

    An endpoint stored for another account moves here only with the same keys
    - the same browser on a shared phone. Knowing someone's endpoint alone is
    not enough to take their device over.
    """
    user = db.get(UserDB, user_id)
    session_version = user.session_version if user else 0
    row = db.query(PushSubscriptionDB).filter(PushSubscriptionDB.endpoint == endpoint).first()
    if row:
        if row.user_id != user_id and (row.p256dh, row.auth) != (p256dh, auth):
            raise EndpointTaken()
        row.user_id, row.p256dh, row.auth = user_id, p256dh, auth
        row.session_version = session_version
        # Re-linked now: must not be the "oldest device" the cap drops below
        row.created_at = utc_now()
    else:
        db.add(PushSubscriptionDB(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth,
                                  session_version=session_version))
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


def live_subscriptions(db: Session, user: UserDB) -> list[PushSubscriptionDB]:
    """Devices switched on in the current session; older ones are deleted.

    After a password reset (session_version bumped) a device that was signed
    in before must not keep receiving the account's pattern triggers.
    """
    live = []
    for subscription in subscriptions_of(db, user.id):
        if subscription.session_version == user.session_version:
            live.append(subscription)
        else:
            db.delete(subscription)
    db.commit()
    return live


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


def _candidates(db: Session, today: date) -> list[tuple[str, str, str]]:
    """(user_id, weekday_time, weekend_time) of active users with a device, not run today."""
    rows = (
        db.query(UserDB.id, ReminderSettingsDB.weekday_time, ReminderSettingsDB.weekend_time)
        .join(PushSubscriptionDB, PushSubscriptionDB.user_id == UserDB.id)
        .outerjoin(ReminderSettingsDB, ReminderSettingsDB.user_id == UserDB.id)
        # Pending (parent consent) accounts cannot use the app - no reminders either
        .filter(UserDB.status == UserStatus.ACTIVE)
        .filter(or_(ReminderSettingsDB.last_run_on.is_(None), ReminderSettingsDB.last_run_on != today))
        .distinct()
        .all()
    )
    return [(uid, wd or DEFAULT_WEEKDAY_TIME, we or DEFAULT_WEEKEND_TIME) for uid, wd, we in rows]


def _due_triggers(db: Session, user_id: str, today: date) -> list[tuple[str, Optional[str]]]:
    """(trigger, category) of due patterns, most overdue first (as PatternRepository.due)."""
    return (
        db.query(PatternDB.trigger, PatternDB.category)
        .filter(PatternDB.user_id == user_id, PatternDB.archived_at.is_(None), PatternDB.due_on <= today)
        .order_by(PatternDB.due_on, PatternDB.created_at)
        .all()
    )


def _release(db: Session, user_id: str) -> None:
    """Every device failed (push service down): let the next run try again."""
    db.execute(update(ReminderSettingsDB).where(ReminderSettingsDB.user_id == user_id).values(last_run_on=None))
    db.commit()


def run_reminders(db: Session, now: Optional[datetime] = None, sender: Sender = send) -> int:
    """Send today's reminders that are due by now; returns how many users got one."""
    now_local = (now or datetime.now(WARSAW)).astimezone(WARSAW)
    today = now_local.date()
    reminded = 0
    for user_id, weekday_time, weekend_time in _candidates(db, today):
        if not should_run(now_local, weekday_time, weekend_time, None):
            continue
        if not _claim(db, user_id, today):
            continue
        due = _due_triggers(db, user_id, today)
        if not due:
            continue
        # The same pattern the review page opens with
        first = srs.interleave(due, key=lambda row: row[1])[0]
        payload = reminder_payload(len(due), first[0])
        counts = deliver(db, live_subscriptions(db, db.get(UserDB, user_id)), payload, sender)
        if counts[OK]:
            reminded += 1
        elif counts[FAILED]:
            _release(db, user_id)
        logger.info(
            f"Pattern reminder for {mask_user_id(user_id)}: {len(due)} due, "
            f"sent {counts[OK]}, gone {counts[GONE]}, failed {counts[FAILED]}"
        )
    return reminded
