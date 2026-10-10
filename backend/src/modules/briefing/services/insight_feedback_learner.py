"""
InsightFeedbackLearner - Learns from user feedback to improve insight quality.

Adjusts insight type weights based on a 90-day rolling window of feedback,
consuming the 7-type FeedbackType enum natively (PLAN-007).

Weight adjustment per signal type:
- USEFUL       -> +0.15 (strong positive signal)
- NOT_USEFUL   -> -0.08 (mild negative)
- NOT_RELEVANT -> -0.12 (type-mismatch: stronger penalty)
- TOO_FREQUENT -> -0.06 (frequency issue: reduce, don't eliminate)
- INCORRECT    -> -0.10 (factual error: moderate penalty)
- DEFER        -> -0.03 (user wants it later, not eliminated)
- NEVER        -> suppressed (handled in get_suppressed_types)

Legacy 3-type → 7-type mapping for historical data:
- "useful"     -> USEFUL
- "ignored"    -> NOT_USEFUL
- "never_again"-> NEVER (handled in get_suppressed_types)
"""
from datetime import timedelta
from typing import Dict, Optional, Set
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now
from ...insight.models import FeedbackType, Insight

logger = get_logger(__name__)

# Weight adjustment constants (7-type native)
_WEIGHT_ADJUSTMENTS: Dict[str, float] = {
    FeedbackType.USEFUL.value:        +0.15,
    FeedbackType.NOT_USEFUL.value:    -0.08,
    FeedbackType.NOT_RELEVANT.value:  -0.12,
    FeedbackType.TOO_FREQUENT.value:  -0.06,
    FeedbackType.INCORRECT.value:     -0.10,
    FeedbackType.DEFER.value:         -0.03,
    FeedbackType.NEVER.value:          0.0,   # handled by suppression
    # Legacy 3-type values (historical rows may use these strings)
    "ignored":    -0.08,   # maps to NOT_USEFUL
    "never_again": 0.0,    # handled by suppression
}

# Suppression triggers: feedback values that mean "never show this type again"
_SUPPRESSION_VALUES = frozenset({
    FeedbackType.NEVER.value,
    "never_again",  # legacy
})

# NOT_USEFUL threshold: 3+ signals in rolling window → zero budget
NOT_USEFUL_ZERO_BUDGET_THRESHOLD = 3

MIN_WEIGHT = 0.0   # 0 = budget zeroed for type
MAX_WEIGHT = 2.0
DEFAULT_WEIGHT = 1.0
ROLLING_WINDOW_DAYS = 90


class InsightFeedbackLearner:
    """
    Insight feedback learner.

    Responsibilities:
    1. Record user feedback on insights
    2. Calculate adjusted insight type weights (90-day rolling window, 7-type native)
    3. Determine whether to suppress certain insight types
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_feedback(
        self,
        user_id: UUID,
        insight_id: UUID,
        feedback_type: str,
    ) -> bool:
        """
        Record user feedback.

        Returns True if feedback recorded, False if insight not found.
        """
        stmt = select(Insight).where(
            and_(
                Insight.id == insight_id,
                Insight.user_id == user_id,
            )
        )
        result = await self.db.execute(stmt)
        insight = result.scalar_one_or_none()

        if not insight:
            return False

        insight.feedback = feedback_type
        insight.feedback_at = utc_now()

        # Mark dismissed for suppression-level feedback
        if feedback_type in _SUPPRESSION_VALUES:
            insight.status = "dismissed"

        await self.db.commit()

        await self._emit_feedback_signal(insight, feedback_type)

        logger.info(
            "Recorded feedback for insight %s: type=%s, feedback=%s",
            insight_id,
            insight.insight_type,
            feedback_type,
        )
        return True

    async def _emit_feedback_signal(
        self,
        insight: Insight,
        feedback_type: str,
    ) -> None:
        """Emit mapped FeedbackBus signal after recording feedback.

        Maps the 7-type FeedbackType to FeedbackSignal, then emits
        via the singleton FeedbackBus. Errors are logged but never
        raised -- emission must not break feedback recording.
        """
        from ....config.settings import settings as _settings

        if not _settings.feedback_bus_emission_enabled:
            return

        from ....core.feedback.feedback_bus import FeedbackSignal, get_feedback_bus

        _FEEDBACK_TO_SIGNAL = {
            FeedbackType.USEFUL.value: FeedbackSignal.INSIGHT_USEFUL,
            FeedbackType.NOT_USEFUL.value: FeedbackSignal.INSIGHT_NOT_USEFUL,
            FeedbackType.NOT_RELEVANT.value: FeedbackSignal.INSIGHT_NOT_USEFUL,
            FeedbackType.INCORRECT.value: FeedbackSignal.INSIGHT_NOT_USEFUL,
            FeedbackType.TOO_FREQUENT.value: FeedbackSignal.INSIGHT_NOT_USEFUL,
            FeedbackType.NEVER.value: FeedbackSignal.INSIGHT_NEVER_AGAIN,
            FeedbackType.DEFER.value: FeedbackSignal.INSIGHT_DEFERRED,
            # Legacy 3-type mappings
            "useful": FeedbackSignal.INSIGHT_USEFUL,
            "ignored": FeedbackSignal.INSIGHT_NOT_USEFUL,
            "never_again": FeedbackSignal.INSIGHT_NEVER_AGAIN,
        }

        signal = _FEEDBACK_TO_SIGNAL.get(feedback_type)
        if signal is None:
            return

        try:
            bus = get_feedback_bus()
            await bus.emit(
                signal=signal,
                data={
                    "insight_type": insight.insight_type,
                    "insight_id": str(insight.id) if insight.id else None,
                    "feedback_type": feedback_type,
                },
                family_id=insight.family_id,
                user_id=insight.user_id,
                source="insight_feedback_learner",
            )
        except Exception as exc:
            logger.warning(
                "FeedbackBus emission failed for insight %s: %s",
                insight.id, exc,
            )

    async def record_lifecycle_transition(
        self,
        insight: Insight,
        transition_type: str,
    ) -> None:
        """Emit FeedbackBus signal for non-user-initiated lifecycle changes.

        Called by ReflectionService (auto-dismiss) and TriggerDispatcher
        (cascade dismiss). Does NOT modify the insight record -- the caller
        owns the status update.
        """
        from ....config.settings import settings as _settings

        if not _settings.feedback_bus_emission_enabled:
            return

        from ....core.feedback.feedback_bus import FeedbackSignal, get_feedback_bus

        _TRANSITION_TO_SIGNAL = {
            "auto_dismiss": FeedbackSignal.INSIGHT_IGNORED,
            "cascade_dismiss": FeedbackSignal.INSIGHT_IGNORED,
            "fulfilled": FeedbackSignal.SUGGESTION_ACTED,
        }

        signal = _TRANSITION_TO_SIGNAL.get(transition_type)
        if signal is None:
            return

        try:
            bus = get_feedback_bus()
            await bus.emit(
                signal=signal,
                data={
                    "insight_type": insight.insight_type,
                    "insight_id": str(insight.id) if insight.id else None,
                    "transition_type": transition_type,
                },
                family_id=insight.family_id,
                user_id=insight.user_id,
                source="lifecycle_transition",
            )
        except Exception as exc:
            logger.warning(
                "FeedbackBus lifecycle emission failed for insight %s: %s",
                insight.id, exc,
            )

    async def get_adjusted_weights(
        self,
        user_id: UUID,
    ) -> Dict[str, float]:
        """Calculate adjusted insight type weights using a 90-day rolling window.

        Consumes the 7-type FeedbackType enum natively:
        - NOT_RELEVANT and TOO_FREQUENT get distinct weight adjustments (not both
          collapsed into the same IGNORED bucket as in the old 3-type system).
        - Legacy 3-type historical data is mapped via _WEIGHT_ADJUSTMENTS.

        Contract: Returns Dict[str, float] with insight_type keys and clamped float
        weights in [MIN_WEIGHT, MAX_WEIGHT]. Caller (_build_generation_budget) expects
        this exact contract.

        TC-3: After 3+ NOT_USEFUL signals for a type within the rolling window,
        weight is set to MIN_WEIGHT (0.0), which maps to budget 0 in
        _build_generation_budget().
        """
        cutoff = utc_now() - timedelta(days=ROLLING_WINDOW_DAYS)

        stmt = (
            select(
                Insight.insight_type,
                Insight.feedback,
                func.count(Insight.id),
            )
            .where(
                and_(
                    Insight.user_id == user_id,
                    Insight.feedback.isnot(None),
                    Insight.feedback_at >= cutoff,
                )
            )
            .group_by(Insight.insight_type, Insight.feedback)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        # Accumulate per-type weight deltas and NOT_USEFUL counts
        weight_deltas: Dict[str, float] = {}
        not_useful_counts: Dict[str, int] = {}

        for insight_type, feedback, count in rows:
            adjustment = _WEIGHT_ADJUSTMENTS.get(feedback, 0.0)
            if adjustment != 0.0:
                weight_deltas[insight_type] = weight_deltas.get(insight_type, 0.0) + adjustment * count

            # Track NOT_USEFUL count for TC-3 threshold
            if feedback in (FeedbackType.NOT_USEFUL.value, "ignored"):
                not_useful_counts[insight_type] = not_useful_counts.get(insight_type, 0) + count

        # Build final weights
        all_types = set(weight_deltas.keys()) | set(not_useful_counts.keys())
        weights: Dict[str, float] = {}
        for itype in all_types:
            raw = DEFAULT_WEIGHT + weight_deltas.get(itype, 0.0)
            # TC-3: 3+ NOT_USEFUL signals → zero budget
            if not_useful_counts.get(itype, 0) >= NOT_USEFUL_ZERO_BUDGET_THRESHOLD:
                raw = MIN_WEIGHT
            weights[itype] = max(MIN_WEIGHT, min(MAX_WEIGHT, raw))

        return weights

    async def should_suppress(
        self,
        user_id: UUID,
        insight_type: str,
    ) -> bool:
        """Determine whether to suppress a certain insight type.

        Suppresses if the user has given NEVER or legacy "never_again" feedback
        for this type. NEVER is permanent -- no rolling window cutoff.
        """
        stmt = (
            select(func.count(Insight.id))
            .where(
                and_(
                    Insight.user_id == user_id,
                    Insight.insight_type == insight_type,
                    Insight.feedback.in_(list(_SUPPRESSION_VALUES)),
                )
            )
        )
        result = await self.db.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def get_suppressed_types(
        self,
        user_id: UUID,
    ) -> Set[str]:
        """Get the set of insight types the user has suppressed.

        Considers both 7-type NEVER and legacy "never_again".
        NEVER is permanent -- no rolling window cutoff.
        """
        stmt = (
            select(Insight.insight_type)
            .where(
                and_(
                    Insight.user_id == user_id,
                    Insight.feedback.in_(list(_SUPPRESSION_VALUES)),
                )
            )
            .distinct()
        )
        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}
