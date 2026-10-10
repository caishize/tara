"""Views module models.

Canonical home for FamilyTask, TodayItem, and AISuggestion.
Also re-exports curation models used by views services for convenience.
"""

from datetime import datetime, date, time
from typing import Optional, Dict, Any, List
from uuid import uuid4

from sqlalchemy import (
    Column, String, Text, DateTime, Date, Time,
    Index, Integer,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from ...db.session import Base
from ...core.utils.timezone import utc_now, local_today
from ..curation.models import CuratedEvent, PreparationItem, EventAssociation


# Status constants for TodayItem
class TodayItemStatus:
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    SNOOZED = "snoozed"
    DISMISSED = "dismissed"


__all__ = [
    "FamilyTask",
    "TodayItem",
    "TodayItemStatus",
    "AISuggestion",
    "CuratedEvent",
    "PreparationItem",
    "EventAssociation",
]


class FamilyTask(Base):
    """家庭协作任务"""
    __tablename__ = "family_tasks"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    family_id = Column(PGUUID(as_uuid=True), nullable=False)
    parent_task_id = Column(PGUUID(as_uuid=True))
    title = Column(String(200), nullable=False)
    description = Column(Text)
    task_type = Column(String(50))  # preparation, shopping, routine, health, household, etc.
    creator_id = Column(PGUUID(as_uuid=True), nullable=False)
    assignee_id = Column(PGUUID(as_uuid=True))
    due_date = Column(Date)
    due_time = Column(Time)
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    status = Column(String(20), default="pending")  # pending, in_progress, completed, cancelled
    completed_at = Column(DateTime(timezone=True))
    task_metadata = Column("metadata", JSONB)  # Additional task data (column name is 'metadata' in DB)
    # metadata structure:
    # {
    #     "source": {"type": "preparation_plan", "id": "..."},
    #     "linked_items": [{"type": "shopping_item", "id": "..."}],
    #     "reminders": [{"time": "...", "sent": false}],
    #     "notes": "..."
    # }
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    # Note: subtasks relationship removed due to FK constraints removal

    __table_args__ = (
        Index("ix_family_tasks_assignee", "assignee_id", "status"),
        Index("ix_family_tasks_family", "family_id", "status"),
        Index("ix_family_tasks_parent", "parent_task_id"),
        Index("ix_family_tasks_due", "due_date", "status"),
    )

    # Priority weights for sorting
    PRIORITY_WEIGHTS = {
        "urgent": 4,
        "high": 3,
        "normal": 2,
        "low": 1,
    }

    @property
    def is_parent_task(self) -> bool:
        """是否是父任务"""
        return self.parent_task_id is None

    @property
    def is_overdue(self) -> bool:
        """是否已逾期"""
        if not self.due_date or self.status in ["completed", "cancelled"]:
            return False
        if self.due_date < local_today():
            return True
        if self.due_date == local_today() and self.due_time:
            return utc_now().time() > self.due_time
        return False

    @property
    def priority_weight(self) -> int:
        """获取优先级权重"""
        return self.PRIORITY_WEIGHTS.get(self.priority, 2)

    @property
    def due_datetime(self) -> Optional[datetime]:
        """获取截止日期时间"""
        if not self.due_date:
            return None
        if self.due_time:
            return datetime.combine(self.due_date, self.due_time)
        return datetime.combine(self.due_date, time(23, 59, 59))

    def get_progress(self) -> Dict[str, Any]:
        """获取任务进度"""
        # Note: subtasks relationship removed, so we just report this task's status
        is_completed = self.status == "completed"
        return {
            "total": 1,
            "completed": 1 if is_completed else 0,
            "percentage": 100 if is_completed else 0,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "family_id": str(self.family_id),
            "parent_task_id": str(self.parent_task_id) if self.parent_task_id else None,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "creator_id": str(self.creator_id),
            "assignee_id": str(self.assignee_id) if self.assignee_id else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "due_time": self.due_time.isoformat() if self.due_time else None,
            "due_datetime": self.due_datetime.isoformat() if self.due_datetime else None,
            "priority": self.priority,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.task_metadata,
            "is_parent_task": self.is_parent_task,
            "is_overdue": self.is_overdue,
            "progress": self.get_progress(),
        }


class TodayItem(Base):
    """今日待办聚合项"""
    __tablename__ = "today_items"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    family_id = Column(PGUUID(as_uuid=True), nullable=False)
    user_id = Column(PGUUID(as_uuid=True))
    source_type = Column(String(50), nullable=False)  # date, task, health, shopping, travel, etc.
    source_id = Column(PGUUID(as_uuid=True), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    urgency = Column(String(20), nullable=False)  # urgent, today, upcoming
    due_datetime = Column(DateTime(timezone=True))
    actions = Column(JSONB)  # [{type: "navigate", label: "导航", url: "/..."}, ...]
    status = Column(String(20), default="pending")  # pending, completed, snoozed, dismissed
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_today_items_family_status", "family_id", "status", "urgency"),
        Index("ix_today_items_user", "user_id", "status"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "family_id": str(self.family_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "source_type": self.source_type,
            "source_id": str(self.source_id),
            "title": self.title,
            "description": self.description,
            "urgency": self.urgency,
            "due_datetime": self.due_datetime.isoformat() if self.due_datetime else None,
            "actions": self.actions or [],
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AISuggestion(Base):
    """AI建议"""
    __tablename__ = "ai_suggestions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    family_id = Column(PGUUID(as_uuid=True), nullable=False)
    user_id = Column(PGUUID(as_uuid=True))
    suggestion_type = Column(String(50), nullable=False)  # weekend_planning, birthday_prep, shopping_deal, etc.
    content = Column(Text, nullable=False)
    actions = Column(JSONB)  # [{type, label, url}]
    context = Column(JSONB)  # Context that generated this suggestion
    priority = Column(Integer, default=0)  # Higher = more important
    valid_until = Column(DateTime(timezone=True))
    dismissed_at = Column(DateTime(timezone=True))
    acted_upon_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_ai_suggestions_family", "family_id", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "family_id": str(self.family_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "suggestion_type": self.suggestion_type,
            "content": self.content,
            "actions": self.actions or [],
            "context": self.context,
            "priority": self.priority,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "is_valid": self.valid_until is None or self.valid_until > utc_now(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
