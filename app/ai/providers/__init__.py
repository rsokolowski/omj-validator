"""AI Provider implementations."""

from .gemini import GeminiProvider

__all__ = ["GeminiProvider", "AnthropicProvider"]


def __getattr__(name: str):
    # Lazy: importing the anthropic SDK costs startup time when Gemini is active.
    if name == "AnthropicProvider":
        from .anthropic import AnthropicProvider

        return AnthropicProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
