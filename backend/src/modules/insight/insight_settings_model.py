"""
User Insight Settings Model - Configurable insight cycle parameters

Canonical definition for the insight module.
Allows users to customize:
- Emotion pattern analysis window
- Relationship reminder threshold
- Insight expiry time
- Old plan follow-up threshold
- Upcoming trip check window
"""

from typing import Dict, Any, Optional
from uuid import uuid4

from sqlalchemy import Column, Integer, Boolean, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from ...core.utils.timezone import utc_now, DEFAULT_TIMEZONE_NAME
from ...db.session import Base


class UserInsightSettings(Base):
    """
    User-configurable settings for insight generation cycles.

    Allows customization of various thresholds and time windows
    used by the proactive insight service.
    """
    __tablename__ = "user_insight_settings"
    __table_args__ = (
        Index("ix_insight_settings_family", "family_id"),
        {"extend_existing": True},
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, unique=True, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    # Cycle configuration (in days)
    emotion_pattern_window_days = Column(Integer, nullable=False, default=7)
    """Number of days to analyze for emotion patterns (1-30, default: 7)"""

    relationship_reminder_threshold_days = Column(Integer, nullable=False, default=90)
    """Days without contact before reminder is generated (7-365, default: 90)"""

    insight_expiry_days = Column(Integer, nullable=False, default=7)
    """Number of days before an insight expires (1-30, default: 7)"""

    old_plan_followup_threshold_days = Column(Integer, nullable=False, default=14)
    """Days for a plan to be considered old and need follow-up (1-60, default: 14)"""

    upcoming_trip_check_days = Column(Integer, nullable=False, default=7)
    """Days ahead to check for upcoming trips (1-30, default: 7)"""

    # Curation settings
    curation_schedule_hour = Column(Integer, nullable=False, default=2)
    """Hour of day to run timeline curation (0-23, default: 2 = 2:00 AM)"""

    curation_days_ahead = Column(Integer, nullable=False, default=14)
    """Days ahead to curate in timeline (1-30, default: 14)"""

    auto_curate_on_trip_create = Column(Boolean, nullable=False, default=True)
    """Whether to auto-curate when trip plan is created (default: true)"""

    curation_interval_minutes = Column(Integer, nullable=False, default=60)
    """Minimum interval between curation runs in minutes (15-1440, default: 60)"""

    auto_curate_on_event_change = Column(Boolean, nullable=False, default=True)
    """Whether to auto-curate when events are created/updated/deleted (default: true)"""

    # Per-user schedule preferences (unified dispatcher)
    briefing_schedule_hour = Column(Integer, nullable=False, default=8)
    """Hour of day for daily briefing generation (0-23, default: 8 = 8:00 AM)"""

    insights_schedule_hour = Column(Integer, nullable=False, default=6)
    """Hour of day for daily insight generation (0-23, default: 6 = 6:00 AM)"""

    # Hygiene settings
    hygiene_enabled = Column(Boolean, nullable=False, default=True)
    """Whether daily event hygiene cleanup is enabled (default: true)"""

    inactive_retention_days = Column(Integer, nullable=False, default=7)
    """Days to retain is_active=False events before hard-delete (1-90, default: 7)"""

    cancelled_retention_days = Column(Integer, nullable=False, default=30)
    """Days to retain cancelled events before hard-delete (1-365, default: 30)"""

    # User timezone
    timezone = Column(
        String(50), nullable=True, server_default=DEFAULT_TIMEZONE_NAME,
        comment="User timezone for schedule calculations (IANA tz name)"
    )
    """IANA timezone name (e.g. 'Asia/Shanghai', 'America/New_York')"""

    # Per-wave delivery configuration (restored from migration 125)
    delivery_waves = Column(
        JSONB,
        nullable=True,
        default=None,
        comment="Per-wave delivery configuration: {morning: {enabled, hour, max_items}, ...}",
    )
    """JSONB dict keyed by wave name (morning/noon/evening/night), each with
    optional overrides: enabled (bool), hour (int), max_items (int)."""

    last_consolidation_at = Column(DateTime(timezone=True), nullable=True,
                                    comment="Last time insight consolidation ran")
    last_association_promotion_at = Column(DateTime(timezone=True), nullable=True,
                                           comment="Last time EA promotion ran")

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    # Default values for easy reference
    DEFAULTS = {
        "emotion_pattern_window_days": 7,
        "relationship_reminder_threshold_days": 90,
        "insight_expiry_days": 7,
        "old_plan_followup_threshold_days": 14,
        "upcoming_trip_check_days": 7,
        "curation_schedule_hour": 2,
        "curation_days_ahead": 14,
        "auto_curate_on_trip_create": True,
        "curation_interval_minutes": 60,
        "auto_curate_on_event_change": True,
        "briefing_schedule_hour": 8,
        "insights_schedule_hour": 6,
        "hygiene_enabled": True,
        "inactive_retention_days": 7,
        "cancelled_retention_days": 30,
        "timezone": DEFAULT_TIMEZONE_NAME,
    }

    # Valid ranges for each setting (excludes boolean fields)
    RANGES = {
        "emotion_pattern_window_days": (1, 30),
        "relationship_reminder_threshold_days": (7, 365),
        "insight_expiry_days": (1, 30),
        "old_plan_followup_threshold_days": (1, 60),
        "upcoming_trip_check_days": (1, 30),
        "curation_schedule_hour": (0, 23),
        "curation_days_ahead": (1, 30),
        "curation_interval_minutes": (15, 1440),
        "briefing_schedule_hour": (0, 23),
        "insights_schedule_hour": (0, 23),
        "inactive_retention_days": (1, 90),
        "cancelled_retention_days": (1, 365),
    }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "emotion_pattern_window_days": self.emotion_pattern_window_days,
            "relationship_reminder_threshold_days": self.relationship_reminder_threshold_days,
            "insight_expiry_days": self.insight_expiry_days,
            "old_plan_followup_threshold_days": self.old_plan_followup_threshold_days,
            "upcoming_trip_check_days": self.upcoming_trip_check_days,
            "curation_schedule_hour": self.curation_schedule_hour,
            "curation_days_ahead": self.curation_days_ahead,
            "auto_curate_on_trip_create": self.auto_curate_on_trip_create,
            "curation_interval_minutes": self.curation_interval_minutes,
            "auto_curate_on_event_change": self.auto_curate_on_event_change,
            "briefing_schedule_hour": self.briefing_schedule_hour,
            "insights_schedule_hour": self.insights_schedule_hour,
            "hygiene_enabled": self.hygiene_enabled,
            "inactive_retention_days": self.inactive_retention_days,
            "cancelled_retention_days": self.cancelled_retention_days,
            "timezone": self.timezone or DEFAULT_TIMEZONE_NAME,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_defaults(cls) -> Dict[str, int]:
        """Get default values as a dictionary."""
        return cls.DEFAULTS.copy()

    @classmethod
    def validate_value(cls, field: str, value: int) -> bool:
        """Validate that a value is within the allowed range."""
        if field not in cls.RANGES:
            return False
        min_val, max_val = cls.RANGES[field]
        return min_val <= value <= max_val

    @classmethod
    def clamp_value(cls, field: str, value: int) -> int:
        """Clamp a value to the allowed range."""
        if field not in cls.RANGES:
            return value
        min_val, max_val = cls.RANGES[field]
        return max(min_val, min(max_val, value))
