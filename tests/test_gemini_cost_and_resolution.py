"""Regression tests for Gemini cost accounting and media-resolution handling.

Both of these failed silently in production before:
  - thinking tokens were omitted from cost, and gemini-3.1-pro-preview had no
    pricing entry, so logged cost was ~45x below the real figure;
  - GEMINI_MEDIA_RESOLUTION_IMAGES=ultra_high was accepted but the enum does not
    exist in the SDK, so images were sent at HIGH with only a per-request warning.
"""

import pytest

from google.genai import types

from app.ai.providers.gemini import (
    GEMINI_PRICING,
    MEDIA_RESOLUTION_LADDER,
    GeminiProvider,
    _pricing_warned,
    _resolution_warned,
)


@pytest.fixture
def provider():
    """A provider instance without touching the network or requiring an API key."""
    p = GeminiProvider.__new__(GeminiProvider)
    p._model_name = "gemini-3.1-pro-preview"
    return p


@pytest.fixture(autouse=True)
def _reset_warn_caches():
    _resolution_warned.clear()
    _pricing_warned.clear()


class TestCost:
    def test_thinking_tokens_are_billed_as_output(self, provider):
        without = provider._calculate_cost(11167, 373, 0)
        with_thoughts = provider._calculate_cost(11167, 373, 2670)
        assert with_thoughts > without
        # 11167/1e6*2 + (373+2670)/1e6*12 = 0.022334 + 0.036516
        assert with_thoughts == pytest.approx(0.05885, rel=1e-6)

    def test_prod_model_has_explicit_pricing(self):
        """The model actually deployed must not fall through to default rates."""
        assert "gemini-3.1-pro-preview" in GEMINI_PRICING

    def test_unknown_model_warns_once(self, provider, caplog):
        provider._model_name = "some-unreleased-model"
        with caplog.at_level("WARNING"):
            provider._calculate_cost(1000, 100, 10)
            provider._calculate_cost(1000, 100, 10)
        assert sum("No pricing entry" in r.message for r in caplog.records) == 1

    def test_long_context_tier_applied_above_threshold(self, provider):
        below = provider._calculate_cost(199_000, 1000, 0)
        above = provider._calculate_cost(201_000, 1000, 0)
        # Rate doubles on input past 200k, so cost more than doubles per token.
        assert above / 201_000 > below / 199_000 * 1.9

    def test_flash_is_cheaper_than_pro_on_identical_usage(self, provider):
        pro = provider._calculate_cost(10_000, 200, 2000)
        provider._model_name = "gemini-3.6-flash"
        flash = provider._calculate_cost(10_000, 200, 2000)
        assert flash < pro


class TestMediaResolution:
    def test_supported_levels_map_through(self, provider):
        assert provider._get_media_resolution("low") is (
            types.MediaResolution.MEDIA_RESOLUTION_LOW
        )
        assert provider._get_media_resolution("high") is (
            types.MediaResolution.MEDIA_RESOLUTION_HIGH
        )

    def test_unsupported_level_degrades_and_warns_once(self, provider, caplog):
        """ultra_high is absent from the SDK enum; it must degrade, loudly, once."""
        if hasattr(types.MediaResolution, "MEDIA_RESOLUTION_ULTRA_HIGH"):
            pytest.skip("SDK now supports ULTRA_HIGH; degradation no longer applies")
        with caplog.at_level("WARNING"):
            first = provider._get_media_resolution("ultra_high")
            second = provider._get_media_resolution("ultra_high")
        assert first is types.MediaResolution.MEDIA_RESOLUTION_HIGH
        assert second is first
        warnings = [r for r in caplog.records if "NOT supported" in r.message]
        assert len(warnings) == 1
        # The operator must be told the setting is inert, not just that it changed.
        assert "no effect" in warnings[0].message

    def test_unknown_level_falls_back_to_high_and_warns_once(self, provider, caplog):
        with caplog.at_level("WARNING"):
            result = provider._get_media_resolution("gigantic")
            provider._get_media_resolution("gigantic")
        assert result is types.MediaResolution.MEDIA_RESOLUTION_HIGH
        assert sum("Unknown media resolution" in r.message for r in caplog.records) == 1

    def test_case_insensitive(self, provider):
        assert provider._get_media_resolution("HIGH") is (
            types.MediaResolution.MEDIA_RESOLUTION_HIGH
        )

    def test_ladder_is_ordered_low_to_high(self):
        assert [n for n, _ in MEDIA_RESOLUTION_LADDER] == [
            "low", "medium", "high", "ultra_high",
        ]
