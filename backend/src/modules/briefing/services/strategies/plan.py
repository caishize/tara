"""Plan reminder strategy — follow up on user's expressed plans.

Generates PLAN_REMINDER suggestions when users have mentioned plans
(e.g. "日本樱花季快到了", "想带孩子去动物园") that are approaching or
have been idle for a while.
"""
from typing import List, Optional
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, and_

from .....config.logging import get_logger
from .....core.utils.timezone import utc_now
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


class PlanStrategy(SuggestionStrategy):
    """Generate plan follow-up reminders from conversation memories."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []

        try:
            from ....memory.models import (
                ConversationMemory,
                MemoryType,
                MemoryStatus,
            )

            # Find active plan/schedule memories
            plan_query = select(ConversationMemory).where(
                and_(
                    ConversationMemory.user_id == user_id,
                    ConversationMemory.memory_type.in_([
                        MemoryType.PLAN.value,
                        MemoryType.SCHEDULE.value,
                    ]),
                    ConversationMemory.status == MemoryStatus.ACTIVE.value,
                )
            ).order_by(
                ConversationMemory.importance.desc(),
                ConversationMemory.created_at.desc(),
            ).limit(10)

            result = await self.db.execute(plan_query)
            plan_memories = list(result.scalars().all())

            now = utc_now()

            for plan in plan_memories:
                entities = plan.entities or {}
                plan_date_str = entities.get("date") or entities.get("target_date")
                plan_location = entities.get("location", "")
                plan_person = entities.get("person", "")

                days_since_created = (now - plan.created_at).days

                # Plans with a date: remind as date approaches
                if plan_date_str:
                    try:
                        from datetime import date as date_type

                        parts = plan_date_str.split("-")
                        if len(parts) == 3:
                            plan_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
                            days_until = (plan_date - now.date()).days

                            if days_until < 0:
                                continue  # past plan
                            elif days_until <= 3:
                                title = "计划即将到来"
                                content = f"您之前提到的计划即将到来：{plan.summary}"
                                priority = 80
                                urgency = "high"
                            elif days_until <= 7:
                                title = "计划跟进提醒"
                                content = f"{plan.summary}还有{days_until}天，需要准备吗？"
                                priority = 65
                                urgency = "normal"
                            elif days_until <= 14:
                                title = "计划提前准备"
                                content = f"{plan.summary}还有{days_until}天"
                                priority = 50
                                urgency = "low"
                            else:
                                continue  # too far away

                            suggestions.append(Suggestion(
                                type=SuggestionType.PLAN_REMINDER,
                                title=title,
                                content=content,
                                icon="event_available",
                                related_event_ids=[],
                                action_options=["view_details", "set_reminder", "ignore"],
                                action_data={
                                    "memory_id": str(plan.id),
                                    "plan_summary": plan.summary,
                                    "target_date": plan_date_str,
                                    "days_until": days_until,
                                },
                                priority=priority,
                                urgency=urgency,
                            ))
                            continue
                    except (ValueError, TypeError):
                        pass  # invalid date, fall through to idle check

                # Plans without a date: remind if idle for a while
                if days_since_created >= 7 and plan.importance >= 5:
                    title = "别忘了这个计划"
                    content = f"您{days_since_created}天前提到：{plan.summary}"
                    priority = min(55, plan.importance * 6)

                    suggestions.append(Suggestion(
                        type=SuggestionType.PLAN_REMINDER,
                        title=title,
                        content=content,
                        icon="lightbulb",
                        action_options=["view_details", "ignore"],
                        action_data={
                            "memory_id": str(plan.id),
                            "plan_summary": plan.summary,
                            "days_since_created": days_since_created,
                        },
                        priority=priority,
                        urgency="low",
                    ))

        except ImportError:
            logger.debug("Memory models not available")
        except Exception as e:
            logger.error("Error finding plan reminders: %s", e)

        return suggestions[:5]
