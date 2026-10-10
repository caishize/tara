"""InsightCascadeService — Trip cancellation cascade + Double Jeopardy protection.

Handles the lifecycle of insights when their parent trip is cancelled:
  - Phase 1: classify pending/active/acknowledged insights (three-way)
  - Phase 2: reactivate acted+adopted insights if obligation still pending
  - Cleanup: dismiss associated EventAssociations
"""

from datetime import timedelta
from typing import Optional, Set
from uuid import UUID, uuid4

from sqlalchemy import and_, select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .models import (
    Insight,
    InsightEntity,
    InsightStatus,
    InsightSource,
    SourceContext,
    SUPPRESSION_WINDOWS,
)

logger = get_logger(__name__)

# Insight types with social obligation semantics
_SOCIAL_OBLIGATION_TYPES = frozenset({"relationship", "favor", "memory"})

# Social obligation action types that should never auto-expire PAs
_SOCIAL_PA_TYPES = frozenset({"favor", "relationship"})

# Maximum reactivation depth before converting directly to PA
_MAX_REACTIVATION_DEPTH = 2

# Delay for rechecking skipped (locked) rows
_RECHECK_DELAY_SECONDS = 300


class InsightCascadeService:
    """Trip cancellation cascade + Double Jeopardy protection."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        favor_service=None,
        commitment_service=None,
        temperature_fn=None,
    ):
        self.db = db
        self._favor_service = favor_service
        self._commitment_service = commitment_service
        self._temperature_fn = temperature_fn

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def cascade_from_trip_cancel(self, trip_id: UUID) -> dict:
        """Two-phase cascade for a cancelled trip.

        Returns a summary dict with counts of each action taken.
        """
        now = utc_now()
        summary = {
            "preserved_as_action": 0,
            "preserved_as_note": 0,
            "dismissed": 0,
            "reactivated": 0,
            "converted_to_pa": 0,
            "ea_dismissed": 0,
            "skipped_locked": 0,
        }

        # Collect obligation IDs preserved in Phase 1 to avoid duplication
        preserved_obligation_ids: Set[UUID] = set()

        # ---- Phase 1: pending / active / acknowledged insights ----
        all_phase1_ids = await self._load_phase1_insight_ids(trip_id)
        phase1_insights = await self._load_phase1_insights(trip_id)
        locked_ids = {insight.id for insight in phase1_insights}
        skipped_ids = [sid for sid in all_phase1_ids if sid not in locked_ids]

        for insight in phase1_insights:
            classification = self._classify_on_cancel(insight)
            if classification == "preserve_as_action":
                await self._convert_to_pending_action(insight, trip_id)
                preserved_obligation_ids.update(self._get_obligation_ids(insight))
                insight.status = InsightStatus.ACTED.value
                insight.acted_at = now
                insight.feedback_source = "cascade_preserved"
                summary["preserved_as_action"] += 1
            elif classification == "preserve_as_note":
                await self._convert_to_secretary_note(insight)
                preserved_obligation_ids.update(self._get_obligation_ids(insight))
                insight.status = InsightStatus.DISMISSED.value
                insight.dismissed_at = now
                insight.feedback_source = "cascade_preserved"
                summary["preserved_as_note"] += 1
            else:
                insight.status = InsightStatus.DISMISSED.value
                insight.dismissed_at = now
                insight.feedback_source = "cascade_dismiss"
                summary["dismissed"] += 1

        # Schedule recheck for rows that were skipped (locked by user)
        if skipped_ids:
            summary["skipped_locked"] = len(skipped_ids)
            await self._schedule_recheck(trip_id, skipped_ids)

        # ---- Phase 2: acted + adopted insights (Double Jeopardy) ----
        phase2_insights = await self._load_phase2_insights(trip_id)

        for insight in phase2_insights:
            obligation_ids = self._get_obligation_ids(insight)
            # Skip obligations already preserved in Phase 1
            if obligation_ids & preserved_obligation_ids:
                continue

            if not await self._has_pending_obligation(insight):
                continue

            ctx = self._parse_source_context(insight)
            depth = ctx.reactivation_depth

            if depth >= _MAX_REACTIVATION_DEPTH:
                # Cycle detection: convert directly to PA
                await self._convert_to_pending_action(insight, trip_id)
                summary["converted_to_pa"] += 1
                continue

            # Create reactivated insight
            await self._create_reactivated_insight(insight, trip_id, depth)
            summary["reactivated"] += 1

        # ---- Cleanup: dismiss linked EventAssociations ----
        ea_count = await self._dismiss_trip_associations(trip_id)
        summary["ea_dismissed"] = ea_count

        await self.db.flush()

        logger.info(
            "Cascade from trip cancel: trip=%s, summary=%s",
            trip_id,
            summary,
        )
        return summary

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_on_cancel(self, insight: Insight) -> str:
        """Three-way classification for a cancelled-trip insight.

        Returns one of: 'preserve_as_action', 'preserve_as_note', 'dismiss'.
        """
        entities = insight.entities or []
        has_date = any(e.entity_type == "important_date" for e in entities)
        has_person = any(e.entity_type == "person" for e in entities)

        if has_date:
            return "preserve_as_action"

        if has_person and insight.insight_type in _SOCIAL_OBLIGATION_TYPES:
            return "preserve_as_action"

        if insight.importance >= 80:
            return "preserve_as_action"

        if (insight.source_context or {}).get("social_intent"):
            return "preserve_as_note"

        return "dismiss"

    # ------------------------------------------------------------------
    # Obligation checking
    # ------------------------------------------------------------------

    async def _has_pending_obligation(self, insight: Insight) -> bool:
        """Check if the underlying domain obligation is still unresolved.

        Inspects insight_entities with role='source' for non-person entities,
        and ALL person entities regardless of role, checking each domain
        model's status.
        """
        all_entities = insight.entities or []
        source_entities = [e for e in all_entities if e.role == "source"]
        person_entities = [
            e for e in all_entities if e.entity_type == "person"
        ]

        if not source_entities and not person_entities:
            ctx = self._parse_source_context(insight)
            return bool(ctx.health_event)

        # Check non-person source entities
        for entity in source_entities:
            if entity.entity_type == "person":
                continue
            if await self._check_entity_obligation(entity):
                return True

        # Check ALL person entities regardless of role
        checked_person_ids: Set[UUID] = set()
        for entity in person_entities:
            if entity.entity_id in checked_person_ids:
                continue
            checked_person_ids.add(entity.entity_id)
            if await self._check_relationship_cold(entity.entity_id):
                return True

        return False

    async def _check_entity_obligation(self, entity: InsightEntity) -> bool:
        """Check a single entity's obligation status."""
        try:
            if entity.entity_type == "favor":
                return await self._check_favor_pending(entity.entity_id)
            if entity.entity_type == "commitment":
                return await self._check_commitment_pending(entity.entity_id)
            if entity.entity_type == "person":
                return await self._check_relationship_cold(entity.entity_id)
            if entity.entity_type == "important_date":
                return await self._check_date_upcoming(entity.entity_id)
        except Exception:
            logger.warning(
                "Failed to check obligation for entity %s:%s",
                entity.entity_type,
                entity.entity_id,
                exc_info=True,
            )
        return False

    async def _check_favor_pending(self, favor_id: UUID) -> bool:
        """Check if FavorRecord is still pending or in progress."""
        from ..relationship.models import FavorRecord as FRModel

        result = await self.db.execute(
            select(FRModel.status).where(FRModel.id == favor_id)
        )
        status = result.scalar_one_or_none()
        return status in ("pending", "in_progress")

    async def _check_commitment_pending(self, commitment_id: UUID) -> bool:
        """Check if CommitmentItemRecord is not yet fulfilled."""
        from ..memory.commitment_models import CommitmentItemRecord

        result = await self.db.execute(
            select(CommitmentItemRecord.status).where(
                CommitmentItemRecord.id == commitment_id
            )
        )
        status = result.scalar_one_or_none()
        return status is not None and status != "fulfilled"

    async def _check_relationship_cold(self, person_id: UUID) -> bool:
        """Check if relationship temperature is cold."""
        if self._temperature_fn is not None:
            try:
                temp = await self._temperature_fn(person_id, self.db)
                return temp.status == "cold"
            except Exception:
                logger.debug(
                    "Temperature check failed for person %s", person_id
                )
        return False

    async def _check_date_upcoming(self, date_id: UUID) -> bool:
        """Check if the important date's next occurrence is in the future."""
        from ..date_manager.date_models import ImportantDate

        result = await self.db.execute(
            select(ImportantDate.solar_date).where(ImportantDate.id == date_id)
        )
        solar_date = result.scalar_one_or_none()
        if solar_date is None:
            return False

        today = utc_now().date()
        return solar_date >= today

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    async def _convert_to_pending_action(
        self, insight: Insight, trip_id: UUID
    ) -> None:
        """Convert an insight to a PendingAction.

        Social obligation types (favor, relationship) get no expiry.
        """
        from ..conversation.pending_action import PendingAction, ActionStatus

        now = utc_now()
        source_entity = self._find_source_entity(insight)

        # Social obligation PAs never expire
        is_social = insight.insight_type in _SOCIAL_PA_TYPES
        expires_at = (
            now + timedelta(days=365 * 10) if is_social
            else now + timedelta(days=30)
        )

        pa = PendingAction(
            user_id=insight.user_id,
            family_id=insight.family_id,
            action_type=self._map_to_pa_action_type(insight),
            payload={
                "insight_id": str(insight.id),
                "insight_type": insight.insight_type,
                "title": insight.title,
                "content": insight.content,
                "cancelled_trip_id": str(trip_id),
            },
            display_data={
                "title": insight.title,
                "content": insight.content,
                "source": "trip_cancel_cascade",
            },
            status=ActionStatus.PENDING.value,
            expires_at=expires_at,
        )
        # source_entity_id exists in DB (migration 120) but not on ORM;
        # set via __dict__ to avoid AttributeError on older ORM versions
        if source_entity is not None:
            pa.__dict__["source_entity_id"] = source_entity.entity_id

        self.db.add(pa)
        await self.db.flush()

        logger.info(
            "Converted insight %s to PendingAction %s (trip_cancel)",
            insight.id,
            pa.id,
        )

    async def _convert_to_secretary_note(self, insight: Insight) -> None:
        """Convert an insight to a low-priority secretary note."""
        from ..memory.secretary_note_model import SecretaryNote, NoteCategory

        note = SecretaryNote(
            user_id=insight.user_id,
            family_id=insight.family_id,
            category=NoteCategory.OBSERVATION.value,
            title=f"[来自取消行程] {insight.title}",
            content=insight.content,
            confidence=0.6,
            priority=3,
        )
        self.db.add(note)
        await self.db.flush()

        logger.info(
            "Converted insight %s to secretary note (trip_cancel)",
            insight.id,
        )

    # ------------------------------------------------------------------
    # Reactivation
    # ------------------------------------------------------------------

    async def _create_reactivated_insight(
        self,
        original: Insight,
        trip_id: UUID,
        current_depth: int,
    ) -> Insight:
        """Create a reactivated insight with increased urgency and depth."""
        now = utc_now()
        new_depth = current_depth + 1

        old_ctx = self._parse_source_context(original)
        new_ctx = SourceContext(
            **{
                **old_ctx.model_dump(),
                "reactivated_from": str(original.id),
                "reactivation_depth": new_depth,
            }
        )

        new_insight = Insight(
            family_id=original.family_id,
            user_id=original.user_id,
            insight_type=original.insight_type,
            title=original.title,
            content=original.content,
            suggested_action=original.suggested_action,
            action_options=original.action_options,
            importance=original.importance,
            urgency=min(100, original.urgency + 10),
            status=InsightStatus.ACTIVE.value,
            source=InsightSource.TRIP_EVENT.value,
            dedup_key=f"reactivated:{original.insight_type}:{original.id}:{trip_id}",
            source_context=new_ctx.model_dump(),
            created_at=now,
            activated_at=now,
        )
        self.db.add(new_insight)
        await self.db.flush()

        # Copy source entities
        for entity_spec in self._copy_source_entities(original):
            ie = InsightEntity(
                insight_id=new_insight.id,
                entity_type=entity_spec["entity_type"],
                entity_id=entity_spec["entity_id"],
                role=entity_spec["role"],
            )
            self.db.add(ie)

        await self.db.flush()

        logger.info(
            "Reactivated insight %s -> %s (depth=%d, trip=%s)",
            original.id,
            new_insight.id,
            new_depth,
            trip_id,
        )
        return new_insight

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_phase1_insight_ids(self, trip_id: UUID) -> list:
        """Load IDs of all pending/active/acknowledged insights for a trip.

        No FOR UPDATE — used to detect which rows were skipped by SKIP LOCKED.
        """
        stmt = (
            select(Insight.id)
            .join(InsightEntity, InsightEntity.insight_id == Insight.id)
            .where(
                InsightEntity.entity_type == "trip",
                InsightEntity.entity_id == trip_id,
                Insight.status.in_([
                    InsightStatus.PENDING.value,
                    InsightStatus.ACTIVE.value,
                    InsightStatus.ACKNOWLEDGED.value,
                ]),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars())

    async def _load_phase1_insights(self, trip_id: UUID) -> list:
        """Load pending/active/acknowledged insights linked to a trip.

        Uses FOR UPDATE SKIP LOCKED to avoid conflicting with user actions.
        """
        stmt = (
            select(Insight)
            .join(InsightEntity, InsightEntity.insight_id == Insight.id)
            .where(
                InsightEntity.entity_type == "trip",
                InsightEntity.entity_id == trip_id,
                Insight.status.in_([
                    InsightStatus.PENDING.value,
                    InsightStatus.ACTIVE.value,
                    InsightStatus.ACKNOWLEDGED.value,
                ]),
            )
            .with_for_update(skip_locked=True)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

    async def _load_phase2_insights(self, trip_id: UUID) -> list:
        """Load acted insights linked to a trip (for Double Jeopardy check)."""
        stmt = (
            select(Insight)
            .join(InsightEntity, InsightEntity.insight_id == Insight.id)
            .where(
                InsightEntity.entity_type == "trip",
                InsightEntity.entity_id == trip_id,
                Insight.status == InsightStatus.ACTED.value,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique())

    async def _dismiss_trip_associations(self, trip_id: UUID) -> int:
        """Cascade-dismiss EventAssociations linked to cancelled trip events."""
        from ..curation.models import CuratedEvent, EventAssociation

        ea_query = (
            select(EventAssociation)
            .join(
                CuratedEvent,
                EventAssociation.source_event_id == CuratedEvent.id,
            )
            .where(
                CuratedEvent.trip_id == trip_id,
                EventAssociation.is_dismissed.is_(False),
                EventAssociation.is_confirmed.is_(False),
            )
        )
        result = await self.db.execute(ea_query)
        eas = list(result.scalars())

        for ea in eas:
            ea.is_dismissed = True

        return len(eas)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_source_context(self, insight: Insight) -> SourceContext:
        """Parse source_context JSONB into a SourceContext model."""
        raw = insight.source_context
        if raw is None:
            return SourceContext()
        if isinstance(raw, dict):
            return SourceContext(**raw)
        return SourceContext()

    def _get_obligation_ids(self, insight: Insight) -> Set[UUID]:
        """Extract obligation entity IDs from insight entities with role='source'."""
        return {
            e.entity_id
            for e in (insight.entities or [])
            if e.role == "source"
        }

    def _copy_source_entities(self, insight: Insight) -> list:
        """Return source entity specs from an insight for copying."""
        return [
            {
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "role": e.role,
            }
            for e in (insight.entities or [])
            if e.role == "source"
        ]

    def _find_source_entity(self, insight: Insight) -> Optional[InsightEntity]:
        """Find the first source entity from an insight."""
        for e in (insight.entities or []):
            if e.role == "source":
                return e
        return None

    @staticmethod
    def _map_to_pa_action_type(insight: Insight) -> str:
        """Map insight type to PendingAction action_type."""
        mapping = {
            "favor": "suggest_gift",
            "relationship": "suggest_greeting",
            "memory": "suggest_meeting",
        }
        return mapping.get(insight.insight_type, "create_event")

    async def _schedule_recheck(
        self, trip_id: UUID, skipped_ids: list
    ) -> None:
        """Schedule a Celery task to recheck skipped (locked) insights.

        Best-effort: if Celery is unavailable, log and continue.
        """
        try:
            from ...tasks import get_celery_app

            app = get_celery_app()
            app.send_task(
                "secretary.recheck_cascade_skipped",
                args=[str(trip_id), [str(sid) for sid in skipped_ids]],
                countdown=_RECHECK_DELAY_SECONDS,
            )
        except Exception:
            logger.warning(
                "Failed to schedule recheck for skipped insights: trip=%s",
                trip_id,
                exc_info=True,
            )
