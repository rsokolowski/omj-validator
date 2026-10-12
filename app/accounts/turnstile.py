"""Cloudflare Turnstile: server-side check of the token from the widget on the
registration page (the steps that create an account or e-mail a parent).

Disabled while TURNSTILE_SECRET_KEY is unset (local dev, e2e). Fails closed:
when Cloudflare cannot be reached the registration is refused and the child
tries again. Nothing about the child is sent - only the secret and the token
(no remoteip, it is optional).

Cloudflare's test keys (developers.cloudflare.com/turnstile/troubleshooting/testing/)
work end to end: site key TEST_SITE_KEY renders a widget that always passes,
and secret TEST_SECRET_PASS / TEST_SECRET_FAIL accept / reject any token.
"""

import logging
from typing import Optional
from urllib.parse import urlsplit

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TIMEOUT_SECONDS = 5.0
# Turnstile tokens are at most 2048 characters
TOKEN_MAX = 2048
# The widget's action (data-action), checked together with the hostname the
# widget was solved on (PUBLIC_BASE_URL). Cloudflare's test keys report
# neither (metadata.result_with_testing_key), so those checks are skipped
# only for test-key results.
ACTION = "register"

TEST_SITE_KEY = "1x00000000000000000000AA"
TEST_SECRET_PASS = "1x0000000000000000000000000000000AA"
TEST_SECRET_FAIL = "2x0000000000000000000000000000000AA"

FAILED_MESSAGE = (
    "Nie udało się potwierdzić, że nie jesteś robotem. Zaznacz pole w ramce jeszcze raz "
    "i spróbuj ponownie."
)

# Tests substitute an httpx.MockTransport here
_transport: Optional[httpx.AsyncBaseTransport] = None


def enabled() -> bool:
    return bool(settings.turnstile_secret_key)


def site_key() -> Optional[str]:
    """What the registration page renders the widget with (None = no widget)."""
    return (settings.turnstile_site_key or None) if enabled() else None


async def verify(token: Optional[str]) -> bool:
    """True when Turnstile is disabled or Cloudflare accepts the token.

    Each token is single-use: a second check of the same token fails.
    """
    if not enabled():
        return True
    if not token or len(token) > TOKEN_MAX:
        return False
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=_transport) as client:
            response = await client.post(
                SITEVERIFY_URL,
                data={"secret": settings.turnstile_secret_key, "response": token},
            )
            result = response.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning(f"Turnstile siteverify failed: {type(e).__name__}")
        return False
    if not isinstance(result, dict) or result.get("success") is not True:
        codes = result.get("error-codes") if isinstance(result, dict) else None
        logger.info(f"Turnstile token rejected: {codes}")
        return False
    metadata = result.get("metadata")
    if isinstance(metadata, dict) and metadata.get("result_with_testing_key") is True:
        return True
    if result.get("action") != ACTION:
        logger.info(f"Turnstile token for another action: {result.get('action')!r}")
        return False
    expected_host = (urlsplit(settings.public_base_url).hostname or "").lower()
    if (result.get("hostname") or "").lower() != expected_host:
        logger.info(f"Turnstile token solved on another hostname: {result.get('hostname')!r}")
        return False
    return True


if settings.turnstile_secret_key and not settings.turnstile_site_key:
    logger.error(
        "TURNSTILE_SECRET_KEY is set but TURNSTILE_SITE_KEY is not: "
        "the registration page cannot show the widget, so every registration will fail"
    )
