import pytest

from app.notifications import take_digest_message


@pytest.fixture(autouse=True)
def _empty_telegram_digest():
    """The digest counters are module state: every test starts from zero."""
    take_digest_message()
    yield
    take_digest_message()


@pytest.fixture(autouse=True)
def _no_background_exercises(monkeypatch):
    """Saving a pattern starts an exercise batch; tests run the batch themselves.

    Started batches stay "running" and their coroutines are dropped unrun. The
    list holds the (batch_id, usage_id) pairs, for tests that want to run one.
    """
    from app.patterns import exercises

    started = []

    def spawn(coro):
        started.append(tuple(coro.cr_frame.f_locals.get(k) for k in ("batch_id", "usage_id")))
        coro.close()

    monkeypatch.setattr(exercises, "spawn", spawn)
    return started
