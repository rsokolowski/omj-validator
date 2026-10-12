"""Telegram notifications: an anonymous submission digest and operational alerts.

Fire-and-forget notifier: sends plain-text messages to a Telegram chat via the
bot configured in settings. Every failure is swallowed and logged as a warning
so a Telegram outage can never affect submission processing.

PRIVACY / RODO - NOTHING THAT POINTS AT ONE SUBMISSION OR ONE CHILD.
The chat is hosted by Telegram FZ-LLC (outside the EEA, no data processing
agreement). Our users are children, so nothing sent there may be personal data
- not even pseudonymous: a submission id, a task and a score, or a message sent
the moment one student submits, can be matched back to a row in our database.
Submissions are therefore reported only as counts per DIGEST window (how many
started, were graded, failed - and failure categories), sent at the end of the
window. Operational alerts (AI failover, spend limit) carry no user data at all.
Whoever needs details looks them up in the admin panel, where access is
authenticated and logged.
"""

import asyncio
import logging
from collections import Counter

import httpx

from .config import settings

logger = logging.getLogger(__name__)

# Telegram Bot API base
TELEGRAM_API_URL = "https://api.telegram.org"

# One digest per window, and only when something happened in it
DIGEST_MINUTES = 15

_digest: Counter = Counter()
_failures: Counter = Counter()


def record_started() -> None:
    _digest["started"] += 1


def record_completed() -> None:
    _digest["completed"] += 1


def record_failed(error: BaseException) -> None:
    _digest["failed"] += 1
    _failures[error_category(error)] += 1


def take_digest_message() -> str | None:
    """The counts since the last call as a message (None if nothing happened); resets them."""
    if not _digest:
        return None
    started, completed, failed = _digest["started"], _digest["completed"], _digest["failed"]
    lines = [
        f"📊 Last {DIGEST_MINUTES} min: {started} started, {completed} graded, {failed} failed"
    ]
    lines += [f"  {count}× {category}" for category, count in _failures.most_common()]
    _digest.clear()
    _failures.clear()
    return "\n".join(lines)


async def digest_loop() -> None:
    """Send the submission digest every DIGEST_MINUTES (started at app startup)."""
    while True:
        await asyncio.sleep(DIGEST_MINUTES * 60)
        message = take_digest_message()
        if message:
            await send_telegram_message(message)


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
