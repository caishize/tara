"""Date Manager module - never forget any important date.

Manages birthdays, anniversaries, medical checkups, etc.
with smart reminder chains (30d/7d/1d/same-day).
"""

from .interface import (
    IDateService,
    IReminderService,
    ImportantDateDTO,
    DateReminderDTO,
    HolidayPlanDTO,
)
from .date_service import DateService
from .reminder_service import ReminderService

__all__ = [
    # Interfaces
    "IDateService",
    "IReminderService",
    # DTOs
    "ImportantDateDTO",
    "DateReminderDTO",
    "HolidayPlanDTO",
    # Implementations
    "DateService",
    "ReminderService",
]
