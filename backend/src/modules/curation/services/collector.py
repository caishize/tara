"""Data collection methods for the curation service.

Contains _collect_raw_events, _get_members_with_locations,
_get_relevant_memories, _get_important_dates_in_range, and
helper methods for time parsing.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from uuid import UUID

from sqlalchemy import select, and_, or_

from ....config.logging import get_logger
from ....core.utils.timezone import local_today, get_user_timezone
from ..models import CuratedEvent, EventAssociation
from ...date_manager.models import ImportantDate
from ...member.models import Member
from ...memory.models import ConversationMemory, MemoryType, MemoryStatus
from .data_models import RawEvent
from .prompts import SYSTEM_HOLIDAY_FAMILY_ID, MEMORY_QUERY_LIMIT
from .date_occurrence_utils import calculate_next_occurrence
from .event_type_utils import map_important_date_type, normalize_event_type
from .association_text import build_person_context_map

logger = get_logger(__name__)


class CurationCollectorMixin:
    """Mixin providing data collection methods for SecretaryCurationService."""

    async def _collect_raw_events(
        self,
        family_id: UUID,
        date_range: Tuple[date, date],
    ) -> List[RawEvent]:
        """
        从多个数据源收集原始事件。

        Sources:
        - TripPlan
        - ImportantDate
        - ConversationMemory (schedule type)
        """
        from ...trip.models.trip_plan import TripPlan

        start_date, end_date = date_range
        raw_events = []
        source_health = {
            "trip_plan": True,
            "important_date": True,
            "extracted_schedule": True,
        }

        # 1. Travel Plans
        try:
            travel_stmt = select(TripPlan).where(
                and_(
                    TripPlan.family_id == family_id,
                    TripPlan.start_date <= end_date,
                    TripPlan.end_date >= start_date,
                    TripPlan.canonical_trip_id.is_(None),
                    TripPlan.is_active.is_(True),
                    TripPlan.status.in_(["planning", "confirmed", "in_progress"]),
                )
            )
            async with self.session.begin_nested():
                travel_result = await self.session.execute(travel_stmt)
                travels = list(travel_result.scalars().all())
                deduped_travels = await self._dedup_overlapping_trips(travels)

            for travel in deduped_travels:
                event_type = "business_trip" if travel.category == "business" else "travel"
                user_tz = get_user_timezone()
                raw_events.append(RawEvent(
                    id=str(travel.trip_id),
                    source_type="trip_plan",
                    title=travel.trip_name or f"{travel.destination}行程",
                    start_time=datetime.combine(travel.start_date, datetime.min.time(), tzinfo=user_tz),
                    end_time=datetime.combine(travel.end_date, datetime.max.time(), tzinfo=user_tz),
                    location=travel.destination,
                    description=travel.notes,
                    event_type=event_type,
                    participants=[str(p) for p in (travel.participants or [])],
                ))
        except Exception as e:
            logger.error(f"Error collecting travel plans: {e}")
            source_health["trip_plan"] = False

        # 2. Important Dates (user's family + system holidays)
        try:
            date_stmt = select(ImportantDate).where(
                or_(
                    ImportantDate.family_id == family_id,
                    ImportantDate.family_id == SYSTEM_HOLIDAY_FAMILY_ID,
                )
            )
            async with self.session.begin_nested():
                date_result = await self.session.execute(date_stmt)
                dates = list(date_result.scalars().all())

            seen_recurring_titles: Dict[str, Tuple[date, RawEvent]] = {}

            for imp_date in dates:
                next_occurrence = self._calculate_next_occurrence(
                    imp_date, start_date, end_date
                )
                if next_occurrence:
                    event_type = self._map_date_type(imp_date.date_type)
                    raw_event = RawEvent(
                        id=str(imp_date.id),
                        source_type="important_date",
                        title=imp_date.title,
                        start_time=datetime.combine(next_occurrence, datetime.min.time(), tzinfo=get_user_timezone()),
                        event_type=event_type,
                        description=imp_date.notes,
                    )

                    if imp_date.is_recurring:
                        existing = seen_recurring_titles.get(imp_date.title)
                        if existing is not None:
                            existing_date, existing_event = existing
                            if next_occurrence >= existing_date:
                                continue
                            if existing_event in raw_events:
                                raw_events.remove(existing_event)
                        seen_recurring_titles[imp_date.title] = (next_occurrence, raw_event)

                    raw_events.append(raw_event)
        except Exception as e:
            logger.error(f"Error collecting important dates: {e}")
            source_health["important_date"] = False

        # 3. Schedule memories from conversations
        try:
            memory_stmt = select(ConversationMemory).where(
                and_(
                    ConversationMemory.family_id == family_id,
                    ConversationMemory.memory_type == MemoryType.SCHEDULE.value,
                    ConversationMemory.status == MemoryStatus.ACTIVE.value,
                )
            )
            async with self.session.begin_nested():
                memory_result = await self.session.execute(memory_stmt)
                memories = list(memory_result.scalars().all())

            for memory in memories:
                entities = memory.entities or {}
                time_hint = entities.get("time_hint")
                location = entities.get("location")
                event_type = normalize_event_type(
                    entities.get("event_type"),
                    default="appointment",
                )

                event_time = self._parse_time_hint(time_hint, start_date, end_date)
                if event_time:
                    raw_events.append(RawEvent(
                        id=str(memory.id),
                        source_type="extracted_schedule",
                        title=memory.summary,
                        start_time=event_time,
                        location=location,
                        description=memory.content,
                        event_type=event_type,
                    ))
        except Exception as e:
            logger.error(f"Error collecting schedule memories: {e}")
            source_health["extracted_schedule"] = False

        logger.info(f"Collected {len(raw_events)} raw events for family {family_id}")
        self._last_collection_source_health = source_health
        return raw_events

    def _calculate_next_occurrence(
        self,
        imp_date: ImportantDate,
        start_date: date,
        end_date: date,
    ) -> Optional[date]:
        """Calculate next occurrence of an important date in range."""
        return calculate_next_occurrence(imp_date, start_date, end_date)

    def _map_date_type(self, date_type: str) -> str:
        """Map date-manager types into normalized curated event types."""
        return map_important_date_type(date_type)

    # Chinese weekday names mapped to Python weekday (0=Mon, 6=Sun)
    _WEEKDAY_MAP = {
        "一": 0, "二": 1, "三": 2, "四": 3,
        "五": 4, "六": 5, "日": 6, "天": 6,
    }

    def _parse_time_hint(
        self,
        time_hint: Optional[str],
        start_date: date,
        end_date: date,
    ) -> Optional[datetime]:
        """Parse a time hint string into datetime."""
        if not time_hint:
            return None

        today = local_today()

        if "明天" in time_hint:
            target = today + timedelta(days=1)
        elif "后天" in time_hint:
            target = today + timedelta(days=2)
        elif "下周" in time_hint:
            target = self._resolve_next_weekday(time_hint, today)
        elif "下个月" in time_hint:
            if today.month == 12:
                target = date(today.year + 1, 1, 1)
            else:
                target = date(today.year, today.month + 1, 1)
        else:
            return None

        if start_date <= target <= end_date:
            return datetime.combine(target, datetime.min.time(), tzinfo=get_user_timezone())
        return None

    def _resolve_next_weekday(self, hint: str, today: date) -> date:
        """Resolve '下周X' to the actual date of next week's weekday."""
        target_weekday = 0  # default: Monday
        for char, wd in self._WEEKDAY_MAP.items():
            if f"下周{char}" in hint:
                target_weekday = wd
                break

        days_to_next_monday = (7 - today.weekday()) % 7
        if days_to_next_monday == 0:
            days_to_next_monday = 7

        return today + timedelta(days=days_to_next_monday + target_weekday)

    async def _get_members_with_locations(
        self,
        family_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """Get family members with their locations."""
        stmt = select(Member).where(and_(
            Member.family_id == family_id,
            Member.is_deleted == False,
        ))
        result = await self.session.execute(stmt)
        members = result.scalars().all()

        member_context = await build_person_context_map(
            self.session,
            family_id=family_id,
            user_id=user_id,
            person_ids=[str(member.id) for member in members],
        )

        result_members = []
        for m in members:
            # Skip the trip creator — no need to suggest "meet yourself"
            if user_id and m.id == user_id:
                continue

            location = m.primary_location or m.address

            if location:
                person_ctx = member_context.get(str(m.id))
                relation_type = person_ctx.relation_type if person_ctx else None
                result_members.append({
                    "id": str(m.id),
                    "name": m.name,
                    "location": location,
                    "relationship": relation_type or (
                        getattr(m, "tags", [None])[0] if m.tags else None
                    ),
                    "relation_type": relation_type,
                    "is_family": person_ctx.is_family if person_ctx else None,
                    "co_resident": person_ctx.co_resident if person_ctx else False,
                })

        return result_members

    async def _get_relevant_memories(
        self,
        family_id: UUID,
        curated_events: List[CuratedEvent],
    ) -> List[Dict[str, Any]]:
        """Get memories relevant to the curated events.

        Excludes memories that have already been "fulfilled".
        """
        from sqlalchemy import cast, String as SAString

        fulfilled_memory_ids = (
            select(EventAssociation.target_id)
            .join(CuratedEvent, EventAssociation.source_event_id == CuratedEvent.id)
            .where(
                and_(
                    EventAssociation.family_id == family_id,
                    EventAssociation.target_type == "memory",
                    EventAssociation.is_confirmed.is_(True),
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.status != "cancelled",
                )
            )
        )

        stmt = select(ConversationMemory).where(
            and_(
                ConversationMemory.family_id == family_id,
                ConversationMemory.status == MemoryStatus.ACTIVE.value,
                ConversationMemory.memory_type.in_([
                    MemoryType.PLAN.value,
                    MemoryType.RELATIONSHIP.value,
                    MemoryType.LOCATION.value,
                    MemoryType.PREFERENCE.value,
                    MemoryType.HEALTH.value,
                ]),
                ~cast(ConversationMemory.id, SAString).in_(fulfilled_memory_ids),
            )
        ).limit(MEMORY_QUERY_LIMIT)

        result = await self.session.execute(stmt)
        memories = result.scalars().all()

        return [
            {
                "id": str(m.id),
                "type": m.memory_type,
                "summary": m.summary,
                "entities": m.entities,
            }
            for m in memories
        ]

    async def _get_important_dates_in_range(
        self,
        family_id: UUID,
        date_range: Tuple[date, date],
    ) -> List[Dict[str, Any]]:
        """Get important dates in the date range (user's + system holidays)."""
        start_date, end_date = date_range

        stmt = select(ImportantDate).where(
            or_(
                ImportantDate.family_id == family_id,
                ImportantDate.family_id == SYSTEM_HOLIDAY_FAMILY_ID,
            )
        )
        result = await self.session.execute(stmt)
        dates = result.scalars().all()

        seen_recurring: Dict[str, Tuple[date, int]] = {}
        result_dates = []

        for imp_date in dates:
            occurrence = self._calculate_next_occurrence(imp_date, start_date, end_date)
            if not occurrence:
                continue

            entry = {
                "id": str(imp_date.id),
                "title": imp_date.title,
                "date": occurrence.isoformat(),
                "type": imp_date.date_type,
                "member_id": str(imp_date.member_id) if imp_date.member_id else None,
            }

            if imp_date.is_recurring:
                prev = seen_recurring.get(imp_date.title)
                if prev is not None:
                    prev_date, prev_idx = prev
                    if occurrence >= prev_date:
                        continue
                    result_dates[prev_idx] = entry
                    seen_recurring[imp_date.title] = (occurrence, prev_idx)
                    continue
                seen_recurring[imp_date.title] = (occurrence, len(result_dates))

            result_dates.append(entry)

        return result_dates
