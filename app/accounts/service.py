"""Account lifecycle: creating users, parents, consent records, e-mailed links,
the e-mail rate limits and the login lockout.

Timestamps here are naive UTC, like every other DateTime column in the app.
Nothing in this module writes a full e-mail address or a token to a log.
"""

import hashlib
import hmac
import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..db.models import (
    ConsentDB,
    ConsentKind,
    EmailTokenDB,
    EmailTokenPurpose,
    LoginFailureDB,
    ParentDB,
    UserDB,
    UserStatus,
)
from ..email import EmailSendError, send_email
from ..email.templates import base_url, months_pl, render
from ..privacy import mask_email_for_display, mask_user_id
from . import passwords

logger = logging.getLogger(__name__)

# How long links live
CONSENT_TOKEN_TTL = timedelta(days=14)
RESET_TOKEN_TTL = timedelta(hours=1)
MANAGE_TOKEN_TTL = timedelta(days=30)

# A pending account is erased this long after pending_since without consent
PENDING_TTL = timedelta(days=14)

# E-mail limits (rolling 24 h, counted from email_tokens rows)
CONSENT_PER_ACCOUNT_PER_DAY = 3
CONSENT_PER_PARENT_PER_DAY = 5
CONSENT_COOLDOWN = timedelta(seconds=60)
RESET_PER_ACCOUNT_PER_DAY = 3
MANAGE_PER_PARENT_PER_DAY = 3

# Login lockout (15-minute window). A device where a login already signed in
# with its current password carries a tag for it in the device cookie; its
# failures count on their own (5), and no global cap applies to it - whoever
# holds a valid tag knew the current password. Every other attempt counts per
# (login, IP) (5), per IP (20) and per login (10). Guessing a child's password
# from elsewhere therefore never locks the child's own device.
LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
LOGIN_MAX_FAILURES_PER_ACTOR = 5
LOGIN_MAX_FAILURES_PER_IP = 20
LOGIN_MAX_FAILURES_PER_LOGIN = 10
DEVICE_COOKIE = "omj_device"
DEVICE_COOKIE_MAX_TAGS = 10
DEVICE_COOKIE_MAX_AGE = 365 * 24 * 60 * 60

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
EMAIL_MAX = 254

LIMIT_MESSAGE = "Wysłaliśmy już kilka wiadomości. Spróbuj jutro."
COOLDOWN_MESSAGE = "Wiadomość właśnie wyszła. Kolejną możesz wysłać za minutę."
SEND_FAILED_MESSAGE = "Nie udało się wysłać wiadomości. Spróbuj za chwilę."

_MONTHS_GENITIVE = (
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
)


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def date_pl(value: datetime) -> str:
    """'26 października 2026' (Warsaw calendar day)."""
    from zoneinfo import ZoneInfo

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    local = value.astimezone(ZoneInfo("Europe/Warsaw"))
    return f"{local.day} {_MONTHS_GENITIVE[local.month - 1]} {local.year}"


# --------------------------------------------------------------------- e-mail


def normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def email_problem(email: str) -> Optional[str]:
    if not email:
        return "Wpisz adres e-mail."
    if len(email) > EMAIL_MAX or not EMAIL_RE.match(email):
        return "To nie wygląda na adres e-mail. Sprawdź, czy nie ma literówki."
    return None


# --------------------------------------------------------------------- tokens


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_token(
    purpose: str, parent_id: str, user_id: Optional[str], ttl: timedelta
) -> tuple[str, EmailTokenDB]:
    raw = secrets.token_urlsafe(32)
    created = now()
    row = EmailTokenDB(
        token_hash=hash_token(raw),
        purpose=purpose,
        user_id=user_id,
        parent_id=parent_id,
        created_at=created,
        expires_at=created + ttl,
    )
    return raw, row


def find_token(db: Session, raw: Optional[str], purpose: str) -> Optional[EmailTokenDB]:
    if not raw or len(raw) > 200:
        return None
    return (
        db.query(EmailTokenDB)
        .filter(EmailTokenDB.token_hash == hash_token(raw), EmailTokenDB.purpose == purpose)
        .first()
    )


def token_state(token: Optional[EmailTokenDB]) -> str:
    """'valid', 'used', 'expired' or 'invalid'."""
    if token is None:
        return "invalid"
    if token.used_at is not None:
        return "used"
    if token.expires_at <= now():
        return "expired"
    return "valid"


def _count_tokens(
    db: Session,
    purpose: str,
    *,
    user_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    window: timedelta = timedelta(hours=24),
) -> tuple[int, Optional[datetime]]:
    """(count, newest created_at) of tokens sent in the window."""
    query = db.query(func.count(EmailTokenDB.id), func.max(EmailTokenDB.created_at)).filter(
        EmailTokenDB.purpose == purpose,
        EmailTokenDB.created_at >= now() - window,
    )
    if user_id is not None:
        query = query.filter(EmailTokenDB.user_id == user_id)
    if parent_id is not None:
        query = query.filter(EmailTokenDB.parent_id == parent_id)
    count, newest = query.one()
    return count or 0, newest


def consent_url(raw: str) -> str:
    return f"{base_url()}/rodzic/zgoda?t={raw}"


def manage_url(raw: str) -> str:
    return f"{base_url()}/rodzic?t={raw}"


def reset_url(raw: str) -> str:
    return f"{base_url()}/reset-hasla/nowe?t={raw}"


# --------------------------------------------------------------------- errors


class EmailLimitError(Exception):
    """An e-mail limit is reached; nothing was sent."""

    def __init__(self, code: str, detail: str, retry_after: Optional[int] = None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retry_after = retry_after


# --------------------------------------------------------------------- parents


def ensure_parent(db: Session, email: str) -> ParentDB:
    """Parent row for a normalised address, created and COMMITTED on its own.

    INSERT ... ON CONFLICT DO NOTHING, then SELECT: two requests naming the
    same address never wait on each other's uncommitted row, and the row is
    never part of a transaction that is still open when an e-mail goes out.
    A row left without children (the account creation failed, or the e-mail
    did) is removed by retention (delete_childless_parents).

    Commits the session: call it before making any other change.
    """
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert

    db.execute(
        insert(ParentDB)
        .values(id=uuid.uuid4().hex, email=email, created_at=now())
        .on_conflict_do_nothing(index_elements=["email"])
    )
    db.commit()
    return db.query(ParentDB).filter(ParentDB.email == email).one()


def end_read_transaction(db: Session) -> None:
    """Close the session's transaction before awaiting an e-mail provider.

    Sending can take seconds; a transaction open across the await would keep
    its locks (and a connection) for that long - and an uncommitted INSERT of
    a unique value makes every concurrent request for the same value wait.
    Callers commit their writes first; anything still pending here is a bug.
    """
    if db.new or db.dirty or db.deleted:
        raise RuntimeError("uncommitted changes would be held across an e-mail send")
    db.commit()


def child_identifier(user: UserDB) -> tuple[str, str]:
    """(label, value) naming the child's account to a parent. Nothing else the
    child typed (no Google display name) ever goes into a parent e-mail."""
    if user.login:
        return "Login dziecka", user.login
    return "Konto Google dziecka", user.email or ""


def pending_deadline(user: UserDB) -> Optional[datetime]:
    if user.status != UserStatus.PENDING_PARENT or user.pending_since is None:
        return None
    return user.pending_since + PENDING_TTL


# --------------------------------------------------------------------- consent


def set_pending(user: UserDB, parent: ParentDB) -> None:
    user.parent_id = parent.id
    user.status = UserStatus.PENDING_PARENT
    user.pending_since = now()


def record_consent(db: Session, user: UserDB, kind: str, parent_id: Optional[str] = None) -> None:
    db.add(
        ConsentDB(
            user_id=user.id,
            kind=kind,
            parent_id=parent_id,
            terms_version=settings.terms_version,
            given_at=now(),
        )
    )


def check_consent_limits(db: Session, user: UserDB, parent: ParentDB) -> None:
    """Raise EmailLimitError when another consent e-mail may not go out now."""
    user_count, user_newest = _count_tokens(db, EmailTokenPurpose.CONSENT, user_id=user.id)
    if user_newest is not None and now() - user_newest < CONSENT_COOLDOWN:
        retry = int((CONSENT_COOLDOWN - (now() - user_newest)).total_seconds()) + 1
        raise EmailLimitError("email_cooldown", COOLDOWN_MESSAGE, retry_after=retry)
    if user_count >= CONSENT_PER_ACCOUNT_PER_DAY:
        raise EmailLimitError("email_limit", LIMIT_MESSAGE)
    parent_count, _ = _count_tokens(db, EmailTokenPurpose.CONSENT, parent_id=parent.id)
    if parent_count >= CONSENT_PER_PARENT_PER_DAY:
        raise EmailLimitError("email_limit", LIMIT_MESSAGE)


def invalidate_consent_tokens(db: Session, user: UserDB) -> None:
    """Old consent links stop working (they read as expired, not as used)."""
    moment = now()
    for token in (
        db.query(EmailTokenDB)
        .filter(
            EmailTokenDB.user_id == user.id,
            EmailTokenDB.purpose == EmailTokenPurpose.CONSENT,
            EmailTokenDB.used_at.is_(None),
            EmailTokenDB.expires_at > moment,
        )
        .all()
    ):
        token.expires_at = moment


async def send_consent_email(
    db: Session,
    user: UserDB,
    parent: Optional[ParentDB] = None,
    on_sent: Optional[Callable[[], None]] = None,
) -> None:
    """Send the consent request to ``parent`` (default: the user's parent).

    Raises EmailLimitError (nothing sent) or EmailSendError (provider failed).
    No transaction is open while the provider is awaited. The token rows -
    which are also the rate-limit log - are written only after a successful
    send, so a failure never uses up a slot. ``on_sent`` runs after a
    successful send, in the same short commit as the token rows (e.g.
    switching the account to the new parent address).
    """
    parent = parent or user.parent
    if parent is None:
        raise ValueError("user has no parent")
    check_consent_limits(db, user, parent)

    consent_raw, consent_row = _new_token(
        EmailTokenPurpose.CONSENT, parent.id, user.id, CONSENT_TOKEN_TTL
    )
    manage_raw, manage_row = _new_token(
        EmailTokenPurpose.PARENT_MANAGE, parent.id, None, MANAGE_TOKEN_TTL
    )
    label, identifier = child_identifier(user)
    deadline = pending_deadline(user) or (now() + PENDING_TTL)
    to = parent.email
    user_id = user.id
    subject = "Prośba o zgodę — konto Twojego dziecka w serwisie Trener OMJ"
    html, text = render(
        "consent_request",
        subject=subject,
        child_identifier_label=label,
        child_identifier=identifier,
        consent_url=consent_url(consent_raw),
        decline_url=f"{consent_url(consent_raw)}&decyzja=nie",
        manage_url=manage_url(manage_raw),
        submission_retention=months_pl(settings.retention_submission_months or 24),
        inactive_retention=months_pl(settings.retention_inactive_account_months or 36),
        deadline=date_pl(min(deadline, consent_row.expires_at)),
    )
    end_read_transaction(db)
    await send_email(to, subject, html, text)
    # One short transaction after the send: the caller's switch + the log rows
    if on_sent is not None:
        on_sent()
    db.add(consent_row)
    db.add(manage_row)
    db.commit()
    logger.info(f"Consent e-mail sent for user {mask_user_id(user_id)}")


async def try_send_consent_email(db: Session, user: UserDB) -> bool:
    """Registration path: the account exists either way; report whether it went."""
    try:
        await send_consent_email(db, user)
        return True
    except (EmailSendError, EmailLimitError):
        return False


def activate_by_parent(db: Session, user: UserDB, token: EmailTokenDB) -> str:
    """Parent clicked "Wyrażam zgodę": activate, record consent, return a
    fresh manage token (raw) for the thank-you page and e-mail."""
    moment = now()
    user.status = UserStatus.ACTIVE
    user.pending_since = None
    record_consent(db, user, ConsentKind.PARENT, parent_id=token.parent_id)
    token.used_at = moment
    # Any other consent link for this account is spent too
    for other in (
        db.query(EmailTokenDB)
        .filter(
            EmailTokenDB.user_id == user.id,
            EmailTokenDB.purpose == EmailTokenPurpose.CONSENT,
            EmailTokenDB.used_at.is_(None),
        )
        .all()
    ):
        other.used_at = moment
    manage_raw, manage_row = _new_token(
        EmailTokenPurpose.PARENT_MANAGE, token.parent_id, None, MANAGE_TOKEN_TTL
    )
    db.add(manage_row)
    db.commit()
    logger.info(f"Parent consent given for user {mask_user_id(user.id)}")
    return manage_raw


async def send_account_active_email(db: Session, user: UserDB, manage_raw: str) -> None:
    """Best effort: the account is active whether or not this arrives."""
    parent = user.parent
    if parent is None:
        return
    to = parent.email
    user_id = user.id
    label, identifier = child_identifier(user)
    subject = "Konto Twojego dziecka jest aktywne"
    html, text = render(
        "account_active",
        subject=subject,
        child_identifier_label=label,
        child_identifier=identifier,
        is_login_account=user.is_login_account,
        manage_url=manage_url(manage_raw),
    )
    end_read_transaction(db)
    try:
        await send_email(to, subject, html, text)
    except EmailSendError:
        logger.warning(f"Account-active e-mail failed for user {mask_user_id(user_id)}")


# --------------------------------------------------------------------- reset


async def send_password_reset(db: Session, user: UserDB) -> None:
    """E-mail the parent a reset link. Raises EmailLimitError / EmailSendError."""
    parent = user.parent
    if parent is None or not user.login:
        raise ValueError("not a login account")
    count, _ = _count_tokens(db, EmailTokenPurpose.PASSWORD_RESET, user_id=user.id)
    if count >= RESET_PER_ACCOUNT_PER_DAY:
        raise EmailLimitError("email_limit", LIMIT_MESSAGE)

    reset_raw, reset_row = _new_token(
        EmailTokenPurpose.PASSWORD_RESET, parent.id, user.id, RESET_TOKEN_TTL
    )
    manage_raw, manage_row = _new_token(
        EmailTokenPurpose.PARENT_MANAGE, parent.id, None, MANAGE_TOKEN_TTL
    )
    subject = f"Zmiana hasła — konto {user.login}"
    html, text = render(
        "password_reset",
        subject=subject,
        login=user.login,
        reset_url=reset_url(reset_raw),
        manage_url=manage_url(manage_raw),
    )
    to = parent.email
    user_id = user.id
    end_read_transaction(db)
    await send_email(to, subject, html, text)
    db.add(reset_row)
    db.add(manage_row)
    db.commit()
    logger.info(f"Password reset e-mail sent for user {mask_user_id(user_id)}")


def set_password(db: Session, user: UserDB, password: str) -> None:
    """New password; every existing session of this account stops working."""
    moment = now()
    user.password_hash = passwords.hash_password(password)
    user.session_version = (user.session_version or 0) + 1
    # Any other reset link still in a mailbox stops working too
    for token in (
        db.query(EmailTokenDB)
        .filter(
            EmailTokenDB.user_id == user.id,
            EmailTokenDB.purpose == EmailTokenPurpose.PASSWORD_RESET,
            EmailTokenDB.used_at.is_(None),
        )
        .all()
    ):
        token.used_at = moment
    clear_login_failures(db, user.login)


# --------------------------------------------------------------------- manage


async def send_manage_link(db: Session, parent: ParentDB) -> None:
    """E-mail a link to the parent page. Raises EmailLimitError / EmailSendError.

    The limit counts every manage link sent to the address in 24 h, including
    the ones inside consent / reset / account-active e-mails.
    """
    count, _ = _count_tokens(db, EmailTokenPurpose.PARENT_MANAGE, parent_id=parent.id)
    if count >= MANAGE_PER_PARENT_PER_DAY:
        raise EmailLimitError("email_limit", LIMIT_MESSAGE)
    manage_raw, manage_row = _new_token(
        EmailTokenPurpose.PARENT_MANAGE, parent.id, None, MANAGE_TOKEN_TTL
    )
    subject = "Link do strony rodzica — Trener OMJ"
    html, text = render("manage_link", subject=subject, manage_url=manage_url(manage_raw))
    to = parent.email
    end_read_transaction(db)
    await send_email(to, subject, html, text)
    db.add(manage_row)
    db.commit()


def manage_token_parent(db: Session, raw: Optional[str]) -> tuple[str, Optional[ParentDB]]:
    """(state, parent) for a manage link."""
    token = find_token(db, raw, EmailTokenPurpose.PARENT_MANAGE)
    state = token_state(token)
    if state == "used":  # manage links are reusable; never marked used
        state = "valid"
    if state != "valid":
        return state, None
    return state, db.get(ParentDB, token.parent_id)


# --------------------------------------------------------------------- users


def new_users_limit_reached(db: Session, email: Optional[str]) -> bool:
    """rate_limit_new_users_per_day, bypassed by ALLOWED_EMAILS."""
    from ..groups import _get_allowed_emails

    from ..db.repositories import UserRepository

    allowed = _get_allowed_emails()
    if email and allowed and email.lower() in allowed:
        return False
    recent = UserRepository(db).count_recent_users(hours=24)
    return recent >= settings.rate_limit_new_users_per_day


@dataclass
class AgeAnswers:
    birth_year: int
    can_consent_alone: bool
    parent_email: Optional[str]  # normalised; None for 16+ Google


def create_google_user(
    db: Session, *, sub: str, email: str, name: Optional[str], answers: AgeAnswers
) -> UserDB:
    parent = ensure_parent(db, answers.parent_email) if answers.parent_email else None
    user = UserDB(
        id=uuid.uuid4().hex,
        google_sub=sub,
        email=email,
        name=name or None,
        birth_year=answers.birth_year,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    if parent is not None:
        set_pending(user, parent)
    else:
        record_consent(db, user, ConsentKind.SELF)
    db.commit()
    db.refresh(user)
    logger.info(f"Created Google user {mask_user_id(user.id)} ({user.status})")
    return user


def create_login_user(
    db: Session, *, login: str, password: str, birth_year: int, parent_email: str
) -> UserDB:
    """Login accounts always wait for a parent, whatever the age."""
    parent = ensure_parent(db, parent_email)
    user = UserDB(
        id=uuid.uuid4().hex,
        login=login,
        password_hash=passwords.hash_password(password),
        birth_year=birth_year,
        status=UserStatus.ACTIVE,
        parent_id=parent.id,
    )
    db.add(user)
    db.flush()
    set_pending(user, parent)
    db.commit()
    db.refresh(user)
    logger.info(f"Created login user {mask_user_id(user.id)}")
    return user


def account_summary(db: Session, user: UserDB) -> dict:
    """What the frontend needs to know about the account's state."""
    pending = None
    if user.status == UserStatus.PENDING_PARENT:
        _, newest = _count_tokens(db, EmailTokenPurpose.CONSENT, user_id=user.id)
        pending = {
            "parent_email": mask_email_for_display(user.parent.email if user.parent else None),
            "deadline": iso_utc(pending_deadline(user)),
            "last_sent_at": iso_utc(newest),
            "resend_available_at": iso_utc(newest + CONSENT_COOLDOWN) if newest else None,
        }
    return {
        "status": user.status,
        "needs_profile": user.birth_year is None,
        "login_method": "login" if user.login else "google",
        "pending": pending,
    }


# --------------------------------------------------------------------- login lockout


def _hmac(value: str) -> str:
    key = (settings.session_secret_key or "").encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def ip_hash(ip: Optional[str]) -> str:
    return _hmac(ip or "unknown")


def _device_serializer():
    from itsdangerous import URLSafeSerializer

    return URLSafeSerializer(settings.session_secret_key or "", salt="omj-device")


@dataclass
class Device:
    """The device cookie: a random id (identifies nobody) and the tags of the
    logins that signed in here with their current password."""

    device_id: Optional[str]
    tags: list


def read_device(cookie_value: Optional[str]) -> Device:
    if not cookie_value:
        return Device(None, [])
    try:
        data = _device_serializer().loads(cookie_value)
    except Exception:  # bad signature, tampering, old format
        return Device(None, [])
    device_id = data.get("d") if isinstance(data, dict) else None
    tags = data.get("t") if isinstance(data, dict) else None
    if not isinstance(device_id, str) or not isinstance(tags, list):
        return Device(None, [])
    return Device(device_id, [t for t in tags if isinstance(t, str)][-DEVICE_COOKIE_MAX_TAGS:])


def device_tag(device_id: str, login: str, session_version: int) -> str:
    """Bound to the password: a reset bumps session_version and voids it."""
    return _hmac(f"device-tag:{device_id}:{login}:{session_version}")[:32]


def device_cookie_after_login(device: Device, login: str, session_version: int) -> str:
    """Signed cookie value with this login's current tag (newest last)."""
    device_id = device.device_id or secrets.token_urlsafe(16)
    tag = device_tag(device_id, login, session_version)
    tags = [t for t in device.tags if t != tag] + [tag]
    return _device_serializer().dumps({"d": device_id, "t": tags[-DEVICE_COOKIE_MAX_TAGS:]})


def login_actor(
    login: str, ip: Optional[str], device: Device, user: Optional[UserDB]
) -> tuple[str, bool]:
    """(actor digest, known device) for counting this attempt."""
    if (
        user is not None
        and device.device_id
        and device_tag(device.device_id, login, user.session_version or 0) in device.tags
    ):
        return _hmac(f"actor-device:{device.device_id}:{login}"), True
    return ip_hash(ip), False


def _failures(db: Session, *conditions) -> int:
    since = now() - LOGIN_FAILURE_WINDOW
    return (
        db.query(func.count(LoginFailureDB.id))
        .filter(LoginFailureDB.at >= since, *conditions)
        .scalar()
        or 0
    )


def login_locked(db: Session, login: str, actor: str, known_device: bool) -> bool:
    if _failures(db, LoginFailureDB.login == login, LoginFailureDB.ip_hash == actor) >= LOGIN_MAX_FAILURES_PER_ACTOR:
        return True
    if known_device:
        return False
    if _failures(db, LoginFailureDB.ip_hash == actor) >= LOGIN_MAX_FAILURES_PER_IP:
        return True
    return _failures(db, LoginFailureDB.login == login) >= LOGIN_MAX_FAILURES_PER_LOGIN


def record_login_failure(db: Session, login: str, actor: str) -> None:
    db.add(LoginFailureDB(login=login[:64], ip_hash=actor, at=now()))
    db.commit()


def clear_login_failures(db: Session, login: Optional[str], actor: Optional[str] = None) -> None:
    """A successful login clears its own actor's failures only; a new
    password (actor=None) clears the login's whole slate."""
    if not login:
        return
    query = db.query(LoginFailureDB).filter(LoginFailureDB.login == login)
    if actor is not None:
        query = query.filter(LoginFailureDB.ip_hash == actor)
    query.delete(synchronize_session=False)
