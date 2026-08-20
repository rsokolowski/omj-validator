"""Retry-After must point at a moment when quota actually frees.

Carried-over quota from an erased account is ONE block released at the
tombstone's expires_at (anchored on the newest submission, so deleting the
account cannot hand the whole daily budget back early). Reporting the oldest
submission behind that block instead told a returning user to retry in an hour,
then answered 429 again - every hour, for the rest of the window.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.main import _calculate_rate_limit_headers, _calculate_retry_after, _rate_limit_reset_anchor

WINDOW = 24
LIMIT = 30


def at(hours: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def reset_of(anchor) -> datetime:
    """The moment the header helpers derive from an anchor."""
    return anchor + timedelta(hours=WINDOW)


class TestNoCarryover:
    def test_no_data_at_all_returns_none(self):
        assert _rate_limit_reset_anchor([], [], limit=LIMIT) is None

    def test_blocks_with_zero_count_are_ignored(self):
        assert _rate_limit_reset_anchor([], [(0, at(5))], limit=LIMIT) is None


class TestCarryoverOnly:
    """The reviewer's scenario: account deleted, signed back in, no live rows."""

    def test_reset_is_the_block_release_not_its_oldest_submission(self):
        expires_at = at(23)  # newest submission was 1h ago -> released in 23h

        anchor = _rate_limit_reset_anchor([], [(30, expires_at)], limit=LIMIT)

        assert reset_of(anchor) == expires_at

    def test_retry_after_spans_the_whole_remaining_window(self):
        expires_at = at(23)

        anchor = _rate_limit_reset_anchor([], [(30, expires_at)], limit=LIMIT)
        retry_after = _calculate_retry_after(anchor, window_hours=WINDOW)

        # ~23h, definitely not the ~1h the old anchor produced
        assert 22 * 3600 < retry_after <= 23 * 3600 + 60

    def test_header_reset_matches_the_release(self):
        expires_at = at(23)

        anchor = _rate_limit_reset_anchor([], [(30, expires_at)], limit=LIMIT)
        headers = _calculate_rate_limit_headers(
            limit=LIMIT, current_count=30, oldest_timestamp=anchor, window_hours=WINDOW
        )

        assert int(headers["X-RateLimit-Reset"]) == int(expires_at.timestamp())
        assert headers["X-RateLimit-Remaining"] == "0"


class TestCarryoverPlusLiveSubmissions:
    def test_a_single_live_slot_is_enough_when_the_block_is_smaller(self):
        """29 carried + 1 live, limit 30: the live one aging out unblocks."""
        live = [at(-20)]  # frees in 4h
        blocks = [(29, at(23))]

        anchor = _rate_limit_reset_anchor(live, blocks, limit=LIMIT)

        assert reset_of(anchor) == live[0] + timedelta(hours=WINDOW)

    def test_live_slots_alone_are_not_enough_when_the_block_fills_the_limit(self):
        """30 carried + 5 live: no number of live expiries helps before release."""
        live = [at(-23), at(-22), at(-21), at(-20), at(-19)]
        blocks = [(30, at(23))]

        anchor = _rate_limit_reset_anchor(live, blocks, limit=LIMIT)

        assert reset_of(anchor) == blocks[0][1]

    def test_partial_relief_picks_the_right_live_submission(self):
        """26 carried + 5 live = 31, limit 30: the count has to reach 29, so TWO
        live submissions must age out - the second one is the answer."""
        live = [at(-23), at(-22), at(-21), at(-20), at(-19)]
        blocks = [(26, at(23))]

        anchor = _rate_limit_reset_anchor(live, blocks, limit=LIMIT)

        assert reset_of(anchor) == live[1] + timedelta(hours=WINDOW)

    def test_reset_never_precedes_a_real_release(self):
        """The bug in one assertion: the answer must be one of the release
        moments, never some earlier timestamp nothing happens at."""
        live = [at(-23), at(-10)]
        blocks = [(28, at(14))]

        anchor = _rate_limit_reset_anchor(live, blocks, limit=LIMIT)
        reset = reset_of(anchor)

        releases = {ts + timedelta(hours=WINDOW) for ts in live} | {blocks[0][1]}
        assert reset in releases

    def test_below_the_limit_reports_the_next_release(self):
        """Informational case: not blocked, so report when the next slot frees."""
        live = [at(-23), at(-2)]
        blocks = [(1, at(20))]

        anchor = _rate_limit_reset_anchor(live, blocks, limit=LIMIT)

        assert reset_of(anchor) == live[0] + timedelta(hours=WINDOW)


class TestSeveralBlocks:
    """The global limit sees one block per erased account."""

    def test_blocks_are_released_independently(self):
        first_release, second_release = at(5), at(18)
        blocks = [(20, first_release), (20, second_release)]

        anchor = _rate_limit_reset_anchor([], blocks, limit=LIMIT)

        # 40 carried, limit 30: the first release (20 freed) already unblocks
        assert reset_of(anchor) == first_release

    def test_the_later_block_matters_when_the_first_is_not_enough(self):
        first_release, second_release = at(5), at(18)
        blocks = [(5, first_release), (30, second_release)]

        anchor = _rate_limit_reset_anchor([], blocks, limit=LIMIT)

        assert reset_of(anchor) == second_release
