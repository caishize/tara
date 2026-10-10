"""Meal care strategy — remind users to eat on busy days."""
from datetime import timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func

from .....config.logging import get_logger
from .....core.utils.timezone import local_today
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)

# Meal windows: (start_hour, end_hour, meal_name)
_MEAL_WINDOWS = [
    (11, 13, "午饭"),
    (17, 19, "晚饭"),
]


class MealCareStrategy(SuggestionStrategy):
    """Generate meal reminders when the schedule blocks meal windows.

    Checks if curated events overlap with lunch/dinner windows and
    reminds the user to eat — like a parent who won't let you skip meals.
    """

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []

        try:
            from ....curation.models import CuratedEvent
            today = local_today()
            tomorrow = today + timedelta(days=1)

            query = select(CuratedEvent).where(
                and_(
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.normalized_start >= today,
                    CuratedEvent.normalized_start < tomorrow,
                )
            )
            if family_id:
                query = query.where(CuratedEvent.family_id == family_id)

            result = await self.db.execute(query)
            events = result.scalars().all()

            if not events:
                return suggestions

            # Count events and check meal window conflicts
            event_count = len(events)

            for start_h, end_h, meal_name in _MEAL_WINDOWS:
                blocked = any(
                    e.normalized_start and e.normalized_end
                    and e.normalized_start.hour < end_h
                    and e.normalized_end.hour >= start_h
                    for e in events
                )
                if blocked:
                    suggestions.append(Suggestion(
                        type=SuggestionType.MEAL_CARE,
                        title=f"别忘了吃{meal_name}",
                        content=f"{meal_name}时间有事情，记得提前吃点或者留出时间，别饿着肚子忙。",
                        icon="restaurant",
                        action_options=["noted", "ignore"],
                        priority=65,
                        urgency="normal",
                    ))

            # Dense day: general meal reminder
            if event_count >= 4 and not suggestions:
                suggestions.append(Suggestion(
                    type=SuggestionType.MEAL_CARE,
                    title="今天事多，记得吃饭",
                    content="今天安排得挺满的，忙归忙，饭还是要好好吃的。",
                    icon="restaurant",
                    action_options=["noted", "ignore"],
                    priority=60,
                    urgency="normal",
                ))

        except Exception as e:
            logger.debug("MealCareStrategy skipped: %s", e)

        return suggestions
