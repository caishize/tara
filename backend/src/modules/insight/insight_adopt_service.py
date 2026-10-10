"""InsightAdoptService — adopt insight to trip + trip task done tracking.

Handles the "adopt" flow where a user acts on an insight by linking it to
a trip entity, and later marks individual entity dimensions as done.

Uses optimistic locking via ``WHERE status IN (...)`` + rowcount check
to prevent double-adopt race conditions.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .insight_domain_bridge import (
    InsightAdoptedEntityRef,
    InsightAdoptedEvent,
    TaskCompletedEvent,
)
from .insight_lifecycle import (
    transition_status,
    get_insight,
    ensure_active_before,
)
from .models import (
    Insight,
    InsightEntity,
    InsightStatus,
    InvalidTransitionError,
    InsightNotActionableError,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Actionable statuses for adopt
# ---------------------------------------------------------------------------

_ADOPTABLE_STATUSES = frozenset({
    InsightStatus.PENDING.value,
    InsightStatus.ACTIVE.value,
    InsightStatus.ACKNOWLEDGED.value,
})


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class InsightAdoptService:
    """Adopt insight to trip + trip task done tracking."""

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

    async def adopt_to_trip(
        self,
        insight_id: UUID,
        user_id: UUID,
        trip_id: UUID,
    ) -> Insight:
        """Adopt an insight to a trip.

        - Optimistic lock: ``WHERE status IN ('pending', 'active', 'acknowledged')``
          + ``RETURNING id`` check rowcount.
        - Sets ``status='acted'``, ``feedback='useful'``, ``feedback_at=now``,
          ``feedback_source='user'``.
        - Sets ``adopted_at`` on the trip entity link (upsert if not exists).
        - Publishes ``InsightAdoptedEvent``.

        Returns:
            The updated :class:`Insight`.

        Raises:
            InsightNotActionableError: If the insight is not in an adoptable status
                (race condition or already adopted).
            ValueError: If the insight is not found.
        """
        now = utc_now()

        # Optimistic update: only succeed if status is still adoptable
        stmt = (
            update(Insight)
            .where(
                and_(
                    Insight.id == insight_id,
                    Insight.user_id == user_id,
                    Insight.status.in_(list(_ADOPTABLE_STATUSES)),
                )
            )
            .values(
                status=InsightStatus.ACTED.value,
                feedback="useful",
                feedback_at=now,
                feedback_source="user",
                acted_at=now,
            )
            .returning(Insight.id)
        )
        result = await self.db.execute(stmt)
        row = result.first()
        if row is None:
            # Either insight does not exist or status was not adoptable
            existing = await get_insight(self.db, insight_id)
            if existing is None:
                raise ValueError(f"Insight {insight_id} not found")
            raise InsightNotActionableError(
                f"Insight {insight_id} is not adoptable: current status={existing.status}"
            )

        # Upsert trip entity link with adopted_at
        await self._upsert_trip_entity(insight_id, trip_id, now)

        # Write preference signal for positive feedback
        await self._write_preference_signal_useful(insight_id, user_id)

        await self.db.flush()

        # Re-fetch the full insight (with entities loaded) to return and publish event
        insight = await get_insight(self.db, insight_id)

        # Publish event with full entity context
        await self._publish_adopted_event(insight, trip_id)
        logger.info(
            "Adopted insight to trip: insight=%s, trip=%s, user=%s",
            insight_id, trip_id, user_id,
        )
        return insight

    async def mark_trip_task_done(
        self,
        insight_id: UUID,
        user_id: UUID,
        trip_id: UUID,
        completed_entity_ids: Optional[List[UUID]] = None,
    ) -> Insight:
        """Mark trip task entity dimensions as done.

        - ``completed_entity_ids``: which entity dimensions are completed.
          For single-entity insights, can omit (treats as all complete).
          For multi-entity insights, must specify.
        - Sets ``done_at`` per entity.
        - Checks if all primary/related entities are done -> if so,
          transitions insight to ``acted``.
        - Publishes ``TaskCompletedEvent``.

        Returns:
            The updated :class:`Insight`.

        Raises:
            ValueError: If insight not found.
            InsightNotActionableError: If the insight has not been adopted to this trip.
        """
        now = utc_now()
        insight = await get_insight(self.db, insight_id)
        if insight is None:
            raise ValueError(f"Insight {insight_id} not found")

        # Get all entity links for this insight + trip
        trip_entities = await self._get_entities_if_trip_adopted(insight_id, trip_id)
        if not trip_entities:
            raise InsightNotActionableError(
                f"Insight {insight_id} has not been adopted to trip {trip_id}"
            )

        # Determine which entities to mark done
        entities = [e for e in trip_entities if e.role in ('primary', 'related')]
        if len(entities) > 1 and not completed_entity_ids:
            raise ValueError("Multi-entity insight requires explicit completed_entity_ids")
        target_entity_ids = completed_entity_ids or [e.entity_id for e in entities]

        # Mark done_at for each target entity
        marked_ids: List[UUID] = []
        for entity in trip_entities:
            if entity.entity_id in target_entity_ids and entity.done_at is None:
                stmt = (
                    update(InsightEntity.__table__)
                    .where(
                        and_(
                            InsightEntity.insight_id == insight_id,
                            InsightEntity.entity_type == entity.entity_type,
                            InsightEntity.entity_id == entity.entity_id,
                        )
                    )
                    .values(done_at=now)
                )
                await self.db.execute(stmt)
                marked_ids.append(entity.entity_id)

        # Check if all primary/related entities are done
        all_done = await self._check_all_entities_done(insight_id)

        # If all done and not already acted, transition to acted
        if all_done and insight.status != InsightStatus.ACTED.value:
            ensure_active_before(insight, InsightStatus.ACTED)
            transition_status(insight, InsightStatus.ACTED)
            insight.acted_at = now
            insight.feedback = "useful"
            insight.feedback_at = now
            insight.feedback_source = "user"

        await self.db.flush()

        # Re-fetch for up-to-date state
        insight = await get_insight(self.db, insight_id)

        # Publish event with full context
        await self._publish_task_completed_event(insight, trip_id, marked_ids, all_done)

        logger.info(
            "Marked trip task done: insight=%s, trip=%s, entities=%s, all_done=%s",
            insight_id, trip_id, marked_ids, all_done,
        )
        return insight

    # ------------------------------------------------------------------
    # Entity helpers
    # ------------------------------------------------------------------

    async def _upsert_trip_entity(
        self,
        insight_id: UUID,
        trip_id: UUID,
        now: datetime,
    ) -> None:
        """Upsert the trip entity link with ``adopted_at`` set.

        If the insight already has a trip entity link, update ``adopted_at``.
        Otherwise, create a new link with role='primary'.
        """
        stmt = select(InsightEntity).where(
            and_(
                InsightEntity.insight_id == insight_id,
                InsightEntity.entity_type == "trip",
                InsightEntity.entity_id == trip_id,
            )
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.adopted_at = now
        else:
            entity = InsightEntity(
                insight_id=insight_id,
                entity_type="trip",
                entity_id=trip_id,
                role="related",
                adopted_at=now,
            )
            self.db.add(entity)

    async def _get_entities_if_trip_adopted(
        self,
        insight_id: UUID,
        trip_id: UUID,
    ) -> List[InsightEntity]:
        """Get all entity links for an insight that have been adopted to a trip.

        Returns entities where:
        - The trip entity itself has adopted_at set, OR
        - Any entity belonging to this insight (for multi-entity completion tracking).
        """
        # First verify the trip itself is adopted
        trip_check_stmt = (
            select(InsightEntity)
            .where(
                and_(
                    InsightEntity.insight_id == insight_id,
                    InsightEntity.entity_type == "trip",
                    InsightEntity.entity_id == trip_id,
                )
            )
        )
        trip_result = await self.db.execute(trip_check_stmt)
        trip_entity = trip_result.scalar_one_or_none()

        if trip_entity is None:
            return []

        # Return all entities for this insight (for done tracking)
        all_stmt = select(InsightEntity).where(
            InsightEntity.insight_id == insight_id,
        )
        all_result = await self.db.execute(all_stmt)
        return list(all_result.scalars().all())

    async def _check_all_entities_done(self, insight_id: UUID) -> bool:
        """Check if all primary/related entities have ``done_at`` set.

        Only considers entities with role in ('primary', 'related').
        """
        stmt = select(InsightEntity).where(
            and_(
                InsightEntity.insight_id == insight_id,
                InsightEntity.role.in_(["primary", "related"]),
            )
        )
        result = await self.db.execute(stmt)
        entities = list(result.scalars().all())

        if not entities:
            return True

        return all(entity.done_at is not None for entity in entities)

    # ------------------------------------------------------------------
    # Preference signal
    # ------------------------------------------------------------------

    async def _write_preference_signal_useful(
        self,
        insight_id: UUID,
        user_id: UUID,
    ) -> None:
        """Write a positive preference signal for adopt actions."""
        insight = await get_insight(self.db, insight_id)
        if insight is None:
            return

        try:
            from ..curation.models import PreferenceSignal
        except ImportError:
            logger.warning("Cannot import PreferenceSignal — signal not recorded")
            return

        signal = PreferenceSignal(
            user_id=insight.user_id,
            family_id=insight.family_id,
            signal_type="useful",
            source_type="insight",
            source_id=insight.id,
            source_context={
                "insight_type": insight.insight_type,
                "dedup_key": insight.dedup_key,
                "title": insight.title,
                "importance": insight.importance,
                "action": "adopt_to_trip",
            },
            user_reason=None,
            category_key=f"insight:{insight.insight_type}:{insight.dedup_key or 'none'}",
        )
        self.db.add(signal)

    # ------------------------------------------------------------------
    # Event publishing + domain bridge writeback
    # ------------------------------------------------------------------

    async def _publish_adopted_event(
        self,
        insight: Insight,
        trip_id: UUID,
    ) -> None:
        """Publish InsightAdoptedEvent and execute domain bridge writeback."""
        from .insight_domain_bridge import InsightDomainBridge

        entity_refs = [
            InsightAdoptedEntityRef(
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                role=e.role,
            )
            for e in (insight.entities or [])
        ]
        event = InsightAdoptedEvent(
            insight_id=insight.id,
            insight_type=insight.insight_type,
            user_id=insight.user_id,
            family_id=insight.family_id,
            trip_id=trip_id,
            entities=entity_refs,
        )
        logger.info(
            "InsightAdoptedEvent: insight=%s, trip=%s, user=%s, entities=%d",
            event.insight_id, trip_id, event.user_id, len(entity_refs),
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
            await bridge.handle_insight_adopted(event)
        except Exception:
            logger.warning(
                "Domain bridge writeback failed for adopted insight %s",
                insight.id,
                exc_info=True,
            )

    async def _publish_task_completed_event(
        self,
        insight: Insight,
        trip_id: UUID,
        completed_entity_ids: List[UUID],
        all_done: bool = False,
    ) -> None:
        """Publish TaskCompletedEvent and execute domain bridge writeback."""
        from .insight_domain_bridge import InsightDomainBridge

        event = TaskCompletedEvent(
            insight_id=insight.id,
            insight_type=insight.insight_type,
            user_id=insight.user_id,
            family_id=insight.family_id,
            trip_id=trip_id,
            completed_entity_ids=completed_entity_ids,
            all_done=all_done,
        )
        logger.info(
            "TaskCompletedEvent: insight=%s, trip=%s, completed=%s",
            event.insight_id, trip_id, event.completed_entity_ids,
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
            await bridge.handle_task_completed(event)
        except Exception:
            logger.warning(
                "Domain bridge writeback failed for task completed insight %s",
                insight.id,
                exc_info=True,
            )

