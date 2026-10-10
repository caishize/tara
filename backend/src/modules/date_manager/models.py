"""Date Manager module models — re-export hub.

Actual ORM models live in:
- date_models.py:      ImportantDate, DateReminder, DateOccurrence
- reminder_models.py:  EventReminder, SmartReminder, UserActivityPattern
- holiday_models.py:   ChineseHolidayPlan + holiday config helpers
- enums.py:            All enum definitions

This file re-exports everything so existing ``from .models import X``
imports throughout the codebase continue to work unchanged.
"""

# Enums
from .enums import (
    DateType,
    ReminderChannel,
    ReminderStatus,
    OccurrenceStatus,
    RecurrenceFreq,
    ReminderType,
    EventReminderStatus,
    HolidayCategory,
)

# Core date models
from .date_models import (
    ImportantDate,
    DateReminder,
    DateOccurrence,
)

# Reminder models
from .reminder_models import (
    EventReminder,
    SmartReminder,
    UserActivityPattern,
)

# Holiday model + config helpers
from .holiday_models import (
    ChineseHolidayPlan,
    HolidayMetadata,
    MAJOR_HOLIDAYS,
    MINOR_HOLIDAYS,
    LUNAR_HOLIDAYS,
    SOLAR_TERMS,
    REMINDER_OFFSETS,
    HOLIDAY_TIPS,
    get_holiday_category,
    get_reminder_offsets,
    get_preparation_tips,
    is_major_holiday,
    is_lunar_holiday,
    is_solar_term,
    HolidayPlanStatus,
)


__all__ = [
    # Core models
    "ImportantDate",
    "DateReminder",
    "DateOccurrence",
    "ChineseHolidayPlan",
    "EventReminder",
    "SmartReminder",
    "UserActivityPattern",
    # Enums
    "DateType",
    "ReminderStatus",
    "ReminderChannel",
    "OccurrenceStatus",
    "RecurrenceFreq",
    "ReminderType",
    "EventReminderStatus",
    "HolidayCategory",
    # Holiday config helpers
    "HolidayMetadata",
    "MAJOR_HOLIDAYS",
    "MINOR_HOLIDAYS",
    "LUNAR_HOLIDAYS",
    "SOLAR_TERMS",
    "REMINDER_OFFSETS",
    "HOLIDAY_TIPS",
    "get_holiday_category",
    "get_reminder_offsets",
    "get_preparation_tips",
    "is_major_holiday",
    "is_lunar_holiday",
    "is_solar_term",
    "HolidayPlanStatus",
]
