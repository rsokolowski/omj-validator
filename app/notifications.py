"""Telegram notifications for submission lifecycle events.

Fire-and-forget notifier: sends plain-text messages to a Telegram chat via the
bot configured in settings. Every failure is swallowed and logged as a warning
so a Telegram outage can never affect submission processing.

PRIVACY / RODO - DO NOT ADD USER IDENTITY BACK IN.
Notifications leave our infrastructure and land in a Telegram chat hosted by
Telegram FZ-LLC (a third country, no data processing agreement in place). Our
users are children aged 10-15, so any name, e-mail or raw user id sent here
would be an undocumented transfer of a minor's personal data to another
processor. Messages therefore carry only operational data: submission id, task,
score, image count and error reason. An admin who needs to know *who* submitted
looks the submission up by its id in the admin panel, where access is
authenticated and logged.

If distinguishing users in the chat is operationally useful, set
TELEGRAM_PSEUDONYM_SALT and a short, irreversible HMAC pseudonym is added. It is
off by default - prefer no identity at all.
"""

import hashlib
import hmac
import logging

import httpx

from .config import settings
from .scoring import get_max_score

logger = logging.getLogger(__name__)

# Telegram Bot API base
TELEGRAM_API_URL = "https://api.telegram.org"

# Length of the hex pseudonym. 8 hex chars = 32 bits: enough to tell a handful
# of concurrent users apart in a chat, useless as an identifier on its own.
PSEUDONYM_LENGTH = 8


def build_user_pseudonym(user_id: str) -> str:
    """Return a short, irreversible pseudonym for a user, or "" when disabled.

    Uses HMAC-SHA256 with a secret salt so the digest cannot be reversed by
    hashing candidate user ids. Returns an empty string (no pseudonym in the
    message at all) unless TELEGRAM_PSEUDONYM_SALT is configured - see the
    module docstring for why the default is "no identity".
    """
    salt = settings.telegram_pseudonym_salt
    if not salt or not user_id:
        return ""
    digest = hmac.new(salt.encode("utf-8"), user_id.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:PSEUDONYM_LENGTH]


def _pseudonym_line(user_id: str) -> str:
    """Optional "User: <pseudonym>" line, empty when pseudonyms are disabled."""
    pseudonym = build_user_pseudonym(user_id)
    return f"User: #{pseudonym}\n" if pseudonym else ""


def build_start_message(
    submission_id: str,
    user_id: str,
    year: str,
    etap: str,
    task_number: int,
    image_count: int,
    text_chars: int = 0,
) -> str:
    """Build the notification text for a submission that started processing."""
    return (
        f"📥 New submission {submission_id}\n"
        f"{_pseudonym_line(user_id)}"
        f"Task: {year}/{etap}/zad {task_number}\n"
        f"Images: {image_count}, text: {text_chars} chars"
    )


def build_completed_message(
    submission_id: str,
    user_id: str,
    year: str,
    etap: str,
    task_number: int,
    score: int,
) -> str:
    """Build the notification text for a completed submission."""
    max_score = get_max_score(etap)
    return (
        f"✅ Submission {submission_id} scored {score}/{max_score}\n"
        f"{_pseudonym_line(user_id)}"
        f"Task: {year}/{etap}/zad {task_number}"
    )


def error_category(error: BaseException) -> str:
    """A short fixed label for an error: class + category, never its text.

    Error messages can quote the model's output or the student's work (an
    SDK error body, a parse failure), so only these labels leave the server.
    """
    from .ai.factory import AIContentBlockedError, AIProviderError, AISpendLimitError, AIUnavailableError

    if isinstance(error, AIUnavailableError):
        category = f"unavailable:{error.kind}"
        if error.status:
            category += f" {error.status}"
    elif isinstance(error, AIContentBlockedError):
        category = "content_blocked"
    elif isinstance(error, AISpendLimitError):
        category = "spend_limit"
    elif isinstance(error, AIProviderError):
        category = "provider_error"
    else:
        category = "unexpected"
    return f"{type(error).__name__} ({category})"


def build_failed_message(
    submission_id: str,
    user_id: str,
    year: str,
    etap: str,
    task_number: int,
    error: BaseException,
) -> str:
    """Build the notification text for a failed submission (error class/category only)."""
    return (
        f"❌ Submission {submission_id} FAILED\n"
        f"{_pseudonym_line(user_id)}"
        f"Task: {year}/{etap}/zad {task_number}\n"
        f"Error: {error_category(error)}"
    )


def build_failover_message(
    primary: str, fallback: str, error: BaseException, breaker_open_minutes: int
) -> str:
    """AI failover activated: which provider failed (error class only) and where calls go now."""
    route = (
        f"All AI calls go to {fallback} for {breaker_open_minutes} min."
        if breaker_open_minutes
        else f"This call went to {fallback}."
    )
    return f"⚠️ AI failover: {primary} unavailable - {error_category(error)}\n{route}"


def build_spend_message(level_percent: int, spent_usd: float, limit_usd: float) -> str:
    """Daily AI spend crossed 80% / 100% of AI_DAILY_SPEND_LIMIT_USD."""
    if level_percent >= 100:
        head = "🛑 AI spend limit reached - new AI calls are refused"
    else:
        head = f"💸 AI spend at {level_percent}% of the daily limit"
    return f"{head}\nLast 24 h: ${spent_usd:.2f} of ${limit_usd:.2f}"


_background_sends: set = set()


def send_telegram_in_background(text: str) -> None:
    """Fire-and-forget send from sync code running on the event loop.

    No running loop (a script): nothing is sent - callers log the event too.
    The task is kept referenced until it finishes so it is not GC'd mid-send.
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(send_telegram_message(text))
    _background_sends.add(task)
    task.add_done_callback(_background_sends.discard)


async def send_telegram_message(text: str) -> None:
    """Send a plain-text message to the configured Telegram chat.

    No-op (debug log) when the bot token or chat id is unset. Every exception is
    caught and logged as a warning; this function never raises. The bot token is
    never included in log output (httpx error strings can contain the request
    URL, so we log only the exception type and response status/body snippet).
    """
    # Treat empty-string env values as unset (feature disabled)
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.debug("Telegram notifications disabled (token or chat_id not set)")
        return

    url = f"{TELEGRAM_API_URL}/bot{settings.telegram_bot_token}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": text,
                },
            )
            response.raise_for_status()
        logger.debug("Telegram notification sent")

    except httpx.HTTPStatusError as e:
        # Log status + short body snippet, never the URL (contains bot token)
        body_snippet = e.response.text[:200] if e.response is not None else ""
        logger.warning(
            f"Telegram notification failed: HTTP {e.response.status_code} - {body_snippet}"
        )

    except Exception as e:
        # str(e) may contain the request URL with the bot token - redact it
        detail = str(e).replace(settings.telegram_bot_token, "***")
        logger.warning(f"Telegram notification failed: {type(e).__name__}: {detail}")
