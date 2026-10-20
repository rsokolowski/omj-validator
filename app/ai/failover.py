"""Automatic failover from the active AI provider to a backup (AI_FAILOVER_MODEL).

create_ai_provider() wraps the active provider in a FailoverProvider when a
backup is usable (factory.failover_target): failover enabled, the backup model
in the catalog, from ANOTHER provider, with its key set and - for Anthropic -
ANTHROPIC_PROCESSOR_APPROVED. Otherwise the plain provider is returned and
nothing here runs: with the GDPR gate closed behaviour is exactly as without
failover.

What fails over - fail closed: only an AIUnavailableError whose cause a
student cannot produce with what they send (``fails_over``): 401/403 (key,
billing, region), 404 (model), 429, 502/503/504/529 and a connection that
could not be established. Never a content/safety block (prompt-level or
finish_reason), an abuse verdict, an empty/unreadable/unparseable answer, any
other 400 - a second provider must not become a way around the first one's
safety filters. At most one failover per call.

Timeouts, 500 INTERNAL and connections dropped mid-request are the
ambiguous case: a request's own content can cause them (oversized input,
thinking that never ends, an input the model chokes on). Rule: they NEVER
fail the request that hit them over (it gets the timeout/error message), but
they count toward the breaker like any transient failure. Only a run of
AI_FAILOVER_BREAKER_THRESHOLD consecutive failures across all requests (any
success resets it) opens the breaker - i.e. when the primary is failing for
other requests too. Worst case a student who times out several requests in
a row with no other grading succeeding in between routes traffic to the
backup for a while: a cost/routing effect, not a bypass - the backup applies
its own refusals and the same abuse/maths gates on its answer.

Streaming grading: the primary may fail after thinking chunks were already
streamed. The grading worker registers a restart hook (``restart_hook``
context variable, set per asyncio task) that resets its partial progress;
the backup then grades from scratch and the student sees progress continue.

Circuit breaker (in-process; production runs one worker): a permanent-looking
error (401/403/404) opens it at once, transient ones (429/5xx/network/timeout) after
AI_FAILOVER_BREAKER_THRESHOLD in a row. While open, calls go straight to the
backup for AI_FAILOVER_BREAKER_MINUTES; afterwards the next call tries the
primary again (one more failure re-opens it, a success closes it).

Limits: callers reserve/count a request once, before calling - a failover
inside the call never counts twice. scoring_meta / ai_usage.meta carry the
provider and model that actually answered (the providers' own usage meta)
plus ``failover: {"from", "reason", "primary_estimated_cost"}``. The failed
primary call reports no usage, so its cost is estimated for the daily spend
cap (spend.py): 502/503/504 can come mid-stream after tokens were generated
and count at the flat in-flight estimate; 401/403/404/429 and a connection
never made are refused before any work and count 0.
"""

import logging
import math
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

from ..config import settings
from .factory import UNAVAILABLE_SERVER, AIUnavailableError

if TYPE_CHECKING:
    from .protocol import AIProvider

logger = logging.getLogger(__name__)

# Set by the grading worker for its own task: called before the backup
# re-runs a streaming grading, to drop the primary's partial progress.
restart_hook: ContextVar[Optional[Callable[[], Awaitable[None]]]] = ContextVar(
    "ai_failover_restart_hook", default=None
)

Key = tuple[str, str]  # (provider, model)


def label(key: Key) -> str:
    return f"{key[0]}/{key[1]}"


@dataclass
class _Entry:
    failures: int = 0           # consecutive availability failures
    open_until: float = 0.0     # time.monotonic()
    last_error: str = ""        # "auth 403" - kind and status, never a message
    last_alert: float = -math.inf


class CircuitBreaker:
    """Per (provider, model) breaker. Thread-safe; no I/O under the lock."""

    def __init__(self):
        self._lock = threading.Lock()
        self._entries: dict[Key, _Entry] = {}

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()

    @staticmethod
    def _period() -> float:
        return max(0, settings.ai_failover_breaker_minutes) * 60.0

    def is_open(self, key: Key) -> bool:
        with self._lock:
            entry = self._entries.get(key)
            return bool(entry and entry.open_until > time.monotonic())

    def record_failure(self, key: Key, error: AIUnavailableError) -> bool:
        """Count a failure; True when this one opened the breaker."""
        now = time.monotonic()
        with self._lock:
            entry = self._entries.setdefault(key, _Entry())
            entry.failures += 1
            entry.last_error = f"{error.kind} {error.status}" if error.status else error.kind
            if error.permanent or entry.failures >= max(1, settings.ai_failover_breaker_threshold):
                was_open = entry.open_until > now
                entry.open_until = now + self._period()
                return not was_open
            return False

    def record_success(self, key: Key) -> None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                entry.failures = 0
                entry.open_until = 0.0

    def claim_alert(self, key: Key) -> bool:
        """True at most once per breaker period per key (Telegram rate limit)."""
        now = time.monotonic()
        with self._lock:
            entry = self._entries.setdefault(key, _Entry())
            if now - entry.last_alert < max(self._period(), 60.0):
                return False
            entry.last_alert = now
            return True

    def state(self, key: Key) -> dict:
        """For /admin/settings: state, until when (UTC ISO), failures in a row, last error."""
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key) or _Entry()
            remaining = entry.open_until - now
            failures, last_error = entry.failures, entry.last_error
        is_open = remaining > 0
        return {
            "state": "open" if is_open else "closed",
            "open_until": (
                (datetime.now(timezone.utc) + timedelta(seconds=remaining)).isoformat() if is_open else None
            ),
            "consecutive_failures": failures,
            "last_error": last_error or None,
        }


breaker = CircuitBreaker()


def _alert(primary: Key, fallback: Key, error: AIUnavailableError, opened: bool) -> None:
    """Telegram message (error class/kind only), fire-and-forget.

    The breaker opening is always reported - exactly once, record_failure
    returns True only for the call that opened it. A single failover that
    leaves the breaker closed is rate-limited to one message per breaker
    period, on its own counter, so it can never swallow the opening alert.
    """
    if not opened and not breaker.claim_alert(primary):
        return
    from ..notifications import build_failover_message, send_telegram_in_background

    minutes = settings.ai_failover_breaker_minutes if opened else 0
    send_telegram_in_background(build_failover_message(label(primary), label(fallback), error, minutes))


_GRADING_METHODS = frozenset({"analyze_solution", "analyze_solution_stream", "analyze_private_solution_stream"})


def _primary_cost_estimate(method: str, error: Optional[AIUnavailableError], primary: Key) -> float:
    """What the failed primary call may have cost (it reports no usage): the
    primary model's nominal call (spend.estimated_call_cost)."""
    if error is None or error.kind != UNAVAILABLE_SERVER:
        return 0.0  # breaker open (not called) or refused before any work
    from .spend import estimated_call_cost

    return estimated_call_cost(primary[0], primary[1], grading=method in _GRADING_METHODS)


def _note(primary: Key, reason: str, primary_cost: float = 0.0) -> dict:
    return {"from": label(primary), "reason": reason, "primary_estimated_cost": primary_cost}


def failure_meta(error: BaseException) -> Optional[dict]:
    """Meta to store for a call that failed after a failover ({"failover": note}),
    so the failed primary's estimated cost still counts toward the daily cap;
    None for any other failure."""
    note = getattr(error, "failover_note", None)
    return {"failover": note} if note else None


def _mark(result: Any, primary: Key, reason: str, primary_cost: float = 0.0) -> Any:
    """Note the failover in the result's meta (the backup's own meta names provider + model)."""
    note = _note(primary, reason, primary_cost)
    if hasattr(result, "scoring_meta"):
        result.scoring_meta = {**(result.scoring_meta or {}), "failover": note}
    elif hasattr(result, "meta"):
        result.meta = {**(result.meta or {}), "failover": note}
    return result


class FailoverProvider:
    """An AIProvider that hands a call to the backup when the primary is unavailable."""

    def __init__(self, primary: "AIProvider", fallback: Key, build: Callable[[str, str], "AIProvider"]):
        self.primary = primary
        self.fallback_key = fallback
        self._build = build  # factory's cached constructor
        self.provider_name = primary.provider_name
        self.model_name = primary.model_name

    @property
    def primary_key(self) -> Key:
        return (self.primary.provider_name, self.primary.model_name)

    def get_timeout(self) -> int:
        return self.primary.get_timeout()

    async def ping(self) -> None:
        await self.primary.ping()

    def _fallback(self) -> Optional["AIProvider"]:
        try:
            return self._build(*self.fallback_key)
        except Exception as e:
            logger.error(f"[AI failover] Backup {label(self.fallback_key)} not available: {type(e).__name__}")
            return None

    async def _call(self, method: str, *args, **kwargs):
        primary = self.primary_key
        if breaker.is_open(primary):
            fallback = self._fallback()
            if fallback is not None:
                logger.info(f"[AI failover] Breaker open for {label(primary)} - {method} on {label(self.fallback_key)}")
                result = await getattr(fallback, method)(*args, **kwargs)
                return _mark(result, primary, "breaker_open")
        try:
            result = await getattr(self.primary, method)(*args, **kwargs)
        except AIUnavailableError as error:
            opened = breaker.record_failure(primary, error)
            if not error.fails_over:
                # Timeout / 500 / dropped connection: this request's own content
                # may have caused it, so it fails closed. The breaker - fed by
                # every request - still opens on a run of them.
                logger.warning(
                    f"[AI failover] {label(primary)} {error.kind} (status={error.status}) on {method} - "
                    f"not failed over (content-dependent){'; breaker opened' if opened else ''}"
                )
                if opened:
                    _alert(primary, self.fallback_key, error, opened=True)
                raise
            fallback = self._fallback()
            if fallback is None:
                raise
            logger.warning(
                f"[AI failover] {label(primary)} unavailable ({error.kind}, status={error.status}, "
                f"{error.error_class or type(error).__name__}) - {method} on {label(self.fallback_key)}"
            )
            _alert(primary, self.fallback_key, error, opened)
            hook = restart_hook.get()
            if hook is not None:
                await hook()
            primary_cost = _primary_cost_estimate(method, error, primary)
            try:
                result = await getattr(fallback, method)(*args, **kwargs)
            except Exception as backup_error:
                # Both failed: the caller stores failure_meta(backup_error) on
                # the FAILED submission / ai_usage row, so the primary's share counts
                backup_error.failover_note = _note(primary, error.kind, primary_cost)
                raise
            return _mark(result, primary, error.kind, primary_cost)
        breaker.record_success(primary)
        return result

    # ---------------------------------------------------- AIProvider methods

    async def analyze_solution(self, *args, **kwargs):
        return await self._call("analyze_solution", *args, **kwargs)

    async def analyze_solution_stream(self, *args, **kwargs):
        return await self._call("analyze_solution_stream", *args, **kwargs)

    async def analyze_private_solution_stream(self, *args, **kwargs):
        return await self._call("analyze_private_solution_stream", *args, **kwargs)

    async def extract_private_tasks(self, *args, **kwargs):
        return await self._call("extract_private_tasks", *args, **kwargs)

    async def generate_private_task_meta(self, *args, **kwargs):
        return await self._call("generate_private_task_meta", *args, **kwargs)

    async def refine_pattern(self, *args, **kwargs):
        return await self._call("refine_pattern", *args, **kwargs)

    async def suggest_patterns(self, *args, **kwargs):
        return await self._call("suggest_patterns", *args, **kwargs)

    async def link_pattern_tasks(self, *args, **kwargs):
        return await self._call("link_pattern_tasks", *args, **kwargs)

    async def generate_pattern_exercises(self, *args, **kwargs):
        return await self._call("generate_pattern_exercises", *args, **kwargs)
