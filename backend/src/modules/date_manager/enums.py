"""Date Manager enums.

Shared enum definitions used across date_models.py, reminder_models.py, and holiday_models.py.
Split from models.py to keep file sizes under 800 lines.
"""

from enum import Enum as PyEnum


class DateType(str, PyEnum):
    """Important date type."""
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"
    HOLIDAY = "holiday"
    HOLIDAY_LEGAL = "holiday_legal"  # Legal/public holidays (法定节假日)
    HOLIDAY_LUNAR = "holiday_lunar"  # Lunar calendar holidays (农历节日)
    HOLIDAY_SOLAR_TERM = "holiday_solar_term"  # 24 solar terms (二十四节气)
    VACCINE = "vaccine"
    MEDICAL_CHECK = "medical_check"
    CUSTOM = "custom"


class ReminderChannel(str, PyEnum):
    """Reminder delivery channel."""
    PUSH = "push"  # Push notification
    SMS = "sms"  # SMS
    EMAIL = "email"  # Email
    WECHAT = "wechat"  # WeChat service notification
    APP = "app"  # In-app notification


class ReminderStatus(str, PyEnum):
    """Reminder status."""
    PENDING = "pending"  # Scheduled, not sent yet
    SENT = "sent"  # Successfully sent
    FAILED = "failed"  # Failed to send
    SKIPPED = "skipped"  # Skipped by user
    CLICKED = "clicked"  # User clicked/viewed


class OccurrenceStatus(str, PyEnum):
    """Date occurrence status."""
    PENDING = "pending"  # Upcoming occurrence
    COMPLETED = "completed"  # Past occurrence, completed
    SKIPPED = "skipped"  # User skipped this occurrence
    MISSED = "missed"  # Missed (past date, no action)


class RecurrenceFreq(str, PyEnum):
    """Recurrence frequency (follows iCalendar RFC 5545)."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class ReminderType(str, PyEnum):
    """Types of event reminders."""
    PREPARATION = "preparation"  # Prepare for event
    ACTION = "action"            # Take an action
    WEATHER = "weather"          # Weather-related
    ITEM = "item"                # Bring items
    FOLLOWUP = "followup"        # Follow up after event


class EventReminderStatus(str, PyEnum):
    """Status of an event reminder."""
    PENDING = "pending"
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    SNOOZED = "snoozed"
    CANCELLED = "cancelled"


class HolidayCategory(str, PyEnum):
    """Holiday category for reminder strategy."""
    MAJOR = "major"  # Major holidays - 30 days advance reminder
    MINOR = "minor"  # Minor holidays - 7 days advance reminder
    SOLAR_TERM = "solar_term"  # Solar terms - 3 days advance reminder
