"""
Event Hygiene Service - Daily cleanup of stale curated events and associations.

Runs as a daily Celery task to:
1. Hard-delete inactive events past retention window
2. Hard-delete cancelled events past retention window
3. Hard-delete dismissed associations older than 7 days
4. Auto-mark past pending events as completed (> 1 day old)
5. Purge old CurationJob records (> 90 days)
6. Detect trip completeness gaps (missing return, missing accommodation)

Safety:
- User-created events are never auto-deleted
- Confirmed events are never deleted by hygiene
- All deletions respect configurable retention windows
- hygiene_enabled setting allows per-family opt-out
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now
from ..models import CuratedEvent, EventAssociation, CurationJob, HygieneRunLog, PreparationItem

logger = get_logger(__name__)

_SIGNIFICANT_EVENT_TYPES = frozenset({
    "medical", "birthday", "anniversary", "social", "travel",
    "business_trip", "appointment",
})

DISMISSED_ASSOCIATION_RETENTION_DAYS = 7
CURATION_JOB_RETENTION_DAYS = 90
AUTO_COMPLETE_GRACE_DAYS = 1
RESOLVED_ACTION_RETENTION_DAYS = 7
EXPIRED_ACTION_RETENTION_DAYS = 3


@dataclass(frozen=True)
class HygieneReport:
    """Immutable report of a hygiene run."""

    family_id: str
    inactive_deleted: int
    cancelled_deleted: int
    dismissed_deleted: int
    auto_completed: int
    jobs_purged: int
    pending_actions_purged: int = 0

    @property
    def total_actions(self) -> int:
        return (
            self.inactive_deleted
            + self.cancelled_deleted
            + self.dismissed_deleted
            + self.auto_completed
            + self.jobs_purged
            + self.pending_actions_purged
        )

    def to_dict(self) -> dict:
        return {
            "family_id": self.family_id,
            "inactive_deleted": self.inactive_deleted,
            "cancelled_deleted": self.cancelled_deleted,
            "dismissed_deleted": self.dismissed_deleted,
            "auto_completed": self.auto_completed,
            "jobs_purged": self.jobs_purged,
            "pending_actions_purged": self.pending_actions_purged,
            "total_actions": self.total_actions,
        }


class EventHygieneService:
    """Daily cleanup of stale curated events, associations, and jobs."""

    def __init__(self, session: AsyncSession, llm_provider=None):
        self.session = session
        self._llm_provider = llm_provider

    async def run_daily_cleanup(
        self,
        family_id: UUID,
        inactive_retention_days: int = 7,
        cancelled_retention_days: int = 30,
    ) -> HygieneReport:
        """Execute all hygiene operations for a family."""
        now = utc_now()

        inactive_deleted = await self._delete_inactive_events(
            family_id, now, inactive_retention_days
        )
        cancelled_deleted = await self._delete_cancelled_events(
            family_id, now, cancelled_retention_days
        )
        dismissed_deleted = await self._delete_dismissed_associations(
            family_id, now
        )
        auto_completed = await self._auto_complete_past_pending(
            family_id, now
        )
        jobs_purged = await self._purge_old_curation_jobs(
            family_id, now
        )
        pending_actions_purged = await self._purge_resolved_pending_actions(
            family_id, now
        )

        await self._recompute_priority_weights(family_id)

        report = HygieneReport(
            family_id=str(family_id),
            inactive_deleted=inactive_deleted,
            cancelled_deleted=cancelled_deleted,
            dismissed_deleted=dismissed_deleted,
            auto_completed=auto_completed,
            jobs_purged=jobs_purged,
            pending_actions_purged=pending_actions_purged,
        )

        completed_at = utc_now()
        run_log = HygieneRunLog(
            family_id=family_id,
            inactive_deleted=inactive_deleted,
            cancelled_deleted=cancelled_deleted,
            dismissed_deleted=dismissed_deleted,
            auto_completed=auto_completed,
            jobs_purged=jobs_purged,
            total_actions=report.total_actions,
            status="completed",
            started_at=now,
            completed_at=completed_at,
        )
        self.session.add(run_log)

        await self.session.commit()

        if report.total_actions > 0:
            logger.info(
                "Hygiene completed for family %s: %d total actions (%s)",
                family_id,
                report.total_actions,
                report.to_dict(),
            )

        return report

    async def _delete_inactive_events(
        self, family_id, now, retention_days
    ) -> int:
        cutoff = now - timedelta(days=retention_days)

        find_stmt = select(CuratedEvent.id).where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(False),
                CuratedEvent.updated_at <= cutoff,
            )
        )
        result = await self.session.execute(find_stmt)
        candidate_ids = result.scalars().all()

        if not candidate_ids:
            return 0

        events_stmt = select(CuratedEvent).where(
            CuratedEvent.id.in_(candidate_ids)
        )
        events_result = await self.session.execute(events_stmt)
        events = events_result.scalars().all()

        ids_to_delete = [
            e.id for e in events
            if "user_created" not in (e.source_types or [])
        ]

        if not ids_to_delete:
            return 0

        del_stmt = delete(CuratedEvent).where(
            CuratedEvent.id.in_(ids_to_delete)
        )
        result = await self.session.execute(del_stmt)
        return result.rowcount

    async def _delete_cancelled_events(
        self, family_id, now, retention_days
    ) -> int:
        cutoff = now - timedelta(days=retention_days)

        find_stmt = select(CuratedEvent).where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.status == "cancelled",
                CuratedEvent.updated_at <= cutoff,
            )
        )
        result = await self.session.execute(find_stmt)
        events = result.scalars().all()

        ids_to_delete = [
            e.id for e in events
            if "user_created" not in (e.source_types or [])
        ]

        if not ids_to_delete:
            return 0

        events_to_delete = [e for e in events if e.id in set(ids_to_delete)]
        await self._extract_cancellation_memories(events_to_delete)

        del_stmt = delete(CuratedEvent).where(
            CuratedEvent.id.in_(ids_to_delete)
        )
        result = await self.session.execute(del_stmt)
        return result.rowcount

    async def _extract_cancellation_memories(
        self, events: list
    ) -> int:
        """Persist a PLAN memory for each significant cancelled event before deletion.

        Filters to events with priority in (normal, high, critical) and
        event_type in _SIGNIFICANT_EVENT_TYPES, then writes a
        ConversationMemory row so the cancellation is not lost from
        the user's memory context.

        Returns the count of memories successfully created.
        """
        from ...memory.models import ConversationMemory, MemoryType

        qualifying = [
            e for e in events
            if (e.priority in ("normal", "high", "critical"))
            and (e.event_type in _SIGNIFICANT_EVENT_TYPES)
        ]

        created = 0
        for event in qualifying:
            if event.user_id is None:
                continue

            try:
                if event.normalized_start is not None:
                    date_text = event.normalized_start.strftime("%Y-%m-%d")
                else:
                    date_text = (
                        event.updated_at.strftime("%Y-%m-%d")
                        if event.updated_at is not None
                        else "未知日期"
                    )

                location_part = (
                    f"地点：{event.location}" if event.location else "地点：未知"
                )
                content = (
                    f"原定于{date_text}的「{event.title}」因故取消"
                    f"（{location_part}）"
                )

                memory = ConversationMemory(
                    user_id=event.user_id,
                    family_id=event.family_id,
                    memory_type=MemoryType.PLAN.value,
                    content=content,
                    summary=content,
                )
                self.session.add(memory)
                created += 1
            except Exception:
                logger.warning(
                    "Failed to create cancellation memory for event %s",
                    event.id,
                    exc_info=True,
                )

        return created

    async def _delete_dismissed_associations(
        self, family_id, now
    ) -> int:
        cutoff = now - timedelta(days=DISMISSED_ASSOCIATION_RETENTION_DAYS)

        del_stmt = delete(EventAssociation).where(
            and_(
                EventAssociation.family_id == family_id,
                EventAssociation.is_dismissed.is_(True),
                EventAssociation.created_at <= cutoff,
            )
        )
        result = await self.session.execute(del_stmt)
        return result.rowcount

    async def _auto_complete_past_pending(
        self, family_id, now
    ) -> int:
        cutoff = now - timedelta(days=AUTO_COMPLETE_GRACE_DAYS)

        from sqlalchemy import func as sa_func

        effective_end = sa_func.coalesce(
            CuratedEvent.normalized_end, CuratedEvent.normalized_start
        )

        upd_stmt = (
            update(CuratedEvent)
            .where(
                and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.status == "pending",
                    CuratedEvent.is_active.is_(True),
                    effective_end <= cutoff,
                )
            )
            .values(status="completed")
        )
        result = await self.session.execute(upd_stmt)
        return result.rowcount

    async def _purge_old_curation_jobs(
        self, family_id, now
    ) -> int:
        cutoff = now - timedelta(days=CURATION_JOB_RETENTION_DAYS)

        del_stmt = delete(CurationJob).where(
            and_(
                CurationJob.family_id == family_id,
                CurationJob.created_at <= cutoff,
            )
        )
        result = await self.session.execute(del_stmt)
        return result.rowcount

    async def _purge_resolved_pending_actions(
        self, family_id, now
    ) -> int:
        from ...conversation.pending_action import (
            PendingAction,
            ActionStatus,
        )
        from sqlalchemy import or_ as sa_or

        resolved_cutoff = now - timedelta(days=RESOLVED_ACTION_RETENTION_DAYS)
        expired_cutoff = now - timedelta(days=EXPIRED_ACTION_RETENTION_DAYS)

        del_stmt = delete(PendingAction).where(
            and_(
                PendingAction.family_id == family_id,
                sa_or(
                    and_(
                        PendingAction.status.in_([
                            ActionStatus.EXECUTED.value,
                            ActionStatus.REJECTED.value,
                            ActionStatus.FAILED.value,
                        ]),
                        PendingAction.created_at <= resolved_cutoff,
                    ),
                    and_(
                        PendingAction.status == ActionStatus.EXPIRED.value,
                        PendingAction.expires_at <= expired_cutoff,
                    ),
                ),
            )
        )
        result = await self.session.execute(del_stmt)
        return result.rowcount

    async def _recompute_priority_weights(self, family_id: UUID) -> None:
        """Recompute priority weights based on confirm/dismiss feedback stats.

        Rules:
        - association_type -> weight dimension mapping:
          - location/stale_contact -> stakeholder
          - date_proximity/approaching_date/temporal -> urgency
          - social_intent/memory -> severity
        - dimension with dismiss_ratio > 70% -> weight -= 0.03 (min 0.10)
        - dimension with confirm_ratio > 80% -> weight += 0.02 (max 0.40)
        - Normalize all weights to sum = 1.0
        """
        try:
            from ....core.cache import redis_client
            from .family_settings import (
                get_priority_weights, update_priority_weights,
            )

            client = redis_client.client
            if client is None:
                return

            key = f"curation:feedback_stats:{family_id}"
            stats = await client.hgetall(key)
            if not stats:
                return

            TYPE_TO_DIMENSION = {
                "location": "stakeholder",
                "stale_contact": "stakeholder",
                "person": "stakeholder",
                "date_proximity": "urgency",
                "approaching_date": "urgency",
                "temporal": "urgency",
                "social_intent": "severity",
                "memory": "severity",
            }

            weights = await get_priority_weights(family_id)
            adjusted = dict(weights)  # don't mutate original

            for atype, dimension in TYPE_TO_DIMENSION.items():
                confirm_key = f"{atype}:confirm_count"
                dismiss_key = f"{atype}:dismiss_count"
                confirms = int(stats.get(confirm_key, 0))
                dismisses = int(stats.get(dismiss_key, 0))
                total = confirms + dismisses
                if total < 5:
                    continue

                dismiss_ratio = dismisses / total
                confirm_ratio = confirms / total

                if dismiss_ratio > 0.70:
                    adjusted[dimension] = max(0.10, adjusted[dimension] - 0.03)
                elif confirm_ratio > 0.80:
                    adjusted[dimension] = min(0.40, adjusted[dimension] + 0.02)

            total_w = sum(adjusted.values())
            if total_w > 0:
                adjusted = {k: v / total_w for k, v in adjusted.items()}

            await update_priority_weights(family_id, adjusted)
        except Exception:
            logger.debug("Failed to recompute priority weights", exc_info=True)

    async def detect_trip_gaps(self, family_id: UUID) -> List[Dict]:
        """Detect trip completeness gaps.

        Checks:
        1. no_return: Has departure/travel event but no return event
        2. no_accommodation: Multi-day trip without accommodation mention

        When an LLM provider is available, delegates to TripCompletenessService
        for semantic detection.  Falls back to keyword logic if LLM is
        unavailable or returns no result.

        Returns list of gaps with gap_type, trip_id, event_id, title,
        urgency, and suggestion.
        """
        from ...trip.models.trip_plan import TripPlan

        if self._llm_provider is not None:
            llm_gaps = await self._detect_gaps_via_llm(family_id)
            if llm_gaps is not None:
                return llm_gaps

        now = utc_now()

        # Query upcoming/in-progress trips for this family
        stmt = (
            select(TripPlan)
            .where(
                and_(
                    TripPlan.family_id == family_id,
                    TripPlan.status.in_(["planning", "confirmed", "in_progress"]),
                    TripPlan.end_date >= now.date(),
                )
            )
            .order_by(TripPlan.start_date)
        )
        result = await self.session.execute(stmt)
        trips = list(result.scalars().all())

        if not trips:
            return []

        gaps: List[Dict] = []

        for trip in trips:
            days_until = (trip.start_date - now.date()).days
            urgency = "high" if days_until < 3 else "medium"

            # Get curated events linked to this trip
            events_stmt = (
                select(CuratedEvent)
                .where(
                    and_(
                        CuratedEvent.trip_id == trip.trip_id,
                        CuratedEvent.family_id == family_id,
                        CuratedEvent.is_active.is_(True),
                        CuratedEvent.status != "cancelled",
                    )
                )
                .order_by(CuratedEvent.normalized_start)
            )
            events_result = await self.session.execute(events_stmt)
            trip_events = list(events_result.scalars().all())

            if not trip_events:
                continue

            # Check 1: no_return - departure without return
            has_departure = False
            has_return = False
            departure_event = None

            for ev in trip_events:
                title_lower = (ev.title or "").lower()
                event_type = ev.event_type or ""
                location_lower = (ev.location or "").lower()

                # Detect departure markers
                if any(kw in title_lower for kw in ["出发", "去程", "departure"]):
                    has_departure = True
                    if departure_event is None:
                        departure_event = ev
                elif event_type in ("travel", "business_trip") and not has_departure:
                    has_departure = True
                    if departure_event is None:
                        departure_event = ev

                # Detect return markers
                if any(kw in title_lower for kw in ["返程", "回程", "return"]):
                    has_return = True
                elif any(kw in location_lower for kw in ["返程", "回程"]):
                    has_return = True

            if has_departure and not has_return:
                dest = trip.destination or "目的地"
                suggestion = f"您的{dest}行程缺少返程安排，建议添加返程交通"
                gap = {
                    "gap_type": "no_return",
                    "trip_id": str(trip.trip_id),
                    "event_id": str(departure_event.id) if departure_event else None,
                    "title": trip.trip_name or dest,
                    "urgency": urgency,
                    "suggestion": suggestion,
                }
                gaps.append(gap)

                # Create a PreparationItem for this gap
                if departure_event:
                    await self._create_gap_prep_item(
                        departure_event.id, suggestion,
                    )

                # High urgency gaps go to BriefingAccumulator
                if urgency == "high":
                    await self._push_gap_to_briefing(family_id, gap)

            # Check 2: no_accommodation - multi-day trip without accommodation
            duration = trip.duration_days
            if duration > 1:
                has_accommodation = False
                for ev in trip_events:
                    title_lower = (ev.title or "").lower()
                    location_lower = (ev.location or "").lower()
                    combined = title_lower + " " + location_lower

                    if any(kw in combined for kw in [
                        "酒店", "住宿", "hotel", "民宿", "公寓",
                        "入住", "check-in", "checkin", "旅馆",
                    ]):
                        has_accommodation = True
                        break

                if not has_accommodation:
                    first_event = trip_events[0]
                    dest = trip.destination or "目的地"
                    suggestion = (
                        f"您的{dest}行程共{duration}天，"
                        f"但未安排住宿，建议预订酒店或民宿"
                    )
                    gap = {
                        "gap_type": "no_accommodation",
                        "trip_id": str(trip.trip_id),
                        "event_id": str(first_event.id),
                        "title": trip.trip_name or dest,
                        "urgency": urgency,
                        "suggestion": suggestion,
                    }
                    gaps.append(gap)

                    await self._create_gap_prep_item(
                        first_event.id, suggestion,
                    )

                    # High urgency gaps go to BriefingAccumulator
                    if urgency == "high":
                        await self._push_gap_to_briefing(family_id, gap)

        if gaps:
            logger.info(
                "Detected %d trip gaps for family %s",
                len(gaps), family_id,
            )

        return gaps

    async def _detect_gaps_via_llm(self, family_id: UUID) -> Optional[List[Dict]]:
        """Run LLM-based completeness detection across all active trips.

        Returns a list of gap dicts (same shape as keyword logic) on success,
        or None if the LLM path fails so the caller can fall back.
        """
        from ...trip.models.trip_plan import TripPlan
        from .trip_completeness_service import TripCompletenessService

        now = utc_now()
        stmt = (
            select(TripPlan)
            .where(
                and_(
                    TripPlan.family_id == family_id,
                    TripPlan.status.in_(["planning", "confirmed", "in_progress"]),
                    TripPlan.end_date >= now.date(),
                )
            )
            .order_by(TripPlan.start_date)
        )
        result = await self.session.execute(stmt)
        trips = list(result.scalars().all())

        if not trips:
            return []

        svc = TripCompletenessService(self.session, self._llm_provider)
        all_gaps: List[Dict] = []

        for trip in trips:
            try:
                completeness = await svc.check_completeness(trip.trip_id, family_id)
            except Exception:
                logger.warning(
                    "LLM completeness check failed for trip %s, using keyword fallback",
                    trip.trip_id, exc_info=True,
                )
                return None

            if completeness is None:
                return None

            days_until = (trip.start_date - now.date()).days
            urgency = "high" if days_until < 3 else "medium"

            for gap in completeness.gaps:
                gap_type = gap.get("gap_type", "")
                suggestion = gap.get("suggestion", "")
                dest = trip.destination or "目的地"
                gap_dict = {
                    "gap_type": gap_type,
                    "trip_id": str(trip.trip_id),
                    "event_id": None,
                    "title": trip.trip_name or dest,
                    "urgency": gap.get("urgency", urgency),
                    "suggestion": suggestion,
                }
                all_gaps.append(gap_dict)

                if gap.get("urgency") == "high" or urgency == "high":
                    await self._push_gap_to_briefing(family_id, gap_dict)

        if all_gaps:
            logger.info(
                "LLM detected %d trip gaps for family %s",
                len(all_gaps), family_id,
            )

        return all_gaps

    async def _push_gap_to_briefing(
        self, family_id: UUID, gap: Dict,
    ) -> None:
        """Push a high-urgency trip gap to BriefingAccumulator for daily briefing."""
        try:
            from ...briefing.services.accumulator import BriefingAccumulator
            acc = BriefingAccumulator()
            await acc.on_proactive_trigger(
                family_id=family_id,
                trigger_type="trip_gap_%s" % gap["gap_type"],
                trigger_data={
                    "title": gap.get("title", ""),
                    "description": gap.get("suggestion", ""),
                    "trip_id": gap.get("trip_id", ""),
                    "gap_type": gap["gap_type"],
                },
                priority="high",
            )
        except Exception:
            logger.warning(
                "Failed to push trip gap to briefing accumulator for family %s",
                family_id,
                exc_info=True,
            )

    async def _create_gap_prep_item(
        self,
        event_id: UUID,
        suggestion: str,
    ) -> None:
        """Create a PreparationItem for a detected trip gap if not already present."""
        # Check if a similar prep item already exists
        existing_stmt = (
            select(PreparationItem)
            .where(
                and_(
                    PreparationItem.event_id == event_id,
                    PreparationItem.source == "hygiene_auto",
                    PreparationItem.text == suggestion,
                )
            )
            .limit(1)
        )
        result = await self.session.execute(existing_stmt)
        if result.scalar_one_or_none() is not None:
            return

        prep = PreparationItem(
            event_id=event_id,
            text=suggestion,
            source="hygiene_auto",
            done=False,
        )
        self.session.add(prep)
