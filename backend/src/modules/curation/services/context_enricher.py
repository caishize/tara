"""
Context Enricher Service

Enriches events with background information, historical context, and decision support.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.utils.timezone import utc_now
from ..models import CuratedEvent, EventAssociation
from ...member.models import Member
from ...memory.models import ConversationMemory
from .memory_engine import MemoryEngine


class EventContext(BaseModel):
    """Event context with enriched information"""

    source_info: Dict[str, Any] = Field(default_factory=dict)
    source_summary: str = Field(default="")
    historical_events: List[Dict[str, Any]] = Field(default_factory=list)
    historical_summary: Optional[str] = Field(default=None)
    related_people: List[Dict[str, Any]] = Field(default_factory=list)
    people_summary: Optional[str] = Field(default=None)
    related_events: List[str] = Field(default_factory=list)
    event_chain_summary: Optional[str] = Field(default=None)
    priority_reason: Optional[str] = Field(default=None)
    adjustability: str = Field(default="flexible")
    adjustability_reason: Optional[str] = Field(default=None)


class ContextEnricher:
    """Enriches events with context and background information"""

    def __init__(self, session: AsyncSession, memory_engine: MemoryEngine):
        self.session = session
        self.memory_engine = memory_engine

    async def enrich_event(
        self,
        event: CuratedEvent,
        family_id: UUID,
    ) -> EventContext:
        """Enrich event with complete context information"""
        context = EventContext(source_info={})

        context.source_info = await self._extract_source_info(event)
        context.source_summary = self._generate_source_summary(context.source_info)

        if event.location:
            context.historical_events = await self._find_historical_events(
                family_id, event.location, limit=5
            )
            context.historical_summary = await self._generate_historical_summary(
                context.historical_events
            )

        context.related_people = await self._find_related_people(
            family_id, event
        )
        context.people_summary = await self._generate_people_summary(
            context.related_people
        )

        context.related_events = await self._find_event_chain(event)
        context.event_chain_summary = await self._generate_event_chain_summary(
            context.related_events
        )

        context.priority_reason = self._analyze_priority(event)
        context.adjustability = self._analyze_adjustability(event)
        context.adjustability_reason = self._explain_adjustability(
            event, context.adjustability
        )

        return context

    async def _extract_source_info(self, event: CuratedEvent) -> Dict[str, Any]:
        """Extract source information from event"""
        source_info = {}

        if event.original_event_ids:
            source_info["original_event_ids"] = event.original_event_ids

            if "conversation" in str(event.original_event_ids).lower():
                source_info["source_type"] = "conversation"
            elif "travel" in str(event.original_event_ids).lower():
                source_info["source_type"] = "trip_plan"
            else:
                source_info["source_type"] = "unknown"

        if event.metadata:
            if "source" in event.metadata:
                source_info["metadata_source"] = event.metadata["source"]
            if "conversation_id" in event.metadata:
                source_info["conversation_id"] = event.metadata["conversation_id"]

        return source_info

    def _generate_source_summary(self, source_info: Dict[str, Any]) -> str:
        """Generate human-readable source summary"""
        if not source_info:
            return "\u6765\u6e90\u4fe1\u606f\u4e0d\u53ef\u7528"

        source_type = source_info.get("source_type", "unknown")

        if source_type == "conversation":
            return "\u6765\u81ea\u4e0e\u52a9\u624b\u7684\u5bf9\u8bdd"
        elif source_type == "trip_plan":
            return "\u6765\u81ea\u65c5\u884c\u8ba1\u5212"
        else:
            return "\u6765\u81ea\u7cfb\u7edf\u8bb0\u5f55"

    async def _find_historical_events(
        self,
        family_id: UUID,
        location: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find historical events in the same location"""
        now = utc_now()
        six_months_ago = now - timedelta(days=180)

        stmt = (
            select(CuratedEvent)
            .where(
                and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.location == location,
                    CuratedEvent.normalized_start < now,
                    CuratedEvent.normalized_start >= six_months_ago,
                )
            )
            .order_by(CuratedEvent.normalized_start.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        events = result.scalars().all()

        return [
            {
                "id": str(event.id),
                "title": event.title,
                "location": event.location,
                "date": event.normalized_start.date().isoformat() if event.normalized_start else None,
                "event_type": event.event_type,
            }
            for event in events
        ]

    async def _generate_historical_summary(
        self,
        historical_events: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Generate summary of historical events"""
        if not historical_events:
            return None

        if len(historical_events) == 1:
            event = historical_events[0]
            loc = event.get("location", "那边")
            title = event.get("title", "相关活动")
            return f"上次去{loc}是因为{title}，这次可以留意一下"

        location = historical_events[0].get("location", "那边")
        count = len(historical_events)
        return f"过去半年去了{location} {count}次，算是常去的地方了"

    async def _find_related_people(
        self,
        family_id: UUID,
        event: CuratedEvent
    ) -> List[Dict[str, Any]]:
        """Find people related to this event"""
        related_people = []

        if event.location:
            stmt = (
                select(Member)
                .where(
                    and_(
                        Member.family_id == family_id,
                        Member.locations.isnot(None),
                    )
                )
                .limit(50)
            )

            result = await self.session.execute(stmt)
            members = result.scalars().all()

            for member in members:
                member_loc = member.primary_location
                if member_loc and (
                    event.location in member_loc or member_loc in event.location
                ):
                    related_people.append({
                        "id": str(member.id),
                        "name": member.name,
                        "location": member_loc,
                    })
                if len(related_people) >= 10:
                    break

        return related_people

    async def _generate_people_summary(
        self,
        related_people: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Generate summary of related people"""
        if not related_people:
            return None

        if len(related_people) == 1:
            person = related_people[0]
            name = person.get("name", "联系人")
            return f"{name}在此地"

        names = [p.get("name", "") for p in related_people[:3]]
        joined = ", ".join(names)
        if len(related_people) > 3:
            total = len(related_people)
            return f"{joined}等{total}位联系人在此地"
        else:
            return f"{joined}在此地"

    async def _find_event_chain(self, event: CuratedEvent) -> List[str]:
        """Find events in the same chain (trip or project)"""
        related_event_ids = []

        if event.trip_id:
            stmt = (
                select(CuratedEvent.id)
                .where(
                    and_(
                        CuratedEvent.trip_id == event.trip_id,
                        CuratedEvent.id != event.id,
                    )
                )
            )

            result = await self.session.execute(stmt)
            trip_event_ids = result.scalars().all()
            related_event_ids.extend([str(eid) for eid in trip_event_ids])

        return related_event_ids

    async def _generate_event_chain_summary(
        self,
        related_events: List[str]
    ) -> Optional[str]:
        """Generate summary of event chain"""
        if not related_events:
            return None

        count = len(related_events)
        if count == 1:
            return "此事件是行程的一部分"
        else:
            total = count + 1
            return f"此事件是包含{total}个活动的行程的一部分"

    def _analyze_priority(self, event: CuratedEvent) -> str:
        """Analyze why this event has its priority"""
        priority = event.priority or "normal"

        reasons = []

        if event.event_type == "meeting":
            reasons.append("\u91cd\u8981\u4f1a\u8bae")
        elif event.event_type == "travel":
            reasons.append("\u51fa\u884c\u5b89\u6392")
        elif event.event_type == "appointment":
            reasons.append("\u9884\u7ea6\u4e8b\u9879")

        if event.status == "confirmed":
            reasons.append("\u5df2\u786e\u8ba4")

        if not reasons:
            if priority == "high":
                return "\u9ad8\u4f18\u5148\u7ea7\u4e8b\u9879"
            elif priority == "critical":
                return "\u7d27\u6025\u91cd\u8981\u4e8b\u9879"
            else:
                return "\u5e38\u89c4\u4e8b\u9879"

        return "\u3001".join(reasons)

    def _analyze_adjustability(self, event: CuratedEvent) -> str:
        """Analyze event adjustability"""
        if event.event_type in ["travel", "flight"]:
            if event.status == "confirmed":
                return "hard_constraint"
            return "soft_constraint"

        if event.event_type == "meeting":
            if event.status == "confirmed":
                return "hard_constraint"
            return "soft_constraint"

        if event.event_type == "appointment":
            return "soft_constraint"

        if event.event_type in ["birthday", "anniversary"]:
            return "hard_constraint"

        return "flexible"

    def _explain_adjustability(
        self,
        event: CuratedEvent,
        adjustability: str
    ) -> str:
        """Explain why event has this adjustability"""
        if adjustability == "hard_constraint":
            if event.event_type == "travel":
                return "\u822a\u73ed/\u706b\u8f66\u7968\u5df2\u786e\u8ba4\uff0c\u65f6\u95f4\u56fa\u5b9a"
            elif event.event_type == "meeting":
                return "\u4f1a\u8bae\u5df2\u786e\u8ba4\uff0c\u6d89\u53ca\u591a\u65b9\uff0c\u96be\u4ee5\u8c03\u6574"
            elif event.event_type in ["birthday", "anniversary"]:
                return "\u91cd\u8981\u65e5\u671f\uff0c\u4e0d\u53ef\u66f4\u6539"
            else:
                return "\u65f6\u95f4\u56fa\u5b9a\uff0c\u4e0d\u53ef\u8c03\u6574"

        elif adjustability == "soft_constraint":
            if event.status == "tentative":
                return "\u5c1a\u672a\u6700\u7ec8\u786e\u8ba4\uff0c\u53ef\u4ee5\u534f\u5546\u8c03\u6574"
            else:
                return "\u53ef\u4ee5\u534f\u5546\u8c03\u6574\u65f6\u95f4"

        else:
            return "\u65f6\u95f4\u7075\u6d3b\uff0c\u53ef\u4ee5\u6839\u636e\u9700\u8981\u8c03\u6574"
