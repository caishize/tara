"""
EventGraphService — event relationship visualization.

Provides event graph functionality for visualizing relationships between
trips, events, people, and other entities.

All data is sourced from curated_events (the single source of truth).

Extracted from secretary/services/event_graph_service.py.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID
from datetime import date
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.utils.timezone import local_today
from ...relationship.models import FavorRecord
from ...trip.services.trip_status import compute_trip_status
from ...curation.models import CuratedEvent, EventAssociation
from ..graph_schemas import (
    EventGraphResponse,
    GraphNode,
    GraphEdge,
    TripSummary,
)
from ._graph_helpers import (
    determine_layer,
    actions_for_node,
    calc_preparation_progress,
    get_event_icon,
)


class EventGraphService:
    """Event graph service — relationship visualization."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_upcoming_trips(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
        limit: int = 5
    ) -> List[TripSummary]:
        """Get upcoming trips from curated_events with 3-phase trip grouping."""
        from ....core.utils.timezone import local_today, local_date_range_to_utc
        from ...curation.services.trip_grouping import group_events_into_trips
        from ._event_converter import get_user_timezone as _get_user_tz

        user_tz = await _get_user_tz(self.db, user_id)
        today = local_today(user_tz)
        today_start_utc, _ = local_date_range_to_utc(today, today, user_tz)

        conditions = [
            CuratedEvent.event_type.in_(["travel", "business_trip"]),
            CuratedEvent.is_active.is_(True),
            CuratedEvent.status != "cancelled",
            CuratedEvent.normalized_end >= today_start_utc,
            CuratedEvent.trip_id.isnot(None),
        ]

        if family_id:
            conditions.append(CuratedEvent.family_id == family_id)
        else:
            conditions.append(CuratedEvent.user_id == user_id)

        query = (
            select(CuratedEvent)
            .where(and_(*conditions))
            .order_by(CuratedEvent.normalized_start.asc())
        )

        result = await self.db.execute(query)
        all_events = list(result.scalars().all())

        sub_groups = group_events_into_trips(all_events, user_tz)

        # Batch-load authoritative dates from TripPlan
        all_trip_ids_for_lookup: Set[UUID] = set()
        for sg in sub_groups:
            for e in sg.events:
                if e.trip_id:
                    all_trip_ids_for_lookup.add(e.trip_id)

        trip_dates: Dict[UUID, Tuple[date, date]] = {}
        if all_trip_ids_for_lookup:
            from ...trip.models.trip_plan import TripPlan
            tp_result = await self.db.execute(
                select(TripPlan.trip_id, TripPlan.start_date, TripPlan.end_date)
                .where(TripPlan.trip_id.in_(all_trip_ids_for_lookup))
            )
            for row in tp_result:
                trip_dates[row.trip_id] = (row.start_date, row.end_date)

        summaries = []
        for sg in sub_groups:
            if len(summaries) >= limit:
                break

            events = sg.events
            if not events:
                continue

            tp_starts = []
            tp_ends = []
            for e in events:
                if e.trip_id and e.trip_id in trip_dates:
                    s, en = trip_dates[e.trip_id]
                    tp_starts.append(s)
                    tp_ends.append(en)

            if tp_starts:
                trip_start = min(tp_starts)
                trip_end = max(tp_ends)
            else:
                starts = [
                    e.normalized_start.astimezone(user_tz)
                    for e in events if e.normalized_start
                ]
                ends = [
                    e.normalized_end.astimezone(user_tz)
                    for e in events if e.normalized_end
                ]
                trip_start = min(starts).date() if starts else today
                trip_end = max(ends).date() if ends else trip_start

            representative = events[0]
            title = representative.trip_name or representative.title
            if title and title.startswith("Day ") and " · " in title:
                title = title.split(" · ", 1)[1]
            if not title or len(title) <= 2:
                title = representative.location or representative.city or title or "未命名行程"

            base_status = "confirmed" if any(e.status == "confirmed" for e in events) else (representative.status or "pending")
            status = compute_trip_status(base_status, trip_start, trip_end, today=today)
            is_current = (status == "in_progress")

            all_trip_ids = sorted(
                {str(tid) for tid in sg.trip_ids if tid}
            )

            trip_id_counts: Dict[str, int] = {}
            for e in events:
                if e.trip_id:
                    tid_str = str(e.trip_id)
                    trip_id_counts[tid_str] = trip_id_counts.get(tid_str, 0) + 1

            if trip_id_counts:
                primary_trip_id = max(trip_id_counts, key=trip_id_counts.get)
            else:
                primary_trip_id = str(representative.id)

            summaries.append(TripSummary(
                id=primary_trip_id,
                title=title,
                start_date=trip_start,
                end_date=trip_end,
                location=representative.location,
                priority=representative.priority or "normal",
                status=status,
                event_count=len(events),
                is_current=is_current,
                trip_ids=all_trip_ids,
            ))

        return summaries

    async def get_event_graph(
        self,
        trip_id: UUID,
        user_id: UUID,
        family_id: Optional[UUID] = None,
        trip_ids: Optional[List[UUID]] = None,
    ) -> EventGraphResponse:
        """Get trip event graph from curated_events."""
        trip_event = await self._get_trip(trip_id, user_id, family_id)
        if not trip_event:
            raise ValueError("Trip not found")

        events = await self._get_trip_events_for_curated(
            trip_event, extra_trip_ids=trip_ids,
        )

        trip_associations = await self._get_associations_for_events(
            event_ids=[e.id for e in events]
        )

        nodes, edges = self._build_graph(trip_event, events, trip_associations)

        event_items = []
        for event in events:
            event_items.append({
                "id": str(event.id),
                "title": event.title,
                "start_time": event.normalized_start.isoformat() if event.normalized_start else None,
                "end_time": event.normalized_end.isoformat() if event.normalized_end else None,
                "event_type": event.event_type or "other",
                "status": event.status,
                "priority": event.priority,
                "location": event.location,
                "preparation_progress": calc_preparation_progress(event),
            })

        from ._event_converter import get_user_timezone as _get_user_tz
        from ...trip.models.trip_plan import TripPlan as _TP
        user_tz = await _get_user_tz(self.db, user_id)

        start_date = None
        end_date = None
        if trip_event.trip_id:
            tp_result = await self.db.execute(
                select(_TP.start_date, _TP.end_date)
                .where(_TP.trip_id == trip_event.trip_id)
            )
            tp_row = tp_result.one_or_none()
            if tp_row:
                start_date = tp_row.start_date
                end_date = tp_row.end_date

        if not start_date:
            if trip_event.normalized_start:
                start_date = trip_event.normalized_start.astimezone(user_tz).date()
            else:
                start_date = local_today(user_tz)
        if not end_date:
            if trip_event.normalized_end:
                end_date = trip_event.normalized_end.astimezone(user_tz).date()
            else:
                end_date = start_date
        today = local_today(user_tz)
        effective_status = compute_trip_status(trip_event.status or "pending", start_date, end_date, today=today)

        return EventGraphResponse(
            trip=TripSummary(
                id=str(trip_event.id),
                title=trip_event.title,
                start_date=start_date,
                end_date=end_date,
                location=trip_event.location,
                priority=trip_event.priority or "normal",
                status=effective_status,
                event_count=len(events),
                is_current=(effective_status == "in_progress"),
            ),
            nodes=nodes,
            edges=edges,
            events=event_items,
        )

    # ==================== Event-Centered Graph ====================

    async def get_event_centered_graph(
        self,
        event_id: UUID,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> EventGraphResponse:
        """Get event-centered association graph."""
        event = await self.db.get(CuratedEvent, event_id)
        if not event:
            raise ValueError("Event not found")

        associations = await self._get_associations_for_events([event_id])
        favor_associations = await self._get_favor_associations(event)
        history_associations = await self._get_historical_associations(event)

        all_associations = associations + favor_associations + history_associations
        nodes, edges = self._build_event_centered_graph(event, all_associations)

        return EventGraphResponse(
            trip=None,
            nodes=nodes,
            edges=edges,
            events=[{
                "id": str(event.id),
                "title": event.title,
                "start_time": event.normalized_start.isoformat() if event.normalized_start else None,
                "end_time": event.normalized_end.isoformat() if event.normalized_end else None,
                "event_type": event.event_type or "other",
                "status": event.status,
                "priority": event.priority,
                "location": event.location,
                "preparation_progress": calc_preparation_progress(event),
            }],
        )

    # ==================== Event Context ====================

    async def get_event_context(
        self,
        event_id: UUID,
        family_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[dict]:
        """Get enriched event context (associations + memories).

        Delegates to kanban module's EventDetailService which owns
        the event detail logic.
        """
        from .event_detail_service import EventDetailService

        service = EventDetailService(self.db)
        result = await service.get_event_detail(
            event_id=event_id,
            family_id=family_id,
            user_id=user_id,
        )
        if result is None:
            return None
        return result.model_dump()

    # ==================== Internal helpers ====================

    async def _get_trip(
        self,
        trip_id: UUID,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> Optional[CuratedEvent]:
        """Get trip detail from CuratedEvent."""
        conditions = [CuratedEvent.id == trip_id]
        if family_id:
            conditions.append(CuratedEvent.family_id == family_id)
        else:
            conditions.append(CuratedEvent.user_id == user_id)
        query = select(CuratedEvent).where(and_(*conditions))
        result = await self.db.execute(query)
        event = result.scalar_one_or_none()
        if event:
            return event

        # Fallback: try by CuratedEvent.trip_id (legacy)
        conditions = [
            CuratedEvent.trip_id == trip_id,
            CuratedEvent.event_type.in_(["travel", "business_trip"]),
            CuratedEvent.is_active.is_(True),
        ]
        if family_id:
            conditions.append(CuratedEvent.family_id == family_id)
        else:
            conditions.append(CuratedEvent.user_id == user_id)
        query = select(CuratedEvent).where(and_(*conditions)).limit(1)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_trip_events_for_curated(
        self,
        trip_event: CuratedEvent,
        extra_trip_ids: Optional[List[UUID]] = None,
    ) -> List[CuratedEvent]:
        """Get all events associated with a trip."""
        events: List[CuratedEvent] = []

        all_trip_ids: List[UUID] = []
        if trip_event.trip_id:
            all_trip_ids.append(trip_event.trip_id)
        if extra_trip_ids:
            for tid in extra_trip_ids:
                if tid not in all_trip_ids:
                    all_trip_ids.append(tid)

        if all_trip_ids:
            query = (
                select(CuratedEvent)
                .where(
                    and_(
                        CuratedEvent.trip_id.in_(all_trip_ids),
                        CuratedEvent.status != "cancelled",
                        CuratedEvent.is_active.is_(True),
                    )
                )
                .order_by(CuratedEvent.normalized_start.asc())
            )
            result = await self.db.execute(query)
            events = list(result.scalars().all())

        if not events and trip_event.normalized_start and trip_event.normalized_end:
            conditions = [
                CuratedEvent.family_id == trip_event.family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
                CuratedEvent.normalized_start >= trip_event.normalized_start,
                CuratedEvent.normalized_start <= trip_event.normalized_end,
            ]
            if trip_event.city:
                conditions.append(
                    or_(
                        CuratedEvent.trip_id.isnot(None),
                        CuratedEvent.city == trip_event.city,
                        CuratedEvent.city.is_(None),
                    )
                )
            query = (
                select(CuratedEvent)
                .where(and_(*conditions))
                .order_by(CuratedEvent.normalized_start.asc())
            )
            result = await self.db.execute(query)
            events = list(result.scalars().all())

        if not any(e.id == trip_event.id for e in events):
            events.insert(0, trip_event)

        return events

    async def _get_associations_for_events(
        self,
        event_ids: List[UUID]
    ) -> List[EventAssociation]:
        if not event_ids:
            return []

        query = (
            select(EventAssociation)
            .where(
                and_(
                    EventAssociation.source_event_id.in_(event_ids),
                    EventAssociation.is_dismissed == False
                )
            )
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    def _build_graph(
        self,
        trip: CuratedEvent,
        events: List[CuratedEvent],
        associations: List[EventAssociation]
    ) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """Build trip-centered 4-layer graph."""
        nodes = []
        edges = []

        start_date = trip.normalized_start.date() if trip.normalized_start else local_today()
        end_date = trip.normalized_end.date() if trip.normalized_end else start_date
        duration_days = (end_date - start_date).days + 1

        center_node = GraphNode(
            id=str(trip.id),
            type="trip",
            label=trip.title,
            icon="✈️",
            layer="core_trips",
            data={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "location": trip.location,
                "duration_days": duration_days,
                "preparation_progress": calc_preparation_progress(trip),
            }
        )
        nodes.append(center_node)

        layer_categories = {
            "core_trips": {"label": "🎯 核心行程", "icon": "✈️", "items": []},
            "must_do": {"label": "🔴 必须处理", "icon": "⚠️", "items": []},
            "convenient": {"label": "🟡 顺便可做", "icon": "💡", "items": []},
            "background": {"label": "🟢 背景信息", "icon": "📖", "items": []},
        }

        seen_assoc_keys: Set[Tuple[str, str]] = set()
        for assoc in associations:
            dedup_key = (assoc.title, assoc.target_type)
            if dedup_key in seen_assoc_keys:
                continue
            seen_assoc_keys.add(dedup_key)

            layer = determine_layer(assoc.priority, assoc.target_type, assoc.association_type)
            if layer in layer_categories:
                layer_categories[layer]["items"].append(("assoc", assoc, layer))

        seen_event_titles: Set[Tuple[str, str]] = set()
        for event in events:
            dedup_key = (event.title, event.event_type or "")
            if dedup_key in seen_event_titles:
                continue
            seen_event_titles.add(dedup_key)

            if event.event_type in ("travel", "business_trip") and event.id != trip.id:
                layer_categories["core_trips"]["items"].append(("event", event, "core_trips"))
            elif event.event_type in ("task", "reminder", "meeting", "appointment"):
                layer_categories["must_do"]["items"].append(("event", event, "must_do"))

        for layer_level, cat_data in layer_categories.items():
            if not cat_data["items"]:
                continue

            cat_node_id = f"cat_{layer_level}"
            cat_node = GraphNode(
                id=cat_node_id,
                type="category",
                label=cat_data["label"],
                icon=cat_data["icon"],
                layer=layer_level,
            )
            nodes.append(cat_node)

            edges.append(GraphEdge(
                source=str(trip.id),
                target=cat_node_id,
                type="has_category"
            ))

            for item_type, item, item_layer in cat_data["items"]:
                if item_type == "assoc":
                    child_id = str(item.id)
                    child_node = GraphNode(
                        id=child_id,
                        type=item.target_type,
                        label=item.title,
                        status="active" if not item.is_confirmed else "confirmed",
                        layer=item_layer,
                        action_required=(item_layer in ["must_do"]),
                        available_actions=actions_for_node(
                            item.target_type, item_layer, item.is_confirmed
                        ),
                        data={
                            "reason": item.reason,
                            "priority": item.priority,
                            "confidence": item.confidence,
                            "target_id": item.target_id,
                        }
                    )
                else:
                    child_id = str(item.id)
                    child_node = GraphNode(
                        id=child_id,
                        type=item.event_type or "event",
                        label=item.title,
                        status=item.status,
                        layer=item_layer,
                        action_required=(item_layer in ["must_do"]),
                        available_actions=actions_for_node(
                            item.event_type or "event", item_layer, False
                        ),
                        data={
                            "start_time": item.normalized_start.isoformat() if item.normalized_start else None,
                            "location": item.location,
                            "preparation_progress": calc_preparation_progress(item),
                        }
                    )

                nodes.append(child_node)
                edges.append(GraphEdge(
                    source=cat_node_id,
                    target=child_id,
                    type="contains"
                ))

        return nodes, edges

    async def _get_favor_associations(
        self,
        event: CuratedEvent,
    ) -> List[EventAssociation]:
        """Get favor associations for an event."""
        person_assocs = await self._get_associations_for_events([event.id])
        person_target_ids = [
            a.target_id for a in person_assocs
            if a.target_type == "person"
        ]

        if not person_target_ids:
            return []

        favor_stmt = select(FavorRecord).where(
            and_(
                FavorRecord.family_id == event.family_id,
                or_(
                    FavorRecord.contact_name.in_(person_target_ids),
                    FavorRecord.contact_id.in_(person_target_ids),
                ),
            )
        )
        result = await self.db.execute(favor_stmt)
        favors = list(result.scalars().all())

        associations = []
        for favor in favors:
            assoc = EventAssociation(
                family_id=event.family_id,
                source_event_id=event.id,
                target_id=str(favor.id),
                target_type="gift",
                association_type="favor",
                title=f"人情记录: {favor.contact_name}",
                reason=f"{favor.direction} {favor.gift_type or '礼物'}"
                       f" (¥{favor.amount or 0})",
                priority="convenient",
                confidence=0.9,
            )
            associations.append(assoc)

        return associations

    async def _get_historical_associations(
        self,
        event: CuratedEvent,
    ) -> List[EventAssociation]:
        """Get historical associations for an event."""
        associations = []

        if not event.location:
            return associations

        history_stmt = (
            select(CuratedEvent)
            .where(
                and_(
                    CuratedEvent.family_id == event.family_id,
                    CuratedEvent.location == event.location,
                    CuratedEvent.id != event.id,
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.status != "cancelled",
                    CuratedEvent.normalized_start < event.normalized_start,
                )
            )
            .order_by(CuratedEvent.normalized_start.desc())
            .limit(5)
        )
        result = await self.db.execute(history_stmt)
        past_events = list(result.scalars().all())

        for past in past_events:
            past_date = past.normalized_start.strftime("%Y-%m-%d") if past.normalized_start else "未知"
            assoc = EventAssociation(
                family_id=event.family_id,
                source_event_id=event.id,
                target_id=str(past.id),
                target_type="date",
                association_type="history",
                title=f"历史记录: {past.title}",
                reason=f"上次在{event.location}是 {past_date}: {past.title}",
                priority="optional",
                confidence=0.7,
            )
            associations.append(assoc)

        return associations

    def _build_event_centered_graph(
        self,
        event: CuratedEvent,
        associations: List[EventAssociation],
    ) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """Build event-centered graph."""
        nodes = []
        edges = []

        center_node = GraphNode(
            id=str(event.id),
            type=event.event_type or "event",
            label=event.title,
            icon=get_event_icon(event.event_type),
            data={
                "start_time": event.normalized_start.isoformat() if event.normalized_start else None,
                "end_time": event.normalized_end.isoformat() if event.normalized_end else None,
                "location": event.location,
                "status": event.status,
            },
        )
        nodes.append(center_node)

        categories = {
            "person": {"label": "相关人物", "icon": "👤", "items": []},
            "task": {"label": "待办事项", "icon": "📋", "items": []},
            "memory": {"label": "人情关联", "icon": "🎁", "items": []},
            "place": {"label": "地点关联", "icon": "📍", "items": []},
            "date": {"label": "历史关联", "icon": "📅", "items": []},
            "gift": {"label": "人情往来", "icon": "🧧", "items": []},
        }

        for assoc in associations:
            target_type = assoc.target_type
            if target_type in categories:
                categories[target_type]["items"].append(assoc)

        for cat_type, cat_data in categories.items():
            if not cat_data["items"]:
                continue

            cat_node_id = f"cat_{cat_type}"
            cat_node = GraphNode(
                id=cat_node_id,
                type="category",
                label=cat_data["label"],
                icon=cat_data["icon"],
            )
            nodes.append(cat_node)

            edges.append(GraphEdge(
                source=str(event.id),
                target=cat_node_id,
                type="has_category",
            ))

            for item in cat_data["items"]:
                child_id = str(item.id)
                child_node = GraphNode(
                    id=child_id,
                    type=item.target_type,
                    label=item.title,
                    status="active" if not item.is_confirmed else "confirmed",
                    data={
                        "reason": item.reason,
                        "priority": item.priority,
                        "confidence": item.confidence,
                        "target_id": item.target_id,
                    },
                )
                nodes.append(child_node)
                edges.append(GraphEdge(
                    source=cat_node_id,
                    target=child_id,
                    type="contains",
                ))

        return nodes, edges
