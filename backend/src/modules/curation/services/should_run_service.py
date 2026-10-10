"""Lightweight should-run decision service for curation tasks."""

import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.utils.timezone import utc_now
from ...conversation.pending_action import ActionStatus, PendingAction
from ...date_manager.models import ImportantDate
from ...memory.models import ConversationMemory, MemoryStatus
from ...trip.models.trip_itinerary import TripItinerary
from ...trip.models.trip_plan import TripPlan
from ..models import CurationJob, CuratedEvent, EventAssociation
from .prompts import SYSTEM_HOLIDAY_FAMILY_ID

FORCE_REVIEW_HOURS = int(os.getenv("CURATION_FORCE_REVIEW_HOURS", "24"))

_FULL_PIPELINE_TRIGGERS = {
    "manual",
    "event_requested",
    "event",
    "event_created",
    "event_updated",
    "event_deleted",
}
_INCREMENTAL_TRIGGERS = {
    "trip_created",
    "trip_updated",
    "trip_cancelled",
    "trip_deleted",
    "itinerary_updated",
    "memory_extracted",
    "date_approaching",
}
_TRIP_TRIGGERS = {
    "trip_created",
    "trip_updated",
    "trip_cancelled",
    "trip_deleted",
    "itinerary_updated",
}


@dataclass
class ShouldRunDecision:
    """Decision returned by CurationShouldRunService."""

    should_run: bool
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_mode: Optional[str] = None


class CurationShouldRunService:
    """Decides whether a curation run should execute or skip.

    When an ImpactArbitrator is available, incremental triggers are first
    assessed for impact level.  SILENT triggers are skipped entirely,
    LOW triggers proceed with reduced priority (execution_mode set),
    and MEDIUM/HIGH triggers proceed at full priority.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        from .impact_arbitrator import ImpactArbitrator
        self._arbitrator = ImpactArbitrator()

    async def evaluate(
        self,
        family_id: UUID,
        date_range: Tuple[date, date],
        trigger_type: str,
        payload: Optional[dict] = None,
    ) -> ShouldRunDecision:
        payload = payload or {}
        last_completed = await self._get_last_completed_at(family_id)

        if self._has_force_signal(payload):
            return ShouldRunDecision(True, "forced_by_payload")

        if trigger_type in _FULL_PIPELINE_TRIGGERS:
            return ShouldRunDecision(True, "full_pipeline_trigger")

        if trigger_type in _INCREMENTAL_TRIGGERS:
            return await self._evaluate_incremental(
                family_id=family_id,
                trigger_type=trigger_type,
                payload=payload,
                last_completed=last_completed,
            )

        return await self._evaluate_scheduled(
            family_id=family_id,
            date_range=date_range,
            payload=payload,
            last_completed=last_completed,
        )

    async def _evaluate_incremental(
        self,
        family_id: UUID,
        trigger_type: str,
        payload: Dict[str, Any],
        last_completed: Optional[datetime],
    ) -> ShouldRunDecision:
        if not payload:
            return ShouldRunDecision(False, "incremental_missing_payload")

        # Impact assessment: skip SILENT, annotate LOW with execution_mode
        from .impact_arbitrator import ImpactLevel, TriggerContext
        try:
            ctx = TriggerContext(
                trigger_type=trigger_type,
                payload=payload,
                diff=payload.get("diff", {}),
            )
            assessment = self._arbitrator.assess(ctx)

            if assessment.level == ImpactLevel.SILENT:
                return ShouldRunDecision(
                    False,
                    "impact_silent",
                    metadata={"impact_reason": assessment.reason},
                    execution_mode=assessment.execution_mode.value,
                )

            # Attach execution_mode for LOW/MEDIUM/HIGH — callers can
            # use it to decide how aggressively to curate.
            exec_mode = assessment.execution_mode.value
        except Exception:
            exec_mode = None

        if last_completed is None:
            return ShouldRunDecision(
                True, "first_incremental_run", execution_mode=exec_mode,
            )

        if trigger_type in _TRIP_TRIGGERS:
            trip_id = self._extract_uuid(payload, ("plan_id", "trip_id"))
            if trip_id is None:
                # Let dispatcher decide whether to skip; no heavy full pipeline fallback.
                return ShouldRunDecision(
                    True, "incremental_trip_without_trip_id",
                    execution_mode=exec_mode,
                )

            if trigger_type == "itinerary_updated":
                itinerary_updated_at = await self._get_itinerary_updated_at(trip_id)
                if (
                    itinerary_updated_at is not None
                    and self._as_utc(itinerary_updated_at) <= self._as_utc(last_completed)
                ):
                    return ShouldRunDecision(
                        False,
                        "stale_incremental_itinerary_signal",
                        metadata={"trip_id": str(trip_id)},
                    )
                return ShouldRunDecision(
                    True,
                    "incremental_itinerary_changed",
                    metadata={"trip_id": str(trip_id)},
                    execution_mode=exec_mode,
                )

            trip_updated_at = await self._get_trip_updated_at(family_id, trip_id)
            if (
                trip_updated_at is not None
                and self._as_utc(trip_updated_at) <= self._as_utc(last_completed)
            ):
                return ShouldRunDecision(
                    False,
                    "stale_incremental_trip_signal",
                    metadata={"trip_id": str(trip_id)},
                )
            return ShouldRunDecision(
                True,
                "incremental_trip_changed",
                metadata={"trip_id": str(trip_id)},
                execution_mode=exec_mode,
            )

        if trigger_type == "memory_extracted":
            memory_id = self._extract_uuid(payload, ("memory_id",))
            if memory_id is None:
                return ShouldRunDecision(False, "incremental_missing_memory_id")

            memory_updated_at = await self._get_memory_updated_at(family_id, memory_id)
            if (
                memory_updated_at is not None
                and self._as_utc(memory_updated_at) <= self._as_utc(last_completed)
            ):
                return ShouldRunDecision(
                    False,
                    "stale_incremental_memory_signal",
                    metadata={"memory_id": str(memory_id)},
                )
            return ShouldRunDecision(
                True,
                "incremental_memory_changed",
                metadata={"memory_id": str(memory_id)},
                execution_mode=exec_mode,
            )

        if trigger_type == "date_approaching":
            return ShouldRunDecision(
                True, "incremental_date_signal", execution_mode=exec_mode,
            )

        return ShouldRunDecision(
            True, "incremental_signal", execution_mode=exec_mode,
        )

    async def _evaluate_scheduled(
        self,
        family_id: UUID,
        date_range: Tuple[date, date],
        payload: Dict[str, Any],
        last_completed: Optional[datetime],
    ) -> ShouldRunDecision:
        if last_completed is None:
            return ShouldRunDecision(True, "first_scheduled_run")

        source_watermarks = await self._get_source_watermarks(family_id)
        changed_sources = [
            source
            for source, watermark in source_watermarks.items()
            if watermark is not None
            and self._as_utc(watermark) > self._as_utc(last_completed)
        ]
        if changed_sources:
            return ShouldRunDecision(
                True,
                "source_watermark_changed",
                metadata={"changed_sources": changed_sources},
            )

        pending_associations = await self._count_pending_associations(family_id)
        pending_actions = await self._count_pending_actions(family_id)
        if pending_associations > 0 or pending_actions > 0:
            return ShouldRunDecision(
                True,
                "pending_follow_up",
                metadata={
                    "pending_associations": pending_associations,
                    "pending_actions": pending_actions,
                },
            )

        if self._has_severe_signal(payload):
            return ShouldRunDecision(True, "severe_external_signal")

        active_events = await self._count_active_events_in_window(family_id, date_range)
        elapsed = utc_now() - self._as_utc(last_completed)
        if elapsed >= timedelta(hours=FORCE_REVIEW_HOURS):
            return ShouldRunDecision(
                True,
                "force_review_due",
                metadata={
                    "elapsed_hours": round(elapsed.total_seconds() / 3600, 2),
                    "active_events": active_events,
                },
            )

        if active_events == 0:
            return ShouldRunDecision(
                False,
                "skip_no_active_events",
                metadata={
                    "elapsed_hours": round(elapsed.total_seconds() / 3600, 2),
                },
            )

        return ShouldRunDecision(
            False,
            "skip_no_signal",
            metadata={
                "active_events": active_events,
                "elapsed_hours": round(elapsed.total_seconds() / 3600, 2),
            },
        )

    async def _get_last_completed_at(self, family_id: UUID) -> Optional[datetime]:
        stmt = select(func.max(CurationJob.completed_at)).where(
            and_(
                CurationJob.family_id == family_id,
                CurationJob.status == "completed",
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_source_watermarks(self, family_id: UUID) -> Dict[str, Optional[datetime]]:
        trip_stmt = select(func.max(TripPlan.updated_at)).where(
            TripPlan.family_id == family_id
        )
        trip_watermark = (await self._session.execute(trip_stmt)).scalar_one_or_none()

        itinerary_stmt = (
            select(func.max(TripItinerary.updated_at))
            .select_from(TripItinerary)
            .join(TripPlan, TripPlan.trip_id == TripItinerary.trip_id)
            .where(TripPlan.family_id == family_id)
        )
        itinerary_watermark = (await self._session.execute(itinerary_stmt)).scalar_one_or_none()

        memory_stmt = select(func.max(ConversationMemory.updated_at)).where(
            and_(
                ConversationMemory.family_id == family_id,
                ConversationMemory.status == MemoryStatus.ACTIVE.value,
            )
        )
        memory_watermark = (await self._session.execute(memory_stmt)).scalar_one_or_none()

        date_family_ids = [family_id]
        system_holiday_family_id = self._coerce_uuid(SYSTEM_HOLIDAY_FAMILY_ID)
        if system_holiday_family_id and system_holiday_family_id != family_id:
            date_family_ids.append(system_holiday_family_id)

        date_stmt = select(func.max(ImportantDate.updated_at)).where(
            ImportantDate.family_id.in_(date_family_ids)
        )
        date_watermark = (await self._session.execute(date_stmt)).scalar_one_or_none()

        return {
            "trip": trip_watermark,
            "itinerary": itinerary_watermark,
            "memory": memory_watermark,
            "important_date": date_watermark,
        }

    async def _count_active_events_in_window(
        self,
        family_id: UUID,
        date_range: Tuple[date, date],
    ) -> int:
        start_date, end_date = date_range
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

        stmt = select(func.count()).select_from(CuratedEvent).where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.normalized_start <= end_dt,
                or_(
                    CuratedEvent.normalized_end.is_(None),
                    CuratedEvent.normalized_end >= start_dt,
                ),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def _count_pending_associations(self, family_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(EventAssociation)
            .join(
                CuratedEvent,
                CuratedEvent.id == EventAssociation.source_event_id,
            )
            .where(
                and_(
                    EventAssociation.family_id == family_id,
                    EventAssociation.is_confirmed.is_(False),
                    EventAssociation.is_dismissed.is_(False),
                    CuratedEvent.is_active.is_(True),
                )
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def _count_pending_actions(self, family_id: UUID) -> int:
        stmt = select(func.count()).select_from(PendingAction).where(
            and_(
                PendingAction.family_id == family_id,
                PendingAction.status == ActionStatus.PENDING.value,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def _get_trip_updated_at(
        self,
        family_id: UUID,
        trip_id: UUID,
    ) -> Optional[datetime]:
        stmt = select(TripPlan.updated_at).where(
            and_(
                TripPlan.family_id == family_id,
                TripPlan.trip_id == trip_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_itinerary_updated_at(self, trip_id: UUID) -> Optional[datetime]:
        stmt = select(func.max(TripItinerary.updated_at)).where(
            TripItinerary.trip_id == trip_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_memory_updated_at(
        self,
        family_id: UUID,
        memory_id: UUID,
    ) -> Optional[datetime]:
        stmt = select(ConversationMemory.updated_at).where(
            and_(
                ConversationMemory.family_id == family_id,
                ConversationMemory.id == memory_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _has_force_signal(payload: Dict[str, Any]) -> bool:
        return any(
            bool(payload.get(key))
            for key in (
                "force_run",
                "force_full",
                "manual_override",
            )
        )

    @staticmethod
    def _has_severe_signal(payload: Dict[str, Any]) -> bool:
        return any(
            bool(payload.get(key))
            for key in (
                "severe_weather",
                "has_severe_weather",
                "critical_alert",
            )
        )

    @staticmethod
    def _extract_uuid(payload: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[UUID]:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            try:
                return UUID(str(value))
            except (ValueError, TypeError):
                continue
        return None

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _coerce_uuid(value: Any) -> Optional[UUID]:
        try:
            return UUID(str(value))
        except (ValueError, TypeError):
            return None
