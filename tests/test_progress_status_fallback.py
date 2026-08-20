"""Status updates must stay Polish even when translation is unavailable.

The headings broadcast during scoring are the model's own English wording, taken
from its reasoning about the student's work. Translation is off by default in
production (TRANSLATE_ENABLED=false), so without a fallback a Polish 12-year-old
would watch English status lines scroll past.
"""

import pytest

from app.config import settings
from app.websocket.progress import (
    UNTRANSLATED_STATUS_FALLBACK,
    ProgressManager,
    StatusMessage,
    extract_latest_heading,
)


@pytest.fixture
def manager(monkeypatch):
    """A ProgressManager with one registered submission and no real WebSocket."""
    mgr = ProgressManager()
    sent: list[str] = []

    async def fake_broadcast(submission_id, msg):
        if isinstance(msg, StatusMessage):
            sent.append(msg.message)

    monkeypatch.setattr(mgr, "_broadcast", fake_broadcast)
    mgr.sent = sent
    return mgr


async def _register(manager, submission_id="sub12345"):
    from app.websocket.progress import SubmissionProgress

    manager._submissions[submission_id] = SubmissionProgress(submission_id=submission_id)
    return submission_id


class TestHeadingExtraction:
    def test_takes_the_latest_heading(self):
        assert extract_latest_heading("**First**\ntext\n**Second**") == "Second"

    def test_returns_none_without_headings(self):
        assert extract_latest_heading("plain reasoning text") is None


@pytest.mark.asyncio
class TestUntranslatedFallback:
    async def test_english_heading_is_replaced_when_translation_is_off(
        self, manager, monkeypatch
    ):
        monkeypatch.setattr(settings, "translate_enabled", False)
        submission_id = await _register(manager)

        await manager.send_thinking(submission_id, "**Analyzing the diagram**")

        assert manager.sent == [UNTRANSLATED_STATUS_FALLBACK]
        assert "Analyzing" not in manager.sent[0]

    async def test_translated_heading_is_broadcast_as_is(self, manager, monkeypatch):
        monkeypatch.setattr(settings, "translate_enabled", True)
        monkeypatch.setattr(
            "app.websocket.progress.translate_to_polish_optional",
            _fake_translate("Analizuję rysunek"),
        )
        submission_id = await _register(manager)

        await manager.send_thinking(submission_id, "**Analyzing the diagram**")

        assert manager.sent == ["Analizuję rysunek"]

    async def test_failed_translation_falls_back(self, manager, monkeypatch):
        """A failure is signalled by None, not by echoing the input."""
        monkeypatch.setattr(settings, "translate_enabled", True)
        monkeypatch.setattr(
            "app.websocket.progress.translate_to_polish_optional",
            _fake_translate(None),
        )
        submission_id = await _register(manager)

        await manager.send_thinking(submission_id, "**Checking the algebra**")

        assert manager.sent == [UNTRANSLATED_STATUS_FALLBACK]

    async def test_heading_that_translates_to_itself_is_kept(self, manager, monkeypatch):
        """Regression: failure used to be inferred from result == input, so a
        correct translation that happens to equal the source (one word, a proper
        noun) was silently replaced by the fallback."""
        monkeypatch.setattr(settings, "translate_enabled", True)
        monkeypatch.setattr(
            "app.websocket.progress.translate_to_polish_optional",
            _fake_translate("Pitagoras"),
        )
        submission_id = await _register(manager)

        await manager.send_thinking(submission_id, "**Pitagoras**")

        assert manager.sent == ["Pitagoras"]
        assert manager.sent != [UNTRANSLATED_STATUS_FALLBACK]

    async def test_empty_translation_falls_back(self, manager, monkeypatch):
        monkeypatch.setattr(settings, "translate_enabled", True)
        monkeypatch.setattr(
            "app.websocket.progress.translate_to_polish_optional",
            _fake_translate(""),
        )
        submission_id = await _register(manager)

        await manager.send_thinking(submission_id, "**Checking the algebra**")

        assert manager.sent == [UNTRANSLATED_STATUS_FALLBACK]

    async def test_stored_status_matches_what_was_sent(self, manager, monkeypatch):
        monkeypatch.setattr(settings, "translate_enabled", False)
        submission_id = await _register(manager)

        await manager.send_thinking(submission_id, "**Analyzing the diagram**")

        assert (
            manager._submissions[submission_id].current_status
            == UNTRANSLATED_STATUS_FALLBACK
        )

    async def test_nothing_is_sent_without_a_heading(self, manager, monkeypatch):
        monkeypatch.setattr(settings, "translate_enabled", False)
        submission_id = await _register(manager)

        await manager.send_thinking(submission_id, "just reasoning, no heading")

        assert manager.sent == []


def _fake_translate(result):
    """Stub for translate_to_polish_optional: returns exactly `result`."""

    async def _translate(text: str):
        return result

    return _translate
