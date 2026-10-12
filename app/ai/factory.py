"""Factory for creating AI providers based on the active model."""

import logging
import threading
from typing import TYPE_CHECKING, Optional

from ..config import settings
from .config_store import ActiveModel, env_default, get_active_model
from .models_catalog import find_model, provider_approved, provider_configured

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
UNAVAILABLE_RATE_LIMIT = "rate_limit"  # 429
UNAVAILABLE_SERVER = "server"        # 502/503/504/529 - provider overloaded or down
UNAVAILABLE_NETWORK = "network"      # connection could not be established
# The request's own content can cause these (huge input, long thinking, an
# input the model chokes on): they never fail the request over, they only
# count toward the circuit breaker, which reacts to the primary failing
# across requests - see app/ai/failover.py.
UNAVAILABLE_TIMEOUT = "timeout"
UNAVAILABLE_INTERNAL = "internal"    # 500 / unspecified internal error
UNAVAILABLE_CONNECTION_LOST = "connection_lost"  # dropped mid-request
PERMANENT_KINDS = frozenset({UNAVAILABLE_AUTH, UNAVAILABLE_NOT_FOUND})
BREAKER_ONLY_KINDS = frozenset({UNAVAILABLE_TIMEOUT, UNAVAILABLE_INTERNAL, UNAVAILABLE_CONNECTION_LOST})


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

    @property
    def fails_over(self) -> bool:
        """Content-independent, so the backup may take THIS request."""
        return self.kind not in BREAKER_ONLY_KINDS


class AISpendLimitError(AIProviderError):
    """The daily AI spend cap (AI_DAILY_SPEND_LIMIT_USD) is reached."""


# One instance per (provider, model): client construction costs ~1.3s
_instances: dict[tuple[str, str], "AIProvider"] = {}
# FailoverProvider per (primary provider, model, backup provider, model)
_wrappers: dict[tuple[str, str, str, str], "AIProvider"] = {}
_instances_lock = threading.Lock()

# (provider, model, reason) already logged as unusable - logged once per process,
# not on every grading call while the stored row stays unusable.
_logged_fallbacks: set[tuple[str, str, str]] = set()


def reset_provider_cache() -> None:
    with _instances_lock:
        _instances.clear()
        _wrappers.clear()
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


def _cached_provider(provider: str, model: str) -> "AIProvider":
    """The cached instance for (provider, model), built on first use.

    Never builds a provider not approved as a processor (GDPR gate); an
    unconfigured one raises in build_provider.
    """
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


# Polish, shown on /admin/settings when failover would not apply
FAILOVER_OFF = "wyłączone (AI_FAILOVER_ENABLED)"
FAILOVER_UNKNOWN_MODEL = "model spoza katalogu (AI_FAILOVER_MODEL)"
FAILOVER_SAME_PROVIDER = "ten sam dostawca co aktywny model"


def _backup_model(primary_provider: str) -> Optional[tuple[str, str]]:
    """The backup (provider, model) for a primary of this provider, gates not checked.

    AI_FAILOVER_MODEL - unless it belongs to the primary's own provider (an
    admin made Claude the active model): then the environment Gemini default
    backs it up. None when AI_FAILOVER_MODEL is not in the catalog.
    """
    info = find_model(settings.ai_failover_model)
    if info is None:
        return None
    if info.provider != primary_provider:
        return info.provider, info.id
    if primary_provider != "gemini":
        default = env_default()
        return default.provider, default.model
    return info.provider, info.id


def _failover_blocker(primary_provider: str) -> tuple[Optional[tuple[str, str]], Optional[str]]:
    """(backup (provider, model), None) when failover applies, else (None, why not)."""
    if not settings.ai_failover_enabled:
        return None, FAILOVER_OFF
    backup = _backup_model(primary_provider)
    if backup is None:
        return None, FAILOVER_UNKNOWN_MODEL
    if backup[0] == primary_provider:
        return None, FAILOVER_SAME_PROVIDER
    # The existing GDPR gate, unchanged: no key or no processor approval = no failover
    reason = _unusable_reason(backup[0])
    if reason is not None:
        return None, reason
    return backup, None


def failover_target(primary_provider: str) -> Optional[tuple[str, str]]:
    """The backup (provider, model) for a primary of this provider, or None."""
    return _failover_blocker(primary_provider)[0]


def failover_status(effective: ActiveModel) -> dict:
    """Failover state for GET /api/admin/ai-config - no keys, no content."""
    from .failover import breaker
    from .models_catalog import get_model

    backup = _backup_model(effective.provider)
    target, reason = _failover_blocker(effective.provider)
    info = get_model(*backup) if backup else None
    return {
        "enabled": settings.ai_failover_enabled,
        "provider": backup[0] if backup else None,
        "model": backup[1] if backup else settings.ai_failover_model,
        "model_label": info.label if info else (backup[1] if backup else settings.ai_failover_model),
        # The backup provider may receive student data (key + GDPR approval)
        "gate_open": bool(backup and _unusable_reason(backup[0]) is None),
        "active": target is not None,
        "inactive_reason": reason,
        "breaker_minutes": settings.ai_failover_breaker_minutes,
        "breaker_threshold": settings.ai_failover_breaker_threshold,
        "breaker": breaker.state((effective.provider, effective.model)),
    }


def create_ai_provider() -> "AIProvider":
    """The provider for the effective model (see resolve_active), cached per pair.

    Wrapped in a FailoverProvider when a backup is usable (failover_target);
    otherwise the plain provider, exactly as without failover. A run already
    holding an instance finishes on it; the next call picks up a switch.

    Raises:
        AIProviderError: If the provider cannot be created (missing config, etc.)
    """
    effective, _ = resolve_active()
    provider, model = effective.provider, effective.model
    primary = _cached_provider(provider, model)
    target = failover_target(provider)
    if target is None:
        return primary
    from .failover import FailoverProvider

    key = (provider, model, *target)
    with _instances_lock:
        wrapper = _wrappers.get(key)
        if wrapper is None or wrapper.primary is not primary:
            wrapper = FailoverProvider(primary, target, _cached_provider)
            _wrappers[key] = wrapper
    return wrapper
