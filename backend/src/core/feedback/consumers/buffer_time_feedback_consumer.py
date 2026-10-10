"""BufferTimeFeedbackConsumer - learns buffer time preferences.

Consumes:
    BUFFER_ADJUSTED  - user manually adjusted buffer time for an event

Writes to:
    FamilyPreference.buffer_minutes  (JSONB)

Learning logic:
    When user adjusts buffer time, update the preference for that context
    (event type or "default") using exponential moving average (EMA).
    This smooths out one-off adjustments while tracking sustained preferences.

Expected ``data`` payload:
    BUFFER_ADJUSTED: {
        "event_type": "meeting",   # or "default" if no specific type
        "new_buffer_minutes": 30,
        "old_buffer_minutes": 15,  # optional, for logging
    }

buffer_minutes structure:
    {
        "default": 15,
        "meeting": 10,
        "location_change": 45,
        ...
    }
"""

import logging
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..feedback_bus import FeedbackConsumer, FeedbackEvent, FeedbackSignal

logger = logging.getLogger(__name__)

# EMA smoothing factor: higher = more responsive to recent changes
_EMA_ALPHA = 0.3

# Default buffer when no preference exists
_DEFAULT_BUFFER = 15

# Clamp bounds (minutes)
_MIN_BUFFER = 0
_MAX_BUFFER = 180


class BufferTimeFeedbackConsumer:
    """Updates buffer_minutes preferences from user adjustments."""

    def __init__(self, db: async_sessionmaker) -> None:
        self._session_factory = db

    @property
    def consumes_signals(self) -> List[FeedbackSignal]:
        return [FeedbackSignal.BUFFER_ADJUSTED]

    async def on_feedback(self, event: FeedbackEvent) -> None:
        try:
            async with self._session_factory() as session:
                self._session = session
                await self._handle_buffer_adjusted(event)
                await session.commit()
        except Exception as exc:
            logger.error(
                "BufferTimeFeedbackConsumer failed for %s (family=%s): %s",
                event.signal.value, event.family_id, exc,
                exc_info=True,
            )

    async def _handle_buffer_adjusted(self, event: FeedbackEvent) -> None:
        new_buffer = event.data.get("new_buffer_minutes")
        if new_buffer is None:
            return

        event_type = event.data.get("event_type", "default")
        new_buffer = max(_MIN_BUFFER, min(_MAX_BUFFER, int(new_buffer)))

        repo = await self._get_repo()
        pref = await repo.get_or_create_default(event.family_id)
        current_buffers: dict = dict(pref.buffer_minutes or {})
        current = current_buffers.get(event_type, _DEFAULT_BUFFER)

        # Exponential moving average to smooth preferences
        smoothed = round(_EMA_ALPHA * new_buffer + (1 - _EMA_ALPHA) * current)
        smoothed = max(_MIN_BUFFER, min(_MAX_BUFFER, smoothed))

        await repo.update_weights(
            event.family_id,
            "buffer_minutes",
            {event_type: smoothed},
        )
        logger.info(
            "BufferTimeFeedbackConsumer: %s buffer %d -> %d (EMA from %d) (family=%s)",
            event_type, current, smoothed, new_buffer, event.family_id,
        )

    async def _get_repo(self):
        from ....modules.curation.services.family_preference_repository import (
            FamilyPreferenceRepository,
        )
        return FamilyPreferenceRepository(self._session)
