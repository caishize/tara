"""Rest care strategy — remind users to rest after consecutive busy days."""
from datetime import timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func

from .....config.logging import get_logger
from .....core.utils.timezone import local_today
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)

# Thresholds
_CONSECUTIVE_BUSY_DAYS_THRESHOLD = 3
_EVENTS_PER_DAY_BUSY = 3


class RestCareStrategy(SuggestionStrategy):
    """Generate rest/recovery suggestions after consecutive busy days.

    Looks at the past few days' event density and today's schedule to
    produce caring rest reminders — like a parent who notices you've
    been working too hard.
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

            # Check past N days event density
            lookback_start = today - timedelta(days=_CONSECUTIVE_BUSY_DAYS_THRESHOLD)

            query = (
                select(
                    func.date(CuratedEvent.normalized_start).label("event_date"),
                    func.count(CuratedEvent.id).label("event_count"),
                )
                .where(
                    and_(
                        CuratedEvent.is_active.is_(True),
                        CuratedEvent.normalized_start >= lookback_start,
                        CuratedEvent.normalized_start < today,
                    )
                )
                .group_by(func.date(CuratedEvent.normalized_start))
            )
            if family_id:
                query = query.where(CuratedEvent.family_id == family_id)

            result = await self.db.execute(query)
            daily_counts = {row.event_date: row.event_count for row in result}

            # Count consecutive busy days
            consecutive_busy = 0
            for i in range(_CONSECUTIVE_BUSY_DAYS_THRESHOLD):
                check_date = today - timedelta(days=i + 1)
                if daily_counts.get(check_date, 0) >= _EVENTS_PER_DAY_BUSY:
                    consecutive_busy += 1
                else:
                    break

            # Also check if today is relatively free (opportunity to rest)
            today_query = select(func.count(CuratedEvent.id)).where(
                and_(
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.normalized_start >= today,
                    CuratedEvent.normalized_start < today + timedelta(days=1),
                )
            )
            if family_id:
                today_query = today_query.where(CuratedEvent.family_id == family_id)

            today_result = await self.db.execute(today_query)
            today_count = today_result.scalar() or 0

            if consecutive_busy >= _CONSECUTIVE_BUSY_DAYS_THRESHOLD:
                if today_count <= 2:
                    # Free-ish day after busy streak — encourage rest
                    suggestions.append(Suggestion(
                        type=SuggestionType.REST_CARE,
                        title="这几天辛苦了，好好休息",
                        content=f"连续忙了{consecutive_busy}天了，今天没什么急事，给自己放松一下吧。",
                        icon="self_improvement",
                        action_options=["noted", "ignore"],
                        priority=72,
                        urgency="normal",
                    ))
                else:
                    # Still busy — at least remind to take care
                    suggestions.append(Suggestion(
                        type=SuggestionType.REST_CARE,
                        title="连续忙了好几天，注意身体",
                        content=f"已经连续忙了{consecutive_busy}天了，今天还有事情，记得忙完早点休息。",
                        icon="bedtime",
                        action_options=["noted", "ignore"],
                        priority=68,
                        urgency="normal",
                    ))

            # Weekend rest encouragement
            if today.weekday() in (5, 6) and today_count <= 1:
                suggestions.append(Suggestion(
                    type=SuggestionType.REST_CARE,
                    title="周末了，好好放松",
                    content="难得周末没什么事，陪陪家人，或者做点自己喜欢的事。",
                    icon="weekend",
                    action_options=["noted", "ignore"],
                    priority=55,
                    urgency="low",
                ))

        except Exception as e:
            logger.debug("RestCareStrategy skipped: %s", e)

        return suggestions
