"""InsightDomainBridge — Event-driven writeback to domain services.

Listens to insight lifecycle events (adopted, task completed, dismissed)
and propagates changes to the owning domain services (favor, commitment,
relationship, EventAssociation).  All operations are best-effort with
error isolation per entity.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Event DTOs (immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InsightAdoptedEntityRef:
    """Reference to a single entity in an adopted insight."""
    entity_type: str
    entity_id: UUID
    role: str


@dataclass(frozen=True)
class InsightAdoptedEvent:
    """Emitted when a user adopts an insight (adds to trip)."""
    insight_id: UUID
    insight_type: str
    user_id: UUID
    family_id: UUID
    trip_id: Optional[UUID] = None
    entities: List[InsightAdoptedEntityRef] = field(default_factory=list)


@dataclass(frozen=True)
class TaskCompletedEvent:
    """Emitted when a trip task linked to an insight is completed."""
    insight_id: UUID
    insight_type: str
    user_id: UUID
    family_id: UUID
    trip_id: Optional[UUID] = None
    completed_entity_ids: List[UUID] = field(default_factory=list)
    all_done: bool = False


@dataclass(frozen=True)
class InsightDismissedEvent:
    """Emitted when an insight is dismissed."""
    insight_id: UUID
    insight_type: str
    user_id: UUID
    family_id: UUID
    feedback: str = ""
    permanent: bool = False
    entities: List[InsightAdoptedEntityRef] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Bridge service
# ---------------------------------------------------------------------------


class InsightDomainBridge:
    """Executes domain writeback on insight lifecycle events.

    Domain services are injected as constructor parameters for testability
    and to avoid circular imports.  If a service is not provided, the
    corresponding handler silently skips that domain.
    """

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
    # Adopted
    # ------------------------------------------------------------------

    async def handle_insight_adopted(self, event: InsightAdoptedEvent) -> None:
        """On adopt: update favor status + record interaction intent.

        Iterates ALL entities on the event:
        - favor source entity  -> mark_in_progress(action_type='adopt_to_trip')
        - person entity        -> record_interaction_intent(type='insight_adopted')
        """
        for e in event.entities:
            if e.entity_type == "favor" and e.role == "source":
                await self._mark_favor_in_progress(
                    e.entity_id,
                    action_type="adopt_to_trip",
                )
            elif e.entity_type == "person":
                await self._record_interaction_intent(
                    person_id=e.entity_id,
                    user_id=event.user_id,
                    interaction_type="insight_adopted",
                )

    async def _mark_favor_in_progress(
        self, favor_id: UUID, *, action_type: str
    ) -> None:
        """Best-effort: mark a FavorRecord as in_progress."""
        try:
            from ..relationship.models import FavorRecord as FRModel
            from sqlalchemy import select

            result = await self.db.execute(
                select(FRModel).where(FRModel.id == favor_id)
            )
            favor = result.scalar_one_or_none()
            if favor is None:
                return
            if favor.status in ("pending", "in_progress"):
                favor.status = "in_progress"
                favor.updated_at = utc_now()
                logger.info(
                    "Favor %s marked in_progress (action=%s)",
                    favor_id,
                    action_type,
                )
        except Exception:
            logger.warning(
                "Failed to mark favor %s in_progress",
                favor_id,
                exc_info=True,
            )

    async def _record_interaction_intent(
        self,
        person_id: UUID,
        user_id: UUID,
        interaction_type: str,
    ) -> None:
        """Best-effort: record an interaction intent on PersonProfile.

        If a temperature_service is injected, delegates to it for proper
        tracking.  Otherwise falls back to direct updated_at bump.
        """
        try:
            if self._temperature_service is not None:
                await self._temperature_service.record_interaction_intent(
                    person_id, interaction_type=interaction_type,
                )
                logger.info(
                    "Recorded interaction intent via temperature_service for person %s (type=%s)",
                    person_id, interaction_type,
                )
                return

            # Fallback: direct DB update
            from ..member.models import PersonProfile as PPModel
            from sqlalchemy import select

            result = await self.db.execute(
                select(PPModel).where(PPModel.id == person_id)
            )
            profile = result.scalar_one_or_none()
            if profile is None:
                return
            profile.updated_at = utc_now()
            logger.info(
                "Recorded interaction intent (direct) for person %s (type=%s)",
                person_id, interaction_type,
            )
        except Exception:
            logger.warning(
                "Failed to record interaction intent for person %s",
                person_id,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Task completed
    # ------------------------------------------------------------------

    async def handle_task_completed(self, event: TaskCompletedEvent) -> None:
        """On trip task completion: update favor + commitment + person.

        Only processes entities whose IDs are in ``completed_entity_ids``
        to avoid over-counting partial completions.
        """
        from .models import Insight, InsightEntity
        from sqlalchemy import select

        # Load all entities for this insight (source + person)
        stmt = (
            select(InsightEntity)
            .where(
                InsightEntity.insight_id == event.insight_id,
            )
        )
        result = await self.db.execute(stmt)
        all_entities = list(result.scalars())

        completed_set = set(event.completed_entity_ids)

        for entity in all_entities:
            if entity.role == "source" and entity.entity_id in completed_set:
                if entity.entity_type == "favor":
                    await self._mark_favor_reciprocated(entity.entity_id)
                elif entity.entity_type == "commitment":
                    await self._mark_commitment_followed_up(entity.entity_id)
            elif entity.entity_type == "person" and entity.entity_id in completed_set:
                await self._record_interaction(
                    person_id=entity.entity_id,
                    user_id=event.user_id,
                    interaction_type="insight_acted",
                )

    async def _mark_favor_reciprocated(self, favor_id: UUID) -> None:
        """Best-effort: mark a FavorRecord as settled/reciprocated."""
        try:
            from ..relationship.models import FavorRecord as FRModel
            from sqlalchemy import select

            result = await self.db.execute(
                select(FRModel).where(FRModel.id == favor_id)
            )
            favor = result.scalar_one_or_none()
            if favor is None:
                return
            favor.status = "settled"
            favor.updated_at = utc_now()
            logger.info(
                "Favor %s marked settled (task_completed)",
                favor_id,
            )
        except Exception:
            logger.warning(
                "Failed to mark favor %s reciprocated",
                favor_id,
                exc_info=True,
            )

    async def _mark_commitment_followed_up(
        self, commitment_id: UUID
    ) -> None:
        """Best-effort: increment follow-up count on commitment."""
        try:
            from ..memory.commitment_models import CommitmentItemRecord
            from sqlalchemy import select

            result = await self.db.execute(
                select(CommitmentItemRecord).where(
                    CommitmentItemRecord.id == commitment_id
                )
            )
            commitment = result.scalar_one_or_none()
            if commitment is None:
                return
            commitment.record_follow_up()
            logger.info(
                "Commitment %s followed up (count=%d)",
                commitment_id,
                commitment.follow_up_count,
            )
        except Exception:
            logger.warning(
                "Failed to follow up commitment %s",
                commitment_id,
                exc_info=True,
            )

    async def _record_interaction(
        self,
        person_id: UUID,
        user_id: UUID,
        interaction_type: str,
    ) -> None:
        """Best-effort: record a completed interaction on PersonProfile.

        Delegates to temperature_service.record_interaction() if available,
        which updates last_contact and recalculates relationship temperature.
        """
        try:
            if self._temperature_service is not None:
                await self._temperature_service.record_interaction(
                    person_id, interaction_type=interaction_type,
                )
                logger.info(
                    "Recorded interaction via temperature_service for person %s (type=%s)",
                    person_id, interaction_type,
                )
                return

            # Fallback: direct DB update
            from ..member.models import PersonProfile as PPModel
            from sqlalchemy import select

            result = await self.db.execute(
                select(PPModel).where(PPModel.id == person_id)
            )
            profile = result.scalar_one_or_none()
            if profile is None:
                return
            profile.updated_at = utc_now()
            logger.info(
                "Recorded interaction (direct) for person %s (type=%s)",
                person_id, interaction_type,
            )
        except Exception:
            logger.warning(
                "Failed to record interaction for person %s",
                person_id,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Dismissed
    # ------------------------------------------------------------------

    async def handle_insight_dismissed(
        self, event: InsightDismissedEvent
    ) -> None:
        """Cascade dismiss to EventAssociation (best-effort).

        Iterates event entities; for any event_association, dismiss the EA.
        Falls back to loading entities from the insight if none provided.
        """
        ea_entities = [
            e for e in event.entities
            if e.entity_type == "event_association"
        ]
        if ea_entities:
            for ea in ea_entities:
                await self._dismiss_ea(ea.entity_id)
        else:
            # Fallback: load entities from insight directly
            await self._cascade_dismiss_ea_from_insight(event.insight_id)

    async def _cascade_dismiss_ea_from_insight(
        self, insight_id: UUID
    ) -> None:
        """Find and dismiss EAs linked to an insight via entities."""
        from .models import InsightEntity
        from sqlalchemy import select

        stmt = (
            select(InsightEntity)
            .where(
                InsightEntity.insight_id == insight_id,
                InsightEntity.entity_type == "event_association",
            )
        )
        result = await self.db.execute(stmt)
        ea_entities = list(result.scalars())

        for ea_entity in ea_entities:
            await self._dismiss_ea(ea_entity.entity_id)

    async def _dismiss_ea(self, ea_id: UUID) -> None:
        """Best-effort: dismiss an EventAssociation."""
        try:
            if self._ea_dismiss_fn is not None:
                await self._ea_dismiss_fn(ea_id)
                return

            # Fallback: direct EA dismiss
            from ..curation.models import EventAssociation

            ea = await self.db.get(EventAssociation, ea_id)
            if ea and not ea.is_dismissed:
                ea.is_dismissed = True
            logger.info("Cascade dismissed EA %s from insight dismiss", ea_id)
        except Exception:
            logger.warning(
                "Failed to cascade dismiss EA %s",
                ea_id,
                exc_info=True,
            )
