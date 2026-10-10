"""Relationship module SQLAlchemy models.

Canonical location for:
    - favor_records: favor exchanges
    - social_events: social events
    - Enums: EventType, InteractionType, FavorDirection, etc.

Note: person_profiles and relationship_edges are owned by the member module.
This module reads them via the member module's interface.
"""

from enum import Enum as PyEnum
import uuid

from sqlalchemy import (
    Column, String, Numeric, Date, Boolean, Text, Integer,
    ForeignKey, Index, DateTime,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ...db.session import Base


# ---------------------------------------------------------------------------
# Enums (moved from relationship_management/models/enums.py)
# ---------------------------------------------------------------------------


class EventType(str, PyEnum):
    """Social event type for 人情往来."""
    WEDDING = "wedding"              # 婚礼
    BABY_FULL_MOON = "baby_month"    # 满月酒
    BIRTHDAY = "birthday"            # 生日
    FUNERAL = "funeral"              # 丧事
    HOUSEWARMING = "housewarming"    # 乔迁
    ILLNESS = "illness"              # 生病慰问
    GRADUATION = "graduation"        # 升学
    PROMOTION = "promotion"          # 升职
    LOAN = "loan"                    # 借款
    FAMILY_GATHERING = "family_gathering"
    BIRTHDAY_PARTY = "birthday_party"
    HOLIDAY_CELEBRATION = "holiday_celebration"
    CASUAL_VISIT = "casual_visit"
    BUSINESS = "business"
    OTHER = "other"


class InteractionType(str, PyEnum):
    """Interaction type."""
    PHONE_CALL = "phone_call"
    VIDEO_CALL = "video_call"
    IN_PERSON = "in_person"
    GIFT_GIVEN = "gift_given"
    GIFT_RECEIVED = "gift_received"
    HELP_PROVIDED = "help_provided"
    HELP_RECEIVED = "help_received"
    MESSAGE = "message"
    OTHER = "other"


class FavorDirection(str, PyEnum):
    """Direction of favor exchange."""
    GIVE = "give"       # 送出
    RECEIVE = "receive"  # 收到


class FavorStatus(str, PyEnum):
    """Status of favor record."""
    PENDING = "pending"     # 待回礼
    RETURNED = "returned"   # 已回礼
    SETTLED = "settled"     # 已结清 (for loans)


class GiftType(str, PyEnum):
    """Type of gift/favor."""
    CASH = "cash"           # 现金
    GIFT = "gift"           # 实物礼物
    SERVICE = "service"     # 服务/帮忙


class EventStatus(str, PyEnum):
    """Status of social event."""
    UPCOMING = "upcoming"       # 即将举办
    ONGOING = "ongoing"         # 进行中
    COMPLETED = "completed"     # 已完成
    CANCELLED = "cancelled"     # 已取消


class ContactTier(str, PyEnum):
    """Contact relationship tier (关系圈层)."""
    CORE = "core"           # 核心圈 (维护周期30天)
    IMPORTANT = "important"  # 重要圈 (维护周期90天)
    GENERAL = "general"     # 一般圈 (维护周期365天)


class GiftOccasion(str, PyEnum):
    """Gift giving occasion."""
    SPRING_FESTIVAL = "spring_festival"   # 春节
    MID_AUTUMN = "mid_autumn"             # 中秋
    DRAGON_BOAT = "dragon_boat"           # 端午
    BIRTHDAY = "birthday"                 # 生日
    TEACHERS_DAY = "teachers_day"         # 教师节
    NEW_YEAR = "new_year"                 # 元旦
    VISIT = "visit"                       # 探望
    OTHER = "other"                       # 其他


class ReminderType(str, PyEnum):
    """Type of favor reminder."""
    FAVOR_RETURN = "favor_return"           # 回礼提醒
    FESTIVAL_GIFT = "festival_gift"         # 节日送礼提醒
    RELATIONSHIP_MAINTAIN = "maintain"      # 关系维护提醒
    LOAN_DUE = "loan_due"                   # 借款到期提醒
    EVENT_UPCOMING = "event"                # 事件提醒


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class FavorRecord(Base):
    """FavorRecord entity for tracking 人情往来."""
    __tablename__ = "favor_records"
    __table_args__ = (
        Index("idx_favor_family_contact", "family_id", "contact_id"),
        Index("idx_favor_family_date", "family_id", "recorded_at"),
        Index("idx_favor_status", "family_id", "status"),
        {"extend_existing": True},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    contact_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    contact_name = Column(String(100), nullable=False)

    # Event info
    event_type = Column(String(50), nullable=False)
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("social_events.id"),
        nullable=True,
        index=True,
    )

    # Amount
    amount = Column(Numeric(10, 2), nullable=False)
    direction = Column(String(20), nullable=False)   # give | receive
    gift_type = Column(String(20), default="cash")    # cash | gift | service

    # Status
    status = Column(String(20), default="pending")    # pending | returned | settled

    # Metadata
    recorded_at = Column(Date, nullable=False)
    note = Column(Text, nullable=True)
    is_private = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    event = relationship("SocialEvent", back_populates="favors")

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "family_id": str(self.family_id),
            "contact_id": str(self.contact_id) if self.contact_id else None,
            "contact_name": self.contact_name,
            "event_type": self.event_type,
            "event_id": str(self.event_id) if self.event_id else None,
            "amount": float(self.amount) if self.amount else 0,
            "direction": self.direction,
            "gift_type": self.gift_type,
            "status": self.status,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "note": self.note,
            "is_private": self.is_private,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SocialEvent(Base):
    """SocialEvent entity for 红白喜事管理."""
    __tablename__ = "social_events"
    __table_args__ = (
        Index("idx_event_family_date", "family_id", "event_date"),
        Index("idx_event_status", "family_id", "status"),
        {"extend_existing": True},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Event details
    title = Column(String(200), nullable=False)
    event_type = Column(String(50), nullable=False)
    event_date = Column(Date, nullable=False)
    location = Column(String(300), nullable=True)

    # Financial tracking
    budget = Column(Numeric(10, 2), nullable=True)
    actual_cost = Column(Numeric(10, 2), nullable=True)
    total_received = Column(Numeric(10, 2), default=0)
    total_given = Column(Numeric(10, 2), default=0)
    guest_count = Column(Integer, default=0)

    # Status and notes
    status = Column(String(20), default="upcoming")
    note = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    favors = relationship(
        "FavorRecord", back_populates="event", cascade="all, delete-orphan",
    )

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "family_id": str(self.family_id),
            "title": self.title,
            "event_type": self.event_type,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "location": self.location,
            "budget": float(self.budget) if self.budget else None,
            "actual_cost": float(self.actual_cost) if self.actual_cost else None,
            "total_received": float(self.total_received) if self.total_received else 0,
            "total_given": float(self.total_given) if self.total_given else 0,
            "guest_count": self.guest_count,
            "status": self.status,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def calculate_balance(self) -> float:
        """Calculate event financial balance (received - given - cost)."""
        received = float(self.total_received or 0)
        given = float(self.total_given or 0)
        cost = float(self.actual_cost or 0)
        return received - given - cost


__all__ = [
    # Enums
    "EventType",
    "InteractionType",
    "FavorDirection",
    "FavorStatus",
    "GiftType",
    "EventStatus",
    "ContactTier",
    "GiftOccasion",
    "ReminderType",
    # ORM models
    "FavorRecord",
    "SocialEvent",
]
