"""Date Manager module public interface.

Defines abstract contracts for important date management
and smart reminder strategies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING


@dataclass(frozen=True)
class ImportantDateDTO:
    """An important date entry."""
    id: str
    family_id: str
    date_type: str
    date_value: date
    title: str
    recurrence: Optional[str] = None
    linked_member_id: Optional[str] = None
    notes: Optional[str] = None
    reminder_days: Optional[List[int]] = None
    days_until: Optional[int] = None
    # Extended fields for API response
    is_lunar: bool = False
    is_recurring: bool = False
    importance_level: int = 5
    lunar_year: Optional[int] = None
    lunar_month: Optional[int] = None
    lunar_day: Optional[int] = None
    reminder_time: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class DateReminderDTO:
    """A reminder configuration for an important date."""
    id: str
    date_id: str
    reminder_offset: int
    status: str = "pending"
    reminder_time: Optional[datetime] = None
    content: Optional[str] = None


@dataclass(frozen=True)
class HolidayPlanDTO:
    """A holiday preparation plan."""
    id: str
    family_id: str
    holiday_type: str
    holiday_year: int
    content: Optional[Dict[str, Any]] = None
    tasks_created: int = 0


class IDateService(ABC):
    """Important date CRUD + holiday templates."""

    @abstractmethod
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
    ) -> ImportantDateDTO:
        """Create an important date with optional reminder chain."""
        ...

    @abstractmethod
    async def get_date(
        self, date_id: str, family_id: str,
    ) -> Optional[ImportantDateDTO]:
        """Get a single important date by ID."""
        ...

    @abstractmethod
    async def list_dates(
        self, family_id: str,
        date_type: Optional[str] = None,
    ) -> List[ImportantDateDTO]:
        """List important dates for a family."""
        ...

    @abstractmethod
    async def update_date(
        self, date_id: str, family_id: str,
        updates: Dict[str, Any],
    ) -> ImportantDateDTO:
        """Update an important date."""
        ...

    @abstractmethod
    async def delete_date(
        self, date_id: str, family_id: str,
    ) -> bool:
        """Delete an important date. Returns True if deleted."""
        ...

    @abstractmethod
    async def get_upcoming(
        self, family_id: str, days: int = 30,
    ) -> List[ImportantDateDTO]:
        """Get dates approaching within N days."""
        ...

    @abstractmethod
    async def get_holidays(
        self, year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get holiday list for a year."""
        ...


class IReminderService(ABC):
    """Smart reminder strategy (30d/7d/1d/same-day chain)."""

    @abstractmethod
    async def create_reminders_for_date(
        self, date_id: str, reminder_days: List[int],
        target_date: date,
    ) -> List[DateReminderDTO]:
        """Create a full reminder chain for an important date."""
        ...

    @abstractmethod
    async def get_due_reminders(
        self, family_id: str,
    ) -> List[Dict[str, Any]]:
        """Get reminders that are due today."""
        ...

    @abstractmethod
    async def mark_sent(self, reminder_id: str) -> None:
        """Mark a reminder as sent."""
        ...

    @abstractmethod
    async def mark_acknowledged(self, reminder_id: str) -> None:
        """Mark a reminder as acknowledged/clicked by user."""
        ...

    @abstractmethod
    async def cancel_reminders(self, date_id: str) -> int:
        """Cancel all pending reminders for a date. Returns count cancelled."""
        ...

    @abstractmethod
    async def generate_smart_schedule(
        self, date_id: str, date_type: str,
        target_date: date,
    ) -> List[DateReminderDTO]:
        """Generate a smart reminder schedule based on date type."""
        ...

    @abstractmethod
    async def reschedule_for_next_occurrence(
        self, date_id: str, next_date: date,
        reminder_days: Optional[List[int]] = None,
    ) -> List[DateReminderDTO]:
        """Cancel existing and reschedule reminders for next occurrence."""
        ...
