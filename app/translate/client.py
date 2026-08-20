"""Google Cloud Translation client for status messages.

Uses Google Cloud Translation API v2 (Basic) with API key to translate
short status messages from English to Polish during submission processing.

Uses direct HTTP calls to the REST API for simplicity and explicit API key handling.
"""

import asyncio
import logging
import threading
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

# Google Cloud Translation v2 REST endpoint
GOOGLE_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"


class TranslationError(Exception):
    """Raised when translation fails."""

    pass


# Initialization state (protected by lock for thread safety)
_initialized = False
_enabled = False
_init_lock = threading.Lock()


def _ensure_initialized() -> bool:
    """
    Initialize translation settings (lazy, thread-safe).

    Returns:
        True if translation is enabled and configured, False otherwise.
    """
    global _initialized, _enabled

    if _initialized:
        return _enabled

    with _init_lock:
        if _initialized:
            return _enabled

        if not settings.translate_enabled:
            logger.debug("Translation disabled via config")
            _initialized = True
            _enabled = False
            return False

        # For custom endpoint (e2e testing), no API key needed
        if settings.translate_api_endpoint:
            logger.info(
                f"Translation using fake server at: {settings.translate_api_endpoint}"
            )
            _initialized = True
            _enabled = True
            return True

        # Production: need API key
        if not settings.translate_api_key:
            logger.warning(
                "Translation enabled but TRANSLATE_API_KEY not set, disabling translation"
            )
            _initialized = True
            _enabled = False
            return False

        logger.info("Translation client initialized (Google Cloud v2 REST)")
        _initialized = True
        _enabled = True
        return True


def _translate_sync(text: str) -> str:
    """
    Synchronous translation via REST API.

    Args:
        text: English text to translate

    Returns:
        Translated Polish text

    Raises:
        TranslationError: If translation fails
    """
    if not text or not text.strip():
        return text

    if not _ensure_initialized():
        raise TranslationError("Translation not available")

    # Determine endpoint
    if settings.translate_api_endpoint:
        # E2E testing: use fake server
        url = f"http://{settings.translate_api_endpoint}/language/translate/v2"
        params = {}
    else:
        # Production: use Google Cloud with API key
        url = GOOGLE_TRANSLATE_URL
        params = {"key": settings.translate_api_key}

    try:
        response = httpx.post(
            url,
            params=params,
            json={
                "q": text,
                "source": "en",
                "target": "pl",
                "format": "text",
            },
            timeout=settings.translate_timeout,
        )
        response.raise_for_status()
        data = response.json()

        # v2 response format: {"data": {"translations": [{"translatedText": "..."}]}}
        translations = data.get("data", {}).get("translations", [])
        if translations:
            translated = translations[0]["translatedText"]
            logger.debug(f"Translated: '{text}' -> '{translated}'")
            return translated
        else:
            raise TranslationError("Empty translation response")

    except httpx.TimeoutException:
        raise TranslationError(f"Translation timeout ({settings.translate_timeout}s)")
    except httpx.HTTPStatusError as e:
        raise TranslationError(f"Translation API error: {e.response.status_code}")
    except Exception as e:
        raise TranslationError(f"Translation error: {e}")


async def translate_to_polish_optional(text: str) -> Optional[str]:
    """Translate English text to Polish, or return None if that did not happen.

    Callers that must never show English text need to tell "the translation is
    the same string" apart from "no translation happened". Comparing the result
    to the input cannot do that: a one-word heading or a proper noun can
    legitimately translate to itself, and treating that as a failure silently
    throws away a perfectly good status.

    Returns None when translation is disabled, when the text is empty, and on
    any timeout or error. Never raises.
    """
    if not text or not text.strip():
        return None

    if not settings.translate_enabled:
        return None

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_translate_sync, text),
            timeout=settings.translate_timeout,
        )

    except asyncio.TimeoutError:
        logger.warning(
            f"Translation timeout ({settings.translate_timeout}s) for: '{text[:50]}...'"
        )
        return None

    except TranslationError as e:
        logger.warning(f"Translation failed: {e}, using original text")
        return None

    except Exception as e:
        logger.warning(f"Unexpected translation error: {e}, using original text")
        return None


async def translate_to_polish(text: str) -> str:
    """
    Translate English text to Polish asynchronously.

    Features:
    - Runs HTTP request in thread pool (non-blocking)
    - Enforces timeout to prevent slow translations blocking submissions
    - Falls back to original text on any error

    Args:
        text: English text to translate

    Returns:
        Translated Polish text, or original text on any error/timeout
    """
    translated = await translate_to_polish_optional(text)
    return translated if translated else text
