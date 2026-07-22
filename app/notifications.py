"""Telegram notifications for submission lifecycle events.

Fire-and-forget notifier: sends plain-text messages to a Telegram chat via the
bot configured in settings. Every failure is swallowed and logged as a warning
so a Telegram outage can never affect submission processing.
"""

import logging

import httpx

from .config import settings
from .scoring import get_max_score

logger = logging.getLogger(__name__)

# Telegram Bot API base
TELEGRAM_API_URL = "https://api.telegram.org"


def build_start_message(
    submission_id: str,
    user_display: str,
    year: str,
    etap: str,
    task_number: int,
    image_count: int,
) -> str:
    """Build the notification text for a submission that started processing."""
    return (
        f"📥 New submission {submission_id}\n"
        f"User: {user_display}\n"
        f"Task: {year}/{etap}/zad {task_number}\n"
        f"Images: {image_count}"
    )


def build_completed_message(
    submission_id: str,
    user_display: str,
    year: str,
    etap: str,
    task_number: int,
    score: int,
) -> str:
    """Build the notification text for a completed submission."""
    max_score = get_max_score(etap)
    return (
        f"✅ Submission {submission_id} scored {score}/{max_score}\n"
        f"User: {user_display}\n"
        f"Task: {year}/{etap}/zad {task_number}"
    )


def build_failed_message(
    submission_id: str,
    user_display: str,
    year: str,
    etap: str,
    task_number: int,
    error_msg: str,
) -> str:
    """Build the notification text for a failed submission."""
    # Telegram rejects messages over 4096 chars; keep the error short so the
    # failure notification always goes through
    if len(error_msg) > 500:
        error_msg = error_msg[:500] + "…"
    return (
        f"❌ Submission {submission_id} FAILED\n"
        f"User: {user_display}\n"
        f"Task: {year}/{etap}/zad {task_number}\n"
        f"Error: {error_msg}"
    )


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
