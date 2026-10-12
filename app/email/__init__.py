"""Transactional e-mail: parent consent, password reset, parent links.

``send_email(to, subject, html, text)`` with two backends (EMAIL_BACKEND):

* ``console`` (default): logs the subject, the masked recipient and the links,
  and keeps the last 50 messages in memory. ``GET /api/dev/outbox`` returns
  them, but only in e2e mode (see app/accounts/routes.py).
* ``resend``: ``POST https://api.resend.com/emails`` with httpx, 10 s timeout.

A failure raises EmailSendError; callers show "Nie udało się wysłać
wiadomości. Spróbuj za chwilę." and must not count it against any limit.
Message bodies and full addresses are never logged - they carry tokens and
a child's or parent's e-mail address.
"""

import logging
import re
import time
from collections import deque
from typing import Optional

import httpx

from ..config import settings
from ..privacy import mask_email

logger = logging.getLogger(__name__)

OUTBOX_SIZE = 50
RESEND_TIMEOUT_SECONDS = 10.0

_outbox: deque = deque(maxlen=OUTBOX_SIZE)
_LINK_RE = re.compile(r"https?://[^\s<>\"']+")


class EmailSendError(Exception):
    """The message was not accepted by the e-mail provider."""


def outbox() -> list[dict]:
    """Messages "sent" by the console backend, newest last."""
    return list(_outbox)


def clear_outbox() -> None:
    _outbox.clear()


def _links(text: str) -> list[str]:
    return _LINK_RE.findall(text or "")


async def send_email(to: str, subject: str, html: str, text: str) -> None:
    """Send one message or raise EmailSendError."""
    backend = (settings.email_backend or "console").strip().lower()
    if backend == "resend":
        await _send_resend(to, subject, html, text)
        return
    if backend != "console":
        logger.error(f"Unknown EMAIL_BACKEND {backend!r}; message not sent")
        raise EmailSendError("unknown backend")

    links = _links(text)
    _outbox.append(
        {
            "to": to,
            "subject": subject,
            "html": html,
            "text": text,
            "links": links,
            "sent_at": time.time(),
        }
    )
    # Links carry single-use tokens; this backend only runs in dev and e2e
    logger.info(f"E-mail (console) to {mask_email(to)}: {subject} | links: {' '.join(links)}")


async def _send_resend(to: str, subject: str, html: str, text: str) -> None:
    if not settings.resend_api_key:
        logger.error("EMAIL_BACKEND=resend but RESEND_API_KEY is not set")
        raise EmailSendError("not configured")

    payload: dict = {
        "from": settings.email_from,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    if settings.email_reply_to:
        payload["reply_to"] = settings.email_reply_to

    try:
        async with httpx.AsyncClient(timeout=RESEND_TIMEOUT_SECONDS) as client:
            response = await client.post(
                settings.resend_api_url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            )
    except httpx.HTTPError as e:
        logger.warning(f"E-mail to {mask_email(to)} failed: {type(e).__name__}")
        raise EmailSendError("transport") from e

    if response.status_code >= 300:
        logger.warning(f"E-mail to {mask_email(to)} rejected by Resend: HTTP {response.status_code}")
        raise EmailSendError(f"http {response.status_code}")

    message_id: Optional[str] = None
    try:
        message_id = response.json().get("id")
    except ValueError:
        pass
    logger.info(f"E-mail sent to {mask_email(to)}: {subject} (id {message_id})")
