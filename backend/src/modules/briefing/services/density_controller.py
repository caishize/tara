"""Rule-driven adaptive information density controller (no LLM).

Controls how much information to show based on schedule density,
time-of-day, emotional state, and family preferences.

Implements the "clean desk" algorithm: urgency items always visible,
remaining budget filled by relevance-sorted content.

Design doc: docs/secretary-intelligence-optimization.md section 3.8
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from ...curation.models import FamilyPreference
from ...curation.services.orchestrator import OrchestratedDay

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAILY_NOISE_BUDGET = 10  # Max items visible without scrolling


class DensityLevel:
    """Density level constants."""

    FOCUSED = "FOCUSED"           # density > 0.8: max 3 recs, P0/P1 only
    STANDARD = "STANDARD"         # 0.4-0.8: max 5 recs, full events
    RELAXED = "RELAXED"           # density < 0.4: max 7 recs, exploratory
    REFLECTIVE = "REFLECTIVE"     # evening + low density: review content


# Level configuration: (max_recommendations, max_annotations, show_household, show_upcoming_trips)
_LEVEL_CONFIG = {
    DensityLevel.FOCUSED:     (3, 2, False, False),
    DensityLevel.STANDARD:    (5, 4, True, True),
    DensityLevel.RELAXED:     (7, 6, True, True),
    DensityLevel.REFLECTIVE:  (5, 3, True, True),
}

# Period multipliers (lower = less info shown)
_PERIOD_MULTIPLIERS = {
    "morning": 1.0,
    "afternoon": 0.7,
    "evening": 0.5,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DensityProfile:
    """Computed density profile for a briefing."""

    day_density: float           # 0-1, from OrchestratedDay.density_score
    period_multiplier: float     # morning=1.0, afternoon=0.7, evening=0.5
    emotional_state: str         # stressed | normal | relaxed
    max_recommendations: int
    max_annotations: int
    show_household: bool
    show_upcoming_trips: bool
    density_level: str           # FOCUSED | STANDARD | RELAXED | REFLECTIVE
    noise_budget: int = DAILY_NOISE_BUDGET


@dataclass(frozen=True)
class CleanDeskResult:
    """Result of the 'clean desk' algorithm."""

    visible_items: tuple       # Always-visible urgency items + top scored items
    deferred_items: tuple      # Items beyond budget (expandable via "show more")
    budget_used: int
    budget_total: int


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class DensityController:
    """Rule-driven information density control (deterministic, no LLM).

    Density levels:
    - FOCUSED (density > 0.8): max 3 recommendations, P0/P1 events only
    - STANDARD (0.4-0.8): max 5 recommendations, full events
    - RELAXED (density < 0.4): max 7 recommendations, exploratory content
    - REFLECTIVE (evening + low density): review content (memory replay, etc.)

    Modifiers:
    - Weekend: one level more relaxed
    - Negative emotional trend: one level more relaxed (reduce pressure)
    - FamilyPreference.density_preferences overrides
    """

    def compute_profile(
        self,
        orchestrated_day: Optional[OrchestratedDay],
        period: str,
        family_prefs: Optional[FamilyPreference] = None,
        emotional_trend: str = "stable",
        target_date: Optional[date] = None,
    ) -> DensityProfile:
        """Compute the density profile for a briefing.

        Args:
            orchestrated_day: The orchestrated schedule (can be None for empty days).
            period: Time-of-day period: ``morning``, ``afternoon``, or ``evening``.
            family_prefs: Optional family-specific preference overrides.
            emotional_trend: ``declining``, ``stable``, or ``improving``.
            target_date: The date (for weekend detection). Falls back to
                orchestrated_day.target_date if available.
        """
        day_density = orchestrated_day.density_score if orchestrated_day else 0.0
        period_mult = _PERIOD_MULTIPLIERS.get(period, 1.0)

        # Determine emotional state label
        emotional_state = _map_emotional_state(emotional_trend)

        # Determine base density level from day_density
        base_level = _base_density_level(day_density, period)

        # Apply modifiers
        level = base_level
        resolve_date = target_date
        if resolve_date is None and orchestrated_day is not None:
            resolve_date = orchestrated_day.target_date

        if resolve_date is not None and _is_weekend(resolve_date):
            level = _relax_level(level)

        if emotional_trend == "declining":
            level = _relax_level(level)

        # Apply family preference overrides
        if family_prefs and family_prefs.density_preferences:
            level = _apply_pref_overrides(level, family_prefs.density_preferences)

        # Get configuration for the resolved level
        max_rec, max_ann, show_hh, show_trips = _LEVEL_CONFIG[level]

        # Scale recommendations/annotations by period multiplier
        max_rec = max(1, int(max_rec * period_mult))
        max_ann = max(1, int(max_ann * period_mult))

        return DensityProfile(
            day_density=round(day_density, 3),
            period_multiplier=period_mult,
            emotional_state=emotional_state,
            max_recommendations=max_rec,
            max_annotations=max_ann,
            show_household=show_hh,
            show_upcoming_trips=show_trips,
            density_level=level,
        )

    def apply_clean_desk(
        self,
        profile: DensityProfile,
        urgency_items: Sequence[Any],
        scored_items: Sequence[Any],
    ) -> CleanDeskResult:
        """Apply the 'clean desk' algorithm.

        Urgency items (alerts, conflicts, overdue preparations) are always shown.
        Remaining budget is filled with relevance-sorted items.

        Args:
            profile: The computed density profile.
            urgency_items: Must-show items (always visible).
            scored_items: Items sorted by relevance score (descending).

        Returns:
            ``CleanDeskResult`` with visible and deferred item tuples.
        """
        budget = profile.noise_budget
        urgency = list(urgency_items)

        remaining = max(0, budget - len(urgency))
        sorted_list = list(scored_items)
        visible_extra = sorted_list[:remaining]
        deferred = sorted_list[remaining:]

        all_visible = urgency + visible_extra

        return CleanDeskResult(
            visible_items=tuple(all_visible),
            deferred_items=tuple(deferred),
            budget_used=len(all_visible),
            budget_total=budget,
        )

    def filter_by_priority(
        self,
        profile: DensityProfile,
        events_with_levels: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Filter events by priority level based on density.

        In FOCUSED mode, only P0/P1 events are shown.
        Other modes show all events.

        Args:
            profile: The computed density profile.
            events_with_levels: Dicts with a ``priority_level`` key (P0-P3).

        Returns:
            Filtered list of event dicts.
        """
        if profile.density_level == DensityLevel.FOCUSED:
            return [
                e for e in events_with_levels
                if e.get("priority_level") in ("P0", "P1")
            ]
        return list(events_with_levels)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_density_level(day_density: float, period: str) -> str:
    """Determine the base density level from raw density score and period."""
    if day_density > 0.8:
        return DensityLevel.FOCUSED
    if day_density >= 0.4:
        return DensityLevel.STANDARD
    # Low density
    if period == "evening":
        return DensityLevel.REFLECTIVE
    return DensityLevel.RELAXED


def _relax_level(level: str) -> str:
    """Shift one level toward more relaxed."""
    progression = [
        DensityLevel.FOCUSED,
        DensityLevel.STANDARD,
        DensityLevel.RELAXED,
        DensityLevel.REFLECTIVE,
    ]
    try:
        idx = progression.index(level)
        return progression[min(idx + 1, len(progression) - 1)]
    except ValueError:
        return level


def _is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # Saturday=5, Sunday=6


def _map_emotional_state(emotional_trend: str) -> str:
    """Map emotional trend to simplified emotional state."""
    if emotional_trend == "declining":
        return "stressed"
    if emotional_trend == "improving":
        return "relaxed"
    return "normal"


def _apply_pref_overrides(level: str, prefs: Dict[str, Any]) -> str:
    """Apply family preference overrides to density level.

    Supported keys in ``density_preferences``:
    - ``forced_level``: Override to a specific level (e.g. "FOCUSED")
    - ``relax_by``: Number of levels to shift toward relaxed (int)
    """
    forced = prefs.get("forced_level")
    if forced and forced in (
        DensityLevel.FOCUSED, DensityLevel.STANDARD,
        DensityLevel.RELAXED, DensityLevel.REFLECTIVE,
    ):
        return forced

    relax_by = int(prefs.get("relax_by", 0))
    result = level
    for _ in range(relax_by):
        result = _relax_level(result)
    return result
