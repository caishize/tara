"""Reminder ORM models: EventReminder, SmartReminder, UserActivityPattern.

Split from models.py to keep file sizes under 800 lines.
"""

import uuid
from datetime import datetime, date, time, timedelta
from typing import Dict, Any

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, Float, Time,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from uuid import uuid4

from ...db.session import Base
from ...core.utils.timezone import utc_now
from .enums import EventReminderStatus


class EventReminder(Base):
    """
    EventReminder (事件提醒) entity.

    Represents a reminder associated with an event or trip.
    """

    __tablename__ = "event_reminders"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User association
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Related entities
    event_id = Column(UUID(as_uuid=True), nullable=True)
    trip_id = Column(UUID(as_uuid=True), nullable=True)

    # Reminder content
    reminder_type = Column(
        String(30), nullable=False,
        comment="preparation, action, weather, item, followup"
    )
    content = Column(Text, nullable=False)

    # Trigger timing
    trigger_time = Column(DateTime(timezone=True), nullable=False)
    triggered = Column(Boolean, nullable=False, default=False)
    triggered_at = Column(DateTime(timezone=True), nullable=True)

    # Status
    status = Column(
        String(20), nullable=False, default="pending",
        comment="pending, triggered, acknowledged, snoozed, cancelled"
    )
    snooze_until = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default="now()")

    def __repr__(self):
        return f"<EventReminder(id={self.id}, type={self.reminder_type}, content={self.content[:30]}...)>"

    @property
    def is_due(self) -> bool:
        """Check if reminder is due to be triggered."""
        if self.triggered or self.status != EventReminderStatus.PENDING.value:
            return False

        now = datetime.now(self.trigger_time.tzinfo)

        # Check snooze
        if self.snooze_until and now < self.snooze_until:
            return False

        return now >= self.trigger_time

    @property
    def minutes_until(self) -> int:
        """Minutes until trigger time (negative if past)."""
        now = utc_now()
        return int((self.trigger_time - now).total_seconds() / 60)

    def trigger(self) -> None:
        """Mark reminder as triggered."""
        self.triggered = True
        self.triggered_at = utc_now()
        self.status = EventReminderStatus.TRIGGERED.value

    def acknowledge(self) -> None:
        """Mark reminder as acknowledged by user."""
        self.status = EventReminderStatus.ACKNOWLEDGED.value

    def snooze(self, minutes: int = 15) -> None:
        """Snooze reminder for specified minutes."""
        self.status = EventReminderStatus.SNOOZED.value
        self.snooze_until = utc_now() + timedelta(minutes=minutes)
        self.triggered = False

    def cancel(self) -> None:
        """Cancel the reminder."""
        self.status = EventReminderStatus.CANCELLED.value


class SmartReminder(Base):
    """智能提醒"""
    __tablename__ = "smart_reminders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    family_id = Column(UUID(as_uuid=True), nullable=False)
    source_type = Column(String(50), nullable=False)  # date, task, health, shopping, etc.
    source_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    urgency_level = Column(String(20), nullable=False)  # urgent, important, normal, low
    preferred_time = Column(Time)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    last_sent_at = Column(DateTime(timezone=True))
    next_send_at = Column(DateTime(timezone=True))
    acknowledged_at = Column(DateTime(timezone=True))
    status = Column(String(20), default="pending")  # pending, sent, acknowledged, snoozed, cancelled, expired
    strategy = Column(JSONB)  # Reminder strategy configuration
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_smart_reminders_next_send", "next_send_at", "status"),
        Index("ix_smart_reminders_user", "user_id", "status"),
    )

    # Urgency level strategies
    URGENCY_STRATEGIES = {
        "urgent": {
            "initial_delay_minutes": 0,
            "retry_intervals": [30, 60, 120],
            "max_retries": 5,
        },
        "important": {
            "initial_delay_minutes": None,  # Use preferred time
            "retry_intervals": [24 * 60],  # Once per day
            "max_retries": 3,
        },
        "normal": {
            "initial_delay_minutes": None,
            "retry_intervals": [48 * 60],  # Every other day
            "max_retries": 2,
        },
        "low": {
            "initial_delay_minutes": None,
            "retry_intervals": [7 * 24 * 60],  # Once per week
            "max_retries": 1,
        },
    }

    @property
    def can_retry(self) -> bool:
        """检查是否可以重试"""
        return self.retry_count < self.max_retries

    @property
    def next_retry_interval(self) -> int:
        """获取下次重试间隔（分钟）"""
        strategy = self.strategy or self.URGENCY_STRATEGIES.get(self.urgency_level, {})
        intervals = strategy.get("retry_intervals", [60])
        idx = min(self.retry_count, len(intervals) - 1)
        return intervals[idx]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "source_type": self.source_type,
            "source_id": str(self.source_id),
            "title": self.title,
            "content": self.content,
            "urgency_level": self.urgency_level,
            "preferred_time": self.preferred_time.isoformat() if self.preferred_time else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_sent_at": self.last_sent_at.isoformat() if self.last_sent_at else None,
            "next_send_at": self.next_send_at.isoformat() if self.next_send_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "status": self.status,
            "can_retry": self.can_retry,
        }


class UserActivityPattern(Base):
    """用户活跃模式"""
    __tablename__ = "user_activity_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    weekday_active_hours = Column(JSONB)  # [8, 9, 12, 13, 18, 19, 20, 21]
    weekend_active_hours = Column(JSONB)
    preferred_reminder_times = Column(JSONB)  # {morning: "08:00", evening: "20:00"}
    busy_patterns = Column(JSONB)  # Detected busy time patterns
    response_rate = Column(Float)  # Historical response rate (0-1)
    avg_response_time_minutes = Column(Integer)
    last_analyzed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    def get_preferred_time_for_urgency(self, urgency: str, target_date: date) -> datetime:
        """根据紧急程度和日期获取最佳提醒时间"""
        is_weekend = target_date.weekday() >= 5
        active_hours = self.weekend_active_hours if is_weekend else self.weekday_active_hours

        if not active_hours:
            # Default active hours
            active_hours = [9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20]

        # For urgent items, use earliest active hour
        if urgency == "urgent":
            hour = min(active_hours)
        # For others, prefer evening hours if available
        else:
            evening_hours = [h for h in active_hours if h >= 18]
            if evening_hours:
                hour = min(evening_hours)
            else:
                hour = max(active_hours)

        return datetime.combine(target_date, time(hour=hour, minute=0))

    def is_busy_at(self, check_time: datetime) -> bool:
        """检查指定时间是否在忙碌时段"""
        if not self.busy_patterns:
            return False

        day_of_week = check_time.weekday()
        hour = check_time.hour

        for pattern in self.busy_patterns:
            if (pattern.get("day_of_week") == day_of_week and
                pattern.get("start_hour", 0) <= hour < pattern.get("end_hour", 24) and
                pattern.get("confidence", 0) > 0.7):
                return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "weekday_active_hours": self.weekday_active_hours,
            "weekend_active_hours": self.weekend_active_hours,
            "preferred_reminder_times": self.preferred_reminder_times,
            "busy_patterns": self.busy_patterns,
            "response_rate": self.response_rate,
            "avg_response_time_minutes": self.avg_response_time_minutes,
            "last_analyzed_at": self.last_analyzed_at.isoformat() if self.last_analyzed_at else None,
        }
