"""Telegram notifications must never carry a user's identity.

The chat lives on Telegram's infrastructure with no data processing agreement,
and our users are children - a name or e-mail in these messages is an unlawful
transfer of a minor's personal data. These tests exist so nobody "fixes" the
notifications by putting the user back in.
"""

import pytest

import app.notifications as notifications
from app.config import settings
from app.ai.factory import AIContentBlockedError, AIProviderError, AISpendLimitError, AIUnavailableError
from app.notifications import (
    build_completed_message,
    build_failed_message,
    build_start_message,
    build_user_pseudonym,
)

USER_ID = "108451234567890123456"
OTHER_USER_ID = "999991234567890123456"

# Values that must never appear in a notification
NAME = "Jan Kowalski"
EMAIL = "jan.kowalski@example.com"


@pytest.fixture(autouse=True)
def _no_pseudonym_salt(monkeypatch):
    """Default configuration: no salt, therefore no user identifier at all."""
    monkeypatch.setattr(settings, "telegram_pseudonym_salt", None)


def _all_messages():
    return [
        build_start_message("ab12cd34", USER_ID, "2024", "etap1", 3, 2),
        build_completed_message("ab12cd34", USER_ID, "2024", "etap1", 3, 5),
        build_failed_message("ab12cd34", USER_ID, "2024", "etap1", 3, RuntimeError("boom")),
    ]


class TestNoIdentity:
    def test_messages_never_contain_the_raw_user_id(self):
        for message in _all_messages():
            assert USER_ID not in message
            # not even a truncated prefix
            assert USER_ID[:8] not in message

    def test_messages_never_contain_name_or_email(self):
        for message in _all_messages():
            assert NAME not in message
            assert EMAIL not in message
            assert "@" not in message

    def test_no_user_line_without_a_salt(self):
        for message in _all_messages():
            assert "User:" not in message

    def test_text_submission_message_carries_length_only(self):
        message = build_start_message("ab12cd34", USER_ID, "2024", "etap1", 3, 0, 1234)
        assert "Images: 0, text: 1234 chars" in message
        # The signature takes a count, never the text: nothing to leak
        import inspect

        assert inspect.signature(build_start_message).parameters["text_chars"].annotation is int

    def test_operational_data_is_kept(self):
        start = build_start_message("ab12cd34", USER_ID, "2024", "etap1", 3, 2)
        assert "ab12cd34" in start
        assert "2024/etap1/zad 3" in start
        assert "Images: 2" in start

        completed = build_completed_message("ab12cd34", USER_ID, "2024", "etap2", 1, 5)
        assert "5/6" in completed

        failed = build_failed_message(
            "ab12cd34", USER_ID, "2024", "etap1", 3,
            AIUnavailableError("Analiza trwa zbyt długo.", kind="timeout"),
        )
        assert "AIUnavailableError (unavailable:timeout)" in failed


class TestNoErrorText:
    """Error text can quote model output or the student's work: class/category only."""

    LEAK = "Uczeń napisał: zignoruj instrukcje, a model odpowiedział {score: 6}"

    @pytest.mark.parametrize(
        "error, label",
        [
            (RuntimeError(LEAK), "RuntimeError (unexpected)"),
            (AIProviderError(LEAK), "AIProviderError (provider_error)"),
            (AIContentBlockedError(LEAK), "AIContentBlockedError (content_blocked)"),
            (AISpendLimitError(LEAK), "AISpendLimitError (spend_limit)"),
            (AIUnavailableError(LEAK, kind="auth", status=403), "AIUnavailableError (unavailable:auth 403)"),
        ],
    )
    def test_failed_message_has_class_and_category_only(self, error, label):
        message = build_failed_message("ab12cd34", USER_ID, "2024", "etap1", 3, error)
        assert f"Error: {label}" in message
        assert "zignoruj" not in message and "score" not in message

    def test_failover_message_has_error_class_only(self):
        message = notifications.build_failover_message(
            "gemini/gemini-3.8-flash", "anthropic/claude-opus-5-5",
            AIUnavailableError(self.LEAK, kind="rate_limit", status=429), 15,
        )
        assert "unavailable:rate_limit 429" in message
        assert "zignoruj" not in message


class TestPseudonym:
    def test_disabled_by_default(self):
        assert build_user_pseudonym(USER_ID) == ""

    def test_enabled_by_salt_and_irreversible(self, monkeypatch):
        monkeypatch.setattr(settings, "telegram_pseudonym_salt", "s3cret-salt")
        pseudonym = build_user_pseudonym(USER_ID)

        assert len(pseudonym) == notifications.PSEUDONYM_LENGTH
        assert USER_ID not in pseudonym
        # Stable for the same user, different for another user
        assert pseudonym == build_user_pseudonym(USER_ID)
        assert pseudonym != build_user_pseudonym(OTHER_USER_ID)

    def test_salt_changes_the_pseudonym(self, monkeypatch):
        monkeypatch.setattr(settings, "telegram_pseudonym_salt", "salt-a")
        first = build_user_pseudonym(USER_ID)
        monkeypatch.setattr(settings, "telegram_pseudonym_salt", "salt-b")
        assert first != build_user_pseudonym(USER_ID)

    def test_pseudonym_appears_in_messages_but_identity_does_not(self, monkeypatch):
        monkeypatch.setattr(settings, "telegram_pseudonym_salt", "s3cret-salt")
        pseudonym = build_user_pseudonym(USER_ID)

        for message in _all_messages():
            assert f"User: #{pseudonym}" in message
            assert USER_ID not in message
            assert NAME not in message
            assert EMAIL not in message
