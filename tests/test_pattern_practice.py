"""Graded practice: a solution submitted from a pattern counts as its review."""

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.websocket.handler as handler
from app import storage
from app.db.models import PatternDB, PrivateTaskDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.patterns import PatternRepository
from app.db.session import Base
from app.models import SubmissionResult, TaskInfo, TaskPdf
from app.patterns import service, srs

USER_ID = "user-1"
OTHER_USER_ID = "user-2"
TASK_ID = "privtask0001"
TODAY = date(2026, 10, 1)


@pytest.fixture
def factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(handler, "SessionLocal", factory)
    monkeypatch.setattr(srs, "today_warsaw", lambda: TODAY)
    db = factory()
    db.add(UserDB(google_sub=USER_ID, email="a@example.com"))
    db.add(UserDB(google_sub=OTHER_USER_ID, email="b@example.com"))
    db.add(PrivateTaskDB(id=TASK_ID, user_id=USER_ID, title="Parzystość",
                         content="Wymyślone zadanie o parzystości sumy.", hints=[],
                         source_images=[], origin="typed"))
    db.commit()
    db.close()
    return factory


@pytest.fixture
def db(factory):
    session = factory()
    yield session
    session.close()


def make_pattern(db, user_id=USER_ID, level=1, streak=1):
    repo = PatternRepository(db)
    p = repo.create(user_id, trigger="Pytają o parzystość", action="Sprawdź sumę modulo 2",
                    example=None, category="teoria_liczb", skills=[], origin="own",
                    refinement=[], due_on=TODAY + timedelta(days=3))
    p.srs_level, p.srs_streak = level, streak
    db.commit()
    return p


def omj_submission(db, sid, pattern_id, score, etap="etap2", status=SubmissionStatus.COMPLETED,
                   hints_used=0, user_id=USER_ID):
    db.add(SubmissionDB(id=sid, user_id=user_id, year="2024", etap=etap, task_number=1, images=[],
                        status=status, score=score, pattern_id=pattern_id, hints_used=hints_used))
    db.commit()


class TestApplyPracticeResult:
    def test_full_score_without_hints_promotes(self, db):
        p = make_pattern(db, level=1, streak=1)
        omj_submission(db, "sub00001", p.id, 6)

        service.apply_practice_result(db, "sub00001")

        db.refresh(p)
        assert (p.srs_level, p.srs_streak) == (2, 0)
        assert p.due_on == TODAY + timedelta(days=7)
        review = p.reviews[0]
        assert (review.kind, review.outcome, review.submission_id) == ("task", "ok", "sub00001")

    def test_etap1_partial_is_hard(self, db):
        p = make_pattern(db, level=2, streak=1)
        omj_submission(db, "sub00001", p.id, 1, etap="etap1")
        service.apply_practice_result(db, "sub00001")
        db.refresh(p)
        assert (p.srs_level, p.srs_streak) == (2, 1)
        assert p.reviews[0].outcome == "hard"

    def test_hints_make_a_full_score_hard(self, db):
        p = make_pattern(db)
        omj_submission(db, "sub00001", p.id, 6, hints_used=2)
        service.apply_practice_result(db, "sub00001")
        db.refresh(p)
        assert p.reviews[0].outcome == "hard"

    def test_private_task_uses_six_point_scale(self, db):
        p = make_pattern(db, level=1, streak=0)
        db.add(SubmissionDB(id="sub00001", user_id=USER_ID, private_task_id=TASK_ID, images=[],
                            status=SubmissionStatus.COMPLETED, score=5, pattern_id=p.id))
        db.commit()
        service.apply_practice_result(db, "sub00001")
        db.refresh(p)
        assert p.reviews[0].outcome == "ok"

    def test_applied_once(self, db):
        p = make_pattern(db)
        omj_submission(db, "sub00001", p.id, 6)
        service.apply_practice_result(db, "sub00001")
        service.apply_practice_result(db, "sub00001")
        db.refresh(p)
        assert len(p.reviews) == 1

    def test_failed_grading_does_not_count(self, db):
        p = make_pattern(db)
        omj_submission(db, "sub00001", p.id, None, status=SubmissionStatus.FAILED)
        service.apply_practice_result(db, "sub00001")
        db.refresh(p)
        assert p.reviews == []

    def test_pattern_deleted_before_grading_finished(self, db):
        p = make_pattern(db)
        omj_submission(db, "sub00001", p.id, 6)
        PatternRepository(db).delete(p)
        db.expire_all()
        service.apply_practice_result(db, "sub00001")  # no exception
        assert db.get(SubmissionDB, "sub00001").pattern_id is None

    def test_someone_elses_pattern_is_ignored(self, db):
        p = make_pattern(db, user_id=OTHER_USER_ID)
        omj_submission(db, "sub00001", p.id, 6)
        service.apply_practice_result(db, "sub00001")
        db.refresh(p)
        assert p.reviews == []

    def test_unknown_submission(self, db):
        service.apply_practice_result(db, "nosuchid")


class TestPracticeCandidates:
    def test_unknown_omj_key_skipped_and_last_attempt_reported(self, db, monkeypatch):
        known = TaskInfo(year="2024", etap="etap2", number=1, title="Zadanie 1",
                         pdf=TaskPdf(tasks="t.pdf"), difficulty=3)
        monkeypatch.setattr(
            storage, "get_task",
            lambda year, etap, number: known if (year, etap, number) == ("2024", "etap2", 1) else None,
        )
        p = make_pattern(db)
        repo = PatternRepository(db)
        repo.add_link(p, task_key="2024_etap2_1", role="practice", origin="ai", status="accepted")
        repo.add_link(p, task_key="1990_etap1_1", role="practice", origin="ai", status="accepted")
        repo.add_link(p, private_task_id=TASK_ID, role="source", origin="manual", status="accepted")
        repo.add_link(p, task_key="2024_etap2_2", role="practice", origin="ai", status="suggested")
        omj_submission(db, "sub00001", None, 6)

        candidates = {c.ref: c for c in service.practice_candidates(db, p, USER_ID)}

        assert set(candidates) == {"2024_etap2_1", TASK_ID}
        assert candidates["2024_etap2_1"].last_attempt is not None
        assert candidates[TASK_ID].last_attempt is None
        assert candidates[TASK_ID].kind == "private"


class StubProvider:
    async def analyze_private_solution_stream(self, task_title, task_content, image_paths,
                                              on_thinking=None, on_upload_complete=None):
        return SubmissionResult(score=6, feedback="Dobrze", scoring_meta={"model": "stub"})


def test_worker_grades_even_when_the_pattern_hook_fails(factory, monkeypatch, tmp_path):
    db = factory()
    p = make_pattern(db)
    db.add(SubmissionDB(id="sub00001", user_id=USER_ID, private_task_id=TASK_ID, images=[],
                        status=SubmissionStatus.PENDING, pattern_id=p.id))
    db.commit()
    db.close()

    calls = []

    def boom(db, submission_id):
        calls.append(submission_id)
        raise RuntimeError("pattern bookkeeping broke")

    monkeypatch.setattr(handler, "apply_practice_result", boom)
    monkeypatch.setattr(handler, "create_ai_provider", lambda: StubProvider())

    async def quiet(text):
        return None

    monkeypatch.setattr(handler, "send_telegram_message", quiet)
    image = tmp_path / "a.jpg"
    image.write_bytes(b"x")

    asyncio.run(handler.process_submission_background(
        submission_id="sub00001", user_id=USER_ID, year=None, etap=None, task_number=None,
        image_paths=[image],
        private_task={"id": TASK_ID, "title": "Parzystość", "content": "Wymyślone zadanie."},
    ))

    db = factory()
    assert calls == ["sub00001"]
    assert db.get(SubmissionDB, "sub00001").status == SubmissionStatus.COMPLETED
    db.close()


def test_worker_applies_practice_result(factory, monkeypatch, tmp_path):
    db = factory()
    p = make_pattern(db, level=1, streak=1)
    pattern_id = p.id
    db.add(SubmissionDB(id="sub00001", user_id=USER_ID, private_task_id=TASK_ID, images=[],
                        status=SubmissionStatus.PENDING, pattern_id=pattern_id))
    db.commit()
    db.close()
    monkeypatch.setattr(handler, "create_ai_provider", lambda: StubProvider())

    async def quiet(text):
        return None

    monkeypatch.setattr(handler, "send_telegram_message", quiet)
    image = tmp_path / "a.jpg"
    image.write_bytes(b"x")

    asyncio.run(handler.process_submission_background(
        submission_id="sub00001", user_id=USER_ID, year=None, etap=None, task_number=None,
        image_paths=[image],
        private_task={"id": TASK_ID, "title": "Parzystość", "content": "Wymyślone zadanie."},
    ))

    db = factory()
    assert db.get(PatternDB, pattern_id).srs_level == 2
    db.close()
