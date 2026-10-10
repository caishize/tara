"""Four-dimension priority scoring for curated events.

Dimensions (weights sum to 1.0):
- urgency (0.30): How soon does this need attention?
- severity (0.25): How bad are the consequences of missing it?
- stakeholder_weight (0.25): How important are the people involved?
- irrecoverability (0.20): Can this be rescheduled/recovered if missed?

Each dimension is scored 0.0-1.0.  The composite score maps to priority
levels: P0 (>=0.8), P1 (>=0.6), P2 (>=0.3), P3 (<0.3).

V8 architecture: docs/architecture-v8-secretary-brain.md section 5.2
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ....core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Priority score dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PriorityScore:
    """Four-dimension priority score.

    Attributes:
        urgency: Time-pressure dimension (0-1). Higher = more urgent.
        severity: Consequence dimension (0-1). Higher = worse if missed.
        stakeholder_weight: People-importance dimension (0-1).
        irrecoverability: Can-not-redo dimension (0-1). Higher = harder to recover.
        w_*_override: Optional per-family weight overrides (None = use default).
    """
    urgency: float
    severity: float
    stakeholder_weight: float
    irrecoverability: float
    w_urgency_override: Optional[float] = None
    w_severity_override: Optional[float] = None
    w_stakeholder_override: Optional[float] = None
    w_irrecoverability_override: Optional[float] = None

    W_URGENCY = 0.30
    W_SEVERITY = 0.25
    W_STAKEHOLDER = 0.25
    W_IRRECOVERABLE = 0.20

    @property
    def composite(self) -> float:
        """Weighted sum of all four dimensions."""
        wu = self.w_urgency_override if self.w_urgency_override is not None else self.W_URGENCY
        ws = self.w_severity_override if self.w_severity_override is not None else self.W_SEVERITY
        wst = self.w_stakeholder_override if self.w_stakeholder_override is not None else self.W_STAKEHOLDER
        wi = self.w_irrecoverability_override if self.w_irrecoverability_override is not None else self.W_IRRECOVERABLE
        return (
            self.urgency * wu
            + self.severity * ws
            + self.stakeholder_weight * wst
            + self.irrecoverability * wi
        )

    @property
    def priority_level(self) -> str:
        """Map composite score to priority level string."""
        c = self.composite
        if c >= 0.8:
            return "P0"
        if c >= 0.6:
            return "P1"
        if c >= 0.3:
            return "P2"
        return "P3"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "urgency": round(self.urgency, 3),
            "severity": round(self.severity, 3),
            "stakeholder_weight": round(self.stakeholder_weight, 3),
            "irrecoverability": round(self.irrecoverability, 3),
            "composite": round(self.composite, 3),
            "priority_level": self.priority_level,
        }


# ---------------------------------------------------------------------------
# Rule-based scoring functions
# ---------------------------------------------------------------------------

# Event types considered high-severity
_HIGH_SEVERITY_TYPES = {"business_trip", "meeting", "appointment", "medical", "birthday", "anniversary"}

# Event types that are irrecoverable (can't be rescheduled easily)
_IRRECOVERABLE_TYPES = {"flight", "business_trip", "medical", "exam", "interview", "birthday", "anniversary"}

# Relation types with high stakeholder weight
_HIGH_STAKEHOLDER_RELATIONS = {"spouse", "parent", "child", "partner"}


def _score_urgency(
    hours_until_start: Optional[float],
    event_type: Optional[str] = None,
) -> float:
    """Score urgency based on time until event start.

    Returns:
        0.0-1.0 urgency score.
    """
    if hours_until_start is None:
        return 0.3  # Unknown timing, moderate default

    if hours_until_start <= 0:
        return 1.0  # Already started or past
    if hours_until_start <= 2:
        return 0.95
    if hours_until_start <= 6:
        return 0.85
    if hours_until_start <= 12:
        return 0.7
    if hours_until_start <= 24:
        return 0.6
    if hours_until_start <= 48:
        return 0.4
    if hours_until_start <= 168:  # 7 days
        return 0.25
    return 0.1


def _score_severity(
    event_type: Optional[str],
    priority_str: Optional[str],
    association_count: int = 0,
) -> float:
    """Score severity based on event type and existing priority.

    Returns:
        0.0-1.0 severity score.
    """
    base = 0.3

    # Event type contribution
    if event_type in _HIGH_SEVERITY_TYPES:
        base = 0.7
    elif event_type in ("travel", "reminder"):
        base = 0.5

    # Existing priority label boost
    priority_boost = {
        "critical": 0.3,
        "high": 0.2,
        "normal": 0.0,
        "low": -0.1,
    }
    base += priority_boost.get(priority_str or "normal", 0.0)

    # Associations add complexity / impact
    if association_count >= 3:
        base += 0.1
    elif association_count >= 1:
        base += 0.05

    return max(0.0, min(1.0, base))


def _score_stakeholder_weight(
    member_context: Optional[Dict[str, Any]] = None,
) -> float:
    """Score stakeholder importance based on member context.

    Args:
        member_context: Dict with optional keys:
            - participant_count: int
            - has_close_relation: bool (spouse/parent/child)
            - relation_types: List[str]

    Returns:
        0.0-1.0 stakeholder score.
    """
    if member_context is None:
        return 0.3  # Default moderate weight

    score = 0.3

    participant_count = member_context.get("participant_count", 1)
    if participant_count >= 5:
        score += 0.3
    elif participant_count >= 3:
        score += 0.2
    elif participant_count >= 2:
        score += 0.1

    relation_types = member_context.get("relation_types", [])
    if any(r in _HIGH_STAKEHOLDER_RELATIONS for r in relation_types):
        score += 0.3

    if member_context.get("has_close_relation"):
        score = max(score, 0.6)

    # Thermometer bonus: cold/frozen relationships need more attention
    temp_status = member_context.get("temperature_status")
    if temp_status == "frozen":
        score += 0.25
    elif temp_status == "cold":
        score += 0.15
    # cool/warm don't get bonus (maintaining is good but not urgent)

    return max(0.0, min(1.0, score))


def _score_irrecoverability(
    event_type: Optional[str],
    has_booking: bool = False,
) -> float:
    """Score how hard it is to recover from missing the event.

    Returns:
        0.0-1.0 irrecoverability score.
    """
    if event_type in _IRRECOVERABLE_TYPES:
        return 0.9

    if has_booking:
        return 0.7

    if event_type in ("meeting", "appointment"):
        return 0.5

    if event_type in ("travel", "reminder"):
        return 0.3

    return 0.2


def compute_priority_score(
    event_data: Dict[str, Any],
    member_context: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
    weights: Optional[Dict[str, float]] = None,
) -> PriorityScore:
    """Compute a four-dimension priority score for an event.

    Args:
        event_data: Dict with keys:
            - normalized_start: datetime or ISO string (optional)
            - event_type: str (optional)
            - priority: str (low/normal/high/critical)
            - association_count: int (optional)
            - interaction_count: int (optional, F3 bonus)
            - has_booking: bool (optional)
        member_context: Dict with stakeholder info (optional)
        now: Current time (defaults to UTC now)
        weights: Optional per-family weight overrides. Keys: urgency,
            severity, stakeholder, irrecoverability. Falls back to
            class-level defaults for missing keys.

    Returns:
        PriorityScore with all four dimensions.

    F3 enhancement: ``interaction_count`` and ``association_count`` now
    contribute additional bonuses (up to +0.15 and +0.10 respectively)
    to severity and stakeholder dimensions, pushing borderline events
    out of the narrowed fuzzy calibration band [0.42, 0.58].
    """
    if now is None:
        now = utc_now()

    # Parse start time
    hours_until_start = None
    start = event_data.get("normalized_start")
    if isinstance(start, datetime):
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        delta = (start - now).total_seconds() / 3600.0
        hours_until_start = delta
    elif isinstance(start, str):
        try:
            parsed = datetime.fromisoformat(start)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            hours_until_start = (parsed - now).total_seconds() / 3600.0
        except (ValueError, TypeError):
            pass

    event_type = event_data.get("event_type")
    priority_str = event_data.get("priority", "normal")
    association_count = int(event_data.get("association_count", 0))
    has_booking = bool(event_data.get("has_booking", False))

    # F3: Additional scoring dimensions to narrow the fuzzy band
    interaction_count = int(event_data.get("interaction_count", 0))
    interaction_bonus = min(interaction_count / 10.0, 1.0) * 0.15
    assoc_bonus = min(association_count / 3.0, 1.0) * 0.10

    base_severity = _score_severity(event_type, priority_str, association_count)
    base_stakeholder = _score_stakeholder_weight(member_context)

    # Distribute bonuses across severity and stakeholder to keep composite balanced
    boosted_severity = min(1.0, base_severity + interaction_bonus)
    boosted_stakeholder = min(1.0, base_stakeholder + assoc_bonus)

    w = weights or {}

    return PriorityScore(
        urgency=_score_urgency(hours_until_start, event_type),
        severity=boosted_severity,
        stakeholder_weight=boosted_stakeholder,
        irrecoverability=_score_irrecoverability(event_type, has_booking),
        w_urgency_override=w.get("urgency"),
        w_severity_override=w.get("severity"),
        w_stakeholder_override=w.get("stakeholder"),
        w_irrecoverability_override=w.get("irrecoverability"),
    )
