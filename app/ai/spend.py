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

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..config import settings
from ..db.models import AIUsageDB, SubmissionDB, SubmissionStatus
from ..db.repositories import SUBMISSION_TIMEOUT_SECONDS
from .factory import AISpendLimitError

logger = logging.getLogger(__name__)

# Estimate for a call without a recorded cost (in flight, or a failed-over
# primary): the model's own catalog price for a nominal call at the upper end
# of what we see (docs/model-ab-playbook.md: ~15k input and 5-15k output
# tokens per grading, thinking billed as output). That is ~$0.38 for Claude
# Opus 5.5 and ~$0.07-0.14 for Gemini Flash. Aux calls (extraction, hints,
# patterns) are shorter.
GRADING_NOMINAL_TOKENS = (20_000, 15_000)  # (input, output incl. thinking)
AUX_NOMINAL_TOKENS = (6_000, 3_000)
# Flat fallbacks, only for a model without a price in the catalog: the upper
# end of a Claude Opus call, so an unknown model is never underestimated
GRADING_UNRECORDED_COST_USD = 0.40
AUX_UNRECORDED_COST_USD = 0.10

# Where failover.py notes its estimate of the failed primary call's cost
FAILOVER_PRIMARY_COST_PATH = ("failover", "primary_estimated_cost")

ALERT_LEVELS = (80, 100)  # percent of the cap; one Telegram alert each per UTC day
WINDOW_HOURS = 24

SPEND_LIMIT_MESSAGE = (
    "Na dziś wyczerpał się limit korzystania z AI w aplikacji. "
    "Spróbuj ponownie za kilka godzin."
)

# The spend window is rolling; an hour is a fair "come back later". Callers
# answer a refused request with SPEND_LIMIT_MESSAGE and this Retry-After.
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


def estimated_call_cost(provider: str, model: str, grading: bool) -> float:
    """Conservative cost of one call to this model, before it reports usage."""
    from .models_catalog import estimate_cost, get_model

    fallback = GRADING_UNRECORDED_COST_USD if grading else AUX_UNRECORDED_COST_USD
    if get_model(provider, model) is None:
        return fallback
    input_tokens, output_tokens = GRADING_NOMINAL_TOKENS if grading else AUX_NOMINAL_TOKENS
    cost = estimate_cost(provider, model, input_tokens, output_tokens)
    return cost if cost > 0 else fallback


def _in_flight_model() -> tuple[str, str]:
    """The model new calls go to (factory.resolve_active). A call that fails
    over mid-flight is accounted afterwards from its recorded meta."""
    from .factory import resolve_active

    effective, _ = resolve_active()
    return effective.provider, effective.model


def _unit_costs() -> tuple[float, float]:
    """(grading, aux) estimate for one call in flight; flat when the model is unknown."""
    try:
        provider, model = _in_flight_model()
    except Exception as e:
        logger.warning(f"[AI spend] Active model unknown ({type(e).__name__}) - flat estimates")
        return GRADING_UNRECORDED_COST_USD, AUX_UNRECORDED_COST_USD
    return estimated_call_cost(provider, model, True), estimated_call_cost(provider, model, False)


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
    # Only PROCESSING rows can be calling a model (at most
    # AI_GRADING_MAX_CONCURRENT); PENDING ones wait in the queue and check the
    # cap themselves once they get a slot. Older than SUBMISSION_TIMEOUT_SECONDS
    # is a dead worker's row, not a grading.
    in_flight = (
        db.query(func.count(SubmissionDB.id))
        .filter(
            SubmissionDB.timestamp >= now - timedelta(seconds=SUBMISSION_TIMEOUT_SECONDS),
            SubmissionDB.status == SubmissionStatus.PROCESSING,
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
            # A failover note without a cost is a finished (double-failed) call
            or_(AIUsageDB.meta.is_(None), and_(usage_cost.is_(None), usage_primary.is_(None))),
        )
        .scalar()
    )
    total = float(recorded_grading or 0) + float(recorded_aux or 0)
    if in_flight or unrecorded_aux:
        grading_unit, aux_unit = _unit_costs()
        total += (in_flight or 0) * grading_unit + (unrecorded_aux or 0) * aux_unit
    return total


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

