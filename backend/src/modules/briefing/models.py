"""Briefing module SQLAlchemy models.

Tables owned by this module:
    - user_briefing_settings: user briefing preferences (schedule_hours, timezone, enabled_modules)
    - user_insights: AI-generated insights about schedule, relationships, tasks
    - preparation_plans: proactive event preparation plans
    - preparation_tasks: tasks within preparation plans
"""
import uuid
from datetime import datetime, date
from enum import Enum as PyEnum
from typing import Optional, Dict, Any, List
from uuid import uuid4

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ...core.utils.timezone import utc_now, local_today
from ...db.session import Base


# ---------------------------------------------------------------------------
# Insight enums (InsightType imported from canonical source)
# ---------------------------------------------------------------------------

from ..insight.models import InsightType  # noqa: F401


class InsightStatus(str, PyEnum):
    """Status of an insight."""
    PENDING = "pending"
    PUSHED = "pushed"
    READ = "read"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"


class InsightFeedback(str, PyEnum):
    """User feedback on insights."""
    USEFUL = "useful"
    IGNORED = "ignored"
    NEVER_AGAIN = "never_again"


# ---------------------------------------------------------------------------
# UserInsight table
# ---------------------------------------------------------------------------


class UserInsight(Base):
    """AI-generated insight about the user's activities, relationships, or schedule."""

    __tablename__ = "user_insights"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(UUID(as_uuid=True), nullable=True)

    insight_type = Column(
        String(30), nullable=False,
        comment="time, relationship, favor, efficiency, health, finance, memory",
    )
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)

    importance_score = Column(Integer, nullable=False, default=50)
    urgency_score = Column(Integer, nullable=False, default=50)

    related_event_id = Column(UUID(as_uuid=True), nullable=True)
    related_important_date_id = Column(UUID(as_uuid=True), nullable=True)
    related_trip_id = Column(UUID(as_uuid=True), nullable=True)
    related_person_id = Column(UUID(as_uuid=True), nullable=True)

    status = Column(
        String(20), nullable=False, default="pending",
        comment="pending, pushed, read, actioned, dismissed",
    )
    push_time = Column(DateTime(timezone=True), nullable=True)
    read_time = Column(DateTime(timezone=True), nullable=True)

    feedback = Column(String(20), nullable=True, comment="useful, ignored, never_again")
    feedback_at = Column(DateTime(timezone=True), nullable=True)

    suggested_action = Column(Text, nullable=True)
    action_taken = Column(Boolean, nullable=False, default=False)

    # Typed action chips (PLAN-003): stores List[ActionSpec] serialized as JSON.
    # Use Column(JSON) for ORM compatibility (not ARRAY(JSONB)).
    action_options = Column(JSON, nullable=True, default=None,
                            comment="List[ActionSpec] as JSON for typed action dispatch")

    extra_data = Column(JSONB, nullable=True, default=dict)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    semantic_dedup_key = Column(String(255), nullable=True, index=True,
                                comment="Entity dedup key: {insight_type}:{entity_type}:{entity_id}")

    source_type = Column(String(30), nullable=True, default="briefing",
                         comment="briefing, trip, association, memory")
    source_id = Column(UUID(as_uuid=True), nullable=True,
                       comment="Source record ID (memory_insight.id or event_association.id)")
    promoted_at = Column(DateTime(timezone=True), nullable=True,
                         comment="When promoted from source to user_insights")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<UserInsight(id={self.id}, type={self.insight_type}, title={self.title})>"

    @property
    def is_expired(self) -> bool:
        if self.expires_at:
            return utc_now() > self.expires_at
        return False

    @property
    def is_actionable(self) -> bool:
        return (
            self.status not in (InsightStatus.ACTIONED.value, InsightStatus.DISMISSED.value)
            and not self.is_expired
        )

    @property
    def combined_score(self) -> int:
        return int(self.importance_score * 0.6 + self.urgency_score * 0.4)

    def get_push_strategy(self) -> str:
        score = self.combined_score
        if score >= 80:
            return "immediate"
        elif score >= 60:
            return "daily_briefing"
        elif score >= 40:
            return "pending_list"
        else:
            return "no_push"

    def mark_as_pushed(self) -> None:
        self.status = InsightStatus.PUSHED.value
        self.push_time = utc_now()

    def mark_as_read(self) -> None:
        self.status = InsightStatus.READ.value
        self.read_time = utc_now()

    def record_feedback(self, fb: "InsightFeedback") -> None:
        self.feedback = fb.value
        self.feedback_at = utc_now()
        if fb == InsightFeedback.USEFUL:
            self.status = InsightStatus.ACTIONED.value
        else:
            self.status = InsightStatus.DISMISSED.value


class UserBriefingSettings(Base):
    """Per-user briefing preferences.

    Columns:
        morning_hour: hour to send morning briefing (0-23, default 7)
        afternoon_hour: hour to send afternoon briefing (0-23, default 12)
        evening_hour: hour to send evening briefing (0-23, default 20)
        timezone: IANA timezone name (e.g. 'Asia/Shanghai')
        enabled_modules: list of enabled briefing sections
        enabled: global on/off switch
    """

    __tablename__ = "user_briefing_settings"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)

    morning_hour = Column(Integer, nullable=False, default=7)
    afternoon_hour = Column(Integer, nullable=False, default=12)
    evening_hour = Column(Integer, nullable=False, default=20)
    timezone = Column(String(50), nullable=True)

    enabled_modules = Column(
        ARRAY(String),
        nullable=False,
        default=["today_events", "preparation", "weather", "favor"],
    )
    enabled = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


# ---------------------------------------------------------------------------
# Preparation models (moved from assistant/models/preparation.py)
# ---------------------------------------------------------------------------


class PreparationPlan(Base):
    """准备方案"""
    __tablename__ = "preparation_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    family_id = Column(UUID(as_uuid=True), nullable=False)
    event_type = Column(String(50), nullable=False)  # birthday, anniversary, holiday
    event_id = Column(UUID(as_uuid=True), nullable=False)
    event_date = Column(Date, nullable=False)
    member_id = Column(UUID(as_uuid=True))
    title = Column(String(200), nullable=False)
    plan_content = Column(JSONB, nullable=False)
    # plan_content structure:
    # {
    #     "gift_options": [{"id", "name", "price", "url", "deals": [...]}],
    #     "cake_options": [{"id", "shop_name", "name", "price", "url"}],
    #     "restaurant_options": [{"id", "name", "cuisine", "price_range", "url"}],
    #     "wish_templates": [{"id", "content", "style"}],
    #     "suggested_schedule": [{"date", "task", "description"}],
    #     "estimated_budget": 1000,
    # }
    status = Column(String(20), default="draft")  # draft, sent, adopted, completed, expired
    adopted_selections = Column(JSONB)  # User's selections when adopting
    adopted_at = Column(DateTime(timezone=True))
    notified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_preparation_plans_family_event", "family_id", "event_type", "event_id"),
        Index("ix_preparation_plans_status", "status", "event_date"),
    )

    @property
    def days_until_event(self) -> int:
        """计算距离事件还有多少天"""
        if not self.event_date:
            return -1
        delta = self.event_date - local_today()
        return delta.days

    @property
    def progress(self) -> Dict[str, Any]:
        """计算准备进度"""
        return {"total": 0, "completed": 0, "percentage": 0}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "family_id": str(self.family_id),
            "event_type": self.event_type,
            "event_id": str(self.event_id),
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "member_id": str(self.member_id) if self.member_id else None,
            "title": self.title,
            "plan_content": self.plan_content,
            "status": self.status,
            "adopted_selections": self.adopted_selections,
            "adopted_at": self.adopted_at.isoformat() if self.adopted_at else None,
            "days_until_event": self.days_until_event,
            "progress": self.progress,
            "tasks": [],
        }


class PreparationTask(Base):
    """准备任务"""
    __tablename__ = "preparation_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    plan_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(String(200), nullable=False)
    task_type = Column(String(50))  # gift, cake, restaurant, decoration, wish, etc.
    assignee_id = Column(UUID(as_uuid=True))
    due_date = Column(Date)
    status = Column(String(20), default="pending")  # pending, in_progress, completed, skipped
    completed_at = Column(DateTime(timezone=True))
    task_metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_preparation_tasks_plan", "plan_id", "status"),
    )

    @property
    def is_overdue(self) -> bool:
        """检查任务是否已逾期"""
        if not self.due_date or self.status == "completed":
            return False
        return self.due_date < local_today()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "plan_id": str(self.plan_id),
            "title": self.title,
            "task_type": self.task_type,
            "assignee_id": str(self.assignee_id) if self.assignee_id else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.task_metadata,
            "is_overdue": self.is_overdue,
        }


# Status constants for preparation (used by services)
class PreparationStatus:
    DRAFT = "draft"
    SENT = "sent"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    ADOPTED = "adopted"
    COMPLETED = "completed"
    EXPIRED = "expired"
