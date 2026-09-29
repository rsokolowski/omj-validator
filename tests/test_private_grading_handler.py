"""The background worker grades private submissions against the task text."""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.websocket.handler as handler
from app.ai.factory import AIProviderError
from app.db.models import PrivateTaskDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base
from app.models import SubmissionResult

USER_ID = "user-1"
TASK_ID = "abcdefghijkl"


class StubProvider:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    async def analyze_private_solution_stream(
        self, task_title, task_content, image_paths, on_thinking=None, on_upload_complete=None
    ):
        self.calls.append((task_title, task_content, list(image_paths)))
        if on_upload_complete:
            await on_upload_complete()
        if on_thinking:
            await on_thinking("**Sprawdzam**")
        if self.fail:
            raise AIProviderError("Analiza trwa zbyt długo. Spróbuj ponownie za chwilę.")
        return SubmissionResult(score=5, feedback="Dobrze", scoring_meta={"model": "stub"})

    async def analyze_solution_stream(self, **kwargs):  # pragma: no cover - must not be used
        raise AssertionError("OMJ grading path used for a private task")


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(handler, "SessionLocal", factory)

    db = factory()
    db.add(UserDB(google_sub=USER_ID, email="a@example.com"))
    db.add(PrivateTaskDB(id=TASK_ID, user_id=USER_ID, title="Parzystość",
                         content="Wykaż, że $n^2+n$ jest parzyste.", hints=[],
                         source_images=[], origin="typed"))
    db.add(SubmissionDB(id="sub00001", user_id=USER_ID, private_task_id=TASK_ID,
                        images=[], status=SubmissionStatus.PENDING))
    db.commit()
    db.close()
    return factory


def run(provider, monkeypatch, image_paths):
    monkeypatch.setattr(handler, "create_ai_provider", lambda: provider)
    sent = []

    async def capture(text):
        sent.append(text)

    monkeypatch.setattr(handler, "send_telegram_message", capture)
    asyncio.run(
        handler.process_submission_background(
            submission_id="sub00001",
            user_id=USER_ID,
            year=None,
            etap=None,
            task_number=None,
            image_paths=image_paths,
            private_task={"id": TASK_ID, "title": "Parzystość",
                          "content": "Wykaż, że $n^2+n$ jest parzyste."},
        )
    )
    return sent


def test_private_submission_is_graded_against_task_text(session_factory, monkeypatch, tmp_path):
    image = tmp_path / "a.jpg"
    image.write_bytes(b"x")
    provider = StubProvider()

    sent = run(provider, monkeypatch, [image])

    db = session_factory()
    sub = db.query(SubmissionDB).one()
    assert sub.status == SubmissionStatus.COMPLETED
    assert sub.score == 5
    assert sub.scoring_meta["task_snapshot"] == {
        "title": "Parzystość",
        "content": "Wykaż, że $n^2+n$ jest parzyste.",
    }
    assert provider.calls[0][:2] == ("Parzystość", "Wykaż, że $n^2+n$ jest parzyste.")
    # Notifications never carry the task title or statement
    assert sent and all("Parzysto" not in text and "n^2" not in text for text in sent)
    assert any("private" in text for text in sent)


def test_private_submission_failure_is_recorded(session_factory, monkeypatch, tmp_path):
    run(StubProvider(fail=True), monkeypatch, [])

    db = session_factory()
    sub = db.query(SubmissionDB).one()
    assert sub.status == SubmissionStatus.FAILED
    assert "zbyt długo" in sub.error_message
