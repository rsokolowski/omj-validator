"""Factory for creating AI providers based on configuration."""

from typing import TYPE_CHECKING, Optional

from ..config import settings

if TYPE_CHECKING:
    from .protocol import AIProvider


class AIProviderError(Exception):
    """Raised when AI provider cannot be created."""

    pass


# Singleton cache for AI provider
_provider_instance: Optional["AIProvider"] = None


def create_ai_provider() -> "AIProvider":
    """
    Create and return the configured AI provider (singleton).

    The provider is cached and reused across requests to avoid
    the ~1.3s initialization overhead of the genai.Client.

    Returns:
        AIProvider instance based on AI_PROVIDER setting

    Raises:
        AIProviderError: If provider cannot be created (missing config, etc.)
    """
    global _provider_instance

    if _provider_instance is not None:
        return _provider_instance

    provider_name = settings.ai_provider.lower()

    if provider_name == "gemini":
        from .providers.gemini import GeminiProvider

        if not settings.gemini_api_key:
            raise AIProviderError(
                "GEMINI_API_KEY is required when AI_PROVIDER=gemini. "
                "Set it in your .env file."
            )
        _provider_instance = GeminiProvider()
        return _provider_instance

    else:
        raise AIProviderError(
            f"Unknown AI provider: {provider_name}. "
            f"Supported providers: gemini"
        )
