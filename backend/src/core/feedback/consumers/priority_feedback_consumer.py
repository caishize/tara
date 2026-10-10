"""PriorityFeedbackConsumer - learns event type severity from user behavior.

Consumes:
    EVENT_RESCHEDULED  - user moved an event to a different time
    EVENT_CANCELLED    - user cancelled an event entirely
    PRIORITY_OVERRIDE  - user manually overrode the system's priority

Writes to:
    FamilyPreference.event_type_severity  (JSONB)
    FamilyPreference.priority_weights     (JSONB, for PRIORITY_OVERRIDE)

Learning logic:
    - Repeated rescheduling/cancellation of an event type  -> lower severity
    - PRIORITY_OVERRIDE with higher priority -> increase urgency weight
    - PRIORITY_OVERRIDE with lower priority  -> decrease urgency weight

Expected ``data`` payloads:
    EVENT_RESCHEDULED: {"event_type": "meeting", "reschedule_count": 2}
    EVENT_CANCELLED:   {"event_type": "meeting"}
    PRIORITY_OVERRIDE: {"event_type": "medical", "old_priority": 3, "new_priority": 8}
"""

import logging
from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..feedback_bus import FeedbackConsumer, FeedbackEvent, FeedbackSignal

logger = logging.getLogger(__name__)

# Severity decay factor when an event type is rescheduled
_RESCHEDULE_DECAY = 0.95

# Severity decay factor when an event type is cancelled
_CANCEL_DECAY = 0.90

# Severity floor - never go below this
_MIN_SEVERITY = 0.1

# Severity ceiling
_MAX_SEVERITY = 1.0

# Default severity for unseen event types
_DEFAULT_SEVERITY = 0.5


class PriorityFeedbackConsumer:
    """Adjusts event_type_severity based on reschedule/cancel/override signals."""

    def __init__(self, db: async_sessionmaker) -> None:
        self._session_factory = db

    @property
    def consumes_signals(self) -> List[FeedbackSignal]:
        return [
            FeedbackSignal.EVENT_RESCHEDULED,
            FeedbackSignal.EVENT_CANCELLED,
            FeedbackSignal.PRIORITY_OVERRIDE,
        ]

    async def on_feedback(self, event: FeedbackEvent) -> None:
        try:
            async with self._session_factory() as session:
                self._session = session
                if event.signal == FeedbackSignal.EVENT_RESCHEDULED:
                    await self._handle_rescheduled(event)
                elif event.signal == FeedbackSignal.EVENT_CANCELLED:
                    await self._handle_cancelled(event)
                elif event.signal == FeedbackSignal.PRIORITY_OVERRIDE:
                    await self._handle_priority_override(event)
                await session.commit()
        except Exception as exc:
            logger.error(
                "PriorityFeedbackConsumer failed for %s (family=%s): %s",
                event.signal.value, event.family_id, exc,
                exc_info=True,
            )

    async def _handle_rescheduled(self, event: FeedbackEvent) -> None:
        event_type = event.data.get("event_type")
        if not event_type:
            return
        await self._decay_severity(event.family_id, event_type, _RESCHEDULE_DECAY)

    async def _handle_cancelled(self, event: FeedbackEvent) -> None:
        event_type = event.data.get("event_type")
        if not event_type:
            return
        await self._decay_severity(event.family_id, event_type, _CANCEL_DECAY)

    async def _handle_priority_override(self, event: FeedbackEvent) -> None:
        event_type = event.data.get("event_type")
        old_priority = event.data.get("old_priority")
        new_priority = event.data.get("new_priority")
        if not event_type or old_priority is None or new_priority is None:
            return

        repo = await self._get_repo()
        pref = await repo.get_or_create_default(event.family_id)
        current_severity: dict = dict(pref.event_type_severity or {})
        current = current_severity.get(event_type, _DEFAULT_SEVERITY)

        # If user raised priority, increase severity; if lowered, decrease
        if new_priority > old_priority:
            adjusted = min(_MAX_SEVERITY, current * 1.1)
        else:
            adjusted = max(_MIN_SEVERITY, current * 0.9)

        await repo.update_weights(
            event.family_id,
            "event_type_severity",
            {event_type: round(adjusted, 4)},
        )
        logger.info(
            "PriorityFeedbackConsumer: %s severity %.3f -> %.3f (family=%s)",
            event_type, current, adjusted, event.family_id,
        )

    async def _decay_severity(
        self, family_id: UUID, event_type: str, factor: float,
    ) -> None:
        repo = await self._get_repo()
        pref = await repo.get_or_create_default(family_id)
        current_severity: dict = dict(pref.event_type_severity or {})
        current = current_severity.get(event_type, _DEFAULT_SEVERITY)
        decayed = max(_MIN_SEVERITY, current * factor)

        await repo.update_weights(
            family_id,
            "event_type_severity",
            {event_type: round(decayed, 4)},
        )
        logger.info(
            "PriorityFeedbackConsumer: %s severity %.3f -> %.3f (family=%s)",
            event_type, current, decayed, family_id,
        )

    async def _get_repo(self):
        from ....modules.curation.services.family_preference_repository import (
            FamilyPreferenceRepository,
        )
        return FamilyPreferenceRepository(self._session)
