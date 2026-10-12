"""Factory for creating AI providers based on the active model."""

import logging
import threading
from typing import TYPE_CHECKING

from .config_store import env_default, get_active_model
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
    tasks) a block means the text must not be saved unchecked.
    """


# One instance per (provider, model): client construction costs ~1.3s
_instances: dict[tuple[str, str], "AIProvider"] = {}
_instances_lock = threading.Lock()


def reset_provider_cache() -> None:
    with _instances_lock:
        _instances.clear()


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


def _usable(provider: str) -> bool:
    return provider_configured(provider) and provider_approved(provider)


def create_ai_provider() -> "AIProvider":
    """The provider for the active model (app_settings row, else env), cached per pair.

    A run already holding an instance finishes on it; the next call picks up a
    switch. An active choice that cannot be used (no key, or Anthropic not yet
    approved as a processor) falls back to the environment default rather than
    stopping grading - or sending data to an unapproved processor.

    Raises:
        AIProviderError: If the provider cannot be created (missing config, etc.)
    """
    active = get_active_model()
    provider, model = active.provider, active.model
    if active.source == "db" and not _usable(provider):
        logger.error(
            f"[AI] Active model {provider}/{model} is not usable "
            f"({'not approved' if provider_configured(provider) else 'no API key'}) - using env default"
        )
        fallback = env_default()
        provider, model = fallback.provider, fallback.model
    key = (provider, model)
    with _instances_lock:
        instance = _instances.get(key)
    if instance is None:
        instance = build_provider(provider, model)
        with _instances_lock:
            instance = _instances.setdefault(key, instance)
    return instance
