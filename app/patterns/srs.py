"""Spaced repetition for patterns - pure functions, no database.

Modelled on the student's paper notebook: three levels (after "stuck", "with a
hint", "alone") with two intervals each, then maintenance. Two successes in a
row move a pattern up a level, a failure moves it down, "hard" repeats the
current interval.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Optional, TypeVar
from zoneinfo import ZoneInfo

INTERVALS = {1: (1, 4), 2: (7, 14), 3: (30, 90)}
MAINTENANCE = 4
MAINTENANCE_DAYS = 180
OUTCOMES = ("fail", "hard", "ok")

# A practice task attempted this recently is not offered again
PRACTICE_COOLDOWN_DAYS = 30

_WARSAW = ZoneInfo("Europe/Warsaw")

T = TypeVar("T")


def today_warsaw() -> date:
    """Review dates are calendar days where the students live."""
    return datetime.now(_WARSAW).date()


def initial_due(today: date) -> date:
    """A new pattern is first reviewed tomorrow."""
    return today + timedelta(days=1)


def _interval(level: int, streak: int) -> int:
    if level >= MAINTENANCE:
        return MAINTENANCE_DAYS
    return INTERVALS[level][streak]


def schedule(level: int, streak: int, outcome: str, today: date) -> tuple[int, int, date]:
    """(level, streak, due_on) after a review with ``outcome``."""
    if outcome not in OUTCOMES:
        raise ValueError(f"Unknown outcome: {outcome!r}")

    if outcome == "ok":
        if level >= MAINTENANCE:
            new_level, new_streak = MAINTENANCE, 0
        elif streak == 0:
            new_level, new_streak = level, 1
        else:
            new_level, new_streak = level + 1, 0
    elif outcome == "hard":
        new_level, new_streak = level, streak
    else:  # fail
        new_level = 2 if level >= 3 else 1
        new_streak = 0

    return new_level, new_streak, today + timedelta(days=_interval(new_level, new_streak))


def outcome_from_grade(score: int, max_score: int, hints_used: int) -> str:
    """Outcome of a graded practice task.

    Solved = 5-6 of 6 points, or 3 of 3 (etap1 scale). Solved without hints is
    "ok"; solved with hints, or partial credit, is "hard"; zero is "fail".
    """
    if score <= 0:
        return "fail"
    solved = score >= max_score if max_score <= 3 else score >= max_score - 1
    if solved and hints_used == 0:
        return "ok"
    return "hard"


def interleave(items: list[T], key: Callable[[T], object]) -> list[T]:
    """Keep the order, but avoid the same key twice in a row when possible."""
    remaining = list(items)
    result: list[T] = []
    while remaining:
        index = 0
        if result:
            previous = key(result[-1])
            index = next((i for i, item in enumerate(remaining) if key(item) != previous), 0)
        result.append(remaining.pop(index))
    return result


def practice_offered(review_count: int, level: int) -> bool:
    """Every third review, and always in maintenance, offer a graded task."""
    return level >= MAINTENANCE or review_count % 3 == 2


@dataclass
class PracticeCandidate:
    kind: str  # "omj" | "private"
    ref: str  # OMJ task key or private task id
    title: str
    difficulty: Optional[int]
    last_attempt: Optional[datetime]


def choose_practice(candidates: list[PracticeCandidate], now: datetime) -> Optional[PracticeCandidate]:
    """The task to offer: never attempted first, else the longest ago."""
    cutoff = now - timedelta(days=PRACTICE_COOLDOWN_DAYS)
    eligible = [c for c in candidates if c.last_attempt is None or c.last_attempt < cutoff]
    fresh = [c for c in eligible if c.last_attempt is None]
    if fresh:
        return min(
            fresh,
            key=lambda c: (c.kind != "omj", c.difficulty if c.difficulty is not None else 99, c.ref),
        )
    if eligible:
        return min(eligible, key=lambda c: c.last_attempt)
    return None
