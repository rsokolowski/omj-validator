"""Factory for creating AI providers based on configuration."""

from typing import TYPE_CHECKING

from ..config import settings

if TYPE_CHECKING:
    from .protocol import AIProvider


class AIProviderError(Exception):
    """Raised when AI provider cannot be created."""

    pass


def create_ai_provider() -> "AIProvider":
    """
    Create and return the configured AI provider.

    Returns:
        AIProvider instance based on AI_PROVIDER setting

    Raises:
        AIProviderError: If provider cannot be created (missing config, etc.)
    """
    provider_name = settings.ai_provider.lower()

    if provider_name == "claude":
        from .providers.claude import ClaudeProvider

        return ClaudeProvider()

    elif provider_name == "gemini":
        from .providers.gemini import GeminiProvider

        if not settings.gemini_api_key:
            raise AIProviderError(
                "GEMINI_API_KEY is required when AI_PROVIDER=gemini. "
                "Set it in your .env file."
            )
        return GeminiProvider()

    else:
        raise AIProviderError(
            f"Unknown AI provider: {provider_name}. "
            f"Supported providers: claude, gemini"
        )
