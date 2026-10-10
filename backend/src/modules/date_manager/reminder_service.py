"""Concrete ReminderService wrapping legacy date_time_management.

Smart reminder strategy: 30-day, 7-day, 1-day, same-day chains.
Checks due reminders by comparing reminder_time against current time.
"""

import logging
from datetime import date, datetime, timedelta, time, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .interface import IReminderService, DateReminderDTO
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)

# Default reminder time (09:00 AM UTC)
DEFAULT_REMINDER_TIME = time(9, 0)

# Smart reminder offsets by importance
SMART_OFFSETS: Dict[str, List[int]] = {
    "birthday": [30, 7, 1, 0],
    "anniversary": [30, 7, 1, 0],
    "medical_check": [7, 3, 1, 0],
    "vaccine": [7, 3, 1, 0],
    "holiday": [30, 7, 1, 0],
    "custom": [7, 1, 0],
}


class ReminderService(IReminderService):
    """Smart reminder strategy (30d/7d/1d/same-day chain)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_reminders_for_date(
        self, date_id: str, reminder_days: List[int],
        target_date: date,
    ) -> List[DateReminderDTO]:
        from .models import DateReminder

        now = utc_now()
        created = []
        for offset in sorted(reminder_days, reverse=True):
            reminder_date = target_date - timedelta(days=offset)
            reminder_dt = datetime.combine(
                reminder_date, DEFAULT_REMINDER_TIME,
            ).replace(tzinfo=timezone.utc)

            # Skip reminders in the past
            if reminder_dt < now:
                continue

            content = self._generate_content(offset, target_date)

            reminder = DateReminder(
                date_id=UUID(date_id),
                reminder_time=reminder_dt,
                reminder_offset=offset,
                reminder_content=content,
                channel="app",
                status="pending",
            )
            self.session.add(reminder)
            await self.session.flush()

            created.append(DateReminderDTO(
                id=str(reminder.id),
                date_id=date_id,
                reminder_offset=offset,
                status="pending",
                reminder_time=reminder_dt,
                content=content,
            ))

        return created

    async def generate_smart_schedule(
        self, date_id: str, date_type: str,
        target_date: date,
    ) -> List[DateReminderDTO]:
        """Generate a smart reminder schedule based on date type.

        Uses predefined offsets per date type (birthday gets 30/7/1/0,
        custom gets 7/1/0, etc.).
        """
        offsets = list(SMART_OFFSETS.get(date_type, [7, 1, 0]))
        return await self.create_reminders_for_date(
            date_id=date_id,
            reminder_days=offsets,
            target_date=target_date,
        )

    async def get_due_reminders(
        self, family_id: str,
    ) -> List[Dict[str, Any]]:
        """Get reminders that are due now.

        Checks pending reminders whose reminder_time has passed
        (up to 24 hours ago, to catch missed ones).
        """
        from .models import DateReminder, ImportantDate

        now = utc_now()
        window_start = now - timedelta(hours=24)

        result = await self.session.execute(
            select(DateReminder, ImportantDate)
            .join(ImportantDate, DateReminder.date_id == ImportantDate.id)
            .where(
                and_(
                    ImportantDate.family_id == UUID(family_id),
                    DateReminder.status == "pending",
                    DateReminder.reminder_time <= now,
                    DateReminder.reminder_time >= window_start,
                )
            )
            .order_by(DateReminder.reminder_time)
        )

        due_reminders = []
        for reminder, imp_date in result.all():
            days_until = None
            if imp_date.solar_date:
                days_until = (imp_date.solar_date - date.today()).days

            due_reminders.append({
                "reminder_id": str(reminder.id),
                "date_id": str(imp_date.id),
                "title": imp_date.title,
                "date": imp_date.solar_date.isoformat() if imp_date.solar_date else None,
                "days_until": days_until,
                "date_type": imp_date.date_type,
                "content": reminder.reminder_content,
                "reminder_offset": reminder.reminder_offset,
                "channel": reminder.channel,
                "member_id": str(imp_date.member_id) if imp_date.member_id else None,
            })

        return due_reminders

    async def mark_sent(self, reminder_id: str) -> None:
        from .models import DateReminder

        result = await self.session.execute(
            select(DateReminder).where(
                DateReminder.id == UUID(reminder_id),
            )
        )
        reminder = result.scalar_one_or_none()
        if reminder is None:
            raise ValueError(f"Reminder {reminder_id} not found")
        reminder.status = "sent"
        reminder.actual_sent_time = utc_now()
        await self.session.flush()

    async def mark_acknowledged(self, reminder_id: str) -> None:
        """Mark a reminder as acknowledged/clicked by the user."""
        from .models import DateReminder

        result = await self.session.execute(
            select(DateReminder).where(
                DateReminder.id == UUID(reminder_id),
            )
        )
        reminder = result.scalar_one_or_none()
        if reminder is None:
            raise ValueError(f"Reminder {reminder_id} not found")
        reminder.status = "clicked"
        reminder.user_clicked = True
        reminder.clicked_at = utc_now()
        await self.session.flush()

    async def cancel_reminders(self, date_id: str) -> int:
        from .models import DateReminder

        result = await self.session.execute(
            select(DateReminder).where(
                and_(
                    DateReminder.date_id == UUID(date_id),
                    DateReminder.status == "pending",
                )
            )
        )
        reminders = result.scalars().all()
        count = 0
        for r in reminders:
            r.status = "skipped"
            count += 1
        if count:
            await self.session.flush()
        return count

    async def reschedule_for_next_occurrence(
        self, date_id: str, next_date: date,
        reminder_days: Optional[List[int]] = None,
    ) -> List[DateReminderDTO]:
        """Cancel existing pending reminders and create new ones
        for the next occurrence of a recurring date.

        Args:
            date_id: The important date ID.
            next_date: The next occurrence date to schedule reminders for.
            reminder_days: Specific offsets; if None, uses existing.
        """
        # Cancel existing pending reminders
        cancelled = await self.cancel_reminders(date_id)
        if cancelled:
            logger.info(
                "Cancelled %d pending reminders for date %s before reschedule",
                cancelled, date_id,
            )

        # Determine offsets
        if reminder_days is None:
            from .models import ImportantDate
            result = await self.session.execute(
                select(ImportantDate).where(
                    ImportantDate.id == UUID(date_id),
                )
            )
            imp = result.scalar_one_or_none()
            if imp and imp.reminder_offsets:
                reminder_days = imp.reminder_offsets
            else:
                reminder_days = [7, 1, 0]

        return await self.create_reminders_for_date(
            date_id=date_id,
            reminder_days=reminder_days,
            target_date=next_date,
        )

    @staticmethod
    def _generate_content(offset: int, target_date: date) -> str:
        """Generate reminder content based on offset."""
        date_str = target_date.strftime("%m/%d")
        if offset == 0:
            return f"今天是 {date_str}，别忘了！"
        elif offset == 1:
            return f"明天就是 {date_str} 了，准备好了吗？"
        elif offset <= 7:
            return f"还有{offset}天就到 {date_str} 了，提前准备一下吧"
        else:
            return f"距离 {date_str} 还有{offset}天，可以开始准备了"
