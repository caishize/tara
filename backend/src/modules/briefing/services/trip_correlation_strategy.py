"""TripCorrelationStrategy -- Scenario 6 "Wow" moment recommendations.

When a user has an upcoming trip or business_trip event, this strategy
checks if any family members (or contacts) live near the destination.
It also looks up favor memories and preferences to compose contextual
recommendations.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger

if TYPE_CHECKING:
    from .recommendation_engine import RecommendationContext

logger = get_logger(__name__)


class TripCorrelationStrategy:
    """Generate recommendations based on trip-member location correlations.

    When a user has an upcoming trip or business_trip event, this strategy
    checks if any family members (or contacts) live near the destination.
    It also looks up favor memories and preferences to compose contextual
    recommendations like:

        "你到深圳了。小王住在那附近。上次他帮你搬家，要不要约他吃个饭？"
    """

    _TRIP_EVENT_TYPES = frozenset({"travel", "business_trip"})

    def __init__(self, db: AsyncSession):
        self._db = db

    @property
    def strategy_name(self) -> str:
        return "trip_correlation"

    async def generate(
        self,
        user_id: UUID,
        family_id: UUID,
        context: RecommendationContext,
    ) -> List[Any]:
        from .recommendation_engine import Recommendation

        try:
            return await self._generate_impl(user_id, family_id, context)
        except Exception:
            logger.warning(
                "TripCorrelationStrategy failed for user=%s", user_id,
                exc_info=True,
            )
            return []

    async def _generate_impl(
        self,
        user_id: UUID,
        family_id: UUID,
        context: RecommendationContext,
    ) -> List[Any]:
        from datetime import time as dt_time

        from sqlalchemy import select, and_

        from ...curation.models import CuratedEvent
        from ...member.models import Member
        from .recommendation_engine import Recommendation

        # Step 1: Find upcoming trip/business_trip events within 7 days
        target = context.target_date
        window_end = target + timedelta(days=7)

        window_start_dt = datetime.combine(target, dt_time.min)
        window_end_dt = datetime.combine(window_end, dt_time.max)

        trip_stmt = (
            select(CuratedEvent)
            .where(
                and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.event_type.in_(list(self._TRIP_EVENT_TYPES)),
                    CuratedEvent.normalized_start != None,  # noqa: E711
                    CuratedEvent.normalized_start >= window_start_dt,
                    CuratedEvent.normalized_start <= window_end_dt,
                    CuratedEvent.status.notin_(["cancelled", "completed"]),
                ),
            )
        )
        trip_result = await self._db.execute(trip_stmt)
        relevant_trips = list(trip_result.scalars().all())

        if not relevant_trips:
            return []

        # Step 2: Load all family members
        member_stmt = select(Member).where(Member.family_id == family_id)
        member_result = await self._db.execute(member_stmt)
        members = member_result.scalars().all()

        if not members:
            return []

        recommendations: List[Recommendation] = []

        for trip_ev in relevant_trips:
            destination = trip_ev.city or trip_ev.location
            if not destination:
                continue

            destination_lower = destination.lower()

            # Step 3: Find members whose primary_location matches destination
            matching_members = []
            for member in members:
                loc = member.primary_location
                if not loc:
                    continue
                if destination_lower in loc.lower() or loc.lower() in destination_lower:
                    matching_members.append(member)

            for member in matching_members:
                # Step 4: Look up favor memories for this member
                favor_context = await self._get_favor_context(
                    family_id, member.id,
                )
                preference_context = await self._get_preference_context(
                    family_id, member.id, member_name=member.name,
                )

                # Step 5: Compose recommendation
                suggestion = self._compose_suggestion(
                    member.name, preference_context,
                )
                favor_text = ""
                if favor_context:
                    favor_text = favor_context + "，"

                content = (
                    f"你到{destination}了。{member.name}住在那附近。"
                    f"{favor_text}{suggestion}"
                )

                recommendations.append(Recommendation(
                    id=uuid4(),
                    title=f"在{destination}可以见{member.name}",
                    content=content,
                    recommendation_type="trip_correlation",
                    priority=0.75,
                    source_strategy="trip_correlation",
                    metadata={
                        "trip_event_id": str(trip_ev.id),
                        "member_id": str(member.id),
                        "member_name": member.name,
                        "destination": destination,
                        "favor_context": favor_context or "",
                    },
                ))

        return recommendations

    async def _get_favor_context(
        self,
        family_id: UUID,
        member_id: UUID,
    ) -> Optional[str]:
        """Look up recent favor memories involving this member."""
        try:
            from sqlalchemy import select, and_

            from ...memory.models import ConversationMemory

            stmt = (
                select(ConversationMemory.content, ConversationMemory.entities)
                .where(
                    and_(
                        ConversationMemory.family_id == family_id,
                        ConversationMemory.memory_type == "favor",
                        ConversationMemory.status == "active",
                    ),
                )
                .order_by(ConversationMemory.created_at.desc())
                .limit(10)
            )
            result = await self._db.execute(stmt)
            rows = result.all()

            member_id_str = str(member_id)
            for content, entities in rows:
                if not entities or not isinstance(entities, dict):
                    continue
                related_ids = entities.get("related_member_ids", [])
                if member_id_str in [str(rid) for rid in related_ids]:
                    favor_dir = entities.get("favor_direction", "")
                    if favor_dir == "received":
                        return f"上次{content[:50]}"
                    elif favor_dir == "given":
                        return f"你之前帮过ta{content[:30]}"
            return None
        except Exception:
            logger.debug("Favor context lookup failed", exc_info=True)
            return None

    async def _get_preference_context(
        self,
        family_id: UUID,
        member_id: UUID,
        member_name: Optional[str] = None,
    ) -> Optional[str]:
        """Look up preference memories for this member.

        Matches via entities.related_member_ids (primary) or member name
        in content text (fallback).
        """
        try:
            from sqlalchemy import select, and_

            from ...memory.models import ConversationMemory

            stmt = (
                select(ConversationMemory.content, ConversationMemory.entities)
                .where(
                    and_(
                        ConversationMemory.family_id == family_id,
                        ConversationMemory.memory_type == "preference",
                        ConversationMemory.status == "active",
                    ),
                )
                .order_by(ConversationMemory.created_at.desc())
                .limit(10)
            )
            result = await self._db.execute(stmt)
            rows = result.all()

            member_id_str = str(member_id)
            for content, entities in rows:
                # Primary: match via entities JSONB related_member_ids
                if entities and isinstance(entities, dict):
                    related_ids = entities.get("related_member_ids", [])
                    if member_id_str in [str(rid) for rid in related_ids]:
                        return (content or "")[:80]

                # Fallback: match member name in content text
                if member_name and member_name in (content or ""):
                    return (content or "")[:80]

            return None
        except Exception:
            logger.debug("Preference context lookup failed", exc_info=True)
            return None

    @staticmethod
    def _compose_suggestion(
        member_name: str,
        preference_context: Optional[str],
    ) -> str:
        """Compose a contextual suggestion based on available info."""
        if preference_context:
            return f"要不要约{member_name}聚聚？"
        return f"要不要顺便见一面？"
