"""Daily AI spend cap, grading concurrency cap and failover restart in the worker."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.websocket.handler as handler
from app.notifications import take_digest_message
from app.ai import spend
from app.ai.factory import AISpendLimitError, AIUnavailableError
from app.ai.failover import FailoverProvider, breaker, restart_hook
from app.config import settings
from app.db.models import AIUsageDB, SubmissionDB, SubmissionStatus, UserDB
from app.db.repositories import QUOTA_RELEASED_KEY, SUBMISSION_TIMEOUT_SECONDS, SubmissionRepository
from app.db.session import Base
from app.models import SubmissionResult
from app.private_tasks import service as private_service

USER_ID = "user-1"


def naive_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(handler, "SessionLocal", factory)
    db = factory()
    db.add(UserDB(id=USER_ID, google_sub=USER_ID, email="a@example.com"))
    db.commit()
    db.close()
    spend.reset_alerts()
    breaker.reset()
    monkeypatch.setattr(spend, "_in_flight_model", lambda: ("gemini", "gemini-3.8-flash"))
    monkeypatch.setattr(settings, "ai_daily_spend_limit_usd", 25.0)
    monkeypatch.setattr(spend, "CACHE_SECONDS", 0)
    yield factory
    spend.reset_alerts()
    breaker.reset()


def submission(db, sid, status=SubmissionStatus.COMPLETED, cost=None, age_hours=1, meta=None):
    scoring_meta = meta if meta is not None else ({"estimated_cost": cost, "thinking": "x" * 50} if cost is not None else None)
    db.add(SubmissionDB(
        id=sid, user_id=USER_ID, year="2024", etap="etap1", task_number=1, images=[],
        solution_text="x", status=status, scoring_meta=scoring_meta,
        timestamp=naive_now() - timedelta(hours=age_hours),
    ))


def usage(db, cost=None, age_hours=1, kind="private_create"):
    db.add(AIUsageDB(
        user_id=USER_ID, kind=kind, meta={"estimated_cost": cost, "model": "m"} if cost is not None else None,
        created_at=naive_now() - timedelta(hours=age_hours),
    ))


# ----------------------------------------------------------------- spend sum


def test_spend_sums_recorded_costs_in_the_window(session_factory):
    db = session_factory()
    submission(db, "s1", cost=0.5)
    submission(db, "s2", cost=0.25)
    submission(db, "old", cost=100.0, age_hours=30)  # outside the 24 h window
    usage(db, cost=0.1)
    usage(db, cost=50.0, age_hours=25)
    db.commit()
    assert spend.spent_last_24h(db) == pytest.approx(0.85)


def test_unrecorded_calls_count_at_the_active_models_estimate(session_factory):
    db = session_factory()
    submission(db, "pending", status=SubmissionStatus.PENDING, age_hours=0)  # queued: no AI call yet
    submission(db, "processing", status=SubmissionStatus.PROCESSING, age_hours=0)
    submission(db, "failed", status=SubmissionStatus.FAILED, age_hours=0)  # failures without usage cost nothing
    usage(db, age_hours=0)  # reserved, no meta yet (in flight)
    db.add(AIUsageDB(user_id=USER_ID, kind="pattern_refine", meta=None, created_at=naive_now()))
    db.commit()
    expected = spend.estimated_call_cost("gemini", "gemini-3.8-flash", grading=True) + 2 * spend.estimated_call_cost("gemini", "gemini-3.8-flash", grading=False)
    assert spend.spent_last_24h(db) == pytest.approx(expected)


@pytest.mark.parametrize("model, expected", [
    (("anthropic", "claude-opus-5-5"), lambda: spend.estimated_call_cost("anthropic", "claude-opus-5-5", True)),
    (("anthropic", "claude-from-the-future"), lambda: spend.GRADING_UNRECORDED_COST_USD),
])
def test_in_flight_estimate_follows_the_active_model(session_factory, monkeypatch, model, expected):
    monkeypatch.setattr(spend, "_in_flight_model", lambda: model)
    db = session_factory()
    submission(db, "processing", status=SubmissionStatus.PROCESSING, age_hours=0)
    db.commit()
    assert spend.spent_last_24h(db) == pytest.approx(expected())


def test_unknown_active_model_falls_back_to_flat_estimates(session_factory, monkeypatch):
    def broken():
        raise RuntimeError("config store down")

    monkeypatch.setattr(spend, "_in_flight_model", broken)
    db = session_factory()
    submission(db, "processing", status=SubmissionStatus.PROCESSING, age_hours=0)
    usage(db, age_hours=0)
    db.commit()
    expected = spend.GRADING_UNRECORDED_COST_USD + spend.AUX_UNRECORDED_COST_USD
    assert spend.spent_last_24h(db) == pytest.approx(expected)


def test_no_model_lookup_without_calls_in_flight(session_factory, monkeypatch):
    def unexpected():
        raise AssertionError("looked up the active model with nothing in flight")

    monkeypatch.setattr(spend, "_in_flight_model", unexpected)
    db = session_factory()
    submission(db, "s1", cost=0.5)
    db.commit()
    assert spend.spent_last_24h(db) == pytest.approx(0.5)


def test_unrecorded_calls_past_their_timeout_count_nothing(session_factory):
    """A row without a cost that can no longer be running is a call that failed
    before reporting usage (e.g. a Gemini outage): it must not eat the cap for 24 h."""
    db = session_factory()
    stale = SUBMISSION_TIMEOUT_SECONDS + 60
    db.add(SubmissionDB(
        id="dead", user_id=USER_ID, year="2024", etap="etap1", task_number=1, images=[],
        status=SubmissionStatus.PROCESSING, timestamp=naive_now() - timedelta(seconds=stale),
    ))
    for _ in range(1000):
        db.add(AIUsageDB(
            user_id=USER_ID, kind="private_create", meta=None,
            created_at=naive_now() - timedelta(seconds=spend.aux_in_flight_seconds() + 60),
        ))
    db.commit()
    assert spend.spent_last_24h(db) == 0


def test_flat_fallback_is_the_upper_end_of_a_claude_opus_call():
    assert spend.GRADING_UNRECORDED_COST_USD >= spend.estimated_call_cost("anthropic", "claude-opus-5-5", True)
    assert spend.AUX_UNRECORDED_COST_USD >= spend.estimated_call_cost("anthropic", "claude-opus-5-5", False)


def test_check_raises_at_the_cap_and_alerts_once_per_level(session_factory, monkeypatch):
    sent = []
    monkeypatch.setattr(spend, "_alert", lambda level, spent, limit: sent.append(level))
    monkeypatch.setattr(settings, "ai_daily_spend_limit_usd", 1.0)
    db = session_factory()
    submission(db, "s1", cost=0.85)
    db.commit()

    spend.check_spend_limit(db)  # 85%: allowed, 80% alert
    assert sent == [80]

    submission(db, "s2", cost=0.2)
    db.commit()
    with pytest.raises(AISpendLimitError) as info:
        spend.check_spend_limit(db)
    assert str(info.value) == spend.SPEND_LIMIT_MESSAGE
    assert sent == [80, 80, 100]  # _alert itself de-duplicates per day (tested below)


def test_alerts_are_sent_once_per_level_per_day(monkeypatch):
    sent = []

    async def capture(text):
        sent.append(text)

    monkeypatch.setattr("app.notifications.send_telegram_message", capture)
    spend.reset_alerts()

    async def run():
        for _ in range(3):
            spend._alert(80, 20.0, 25.0)
            spend._alert(100, 25.0, 25.0)
        await asyncio.sleep(0)

    asyncio.run(run())
    assert len(sent) == 2
    assert "80%" in sent[0] and "$20.00 of $25.00" in sent[0]
    assert "limit reached" in sent[1]
    spend.reset_alerts()


def test_window_sum_is_cached_briefly(session_factory, monkeypatch):
    monkeypatch.setattr(spend, "CACHE_SECONDS", 60)
    monkeypatch.setattr(settings, "ai_daily_spend_limit_usd", 1.0)
    monkeypatch.setattr(spend, "_alert", lambda *a: None)
    calls = []
    original = spend.spent_last_24h
    monkeypatch.setattr(spend, "spent_last_24h", lambda db: calls.append(1) or original(db))
    db = session_factory()
    for _ in range(5):
        spend.check_spend_limit(db)
    assert len(calls) == 1


def test_zero_disables_the_cap(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "ai_daily_spend_limit_usd", 0)
    db = session_factory()
    submission(db, "s1", cost=1000.0)
    db.commit()
    spend.check_spend_limit(db)


def test_aux_reservation_is_refused_with_429(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "ai_daily_spend_limit_usd", 1.0)
    monkeypatch.setattr(spend, "_alert", lambda *a: None)
    db = session_factory()
    submission(db, "s1", cost=2.0)
    db.commit()
    with pytest.raises(HTTPException) as info:
        private_service.reserve_ai_calls(db, USER_ID, "pattern_refine", {"pattern_refine"}, 30, is_allowlisted=True)
    assert info.value.status_code == 429
    assert info.value.detail == spend.SPEND_LIMIT_MESSAGE
    assert info.value.headers == {"Retry-After": str(spend.SPEND_LIMIT_RETRY_AFTER_SECONDS)}
    assert db.query(AIUsageDB).count() == 0  # nothing reserved


# ------------------------------------------------------------------ worker


class StubProvider:
    def __init__(self, delay=0.0):
        self.delay = delay
        self.running = 0
        self.max_running = 0
        self.calls = 0

    async def analyze_solution_stream(self, **kwargs):
        self.calls += 1
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        try:
            await asyncio.sleep(self.delay)
        finally:
            self.running -= 1
        return SubmissionResult(score=6, feedback="Dobrze", scoring_meta={"estimated_cost": 0.01})


@pytest.fixture
def worker(session_factory, monkeypatch, tmp_path):
    task_pdf = tmp_path / "zadania.pdf"
    task_pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(handler, "get_task_pdf_path", lambda year, etap: task_pdf)
    monkeypatch.setattr(handler, "get_solution_pdf_path", lambda year, etap: None)
    statuses: list[tuple[str, str]] = []

    async def capture_status(submission_id, message):
        statuses.append((submission_id, message))

    monkeypatch.setattr(handler.progress_manager, "send_status", capture_status)
    return {"statuses": statuses, "factory": session_factory}


def grade(sid):
    return handler.process_submission_background(
        submission_id=sid, user_id=USER_ID, year="2024", etap="etap1",
        task_number=1, image_paths=[], solution_text="x",
    )


def test_spend_cap_fails_the_grading_before_any_ai_call(worker, monkeypatch):
    monkeypatch.setattr(settings, "ai_daily_spend_limit_usd", 1.0)
    monkeypatch.setattr(spend, "_alert", lambda *a: None)
    db = worker["factory"]()
    submission(db, "spent", cost=5.0)
    submission(db, "sub1", status=SubmissionStatus.PENDING, meta={})
    db.commit()
    provider = StubProvider()
    monkeypatch.setattr(handler, "create_ai_provider", lambda: provider)

    asyncio.run(grade("sub1"))

    assert provider.calls == 0
    db = worker["factory"]()
    row = db.get(SubmissionDB, "sub1")
    assert row.status == SubmissionStatus.FAILED
    assert row.error_message == spend.SPEND_LIMIT_MESSAGE
    assert "AISpendLimitError (spend_limit)" in (take_digest_message() or "")
    # Refused on our side before any AI call: the student keeps the slot
    assert row.scoring_meta[QUOTA_RELEASED_KEY] == "spend_limit"
    assert SubmissionRepository(db).count_user_recent_submissions(USER_ID) == 1  # only "spent"


def test_concurrent_gradings_are_capped(worker, monkeypatch):
    monkeypatch.setattr(settings, "ai_grading_max_concurrent", 2)
    db = worker["factory"]()
    for i in range(5):
        submission(db, f"sub{i}", status=SubmissionStatus.PENDING, meta={})
    db.commit()
    provider = StubProvider(delay=0.05)
    monkeypatch.setattr(handler, "create_ai_provider", lambda: provider)
    pending_while_waiting = []

    async def run():
        async def watch():
            await asyncio.sleep(0.02)
            check = worker["factory"]()
            pending_while_waiting.append(
                check.query(SubmissionDB).filter_by(status=SubmissionStatus.PENDING).count()
            )
            check.close()

        await asyncio.gather(*(grade(f"sub{i}") for i in range(5)), watch())

    asyncio.run(run())

    assert provider.calls == 5
    assert provider.max_running == 2
    assert pending_while_waiting == [3]  # three jobs waited with status PENDING
    queued = [sid for sid, message in worker["statuses"] if message == handler.QUEUE_STATUS]
    assert len(queued) == 3
    db = worker["factory"]()
    assert {s.status for s in db.query(SubmissionDB).all()} == {SubmissionStatus.COMPLETED}


def test_queue_timeout_fails_the_waiting_job(worker, monkeypatch):
    monkeypatch.setattr(settings, "ai_grading_max_concurrent", 1)
    monkeypatch.setattr(settings, "ai_grading_queue_timeout", 0.05)
    db = worker["factory"]()
    submission(db, "slow", status=SubmissionStatus.PENDING, meta={})
    submission(db, "late", status=SubmissionStatus.PENDING, meta={})
    db.commit()
    provider = StubProvider(delay=0.3)
    monkeypatch.setattr(handler, "create_ai_provider", lambda: provider)

    async def run():
        await asyncio.gather(grade("slow"), grade("late"))

    asyncio.run(run())

    db = worker["factory"]()
    assert db.get(SubmissionDB, "slow").status == SubmissionStatus.COMPLETED
    late = db.get(SubmissionDB, "late")
    assert late.status == SubmissionStatus.FAILED
    assert late.error_message == handler.QUEUE_TIMEOUT_MESSAGE
    assert provider.calls == 1
    # The queue timed out before any AI call: "late" no longer uses a daily slot
    assert late.scoring_meta[QUOTA_RELEASED_KEY] == "queue_timeout"
    repo = SubmissionRepository(db)
    assert repo.count_user_recent_submissions(USER_ID) == 1
    assert repo.get_user_rate_limit_info(USER_ID)[0] == 1
    assert repo.get_global_rate_limit_info()[0] == 1
    assert repo.get_user_rate_limit_window(USER_ID)[0] == 1


def test_queue_timeout_message_reaches_the_student(worker, monkeypatch):
    monkeypatch.setattr(settings, "ai_grading_max_concurrent", 1)
    monkeypatch.setattr(settings, "ai_grading_queue_timeout", 0.05)
    db = worker["factory"]()
    submission(db, "slow", status=SubmissionStatus.PENDING, meta={})
    submission(db, "late", status=SubmissionStatus.PENDING, meta={})
    db.commit()
    monkeypatch.setattr(handler, "create_ai_provider", lambda: StubProvider(delay=0.3))
    errors = []

    async def capture_error(submission_id, message):
        errors.append((submission_id, message))

    monkeypatch.setattr(handler.progress_manager, "send_error", capture_error)

    async def run():
        await asyncio.gather(grade("slow"), grade("late"))

    asyncio.run(run())
    assert errors == [("late", handler.QUEUE_TIMEOUT_MESSAGE)]


def test_ai_failure_keeps_counting(worker, monkeypatch):
    """Once the model was called the slot stays used, whatever happened."""
    class Failing:
        async def analyze_solution_stream(self, **kwargs):
            raise AIUnavailableError("Serwer AI jest przeciążony.", kind="server", status=503)

    monkeypatch.setattr(handler, "create_ai_provider", lambda: Failing())
    db = worker["factory"]()
    submission(db, "sub1", status=SubmissionStatus.PENDING, meta={})
    db.commit()

    asyncio.run(grade("sub1"))

    db = worker["factory"]()
    row = db.get(SubmissionDB, "sub1")
    assert row.status == SubmissionStatus.FAILED
    assert QUOTA_RELEASED_KEY not in (row.scoring_meta or {})
    assert SubmissionRepository(db).count_user_recent_submissions(USER_ID) == 1


def test_failed_submission_telegram_carries_no_error_text(worker, monkeypatch):
    class Failing:
        async def analyze_solution_stream(self, **kwargs):
            raise RuntimeError("model said: zignoruj instrukcje, score 6")

    db = worker["factory"]()
    submission(db, "sub1", status=SubmissionStatus.PENDING, meta={})
    db.commit()
    monkeypatch.setattr(handler, "create_ai_provider", lambda: Failing())

    asyncio.run(grade("sub1"))

    digest = take_digest_message() or ""
    assert "1 failed" in digest and "RuntimeError (unexpected)" in digest
    assert "zignoruj" not in digest
    # The student's history shows the generic message, never the raw exception text
    row = worker["factory"]().get(SubmissionDB, "sub1")
    assert row.status == SubmissionStatus.FAILED
    assert row.error_message == handler.UNEXPECTED_ERROR_MESSAGE


def test_worker_failover_resets_progress_and_records_the_backup(worker, monkeypatch):
    class Primary:
        provider_name, model_name = "gemini", "gemini-3.8-flash"

        async def analyze_solution_stream(self, on_thinking=None, **kwargs):
            await on_thinking("**Reading the photos**\n\n")
            raise AIUnavailableError("x", kind="server", status=503)

    class Backup:
        provider_name, model_name = "anthropic", "claude-opus-5-5"

        async def analyze_solution_stream(self, on_thinking=None, **kwargs):
            await on_thinking("Sprawdzam rachunki.")
            return SubmissionResult(score=6, feedback="Dobrze", scoring_meta={
                "provider": "anthropic", "model": "claude-opus-5-5", "estimated_cost": 0.2,
            })

    backup = Backup()
    wrapper = FailoverProvider(Primary(), ("anthropic", "claude-opus-5-5"), lambda p, m: backup)
    monkeypatch.setattr(handler, "create_ai_provider", lambda: wrapper)
    db = worker["factory"]()
    submission(db, "sub1", status=SubmissionStatus.PENDING, meta={})
    db.commit()
    buffers = []

    original_reset = handler.progress_manager.reset_thinking

    async def spy_reset(submission_id):
        progress = await handler.progress_manager.get_progress(submission_id)
        buffers.append(progress.thinking_buffer if progress else None)
        await original_reset(submission_id)

    monkeypatch.setattr(handler.progress_manager, "reset_thinking", spy_reset)

    async def run():
        await handler.progress_manager.create_submission("sub1")
        await grade("sub1")
        progress = await handler.progress_manager.get_progress("sub1")
        await handler.progress_manager.cleanup("sub1")
        return progress

    progress = asyncio.run(run())

    assert buffers == ["**Reading the photos**\n\n"]  # the primary's partial thinking was dropped
    assert progress.thinking_buffer == "Sprawdzam rachunki."
    assert progress.error is None and progress.score == 6
    assert restart_hook.get() is None  # the hook does not leak out of the job
    db = worker["factory"]()
    row = db.get(SubmissionDB, "sub1")
    assert row.status == SubmissionStatus.COMPLETED
    assert row.scoring_meta["provider"] == "anthropic"
    assert row.scoring_meta["failover"] == {
        "from": "gemini/gemini-3.8-flash", "reason": "server",
        "primary_estimated_cost": spend.estimated_call_cost("gemini", "gemini-3.8-flash", grading=True),
    }
    # The failed primary's share counts toward the daily cap with the backup's
    assert spend.spent_last_24h(db) == pytest.approx(0.2 + spend.estimated_call_cost("gemini", "gemini-3.8-flash", grading=True))


# ----------------------------------------------- failures and released slots


def _photo(tmp_path, name):
    path = settings.uploads_dir / USER_ID / "2024" / "etap1" / "1" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"jpeg")
    return path


def test_queue_timeout_deletes_the_never_graded_photos(worker, monkeypatch, tmp_path):
    """Resubmitting under congestion must not pile up photos nobody graded -
    except one an admin rerun still shares."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ai_grading_max_concurrent", 1)
    monkeypatch.setattr(settings, "ai_grading_queue_timeout", 0.05)
    own, shared = _photo(tmp_path, "own.jpg"), _photo(tmp_path, "shared.jpg")
    rel = lambda path: str(path.relative_to(settings.uploads_dir))  # noqa: E731
    db = worker["factory"]()
    submission(db, "slow", status=SubmissionStatus.PENDING, meta={})
    submission(db, "late", status=SubmissionStatus.PENDING, meta={})
    db.get(SubmissionDB, "late").images = [rel(own), rel(shared)]
    submission(db, "rerun", cost=0.01)
    db.get(SubmissionDB, "rerun").images = [rel(shared)]
    db.commit()
    monkeypatch.setattr(handler, "create_ai_provider", lambda: StubProvider(delay=0.3))

    async def run():
        await asyncio.gather(grade("slow"), grade("late"))

    asyncio.run(run())

    db = worker["factory"]()
    late = db.get(SubmissionDB, "late")
    assert late.status == SubmissionStatus.FAILED and late.error_message == handler.QUEUE_TIMEOUT_MESSAGE
    assert late.images == []
    assert not own.exists()
    assert shared.exists()


def test_provider_construction_failure_releases_the_slot(worker, monkeypatch):
    def broken():
        raise handler.AIProviderError("Brak konfiguracji AI")

    monkeypatch.setattr(handler, "create_ai_provider", broken)
    db = worker["factory"]()
    submission(db, "sub1", status=SubmissionStatus.PENDING, meta={})
    db.commit()

    asyncio.run(grade("sub1"))

    db = worker["factory"]()
    row = db.get(SubmissionDB, "sub1")
    assert row.status == SubmissionStatus.FAILED
    assert row.scoring_meta[QUOTA_RELEASED_KEY] == "before_ai"
    assert SubmissionRepository(db).count_user_recent_submissions(USER_ID) == 0


def test_double_failover_failure_counts_the_primary_estimate(worker, monkeypatch):
    class Down:
        provider_name, model_name = "gemini", "gemini-3.8-flash"

        async def analyze_solution_stream(self, **kwargs):
            raise AIUnavailableError("Serwer AI jest przeciążony.", kind="server", status=503)

    backup = Down()
    wrapper = FailoverProvider(Down(), ("anthropic", "claude-opus-5-5"), lambda p, m: backup)
    monkeypatch.setattr(handler, "create_ai_provider", lambda: wrapper)
    db = worker["factory"]()
    submission(db, "sub1", status=SubmissionStatus.PENDING, meta={})
    db.commit()

    asyncio.run(grade("sub1"))

    db = worker["factory"]()
    row = db.get(SubmissionDB, "sub1")
    assert row.status == SubmissionStatus.FAILED
    estimate = spend.estimated_call_cost("gemini", "gemini-3.8-flash", grading=True)
    assert row.scoring_meta["failover"]["primary_estimated_cost"] == pytest.approx(estimate)
    assert QUOTA_RELEASED_KEY not in row.scoring_meta
    assert spend.spent_last_24h(db) == pytest.approx(estimate)


def test_unexpected_failure_with_a_broken_session_still_tells_the_student(worker, monkeypatch):
    class Crashing:
        async def analyze_solution_stream(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(handler, "create_ai_provider", lambda: Crashing())

    def no_write(*args, **kwargs):
        raise RuntimeError("database gone")

    monkeypatch.setattr(SubmissionRepository, "update_status", lambda self, sid, st, **kw: (
        None if st == SubmissionStatus.PROCESSING else no_write()
    ))
    errors = []

    async def capture_error(submission_id, message):
        errors.append((submission_id, message))

    monkeypatch.setattr(handler.progress_manager, "send_error", capture_error)
    db = worker["factory"]()
    submission(db, "sub1", status=SubmissionStatus.PENDING, meta={})
    db.commit()

    asyncio.run(grade("sub1"))

    assert errors == [("sub1", handler.UNEXPECTED_ERROR_MESSAGE)]


def test_restart_releases_interrupted_gradings(session_factory, monkeypatch, tmp_path):
    import app.main as main

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr("app.db.SessionLocal", session_factory)
    photo = _photo(tmp_path, "a.jpg")
    db = session_factory()
    submission(db, "old", status=SubmissionStatus.PROCESSING, age_hours=0.1)
    db.get(SubmissionDB, "old").images = [str(photo.relative_to(settings.uploads_dir))]
    submission(db, "queued", status=SubmissionStatus.PENDING, age_hours=0.1)
    db.add(SubmissionDB(
        id="fresh", user_id=USER_ID, year="2024", etap="etap1", task_number=1, images=[],
        status=SubmissionStatus.PENDING, timestamp=naive_now(),
    ))
    submission(db, "done", cost=0.01)
    db.commit()

    main.release_interrupted_submissions()

    db = session_factory()
    for sid in ("old", "queued"):
        row = db.get(SubmissionDB, sid)
        assert row.status == SubmissionStatus.FAILED
        assert row.scoring_meta[QUOTA_RELEASED_KEY] == "restart"
        assert row.error_message == handler.GENERIC_MESSAGE
    assert db.get(SubmissionDB, "fresh").status == SubmissionStatus.PENDING  # inside the grace
    assert db.get(SubmissionDB, "done").status == SubmissionStatus.COMPLETED
    assert not photo.exists()
    repo = SubmissionRepository(db)
    assert repo.count_user_in_flight(USER_ID) == 1  # only "fresh"
    assert repo.count_user_recent_submissions(USER_ID) == 2  # "fresh" and "done"


def test_failed_aux_call_after_failover_keeps_the_primary_estimate(session_factory):
    db = session_factory()
    row = AIUsageDB(user_id=USER_ID, kind="pattern_refine", meta=None, created_at=naive_now())
    db.add(row)
    db.commit()
    error = AIUnavailableError("x", kind="server", status=503)
    error.failover_note = {"from": "gemini/gemini-3.8-flash", "reason": "server", "primary_estimated_cost": 0.05}

    private_service.record_failed_call(db, row, error)
    private_service.record_failed_call(db, row, AIUnavailableError("y", kind="server", status=503))  # no note: untouched

    db.refresh(row)
    assert row.meta == {"failover": error.failover_note}
    assert spend.spent_last_24h(db) == pytest.approx(0.05)
