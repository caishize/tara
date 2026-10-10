"""Gift module enums.

Shared enum definitions used across all gift models and services.
"""
from enum import Enum as PyEnum


class RecommendStatus(str, PyEnum):
    """Gift recommendation status."""
    PENDING = "pending"
    VIEWED = "viewed"
    SELECTED = "selected"
    PURCHASED = "purchased"
    EXPIRED = "expired"
    REJECTED = "rejected"


class OccasionType(str, PyEnum):
    """Gift occasion type."""
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"
    HOLIDAY = "holiday"
    GRADUATION = "graduation"
    WEDDING = "wedding"
    NEWBORN = "newborn"
    HOUSEWARMING = "housewarming"
    PROMOTION = "promotion"
    RECOVERY = "recovery"
    CUSTOM = "custom"


class GiftCategory(str, PyEnum):
    """Gift category classification."""
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    JEWELRY = "jewelry"
    COSMETICS = "cosmetics"
    HEALTH = "health"
    BOOKS = "books"
    TOYS = "toys"
    SPORTS = "sports"
    HOME = "home"
    FOOD = "food"
    EXPERIENCE = "experience"
    CUSTOM = "custom"


class GiftType(str, PyEnum):
    """Gift recommendation type."""
    ROMANTIC = "romantic"
    PRACTICAL = "practical"
    LUXURY = "luxury"
    EXPERIENCE = "experience"
    EMOTIONAL = "emotional"
    TRADITIONAL = "traditional"


class FeedbackRating(str, PyEnum):
    """Gift feedback rating."""
    LOVE_IT = "love_it"
    LIKE_IT = "like_it"
    NEUTRAL = "neutral"
    DISLIKE = "dislike"
    HATE_IT = "hate_it"


class TriggerSource(str, PyEnum):
    """Recommendation trigger source."""
    AUTO_DATE = "auto_date"
    USER_REQUEST = "user_request"
    BATCH_HOLIDAY = "batch_holiday"
    MANUAL = "manual"
    REMINDER = "reminder"


class TaskStatus(str, PyEnum):
    """Gift task status.

    Design state machine:
      discovered -> recommended -> purchased -> shipped -> completed
    Internal states (not user-visible): pending, generating, failed, cancelled, expired
    """
    # User-visible lifecycle states (per design doc)
    DISCOVERED = "discovered"
    RECOMMENDED = "recommended"
    PURCHASED = "purchased"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    # Internal / system states
    PENDING = "pending"
    SCHEDULED = "scheduled"
    GENERATING = "generating"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class UpdateStatus(str, PyEnum):
    """Status of data update tasks."""
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class DateType(str, PyEnum):
    """Type of date for occasions."""
    SOLAR = "solar"
    LUNAR = "lunar"
    RELATIVE = "relative"


class WarningLevel(str, PyEnum):
    """Dedup warning level."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
