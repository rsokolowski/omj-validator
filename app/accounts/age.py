"""Age arithmetic for the registration step.

We ask for the year of birth only (minimisation). In Poland a child can
consent alone from 16 (art. 8 RODO + art. 8 of the 2018 act), so a child who
turns 16 this calendar year is ambiguous and is asked "Czy masz już ukończone
16 lat?".
"""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

AGE_OF_CONSENT = 16
MIN_AGE = 6
MAX_AGE = 100

_WARSAW = ZoneInfo("Europe/Warsaw")


def current_year() -> int:
    return datetime.now(_WARSAW).year


def allowed_birth_years(year: Optional[int] = None) -> range:
    """Years offered in the select: current-100 ... current-6 (inclusive)."""
    year = current_year() if year is None else year
    return range(year - MAX_AGE, year - MIN_AGE + 1)


def is_ambiguous(birth_year: int, year: Optional[int] = None) -> bool:
    """True when the child turns 16 this calendar year (ask the follow-up)."""
    year = current_year() if year is None else year
    return year - birth_year == AGE_OF_CONSENT


class AgeAnswerError(ValueError):
    """The year is out of range or the follow-up answer is missing."""


def can_consent_alone(
    birth_year: int, turned_16: Optional[bool] = None, year: Optional[int] = None
) -> bool:
    """Whether the user is 16 or older, i.e. may consent without a parent.

    Raises AgeAnswerError for a year outside the offered range, or when the
    year is ambiguous and ``turned_16`` was not answered.
    """
    year = current_year() if year is None else year
    if birth_year not in allowed_birth_years(year):
        raise AgeAnswerError("birth_year out of range")
    age_this_year = year - birth_year
    if age_this_year > AGE_OF_CONSENT:
        return True
    if age_this_year < AGE_OF_CONSENT:
        return False
    if turned_16 is None:
        raise AgeAnswerError("turned_16 required")
    return bool(turned_16)
