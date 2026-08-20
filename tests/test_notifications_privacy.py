"""Telegram notifications must never carry a user's identity.

The chat lives on Telegram's infrastructure with no data processing agreement,
and our users are children - a name or e-mail in these messages is an unlawful
transfer of a minor's personal data. These tests exist so nobody "fixes" the
notifications by putting the user back in.
"""

import pytest

import app.notifications as notifications
from app.config import settings
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
        build_failed_message("ab12cd34", USER_ID, "2024", "etap1", 3, "boom"),
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

    def test_operational_data_is_kept(self):
        start = build_start_message("ab12cd34", USER_ID, "2024", "etap1", 3, 2)
        assert "ab12cd34" in start
        assert "2024/etap1/zad 3" in start
        assert "Images: 2" in start

        completed = build_completed_message("ab12cd34", USER_ID, "2024", "etap2", 1, 5)
        assert "5/6" in completed

        failed = build_failed_message("ab12cd34", USER_ID, "2024", "etap1", 3, "timeout")
        assert "timeout" in failed

    def test_long_error_is_truncated(self):
        message = build_failed_message("ab12cd34", USER_ID, "2024", "etap1", 3, "x" * 5000)
        assert len(message) < 700


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
