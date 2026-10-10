"""Gift reminder strategy — birthday/anniversary gift suggestions.

Generates GIFT_REMINDER suggestions when upcoming birthdays or anniversaries
approach and gifts haven't been prepared yet.
"""
from typing import List, Optional
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, and_

from .....config.logging import get_logger
from .....core.utils.timezone import local_today
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


class GiftStrategy(SuggestionStrategy):
    """Generate gift reminders for approaching birthdays and events."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        today = local_today()

        # 1. Birthday-based gift reminders
        try:
            from ....date_manager.models import ImportantDate

            query = select(ImportantDate).where(
                and_(
                    ImportantDate.date_type == "birthday",
                    ImportantDate.solar_date >= today,
                    ImportantDate.solar_date <= today + timedelta(days=14),
                )
            )
            if family_id:
                query = query.where(ImportantDate.family_id == family_id)

            result = await self.db.execute(query)
            birthday_dates = result.scalars().all()

            for bd in birthday_dates:
                days_until = (bd.solar_date - today).days
                member_name = bd.title.replace("生日", "").replace("的", "").strip()
                if not member_name:
                    member_name = bd.title

                if days_until <= 0:
                    title = f"{member_name}生日快乐"
                    content = f"今天是{bd.title}！记得送上祝福和礼物"
                    priority = 95
                    urgency = "high"
                elif days_until <= 3:
                    title = f"{member_name}的生日快到了"
                    content = f"{bd.title}还有{days_until}天，需要准备礼物吗？"
                    priority = 85
                    urgency = "high"
                elif days_until <= 7:
                    title = "生日礼物提醒"
                    content = f"{bd.title}还有{days_until}天，提前选好礼物"
                    priority = 70
                    urgency = "normal"
                else:
                    title = "提前准备生日礼物"
                    content = f"{bd.title}还有{days_until}天，现在选礼物不会太晚"
                    priority = 50
                    urgency = "low"

                suggestions.append(Suggestion(
                    type=SuggestionType.GIFT_REMINDER,
                    title=title,
                    content=content,
                    icon="cake",
                    related_event_ids=[str(bd.id)],
                    related_member_ids=[str(bd.member_id)] if bd.member_id else [],
                    action_options=["prepare_gift", "set_reminder", "ignore"],
                    action_data={
                        "date_id": str(bd.id),
                        "date_title": bd.title,
                        "member_name": member_name,
                        "days_until": days_until,
                        "occasion": "birthday",
                    },
                    priority=priority,
                    urgency=urgency,
                ))

        except ImportError:
            logger.debug("ImportantDate model not available")
        except Exception as e:
            logger.error("Error finding birthday gift reminders: %s", e)

        # 2. Gift task status reminders
        try:
            from ....gift.models import GiftTask

            active_tasks_query = select(GiftTask).where(
                and_(
                    GiftTask.family_id == family_id,
                    GiftTask.status.in_(["discovered", "recommended"]),
                )
            ).limit(5)

            result = await self.db.execute(active_tasks_query)
            tasks = result.scalars().all()

            for task in tasks:
                recipient = getattr(task, "recipient_name", None) or "收礼人"
                occasion = getattr(task, "occasion", None) or "送礼"

                suggestions.append(Suggestion(
                    type=SuggestionType.GIFT_REMINDER,
                    title=f"礼物待购买：{recipient}",
                    content=f"为{recipient}的{occasion}准备的礼物还没购买",
                    icon="card_giftcard",
                    action_options=["view_details", "ignore"],
                    action_data={
                        "gift_task_id": str(task.id),
                        "recipient": recipient,
                        "occasion": occasion,
                    },
                    priority=60,
                    urgency="normal",
                ))

        except ImportError:
            logger.debug("GiftTask model not available")
        except Exception as e:
            logger.error("Error finding gift task reminders: %s", e)

        return suggestions
