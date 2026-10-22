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


# ------------------------------------------------------------ exercise reviews


@dataclass
class ExerciseState:
    """A generated exercise of a pattern and how its last review went."""

    id: str
    level: str  # "easy" | "medium"
    created_at: datetime
    last_outcome: Optional[str] = None  # "ok" | "hard" | "fail"; None = never reviewed
    last_reviewed_at: Optional[datetime] = None


# Up to this SRS level easy exercises come first; above it, medium ones
EASY_FIRST_MAX_LEVEL = 2
# From this SRS level on the trigger is hidden until the student asks for it
TRIGGER_HIDDEN_FROM_LEVEL = 2


def _tier(state: ExerciseState) -> int:
    if state.last_outcome is None:
        return 0
    return 1 if state.last_outcome == "fail" else 2


def choose_exercise(states: list[ExerciseState], srs_level: int) -> Optional[ExerciseState]:
    """The exercise for today's card: never reviewed, then failed, then the rest.

    Within a tier the preferred level (easy at levels 1-2, medium above) comes
    first, then the one reviewed (or created) longest ago. Deterministic, so a
    reload before rating shows the same exercise.
    """
    if not states:
        return None
    preferred = "easy" if srs_level <= EASY_FIRST_MAX_LEVEL else "medium"
    return min(
        states,
        key=lambda s: (_tier(s), s.level != preferred, s.last_reviewed_at or s.created_at, s.created_at, s.id),
    )


def unseen_count(states: list[ExerciseState]) -> int:
    return sum(1 for s in states if s.last_outcome is None)


def trigger_hidden(srs_level: int) -> bool:
    """A familiar pattern (level 2+) shows its trigger only on request."""
    return srs_level >= TRIGGER_HIDDEN_FROM_LEVEL


def capped_outcome(outcome: str, srs_level: int, trigger_shown: bool) -> str:
    """Peeking at a hidden trigger caps the review at "hard"."""
    if outcome == "ok" and trigger_shown and trigger_hidden(srs_level):
        return "hard"
    return outcome
