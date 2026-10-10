"""Anniversary reminder strategy — important date reminders."""
from typing import List, Optional
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, and_

from .....config.logging import get_logger
from .....core.utils.timezone import local_today
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


class AnniversaryStrategy(SuggestionStrategy):
    """Find anniversary and important date reminders."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        today = local_today()

        try:
            from ....date_manager.models import ImportantDate

            query = select(ImportantDate).where(
                and_(
                    ImportantDate.date_type != "birthday",
                    ImportantDate.solar_date >= today,
                    ImportantDate.solar_date <= today + timedelta(days=14),
                )
            )

            if family_id:
                query = query.where(ImportantDate.family_id == family_id)

            result = await self.db.execute(query)
            dates = result.scalars().all()

            for important_date in dates:
                days_until = (important_date.solar_date - today).days
                date_type = important_date.date_type

                if date_type in ("anniversary", "wedding_anniversary"):
                    if days_until <= 7:
                        if days_until == 0:
                            title = "纪念日提醒"
                            content = f"今天是{important_date.title}！"
                            priority = 95
                            urgency = "high"
                            actions = ["book_restaurant", "prepare_gift", "ignore"]
                        else:
                            title = "纪念日即将到来"
                            content = f"{important_date.title}还有{days_until}天，需要预订餐厅吗？"
                            priority = 80 if days_until <= 3 else 65
                            urgency = "high" if days_until <= 3 else "normal"
                            actions = ["book_restaurant", "prepare_gift", "set_reminder", "ignore"]

                        suggestions.append(Suggestion(
                            type=SuggestionType.ANNIVERSARY_REMINDER,
                            title=title,
                            content=content,
                            icon="favorite",
                            related_event_ids=[str(important_date.id)],
                            action_options=actions,
                            action_data={
                                "date_id": str(important_date.id),
                                "date_title": important_date.title,
                                "date_type": date_type,
                                "date": important_date.solar_date.isoformat(),
                                "days_until": days_until,
                            },
                            priority=priority,
                            urgency=urgency,
                        ))
                else:
                    if days_until <= 3:
                        suggestions.append(Suggestion(
                            type=SuggestionType.TIME_CORRELATION,
                            title="重要日期提醒",
                            content=(
                                f"{important_date.title}还有{days_until}天"
                                if days_until > 0
                                else f"今天是{important_date.title}"
                            ),
                            icon="event_note",
                            related_event_ids=[str(important_date.id)],
                            action_options=["view_details", "set_reminder", "ignore"],
                            action_data={
                                "date_id": str(important_date.id),
                                "date_title": important_date.title,
                                "date_type": date_type,
                                "date": important_date.solar_date.isoformat(),
                            },
                            priority=70 if days_until == 0 else 50,
                            urgency="high" if days_until == 0 else "normal",
                        ))

        except Exception as e:
            logger.error(f"Error finding anniversary reminders: {e}")

        return suggestions
