"""Regression tests for Gemini cost accounting and media-resolution handling.

Both of these failed silently in production before:
  - thinking tokens were omitted from cost, and gemini-3.1-pro-preview had no
    pricing entry, so logged cost was ~45x below the real figure;
  - GEMINI_MEDIA_RESOLUTION_IMAGES=ultra_high was accepted but the enum does not
    exist in the SDK, so images were sent at HIGH with only a per-request warning.
"""

from datetime import date

import pytest

from google.genai import types

import app.ai.providers.gemini as gemini_module
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

    def test_prod_model_has_explicit_pricing_for_flash(self):
        assert "gemini-3.7-flash" in GEMINI_PRICING
        # Candidate evaluated in docs/model-ab-2026-09-05.md; same price list.
        assert "gemini-3.8-flash" in GEMINI_PRICING

    def test_promo_rate_applies_before_expiry_and_lapses_after(self, provider, monkeypatch):
        """Flash is half-price through 2026-12-31; the table must not overstate
        cost now, nor understate it once the promo lapses."""
        provider._model_name = "gemini-3.7-flash"
        entry = GEMINI_PRICING["gemini-3.7-flash"]

        class _FrozenDate(date):
            _today = date(2026, 8, 17)

            @classmethod
            def today(cls):
                return cls._today

        monkeypatch.setattr(gemini_module, "date", _FrozenDate)
        promo = provider._calculate_cost(1_000_000, 0, 1_000_000)
        assert promo == pytest.approx(entry["promo_input"] + entry["promo_output"])

        _FrozenDate._today = date(2027, 1, 1)
        after = provider._calculate_cost(1_000_000, 0, 1_000_000)
        assert after == pytest.approx(entry["input"] + entry["output"])
        assert after > promo

    def test_promo_does_not_apply_to_long_context_tier(self, provider):
        """Models with a long-context tier must keep using its absolute rates."""
        provider._model_name = "gemini-3.1-pro-preview"
        assert "promo_until" not in GEMINI_PRICING["gemini-3.1-pro-preview"]

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


class TestLatexEscapeRepair:
    """The feedback prompt now demands heavy LaTeX; JSON escaping must survive it."""

    def test_mangled_macros_are_restored(self):
        from app.ai.parsing import repair_latex_escapes

        # What json.loads produces from an unescaped "$90^\text{o}$".
        assert repair_latex_escapes("$90^\text{o}$") == "$90^\\text{o}$"
        assert repair_latex_escapes("$\frac{1}{2}$") == "$\\frac{1}{2}$"
        assert repair_latex_escapes("$a \neq b$") == "$a \\neq b$"

    def test_short_macros_are_restored(self):
        """Enumerating macro names missed \\ne, \\to, \\beta and friends."""
        from app.ai.parsing import repair_latex_escapes

        assert repair_latex_escapes("$a \ne b$") == "$a \\ne b$"
        assert repair_latex_escapes("$x \to 0$") == "$x \\to 0$"
        assert repair_latex_escapes("$\beta$") == "$\\beta$"
        assert repair_latex_escapes("$n \bmod 2$") == "$n \\bmod 2$"

    def test_genuine_whitespace_is_preserved(self):
        from app.ai.parsing import repair_latex_escapes

        text = "Pierwszy akapit.\n\nDrugi akapit zaczyna się od słowa eq? Nie."
        assert repair_latex_escapes(text) == text
        assert repair_latex_escapes("koniec zdania.\nNastępne zdanie.") == (
            "koniec zdania.\nNastępne zdanie."
        )

    def test_unmatched_dollar_does_not_eat_the_feedback(self):
        from app.ai.parsing import repair_latex_escapes

        text = "Koszt to $50 zł.\nNa przyszłość zapisuj jednostki."
        assert repair_latex_escapes(text) == text

    def test_unescaped_latex_still_parses(self):
        """A lone backslash must not cost the student their whole score."""
        from app.ai.parsing import _extract_json_from_text

        raw = '{"score": 5, "feedback": "Kąt $90^\\circ$ oraz $a \\ge b$."}'
        parsed = _extract_json_from_text(raw)
        assert parsed is not None
        assert parsed["score"] == 5
        assert "\\circ" in parsed["feedback"]

    def test_partially_escaped_latex_still_parses(self):
        """The realistic case: the model doubles some backslashes but not all."""
        from app.ai.parsing import _extract_json_from_text

        # "\\\\circ" is a correctly escaped macro; "\\ge" is a lone one.
        raw = '{"score": 5, "feedback": "Kąt $90^\\\\circ$ oraz $a \\ge b$."}'
        parsed = _extract_json_from_text(raw)
        assert parsed is not None
        assert "\\circ" in parsed["feedback"]
        assert "\\ge" in parsed["feedback"]

    def test_unicode_escape_is_not_mistaken_for_a_macro(self):
        from app.ai.parsing import _escape_lone_backslashes

        assert _escape_lone_backslashes(r'"°"') == r'"°"'
        # \underline is a macro, not a unicode escape, so it must be doubled.
        assert _escape_lone_backslashes(r'"\underline{x}"') == r'"\\underline{x}"'

    def test_repair_reaches_fenced_and_prefixed_json(self):
        """Strategies 2-4 must repair too, or those responses still score 0."""
        from app.ai.parsing import _extract_json_from_text

        fenced = '```json\n{"score": 3, "feedback": "$a \\ge b$"}\n```'
        assert _extract_json_from_text(fenced)["score"] == 3

        prefixed = 'Oto ocena:\n{"score": 6, "feedback": "$\\alpha + \\beta$"}'
        assert _extract_json_from_text(prefixed)["score"] == 6

    def test_valid_json_is_untouched(self):
        from app.ai.parsing import _extract_json_from_text

        parsed = _extract_json_from_text('{"score": 3, "feedback": "Linia1\\nLinia2"}')
        assert parsed["feedback"] == "Linia1\nLinia2"
