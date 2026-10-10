"""
ImportantDate repository - Data access layer for ImportantDate entity.

Canonical location for date CRUD operations. During the coexistence
period, the ImportantDate ORM class is imported via the models.py shim.
"""
import logging
from typing import List, Optional
from uuid import UUID
from datetime import date, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import uuid as uuid_module

from .models import ImportantDate

logger = logging.getLogger(__name__)


class ImportantDateRepository:
    """Repository for ImportantDate CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_date(
        self,
        family_id: UUID,
        title: str,
        date_type: str,
        month: int,
        day: int,
        is_lunar: bool = False,
        member_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
        **kwargs
    ) -> ImportantDate:
        """Create a new important date."""
        # Build solar_date for current year
        today = date.today()
        solar_date = date(today.year, month, day)

        # If the date has passed this year, use next year
        if solar_date < today:
            solar_date = date(today.year + 1, month, day)

        important_date = ImportantDate(
            id=uuid_module.uuid4(),
            family_id=family_id,
            title=title,
            date_type=date_type,
            solar_date=solar_date,
            is_lunar=is_lunar,
            member_id=member_id,
            created_by=created_by or family_id,
            is_recurring=True,
            reminder_offsets=[-30, -7, -1, 0],
            reminder_time="09:00",
            **kwargs
        )

        if is_lunar:
            important_date.lunar_month = month
            important_date.lunar_day = day

        self.session.add(important_date)
        await self.session.flush()
        await self.session.refresh(important_date)
        return important_date

    async def get_by_id(self, date_id: UUID) -> Optional[ImportantDate]:
        """Get important date by ID."""
        stmt = select(ImportantDate).where(ImportantDate.id == date_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_family_dates(
        self,
        family_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[ImportantDate]:
        """Get all important dates for a family."""
        stmt = (
            select(ImportantDate)
            .where(ImportantDate.family_id == family_id)
            .order_by(ImportantDate.solar_date)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_upcoming_dates(
        self,
        family_id: UUID,
        days: int = 30
    ) -> List[ImportantDate]:
        """Get upcoming important dates within specified days."""
        today = date.today()
        end_date = today + timedelta(days=days)

        # Get all dates for the family
        all_dates = await self.get_family_dates(family_id)

        upcoming = []
        for d in all_dates:
            next_occurrence = self._get_next_occurrence(d)
            if next_occurrence and today <= next_occurrence <= end_date:
                # Attach the next occurrence for convenience
                d._next_occurrence = next_occurrence
                upcoming.append(d)

        # Sort by next occurrence
        upcoming.sort(key=lambda x: x._next_occurrence)
        return upcoming

    def _get_next_occurrence(self, important_date: ImportantDate) -> Optional[date]:
        """Calculate the next occurrence of an important date."""
        today = date.today()

        if important_date.is_lunar and important_date.lunar_month and important_date.lunar_day:
            result = self._lunar_to_next_solar(
                important_date.lunar_month,
                important_date.lunar_day,
                getattr(important_date, "lunar_leap", False) or False,
                today,
            )
            if result is not None:
                return result
            logger.warning(
                "Lunar conversion failed for date %s (lunar %d/%d), "
                "falling back to solar_date",
                important_date.id,
                important_date.lunar_month,
                important_date.lunar_day,
            )

        month = important_date.solar_date.month
        day = important_date.solar_date.day

        try:
            this_year = date(today.year, month, day)
            if this_year >= today:
                return this_year
            return date(today.year + 1, month, day)
        except ValueError:
            return None

    @staticmethod
    def _lunar_to_next_solar(
        lunar_month: int, lunar_day: int, is_leap: bool, today: date
    ) -> Optional[date]:
        """Convert lunar month/day to the next upcoming solar date."""
        try:
            from lunarcalendar import Converter, Lunar

            lunar_this = Lunar(today.year, lunar_month, lunar_day, isleap=is_leap)
            solar_this = Converter.Lunar2Solar(lunar_this)
            this_year_date = date(solar_this.year, solar_this.month, solar_this.day)

            if this_year_date >= today:
                return this_year_date

            lunar_next = Lunar(today.year + 1, lunar_month, lunar_day, isleap=is_leap)
            solar_next = Converter.Lunar2Solar(lunar_next)
            return date(solar_next.year, solar_next.month, solar_next.day)
        except Exception:
            return None

    async def search_dates(
        self,
        family_id: UUID,
        query: str
    ) -> List[ImportantDate]:
        """Search important dates by title."""
        stmt = (
            select(ImportantDate)
            .where(
                and_(
                    ImportantDate.family_id == family_id,
                    ImportantDate.title.ilike(f"%{query}%")
                )
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, date_id: UUID) -> bool:
        """Delete an important date."""
        stmt = select(ImportantDate).where(ImportantDate.id == date_id)
        result = await self.session.execute(stmt)
        important_date = result.scalar_one_or_none()

        if important_date:
            await self.session.delete(important_date)
            await self.session.flush()
            return True
        return False
