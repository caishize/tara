"""Concrete DateService wrapping legacy date_time_management.

Handles CRUD for important dates, recurring date logic,
upcoming date calculations, and holiday listing.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from .interface import IDateService, ImportantDateDTO
from ...core.utils.timezone import local_today, utc_now
from ...core.constants import SYSTEM_FAMILY_ID

logger = logging.getLogger(__name__)

# Default reminder offsets per date type
_DEFAULT_OFFSETS: Dict[str, List[int]] = {
    "birthday": [30, 7, 3, 0],
    "anniversary": [30, 7, 1, 0],
    "medical_check": [7, 3, 1, 0],
    "vaccine": [7, 3, 1, 0],
    "holiday": [7, 1, 0],
    "custom": [7, 1, 0],
}

# E7: Default preparation lead days per date type
_DEFAULT_LEAD_DAYS: Dict[str, int] = {
    "birthday": 14,
    "anniversary": 14,
    "spring_festival": 30,
    "mid_autumn": 21,
    "milestone_birthday": 60,
    "wedding": 90,
    "holiday_lunar": 14,
    "holiday_legal": 7,
    "holiday": 7,
    "medical_check": 7,
    "vaccine": 7,
    "custom": 7,
}


def _compute_default_lead_days(
    date_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """Compute default preparation lead days based on date type (E7).

    Milestone birthdays (e.g. 30th, 50th, 60th) get a longer lead time.
    """
    if date_type == "birthday" and metadata and metadata.get("is_milestone"):
        return _DEFAULT_LEAD_DAYS["milestone_birthday"]
    return _DEFAULT_LEAD_DAYS.get(date_type, 7)


class DateService(IDateService):
    """Important date CRUD + holiday templates."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_date(
        self, family_id: str, date_type: str,
        date_value: date, title: str,
        recurrence: Optional[str] = None,
        linked_member_id: Optional[str] = None,
        reminder_days: Optional[List[int]] = None,
        notes: Optional[str] = None,
        created_by: Optional[str] = None,
        preparation_lead_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_lunar: bool = False,
        lunar_year: Optional[int] = None,
        source: str = "manual",
        importance_level: int = 5,
    ) -> ImportantDateDTO:
        from .models import ImportantDate

        if reminder_days is None:
            reminder_days = list(_DEFAULT_OFFSETS.get(date_type, [7, 1, 0]))

        # E7: Compute default preparation lead days if not explicitly set
        if preparation_lead_days is None:
            preparation_lead_days = _compute_default_lead_days(
                date_type, metadata,
            )

        creator_id = UUID(created_by) if created_by else UUID(family_id)

        imp_date = ImportantDate(
            family_id=UUID(family_id),
            created_by=creator_id,
            title=title,
            date_type=date_type,
            solar_date=date_value,
            is_recurring=recurrence is not None and recurrence != "once",
            recurrence_rule={"freq": recurrence} if recurrence else None,
            member_id=UUID(linked_member_id) if linked_member_id else None,
            reminder_offsets=reminder_days,
            notes=notes,
            preparation_lead_days=preparation_lead_days,
            is_lunar=is_lunar,
            lunar_year=lunar_year,
            source=source,
            importance_level=importance_level,
        )
        self.session.add(imp_date)
        await self.session.flush()
        return self._to_dto(imp_date)

    async def get_date(
        self, date_id: str, family_id: str,
    ) -> Optional[ImportantDateDTO]:
        from .models import ImportantDate

        result = await self.session.execute(
            select(ImportantDate).where(
                and_(
                    ImportantDate.id == UUID(date_id),
                    ImportantDate.family_id == UUID(family_id),
                )
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_dto(row)

    async def list_dates(
        self, family_id: str,
        date_type: Optional[str] = None,
        member_id: Optional[UUID] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[ImportantDateDTO]:
        from .models import ImportantDate

        fid = UUID(family_id) if isinstance(family_id, str) else family_id
        query = select(ImportantDate).where(
            ImportantDate.family_id == fid,
        )
        if date_type:
            query = query.where(ImportantDate.date_type == date_type)
        if member_id:
            query = query.where(ImportantDate.member_id == member_id)
        if from_date:
            query = query.where(ImportantDate.solar_date >= from_date)
        if to_date:
            query = query.where(ImportantDate.solar_date <= to_date)
        query = query.order_by(ImportantDate.solar_date)

        result = await self.session.execute(query)
        return [self._to_dto(d) for d in result.scalars().all()]

    async def get_upcoming_dates(
        self,
        family_id: str,
        days: int = 30,
        *,
        days_ahead: Optional[int] = None,
        target_date: Optional[date] = None,
    ) -> List[ImportantDateDTO]:
        """Alias for get_upcoming() used by API routes and insight services.

        Backward-compatible parameter support:
        - ``days``: legacy positional/keyword days window
        - ``days_ahead``: newer keyword alias used by insight services
        - ``target_date``: reference date for "upcoming" calculations
        """
        fid = str(family_id) if not isinstance(family_id, str) else family_id
        effective_days = days_ahead if days_ahead is not None else days
        return await self.get_upcoming(
            fid,
            days=effective_days,
            target_date=target_date,
        )

    async def update_date(
        self, date_id: str, family_id: str,
        updates: Dict[str, Any],
    ) -> ImportantDateDTO:
        from .models import ImportantDate

        result = await self.session.execute(
            select(ImportantDate).where(
                and_(
                    ImportantDate.id == UUID(date_id),
                    ImportantDate.family_id == UUID(family_id),
                )
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"Important date {date_id} not found")

        # Handle recurrence update
        if "recurrence" in updates:
            rec = updates.pop("recurrence")
            row.is_recurring = rec is not None and rec != "once"
            row.recurrence_rule = {"freq": rec} if rec else None

        # Handle field-by-field updates safely
        field_map = {
            "title": "title",
            "date_type": "date_type",
            "date_value": "solar_date",
            "solar_date": "solar_date",
            "linked_member_id": "member_id",
            "member_id": "member_id",
            "reminder_days": "reminder_offsets",
            "reminder_offsets": "reminder_offsets",
            "notes": "notes",
            "is_recurring": "is_recurring",
            "importance_level": "importance_level",
            "preparation_lead_days": "preparation_lead_days",
        }
        for key, value in updates.items():
            attr_name = field_map.get(key, key)
            if hasattr(row, attr_name):
                if attr_name == "member_id" and isinstance(value, str):
                    value = UUID(value)
                setattr(row, attr_name, value)

        await self.session.flush()
        return self._to_dto(row)

    async def delete_date(
        self, date_id: str, family_id: str,
    ) -> bool:
        from .models import ImportantDate

        result = await self.session.execute(
            select(ImportantDate).where(
                and_(
                    ImportantDate.id == UUID(date_id),
                    ImportantDate.family_id == UUID(family_id),
                )
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True

    async def get_upcoming(
        self,
        family_id: str,
        days: int = 30,
        target_date: Optional[date] = None,
    ) -> List[ImportantDateDTO]:
        """Get dates approaching within N days.

        Handles recurring dates by computing next occurrence for each
        recurring date, not just checking raw solar_date.
        """
        from .models import ImportantDate

        today = target_date or local_today()
        end_date = today + timedelta(days=days)

        # Fetch all dates for this family + system holidays
        # For recurring dates, we need to check next occurrence
        result = await self.session.execute(
            select(ImportantDate).where(
                or_(
                    ImportantDate.family_id == UUID(family_id),
                    ImportantDate.family_id == SYSTEM_FAMILY_ID,
                )
            ).order_by(ImportantDate.solar_date)
        )
        all_dates = result.scalars().all()

        upcoming = []
        for d in all_dates:
            next_occ = self._compute_next_occurrence(d, today)
            if next_occ is None:
                continue
            if next_occ > end_date:
                continue

            days_until = (next_occ - today).days
            upcoming.append(ImportantDateDTO(
                id=str(d.id),
                family_id=str(d.family_id),
                date_type=d.date_type,
                date_value=next_occ,
                title=d.title,
                recurrence=self._extract_recurrence(d),
                linked_member_id=str(d.member_id) if d.member_id else None,
                notes=d.notes,
                reminder_days=d.reminder_offsets,
                days_until=days_until,
                is_lunar=getattr(d, "is_lunar", False),
                is_recurring=getattr(d, "is_recurring", False),
                importance_level=getattr(d, "importance_level", 5),
                lunar_month=getattr(d, "lunar_month", None),
                lunar_day=getattr(d, "lunar_day", None),
            ))

        # Sort by days_until ascending
        upcoming.sort(key=lambda dto: dto.days_until if dto.days_until is not None else 9999)
        return upcoming

    async def get_holidays(
        self, year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        from .models import ImportantDate

        target_year = year or date.today().year
        result = await self.session.execute(
            select(ImportantDate).where(
                and_(
                    ImportantDate.family_id == SYSTEM_FAMILY_ID,
                    ImportantDate.date_type.in_([
                        "holiday", "holiday_legal",
                        "holiday_lunar", "holiday_solar_term",
                    ]),
                )
            ).order_by(ImportantDate.solar_date)
        )
        holidays = result.scalars().all()
        return [
            {
                "id": str(h.id),
                "title": h.title,
                "date": h.solar_date.isoformat() if h.solar_date else None,
                "type": h.date_type,
                "is_lunar": h.is_lunar,
                "importance_level": h.importance_level,
            }
            for h in holidays
            if h.solar_date and h.solar_date.year == target_year
        ]

    # ── Recurring date helpers ──────────────────────────────────────

    @staticmethod
    def _compute_next_occurrence(
        imp_date: Any, reference_date: date,
    ) -> Optional[date]:
        """Compute the next occurrence of a date on or after reference_date.

        For non-recurring dates, returns solar_date if >= reference_date.
        For recurring dates, computes this-year or next-year occurrence.
        Uses the model's get_next_occurrence() for lunar dates.
        """
        if not imp_date.solar_date:
            return None

        if not imp_date.is_recurring:
            if imp_date.solar_date >= reference_date:
                return imp_date.solar_date
            return None

        # Lunar recurrence path (reference-date aware)
        if (
            getattr(imp_date, "is_lunar", False)
            and getattr(imp_date, "lunar_month", None)
            and getattr(imp_date, "lunar_day", None)
        ):
            lunar_occ = DateService._lunar_to_next_solar(
                int(imp_date.lunar_month),
                int(imp_date.lunar_day),
                bool(getattr(imp_date, "lunar_leap", False) or False),
                reference_date,
            )
            if lunar_occ is not None:
                return lunar_occ

        # Manual yearly recurrence calculation for solar dates
        month = imp_date.solar_date.month
        day = imp_date.solar_date.day
        try:
            this_year = date(reference_date.year, month, day)
            if this_year >= reference_date:
                return this_year
            return date(reference_date.year + 1, month, day)
        except ValueError:
            # Feb 29 in non-leap year
            try:
                return date(reference_date.year + 1, month, day)
            except ValueError:
                return None

    @staticmethod
    def _lunar_to_next_solar(
        lunar_month: int,
        lunar_day: int,
        is_leap: bool,
        reference_date: date,
    ) -> Optional[date]:
        """Convert a lunar month/day to next solar occurrence after reference_date."""
        try:
            from lunarcalendar import Converter, Lunar

            lunar_this = Lunar(
                reference_date.year, lunar_month, lunar_day, isleap=is_leap,
            )
            solar_this = Converter.Lunar2Solar(lunar_this)
            this_year_date = date(
                solar_this.year, solar_this.month, solar_this.day,
            )

            if this_year_date >= reference_date:
                return this_year_date

            lunar_next = Lunar(
                reference_date.year + 1, lunar_month, lunar_day, isleap=is_leap,
            )
            solar_next = Converter.Lunar2Solar(lunar_next)
            return date(solar_next.year, solar_next.month, solar_next.day)
        except Exception:
            return None

    @staticmethod
    def _extract_recurrence(imp_date: Any) -> Optional[str]:
        """Extract recurrence string from a model instance."""
        if imp_date.recurrence_rule and isinstance(imp_date.recurrence_rule, dict):
            return imp_date.recurrence_rule.get("freq")
        if imp_date.is_recurring:
            return "yearly"
        return None

    @staticmethod
    def _to_dto(imp_date: Any) -> ImportantDateDTO:
        recurrence = None
        if imp_date.recurrence_rule and isinstance(imp_date.recurrence_rule, dict):
            recurrence = imp_date.recurrence_rule.get("freq")
        elif imp_date.is_recurring:
            recurrence = "yearly"

        created_at_str = None
        if hasattr(imp_date, "created_at") and imp_date.created_at:
            created_at_str = imp_date.created_at.isoformat()

        return ImportantDateDTO(
            id=str(imp_date.id),
            family_id=str(imp_date.family_id),
            date_type=imp_date.date_type,
            date_value=imp_date.solar_date,
            title=imp_date.title,
            recurrence=recurrence,
            linked_member_id=str(imp_date.member_id) if imp_date.member_id else None,
            notes=imp_date.notes,
            reminder_days=imp_date.reminder_offsets,
            is_lunar=getattr(imp_date, "is_lunar", False),
            is_recurring=getattr(imp_date, "is_recurring", False),
            importance_level=getattr(imp_date, "importance_level", 5),
            lunar_year=getattr(imp_date, "lunar_year", None),
            lunar_month=getattr(imp_date, "lunar_month", None),
            lunar_day=getattr(imp_date, "lunar_day", None),
            reminder_time=getattr(imp_date, "reminder_time", None),
            created_at=created_at_str,
        )
