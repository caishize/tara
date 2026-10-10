"""Memory lane and on-this-day services.

Extracted from secretary/services/event_context_service.py
(get_memory_lane, get_on_this_day).
"""
from __future__ import annotations
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now, local_today, to_local
from ...curation.models import CuratedEvent
from ..kanban_schemas import (
    StoryGroup,
    YearGroup,
    MemoryLaneResponse,
    OnThisDayEvent,
    OnThisDayItem,
    OnThisDayResponse,
)
from ._event_converter import to_kanban_event, get_user_timezone

logger = get_logger(__name__)

# Theme labels for deriving month story titles from dominant event types
_MONTH_THEME_MAP = {
    "social": "\u805a\u4f1a",
    "meeting": "\u805a\u4f1a",
    "travel": "\u65c5\u884c",
    "trip": "\u65c5\u884c",
    "birthday": "\u5e86\u795d",
    "anniversary": "\u7eaa\u5ff5",
    "medical": "\u5065\u5eb7",
    "favor": "\u4eba\u60c5\u5f80\u6765",
}


class MemoryLaneService:
    """Past events organized into story groups by trip or month."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_memory_lane(
        self,
        family_id: UUID,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        year: Optional[int] = None,
    ) -> MemoryLaneResponse:
        """Past events organized into story groups by trip or month."""
        now = utc_now()

        conditions = [
            CuratedEvent.family_id == family_id,
            CuratedEvent.is_active.is_(True),
            CuratedEvent.status != "cancelled",
            CuratedEvent.normalized_start < now,
        ]
        if year is not None:
            conditions.append(
                extract("year", CuratedEvent.normalized_start) == year
            )

        stmt = (
            select(CuratedEvent)
            .where(and_(*conditions))
            .order_by(CuratedEvent.normalized_start.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()

        if not events:
            return MemoryLaneResponse()

        trip_ids = {ev.trip_id for ev in events if ev.trip_id}
        memory_map = await self._fetch_trip_memory_summaries(
            family_id, trip_ids,
        )

        # Group events into stories
        trip_groups: dict[UUID, List[CuratedEvent]] = {}
        month_groups: dict[str, List[CuratedEvent]] = {}

        _special_types = {"birthday", "anniversary", "holiday"}
        for ev in events:
            if ev.trip_id:
                trip_groups.setdefault(ev.trip_id, []).append(ev)
                if ev.event_type in _special_types:
                    key = f"special-{ev.id}"
                    month_groups.setdefault(key, []).append(ev)
            else:
                local_dt = to_local(ev.normalized_start) if ev.normalized_start else None
                key = local_dt.strftime("%Y-%m") if local_dt else "unknown"
                month_groups.setdefault(key, []).append(ev)

        # Build story groups
        stories: List[StoryGroup] = []

        for tid, trip_events in trip_groups.items():
            sorted_evs = sorted(trip_events, key=lambda e: e.normalized_start or now)
            title = self._build_trip_story_title(sorted_evs)
            summaries = memory_map.get(tid, [])
            stories.append(StoryGroup(
                trip_id=str(tid),
                title=title,
                events=[to_kanban_event(e) for e in sorted_evs],
                memory_summaries=summaries,
                start_date=sorted_evs[0].normalized_start.date() if sorted_evs[0].normalized_start else None,
                end_date=sorted_evs[-1].normalized_start.date() if sorted_evs[-1].normalized_start else None,
                emotional_summary=summaries[0] if summaries else None,
                emotional_tag=self._compute_emotional_tag(sorted_evs),
            ))

        for month_key, month_events in month_groups.items():
            sorted_evs = sorted(month_events, key=lambda e: e.normalized_start or now)
            title = self._build_month_story_title(sorted_evs, month_key)
            stories.append(StoryGroup(
                title=title,
                events=[to_kanban_event(e) for e in sorted_evs],
                start_date=sorted_evs[0].normalized_start.date() if sorted_evs[0].normalized_start else None,
                end_date=sorted_evs[-1].normalized_start.date() if sorted_evs[-1].normalized_start else None,
                emotional_tag=self._compute_emotional_tag(sorted_evs),
            ))

        stories.sort(key=lambda s: s.start_date or date.min, reverse=True)

        # Group into year groups
        year_groups_map: dict[int, List[StoryGroup]] = {}
        for story in stories:
            y = story.start_date.year if story.start_date else 0
            year_groups_map.setdefault(y, []).append(story)

        years = [
            YearGroup(
                year=y,
                stories=story_list,
                event_count=sum(len(s.events) for s in story_list),
            )
            for y, story_list in sorted(year_groups_map.items(), reverse=True)
        ]

        return MemoryLaneResponse(
            years=years,
            total_events=len(events),
        )

    async def get_on_this_day(
        self,
        family_id: UUID,
        user_id: UUID,
    ) -> OnThisDayResponse:
        """Find events from previous years on the same month/day.

        Groups by year with years_ago and enriches with memory fragments.
        """
        user_tz = await get_user_timezone(self.session, user_id)
        today = local_today(user_tz)
        current_year = today.year

        stmt = (
            select(CuratedEvent)
            .where(and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
                extract("month", CuratedEvent.normalized_start) == today.month,
                extract("day", CuratedEvent.normalized_start) == today.day,
                extract("year", CuratedEvent.normalized_start) != current_year,
            ))
            .order_by(extract("year", CuratedEvent.normalized_start).desc())
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()

        trip_ids = {ev.trip_id for ev in events if ev.trip_id}
        memory_map = await self._fetch_trip_memory_summaries(
            family_id, trip_ids,
        )

        # Group events by year
        year_groups: dict[int, List[CuratedEvent]] = {}
        for ev in events:
            ev_year = ev.normalized_start.year if ev.normalized_start else 0
            year_groups.setdefault(ev_year, []).append(ev)

        items: List[OnThisDayItem] = []
        for yr in sorted(year_groups.keys(), reverse=True):
            yr_events = year_groups[yr]
            on_this_day_events = [
                OnThisDayEvent(
                    id=str(ev.id),
                    title=ev.title,
                    event_type=ev.event_type,
                    participants=self._extract_participants(ev),
                    memory_fragments=memory_map.get(ev.trip_id, [])[:3] if ev.trip_id else [],
                )
                for ev in yr_events
            ]
            years_ago = current_year - yr
            narrative = self._build_on_this_day_narrative(
                years_ago, on_this_day_events,
            )
            items.append(OnThisDayItem(
                year=yr,
                years_ago=years_ago,
                events=on_this_day_events,
                narrative=narrative,
            ))

        return OnThisDayResponse(
            items=items,
            month=today.month,
            day=today.day,
        )

    async def _fetch_trip_memory_summaries(
        self,
        family_id: UUID,
        trip_ids: set,
    ) -> dict:
        """Fetch conversation memory summaries keyed by trip UUID.

        Shared by get_memory_lane and get_on_this_day to avoid duplication.
        """
        if not trip_ids:
            return {}

        from ...memory.models import ConversationMemory

        mem_stmt = (
            select(ConversationMemory.entities, ConversationMemory.summary)
            .where(and_(
                ConversationMemory.family_id == family_id,
                ConversationMemory.status == "active",
            ))
            .limit(200)
        )
        mem_result = await self.session.execute(mem_stmt)

        memory_map: dict[UUID, List[str]] = {}
        for row in mem_result.all():
            entities = row[0] or {}
            trip_ref = entities.get("trip_id")
            if not trip_ref:
                continue
            try:
                tid = UUID(trip_ref) if isinstance(trip_ref, str) else trip_ref
                if tid in trip_ids:
                    memory_map.setdefault(tid, []).append(row[1])
            except (ValueError, TypeError):
                pass
        return memory_map

    @staticmethod
    def _build_trip_story_title(sorted_events: List[CuratedEvent]) -> str:
        """Build a warm narrative title for a trip story group.

        Life-secretary style: focuses on the experience, not logistics.
        Examples:
        - "那次去丽江的旅行" (with destination)
        - "全家三亚5天之旅" (family trip)
        - Trip name or first event title as fallback
        """
        first = sorted_events[0]
        last = sorted_events[-1]

        destination = (first.trip_name or "").strip()
        if not destination:
            destination = (first.location or "").strip()

        start_dt = first.normalized_start
        end_dt = last.normalized_start
        if start_dt and end_dt:
            duration = max((end_dt.date() - start_dt.date()).days + 1, 1)
        else:
            duration = len(sorted_events)

        if not destination:
            return first.trip_name or first.title or "\u65c5\u884c\u56de\u5fc6"

        # For short trips, emphasize the destination experience
        if duration <= 2:
            return f"\u90a3\u6b21\u53bb{destination}"

        # For longer trips, include duration for warmth
        return f"{destination}{duration}\u5929\u4e4b\u65c5"

    @staticmethod
    def _build_month_story_title(
        sorted_events: List[CuratedEvent],
        month_key: str,
    ) -> str:
        """Build a warm narrative title for a month story group.

        Life-secretary style: characterizes the month by its dominant theme.
        Examples:
        - Single event: use its title directly
        - Special events: use the event title
        - Multiple events: derive theme from event types
        """
        if len(sorted_events) == 1:
            return sorted_events[0].title

        if month_key.startswith("special-"):
            return sorted_events[0].title

        parts = month_key.split("-")
        if len(parts) != 2:
            return month_key

        try:
            year_num = int(parts[0])
            month_num = int(parts[1])
        except (ValueError, TypeError):
            return month_key

        # Derive month theme from dominant event types
        type_counts: dict[str, int] = {}
        for ev in sorted_events:
            et = ev.event_type or "other"
            type_counts[et] = type_counts.get(et, 0) + 1

        dominant_type = max(type_counts, key=lambda t: type_counts[t])

        theme = _MONTH_THEME_MAP.get(dominant_type, "")

        if theme:
            return f"{year_num}\u5e74{month_num}\u6708\u7684{theme}\u65f6\u5149"

        return f"{year_num}\u5e74{month_num}\u6708\u7684\u56de\u5fc6"

    @staticmethod
    def _build_on_this_day_narrative(
        years_ago: int,
        events: List[OnThisDayEvent],
    ) -> str:
        """Build warm narrative framing text for on-this-day items.

        Life-secretary style: creates emotional connection to the past.
        Examples:
        - "3年前的今天，你们一家去了三亚"
        - "去年的今天，是爸爸的生日"
        - "2年前的今天，和老朋友们聚了聚"
        """
        prefix = "\u53bb\u5e74\u7684\u4eca\u5929" if years_ago == 1 else f"{years_ago}\u5e74\u524d\u7684\u4eca\u5929"

        if not events:
            return prefix

        first = events[0]
        first_title = first.title

        # Enrich with participants if available
        if first.participants and len(first.participants) <= 3:
            people = "\u3001".join(first.participants)
            if first.event_type in ("travel", "trip", "business_trip"):
                return f"{prefix}\uff0c\u548c{people}\u53bb\u4e86\u65c5\u884c"
            if first.event_type in ("social", "meeting"):
                return f"{prefix}\uff0c\u548c{people}\u805a\u4e86\u805a"

        # Enrich with memory fragments
        if first.memory_fragments:
            fragment = first.memory_fragments[0]
            if len(fragment) <= 30:
                return f"{prefix}\uff0c{first_title}\u2014\u2014\u300c{fragment}\u300d"

        return f"{prefix}\uff0c{first_title}"

    @staticmethod
    def _compute_emotional_tag(events: List[CuratedEvent]) -> Optional[str]:
        """Compute a warm emotional tag for a story group.

        Returns tags like '温馨旅途', '家庭时光', '朋友聚会', '成长记录'
        """
        if not events:
            return None

        types = {ev.event_type or "other" for ev in events}

        if "business_trip" in types and not (types & {"travel", "trip"}):
            return "\u51fa\u5dee\u8bb0\u5f55"
        if types & {"travel", "trip", "business_trip"}:
            return "\u6e29\u99a8\u65c5\u9014"
        if types & {"birthday", "anniversary"}:
            return "\u7279\u522b\u7684\u65e5\u5b50"
        if types & {"social", "meeting"}:
            return "\u670b\u53cb\u805a\u4f1a"
        if types & {"favor"}:
            return "\u4eba\u60c5\u5f80\u6765"
        if types & {"medical"}:
            return "\u5065\u5eb7\u8bb0\u5f55"

        return None

    @staticmethod
    def _extract_participants(ev: CuratedEvent) -> List[str]:
        """Extract participant names from event metadata."""
        participants = getattr(ev, "participants", None)
        if isinstance(participants, list):
            return [str(p) for p in participants]
        tags = ev.tags or []
        return [t for t in tags if t and not t.startswith("#")]
