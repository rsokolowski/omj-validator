"""HTTP API for accounts: registration, login/password, the age step for
existing accounts, the pending screen, the parent page and password reset.

Parent endpoints authenticate with the token from the e-mail, never with the
session (the parent is usually on their own phone). The e-mail links open
PAGES (mail scanners and link previewers open links); the page sends the
token to the API in a POST body - never in a query string, which would land
in proxy access logs - and only an explicit button press changes anything.
"""

import contextlib
import logging
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import (
    SESSION_PENDING_GOOGLE_KEY,
    SESSION_PENDING_REGISTRATION_KEY,
    PENDING_GOOGLE_SECONDS,
    allow_inactive_account,
    current_account,
    safe_next_path,
    start_session,
)
from ..config import settings
from ..db import SessionLocal, get_db
from ..db.models import (
    EmailTokenPurpose,
    ParentDB,
    UserDB,
    UserStatus,
)
from ..email import EmailSendError, outbox
from ..privacy import mask_email_for_display, mask_user_id
from ..rate_limits import record_erasure_quota
from ..retention import erase_user_data
from . import age, passwords, service, turnstile
from .service import EmailLimitError, SEND_FAILED_MESSAGE

logger = logging.getLogger(__name__)

router = APIRouter(tags=["accounts"])

GENERIC_LOGIN_ERROR = "Nieprawidłowy login lub hasło."
LOCKED_MESSAGE = "Zbyt wiele nieudanych prób logowania. Spróbuj ponownie za 15 minut."
NEW_USERS_LIMIT_MESSAGE = (
    "Dziś założono już bardzo dużo kont, więc rejestracja jest chwilowo wstrzymana. "
    "Spróbuj jutro."
)
IP_LIMIT_MESSAGE = (
    "Z tej sieci (np. szkolnej) założono dziś już bardzo dużo kont, więc kolejne można "
    "będzie założyć jutro. Możesz też spróbować z innej sieci, np. w domu."
)
LINK_INVALID = "Ten link jest nieprawidłowy albo konto zostało już usunięte."
LINK_EXPIRED = "Ten link wygasł."
LINK_USED = "Ten link został już wykorzystany."


def _fail(status_code: int, detail: str, code: Optional[str] = None, **extra) -> JSONResponse:
    body = {"detail": detail}
    if code:
        body["code"] = code
    body.update(extra)
    return JSONResponse(body, status_code=status_code)


def _limit_response(error: EmailLimitError) -> JSONResponse:
    extra = {"retry_after": error.retry_after} if error.retry_after else {}
    headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
    response = _fail(429, error.detail, error.code, **extra)
    if headers:
        response.headers.update(headers)
    return response


def _send_failed() -> JSONResponse:
    return _fail(502, SEND_FAILED_MESSAGE, "email_failed")


def client_ip(request: Request) -> str:
    """Cloudflare's header in production (tunnel -> nginx -> Next -> API);
    the socket peer otherwise. Only the HMAC of it is ever stored."""
    forwarded = request.headers.get("cf-connecting-ip")
    if forwarded:
        return forwarded.strip()
    return request.client.host if request.client else "unknown"


async def _group_access(email: Optional[str]) -> bool:
    """Full access for a new session. Login accounts have no e-mail, so the
    allowlist / Google Group cannot apply to them - only PUBLIC_ACCESS."""
    if not email:
        return bool(settings.public_access)
    from ..groups import check_group_membership

    return await check_group_membership(email)


# --------------------------------------------------------------------- age answers


class AgeFields(BaseModel):
    birth_year: Optional[int] = None
    turned_16: Optional[bool] = None


def _age(body: AgeFields) -> tuple[Optional[bool], Optional[JSONResponse]]:
    """(can consent alone, error)."""
    if body.birth_year is None:
        return None, _fail(400, "Wybierz rok urodzenia.", "invalid", field="birth_year")
    try:
        return age.can_consent_alone(body.birth_year, body.turned_16), None
    except age.AgeAnswerError as e:
        if "turned_16" in str(e):
            return None, _fail(400, "Odpowiedz, czy masz już ukończone 16 lat.", "invalid", field="turned_16")
        return None, _fail(400, "Wybierz rok urodzenia z listy.", "invalid", field="birth_year")


def _parent_email(raw: Optional[str], own_email: Optional[str]) -> tuple[str, Optional[JSONResponse]]:
    email = service.normalize_email(raw)
    problem = service.email_problem(email)
    if problem:
        return email, _fail(400, problem, "invalid", field="parent_email")
    # An alias of the child's own Google address (j.a.n+x@gmail.com) is
    # still the child's mailbox: the child would consent for themselves
    if own_email and service.same_mailbox(email, own_email):
        return email, _fail(
            400,
            "To adres Twojego konta. Wpisz adres e-mail rodzica lub opiekuna.",
            "invalid",
            field="parent_email",
        )
    return email, None


# --------------------------------------------------------------------- registration


class GoogleRegistrationRequest(AgeFields):
    parent_email: Optional[str] = None
    accept_terms: Optional[bool] = None
    turnstile_token: Optional[str] = None


class LoginRegistrationRequest(AgeFields):
    login: Optional[str] = None
    password: Optional[str] = None
    parent_email: Optional[str] = None
    turnstile_token: Optional[str] = None


def _ip_limit() -> JSONResponse:
    return _fail(429, IP_LIMIT_MESSAGE, "registration_ip_limit")


async def _human_check(request: Request, token: Optional[str], email: Optional[str] = None) -> Optional[JSONResponse]:
    """The checks every registration request passes once its answers are
    valid, before anything is created or e-mailed: the per-IP limit (checked
    first - it is free) and Turnstile. The IP slot itself is taken only when
    the account is created (take_registration_slot)."""
    if service.registration_ip_limit_reached(service.ip_hash(client_ip(request)), email):
        return _ip_limit()
    if not await turnstile.verify(token):
        return _fail(400, turnstile.FAILED_MESSAGE, "turnstile_failed")
    return None


def _fresh_google(entry: Optional[dict]) -> Optional[dict]:
    if not entry or time.time() - entry.get("at", 0) > PENDING_GOOGLE_SECONDS:
        return None
    return entry


@router.get("/api/auth/register/state")
async def registration_state(request: Request):
    """Whether a Google identity waits for its registration (?google=1)."""
    pending = _fresh_google(request.session.get(SESSION_PENDING_GOOGLE_KEY))
    return {
        "google": {"email": pending["email"]} if pending else None,
        "turnstile_site_key": turnstile.site_key(),
    }


@router.post("/api/auth/register/google")
@allow_inactive_account
async def register_google(
    request: Request, body: GoogleRegistrationRequest, db: Session = Depends(get_db)
):
    """Registration with Google, either before or after the Google redirect.

    Before (no Google identity in the session yet): the answers are stored as
    pending_registration and the client is sent to /login/google?register=1;
    the OAuth callback finishes the job. After (pending_google in the
    session, i.e. the child came back from Google without an account): the
    account is created right here.
    """
    alone, error = _age(body)
    if error:
        return error
    if alone and not body.accept_terms:
        return _fail(400, "Zaznacz zgodę, żeby założyć konto.", "invalid", field="accept_terms")

    pending_google = _fresh_google(request.session.get(SESSION_PENDING_GOOGLE_KEY))
    parent_email = None
    if not alone:
        parent_email, error = _parent_email(
            body.parent_email, pending_google["email"] if pending_google else None
        )
        if error:
            return error

    answers = service.AgeAnswers(
        birth_year=body.birth_year, can_consent_alone=bool(alone), parent_email=parent_email
    )

    # Before the Google redirect too: answers are stored only for a request
    # that passed, and the OAuth callback creates the account from them
    error = await _human_check(
        request, body.turnstile_token, pending_google["email"] if pending_google else None
    )
    if error:
        return error

    if pending_google is None:
        request.session[SESSION_PENDING_REGISTRATION_KEY] = {
            "birth_year": answers.birth_year,
            "can_consent_alone": answers.can_consent_alone,
            "parent_email": answers.parent_email,
            "at": time.time(),
        }
        return {"action": "google", "redirect": "/login/google?register=1"}

    return await finish_google_registration(request, db, pending_google, answers)


async def finish_google_registration(
    request: Request, db: Session, identity: dict, answers: "service.AgeAnswers"
):
    """Create the Google user from verified identity + answers and log in.

    The waiting identity and answers are consumed here, whatever the outcome:
    after a 429 or 409 the child signs in with Google again. On a shared
    computer a lingering identity could end up on another child's account.
    """
    request.session.pop(SESSION_PENDING_GOOGLE_KEY, None)
    request.session.pop(SESSION_PENDING_REGISTRATION_KEY, None)

    existing = db.query(UserDB).filter(UserDB.google_sub == identity["sub"]).first()
    if existing is not None:  # registered meanwhile (second tab) - just log in
        start_session(
            request, existing, remember=True, is_group_member=await _group_access(existing.email),
        )
        return {"action": "done", "redirect": _home_for(existing), "email_sent": None}

    if service.new_users_limit_reached(
        db, identity["email"], needs_parent=answers.parent_email is not None
    ):
        return _fail(429, NEW_USERS_LIMIT_MESSAGE, "new_users_limit")
    if not service.take_registration_slot(service.ip_hash(client_ip(request)), identity["email"]):
        return _ip_limit()

    try:
        user = service.create_google_user(
            db, sub=identity["sub"], email=identity["email"], name=identity.get("name"), answers=answers
        )
    except IntegrityError:
        db.rollback()
        return _fail(409, "To konto Google jest już zarejestrowane. Zaloguj się.", "conflict")

    start_session(
        request, user, remember=True, is_group_member=await _group_access(user.email),
        picture=identity.get("picture"),
    )
    email_sent = None
    if user.status == UserStatus.PENDING_PARENT:
        email_sent = await service.try_send_consent_email(db, user)
    return {"action": "done", "redirect": _home_for(user), "email_sent": email_sent}


def _home_for(user: UserDB) -> str:
    if user.birth_year is None:
        return "/konto/uzupelnij"
    if user.status == UserStatus.PENDING_PARENT:
        return "/konto/oczekuje"
    return "/years"


@router.post("/api/auth/register/login")
@allow_inactive_account
async def register_login(
    request: Request, body: LoginRegistrationRequest, db: Session = Depends(get_db)
):
    """Login + password account. Always needs a parent (the only recovery
    contact), so it starts pending whatever the age."""
    _, error = _age(body)
    if error:
        return error

    login = passwords.normalize_login(body.login)
    problem = passwords.login_problem(login)
    if problem:
        return _fail(400, problem, "invalid", field="login")
    if db.query(UserDB.id).filter(UserDB.login == login).first() is not None:
        return _fail(409, "Ten login jest zajęty. Wymyśl inny.", "login_taken", field="login")

    problem = passwords.password_problem(body.password, login)
    if problem:
        return _fail(400, problem, "invalid", field="password")

    parent_email, error = _parent_email(body.parent_email, None)
    if error:
        return error

    if service.new_users_limit_reached(db, None, needs_parent=True):
        return _fail(429, NEW_USERS_LIMIT_MESSAGE, "new_users_limit")
    error = await _human_check(request, body.turnstile_token)
    if error:
        return error
    # Taken after the await above: check + record with nothing in between
    if not service.take_registration_slot(service.ip_hash(client_ip(request))):
        return _ip_limit()

    try:
        user = service.create_login_user(
            db, login=login, password=body.password, birth_year=body.birth_year,
            parent_email=parent_email,
        )
    except IntegrityError:
        db.rollback()
        return _fail(409, "Ten login jest zajęty. Wymyśl inny.", "login_taken", field="login")

    start_session(request, user, remember=False, is_group_member=await _group_access(None))
    email_sent = await service.try_send_consent_email(db, user)
    return {"redirect": "/konto/oczekuje", "email_sent": email_sent}


# Login availability: rate-limited per client, in memory (single worker)
_AVAILABILITY_WINDOW_SECONDS = 60
_AVAILABILITY_MAX = 30
_availability_hits: dict[str, deque] = defaultdict(deque)


def _availability_allowed(key: str) -> bool:
    now = time.time()
    hits = _availability_hits[key]
    while hits and now - hits[0] > _AVAILABILITY_WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= _AVAILABILITY_MAX:
        return False
    hits.append(now)
    if len(_availability_hits) > 10_000:  # bound memory; one stale key is harmless
        _availability_hits.pop(next(iter(_availability_hits)))
    return True


@router.get("/api/auth/login-available")
async def login_available(request: Request, login: str = "", db: Session = Depends(get_db)):
    """"Ten login jest zajęty" on blur in the registration form."""
    if not _availability_allowed(service.ip_hash(client_ip(request))):
        return _fail(429, "Za dużo sprawdzeń. Poczekaj minutę.", "rate_limited")
    normalized = passwords.normalize_login(login)
    problem = passwords.login_problem(normalized)
    if problem:
        return {"login": normalized, "valid": False, "available": False, "message": problem}
    taken = db.query(UserDB.id).filter(UserDB.login == normalized).first() is not None
    return {
        "login": normalized,
        "valid": True,
        "available": not taken,
        "message": "Ten login jest zajęty. Wymyśl inny." if taken else None,
    }


# --------------------------------------------------------------------- login


class LoginRequest(BaseModel):
    login: Optional[str] = None
    password: Optional[str] = None
    remember: bool = False
    next: Optional[str] = None


@router.post("/api/auth/login")
@allow_inactive_account
async def login_with_password(
    request: Request, response: Response, body: LoginRequest, db: Session = Depends(get_db)
):
    """Login + password. One generic error for unknown login and wrong
    password; the lockout answer is the same for existing and unknown logins.
    See service.LOGIN_* for how failures are counted (per login and device
    or IP, so nobody can lock a child out of their own device)."""
    login = passwords.normalize_login(body.login)[:64]
    password = body.password or ""
    if not login or not password:
        return _fail(400, "Wpisz login i hasło.", "invalid")

    user = db.query(UserDB).filter(UserDB.login == login).first()
    device = service.read_device(request.cookies.get(service.DEVICE_COOKIE))
    actor, known_device = service.login_actor(login, client_ip(request), device, user)
    if service.login_locked(db, login, actor, known_device):
        return _fail(429, LOCKED_MESSAGE, "login_locked")

    ok = passwords.verify_password(user.password_hash if user else None, password[: passwords.PASSWORD_MAX])
    if not ok or user is None:
        service.record_login_failure(db, login, actor)
        logger.info("Failed password login")
        return _fail(401, GENERIC_LOGIN_ERROR, "invalid_credentials")

    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(password)
    service.clear_login_failures(db, login, actor)
    # A sign-in is activity: delete_inactive_accounts counts from updated_at
    user.updated_at = service.now()
    session_version = user.session_version or 0
    db.commit()

    start_session(request, user, remember=body.remember, is_group_member=await _group_access(None))
    # Remember this device for this login (random device id + a tag bound to
    # the current password); its failed attempts are then counted on their own
    response.set_cookie(
        service.DEVICE_COOKIE,
        service.device_cookie_after_login(device, login, session_version),
        max_age=service.DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        secure=not settings.auth_disabled,
        samesite="lax",
    )
    logger.info(f"Password login: user {mask_user_id(user.id)}")
    redirect = _home_for(user)
    if redirect == "/years":
        redirect = safe_next_path(body.next) or redirect
    return {"redirect": redirect}


# --------------------------------------------------------------------- existing accounts: age step


class ProfileRequest(AgeFields):
    parent_email: Optional[str] = None
    accept_terms: Optional[bool] = None


@router.post("/api/auth/profile")
@allow_inactive_account
async def complete_profile(
    body: ProfileRequest,
    db: Session = Depends(get_db),
    account: Optional[UserDB] = Depends(current_account),
):
    """Year of birth for accounts created before the age step existed."""
    if account is None:
        raise HTTPException(status_code=401, detail="Nieautoryzowany dostęp")
    if account.birth_year is not None:
        return _fail(409, "Ten krok jest już za Tobą.", "already_done", redirect=_home_for(account))

    alone, error = _age(body)
    if error:
        return error

    if alone:
        if not body.accept_terms:
            return _fail(400, "Zaznacz zgodę, żeby korzystać z serwisu.", "invalid", field="accept_terms")
        account.birth_year = body.birth_year
        service.record_consent(db, account, "self")
        db.commit()
        return {"redirect": "/years", "email_sent": None}

    parent_email, error = _parent_email(body.parent_email, account.email)
    if error:
        return error
    parent = service.ensure_parent(db, parent_email)  # commits on its own
    account.birth_year = body.birth_year
    service.set_pending(account, parent)
    db.commit()
    email_sent = await service.try_send_consent_email(db, account)
    return {"redirect": "/konto/oczekuje", "email_sent": email_sent}


# --------------------------------------------------------------------- pending screen


def _require_pending(account: Optional[UserDB]) -> Optional[JSONResponse]:
    if account is None:
        return _fail(401, "Nieautoryzowany dostęp")
    if account.status != UserStatus.PENDING_PARENT:
        return _fail(409, "To konto nie czeka na zgodę rodzica.", "not_pending")
    return None


@router.post("/api/account/consent/resend")
@allow_inactive_account
async def resend_consent(
    db: Session = Depends(get_db), account: Optional[UserDB] = Depends(current_account)
):
    error = _require_pending(account)
    if error:
        return error
    try:
        await service.send_consent_email(db, account)
    except EmailLimitError as e:
        return _limit_response(e)
    except EmailSendError:
        return _send_failed()
    return {"sent": True, "account": service.account_summary(db, account)}


class ParentEmailRequest(BaseModel):
    parent_email: Optional[str] = None


@router.post("/api/account/parent-email")
@allow_inactive_account
async def change_parent_email(
    body: ParentEmailRequest,
    db: Session = Depends(get_db),
    account: Optional[UserDB] = Depends(current_account),
):
    """Correct the parent's address while waiting. Same limits as resending;
    old consent links stop working. The 14-day clock is not restarted."""
    error = _require_pending(account)
    if error:
        return error
    parent_email, error = _parent_email(body.parent_email, account.email)
    if error:
        return error

    # (a) the address row, committed on its own (no lock held across the send)
    parent = service.ensure_parent(db, parent_email)
    new_parent_id = parent.id

    def switch_parent() -> None:
        # (d) only once the new e-mail is out, in the short commit that also
        # writes the new link: until then the old address and links stand
        service.invalidate_consent_tokens(db, account)
        account.parent_id = new_parent_id

    # (b, c) the new links exist only in memory until the send succeeds.
    # The previous parent row stays until retention: its e-mail log keeps
    # counting against the limits for 24 h. On failure nothing is pending;
    # at most a childless parent row is left for retention.
    try:
        await service.send_consent_email(db, account, parent, on_sent=switch_parent)
    except EmailLimitError as e:
        return _limit_response(e)
    except EmailSendError:
        return _send_failed()
    db.refresh(account)
    return {"sent": True, "account": service.account_summary(db, account)}


# --------------------------------------------------------------------- parent: consent page


def _child_view(user: UserDB) -> dict:
    label, identifier = service.child_identifier(user)
    return {
        "id": user.id,
        "kind": "login" if user.login else "google",
        "identifier_label": label,
        "identifier": identifier,
        "created_at": service.iso_utc(user.created_at),
        "status": user.status,
        "pending_deadline": service.iso_utc(service.pending_deadline(user)),
    }


def _processing_summary() -> dict:
    from ..email.templates import months_pl

    return {
        "submission_retention": months_pl(settings.retention_submission_months or 24),
        "inactive_retention": months_pl(settings.retention_inactive_account_months or 36),
        "pending_days": service.PENDING_TTL.days,
    }


def _consent_lookup(db: Session, raw: Optional[str]):
    """(state, token, user); a token whose account changed parent or is no
    longer pending is not usable."""
    token = service.find_token(db, raw, EmailTokenPurpose.CONSENT)
    state = service.token_state(token)
    user = db.get(UserDB, token.user_id) if token is not None and token.user_id else None
    if token is not None and user is None:
        state = "invalid"
    elif user is not None and state == "valid":
        if user.status != UserStatus.PENDING_PARENT:
            state = "used"
        elif user.parent_id != token.parent_id:
            state = "expired"
    return state, token, user


class TokenRequest(BaseModel):
    token: Optional[str] = None


# Tokens travel in POST bodies only, never in an API query string: query
# strings end up in proxy access logs. These lookups change nothing.


@router.post("/api/parent/consent/view")
@allow_inactive_account
async def parent_consent_view(body: TokenRequest, db: Session = Depends(get_db)):
    """What the consent page shows. Never changes anything."""
    state, token, user = _consent_lookup(db, body.token)
    can_resend = (
        state == "expired"
        and user is not None
        and user.status == UserStatus.PENDING_PARENT
        and user.parent_id == token.parent_id
    )
    return {
        "state": state,
        "child": _child_view(user) if user is not None and state != "invalid" else None,
        "can_resend": can_resend,
        "summary": _processing_summary(),
    }


class ConsentDecisionRequest(BaseModel):
    token: Optional[str] = None
    decision: Optional[str] = None  # "accept" | "decline"


@router.post("/api/parent/consent")
@allow_inactive_account
async def parent_consent_decide(body: ConsentDecisionRequest, db: Session = Depends(get_db)):
    if body.decision not in ("accept", "decline"):
        return _fail(400, "Wybierz jedną z odpowiedzi.", "invalid")
    state, token, user = _consent_lookup(db, body.token)
    if state != "valid":
        message = {"used": LINK_USED, "expired": LINK_EXPIRED}.get(state, LINK_INVALID)
        return _fail(410, message, f"link_{state}", state=state)

    if body.decision == "decline":
        record_erasure_quota(db, user.id)
        erase_user_data(db, user.id)
        logger.info(f"Parent declined consent; account {mask_user_id(user.id)} erased")
        return {"result": "declined"}

    manage_raw = service.activate_by_parent(db, user, token)
    db.refresh(user)
    await service.send_account_active_email(db, user, manage_raw)
    return {"result": "accepted", "manage_url": f"/rodzic?t={manage_raw}", "child": _child_view(user)}


@router.post("/api/parent/consent/resend")
@allow_inactive_account
async def parent_consent_resend(body: TokenRequest, db: Session = Depends(get_db)):
    """"Wyślij nowy link" on the expired-link page."""
    state, token, user = _consent_lookup(db, body.token)
    if state != "expired" or user is None or user.parent_id != token.parent_id:
        return _fail(410, LINK_INVALID, "link_invalid", state=state)
    try:
        await service.send_consent_email(db, user)
    except EmailLimitError as e:
        return _limit_response(e)
    except EmailSendError:
        return _send_failed()
    return {"sent": True}


# --------------------------------------------------------------------- parent page


def _manage_parent(db: Session, raw: Optional[str]) -> tuple[Optional[ParentDB], Optional[JSONResponse]]:
    state, parent = service.manage_token_parent(db, raw)
    if state == "expired":
        return None, _fail(410, LINK_EXPIRED, "link_expired", state="expired")
    if parent is None:
        return None, _fail(404, LINK_INVALID, "link_invalid", state="invalid")
    return parent, None


@router.post("/api/parent/children")
@allow_inactive_account
async def parent_children(body: TokenRequest, db: Session = Depends(get_db)):
    """The parent page: children of this parent address. Changes nothing."""
    parent, error = _manage_parent(db, body.token)
    if error:
        return error
    children = sorted(parent.children, key=lambda u: u.created_at)
    return {
        "parent_email": mask_email_for_display(parent.email),
        "children": [_child_view(child) for child in children],
    }


def _owned_child(parent: ParentDB, child_id: str) -> Optional[UserDB]:
    return next((child for child in parent.children if child.id == child_id), None)


@router.post("/api/parent/children/{child_id}/delete")
@allow_inactive_account
async def parent_delete_child(child_id: str, body: TokenRequest, db: Session = Depends(get_db)):
    """"Usuń konto i wszystkie dane" - also the withdrawal of consent."""
    parent, error = _manage_parent(db, body.token)
    if error:
        return error
    child = _owned_child(parent, child_id)
    if child is None:
        return _fail(404, "Nie znaleziono tego konta.", "not_found")
    remaining = len(parent.children) - 1
    record_erasure_quota(db, child.id)
    report = erase_user_data(db, child.id)
    logger.info(f"Parent erased account {mask_user_id(child_id)}")
    return {"deleted": True, "remaining": remaining, "deleted_submissions": report.submissions_deleted}


class ParentPasswordRequest(BaseModel):
    token: Optional[str] = None
    password: Optional[str] = None


@router.post("/api/parent/children/{child_id}/password")
@allow_inactive_account
async def parent_set_password(child_id: str, body: ParentPasswordRequest, db: Session = Depends(get_db)):
    parent, error = _manage_parent(db, body.token)
    if error:
        return error
    child = _owned_child(parent, child_id)
    if child is None or not child.login:
        return _fail(404, "Nie znaleziono tego konta.", "not_found")
    problem = passwords.password_problem(body.password, child.login)
    if problem:
        return _fail(400, problem, "invalid", field="password")
    service.set_password(db, child, body.password)
    db.commit()
    return {"ok": True}


class ParentLinkRequest(BaseModel):
    email: Optional[str] = None


@contextlib.contextmanager
def _background_session():
    """A session of its own for work done after the response is sent (the
    request's session is closed by then). Tests substitute theirs."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def _send_manage_link_if_parent(email: str) -> None:
    with _background_session() as db:
        parent = db.query(ParentDB).filter(ParentDB.email == email).first()
        if parent is None or not parent.children:
            return
        try:
            await service.send_manage_link(db, parent)
        except (EmailLimitError, EmailSendError):
            logger.info("Parent link not sent (limit or provider failure)")
        except Exception:
            logger.exception("Parent link not sent (unexpected error)")


@router.post("/api/parent/request-link")
@allow_inactive_account
async def parent_request_link(body: ParentLinkRequest, background: BackgroundTasks):
    """Always the same answer, so the page reveals nothing about who has an
    account. The lookup and the send run after the response, so neither does
    its timing (the provider is awaited only for a known address)."""
    email = service.normalize_email(body.email)
    problem = service.email_problem(email)
    if problem:
        return _fail(400, problem, "invalid", field="email")
    background.add_task(_send_manage_link_if_parent, email)
    return {"sent": True}


# --------------------------------------------------------------------- password reset


class ResetRequest(BaseModel):
    login: Optional[str] = None


async def _send_password_reset_if_known(login: str) -> None:
    with _background_session() as db:
        user = db.query(UserDB).filter(UserDB.login == login).first()
        if user is None or user.parent is None:
            return
        try:
            await service.send_password_reset(db, user)
        except (EmailLimitError, EmailSendError):
            logger.info("Password reset not sent (limit or provider failure)")
        except Exception:
            logger.exception("Password reset not sent (unexpected error)")


@router.post("/api/auth/password-reset/request")
@allow_inactive_account
async def password_reset_request(body: ResetRequest, background: BackgroundTasks):
    """Always the same answer; the link goes to the parent, never to the child.

    The lookup and the send run after the response: an answer that waited
    for the e-mail provider (or failed with it) would tell whoever asks that
    the login exists. A provider failure is therefore only logged."""
    login = passwords.normalize_login(body.login)
    if not login:
        return _fail(400, "Wpisz swój login.", "invalid", field="login")
    if len(login) <= passwords.LOGIN_MAX:
        background.add_task(_send_password_reset_if_known, login)
    return {"sent": True}


def _reset_lookup(db: Session, raw: Optional[str]):
    token = service.find_token(db, raw, EmailTokenPurpose.PASSWORD_RESET)
    state = service.token_state(token)
    user = db.get(UserDB, token.user_id) if token is not None and token.user_id else None
    if token is not None and user is None:
        state = "invalid"
    return state, token, user


@router.post("/api/auth/password-reset/check")
@allow_inactive_account
async def password_reset_check(body: TokenRequest, db: Session = Depends(get_db)):
    """Is a reset link still good (and for which login). Changes nothing."""
    state, _, user = _reset_lookup(db, body.token)
    return {"state": state, "login": user.login if user is not None and state == "valid" else None}


class ResetConfirmRequest(BaseModel):
    token: Optional[str] = None
    password: Optional[str] = None


@router.post("/api/auth/password-reset/confirm")
@allow_inactive_account
async def password_reset_confirm(body: ResetConfirmRequest, db: Session = Depends(get_db)):
    """Set the new password. Never logs anyone in (the parent is likely on
    their own phone); every session of the account ends."""
    state, token, user = _reset_lookup(db, body.token)
    if state != "valid":
        message = {"used": LINK_USED, "expired": LINK_EXPIRED}.get(state, LINK_INVALID)
        return _fail(410, message, f"link_{state}", state=state)
    problem = passwords.password_problem(body.password, user.login)
    if problem:
        return _fail(400, problem, "invalid", field="password")
    service.set_password(db, user, body.password)
    token.used_at = service.now()
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------- dev outbox


def outbox_enabled() -> bool:
    """Only the e2e stack: console backend, real auth, E2E_MODE."""
    return (
        (settings.email_backend or "").strip().lower() == "console"
        and not settings.auth_disabled
        and settings.e2e_mode
    )


@router.get("/api/dev/outbox")
async def dev_outbox():
    if not outbox_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    return {"messages": outbox()}
