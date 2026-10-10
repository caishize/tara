"""ImpactArbitrator — pure rule engine for trigger event impact assessment.

Zero LLM calls. Evaluates the impact level of trigger events and decides
the execution strategy (SILENT/LOW/MEDIUM/HIGH → T0/T1/T2/T3).

This sits between the trigger source and the TriggerDispatcher, filtering
out noise (SILENT) and right-sizing the processing pipeline for each event.

V8 architecture: docs/architecture-v8-secretary-brain.md section 4.3
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ImpactLevel(str, Enum):
    """Impact level of a trigger event, ordered from lowest to highest."""
    SILENT = "silent"    # No visible change, pure background update
    LOW = "low"          # Minor adjustment, no push notification
    MEDIUM = "medium"    # Worth mentioning in daily briefing
    HIGH = "high"        # Requires immediate push notification

    def __ge__(self, other: "ImpactLevel") -> bool:
        return _LEVEL_ORDER[self] >= _LEVEL_ORDER[other]

    def __gt__(self, other: "ImpactLevel") -> bool:
        return _LEVEL_ORDER[self] > _LEVEL_ORDER[other]

    def __le__(self, other: "ImpactLevel") -> bool:
        return _LEVEL_ORDER[self] <= _LEVEL_ORDER[other]

    def __lt__(self, other: "ImpactLevel") -> bool:
        return _LEVEL_ORDER[self] < _LEVEL_ORDER[other]


_LEVEL_ORDER: Dict[ImpactLevel, int] = {
    ImpactLevel.SILENT: 0,
    ImpactLevel.LOW: 1,
    ImpactLevel.MEDIUM: 2,
    ImpactLevel.HIGH: 3,
}


class ExecutionMode(str, Enum):
    """Execution strategy mapped from ImpactLevel."""
    SILENT_UPDATE = "silent_update"    # T0: no LLM, silent DB write
    T1_HEURISTIC = "t1_heuristic"     # T1: heuristic fill, no LLM
    T2_INCREMENTAL = "t2_incremental"  # T2: incremental LLM processing
    T3_FULL = "t3_full"               # T3: full orchestration pipeline


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TriggerContext:
    """Contextual information about a trigger event for impact assessment.

    Attributes:
        trigger_type: Type of trigger (e.g. "trip_created", "memory_extracted")
        payload: Trigger payload dict (event-specific data)
        diff: Dict of changed fields → {"field": {"old": ..., "new": ...}}
              or {"field": {"delta_hours": float}} for time shifts.
              Empty dict if not applicable (e.g. new creation).
    """
    trigger_type: str
    payload: Dict[str, Any]
    diff: Dict[str, Any]


@dataclass(frozen=True)
class ImpactAssessment:
    """Result of impact assessment.

    Attributes:
        level: Assessed impact level
        should_push: Whether to send a push notification
        should_brief: Whether to include in daily briefing
        execution_mode: Recommended execution strategy
        reason: Human-readable explanation of the decision
    """
    level: ImpactLevel
    should_push: bool
    should_brief: bool
    execution_mode: ExecutionMode
    reason: str


# ---------------------------------------------------------------------------
# Fields considered low-impact when changed alone
# ---------------------------------------------------------------------------

_SILENT_ONLY_FIELDS: Set[str] = {"notes", "description", "priority"}

_LOCATION_FIELDS: Set[str] = {"location", "destination"}

_DATE_FIELDS: Set[str] = {"date", "start_date", "end_date"}

# Threshold for time shift (hours) below which change is low impact
_TIME_SHIFT_LOW_THRESHOLD_HOURS = 2.0

# Threshold for number of simultaneous field changes → HIGH
_MULTI_FIELD_HIGH_THRESHOLD = 3


# ---------------------------------------------------------------------------
# ImpactArbitrator
# ---------------------------------------------------------------------------

class ImpactArbitrator:
    """Pure rule engine that evaluates trigger event impact levels.

    No LLM calls, no database access, no side effects.
    Designed to be called synchronously from TriggerDispatcher or DirtyBitManager.

    Rules (priority order):
    1. trip_created → HIGH
    2. date_approaching + <= 3 days → HIGH
    3. date_approaching + <= 7 days → MEDIUM
    4. New person entities in payload → HIGH
    5. Only notes/description/priority changed → SILENT
    6. Time shift < 2h and no conflict → LOW
    7. Location/destination/date changed → MEDIUM
    8. 3+ fields changed simultaneously → HIGH
    9. memory_extracted + no conflict → SILENT
    10. Default → LOW
    """

    def assess(self, context: TriggerContext) -> ImpactAssessment:
        """Assess the impact of a trigger event.

        Args:
            context: Trigger context with type, payload, and diff.

        Returns:
            ImpactAssessment with level, push/brief flags, and execution mode.
        """
        level, reason = self._classify_impact(context)
        return ImpactAssessment(
            level=level,
            should_push=level >= ImpactLevel.HIGH,
            should_brief=level >= ImpactLevel.MEDIUM,
            execution_mode=_decide_mode(level),
            reason=reason,
        )

    def _classify_impact(
        self,
        context: TriggerContext,
    ) -> tuple:
        """Apply rules in priority order. Returns (ImpactLevel, reason)."""
        trigger_type = context.trigger_type
        payload = context.payload
        diff = context.diff
        changed_fields = set(diff.keys()) if diff else set()

        # Rule 1: trip_created → HIGH
        if trigger_type == "trip_created":
            return ImpactLevel.HIGH, "new trip created"

        # Rule 2-3: date_approaching
        if trigger_type == "date_approaching":
            return self._assess_date_approaching(payload)

        # Rule 4: new person entities → HIGH
        new_persons = payload.get("new_person_entities")
        if new_persons:
            return ImpactLevel.HIGH, "new person entities added"

        # Rule 5: only silent-only fields changed → SILENT
        if changed_fields and not (changed_fields - _SILENT_ONLY_FIELDS):
            return ImpactLevel.SILENT, "only notes/description/priority changed"

        # Rule 6: time shift < 2h with no conflict → LOW
        time_level = self._assess_time_shift(diff, payload)
        if time_level is not None:
            return time_level

        # Rule 7: location/destination/date changed → MEDIUM
        if changed_fields & (_LOCATION_FIELDS | _DATE_FIELDS):
            return ImpactLevel.MEDIUM, "location or date changed"

        # Rule 8: 3+ fields changed simultaneously → HIGH
        if len(changed_fields) >= _MULTI_FIELD_HIGH_THRESHOLD:
            return (
                ImpactLevel.HIGH,
                f"{len(changed_fields)} fields changed simultaneously",
            )

        # Rule 9: memory_extracted + no conflict → SILENT
        if trigger_type == "memory_extracted":
            return self._assess_memory_extracted(payload)

        # Rule 10: default
        return ImpactLevel.LOW, "default: minor change"

    @staticmethod
    def _assess_date_approaching(
        payload: Dict[str, Any],
    ) -> tuple:
        """Assess date_approaching triggers based on days_until."""
        days_until = payload.get("days_until")
        if days_until is None:
            return ImpactLevel.MEDIUM, "date approaching (unknown days)"

        try:
            days = float(days_until)
        except (TypeError, ValueError):
            return ImpactLevel.MEDIUM, "date approaching (invalid days_until)"

        if days <= 3:
            return ImpactLevel.HIGH, f"date approaching in {days:.0f} days (urgent)"
        if days <= 7:
            return ImpactLevel.MEDIUM, f"date approaching in {days:.0f} days"

        return ImpactLevel.LOW, f"date approaching in {days:.0f} days (not urgent)"

    @staticmethod
    def _assess_time_shift(
        diff: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> Optional[tuple]:
        """Check if time shift is small enough for LOW impact.

        Returns (level, reason) tuple or None if this rule doesn't apply.
        """
        if "start_time" not in diff:
            return None

        start_time_diff = diff["start_time"]
        if not isinstance(start_time_diff, dict):
            return None

        delta_hours = start_time_diff.get("delta_hours")
        if delta_hours is None:
            return None

        try:
            shift = abs(float(delta_hours))
        except (TypeError, ValueError):
            return None

        has_conflict = bool(payload.get("has_conflict"))

        if shift < _TIME_SHIFT_LOW_THRESHOLD_HOURS and not has_conflict:
            return (
                ImpactLevel.LOW,
                f"time shift {shift:.1f}h (< {_TIME_SHIFT_LOW_THRESHOLD_HOURS}h, no conflict)",
            )

        # Time shift is significant or has conflict — let other rules decide
        return None

    @staticmethod
    def _assess_memory_extracted(
        payload: Dict[str, Any],
    ) -> tuple:
        """Assess memory_extracted triggers."""
        has_conflict = bool(payload.get("has_conflict"))
        if has_conflict:
            return ImpactLevel.MEDIUM, "memory extracted with conflict"
        return ImpactLevel.SILENT, "memory extracted without conflict"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decide_mode(level: ImpactLevel) -> ExecutionMode:
    """Map impact level to execution mode."""
    return _LEVEL_TO_MODE[level]


_LEVEL_TO_MODE: Dict[ImpactLevel, ExecutionMode] = {
    ImpactLevel.SILENT: ExecutionMode.SILENT_UPDATE,
    ImpactLevel.LOW: ExecutionMode.T1_HEURISTIC,
    ImpactLevel.MEDIUM: ExecutionMode.T2_INCREMENTAL,
    ImpactLevel.HIGH: ExecutionMode.T3_FULL,
}
