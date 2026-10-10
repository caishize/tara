"""Audit log model for tracking system events."""

from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from ...core.utils.timezone import utc_now
from ...db.session import Base


class AuditLog(Base):
    """Immutable audit trail for tracking key system events.

    Stores structured event data for compliance, debugging, and analytics.
    """

    __tablename__ = "audit_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    event_data = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_audit_logs_user_event", "user_id", "event_type"),
        Index("ix_audit_logs_created", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "event_type": self.event_type,
            "event_data": self.event_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
