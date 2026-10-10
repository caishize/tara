"""Person correlation strategy — upcoming birthday reminders."""
from typing import List, Optional
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select, and_

from .....config.logging import get_logger
from .....core.utils.timezone import local_today
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


class PersonStrategy(SuggestionStrategy):
    """Find person-related suggestions (e.g. upcoming birthdays)."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        today = local_today()

        try:
            from ....member.models.member import Member

            member_query = select(Member).where(
                and_(
                    Member.is_deleted == False,
                    Member.date_of_birth.isnot(None),
                )
            )

            if family_id:
                member_query = member_query.where(Member.family_id == family_id)

            result = await self.db.execute(member_query)
            members = result.scalars().all()

            for member in members:
                if not member.date_of_birth:
                    continue

                try:
                    next_birthday = date(
                        today.year,
                        member.date_of_birth.month,
                        member.date_of_birth.day,
                    )
                    if next_birthday < today:
                        next_birthday = date(
                            today.year + 1,
                            member.date_of_birth.month,
                            member.date_of_birth.day,
                        )
                except ValueError:
                    try:
                        next_birthday = date(today.year, 2, 28)
                        if next_birthday < today:
                            next_birthday = date(today.year + 1, 2, 28)
                    except ValueError:
                        continue

                days_until = (next_birthday - today).days

                if 0 <= days_until <= 7:
                    age = next_birthday.year - member.date_of_birth.year

                    if days_until == 0:
                        title = "生日提醒"
                        content = f"今天是{member.name}的{age}岁生日！"
                        priority = 95
                        urgency = "high"
                    elif days_until == 1:
                        title = "生日提醒"
                        content = f"明天是{member.name}的{age}岁生日，准备好祝福了吗？"
                        priority = 85
                        urgency = "high"
                    else:
                        title = "生日即将到来"
                        content = f"{member.name}的{age}岁生日还有{days_until}天，需要准备礼物吗？"
                        priority = 70
                        urgency = "normal"

                    suggestions.append(Suggestion(
                        type=SuggestionType.GIFT_REMINDER,
                        title=title,
                        content=content,
                        icon="cake",
                        related_member_ids=[str(member.id)],
                        action_options=["prepare_gift", "send_message", "set_reminder", "ignore"],
                        action_data={
                            "member_id": str(member.id),
                            "member_name": member.name,
                            "birthday": next_birthday.isoformat(),
                            "age": age,
                            "days_until": days_until,
                        },
                        priority=priority,
                        urgency=urgency,
                    ))

        except Exception as e:
            logger.error(f"Error finding person correlations: {e}")

        return suggestions
