"""AssociationFeedbackConsumer - learns association type effectiveness.

Consumes:
    CONTACT_INITIATED   - user acted on a contact suggestion
    CONTACT_SKIPPED     - user ignored/dismissed a contact suggestion
    ANNOTATION_HELPFUL  - user marked a secretary annotation as helpful
    ANNOTATION_DISMISSED - user dismissed a secretary annotation

Writes to:
    FamilyPreference.association_weights  (JSONB)

Learning logic:
    - CONTACT_INITIATED  -> association type weight +0.2  (capped at 2.0)
    - CONTACT_SKIPPED    -> association type weight -0.1  (floored at 0.1)
    - ANNOTATION_HELPFUL -> annotation type weight +0.15 (capped at 2.0)
    - ANNOTATION_DISMISSED -> annotation type weight -0.1 (floored at 0.1)

Expected ``data`` payloads:
    CONTACT_INITIATED:   {"association_type": "stale_contact", "member_id": "..."}
    CONTACT_SKIPPED:     {"association_type": "stale_contact", "member_id": "..."}
    ANNOTATION_HELPFUL:  {"annotation_type": "preparation_hint"}
    ANNOTATION_DISMISSED: {"annotation_type": "preparation_hint"}
"""

import logging
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..feedback_bus import FeedbackConsumer, FeedbackEvent, FeedbackSignal

logger = logging.getLogger(__name__)

# Weight adjustment amounts
_INITIATED_BOOST = 0.2
_SKIPPED_PENALTY = 0.1
_HELPFUL_BOOST = 0.15

# Weight bounds
_MIN_WEIGHT = 0.1
_MAX_WEIGHT = 2.0
_DEFAULT_WEIGHT = 1.0


class AssociationFeedbackConsumer:
    """Adjusts association_weights based on contact/annotation feedback."""

    def __init__(self, db: async_sessionmaker) -> None:
        self._session_factory = db

    @property
    def consumes_signals(self) -> List[FeedbackSignal]:
        return [
            FeedbackSignal.CONTACT_INITIATED,
            FeedbackSignal.CONTACT_SKIPPED,
            FeedbackSignal.ANNOTATION_HELPFUL,
            FeedbackSignal.ANNOTATION_DISMISSED,
        ]

    async def on_feedback(self, event: FeedbackEvent) -> None:
        try:
            async with self._session_factory() as session:
                self._session = session
                if event.signal == FeedbackSignal.CONTACT_INITIATED:
                    await self._handle_contact_initiated(event)
                elif event.signal == FeedbackSignal.CONTACT_SKIPPED:
                    await self._handle_contact_skipped(event)
                elif event.signal == FeedbackSignal.ANNOTATION_HELPFUL:
                    await self._handle_annotation_helpful(event)
                elif event.signal == FeedbackSignal.ANNOTATION_DISMISSED:
                    await self._handle_annotation_dismissed(event)
                await session.commit()
        except Exception as exc:
            logger.error(
                "AssociationFeedbackConsumer failed for %s (family=%s): %s",
                event.signal.value, event.family_id, exc,
                exc_info=True,
            )

    async def _handle_contact_initiated(self, event: FeedbackEvent) -> None:
        assoc_type = event.data.get("association_type")
        if not assoc_type:
            return
        await self._adjust_weight(
            event.family_id, assoc_type, _INITIATED_BOOST,
        )

    async def _handle_contact_skipped(self, event: FeedbackEvent) -> None:
        assoc_type = event.data.get("association_type")
        if not assoc_type:
            return
        await self._adjust_weight(
            event.family_id, assoc_type, -_SKIPPED_PENALTY,
        )

    async def _handle_annotation_helpful(self, event: FeedbackEvent) -> None:
        annotation_type = event.data.get("annotation_type")
        if not annotation_type:
            return
        # Store annotation weights under a prefixed key to avoid collisions
        key = f"annotation:{annotation_type}"
        await self._adjust_weight(event.family_id, key, _HELPFUL_BOOST)

    async def _handle_annotation_dismissed(self, event: FeedbackEvent) -> None:
        annotation_type = event.data.get("annotation_type")
        if not annotation_type:
            return
        key = f"annotation:{annotation_type}"
        await self._adjust_weight(event.family_id, key, -_SKIPPED_PENALTY)

    async def _adjust_weight(
        self, family_id, key: str, delta: float,
    ) -> None:
        repo = await self._get_repo()
        pref = await repo.get_or_create_default(family_id)
        current_weights: dict = dict(pref.association_weights or {})
        current = current_weights.get(key, _DEFAULT_WEIGHT)
        adjusted = max(_MIN_WEIGHT, min(_MAX_WEIGHT, current + delta))

        await repo.update_weights(
            family_id,
            "association_weights",
            {key: round(adjusted, 4)},
        )
        logger.info(
            "AssociationFeedbackConsumer: %s weight %.3f -> %.3f (family=%s)",
            key, current, adjusted, family_id,
        )

    async def _get_repo(self):
        from ....modules.curation.services.family_preference_repository import (
            FamilyPreferenceRepository,
        )
        return FamilyPreferenceRepository(self._session)
