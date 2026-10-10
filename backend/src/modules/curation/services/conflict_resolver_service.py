"""
Conflict Resolver Service

Handles conflict detection and resolution for curated events.
Provides multiple resolution options with impact analysis.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..models import CuratedEvent, EventAssociation
from .conflict_detection import detect_conflicts


class ResolutionOption(BaseModel):
    """Conflict resolution option."""

    type: str = Field(
        description="Resolution type: adjust_time, cancel, merge"
    )
    target_event_id: UUID = Field(
        description="Event ID that needs adjustment"
    )
    new_start_time: Optional[datetime] = Field(
        default=None,
        description="New start time (for adjust_time type)"
    )
    new_end_time: Optional[datetime] = Field(
        default=None,
        description="New end time (for adjust_time type)"
    )
    reason: str = Field(
        description="Reason for this adjustment"
    )
    impact_analysis: str = Field(
        description="Impact analysis of this adjustment"
    )
    score: float = Field(
        default=0.0,
        description="Recommendation score (0-1)"
    )


class ConflictResolver:
    """Conflict resolution service.

    Analyzes conflicts and generates multiple resolution options
    with impact analysis and scoring.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve_conflict(
        self,
        event1: CuratedEvent,
        event2: CuratedEvent,
        family_id: UUID,
    ) -> List[ResolutionOption]:
        """Generate multiple conflict resolution options."""
        options = []

        adj1 = self._analyze_adjustability(event1)
        adj2 = self._analyze_adjustability(event2)

        if adj1 in ["flexible", "soft_constraint"]:
            options.extend(await self._generate_adjustment_options(
                event1, event2, adjust_event=event1, family_id=family_id
            ))

        if adj2 in ["flexible", "soft_constraint"]:
            options.extend(await self._generate_adjustment_options(
                event1, event2, adjust_event=event2, family_id=family_id
            ))

        if adj1 != "hard_constraint":
            cancel_option = await self._generate_cancellation_option(
                event1, event2, cancel_event=event1
            )
            if cancel_option:
                options.append(cancel_option)

        if adj2 != "hard_constraint":
            cancel_option = await self._generate_cancellation_option(
                event1, event2, cancel_event=event2
            )
            if cancel_option:
                options.append(cancel_option)

        for option in options:
            option.score = await self._calculate_resolution_score(
                option, event1, event2
            )

        options.sort(key=lambda x: x.score, reverse=True)

        return options[:3]

    def _analyze_adjustability(self, event: CuratedEvent) -> str:
        """Analyze event adjustability.

        Returns:
            "hard_constraint", "soft_constraint", or "flexible"
        """
        if event.event_type in ["travel", "flight", "train"]:
            if event.status == "confirmed":
                return "hard_constraint"
            return "soft_constraint"

        if event.event_type in ["meeting", "appointment"]:
            if event.status == "confirmed":
                return "hard_constraint"
            return "soft_constraint"

        if event.event_type in ["birthday", "anniversary"]:
            return "hard_constraint"

        if event.priority in ["critical", "high"]:
            return "soft_constraint"

        return "flexible"

    async def _generate_adjustment_options(
        self,
        event1: CuratedEvent,
        event2: CuratedEvent,
        adjust_event: CuratedEvent,
        family_id: UUID,
    ) -> List[ResolutionOption]:
        """Generate time adjustment options."""
        options = []
        anchor_event = event1 if adjust_event.id == event2.id else event2

        before_time = anchor_event.normalized_start - timedelta(hours=2)
        if await self._check_no_new_conflicts(
            adjust_event, before_time, family_id
        ):
            duration = self._get_event_duration(adjust_event)
            options.append(ResolutionOption(
                type="adjust_time",
                target_event_id=adjust_event.id,
                new_start_time=before_time,
                new_end_time=before_time + duration if duration else None,
                reason=f"\u5c06{adjust_event.title}\u8c03\u6574\u5230{anchor_event.title}\u4e4b\u524d",
                impact_analysis=await self._analyze_impact(
                    adjust_event, before_time, family_id
                ),
            ))

        anchor_end = anchor_event.normalized_end or (
            anchor_event.normalized_start + timedelta(hours=1)
        )
        after_time = anchor_end + timedelta(hours=1)
        if await self._check_no_new_conflicts(
            adjust_event, after_time, family_id
        ):
            duration = self._get_event_duration(adjust_event)
            options.append(ResolutionOption(
                type="adjust_time",
                target_event_id=adjust_event.id,
                new_start_time=after_time,
                new_end_time=after_time + duration if duration else None,
                reason=f"\u5c06{adjust_event.title}\u8c03\u6574\u5230{anchor_event.title}\u4e4b\u540e",
                impact_analysis=await self._analyze_impact(
                    adjust_event, after_time, family_id
                ),
            ))

        next_day = anchor_event.normalized_start.replace(
            hour=9, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        if await self._check_no_new_conflicts(
            adjust_event, next_day, family_id
        ):
            duration = self._get_event_duration(adjust_event)
            options.append(ResolutionOption(
                type="adjust_time",
                target_event_id=adjust_event.id,
                new_start_time=next_day,
                new_end_time=next_day + duration if duration else None,
                reason=f"\u5c06{adjust_event.title}\u63a8\u8fdf\u5230\u7b2c\u4e8c\u5929",
                impact_analysis=await self._analyze_impact(
                    adjust_event, next_day, family_id
                ),
            ))

        return options

    async def _generate_cancellation_option(
        self,
        event1: CuratedEvent,
        event2: CuratedEvent,
        cancel_event: CuratedEvent,
    ) -> Optional[ResolutionOption]:
        """Generate cancellation option."""
        keep_event = event1 if cancel_event.id == event2.id else event2

        if cancel_event.priority in ["low", "normal"]:
            return ResolutionOption(
                type="cancel",
                target_event_id=cancel_event.id,
                reason=f"\u53d6\u6d88{cancel_event.title}\uff0c\u4fdd\u7559{keep_event.title}",
                impact_analysis=f"\u53d6\u6d88\u4f18\u5148\u7ea7\u8f83\u4f4e\u7684\u4e8b\u4ef6\uff0c\u4fdd\u7559\u66f4\u91cd\u8981\u7684{keep_event.title}",
            )

        return None

    async def _check_no_new_conflicts(
        self,
        event: CuratedEvent,
        new_time: datetime,
        family_id: UUID,
    ) -> bool:
        """Check if adjustment would create new conflicts."""
        duration = self._get_event_duration(event)
        virtual_event = CuratedEvent(
            id=event.id,
            family_id=family_id,
            title=event.title,
            normalized_start=new_time,
            normalized_end=new_time + duration if duration else None,
            event_type=event.event_type,
            status=event.status,
            priority=event.priority,
        )

        conflicts = await detect_conflicts(
            self.session,
            family_id,
            virtual_event,
            exclude_event_ids={event.id},
            read_only=True,
        )

        return len(conflicts) == 0

    async def _analyze_impact(
        self,
        event: CuratedEvent,
        new_time: datetime,
        family_id: UUID,
    ) -> str:
        """Analyze impact of time adjustment."""
        impacts = []

        time_diff = new_time - event.normalized_start
        if time_diff.days > 0:
            impacts.append(f"\u63a8\u8fdf{time_diff.days}\u5929")
        elif time_diff.days < 0:
            impacts.append(f"\u63d0\u524d{abs(time_diff.days)}\u5929")
        elif time_diff.total_seconds() / 3600 > 2:
            hours = int(time_diff.total_seconds() / 3600)
            impacts.append(f"\u63a8\u8fdf{hours}\u5c0f\u65f6")
        elif time_diff.total_seconds() / 3600 < -2:
            hours = int(abs(time_diff.total_seconds() / 3600))
            impacts.append(f"\u63d0\u524d{hours}\u5c0f\u65f6")

        associations = await self._get_event_associations(event.id)
        if associations:
            impacts.append(f"\u5f71\u54cd{len(associations)}\u4e2a\u5173\u8054\u4e8b\u9879")

        if event.trip_id:
            trip_events = await self._get_trip_events(event.trip_id, family_id)
            if len(trip_events) > 1:
                impacts.append(f"\u5f71\u54cd\u6574\u4e2a\u884c\u7a0b\uff08\u5171{len(trip_events)}\u4e2a\u4e8b\u4ef6\uff09")

        return "\uff1b".join(impacts) if impacts else "\u65e0\u660e\u663e\u5f71\u54cd"

    async def _calculate_resolution_score(
        self,
        option: ResolutionOption,
        event1: CuratedEvent,
        event2: CuratedEvent,
    ) -> float:
        """Calculate resolution option score."""
        score = 1.0

        target_event = event1 if option.target_event_id == event1.id else event2

        priority_scores = {
            "low": 1.0,
            "normal": 0.8,
            "high": 0.6,
            "critical": 0.5,
        }
        score *= priority_scores.get(target_event.priority, 0.8)

        adj = self._analyze_adjustability(target_event)
        adj_scores = {
            "flexible": 1.0,
            "soft_constraint": 0.85,
            "hard_constraint": 0.7,
        }
        score *= adj_scores.get(adj, 0.85)

        if option.type == "cancel":
            score *= 0.7

        if option.new_start_time:
            time_diff = abs(
                (option.new_start_time - target_event.normalized_start).total_seconds()
            )
            hours_diff = time_diff / 3600
            if hours_diff < 2:
                score *= 1.0
            elif hours_diff < 24:
                score *= 0.9
            else:
                score *= 0.8

        return min(score, 1.0)

    def _get_event_duration(self, event: CuratedEvent) -> timedelta:
        """Get event duration."""
        if event.normalized_end:
            return event.normalized_end - event.normalized_start
        return timedelta(hours=1)

    async def _get_event_associations(
        self, event_id: UUID
    ) -> List[EventAssociation]:
        """Get event associations."""
        stmt = select(EventAssociation).where(
            EventAssociation.source_event_id == event_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_trip_events(
        self, trip_id: UUID, family_id: UUID
    ) -> List[CuratedEvent]:
        """Get all events in a trip."""
        stmt = select(CuratedEvent).where(
            and_(
                CuratedEvent.trip_id == trip_id,
                CuratedEvent.family_id == family_id,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def generate_unresolvable_explanation(
        self,
        event1: CuratedEvent,
        event2: CuratedEvent,
    ) -> str:
        """Generate explanation for unresolvable conflicts."""
        adj1 = self._analyze_adjustability(event1)
        adj2 = self._analyze_adjustability(event2)

        reasons = []

        if adj1 == "hard_constraint" and adj2 == "hard_constraint":
            reasons.append("\u4e24\u4e2a\u4e8b\u4ef6\u90fd\u662f\u786c\u7ea6\u675f\uff0c\u65e0\u6cd5\u81ea\u52a8\u8c03\u6574")
            reasons.append(f"- {event1.title}: {self._explain_hard_constraint(event1)}")
            reasons.append(f"- {event2.title}: {self._explain_hard_constraint(event2)}")
            reasons.append("\n\u9700\u8981\u60a8\u51b3\u5b9a\uff1a\u4fdd\u7559\u54ea\u4e2a\u4e8b\u4ef6\uff0c\u6216\u624b\u52a8\u8c03\u6574\u65f6\u95f4")
        elif adj1 == "hard_constraint":
            reasons.append(f"{event1.title}\u662f\u786c\u7ea6\u675f\uff0c\u65e0\u6cd5\u8c03\u6574")
            reasons.append(f"\u539f\u56e0\uff1a{self._explain_hard_constraint(event1)}")
            reasons.append(f"\n\u5efa\u8bae\uff1a\u8c03\u6574\u6216\u53d6\u6d88{event2.title}")
        elif adj2 == "hard_constraint":
            reasons.append(f"{event2.title}\u662f\u786c\u7ea6\u675f\uff0c\u65e0\u6cd5\u8c03\u6574")
            reasons.append(f"\u539f\u56e0\uff1a{self._explain_hard_constraint(event2)}")
            reasons.append(f"\n\u5efa\u8bae\uff1a\u8c03\u6574\u6216\u53d6\u6d88{event1.title}")
        else:
            reasons.append("\u8c03\u6574\u4efb\u4e00\u4e8b\u4ef6\u90fd\u4f1a\u4ea7\u751f\u65b0\u7684\u51b2\u7a81")
            reasons.append("\n\u9700\u8981\u60a8\u624b\u52a8\u534f\u8c03\u65f6\u95f4\u5b89\u6392")

        return "\n".join(reasons)

    def _explain_hard_constraint(self, event: CuratedEvent) -> str:
        """Explain why event is a hard constraint."""
        if event.event_type in ["travel", "flight", "train"]:
            return "\u4ea4\u901a\u5de5\u5177\u65f6\u95f4\u56fa\u5b9a"
        if event.event_type in ["meeting", "appointment"]:
            if event.status == "confirmed":
                return "\u5df2\u786e\u8ba4\u7684\u4f1a\u8bae/\u9884\u7ea6"
            return "\u91cd\u8981\u4f1a\u8bae"
        if event.event_type in ["birthday", "anniversary"]:
            return "\u91cd\u8981\u65e5\u671f\u4e0d\u53ef\u66f4\u6539"
        if event.priority == "critical":
            return "\u5173\u952e\u4f18\u5148\u7ea7\u4e8b\u4ef6"
        return "\u65f6\u95f4\u56fa\u5b9a\u7684\u4e8b\u4ef6"
