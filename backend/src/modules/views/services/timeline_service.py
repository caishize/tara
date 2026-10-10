"""
TimelineService — curated timeline with directional pagination.

Provides curated timeline data with support for:
- Past (history) and Future tabs
- Cursor-based pagination
- Day grouping with smart labels
- TripPlan fallback for trips not yet curated
- DayTheme consumed from OrchestratedDay (single source of truth)
"""
from __future__ import annotations

import asyncio
import json
from typing import Dict, List, Optional, Literal, Tuple
from uuid import UUID
from datetime import date, datetime, timedelta
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ....config.logging import get_logger
from ....core.utils.timezone import (
    utc_now,
    to_local,
    to_local_date,
    local_today,
    local_date_range_to_utc,
    get_user_timezone,
    DEFAULT_TIMEZONE,
)

from ...insight.models import Insight, InsightStatus
from ...curation.models import CuratedEvent
from ...curation.services.orchestrator import DayTheme
from ..kanban_schemas import (
    TimelineAlertItem,
    TimelineInsightItem,
    TimelineResponse,
    TimelineDayGroup,
    TimelineEventItem,
)

logger = get_logger(__name__)

# GapWarning cache TTL (30 minutes)
_GAP_CACHE_TTL = 1800

# GapWarning type -> icon mapping (mirrors briefing_service._GAP_ICONS)
_TIMELINE_GAP_ICONS = {
    "no_buffer": "\U0001f4a1",
    "impossible_commute": "\U0001f4a1",
    "back_to_back": "\U0001f4a1",
    "overloaded": "\U0001f525",
    "meal_conflict": "\U0001f37d\ufe0f",
}

# Event types that indicate family/relationship-oriented activities
_FAMILY_EVENT_TYPES = frozenset({
    "birthday", "anniversary", "social", "meeting", "favor",
})

# Event types that indicate special occasions worth highlighting
_SPECIAL_EVENT_TYPES = frozenset({
    "birthday", "anniversary", "holiday",
})

# Event types that indicate travel/outing
_TRAVEL_EVENT_TYPES = frozenset({
    "trip", "travel", "business_trip",
})

# Fallback life-context hints for events not yet enriched by CurationEnricher
_HINT_MAP = {
    "birthday": "记得准备礼物",
    "anniversary": "特别的日子",
    "medical": "记得带病历和证件",
    "favor": "人情往来",
    "meeting": "会议结束后可以简单记录一下讨论要点",
    "flight": "建议提前2小时到达机场，确认行李限额",
    "medical_appointment": "记得带上历次就诊记录和检查报告",
    "exam": "考试当天注意休息，提前确认考场地址",
    "child_pickup": "接送时间有变化记得提前通知老师",
    "work_deadline": "截止前一天留时间做最终检查",
    "school_event": "提前确认活动时间和地点，带好需要的材料",
    "family_dinner": "提前确认人数和忌口，预留充足时间",
    "gym": "记得带运动装备和水杯",
    "medication": "按时用药，注意用法用量",
    "concert": "提前确认座位和入场时间，注意停车安排",
    "conference": "准备好名片和笔记本，提前熟悉议程",
}


class TimelineService:
    """Timeline service — day-grouped curated events with conflict detection."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_timeline(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
        direction: Literal["past", "future"] = "future",
        days: int = 14,
        cursor: Optional[str] = None,
        day_themes: Optional[Dict[date, DayTheme]] = None,
    ) -> TimelineResponse:
        """Get timeline data with directional support and cursor pagination."""
        today = local_today()

        if cursor:
            try:
                anchor_date = date.fromisoformat(cursor)
            except ValueError:
                anchor_date = today
        else:
            anchor_date = today

        if direction == "past":
            start_date = anchor_date - timedelta(days=days)
            end_date = anchor_date
        else:
            start_date = anchor_date
            end_date = anchor_date + timedelta(days=days)

        events = await self._query_events(
            user_id=user_id,
            family_id=family_id,
            start_date=start_date,
            end_date=end_date,
            direction=direction
        )

        # Compute has_more from curated event count BEFORE merging fallback trips
        curated_count = len(events)

        # Fallback: include active TripPlan records that have no CuratedEvent
        if direction == "future":
            fallback = await self._query_uncurated_trips(
                family_id=family_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )
            events = list(events) + fallback

        # PLAN-014: query date-anchored insights for the visible date range.
        # Returns a mapping {event_id_str: [TimelineInsightItem, ...]} so that
        # _group_by_date can attach insights to the correct day groups.
        insights_by_event_id = await self._query_date_anchored_insights(
            user_id=user_id,
            family_id=family_id,
            start_date=start_date,
            end_date=end_date,
        )

        # PLAN-010: compute GapWarnings for visible date range (cross-view parity).
        # Batch-prefetch to avoid N cold-cache hits. Graceful degradation on timeout.
        gap_alerts_by_date: Dict[date, List[TimelineAlertItem]] = {}
        if family_id and direction == "future":
            gap_alerts_by_date = await self._compute_gap_warnings(
                family_id=family_id,
                user_id=user_id,
                events=events,
                start_date=start_date,
                end_date=end_date,
            )

        day_groups = self._group_by_date(
            events=events,
            today=today,
            direction=direction,
            day_themes=day_themes or {},
            insights_by_event_id=insights_by_event_id,
            gap_alerts_by_date=gap_alerts_by_date,
        )

        if direction == "past":
            next_cursor = (start_date - timedelta(days=1)).isoformat() if events else None
        else:
            next_cursor = (end_date + timedelta(days=1)).isoformat() if events else None

        has_more = curated_count >= days

        return TimelineResponse(
            direction=direction,
            day_groups=day_groups,
            next_cursor=next_cursor,
            has_more=has_more
        )

    async def _query_events(
        self,
        user_id: UUID,
        family_id: Optional[UUID],
        start_date: date,
        end_date: date,
        direction: str
    ) -> List[CuratedEvent]:
        """Query curated events within the date range."""
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        conditions = [
            or_(
                # Events that start within the range
                and_(
                    CuratedEvent.normalized_start >= start_dt,
                    CuratedEvent.normalized_start < end_dt,
                ),
                # Multi-day events that started before but span into the range
                and_(
                    CuratedEvent.normalized_start <= start_dt,
                    CuratedEvent.normalized_end >= start_dt,
                ),
            ),
            CuratedEvent.status != "cancelled",
            CuratedEvent.is_active.is_(True),
        ]

        if family_id:
            conditions.append(CuratedEvent.family_id == family_id)
        else:
            conditions.append(CuratedEvent.user_id == user_id)

        query = (
            select(CuratedEvent)
            .options(selectinload(CuratedEvent.trip_plan))
            .where(and_(*conditions))
        )

        if direction == "past":
            query = query.order_by(CuratedEvent.normalized_start.desc())
        else:
            query = query.order_by(CuratedEvent.normalized_start.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _query_uncurated_trips(
        self,
        family_id: Optional[UUID],
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[CuratedEvent]:
        """Find active TripPlan records that have no corresponding CuratedEvent.

        Builds lightweight CuratedEvent-compatible objects so that the
        timeline can display trips whose curation trigger was missed or
        hasn't executed yet.  Uses NOT EXISTS subquery to atomically
        exclude already-curated trips (avoids TOCTOU race).
        """
        import uuid as uuid_mod
        from sqlalchemy import exists
        from sqlalchemy.orm import make_transient
        from ...trip.models.trip_plan import TripPlan

        # Deterministic namespace for synthetic CuratedEvent IDs
        # to avoid collision with real CuratedEvent or TripPlan PKs
        _SYNTHETIC_NS = uuid_mod.UUID("b7e3d1a0-4f2c-4a8b-9c6e-1d5f3a2b7c8e")

        # NOT EXISTS subquery: exclude trips that already have an active CuratedEvent
        curated_exists = (
            select(CuratedEvent.id)
            .where(
                CuratedEvent.trip_id == TripPlan.trip_id,
                CuratedEvent.is_active.is_(True),
            )
            .correlate(TripPlan)
            .exists()
        )

        conditions = [
            TripPlan.is_active.is_(True),
            TripPlan.status.in_(["planning", "confirmed", "in_progress"]),
            ~curated_exists,
            or_(
                and_(
                    TripPlan.start_date >= start_date,
                    TripPlan.start_date <= end_date,
                ),
                and_(
                    TripPlan.start_date <= start_date,
                    TripPlan.end_date >= start_date,
                ),
            ),
        ]

        if family_id:
            conditions.append(TripPlan.family_id == family_id)
        else:
            conditions.append(TripPlan.created_by == user_id)

        trip_query = select(TripPlan).where(and_(*conditions))
        trip_result = await self.db.execute(trip_query)
        trips = trip_result.scalars().all()

        fallback_events: List[CuratedEvent] = []
        user_tz = get_user_timezone()

        for trip in trips:
            if trip.start_date is None or trip.end_date is None:
                continue
            destination = (trip.destination or "").strip() or "未知目的地"
            trip_name = (trip.trip_name or "").strip() or f"{destination}行程"
            event_type = "business_trip" if trip.category == "business" else "travel"

            # Deterministic ID: stable across requests, no collision with real PKs
            synthetic_id = uuid_mod.uuid5(_SYNTHETIC_NS, str(trip.trip_id))

            # Build a transient CuratedEvent (not persisted) for display only
            synthetic = CuratedEvent(
                id=synthetic_id,
                family_id=trip.family_id,
                user_id=trip.created_by,
                trip_id=trip.trip_id,
                original_event_ids=[str(trip.trip_id)],
                source_types=["trip_plan_fallback"],
                title=trip_name,
                normalized_start=datetime.combine(
                    trip.start_date, datetime.min.time(), tzinfo=user_tz
                ),
                normalized_end=datetime.combine(
                    trip.end_date, datetime.max.time(), tzinfo=user_tz
                ),
                location=destination,
                event_type=event_type,
                status=trip.status,
                priority=trip.priority or "normal",
                trip_name=trip_name[:200],
                is_active=True,
                notes=trip.description,
                confidence=0.5,
                visibility_tier="standard",
            )
            # Detach from session to prevent accidental persistence
            make_transient(synthetic)
            # Safe to assign relationship after detaching
            synthetic.trip_plan = trip
            fallback_events.append(synthetic)

        if fallback_events:
            logger.info(
                "Timeline fallback: synthesized %d events for uncurated trips",
                len(fallback_events),
            )

        return fallback_events

    async def _query_date_anchored_insights(
        self,
        user_id: UUID,
        family_id: Optional[UUID],
        start_date: date,
        end_date: date,
    ) -> Dict[str, List[TimelineInsightItem]]:
        """Query pending Insights anchored to events in the date range.

        Uses the unified ``insights`` + ``insight_entities`` tables.
        Returns a mapping keyed by event entity_id (str) to list of
        TimelineInsightItem.  Only insights linked to an event entity are
        included (date-anchored by association to a specific event).

        Insights that are expired, dismissed, or actioned are excluded.
        """
        from ...insight.models import InsightEntity

        now = utc_now()
        # Convert local date range to UTC for created_at filter (PLAN-007)
        start_date_utc, end_date_utc = local_date_range_to_utc(start_date, end_date)
        try:
            conditions = [
                Insight.user_id == user_id,
                Insight.status.in_([
                    InsightStatus.PENDING.value,
                    InsightStatus.ACTIVE.value,
                    InsightStatus.ACKNOWLEDGED.value,
                ]),
                or_(
                    Insight.expires_at.is_(None),
                    Insight.expires_at > now,
                ),
                InsightEntity.entity_type == "event",
                Insight.created_at.between(start_date_utc, end_date_utc),
            ]
            if family_id:
                conditions.append(Insight.family_id == family_id)

            result = await self.db.execute(
                select(Insight, InsightEntity.entity_id)
                .join(InsightEntity, InsightEntity.insight_id == Insight.id)
                .where(and_(*conditions))
            )
            rows = list(result.all())
        except Exception as exc:
            logger.warning("Timeline: failed to query insights: %s", exc)
            return {}

        mapping: Dict[str, List[TimelineInsightItem]] = {}
        for insight_row, event_entity_id in rows:
            event_id_str = str(event_entity_id)
            # Map numeric urgency to string label
            urgency_val = insight_row.urgency
            if isinstance(urgency_val, int):
                if urgency_val >= 70:
                    urgency_str = "high"
                elif urgency_val >= 40:
                    urgency_str = "normal"
                else:
                    urgency_str = "low"
            else:
                urgency_str = str(urgency_val or "normal")
            item = TimelineInsightItem(
                id=str(insight_row.id),
                insight_type=insight_row.insight_type,
                title=insight_row.title,
                content=insight_row.content,
                urgency=urgency_str,
                action_options=insight_row.action_options or [],
            )
            if event_id_str not in mapping:
                mapping[event_id_str] = []
            mapping[event_id_str].append(item)
        return mapping

    def _group_by_date(
        self,
        events: List[CuratedEvent],
        today: date,
        direction: str,
        day_themes: Optional[Dict[date, DayTheme]] = None,
        insights_by_event_id: Optional[Dict[str, List[TimelineInsightItem]]] = None,
        gap_alerts_by_date: Optional[Dict[date, List[TimelineAlertItem]]] = None,
    ) -> List[TimelineDayGroup]:
        """Group events by date, detect conflicts, and enrich with life context.

        ``day_themes`` is an optional mapping from date → DayTheme produced by
        ``SecretaryOrchestrator``.  When a theme is available for a given date
        its ``title`` is used as the ``day_mood`` label, ensuring the timeline
        shows the same mood signal that the briefing uses.  When no theme is
        available the mood is ``None`` (no mood label).

        ``insights_by_event_id`` (PLAN-014): maps event_id str → list of
        TimelineInsightItem.  When provided, each day group is populated with
        the insights whose related_event_id belongs to events in that day.
        """
        themes = day_themes or {}
        insight_map = insights_by_event_id or {}
        alerts_map = gap_alerts_by_date or {}
        grouped: dict = {}
        # Track which event_ids appear on each date for insight attachment.
        date_event_ids: Dict[date, List[str]] = {}

        for event in events:
            if event.normalized_start is None:
                continue
            event_date = to_local_date(event.normalized_start)
            if event_date not in grouped:
                grouped[event_date] = []
                date_event_ids[event_date] = []

            trip_label = event.get_trip_label()
            visibility_tier = event.visibility_tier
            life_hint = self._build_life_context_hint(event)

            timeline_event = TimelineEventItem(
                id=str(event.id),
                title=event.title,
                start_time=event.normalized_start,
                end_time=event.normalized_end,
                event_type=event.event_type or "other",
                status=event.status,
                priority=event.priority,
                location=event.location,
                notes=event.notes,
                trip_id=str(event.trip_id) if event.trip_id else None,
                trip_label=trip_label,
                visibility_tier=visibility_tier,
                life_context_hint=life_hint,
            )
            grouped[event_date].append(timeline_event)
            # PLAN-014: track event IDs per date for insight attachment.
            date_event_ids[event_date].append(str(event.id))

        day_groups = []
        sorted_dates = sorted(grouped.keys(), reverse=(direction == "past"))

        for event_date in sorted_dates:
            day_events = grouped[event_date]
            day_events.sort(key=lambda e: e.start_time)
            self._detect_conflicts_and_assign_sequences(day_events)

            if direction == "past":
                day_events.sort(key=lambda e: e.start_time, reverse=True)

            # Use DayTheme.title from the orchestrator as the single source
            # of truth for day mood.  Falls back to None when no theme exists.
            theme = themes.get(event_date)
            day_mood = theme.title if theme is not None else None
            highlight_id = self._pick_highlight_event(day_events)

            # PLAN-014: collect insights anchored to events on this day.
            day_insights: List[TimelineInsightItem] = []
            if insight_map:
                seen_insight_ids: set = set()
                for eid in date_event_ids.get(event_date, []):
                    for insight_item in insight_map.get(eid, []):
                        if insight_item.id not in seen_insight_ids:
                            day_insights.append(insight_item)
                            seen_insight_ids.add(insight_item.id)

            # PLAN-010: attach GapWarning alerts for this day
            day_alerts = alerts_map.get(event_date, [])

            day_groups.append(TimelineDayGroup(
                date=event_date,
                date_label=self._format_date_label(event_date, today),
                events=day_events,
                summary=self._generate_day_summary(
                    day_events, event_date, day_mood=day_mood,
                ),
                week_label=self._get_week_label(event_date, today),
                day_mood=day_mood,
                highlight_event_id=highlight_id,
                insights=day_insights,
                alerts=day_alerts,
            ))

        return day_groups

    def _detect_conflicts_and_assign_sequences(
        self,
        events: List[TimelineEventItem],
    ) -> None:
        """Detect time conflicts and assign day-sequence numbers (in-place)."""
        n = len(events)
        for i, event in enumerate(events):
            event.sequence_of_day = i + 1

            if not event.end_time:
                continue

            conflicts = []
            for j in range(n):
                if i == j:
                    continue
                other = events[j]
                if not other.end_time:
                    continue
                if event.start_time < other.end_time and other.start_time < event.end_time:
                    conflicts.append(other.id)

            if conflicts:
                event.has_conflict = True
                event.conflict_with = conflicts

    def _format_date_label(self, event_date: date, today: date) -> str:
        """Format date label with relative day names."""
        diff = (event_date - today).days
        weekday = self._weekday(event_date)

        if diff == 0:
            return f"\u4eca\u5929 \u00b7 {event_date.month}\u6708{event_date.day}\u65e5 {weekday}"
        elif diff == -1:
            return f"\u6628\u5929 \u00b7 {event_date.month}\u6708{event_date.day}\u65e5 {weekday}"
        elif diff == 1:
            return f"\u660e\u5929 \u00b7 {event_date.month}\u6708{event_date.day}\u65e5 {weekday}"
        else:
            return f"{event_date.month}\u6708{event_date.day}\u65e5 {weekday}"

    def _weekday(self, d: date) -> str:
        weekdays = ["\u5468\u4e00", "\u5468\u4e8c", "\u5468\u4e09", "\u5468\u56db", "\u5468\u4e94", "\u5468\u516d", "\u5468\u65e5"]
        return weekdays[d.weekday()]

    def _get_week_label(self, event_date: date, today: date) -> Optional[str]:
        """Get week separator label."""
        today_week = today.isocalendar()[1]
        event_week = event_date.isocalendar()[1]
        today_year = today.isocalendar()[0]
        event_year = event_date.isocalendar()[0]

        if event_year == today_year:
            if event_week == today_week:
                return "\u672c\u5468"
            elif event_week == today_week + 1:
                return "\u4e0b\u5468"
            elif event_week == today_week - 1:
                return "\u4e0a\u5468"

        return None

    def _generate_day_summary(
        self,
        events: List[TimelineEventItem],
        event_date: Optional[date] = None,
        day_mood: Optional[str] = None,
    ) -> str:
        """Generate warm, life-secretary style day summary.

        A life secretary describes your day in terms of what matters to you
        personally, not just counts and categories. She highlights the most
        meaningful event and frames the day around life rhythm.
        """
        total = len(events)
        if total == 0:
            return ""

        completed = sum(1 for e in events if e.status == "completed")
        all_completed = completed == total
        suffix = "\u2014\u2014\u90fd\u5df2\u5b8c\u6210" if all_completed else ""

        # Single event: use title directly with warm framing
        if total == 1:
            ev = events[0]
            if all_completed:
                return f"{ev.title}\uff0c\u5df2\u5b8c\u6210"
            if ev.event_type in _SPECIAL_EVENT_TYPES:
                return ev.title
            if ev.location:
                return f"{ev.title}\uff0c\u5728{ev.location}"
            return ev.title

        # Find the most important event for narrative focus
        focus_event = self._find_focus_event(events)

        # Check for special-occasion days
        has_special = any(
            ev.event_type in _SPECIAL_EVENT_TYPES for ev in events
        )
        has_travel = any(
            ev.event_type in _TRAVEL_EVENT_TYPES for ev in events
        )

        is_weekend = event_date is not None and event_date.weekday() >= 5

        # Build narrative summary based on day character
        if has_special and focus_event:
            # Special occasion anchors the day
            others = total - 1
            if others > 0:
                return f"{focus_event.title}\uff0c\u8fd8\u6709{others}\u4ef6\u4e8b{suffix}"
            return f"{focus_event.title}{suffix}"

        if has_travel and focus_event:
            trip_label = focus_event.trip_label or focus_event.location or ""
            if trip_label:
                others = total - 1
                if others > 0:
                    return f"{trip_label}\u7684\u884c\u7a0b\uff0c\u53e6\u6709{others}\u4ef6\u4e8b{suffix}"
                return f"{trip_label}\u7684\u884c\u7a0b{suffix}"

        if total <= 3:
            # Compact: mention the focus event + count
            if focus_event:
                others = total - 1
                if others == 1:
                    return f"{focus_event.title}\uff0c\u8fd8\u6709\u4e00\u4ef6\u4e8b{suffix}"
                return f"{focus_event.title}\u7b49{total}\u4ef6\u4e8b{suffix}"
            return f"{total}\u4ef6\u4e8b{suffix}"

        # 4+ events: frame around day mood
        if is_weekend:
            if day_mood:
                return f"{day_mood}\uff0c{total}\u4ef6\u4e8b{suffix}"
            return f"\u5468\u672b\u5b89\u6392\u4e30\u5bcc\uff0c{total}\u4ef6\u4e8b{suffix}"

        if day_mood:
            return f"{day_mood}\uff0c{total}\u4ef6\u4e8b{suffix}"
        return f"\u5145\u5b9e\u7684\u4e00\u5929\uff0c{total}\u4ef6\u4e8b{suffix}"

    @staticmethod
    def _find_focus_event(
        events: List[TimelineEventItem],
    ) -> Optional[TimelineEventItem]:
        """Pick the most meaningful event to anchor the day summary around.

        Priority order:
        1. Special occasions (birthday, anniversary, holiday)
        2. Focus-tier events
        3. Travel events
        4. High-priority events
        5. First event of the day
        """
        # Special occasions first
        for ev in events:
            if ev.event_type in _SPECIAL_EVENT_TYPES:
                return ev

        # Focus-tier events
        for ev in events:
            if ev.visibility_tier == "focus":
                return ev

        # Travel events
        for ev in events:
            if ev.event_type in _TRAVEL_EVENT_TYPES:
                return ev

        # High-priority
        for ev in events:
            if ev.priority in ("high", "critical"):
                return ev

        # Default to first
        return events[0] if events else None

    @staticmethod
    def _pick_highlight_event(
        events: List[TimelineEventItem],
    ) -> Optional[str]:
        """Pick the event ID that should be visually highlighted.

        Only highlights truly important events (focus-tier, special
        occasions, high priority).  Regular events return None.

        NOTE: Priority order intentionally differs from _find_focus_event.
        Focus-tier first here because visual highlighting should respect
        the curator's explicit focus designation, whereas _find_focus_event
        (used for day summary anchoring) prioritizes life significance.
        """
        for ev in events:
            if ev.visibility_tier == "focus":
                return ev.id
        for ev in events:
            if ev.event_type in _SPECIAL_EVENT_TYPES:
                return ev.id
        for ev in events:
            if ev.priority in ("high", "critical"):
                return ev.id
        return None

    @staticmethod
    def _build_life_context_hint(event: CuratedEvent) -> Optional[str]:
        """Build a short warm contextual hint for an event.

        Pre-generated path (PLAN-013): returns event.life_context_hint when
        it has been populated by CurationEnricher at curation time.

        Fallback path: uses the static _HINT_MAP for events that have not
        been enriched yet, preserving backward compatibility.

        Examples: '和家人一起', '记得带证件', '准备礼物'
        """
        # --- Pre-generated path (warm content from CurationEnricher) ---
        if event.life_context_hint is not None:
            return event.life_context_hint

        # --- Fallback: static rule-based hints ---
        event_type = event.event_type or ""

        hint = _HINT_MAP.get(event_type)
        if hint:
            return hint

        if event_type in ("travel", "trip"):
            if event.location:
                return f"\u76ee\u7684\u5730: {event.location}"
            return None

        return None

    # ------------------------------------------------------------------
    # PLAN-010: GapWarning computation (cross-view parity)
    # ------------------------------------------------------------------

    async def _compute_gap_warnings(
        self,
        family_id: UUID,
        user_id: UUID,
        events: List[CuratedEvent],
        start_date: date,
        end_date: date,
    ) -> Dict[date, List[TimelineAlertItem]]:
        """Compute GapWarnings for the visible date range.

        Uses SecretaryOrchestrator to detect schedule conflicts, with
        Redis caching per (family_id, date) and batch prefetch.
        Returns a mapping {date: [TimelineAlertItem, ...]}.
        """
        from ....core.cache import redis_client

        result: Dict[date, List[TimelineAlertItem]] = {}

        # Group events by date for per-day orchestration
        events_by_date: Dict[date, List[CuratedEvent]] = {}
        for event in events:
            if event.normalized_start is None:
                continue
            event_date = to_local_date(event.normalized_start)
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(event)

        # Only process dates that have 2+ events (conflicts require multiple events)
        dates_to_process = [
            d for d, evts in events_by_date.items() if len(evts) >= 2
        ]
        if not dates_to_process:
            return result

        # Check cache first
        uncached_dates: List[date] = []
        for d in dates_to_process:
            cache_key = f"timeline:gap:{family_id}:{d.isoformat()}"
            try:
                cached = await redis_client.get(cache_key)
                if cached is not None:
                    alerts = self._deserialize_gap_alerts(cached)
                    if alerts:
                        result[d] = alerts
                    continue
            except Exception:
                pass
            uncached_dates.append(d)

        if not uncached_dates:
            return result

        # Batch orchestrate uncached dates with timeout for graceful degradation
        try:
            orchestrated = await asyncio.wait_for(
                self._batch_orchestrate_days(
                    family_id=family_id,
                    user_id=user_id,
                    events_by_date={d: events_by_date[d] for d in uncached_dates},
                ),
                timeout=0.2,  # 200ms graceful degradation threshold
            )
        except asyncio.TimeoutError:
            logger.warning(
                "GapWarning orchestration timed out for family %s, skipping",
                family_id,
            )
            return result
        except Exception:
            logger.warning(
                "GapWarning orchestration failed for family %s",
                family_id,
                exc_info=True,
            )
            return result

        # Convert GapWarnings to TimelineAlertItems and cache
        for d, orchestrated_day in orchestrated.items():
            alerts: List[TimelineAlertItem] = []
            for gap in orchestrated_day.gaps:
                alerts.append(TimelineAlertItem(
                    alert_type=f"gap_{gap.gap_type}",
                    severity="suggestion",
                    title=gap.gap_type.replace("_", " ").title(),
                    description=gap.suggestion or "",
                    related_event_ids=[str(eid) for eid in gap.affected_event_ids],
                    icon=_TIMELINE_GAP_ICONS.get(gap.gap_type, "\U0001f4a1"),
                ))
            if alerts:
                result[d] = alerts

            # Cache result (even empty — prevents repeated orchestration)
            cache_key = f"timeline:gap:{family_id}:{d.isoformat()}"
            try:
                serialized = self._serialize_gap_alerts(alerts)
                await redis_client.set(cache_key, serialized, ex=_GAP_CACHE_TTL)
            except Exception:
                pass

        return result

    async def _batch_orchestrate_days(
        self,
        family_id: UUID,
        user_id: UUID,
        events_by_date: Dict[date, List[CuratedEvent]],
    ) -> dict:
        """Run SecretaryOrchestrator for multiple dates in parallel."""
        from ...curation.services.orchestrator import SecretaryOrchestrator
        from ...curation.services.priority_engine import HybridPriorityEngine

        orchestrator = SecretaryOrchestrator(
            self.db, HybridPriorityEngine(calibration_enabled=False),
        )

        async def _orchestrate_single(target_date: date, day_events: List[CuratedEvent]):
            try:
                return target_date, await orchestrator.orchestrate_day(
                    family_id=family_id,
                    user_id=user_id,
                    target_date=target_date,
                    events=day_events,
                )
            except Exception:
                logger.debug(
                    "GapWarning orchestration failed for date %s", target_date,
                    exc_info=True,
                )
                return target_date, None

        tasks = [
            _orchestrate_single(d, evts)
            for d, evts in events_by_date.items()
        ]
        results = await asyncio.gather(*tasks)

        return {
            d: orch_day
            for d, orch_day in results
            if orch_day is not None
        }

    @staticmethod
    def _serialize_gap_alerts(alerts: List[TimelineAlertItem]) -> str:
        """Serialize gap alerts to JSON string for Redis caching."""
        return json.dumps([a.model_dump() for a in alerts])

    @staticmethod
    def _deserialize_gap_alerts(data: str) -> List[TimelineAlertItem]:
        """Deserialize gap alerts from Redis cached JSON string."""
        try:
            items = json.loads(data)
            return [TimelineAlertItem(**item) for item in items]
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    async def get_event_detail(
        self,
        event_id: UUID,
        user_id: UUID,
        family_id: Optional[UUID] = None
    ) -> Optional[CuratedEvent]:
        """Get single event detail with associations."""
        conditions = [CuratedEvent.id == event_id]

        if family_id:
            conditions.append(CuratedEvent.family_id == family_id)
        else:
            conditions.append(CuratedEvent.user_id == user_id)

        query = (
            select(CuratedEvent)
            .options(selectinload(CuratedEvent.trip_plan))
            .options(selectinload(CuratedEvent.associations))
            .where(and_(*conditions))
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

