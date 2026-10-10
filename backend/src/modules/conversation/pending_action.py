"""
PendingAction Model - Actions awaiting user confirmation.

Implements the "Action Decoupling" pattern from the architecture:
Agent generates pending actions, users confirm, then execution occurs.

This is the canonical definition. Other modules should import from here.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ...core.utils.timezone import utc_now
from ...db.session import Base


class ActionType(str, Enum):
    """Types of actions that require confirmation."""
    PURCHASE = "purchase"
    BOOK_TICKET = "book_ticket"
    TRANSFER_MONEY = "transfer_money"
    SEND_MESSAGE = "send_message"
    CREATE_EVENT = "create_event"
    CANCEL_BOOKING = "cancel_booking"
    DELETE_EVENT = "delete_event"
    RESCHEDULE_EVENT = "reschedule_event"
    SUGGEST_MEETING    = "suggest_meeting"     # 建议会面（顺便见面场景）
    SUGGEST_GREETING   = "suggest_greeting"    # 建议问候（久未联系场景）
    SUGGEST_GIFT       = "suggest_gift"        # 建议礼物/祝福（重要日期场景）
    SUGGEST_DEFER      = "suggest_defer"       # 建议推迟（日程减负场景）


class ActionStatus(str, Enum):
    """Status of a pending action."""
    PENDING = "pending"      # Awaiting user confirmation
    CONFIRMED = "confirmed"  # User confirmed, ready to execute
    REJECTED = "rejected"    # User rejected
    EXPIRED = "expired"      # TTL exceeded without action
    EXECUTED = "executed"    # Successfully executed
    FAILED = "failed"        # Execution failed


class PendingAction(Base):
    """
    Model for actions awaiting user confirmation.

    Implements the Human-in-the-Loop pattern for sensitive operations.
    Agent generates the action, user confirms, then Tool Gateway executes.
    """

    __tablename__ = "pending_actions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected', 'expired', 'executed', 'failed')",
            name='ck_pending_actions_status',
        ),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # User and family reference
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    family_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )

    # Job reference (links to originating agent task)
    job_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )

    # Action details
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    display_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ActionStatus.PENDING.value,
    )

    # Expiration
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Execution result
    execution_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Association linkage (for suggest_* action types)
    association_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("event_associations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    draft_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="预拟的行动内容（如草拟的邀约消息文本），用于suggest_*类型",
    )

    def __repr__(self) -> str:
        return (
            f"<PendingAction(id={self.id}, type={self.action_type}, "
            f"status={self.status})>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if action has expired."""
        return (
            self.status == ActionStatus.PENDING.value
            and utc_now() > self.expires_at
        )

    @property
    def can_confirm(self) -> bool:
        """Check if action can be confirmed."""
        return (
            self.status == ActionStatus.PENDING.value
            and not self.is_expired
        )

    @property
    def can_execute(self) -> bool:
        """Check if action can be executed."""
        return self.status == ActionStatus.CONFIRMED.value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "job_id": str(self.job_id) if self.job_id else None,
            "action_type": self.action_type,
            "payload": self.payload,
            "display_data": self.display_data,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "execution_result": self.execution_result,
            "error_message": self.error_message,
            "is_expired": self.is_expired,
            "can_confirm": self.can_confirm,
            "can_execute": self.can_execute,
            "association_id": str(self.association_id) if self.association_id else None,
            "draft_content": self.draft_content,
        }


__all__ = [
    "ActionType",
    "ActionStatus",
    "PendingAction",
]
