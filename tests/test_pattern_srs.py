"""Spaced repetition for patterns - the notebook's utk/pod/sam/maintenance ladder."""

from datetime import date, datetime, timedelta

import pytest

from app.patterns import srs
from app.patterns.srs import PracticeCandidate

TODAY = date(2026, 10, 1)


@pytest.mark.parametrize(
    "level,streak,outcome,expected",
    [
        (1, 0, "ok", (1, 1, 4)),
        (1, 1, "ok", (2, 0, 7)),
        (2, 0, "ok", (2, 1, 14)),
        (2, 1, "ok", (3, 0, 30)),
        (3, 0, "ok", (3, 1, 90)),
        (3, 1, "ok", (4, 0, 180)),
        (4, 0, "ok", (4, 0, 180)),
        (1, 0, "hard", (1, 0, 1)),
        (2, 1, "hard", (2, 1, 14)),
        (4, 0, "hard", (4, 0, 180)),
        (4, 0, "fail", (2, 0, 7)),
        (3, 1, "fail", (2, 0, 7)),
        (2, 0, "fail", (1, 0, 1)),
        (1, 1, "fail", (1, 0, 1)),
    ],
)
def test_schedule(level, streak, outcome, expected):
    new_level, new_streak, due = srs.schedule(level, streak, outcome, TODAY)
    assert (new_level, new_streak, (due - TODAY).days) == expected


def test_unknown_outcome_rejected():
    with pytest.raises(ValueError):
        srs.schedule(1, 0, "maybe", TODAY)


def test_initial_due_is_tomorrow():
    assert srs.initial_due(TODAY) == TODAY + timedelta(days=1)


@pytest.mark.parametrize(
    "score,max_score,hints,expected",
    [
        (6, 6, 0, "ok"),
        (5, 6, 0, "ok"),
        (6, 6, 2, "hard"),
        (2, 6, 0, "hard"),
        (0, 6, 0, "fail"),
        (3, 3, 0, "ok"),
        (3, 3, 1, "hard"),
        (1, 3, 0, "hard"),
        (0, 3, 1, "fail"),
    ],
)
def test_outcome_from_grade(score, max_score, hints, expected):
    assert srs.outcome_from_grade(score, max_score, hints) == expected


class TestInterleave:
    def test_avoids_same_category_twice(self):
        items = ["a1", "a2", "b1", "a3", "c1"]
        assert srs.interleave(items, key=lambda x: x[0]) == ["a1", "b1", "a2", "c1", "a3"]

    def test_single_category_keeps_order(self):
        assert srs.interleave(["a1", "a2", "a3"], key=lambda x: x[0]) == ["a1", "a2", "a3"]

    def test_empty(self):
        assert srs.interleave([], key=lambda x: x) == []


@pytest.mark.parametrize(
    "review_count,level,expected",
    [(0, 1, False), (1, 1, False), (2, 1, True), (5, 2, True), (3, 3, False), (0, 4, True)],
)
def test_practice_offered(review_count, level, expected):
    assert srs.practice_offered(review_count, level) is expected


class TestChoosePractice:
    NOW = datetime(2026, 10, 1, 12, 0)

    def cand(self, kind, ref, difficulty=None, days_ago=None):
        last = None if days_ago is None else self.NOW - timedelta(days=days_ago)
        return PracticeCandidate(kind=kind, ref=ref, title=ref, difficulty=difficulty, last_attempt=last)

    def test_recent_attempt_excluded(self):
        assert srs.choose_practice([self.cand("omj", "k1", days_ago=10)], self.NOW) is None

    def test_never_attempted_omj_before_private(self):
        chosen = srs.choose_practice(
            [self.cand("private", "p1", difficulty=1), self.cand("omj", "k1", difficulty=5)], self.NOW
        )
        assert chosen.ref == "k1"

    def test_never_attempted_easier_first(self):
        chosen = srs.choose_practice(
            [self.cand("omj", "hard", difficulty=5), self.cand("omj", "easy", difficulty=2)], self.NOW
        )
        assert chosen.ref == "easy"

    def test_never_attempted_beats_attempted(self):
        chosen = srs.choose_practice(
            [self.cand("omj", "old", days_ago=90), self.cand("private", "new")], self.NOW
        )
        assert chosen.ref == "new"

    def test_oldest_attempt_wins(self):
        chosen = srs.choose_practice(
            [self.cand("omj", "k40", days_ago=40), self.cand("omj", "k90", days_ago=90)], self.NOW
        )
        assert chosen.ref == "k90"

    def test_empty(self):
        assert srs.choose_practice([], self.NOW) is None
