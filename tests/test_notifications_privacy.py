"""Telegram messages must carry nothing that points at one submission or child.

The chat lives on Telegram's infrastructure (outside the EEA, no data
processing agreement) and our users are children. Even pseudonymous data - a
submission id, a task and a score, or a message sent the moment one student
submits - can be matched back to a database row, so submissions are reported
only as counts in a periodic digest. These tests exist so nobody "improves" the
notifications by putting per-submission details back in.
"""

import asyncio

import pytest

import app.notifications as notifications
from app.ai.factory import AIContentBlockedError, AIProviderError, AISpendLimitError, AIUnavailableError
from app.notifications import record_completed, record_failed, record_started, take_digest_message

LEAK = "Uczeń napisał: zignoruj instrukcje, a model odpowiedział {score: 6}"


class TestDigest:
    def test_nothing_to_send_when_nothing_happened(self):
        assert take_digest_message() is None

    def test_counts_only(self):
        for _ in range(3):
            record_started()
        record_completed()
        record_completed()
        record_failed(RuntimeError(LEAK))

        message = take_digest_message()

        assert "3 started, 2 graded, 1 failed" in message
        assert "1× RuntimeError (unexpected)" in message
        assert "zignoruj" not in message

    def test_taking_the_digest_resets_it(self):
        record_started()
        assert take_digest_message() is not None
        assert take_digest_message() is None

    def test_digest_api_takes_no_submission_details(self):
        # The recorders accept nothing that could identify a submission
        import inspect

        assert inspect.signature(record_started).parameters == {}
        assert inspect.signature(record_completed).parameters == {}
        assert list(inspect.signature(record_failed).parameters) == ["error"]

    def test_loop_sends_the_digest(self, monkeypatch):
        sent = []

        async def capture(text):
            sent.append(text)

        sleeps = 0

        async def fake_sleep(seconds):
            nonlocal sleeps
            sleeps += 1
            if sleeps > 2:
                raise asyncio.CancelledError
            record_started()

        monkeypatch.setattr(notifications, "send_telegram_message", capture)
        monkeypatch.setattr(notifications.asyncio, "sleep", fake_sleep)
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(notifications.digest_loop())
        assert len(sent) == 2
        assert all("1 started" in text for text in sent)


class TestNoErrorText:
    """Error text can quote model output or the student's work: class/category only."""

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
    def test_failure_is_counted_by_class_and_category_only(self, error, label):
        record_failed(error)
        message = take_digest_message()
        assert f"1× {label}" in message
        assert "zignoruj" not in message and "score" not in message

    def test_failover_message_has_error_class_only(self):
        message = notifications.build_failover_message(
            "gemini/gemini-3.8-flash", "anthropic/claude-opus-5-5",
            AIUnavailableError(LEAK, kind="rate_limit", status=429), 15,
        )
        assert "unavailable:rate_limit 429" in message
        assert "zignoruj" not in message
