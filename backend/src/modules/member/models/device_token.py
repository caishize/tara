"""DeviceToken ORM model - FCM device tokens for push notifications."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ....db.session import Base


class DeviceToken(Base):
    """
    Model for FCM device tokens.

    Each user can have multiple active tokens (one per device).
    Tokens are deactivated when they become invalid or on user logout.
    """

    __tablename__ = "device_tokens"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True,
    )
    fcm_token: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True,
    )
    device_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )
    device_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
    )
    app_version: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<DeviceToken(id={self.id}, user_id={self.user_id}, "
            f"device_type={self.device_type}, active={self.is_active})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response (fcm_token excluded for security)."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "device_type": self.device_type,
            "device_name": self.device_name,
            "app_version": self.app_version,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
