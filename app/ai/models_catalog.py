"""The AI models an admin may select, with prices for cost estimates.

Single source of truth for /admin/settings, validation of the persisted choice
and the cost figures in scoring_meta and the A/B scripts. Gemini prices stay in
GEMINI_PRICING (older models there are still referenced by stored rows and the
eval scripts); Claude prices live here.
"""

from dataclasses import dataclass, field
from typing import Optional

from ..config import settings

PROVIDERS = ("gemini", "anthropic")
PROVIDER_LABELS = {"gemini": "Google Gemini", "anthropic": "Anthropic Claude"}


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    id: str
    label: str
    # USD per 1M tokens. Claude: "input", "output", "cache_read", "cache_write",
    # optional "long_threshold"/"long_input"/"long_output" (cache rates in the
    # long tier are derived from long_input). Gemini entries are empty -
    # estimate_cost delegates to GEMINI_PRICING.
    pricing: dict = field(default_factory=dict)


# Claude prices: platform.claude.com pricing, checked 2026-10-12.
# cache_write is the 5-minute TTL rate (1.25x input).
LONG_CACHE_READ_FACTOR = 0.1
LONG_CACHE_WRITE_FACTOR = 1.25
# Thinking tokens are part of output_tokens in the Messages API usage.
CATALOG: tuple[ModelInfo, ...] = (
    ModelInfo("gemini", "gemini-3.8-flash", "Gemini 3.8 Flash"),
    ModelInfo("gemini", "gemini-3.1-pro-preview", "Gemini 3.1 Pro (preview)"),
    ModelInfo("anthropic", "claude-opus-5-5", "Claude Opus 5.5",
              {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00}),
    ModelInfo("anthropic", "claude-sonnet-5-5", "Claude Sonnet 5.5",
              {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50}),
    ModelInfo("anthropic", "claude-haiku-5-5", "Claude Haiku 5.5",
              {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125,
               "long_threshold": 100_000, "long_input": 0.50, "long_output": 2.50}),
)


def get_model(provider: str, model: str) -> Optional[ModelInfo]:
    return next((m for m in CATALOG if m.provider == provider and m.id == model), None)


def models_for(provider: str) -> list[ModelInfo]:
    return [m for m in CATALOG if m.provider == provider]


def provider_configured(provider: str) -> bool:
    """The provider's API key is set (the key itself never leaves the server)."""
    if provider == "gemini":
        return bool(settings.gemini_api_key)
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    return False


def provider_approved(provider: str) -> bool:
    """GDPR gate: may student data be sent to this provider at all."""
    if provider == "anthropic":
        return settings.anthropic_processor_approved
    return provider == "gemini"


def estimate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    thoughts_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Estimated USD cost of one call. Logging/meta only, never billing."""
    if provider == "gemini":
        from .providers.gemini import estimate_cost as gemini_cost
        return gemini_cost(model, input_tokens, output_tokens, thoughts_tokens)

    info = get_model(provider, model)
    if info is None:
        return 0.0
    p = info.pricing
    prompt_tokens = input_tokens + cache_read_tokens + cache_write_tokens
    threshold = p.get("long_threshold")
    long = bool(threshold and prompt_tokens > threshold)
    if long:
        in_rate, out_rate = p["long_input"], p["long_output"]
        read_rate, write_rate = in_rate * LONG_CACHE_READ_FACTOR, in_rate * LONG_CACHE_WRITE_FACTOR
    else:
        in_rate, out_rate = p["input"], p["output"]
        read_rate, write_rate = p.get("cache_read", in_rate), p.get("cache_write", in_rate)
    return (
        input_tokens * in_rate
        + output_tokens * out_rate
        + cache_read_tokens * read_rate
        + cache_write_tokens * write_rate
    ) / 1_000_000
