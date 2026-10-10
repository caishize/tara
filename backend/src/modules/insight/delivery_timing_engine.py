"""Delivery timing engine — four-wave daily insight scheduling.

Selects and scores insights for each delivery wave (morning/noon/evening/night).
All logic is deterministic (no LLM). The engine does NOT query the DB directly;
it receives pre-fetched insights and user state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ...core.utils.timezone import utc_now
from .models import Insight, InformationTier


# ---------------------------------------------------------------------------
# Data structures (immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserMomentState:
    """Snapshot of user's current state for delivery decisions."""

    current_activity: Optional[str] = None
    energy_level: str = "medium"  # high/medium/low
    receptivity: str = "open"  # open/busy/recovering
    next_transition: Optional[datetime] = None
    unread_insight_count: int = 0
    density_score: float = 0.0


@dataclass(frozen=True)
class DeliveryWave:
    """Configuration for a delivery time slot."""

    name: str  # morning/noon/evening/night
    hour: int
    max_items: int
    focus_types: Tuple[str, ...]
    style: str  # quick/relaxed/practical/calm


# Default wave definitions with focus types
WAVE_CONFIGS: Tuple[DeliveryWave, ...] = (
    DeliveryWave(
        name="morning",
        hour=7,
        max_items=3,
        focus_types=(
            "weather_care", "time", "life_admin", "prep_chain", "health",
        ),
        style="quick",
    ),
    DeliveryWave(
        name="noon",
        hour=12,
        max_items=2,
        focus_types=(
            "time", "efficiency", "positive_affirmation", "habit_tracking",
        ),
        style="relaxed",
    ),
    DeliveryWave(
        name="evening",
        hour=17,
        max_items=2,
        focus_types=(
            "life_admin", "favor", "relationship", "social_obligation",
        ),
        style="practical",
    ),
    DeliveryWave(
        name="night",
        hour=21,
        max_items=3,
        focus_types=(
            "time", "relationship", "trend_alert", "family_climate", "memory",
        ),
        style="calm",
    ),
)

WAVE_NAMES: Tuple[str, ...] = tuple(w.name for w in WAVE_CONFIGS)

_WAVE_BY_NAME: Dict[str, DeliveryWave] = {w.name: w for w in WAVE_CONFIGS}


# ---------------------------------------------------------------------------
# Moment-state builder
# ---------------------------------------------------------------------------


def build_moment_state(
    *,
    density_score: float = 0.0,
    unread_insight_count: int = 0,
    current_hour: Optional[int] = None,
    current_activity: Optional[str] = None,
    next_transition: Optional[datetime] = None,
) -> UserMomentState:
    """Build a ``UserMomentState`` from available signals.

    Infers ``energy_level`` and ``receptivity`` from time-of-day and
    density score when explicit values are not available.
    """
    hour = current_hour if current_hour is not None else utc_now().hour

    energy_level = _infer_energy_level(hour, density_score)
    receptivity = _infer_receptivity(density_score, unread_insight_count)

    return UserMomentState(
        current_activity=current_activity,
        energy_level=energy_level,
        receptivity=receptivity,
        next_transition=next_transition,
        unread_insight_count=unread_insight_count,
        density_score=density_score,
    )


def _infer_energy_level(hour: int, density_score: float) -> str:
    """Heuristic energy level from hour-of-day and schedule density."""
    if 6 <= hour <= 10:
        return "high"
    if 11 <= hour <= 14:
        return "medium" if density_score < 0.7 else "low"
    if 15 <= hour <= 18:
        return "medium"
    if 19 <= hour <= 22:
        return "medium" if density_score < 0.5 else "low"
    # Late night / early morning
    return "low"


def _infer_receptivity(
    density_score: float, unread_count: int,
) -> str:
    """Heuristic receptivity from density and unread count."""
    if density_score > 0.8 or unread_count >= 5:
        return "busy"
    if density_score > 0.5 or unread_count >= 3:
        return "recovering"
    return "open"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class DeliveryTimingEngine:
    """Selects and scores insights for each delivery wave."""

    def get_wave_config(
        self,
        wave_name: str,
        user_settings_waves: Optional[Dict] = None,
    ) -> DeliveryWave:
        """Get wave config, merging user overrides with defaults.

        User overrides can set ``hour`` and ``max_items`` per wave.
        ``focus_types`` and ``style`` are not user-configurable.
        """
        base = _WAVE_BY_NAME.get(wave_name)
        if base is None:
            raise ValueError(f"Unknown wave: {wave_name}")

        if not user_settings_waves or wave_name not in user_settings_waves:
            return base

        overrides = user_settings_waves[wave_name]
        return DeliveryWave(
            name=wave_name,
            hour=overrides.get("hour", base.hour),
            max_items=overrides.get("max_items", base.max_items),
            focus_types=base.focus_types,
            style=base.style,
        )

    def is_wave_enabled(
        self,
        wave_name: str,
        user_settings_waves: Optional[Dict] = None,
    ) -> bool:
        """Check if a wave is enabled (defaults to True)."""
        if not user_settings_waves or wave_name not in user_settings_waves:
            return True
        return user_settings_waves[wave_name].get("enabled", True)

    def get_enabled_waves(
        self,
        user_settings_waves: Optional[Dict] = None,
    ) -> List[DeliveryWave]:
        """Return all enabled waves with user overrides applied."""
        return [
            self.get_wave_config(name, user_settings_waves)
            for name in WAVE_NAMES
            if self.is_wave_enabled(name, user_settings_waves)
        ]

    def select_for_wave(
        self,
        insights: List[Insight],
        wave: DeliveryWave,
        moment: UserMomentState,
    ) -> List[Insight]:
        """Select top insights for a delivery wave, ranked by delivery score.

        Filters out L0_AUTO insights (those are handled without user attention).
        """
        eligible = [
            i for i in insights
            if getattr(i, "information_tier", "L2_FORMAL") != InformationTier.L0_AUTO.value
        ]

        scored = [
            (self._compute_delivery_score(i, wave, moment), i)
            for i in eligible
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)

        return [i for _, i in scored[:wave.max_items]]

    def select_all_waves(
        self,
        insights: List[Insight],
        moment: UserMomentState,
        user_settings_waves: Optional[Dict] = None,
    ) -> Dict[str, List[Insight]]:
        """Select insights for every enabled wave.

        Returns a mapping of wave_name -> selected insights.
        Already-selected insights are excluded from later waves to
        avoid delivering the same insight twice in one day.
        """
        result: Dict[str, List[Insight]] = {}
        used_ids: set = set()
        remaining = list(insights)

        for wave in self.get_enabled_waves(user_settings_waves):
            available = [i for i in remaining if i.id not in used_ids]
            selected = self.select_for_wave(available, wave, moment)
            result[wave.name] = selected
            used_ids.update(i.id for i in selected)

        return result

    def _compute_delivery_score(
        self,
        insight: Insight,
        wave: DeliveryWave,
        moment: UserMomentState,
    ) -> float:
        """Compute delivery priority score.

        Formula: importance*0.4 + urgency*0.3 + context_bonus - interruption_cost - unread_penalty
        """
        base = insight.importance * 0.4 + insight.urgency * 0.3

        # Focus type bonus: reward insights matching this wave's themes
        insight_type = insight.insight_type or ""
        context_bonus = 20.0 if insight_type in wave.focus_types else 0.0

        # Interruption cost based on receptivity
        _interruption_costs = {"open": 0.0, "busy": 30.0, "recovering": 15.0}
        interruption_cost = _interruption_costs.get(moment.receptivity, 10.0)

        # Unread penalty (back-pressure when too many unread)
        unread_penalty = min(moment.unread_insight_count * 3.0, 15.0)

        return base + context_bonus - interruption_cost - unread_penalty

    def compute_daily_budget(
        self, engagement_days: int, dismiss_rate_7d: float,
    ) -> int:
        """Frequency adaptation based on user engagement.

        - New users (<7 days): conservative 3/day
        - Active (dismiss_rate < 30%): full waves (up to 10)
        - Disengaged (dismiss_rate > 50%): 1 killer insight/day
        """
        if engagement_days < 7:
            return 3
        if dismiss_rate_7d > 0.5:
            return 1
        if dismiss_rate_7d > 0.3:
            return 5
        return 10


# ---------------------------------------------------------------------------
# Module-level singleton for convenience
# ---------------------------------------------------------------------------

delivery_timing_engine = DeliveryTimingEngine()
