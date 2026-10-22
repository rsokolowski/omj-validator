"""Spaced repetition for patterns - the notebook's utk/pod/sam/maintenance ladder."""

from datetime import date, datetime, timedelta

import pytest

from app.patterns import srs
from app.patterns.srs import ExerciseState

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


class TestInterleave:
    def test_avoids_same_category_twice(self):
        items = ["a1", "a2", "b1", "a3", "c1"]
        assert srs.interleave(items, key=lambda x: x[0]) == ["a1", "b1", "a2", "c1", "a3"]

    def test_single_category_keeps_order(self):
        assert srs.interleave(["a1", "a2", "a3"], key=lambda x: x[0]) == ["a1", "a2", "a3"]

    def test_empty(self):
        assert srs.interleave([], key=lambda x: x) == []


class TestChooseExercise:
    BASE = datetime(2026, 10, 1, 12, 0)

    def ex(self, id, level="easy", created=0, outcome=None, reviewed=None):
        return ExerciseState(
            id=id,
            level=level,
            created_at=self.BASE + timedelta(minutes=created),
            last_outcome=outcome,
            last_reviewed_at=None if reviewed is None else self.BASE + timedelta(days=reviewed),
        )

    def test_unseen_beats_failed_beats_solved(self):
        states = [self.ex("ok", outcome="ok", reviewed=1), self.ex("fail", outcome="fail", reviewed=2), self.ex("new")]
        assert srs.choose_exercise(states, 1).id == "new"
        assert srs.choose_exercise(states[:2], 1).id == "fail"

    def test_unseen_oldest_first(self):
        states = [self.ex("b", created=5), self.ex("a", created=1)]
        assert srs.choose_exercise(states, 1).id == "a"

    def test_reviewed_longest_ago_first(self):
        states = [self.ex("recent", outcome="hard", reviewed=9), self.ex("old", outcome="ok", reviewed=3)]
        assert srs.choose_exercise(states, 1).id == "old"
        failed = [self.ex("f2", outcome="fail", reviewed=8), self.ex("f1", outcome="fail", reviewed=4)]
        assert srs.choose_exercise(failed, 1).id == "f1"

    def test_level_preference(self):
        states = [self.ex("easy", "easy", created=2), self.ex("medium", "medium", created=1)]
        assert srs.choose_exercise(states, 1).id == "easy"
        assert srs.choose_exercise(states, 2).id == "easy"
        assert srs.choose_exercise(states, 3).id == "medium"
        assert srs.choose_exercise(states, 4).id == "medium"

    def test_tier_before_level(self):
        # An unseen medium exercise beats a failed easy one at level 1
        states = [self.ex("easy-failed", "easy", outcome="fail", reviewed=1), self.ex("medium-new", "medium")]
        assert srs.choose_exercise(states, 1).id == "medium-new"

    def test_empty_and_deterministic(self):
        assert srs.choose_exercise([], 1) is None
        states = [self.ex("x", created=1), self.ex("y", created=1)]
        assert srs.choose_exercise(states, 1).id == srs.choose_exercise(list(reversed(states)), 1).id

    def test_unseen_count(self):
        assert srs.unseen_count([self.ex("a"), self.ex("b", outcome="ok", reviewed=1), self.ex("c")]) == 2


@pytest.mark.parametrize("level,hidden", [(1, False), (2, True), (3, True), (4, True)])
def test_trigger_hidden(level, hidden):
    assert srs.trigger_hidden(level) is hidden


@pytest.mark.parametrize(
    "outcome,level,shown,expected",
    [
        ("ok", 2, True, "hard"),
        ("ok", 4, True, "hard"),
        ("ok", 1, True, "ok"),
        ("ok", 3, False, "ok"),
        ("hard", 3, True, "hard"),
        ("fail", 3, True, "fail"),
    ],
)
def test_capped_outcome(outcome, level, shown, expected):
    assert srs.capped_outcome(outcome, level, shown) == expected
