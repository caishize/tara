"""Query-time priority adjustment for insights.

Adjusts importance/urgency at query time without modifying DB records.
Applied in InsightQueryService before sorting results for delivery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from ...core.utils.timezone import utc_now
from .models import InformationTier


# ---------------------------------------------------------------------------
# Query context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserQueryContext:
    """Context for dynamic priority adjustment at query time."""

    recent_entity_ids: frozenset = frozenset()  # Entities user interacted with in 24h
    dismiss_count_7d: Optional[Dict[str, int]] = None  # {insight_type: count}
    density_score: float = 0.0  # Today's schedule density (0-1)
    is_weekend: bool = False
    is_holiday: bool = False
    user_mood: Optional[str] = None  # low/normal/high from emotional_trend


# ---------------------------------------------------------------------------
# Adjuster
# ---------------------------------------------------------------------------

_FAMILY_TYPES = frozenset({
    "relationship", "family_climate", "positive_affirmation", "social_obligation",
})

_NEGATIVE_TYPES = frozenset({
    "trend_alert", "social_obligation",
})

# Work-category insight types suppressed during weekends/holidays.
# Design doc §8: weekend/holiday -25 urgency rule for work insights.
_WORK_TYPES = frozenset({
    "work_reminder", "work_task", "work_deadline", "task",
    "commitment", "schedule_optimization",
})

_URGENCY_ENTITY_BOOST = 20
_IMPORTANCE_DISMISS_PENALTY = 30
_DISMISS_THRESHOLD = 3
_DEADLINE_URGENCY_FLOOR = 95
_DEADLINE_SECONDS = 86400  # 24h
_DENSITY_IMPORTANCE_PENALTY = 15
_DENSITY_THRESHOLD = 0.8
_WEEKEND_FAMILY_BOOST = 10
_WEEKEND_WORK_PENALTY = 25  # urgency penalty for work insights on weekends/holidays
_LOW_MOOD_PENALTY = 20
_LOW_MOOD_URGENCY_THRESHOLD = 70


class DynamicPriorityAdjuster:
    """Adjusts insight importance/urgency at query time without modifying DB.

    Pure function over (insight, context) → (importance, urgency).
    All adjustments are clamped to [0, 100].
    """

    def adjust(self, insight, context: UserQueryContext) -> Tuple[int, int]:
        """Return adjusted (importance, urgency) for the given insight and context."""
        importance = insight.importance
        urgency = insight.urgency

        # 1. Recent entity interaction → urgency boost
        entity_ids = {
            str(e.entity_id) for e in (getattr(insight, "entities", None) or [])
        }
        if entity_ids & context.recent_entity_ids:
            urgency = min(100, urgency + _URGENCY_ENTITY_BOOST)

        # 2. Consecutive dismissals of same type → importance penalty
        dismiss_counts = context.dismiss_count_7d or {}
        if dismiss_counts.get(insight.insight_type, 0) >= _DISMISS_THRESHOLD:
            importance = max(0, importance - _IMPORTANCE_DISMISS_PENALTY)

        # 3. Approaching deadline → urgency force
        expires_at = getattr(insight, "expires_at", None)
        if expires_at is not None:
            remaining = (expires_at - utc_now()).total_seconds()
            if remaining < _DEADLINE_SECONDS:
                urgency = max(urgency, _DEADLINE_URGENCY_FLOOR)

        # 4. High schedule density → non-critical penalty
        info_tier = getattr(insight, "information_tier", None)
        if context.density_score > _DENSITY_THRESHOLD:
            if info_tier != InformationTier.L2_FORMAL.value:
                importance = max(0, importance - _DENSITY_IMPORTANCE_PENALTY)

        # 5. Weekend/holiday → family boost + work penalty
        if context.is_weekend or context.is_holiday:
            if insight.insight_type in _FAMILY_TYPES:
                importance = min(100, importance + _WEEKEND_FAMILY_BOOST)
            if insight.insight_type in _WORK_TYPES:
                # Suppress work urgency on rest days (design doc §8: -25)
                urgency = max(0, urgency - _WEEKEND_WORK_PENALTY)

        # 6. Low mood → suppress non-urgent negative info
        if context.user_mood == "low" and urgency < _LOW_MOOD_URGENCY_THRESHOLD:
            if insight.insight_type in _NEGATIVE_TYPES:
                importance = max(0, importance - _LOW_MOOD_PENALTY)

        return importance, urgency
