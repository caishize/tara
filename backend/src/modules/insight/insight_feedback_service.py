"""InsightFeedbackService — feedback recording, status transitions, cumulative upgrade.

Handles user feedback on unified Insight records (the ``insights`` table).
Each feedback type maps to a severity level that determines how the insight
is dismissed, snoozed, or permanently suppressed.

Feedback levels:
    Level 1 (timing)   — defer / not_now  → snooze
    Level 2 (content)   — not_useful / not_relevant / incorrect → dismiss + regen suppression
    Level 3 (permanent) — never → dismiss + user_preference_rules entry
"""

from datetime import timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .insight_domain_bridge import (
    InsightAdoptedEntityRef,
    InsightDismissedEvent,
)
from .insight_lifecycle import (
    transition_status,
    get_insight,
    ensure_active_before,
)
from .models import (
    ACKNOWLEDGED_SNOOZE_DAYS,
    Insight,
    InsightStatus,
    SUPPRESSION_WINDOWS,
    SUPPRESSION_THRESHOLDS,
    InvalidTransitionError,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Feedback classification
# ---------------------------------------------------------------------------

# Level 1: timing only — snooze and revisit later
_SNOOZE_FEEDBACKS = frozenset({"defer", "not_now"})

# Level 2: content denial — dismiss + regeneration suppression
_DISMISS_FEEDBACKS = frozenset({"not_useful", "not_relevant", "incorrect", "dismiss"})

# Level 3: permanent suppression
_PERMANENT_FEEDBACKS = frozenset({"never"})

# Default snooze durations by feedback type
_SNOOZE_DURATIONS: Dict[str, timedelta] = {
    "defer": timedelta(days=3),  # overridden per-type in record_feedback
    "not_now": timedelta(days=3),  # overridden per-type in record_feedback
    "acknowledged": timedelta(days=ACKNOWLEDGED_SNOOZE_DAYS),
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class InsightFeedbackService:
    """Feedback recording + status transitions + cumulative upgrade."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        favor_service=None,
        commitment_service=None,
        temperature_service=None,
        ea_dismiss_fn=None,
    ):
        self.db = db
        self._favor_service = favor_service
        self._commitment_service = commitment_service
        self._temperature_service = temperature_service
        self._ea_dismiss_fn = ea_dismiss_fn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def record_feedback(
        self,
        insight_id: UUID,
        user_id: UUID,
        feedback: str,
        reason: Optional[str] = None,
    ) -> Insight:
        """Record user feedback and execute the corresponding status transition.

        Feedback types and their effects:
        - ``never``: Level 3 permanent suppression -> dismissed +
          ``user_preference_rules`` entry.
        - ``not_useful`` / ``not_relevant`` / ``incorrect``: Level 2 content
          denial -> dismissed + ``regen_suppressed_until``.
          Cumulative dismiss upgrade: same ``dedup_key`` reaches type threshold
          -> auto-upgrade to Level 3.
        - ``defer`` / ``not_now``: Level 1 timing -> ``snoozed_until`` (+3d).
          If ``expires_at`` < ``snoozed_until``, extend ``expires_at``.
        - ``acknowledged``: User confirms awareness -> acknowledged status +
          ``snoozed_until`` +90 days.  Satisfies obligation coverage audit.
        - ``useful``: -> acted status.

        Also writes a PreferenceSignal record and publishes
        ``InsightDismissedEvent`` for dismiss feedback types.

        Returns:
            The updated :class:`Insight` instance.

        Raises:
            ValueError: If ``insight_id`` is not found.
            InvalidTransitionError: If the status transition is not allowed.
        """
        insight = await get_insight(self.db, insight_id)
        if insight is None:
            raise ValueError(f"Insight {insight_id} not found")

        now = utc_now()

        # Normalize alias
        effective_feedback = "defer" if feedback == "not_now" else feedback

        # ---- Level 3: permanent suppression ----
        if effective_feedback in _PERMANENT_FEEDBACKS:
            transition_status(insight, InsightStatus.DISMISSED)
            insight.feedback = effective_feedback
            insight.feedback_at = now
            insight.feedback_source = "user"
            insight.dismissed_at = now
            await self._create_permanent_suppression(insight)
            await self._write_preference_signal(insight, effective_feedback, reason)
            await self._publish_dismissed_event(insight, effective_feedback, reason, permanent=True)

        # ---- Level 2: content denial ----
        elif effective_feedback in _DISMISS_FEEDBACKS:
            transition_status(insight, InsightStatus.DISMISSED)
            insight.feedback = effective_feedback
            insight.feedback_at = now
            insight.feedback_source = "user"
            insight.dismissed_at = now
            suppression_window = self._get_suppression_window(insight)
            insight.regen_suppressed_until = now + suppression_window
            await self._write_preference_signal(insight, effective_feedback, reason)
            await self._publish_dismissed_event(insight, effective_feedback, reason, permanent=False)

            # Cumulative upgrade check
            if insight.dedup_key:
                dismiss_count = await self._get_dismiss_count(user_id, insight.dedup_key)
                threshold = SUPPRESSION_THRESHOLDS.get(insight.insight_type, 5)
                # Current dismiss hasn't been committed yet, so count doesn't include it
                if dismiss_count >= threshold - 1:
                    logger.info(
                        "Cumulative upgrade to permanent suppression: "
                        "user=%s, dedup_key=%s, count=%d, threshold=%d",
                        user_id, insight.dedup_key, dismiss_count, threshold,
                    )
                    await self._create_permanent_suppression(insight)

        # ---- Level 1: timing (snooze) ----
        elif effective_feedback in _SNOOZE_FEEDBACKS:
            # Snooze keeps the current status but sets snoozed_until
            # favor/relationship insights get a longer snooze (7 days)
            snooze_days = 7 if insight.insight_type in ('favor', 'relationship') else 3
            snoozed_until = now + timedelta(days=snooze_days)
            insight.feedback = effective_feedback
            insight.feedback_at = now
            insight.feedback_source = "user"
            insight.snoozed_until = snoozed_until

            # Extend expiry if it would expire before the snooze ends
            if insight.expires_at is not None and insight.expires_at < snoozed_until:
                insight.expires_at = snoozed_until + timedelta(days=1)

            await self._write_preference_signal(insight, effective_feedback, reason)

        # ---- acknowledged ----
        elif effective_feedback == "acknowledged":
            # Idempotent: already acknowledged → just refresh snooze window
            if InsightStatus(insight.status) != InsightStatus.ACKNOWLEDGED:
                ensure_active_before(insight, InsightStatus.ACKNOWLEDGED)
                transition_status(insight, InsightStatus.ACKNOWLEDGED)
            insight.feedback = effective_feedback
            insight.feedback_at = now
            insight.feedback_source = "user"
            insight.acknowledged_at = now
            snooze_duration = _SNOOZE_DURATIONS["acknowledged"]
            insight.snoozed_until = now + snooze_duration
            if insight.expires_at and insight.expires_at < insight.snoozed_until:
                insight.expires_at = insight.snoozed_until + timedelta(days=1)
            await self._write_preference_signal(insight, effective_feedback, reason)

        # ---- useful ----
        elif effective_feedback == "useful":
            ensure_active_before(insight, InsightStatus.ACTED)
            transition_status(insight, InsightStatus.ACTED)
            insight.feedback = effective_feedback
            insight.feedback_at = now
            insight.feedback_source = "user"
            insight.acted_at = now
            await self._write_preference_signal(insight, effective_feedback, reason)

        else:
            raise ValueError(f"Unknown feedback type: {feedback}")

        await self.db.flush()
        logger.info(
            "Recorded feedback: insight=%s, feedback=%s, status=%s",
            insight_id, effective_feedback, insight.status,
        )
        return insight

    async def record_implicit_feedback(
        self,
        insight_id: UUID,
        user_id: UUID,
        implicit_type: str,
        *,
        action_type: Optional[str] = None,
    ) -> Optional["Insight"]:
        """Record implicit feedback inferred from user behavior.

        Wraps ImplicitFeedbackCollector calls and returns the updated
        Insight if applicable.

        Args:
            insight_id: The insight to record feedback for.
            user_id: The user whose behavior was observed.
            implicit_type: One of ImplicitFeedbackType values.
            action_type: For ACTION_ABANDONED, the type of action started.

        Returns:
            The updated Insight, or None if not applicable.
        """
        from .implicit_feedback import ImplicitFeedbackCollector
        from .models import ImplicitFeedbackType

        collector = ImplicitFeedbackCollector(self.db)

        try:
            feedback_type = ImplicitFeedbackType(implicit_type)
        except ValueError:
            logger.warning("Unknown implicit feedback type: %s", implicit_type)
            return None

        try:
            if feedback_type == ImplicitFeedbackType.ACTION_ABANDONED:
                if action_type is None:
                    logger.warning(
                        "action_type required for ACTION_ABANDONED feedback",
                    )
                    return None
                return await collector.record_action_abandoned(
                    insight_id, user_id, action_type,
                )

            elif feedback_type == ImplicitFeedbackType.SUGGESTION_FOLLOWED:
                return await collector.record_suggestion_followed(
                    insight_id, user_id,
                )

            elif feedback_type == ImplicitFeedbackType.TOPIC_MENTIONED:
                return await collector.record_topic_mentioned(
                    insight_id, user_id,
                )

            elif feedback_type == ImplicitFeedbackType.VIEWED_NO_ACTION:
                return await collector.record_viewed_no_action(
                    insight_id, user_id,
                )

        except Exception:
            logger.error(
                "Failed to record implicit feedback: insight=%s, type=%s",
                insight_id, implicit_type,
                exc_info=True,
            )
            return None

        return None

    async def batch_feedback(
        self,
        insight_ids: List[UUID],
        user_id: UUID,
        feedback: str,
        reason: Optional[str] = None,
    ) -> List[Insight]:
        """Apply the same feedback to multiple insights (e.g., dismiss all).

        Processes each insight individually so that per-insight transition
        validation and cumulative upgrade logic still apply.  Failures on
        individual insights are logged and skipped.

        Returns:
            List of successfully updated :class:`Insight` instances.
        """
        results: List[Insight] = []
        for iid in insight_ids:
            try:
                updated = await self.record_feedback(iid, user_id, feedback, reason)
                results.append(updated)
            except (ValueError, InvalidTransitionError) as exc:
                logger.warning(
                    "Skipping insight %s in batch feedback: %s", iid, exc,
                )
        return results

    # ------------------------------------------------------------------
    # Dismiss counting & suppression
    # ------------------------------------------------------------------

    async def _get_dismiss_count(self, user_id: UUID, dedup_key: str) -> int:
        """Count previous user dismissals for the same ``dedup_key``.

        Only counts insights with ``status='dismissed'`` and a Level 2 feedback type.
        """
        stmt = (
            select(func.count(Insight.id))
            .where(
                and_(
                    Insight.user_id == user_id,
                    Insight.dedup_key == dedup_key,
                    Insight.status == InsightStatus.DISMISSED.value,
                    Insight.feedback.in_(list(_DISMISS_FEEDBACKS)),
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    def _get_suppression_window(self, insight: Insight) -> timedelta:
        """Return suppression window based on insight type."""
        return SUPPRESSION_WINDOWS.get(
            insight.insight_type,
            timedelta(days=14),  # safe default
        )

    async def _create_permanent_suppression(self, insight: Insight) -> None:
        """Create a ``user_preference_rules`` entry for permanent suppression.

        Uses lazy import to avoid circular dependency with the curation module.
        """
        try:
            from ..curation.models import UserPreferenceRule
        except ImportError:
            logger.error(
                "Cannot import UserPreferenceRule — permanent suppression skipped "
                "for insight %s",
                insight.id,
            )
            return

        rule = UserPreferenceRule(
            user_id=insight.user_id,
            family_id=insight.family_id,
            condition_suggestion_type=insight.insight_type,
            action="suppress",
            confidence=1.0,
            explanation=f"User selected 'never' for insight dedup_key={insight.dedup_key}",
            scope="event_type",
            source_signal_count=1,
            expires_at=utc_now() + timedelta(days=365 * 10),
            is_active=True,
        )
        self.db.add(rule)
        logger.info(
            "Created permanent suppression rule: user=%s, type=%s, dedup_key=%s",
            insight.user_id, insight.insight_type, insight.dedup_key,
        )

    # ------------------------------------------------------------------
    # Preference signal recording
    # ------------------------------------------------------------------

    async def _write_preference_signal(
        self,
        insight: Insight,
        feedback: str,
        reason: Optional[str],
    ) -> None:
        """Write a PreferenceSignal for downstream preference extraction."""
        try:
            from ..curation.models import PreferenceSignal
        except ImportError:
            logger.warning("Cannot import PreferenceSignal — signal not recorded")
            return

        signal = PreferenceSignal(
            user_id=insight.user_id,
            family_id=insight.family_id,
            signal_type=feedback,
            source_type="insight",
            source_id=insight.id,
            source_context={
                "insight_type": insight.insight_type,
                "dedup_key": insight.dedup_key,
                "title": insight.title,
                "importance": insight.importance,
            },
            user_reason=reason,
            category_key=f"insight:{insight.insight_type}:{insight.dedup_key or 'none'}",
        )
        self.db.add(signal)

    # ------------------------------------------------------------------
    # Event publishing (placeholder — logs until full event bus)
    # ------------------------------------------------------------------

    async def _publish_dismissed_event(
        self,
        insight: Insight,
        feedback: str,
        reason: Optional[str],
        *,
        permanent: bool,
    ) -> None:
        """Publish InsightDismissedEvent and execute domain bridge writeback."""
        from .insight_domain_bridge import InsightDomainBridge

        entity_refs = [
            InsightAdoptedEntityRef(
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                role=e.role,
            )
            for e in (insight.entities or [])
        ]
        event = InsightDismissedEvent(
            insight_id=insight.id,
            insight_type=insight.insight_type,
            user_id=insight.user_id,
            family_id=insight.family_id,
            feedback=feedback,
            permanent=permanent,
            entities=entity_refs,
        )
        logger.info(
            "InsightDismissedEvent: insight=%s, permanent=%s, feedback=%s",
            event.insight_id, event.permanent, event.feedback,
        )

        # Execute domain bridge writeback (best-effort)
        try:
            bridge = InsightDomainBridge(
                self.db,
                favor_service=self._favor_service,
                commitment_service=self._commitment_service,
                temperature_service=self._temperature_service,
                ea_dismiss_fn=self._ea_dismiss_fn,
            )
            await bridge.handle_insight_dismissed(event)
        except Exception:
            logger.warning(
                "Domain bridge writeback failed for dismissed insight %s",
                insight.id,
                exc_info=True,
            )

