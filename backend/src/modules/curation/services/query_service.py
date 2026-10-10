"""Read-path query methods for the curation service.

Contains get_curated_timeline, get_curated_graph, and related
helper methods (_to_timeline_event, _build_graph_from_trip_plan).
"""
from copy import copy
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Dict, Set
from uuid import UUID

from sqlalchemy import select, and_, or_, func

from ....config.logging import get_logger
from ....core.utils.timezone import (
    local_date_range_to_utc,
    local_today,
    get_user_timezone,
)
from ..models import CuratedEvent, EventAssociation, CurationJob
from ..schemas import (
    CuratedTimelineEvent,
    CuratedTimelineResponse,
    CuratedGraphResponse,
    AssociationItem,
    TimelineItem,
    AssociationPriority,
    AssociationType,
    TargetType,
)
from .conflict_detection import detect_conflicts
from ...trip.models.trip_plan import TripPlan
from ...member.models import Member
from .prompts import DEFAULT_TIMELINE_LIMIT, DEFAULT_TIMELINE_OFFSET

logger = get_logger(__name__)


class CurationQueryMixin:
    """Mixin providing read-path query methods for SecretaryCurationService."""

    async def get_curated_timeline(
        self,
        family_id: UUID,
        start_date: date,
        end_date: date,
        limit: int = DEFAULT_TIMELINE_LIMIT,
        offset: int = DEFAULT_TIMELINE_OFFSET,
        tier: Optional[str] = None,
    ) -> CuratedTimelineResponse:
        """获取AI整理后的时光轴数据。"""
        start_utc, end_utc = local_date_range_to_utc(start_date, end_date)

        conditions = [
            CuratedEvent.family_id == family_id,
            CuratedEvent.is_active.is_(True),
            CuratedEvent.status != "cancelled",
            CuratedEvent.normalized_start >= start_utc,
            CuratedEvent.normalized_start <= end_utc,
        ]
        if tier:
            conditions.append(CuratedEvent.visibility_tier == tier)
        base_conditions = and_(*conditions)

        count_stmt = select(func.count()).select_from(CuratedEvent).where(base_conditions)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(CuratedEvent)
            .where(base_conditions)
            .order_by(CuratedEvent.normalized_start)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        db_events = result.scalars().all()

        job_stmt = (
            select(CurationJob)
            .where(
                and_(
                    CurationJob.family_id == family_id,
                    CurationJob.status == "completed",
                )
            )
            .order_by(CurationJob.completed_at.desc())
            .limit(1)
        )
        job_result = await self.session.execute(job_stmt)
        last_job = job_result.scalar_one_or_none()

        for db_event in db_events:
            try:
                context = await self.context_enricher.enrich_event(db_event, family_id)
                if db_event.enrichments is None:
                    db_event.enrichments = {}
                db_event.enrichments["context"] = context.dict()
            except Exception as e:
                logger.warning(f"Failed to enrich event {db_event.id}: {e}")

        try:
            await self.session.commit()
        except Exception as e:
            logger.warning(f"Failed to commit enrichments: {e}")
            await self.session.rollback()

        for db_event in db_events:
            await self.session.refresh(db_event)

        events = []
        unconfirmed_count = 0
        for db_event in db_events:
            event = self._to_timeline_event(db_event)
            unconfirmed_count += sum(1 for ti in event.timeline_items if not ti.confirmed)
            events.append(event)

        has_more = (offset + len(events)) < total

        return CuratedTimelineResponse(
            events=events,
            last_curated_at=last_job.completed_at if last_job else None,
            has_unconfirmed=unconfirmed_count > 0,
            unconfirmed_count=unconfirmed_count,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    async def get_curated_graph(
        self,
        family_id: UUID,
        event_id: Optional[str] = None,
    ) -> CuratedGraphResponse:
        """获取AI整理后的关联图谱。"""
        if event_id:
            event_uuid = self._parse_uuid(event_id)
            if event_uuid is None:
                return CuratedGraphResponse(
                    core_event=None,
                    associations=[],
                    last_curated_at=None,
                )

            event_stmt = select(CuratedEvent).where(
                and_(
                    CuratedEvent.id == event_uuid,
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.status != "cancelled",
                )
            )
            id_result = await self.session.execute(event_stmt)
            core_by_id = id_result.scalar_one_or_none()

            if not core_by_id:
                from sqlalchemy import case as sa_case

                trip_id_stmt = (
                    select(CuratedEvent)
                    .where(
                        and_(
                            CuratedEvent.trip_id == event_uuid,
                            CuratedEvent.family_id == family_id,
                            CuratedEvent.is_active.is_(True),
                            CuratedEvent.status != "cancelled",
                        )
                    )
                    .order_by(
                        sa_case(
                            (CuratedEvent.event_type.in_(
                                ["business_trip", "travel"]
                            ), 0),
                            else_=1,
                        ),
                        CuratedEvent.normalized_start,
                    )
                    .limit(1)
                )
                trip_id_result = await self.session.execute(trip_id_stmt)
                core_by_trip = trip_id_result.scalar_one_or_none()
                if core_by_trip:
                    event_stmt = select(CuratedEvent).where(
                        CuratedEvent.id == core_by_trip.id
                    )
                else:
                    tp_stmt = select(TripPlan).where(
                        TripPlan.trip_id == event_uuid
                    )
                    tp_result = await self.session.execute(tp_stmt)
                    trip_plan = tp_result.scalar_one_or_none()
                    if trip_plan:
                        return self._build_graph_from_trip_plan(trip_plan)
        else:
            today_start_utc = datetime.combine(
                local_today(), datetime.min.time()
            ).replace(tzinfo=timezone.utc)

            trip_event_stmt = (
                select(CuratedEvent)
                .where(
                    and_(
                        CuratedEvent.family_id == family_id,
                        CuratedEvent.is_active.is_(True),
                        CuratedEvent.status != "cancelled",
                        CuratedEvent.normalized_start >= today_start_utc,
                        CuratedEvent.trip_id.isnot(None),
                        CuratedEvent.event_type.in_(["business_trip", "travel"]),
                    )
                )
                .order_by(CuratedEvent.normalized_start)
                .limit(1)
            )
            trip_event_result = await self.session.execute(trip_event_stmt)
            trip_event = trip_event_result.scalar_one_or_none()

            if trip_event is None:
                legacy_trip_stmt = (
                    select(CuratedEvent)
                    .where(
                        and_(
                            CuratedEvent.family_id == family_id,
                            CuratedEvent.is_active.is_(True),
                            CuratedEvent.status != "cancelled",
                            CuratedEvent.normalized_start >= today_start_utc,
                            CuratedEvent.event_type.in_(["business_trip", "travel"]),
                        )
                    )
                    .order_by(CuratedEvent.normalized_start)
                    .limit(1)
                )
                legacy_result = await self.session.execute(legacy_trip_stmt)
                trip_event = legacy_result.scalar_one_or_none()

            if trip_event:
                event_stmt = select(CuratedEvent).where(CuratedEvent.id == trip_event.id)
            else:
                event_stmt = (
                    select(CuratedEvent)
                    .where(
                        and_(
                            CuratedEvent.family_id == family_id,
                            CuratedEvent.is_active.is_(True),
                            CuratedEvent.status != "cancelled",
                            CuratedEvent.normalized_start >= today_start_utc,
                        )
                    )
                    .order_by(CuratedEvent.normalized_start)
                    .limit(1)
                )

        event_result = await self.session.execute(event_stmt)
        core_event_db = event_result.scalar_one_or_none()

        if not core_event_db:
            return CuratedGraphResponse(
                core_event=None,
                associations=[],
                last_curated_at=None,
            )

        # Get associations for this event (+ child events for trips)
        assoc_conditions = [
            and_(
                EventAssociation.source_event_id == core_event_db.id,
                EventAssociation.is_dismissed == False,
                EventAssociation.is_confirmed == False,
            )
        ]
        if core_event_db.trip_id and core_event_db.event_type in (
            "business_trip", "travel",
        ):
            child_ids_stmt = select(CuratedEvent.id).where(
                and_(
                    CuratedEvent.trip_id == core_event_db.trip_id,
                    CuratedEvent.id != core_event_db.id,
                    CuratedEvent.is_active.is_(True),
                )
            )
            child_result = await self.session.execute(child_ids_stmt)
            child_ids = [row[0] for row in child_result]
            if child_ids:
                assoc_conditions.append(
                    and_(
                        EventAssociation.source_event_id.in_(child_ids),
                        EventAssociation.is_dismissed == False,
                        EventAssociation.is_confirmed == False,
                    )
                )
        assoc_stmt = select(EventAssociation).where(or_(*assoc_conditions))
        assoc_result = await self.session.execute(assoc_stmt)
        db_associations = assoc_result.scalars().all()

        # Get other events from the same trip
        trip_related_events: List[CuratedEvent] = []
        if core_event_db.trip_id:
            trip_events_stmt = (
                select(CuratedEvent)
                .where(
                    and_(
                        CuratedEvent.trip_id == core_event_db.trip_id,
                        CuratedEvent.id != core_event_db.id,
                        CuratedEvent.is_active.is_(True),
                        CuratedEvent.status != "cancelled",
                    )
                )
                .order_by(CuratedEvent.normalized_start)
            )
            trip_events_result = await self.session.execute(trip_events_stmt)
            all_trip_events = [core_event_db] + list(trip_events_result.scalars().all())
            try:
                from .trip_grouping import group_events_into_trips

                user_tz = get_user_timezone()
                sub_groups = group_events_into_trips(all_trip_events, user_tz)
                selected = next(
                    (sg for sg in sub_groups
                     if any(e.id == core_event_db.id for e in sg.events)),
                    None,
                )
                if selected:
                    trip_related_events = [
                        e for e in selected.events if e.id != core_event_db.id
                    ]
                else:
                    trip_related_events = [
                        e for e in all_trip_events if e.id != core_event_db.id
                    ]
            except Exception:
                trip_related_events = [
                    e for e in all_trip_events if e.id != core_event_db.id
                ]

        # Enrich core event with context
        core_event_id = core_event_db.id
        try:
            context = await self.context_enricher.enrich_event(core_event_db, family_id)
            if core_event_db.enrichments is None:
                core_event_db.enrichments = {}
            core_event_db.enrichments["context"] = context.dict()
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            logger.warning(f"Failed to enrich core event {core_event_id}: {e}")

        await self.session.refresh(core_event_db)
        for ev in trip_related_events:
            await self.session.refresh(ev)
        for assoc in db_associations:
            await self.session.refresh(assoc)

        core_event = self._to_timeline_event(core_event_db)
        if (
            core_event_db.trip_name
            and core_event.title.startswith("Day ")
            and " \u00b7 " in core_event.title
        ):
            core_event = core_event.model_copy(
                update={"title": core_event_db.trip_name}
            )

        # Batch-fetch member names for person associations
        person_target_ids = []
        for db_assoc in db_associations:
            if db_assoc.target_type == "person":
                try:
                    person_target_ids.append(UUID(db_assoc.target_id))
                except (ValueError, AttributeError):
                    pass

        member_names_map: Dict[str, str] = {}
        if person_target_ids:
            try:
                member_stmt = select(Member.id, Member.name).where(
                    Member.id.in_(person_target_ids)
                )
                member_result = await self.session.execute(member_stmt)
                member_names_map = {
                    str(row[0]): row[1] for row in member_result.all()
                }
            except Exception:
                logger.warning("Failed to batch-fetch member names", exc_info=True)

        associations = []
        for db_assoc in db_associations:
            member_name = member_names_map.get(db_assoc.target_id) if db_assoc.target_type == "person" else None

            associations.append(AssociationItem(
                id=str(db_assoc.id),
                title=db_assoc.title,
                target_id=db_assoc.target_id,
                target_type=TargetType(db_assoc.target_type),
                association_type=AssociationType(db_assoc.association_type),
                reason=db_assoc.reason,
                priority=AssociationPriority(db_assoc.priority),
                confidence=db_assoc.confidence,
                is_dismissed=db_assoc.is_dismissed,
                is_confirmed=db_assoc.is_confirmed,
                related_member_id=db_assoc.target_id if db_assoc.target_type == "person" else None,
                related_member_name=member_name,
            ))

        # Dedup associations with identical titles
        deduped_associations: List[AssociationItem] = []
        seen_titles: Set[str] = set()
        for assoc in associations:
            if assoc.title in seen_titles:
                continue
            seen_titles.add(assoc.title)
            deduped_associations.append(assoc)
        associations = deduped_associations

        # Expand trip_related_events with same-location adjacent events
        if core_event_db.location:
            norm_loc = self._normalize_destination(core_event_db.location)
            if norm_loc:
                existing_ids = {e.id for e in trip_related_events} | {core_event_db.id}
                current_starts = [
                    e.normalized_start for e in [core_event_db] + trip_related_events
                    if e.normalized_start
                ]
                current_ends = [
                    (e.normalized_end or e.normalized_start)
                    for e in [core_event_db] + trip_related_events
                    if e.normalized_start
                ]
                if current_starts and current_ends:
                    trip_window_start = min(current_starts) - timedelta(days=2)
                    trip_window_end = max(current_ends) + timedelta(days=2)
                else:
                    trip_window_start = None
                    trip_window_end = None

                loc_events_stmt = (
                    select(CuratedEvent)
                    .where(and_(
                        CuratedEvent.family_id == family_id,
                        CuratedEvent.is_active.is_(True),
                        CuratedEvent.status != "cancelled",
                        CuratedEvent.id.notin_(existing_ids),
                        CuratedEvent.location.isnot(None),
                    ))
                )
                loc_result = await self.session.execute(loc_events_stmt)
                for ev in loc_result.scalars():
                    if self._normalize_destination(ev.location or "") != norm_loc:
                        continue
                    if trip_window_start and trip_window_end and ev.normalized_start:
                        ev_end = ev.normalized_end or ev.normalized_start
                        if ev.normalized_start > trip_window_end or ev_end < trip_window_start:
                            continue
                    trip_related_events.append(ev)

        # Conflict detection
        user_id = core_event_db.user_id
        conflict_event = core_event_db
        trip_event_ids: Set[UUID] = set()

        if core_event_db.trip_id or (core_event_db.title or "").startswith("Day "):
            all_trip_events_list = [core_event_db] + trip_related_events
            starts = [e.normalized_start for e in all_trip_events_list if e.normalized_start]
            ends = [
                (e.normalized_end or e.normalized_start)
                for e in all_trip_events_list if e.normalized_start
            ]
            if starts and ends:
                conflict_event = copy(core_event_db)
                conflict_event.normalized_start = min(starts)
                conflict_event.normalized_end = max(ends)
                title = conflict_event.title or ""
                if title.startswith("Day ") and " \u00b7 " in title:
                    conflict_event.title = title.split(" \u00b7 ", 1)[1]

            trip_event_ids = {e.id for e in trip_related_events}

        conflicts = await detect_conflicts(
            self.session, family_id, conflict_event,
            user_id=user_id,
            exclude_event_ids=trip_event_ids,
            read_only=True,
        )

        if conflicts:
            await self._ensure_pending_actions(conflicts, family_id, user_id, conflict_event)

        job_stmt = (
            select(CurationJob.completed_at)
            .where(
                and_(
                    CurationJob.family_id == family_id,
                    CurationJob.status == "completed",
                )
            )
            .order_by(CurationJob.completed_at.desc())
            .limit(1)
        )
        job_result = await self.session.execute(job_stmt)
        last_curated_at = job_result.scalar_one_or_none()

        return CuratedGraphResponse(
            core_event=core_event,
            associations=associations,
            conflicts=conflicts,
            last_curated_at=last_curated_at,
        )

    # --- Helper Methods (used by query path) ---

    def _to_timeline_event(self, db_event: CuratedEvent) -> CuratedTimelineEvent:
        """Convert a CuratedEvent DB model to a CuratedTimelineEvent schema."""
        timeline_items = self._convert_timeline_items(db_event.timeline_items)
        return CuratedTimelineEvent(
            id=str(db_event.id),
            title=db_event.title,
            event_type=db_event.event_type,
            start_time=db_event.normalized_start,
            end_time=db_event.normalized_end,
            location=db_event.location,
            notes=db_event.notes,
            priority=db_event.priority,
            timeline_items=timeline_items,
            source_types=db_event.source_types or [],
            merged_count=db_event.merged_count,
            dedup_reason=db_event.dedup_reason,
            confidence=db_event.confidence,
            enrichments=db_event.enrichments,
            original_event_ids=db_event.original_event_ids or [],
            trip_id=str(db_event.trip_id) if db_event.trip_id else None,
            trip_name=db_event.trip_name,
            trip_day_label=db_event.trip_day_label,
            visibility_tier=db_event.visibility_tier or "standard",
        )

    def _build_graph_from_trip_plan(
        self, trip_plan: TripPlan
    ) -> CuratedGraphResponse:
        """Build a synthetic CuratedGraphResponse from a TripPlan."""
        title = (trip_plan.trip_name or "").strip() or trip_plan.destination
        event_type = (
            "business_trip"
            if trip_plan.trip_type in ("business_trip", "conference", "client_visit")
            else "travel"
        )
        start_dt = datetime.combine(
            trip_plan.start_date, datetime.min.time()
        ).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(
            trip_plan.end_date, datetime.min.time()
        ).replace(tzinfo=timezone.utc)

        core_event = CuratedTimelineEvent(
            id=str(trip_plan.trip_id),
            title=title,
            event_type=event_type,
            start_time=start_dt,
            end_time=end_dt,
            location=trip_plan.destination,
            trip_id=str(trip_plan.trip_id),
            trip_name=title,
        )
        return CuratedGraphResponse(
            core_event=core_event,
            associations=[],
            conflicts=[],
        )

    def _convert_timeline_items(self, items: Optional[list]) -> List[TimelineItem]:
        """Convert raw timeline item dicts to TimelineItem objects."""
        if not items:
            return []
        return [
            TimelineItem(
                time=item.get("time", ""),
                item=item.get("item", ""),
                confirmed=item.get("confirmed", True),
                note=item.get("note"),
            )
            for item in items
        ]
