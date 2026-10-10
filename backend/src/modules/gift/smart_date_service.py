"""
SmartDateService - Provides intelligent date suggestions for gift recommendations.

Combines member's important dates with natural holidays to provide
contextual date selection for gift giving.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, datetime
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from .models import MemberGiftMemory, Occasion
from ..date_manager.models import ImportantDate
from ..member.repositories.member_repository import MemberRepository
from ...config.logging import get_logger

logger = get_logger(__name__)


class SmartDateSource(str, Enum):
    """Source of a smart date."""
    MEMBER_DATE = "member_date"
    NATURAL_HOLIDAY = "natural_holiday"
    GENERAL = "general"


# Mapping from ImportantDate.date_type to GiftOccasion
DATE_TYPE_TO_OCCASION = {
    "birthday": "birthday",
    "anniversary": "anniversary",
    "wedding": "wedding",
    "graduation": "graduation",
    "holiday": "holiday",
    "holiday_legal": "holiday",
    "holiday_lunar": "holiday",
    "memorial": "other",
    "vaccine": "other",
    "checkup": "other",
    "custom": "other",
}

# Mapping from Occasion.name_en to GiftOccasion
OCCASION_NAME_TO_GIFT_OCCASION = {
    "spring_festival": "holiday",
    "valentines_day": "anniversary",  # Treat as romantic occasion
    "womens_day": "holiday",
    "mothers_day": "birthday",  # Special family occasion
    "childrens_day": "birthday",  # Special for children
    "fathers_day": "birthday",  # Special family occasion
    "qixi": "anniversary",  # Chinese Valentine's
    "mid_autumn": "holiday",
    "national_day": "holiday",
    "christmas": "holiday",
}


@dataclass
class SmartDateResponse:
    """Response model for a smart date suggestion."""
    id: Optional[str]
    name: str
    date_value: Optional[str]  # ISO date string
    days_until: Optional[int]
    occasion_type: str
    source: str
    date_type: Optional[str]
    importance_level: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "date_value": self.date_value,
            "days_until": self.days_until,
            "occasion_type": self.occasion_type,
            "source": self.source,
            "date_type": self.date_type,
            "importance_level": self.importance_level,
        }


class SmartDateService:
    """Service for intelligent date suggestions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.member_repo = MemberRepository(session)

    async def get_smart_dates_for_member(
        self,
        member_id: UUID,
        family_id: UUID,
        days_ahead: int = 90
    ) -> Dict[str, Any]:
        """
        Get smart date suggestions for a member.

        Combines:
        1. Member's important dates (birthday, anniversary, etc.)
        2. Natural holidays (Spring Festival, Mother's Day, etc.)
        3. A "General recommendation" fallback option

        Args:
            member_id: The member to get dates for
            family_id: The family context
            days_ahead: How many days ahead to look (default 90)

        Returns:
            Dict with 'dates' list and 'nearest_date_id'
        """
        today = date.today()

        # Get member's name for display
        member = await self.member_repo.get_by_id(member_id)
        member_name = member.name if member else "成员"

        # 1. Get member's important dates
        member_dates = await self._get_member_dates(
            member_id, family_id, member_name, today, days_ahead
        )

        # 2. Get upcoming natural holidays
        holidays = await self._get_upcoming_holidays(today, days_ahead)

        # 3. Combine and sort by days_until
        all_dates = member_dates + holidays
        all_dates.sort(key=lambda x: x.days_until if x.days_until is not None else 999)

        # 4. Add general recommendation option at the end
        all_dates.append(SmartDateResponse(
            id=None,
            name="通用推荐",
            date_value=None,
            days_until=None,
            occasion_type="other",
            source=SmartDateSource.GENERAL.value,
            date_type=None,
            importance_level=3,
        ))

        # Find nearest date for default selection
        nearest_date_id = None
        for d in all_dates:
            if d.days_until is not None and d.days_until >= 0:
                nearest_date_id = d.id
                break

        return {
            "dates": [d.to_dict() for d in all_dates],
            "nearest_date_id": nearest_date_id,
        }

    async def _get_member_dates(
        self,
        member_id: UUID,
        family_id: UUID,
        member_name: str,
        today: date,
        days_ahead: int
    ) -> List[SmartDateResponse]:
        """Get member's important dates within the specified window."""
        # Query ImportantDate for this member
        stmt = select(ImportantDate).where(
            and_(
                ImportantDate.member_id == member_id,
                ImportantDate.family_id == family_id,
            )
        )
        result = await self.session.execute(stmt)
        important_dates = result.scalars().all()

        smart_dates = []
        for imp_date in important_dates:
            # Calculate next occurrence
            next_date = self._calculate_next_occurrence(imp_date, today)
            if next_date is None:
                continue

            days_until = (next_date - today).days
            if days_until < 0 or days_until > days_ahead:
                continue

            # Build display name
            date_type = imp_date.date_type or "custom"
            display_name = self._build_member_date_name(member_name, date_type, imp_date.title)

            # Map to gift occasion
            occasion_type = DATE_TYPE_TO_OCCASION.get(date_type, "other")

            smart_dates.append(SmartDateResponse(
                id=str(imp_date.id),
                name=display_name,
                date_value=next_date.isoformat(),
                days_until=days_until,
                occasion_type=occasion_type,
                source=SmartDateSource.MEMBER_DATE.value,
                date_type=date_type,
                importance_level=imp_date.importance_level or 5,
            ))

        return smart_dates

    def _calculate_next_occurrence(self, imp_date: ImportantDate, today: date) -> Optional[date]:
        """Calculate the next occurrence of an important date."""
        if imp_date.solar_date is None:
            return None

        base_date = imp_date.solar_date

        if not imp_date.is_recurring:
            # Non-recurring: return the date if it's in the future
            return base_date if base_date >= today else None

        # Recurring: calculate this year's and next year's occurrence
        this_year_date = base_date.replace(year=today.year)
        if this_year_date >= today:
            return this_year_date
        else:
            return base_date.replace(year=today.year + 1)

    def _build_member_date_name(self, member_name: str, date_type: str, title: Optional[str]) -> str:
        """Build display name for a member's date."""
        type_names = {
            "birthday": "生日",
            "anniversary": "纪念日",
            "wedding": "结婚纪念日",
            "graduation": "毕业纪念",
            "memorial": "纪念日",
            "custom": "纪念日",
        }
        type_name = type_names.get(date_type, title or "纪念日")

        # Use title if it doesn't contain the member's name already
        if title and member_name not in title:
            return title

        return f"{member_name}的{type_name}"

    async def _get_upcoming_holidays(
        self,
        today: date,
        days_ahead: int
    ) -> List[SmartDateResponse]:
        """Get upcoming natural holidays within the specified window."""
        # Query active occasions
        stmt = select(Occasion).where(Occasion.is_active == True)
        result = await self.session.execute(stmt)
        occasions = result.scalars().all()

        smart_dates = []
        for occasion in occasions:
            # Calculate the date for this year
            next_date = occasion.calculate_date(today.year)
            if next_date is None:
                continue

            # If this year's date has passed, try next year
            if next_date < today:
                next_date = occasion.calculate_date(today.year + 1)
                if next_date is None:
                    continue

            days_until = (next_date - today).days
            if days_until < 0 or days_until > days_ahead:
                continue

            # Map to gift occasion type
            occasion_type = OCCASION_NAME_TO_GIFT_OCCASION.get(
                occasion.name_en, "holiday"
            )

            # Determine importance level based on occasion
            importance = self._get_occasion_importance(occasion.name_en)

            smart_dates.append(SmartDateResponse(
                id=f"occasion_{occasion.id}",
                name=occasion.name,
                date_value=next_date.isoformat(),
                days_until=days_until,
                occasion_type=occasion_type,
                source=SmartDateSource.NATURAL_HOLIDAY.value,
                date_type="holiday",
                importance_level=importance,
            ))

        return smart_dates

    def _get_occasion_importance(self, name_en: Optional[str]) -> int:
        """Get importance level for an occasion (1-10)."""
        importance_map = {
            "spring_festival": 10,
            "mid_autumn": 8,
            "valentines_day": 7,
            "mothers_day": 9,
            "fathers_day": 9,
            "qixi": 7,
            "christmas": 7,
            "childrens_day": 6,
            "national_day": 6,
            "womens_day": 6,
        }
        return importance_map.get(name_en, 5)
