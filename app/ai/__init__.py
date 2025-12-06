"""AI module - provides abstraction layer for AI solution analyzers."""

from .factory import AIProviderError, create_ai_provider
from .protocol import AIProvider

__all__ = ["AIProvider", "AIProviderError", "create_ai_provider"]
