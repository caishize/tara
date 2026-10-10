"""Insight Expiry Policy - Two-track expiry for insights.

Track 1 (Event-Anchored): Insights tied to a specific date get
    expires_at = anchor_date + buffer. Objectively stale once the event passes.

Track 2 (Secretary-Judged): Everything else gets a safety-net max age
    (default 90 days). The daily LLM consolidation service reviews and
    dismisses stale/irrelevant insights before that limit is reached.
"""

from datetime import date, datetime, timedelta, time
from typing import Any, Dict, Optional

from ...core.utils.timezone import utc_now
from ..memory.config import memory_config

# Keys in action_data that represent an anchor date (ISO format strings).
_ANCHOR_KEYS = ("trip_end_date", "date", "week_ending", "week_starting")

# Bounds for user-supplied safety_net_days (PLAN-015).
_USER_EXPIRY_MIN_DAYS = 1
_USER_EXPIRY_MAX_DAYS = 90


def compute_expires_at(
    insight_type: str,
    *,
    action_data: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
    safety_net_days: Optional[int] = None,
) -> datetime:
    """Compute the expiry timestamp for an insight.

    Args:
        insight_type: The insight type string (unused today but passed for
            future extensibility).
        action_data: Optional dict that may contain an anchor date field.
        now: Override for current time (useful in tests).
        safety_net_days: Per-user expiry preference from
            ``UserInsightSettings.insight_expiry_days``.  When provided, it
            overrides the global ``memory_config.insight_safety_net_days``
            for Track-2 (secretary-judged) insights.  Clamped to
            [``_USER_EXPIRY_MIN_DAYS``, ``_USER_EXPIRY_MAX_DAYS``].
            NR-3: Event-anchored (Track-1) expiry is never affected by this
            parameter.

    Returns:
        A timezone-aware UTC datetime for ``expires_at``.
    """
    if now is None:
        now = utc_now()

    anchor = _extract_anchor_date(action_data)
    if anchor is not None:
        # Event-anchored (Track 1): expire 1 day after the anchor.
        # NR-3: this path is intentionally unaffected by safety_net_days.
        anchor_dt = datetime.combine(anchor + timedelta(days=1), time.min)
        if anchor_dt.tzinfo is None:
            anchor_dt = anchor_dt.replace(tzinfo=now.tzinfo)
        return anchor_dt

    # Secretary-judged (Track 2): honour per-user preference if provided.
    if safety_net_days is not None:
        effective_days = max(
            _USER_EXPIRY_MIN_DAYS,
            min(_USER_EXPIRY_MAX_DAYS, safety_net_days),
        )
    else:
        effective_days = memory_config.insight_safety_net_days
    return now + timedelta(days=effective_days)


def _extract_anchor_date(action_data: Optional[Dict[str, Any]]) -> Optional[date]:
    """Try to extract an anchor date from action_data."""
    if not action_data:
        return None

    for key in _ANCHOR_KEYS:
        value = action_data.get(key)
        if value is None:
            continue
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except (ValueError, TypeError):
                continue
    return None
