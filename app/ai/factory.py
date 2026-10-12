"""Factory for creating AI providers based on the active model."""

import logging
import threading
from typing import TYPE_CHECKING, Optional

from .config_store import ActiveModel, env_default, get_active_model
from .models_catalog import provider_approved, provider_configured

if TYPE_CHECKING:
    from .protocol import AIProvider

logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    """Raised when AI provider cannot be created."""

    pass


class AIContentBlockedError(AIProviderError):
    """The model's safety filter refused the input.

    Distinct from a timeout or an outage: for student-supplied text (private
    tasks) a block means the text must not be saved unchecked. Never a reason
    to fail over - a second provider must not become a way around the first
    one's safety filter.
    """


# Kinds of AIUnavailableError. "auth" and "not_found" look permanent (revoked
# key, retired model) and open the failover breaker at once.
UNAVAILABLE_AUTH = "auth"            # 401/403, invalid/suspended key, billing
UNAVAILABLE_NOT_FOUND = "not_found"  # 404 model
UNAVAILABLE_RATE_LIMIT = "rate_limit"  # 429 / quota
UNAVAILABLE_SERVER = "server"        # 5xx / overloaded
UNAVAILABLE_NETWORK = "network"      # connection errors
UNAVAILABLE_TIMEOUT = "timeout"
PERMANENT_KINDS = frozenset({UNAVAILABLE_AUTH, UNAVAILABLE_NOT_FOUND})


class AIUnavailableError(AIProviderError):
    """The provider could not serve the request at all (availability, not content).

    The only error that may trigger a failover to the backup provider. The
    message is the Polish text for the student; ``kind``/``status``/
    ``error_class`` describe the cause without any response content.
    """

    def __init__(
        self,
        message: str,
        *,
        kind: str,
        status: Optional[int] = None,
        error_class: str = "",
    ):
        super().__init__(message)
        self.kind = kind
        self.status = status
        self.error_class = error_class

    @property
    def permanent(self) -> bool:
        return self.kind in PERMANENT_KINDS


class AISpendLimitError(AIProviderError):
    """The daily AI spend cap (AI_DAILY_SPEND_LIMIT_USD) is reached."""


# One instance per (provider, model): client construction costs ~1.3s
_instances: dict[tuple[str, str], "AIProvider"] = {}
_instances_lock = threading.Lock()

# (provider, model, reason) already logged as unusable - logged once per process,
# not on every grading call while the stored row stays unusable.
_logged_fallbacks: set[tuple[str, str, str]] = set()


def reset_provider_cache() -> None:
    with _instances_lock:
        _instances.clear()
        _logged_fallbacks.clear()


def _construct(provider: str, model: str) -> "AIProvider":
    if provider == "gemini":
        from .providers.gemini import GeminiProvider
        return GeminiProvider(model)
    if provider == "anthropic":
        from .providers.anthropic import AnthropicProvider
        return AnthropicProvider(model)
    raise AIProviderError(f"Unknown AI provider: {provider}. Supported providers: gemini, anthropic")


def build_provider(provider: str, model: str) -> "AIProvider":
    """A fresh, uncached provider for (provider, model). Used by ping and scripts."""
    if provider not in ("gemini", "anthropic"):
        raise AIProviderError(f"Unknown AI provider: {provider}. Supported providers: gemini, anthropic")
    if not provider_configured(provider):
        raise AIProviderError(
            f"{provider.upper()}_API_KEY is required for provider {provider}. Set it in your .env file."
        )
    return _construct(provider, model)


def remember(provider: str, model: str, instance: "AIProvider") -> None:
    """Seed the cache with an instance already built (and pinged) by the admin switch,
    so the first real call does not construct a client on the event loop."""
    with _instances_lock:
        _instances.setdefault((provider, model), instance)


# Polish, shown on /admin/settings; also the log key for "log once".
REASON_NO_KEY = "brak klucza API"
REASON_NOT_APPROVED = "dostawca niezatwierdzony (RODO)"

def _unusable_reason(provider: str) -> Optional[str]:
    if not provider_configured(provider):
        return REASON_NO_KEY
    if not provider_approved(provider):
        return REASON_NOT_APPROVED
    return None


def resolve_active(active: Optional[ActiveModel] = None) -> tuple[ActiveModel, Optional[str]]:
    """The model AI calls actually use, and why it differs from the stored one (or None).

    Single source of truth for create_ai_provider and GET /api/admin/ai-config, so
    the admin page never shows a model other than the one grading. A stored
    choice that cannot be used (no key, or Anthropic not yet approved as a
    processor) falls back to the environment default rather than stopping
    grading - or sending data to an unapproved processor.

    ``active`` = an already-read stored choice (default: get_active_model()).
    """
    if active is None:
        active = get_active_model()
    if active.source == "env":
        return active, None
    reason = _unusable_reason(active.provider)
    if reason is None:
        return active, None
    key = (active.provider, active.model, reason)
    with _instances_lock:
        first = key not in _logged_fallbacks
        _logged_fallbacks.add(key)
    if first:
        logger.error(f"[AI] Active model {active.provider}/{active.model} is not usable ({reason}) - using env default")
    return env_default(), reason


def create_ai_provider() -> "AIProvider":
    """The provider for the effective model (see resolve_active), cached per pair.

    A run already holding an instance finishes on it; the next call picks up a
    switch.

    Raises:
        AIProviderError: If the provider cannot be created (missing config, etc.)
    """
    effective, _ = resolve_active()
    provider, model = effective.provider, effective.model
    # Whatever the source: never build a provider not approved as a processor.
    # (An env Gemini without a key raises in build_provider.)
    if not provider_approved(provider):
        raise AIProviderError(f"Provider {provider} is not approved as a data processor")
    key = (provider, model)
    with _instances_lock:
        instance = _instances.get(key)
    if instance is None:
        instance = build_provider(provider, model)
        with _instances_lock:
            instance = _instances.setdefault(key, instance)
    return instance
