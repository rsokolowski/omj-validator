"""Global daily cap on estimated AI spend (AI_DAILY_SPEND_LIMIT_USD).

Checked before every AI call a student can trigger: the grading worker before
it calls the model, and reserve_ai_calls (extraction, hints, patterns) before
it reserves. The spend is the sum of the estimated costs already recorded in
the rolling 24 h window:

- submissions.scoring_meta["estimated_cost"] (written by the grading worker);
- ai_usage.meta["estimated_cost"] (the routes store the provider's usage meta).

No migration and no new column: both tables already carry the provider's own
estimate. A row without one that is young enough to still be in flight is
counted at a conservative flat estimate, so a burst of parallel calls cannot
overshoot the cap before the first one reports. Older rows without a cost are
calls that failed before reporting usage and count as 0 - most failures
(quota, timeouts before an answer, this cap itself) cost nothing, and counting
them would let an outage push the spend up on its own. Failed submissions
without a recorded cost count as 0 at any age.

A call that failed over (failover.py) also carries the primary's share in
``failover.primary_estimated_cost``: the backup's usage is what the provider
reports, the primary's is an estimate.

Estimates, never billing: the provider dashboards stay the source of truth.
"""

import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import settings
from ..db.models import AIUsageDB, SubmissionDB, SubmissionStatus
from ..db.repositories import SUBMISSION_TIMEOUT_SECONDS
from .factory import AISpendLimitError

logger = logging.getLogger(__name__)

# Flat estimates for calls without a recorded cost (in flight). Grading: the
# upper end of a Claude grading (docs/model-ab-playbook.md: $0.20-0.40 with
# Opus), so a failover burst is not underestimated; Gemini Flash costs
# ~$0.01-0.03. Aux calls are text-only and short.
GRADING_UNRECORDED_COST_USD = 0.40
AUX_UNRECORDED_COST_USD = 0.02

# Where failover.py notes its estimate of the failed primary call's cost
FAILOVER_PRIMARY_COST_PATH = ("failover", "primary_estimated_cost")

ALERT_LEVELS = (80, 100)  # percent of the cap; one Telegram alert each per UTC day
WINDOW_HOURS = 24

SPEND_LIMIT_MESSAGE = (
    "Na dziś wyczerpał się limit korzystania z AI w aplikacji. "
    "Spróbuj ponownie za kilka godzin."
)

# The spend window is rolling; an hour is a fair "come back later"
SPEND_LIMIT_RETRY_AFTER_SECONDS = 3600

# The window sum is cached briefly: it runs before every AI call, and the
# submissions scan is not indexed by time. A burst can overshoot the cap by
# at most this many seconds' worth of new calls.
CACHE_SECONDS = 15.0

_alert_lock = threading.Lock()
_alerted: set[tuple[date, int]] = set()
_cached: Optional[tuple[float, float]] = None  # (time.monotonic(), spent)


def reset_alerts() -> None:
    """Forget sent alerts and the cached sum (tests)."""
    global _cached
    with _alert_lock:
        _alerted.clear()
        _cached = None


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def aux_in_flight_seconds() -> int:
    """How long an aux call (extraction, hints, patterns) can still be running:
    the primary's timeout, the backup's after a failover, and a margin."""
    return settings.gemini_timeout + settings.anthropic_timeout + 60


def spent_last_24h(db: Session, now: Optional[datetime] = None) -> float:
    """Estimated USD spent on AI calls in the rolling window (see module docstring)."""
    now = now or _naive_utc_now()
    since = now - timedelta(hours=WINDOW_HOURS)

    submission_cost = SubmissionDB.scoring_meta["estimated_cost"].as_float()
    submission_primary = SubmissionDB.scoring_meta[FAILOVER_PRIMARY_COST_PATH].as_float()
    recorded_grading = (
        db.query(
            func.coalesce(func.sum(submission_cost), 0.0) + func.coalesce(func.sum(submission_primary), 0.0)
        )
        .filter(SubmissionDB.timestamp >= since)
        .scalar()
    )
    # A PENDING/PROCESSING row older than this is a dead worker's, not a grading
    in_flight = (
        db.query(func.count(SubmissionDB.id))
        .filter(
            SubmissionDB.timestamp >= now - timedelta(seconds=SUBMISSION_TIMEOUT_SECONDS),
            SubmissionDB.status.in_([SubmissionStatus.PENDING, SubmissionStatus.PROCESSING]),
            or_(SubmissionDB.scoring_meta.is_(None), submission_cost.is_(None)),
        )
        .scalar()
    )

    usage_cost = AIUsageDB.meta["estimated_cost"].as_float()
    usage_primary = AIUsageDB.meta[FAILOVER_PRIMARY_COST_PATH].as_float()
    recorded_aux = (
        db.query(func.coalesce(func.sum(usage_cost), 0.0) + func.coalesce(func.sum(usage_primary), 0.0))
        .filter(AIUsageDB.created_at >= since)
        .scalar()
    )
    unrecorded_aux = (
        db.query(func.count(AIUsageDB.id))
        .filter(
            AIUsageDB.created_at >= now - timedelta(seconds=aux_in_flight_seconds()),
            or_(AIUsageDB.meta.is_(None), usage_cost.is_(None)),
        )
        .scalar()
    )
    return (
        float(recorded_grading or 0)
        + float(recorded_aux or 0)
        + (in_flight or 0) * GRADING_UNRECORDED_COST_USD
        + (unrecorded_aux or 0) * AUX_UNRECORDED_COST_USD
    )


def _alert(level: int, spent: float, limit: float) -> None:
    """One Telegram message per level per UTC day; fire-and-forget."""
    key = (datetime.now(timezone.utc).date(), level)
    with _alert_lock:
        if key in _alerted:
            return
        _alerted.add(key)
    logger.warning(f"[AI spend] {level}% of the daily limit: ${spent:.2f} of ${limit:.2f}")
    from ..notifications import build_spend_message, send_telegram_in_background

    send_telegram_in_background(build_spend_message(level, spent, limit))


def _spent_cached(db: Session) -> float:
    global _cached
    now = time.monotonic()
    with _alert_lock:
        if _cached is not None and now - _cached[0] < CACHE_SECONDS:
            return _cached[1]
    spent = spent_last_24h(db)
    with _alert_lock:
        _cached = (now, spent)
    return spent


def check_spend_limit(db: Session) -> None:
    """Raise AISpendLimitError when the window's spend has reached the cap (0 = off).

    Also sends the 80% / 100% alerts. Never raises for any other reason: a
    failing query must not stop grading, so it is logged and let through.
    """
    limit = settings.ai_daily_spend_limit_usd
    if not limit or limit <= 0:
        return
    try:
        spent = _spent_cached(db)
    except Exception as e:
        logger.error(f"[AI spend] Could not compute spend ({type(e).__name__}) - not enforcing")
        try:
            db.rollback()
        except Exception:
            pass
        return
    percent = spent / limit * 100
    for level in ALERT_LEVELS:
        if percent >= level:
            _alert(level, spent, limit)
    if spent >= limit:
        logger.warning(f"[AI spend] Limit reached (${spent:.2f} / ${limit:.2f}) - AI call refused")
        raise AISpendLimitError(SPEND_LIMIT_MESSAGE)


def spend_limit_http_error(db: Session) -> Optional[HTTPException]:
    """The 429 for a request refused by the cap (check_spend_limit), else None.

    One message and Retry-After for every route; the body is
    {"detail": message} as raised, or the caller re-wraps ``detail`` in its
    own shape (submit answers {"error"}).
    """
    try:
        check_spend_limit(db)
    except AISpendLimitError as e:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": str(SPEND_LIMIT_RETRY_AFTER_SECONDS)},
        )
    return None
