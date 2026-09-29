"""The OMJ grading path passes a typed solution through to the provider."""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.websocket.handler as handler
from app.db.models import SubmissionDB, SubmissionStatus, UserDB
from app.db.session import Base
from app.models import SubmissionResult

USER_ID = "user-1"
TEXT = "Niech $n$ będzie liczbą całkowitą. Wtedy $n(n+1)$ jest parzyste."


class StubProvider:
    def __init__(self):
        self.kwargs = None

    async def analyze_solution_stream(self, **kwargs):
        self.kwargs = kwargs
        if kwargs.get("on_upload_complete"):
            await kwargs["on_upload_complete"]()
        return SubmissionResult(score=6, feedback="Dobrze", scoring_meta={"model": "stub"})


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
    db.add(SubmissionDB(id="sub00001", user_id=USER_ID, year="2024", etap="etap1",
                        task_number=1, images=[], solution_text=TEXT,
                        status=SubmissionStatus.PENDING))
    db.commit()
    db.close()
    return factory


def test_omj_worker_passes_text_and_no_images(session_factory, monkeypatch, tmp_path, caplog):
    task_pdf = tmp_path / "zadania.pdf"
    task_pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(handler, "get_task_pdf_path", lambda year, etap: task_pdf)
    monkeypatch.setattr(handler, "get_solution_pdf_path", lambda year, etap: None)
    provider = StubProvider()
    monkeypatch.setattr(handler, "create_ai_provider", lambda: provider)
    sent = []

    async def capture(text):
        sent.append(text)

    monkeypatch.setattr(handler, "send_telegram_message", capture)

    with caplog.at_level("INFO"):
        asyncio.run(handler.process_submission_background(
            submission_id="sub00001", user_id=USER_ID, year="2024", etap="etap1",
            task_number=1, image_paths=[], solution_text=TEXT,
        ))

    assert provider.kwargs["solution_text"] == TEXT
    assert provider.kwargs["image_paths"] == []
    assert provider.kwargs["etap"] == "etap1"
    db = session_factory()
    assert db.query(SubmissionDB).one().status == SubmissionStatus.COMPLETED
    assert any(f"text_chars={len(TEXT)}" in r.message for r in caplog.records)
    assert all(TEXT not in r.message for r in caplog.records)
    assert all(TEXT not in message for message in sent)
