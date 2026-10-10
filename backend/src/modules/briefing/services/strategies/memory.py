"""Memory-based suggestion strategy — suggestions from conversation memories."""
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, and_, or_

from .....config.logging import get_logger
from .....core.utils.timezone import utc_now, local_today
from ....curation.services.query_utils import escape_like
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


class MemoryStrategy(SuggestionStrategy):
    """Find suggestions based on conversation memories."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        today = local_today()

        try:
            from ....memory.models import (
                ConversationMemory,
                MemoryType,
                MemoryStatus,
            )
            from ....trip.models.trip_plan import TripPlan

            trip_query = select(TripPlan).where(
                and_(
                    TripPlan.is_active.is_(True),
                    TripPlan.status.in_(["planning", "confirmed"]),
                    TripPlan.start_date >= today,
                    TripPlan.start_date <= today + timedelta(days=14),
                )
            )

            if family_id:
                trip_query = trip_query.where(TripPlan.family_id == family_id)

            trip_result = await self.db.execute(trip_query)
            trips = trip_result.scalars().all()

            for trip in trips:
                destination = trip.destination.lower()
                days_until = (trip.start_date - today).days

                # Only fetch memories created around this trip's planning
                # window to avoid stale memories from cancelled trips.
                trip_created = getattr(trip, "created_at", None)
                if trip_created is not None:
                    mem_cutoff = trip_created - timedelta(days=3)
                else:
                    mem_cutoff = utc_now() - timedelta(days=30)

                memory_query = select(ConversationMemory).where(
                    and_(
                        ConversationMemory.user_id == user_id,
                        ConversationMemory.status == MemoryStatus.ACTIVE.value,
                        ConversationMemory.memory_type.in_([
                            MemoryType.PLAN.value,
                            MemoryType.RELATIONSHIP.value,
                        ]),
                        ConversationMemory.created_at >= mem_cutoff,
                        or_(
                            ConversationMemory.summary.ilike(f"%{escape_like(destination)}%", escape="\\"),
                            ConversationMemory.entities["location"].astext.ilike(f"%{escape_like(destination)}%", escape="\\"),
                        ),
                    )
                ).limit(5)

                memory_result = await self.db.execute(memory_query)
                related_memories = memory_result.scalars().all()

                for mem in related_memories:
                    entities = mem.entities or {}
                    person = entities.get("person")

                    if person:
                        if days_until <= 3:
                            title = f"别忘了联系{person}"
                            content = f"您之前提到在{trip.destination}要找{person}，{days_until}天后就要出发了！"
                            priority = 85
                            urgency = "high"
                        else:
                            title = f"去{trip.destination}记得找{person}"
                            content = f"您提到过想在{trip.destination}见{person}，行程还有{days_until}天"
                            priority = 70
                            urgency = "normal"

                        suggestions.append(Suggestion(
                            type=SuggestionType.MEMORY_CORRELATION,
                            title=title,
                            content=content,
                            icon="lightbulb",
                            related_trip_ids=[str(trip.trip_id)],
                            action_options=["send_message", "schedule_meeting", "set_reminder", "ignore"],
                            action_data={
                                "trip_id": str(trip.trip_id),
                                "destination": trip.destination,
                                "person": person,
                                "memory_id": str(mem.id),
                                "memory_summary": mem.summary,
                            },
                            priority=priority,
                            urgency=urgency,
                            expires_at=datetime.combine(
                                trip.start_date + timedelta(days=1),
                                datetime.min.time(),
                            ),
                        ))
                    else:
                        suggestions.append(Suggestion(
                            type=SuggestionType.PLAN_REMINDER,
                            title=f"您在{trip.destination}的计划",
                            content=f"之前您提到：{mem.summary[:60]}...",
                            icon="event_note",
                            related_trip_ids=[str(trip.trip_id)],
                            action_options=["view_details", "set_reminder", "ignore"],
                            action_data={
                                "trip_id": str(trip.trip_id),
                                "destination": trip.destination,
                                "memory_id": str(mem.id),
                                "memory_summary": mem.summary,
                            },
                            priority=60,
                            urgency="normal",
                            expires_at=datetime.combine(
                                trip.start_date + timedelta(days=1),
                                datetime.min.time(),
                            ),
                        ))

            # Find old plan memories that might need follow-up
            two_weeks_ago = utc_now() - timedelta(days=14)
            old_plan_query = select(ConversationMemory).where(
                and_(
                    ConversationMemory.user_id == user_id,
                    ConversationMemory.status == MemoryStatus.ACTIVE.value,
                    ConversationMemory.memory_type == MemoryType.PLAN.value,
                    ConversationMemory.created_at < two_weeks_ago,
                )
            ).order_by(ConversationMemory.importance.desc()).limit(3)

            old_plan_result = await self.db.execute(old_plan_query)
            old_plans = old_plan_result.scalars().all()

            for plan in old_plans:
                entities = plan.entities or {}
                person = entities.get("person")
                location = entities.get("location")

                if person:
                    title = f"还记得要联系{person}吗？"
                    content = f"您之前提到想找{person}，这个计划还在进行吗？"
                elif location:
                    title = f"关于去{location}的计划"
                    content = f"您之前提到要去{location}，还有这个计划吗？"
                else:
                    title = "计划跟进"
                    content = f"之前您提到：{plan.summary[:50]}... 还在计划中吗？"

                suggestions.append(Suggestion(
                    type=SuggestionType.PLAN_REMINDER,
                    title=title,
                    content=content,
                    icon="help_outline",
                    action_options=["still_planning", "completed", "cancelled", "ignore"],
                    action_data={
                        "memory_id": str(plan.id),
                        "memory_summary": plan.summary,
                        "person": person,
                        "location": location,
                    },
                    priority=40,
                    urgency="low",
                ))

        except ImportError as e:
            logger.warning(f"Memory models not available: {e}")
        except Exception as e:
            logger.error(f"Error finding memory-based suggestions: {e}")

        return suggestions
