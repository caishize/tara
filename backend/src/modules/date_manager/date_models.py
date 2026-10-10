"""Core date ORM models: ImportantDate, DateReminder, DateOccurrence.

Split from models.py to keep file sizes under 800 lines.
"""

import uuid
from datetime import date as date_type
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Column, String, Integer, Boolean, Date, DateTime, Text, Float,
    ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ...db.session import Base
from .enums import ReminderStatus, OccurrenceStatus

if TYPE_CHECKING:
    from ..member.models.member import Member


class ImportantDate(Base):
    """ImportantDate (重要日期) entity."""

    __tablename__ = "important_dates"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    member_id = Column(UUID(as_uuid=True), nullable=True)  # NULL for family-wide dates
    created_by = Column(UUID(as_uuid=True), nullable=False)

    # Basic Info
    title = Column(String(200), nullable=False)
    date_type = Column(String(50), nullable=False)  # DateType enum
    solar_date = Column(Date, nullable=False)  # Gregorian date (primary)

    # Lunar Info (optional)
    is_lunar = Column(Boolean, nullable=False, default=False)
    lunar_year = Column(Integer, nullable=True)
    lunar_month = Column(Integer, nullable=True)
    lunar_day = Column(Integer, nullable=True)
    lunar_leap = Column(Boolean, nullable=True)

    # Recurrence
    is_recurring = Column(Boolean, nullable=False, default=False)
    recurrence_rule = Column(JSONB, nullable=True)  # iCalendar-like rule

    # Reminder Settings
    reminder_offsets = Column(ARRAY(Integer), nullable=True)  # e.g., [-30, -7, -1, 0] days
    reminder_time = Column(String(5), nullable=True)  # HH:MM format, e.g., "09:00"
    reminder_channels = Column(ARRAY(String), nullable=True)  # List of ReminderChannel

    # Preparation lead days (E7 - configurable per date type)
    preparation_lead_days = Column(
        Integer, nullable=True, server_default="7",
        comment="Per-date preparation lead days (birthday=14d, spring_festival=30d, milestone=60d)",
    )

    # Metadata
    importance_level = Column(Integer, nullable=False, default=5)  # 1-10
    source = Column(String(50), nullable=False, default="manual")  # "manual", "conversation", "ocr"
    health_related = Column(Boolean, nullable=False, default=False)
    attachments = Column(ARRAY(String), nullable=True)  # URLs to uploaded files
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    member = relationship(
        "Member",
        foreign_keys=[member_id],
        primaryjoin="ImportantDate.member_id == Member.id",
        lazy="joined"
    )

    # Indexes
    __table_args__ = (
        Index("idx_date_family_solar", "family_id", "solar_date"),
        Index("idx_date_member", "member_id"),
        Index("idx_date_type", "date_type"),
    )

    def __repr__(self):
        return f"<ImportantDate(id={self.id}, title={self.title}, date={self.solar_date})>"

    def get_next_occurrence(self) -> "Optional[date_type]":
        """Calculate the next occurrence of this important date."""
        from datetime import date
        today = date.today()

        if not self.is_recurring:
            return self.solar_date

        if self.is_lunar and self.lunar_month and self.lunar_day:
            # For lunar dates, convert lunar to solar for this year and next year
            from lunarcalendar import Converter, Lunar

            try:
                # Try this year's lunar date
                lunar_this_year = Lunar(today.year, self.lunar_month, self.lunar_day, isleap=self.lunar_leap or False)
                solar_this_year = Converter.Lunar2Solar(lunar_this_year)
                this_year_date = date_type(solar_this_year.year, solar_this_year.month, solar_this_year.day)

                if this_year_date >= today:
                    return this_year_date

                # Already passed, try next year
                lunar_next_year = Lunar(today.year + 1, self.lunar_month, self.lunar_day, isleap=self.lunar_leap or False)
                solar_next_year = Converter.Lunar2Solar(lunar_next_year)
                return date_type(solar_next_year.year, solar_next_year.month, solar_next_year.day)
            except Exception:
                # Fallback to solar date if lunar conversion fails
                pass

        # For solar dates (or lunar fallback)
        month = self.solar_date.month
        day = self.solar_date.day

        # Try this year
        try:
            this_year = date_type(today.year, month, day)
            if this_year >= today:
                return this_year
            # Already passed, use next year
            return date_type(today.year + 1, month, day)
        except ValueError:
            # Invalid date (e.g., Feb 29 in non-leap year)
            # Try next year for leap year dates
            try:
                return date_type(today.year + 1, month, day)
            except ValueError:
                return None


class DateReminder(Base):
    """DateReminder (日期提醒) entity."""

    __tablename__ = "date_reminders"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    date_id = Column(UUID(as_uuid=True), ForeignKey("important_dates.id", ondelete="CASCADE"), nullable=False)
    # occurrence_id foreign key removed for P1 MVP (date_occurrences table doesn't exist yet - P3 feature)
    occurrence_id = Column(UUID(as_uuid=True), nullable=True)  # Will add FK when implementing recurring dates

    # Reminder Timing
    reminder_time = Column(DateTime(timezone=True), nullable=False)  # When to send
    actual_sent_time = Column(DateTime(timezone=True), nullable=True)  # When actually sent
    reminder_offset = Column(Integer, nullable=False)  # Days before event (e.g., -30, -7, 0)

    # Reminder Content
    reminder_content = Column(Text, nullable=False)
    channel = Column(String(20), nullable=False)  # ReminderChannel enum

    # Status
    status = Column(String(20), nullable=False, default=ReminderStatus.PENDING.value)
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)

    # User Interaction
    user_clicked = Column(Boolean, nullable=False, default=False)
    clicked_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    date = relationship("ImportantDate", backref="reminders")

    # Indexes
    __table_args__ = (
        Index("idx_reminder_date", "date_id"),
        Index("idx_reminder_time", "reminder_time"),
        Index("idx_reminder_status", "status"),
        Index("idx_reminder_pending", "status", "reminder_time",
              postgresql_where=(status == ReminderStatus.PENDING.value)),
    )

    def __repr__(self):
        return f"<DateReminder(id={self.id}, time={self.reminder_time}, status={self.status})>"


class DateOccurrence(Base):
    """DateOccurrence (日期发生记录) entity."""

    __tablename__ = "date_occurrences"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Key
    parent_date_id = Column(UUID(as_uuid=True), ForeignKey("important_dates.id", ondelete="CASCADE"), nullable=False)

    # Occurrence Info
    occurrence_date = Column(DateTime(timezone=True), nullable=False)  # Specific occurrence date/time
    status = Column(String(20), nullable=False, default=OccurrenceStatus.PENDING.value)

    # User Response
    user_response = Column(String(50), nullable=True)  # "acknowledged", "completed", "skipped"
    response_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    parent_date = relationship("ImportantDate", backref="occurrences")

    # Indexes
    __table_args__ = (
        Index("idx_occurrence_parent", "parent_date_id"),
        Index("idx_occurrence_date", "occurrence_date"),
        Index("idx_occurrence_status", "status"),
    )

    def __repr__(self):
        return f"<DateOccurrence(id={self.id}, date={self.occurrence_date}, status={self.status})>"
