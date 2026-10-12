import pytest

from app.notifications import take_digest_message


@pytest.fixture(autouse=True)
def _empty_telegram_digest():
    """The digest counters are module state: every test starts from zero."""
    take_digest_message()
    yield
    take_digest_message()
