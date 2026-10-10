"""User ORM model."""
import uuid

from sqlalchemy import (
    CheckConstraint, Column, Index, String, Boolean, Text, TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from ....db.session import Base
from ....core.utils.timezone import DEFAULT_TIMEZONE_NAME


class User(Base):
    """User entity."""

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(Text, nullable=False)
    username = Column(String(100), nullable=False)
    nickname = Column(String(50), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    timezone = Column(String(50), nullable=False, server_default=DEFAULT_TIMEZONE_NAME)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "phone IS NOT NULL OR email IS NOT NULL",
            name="ck_users_phone_or_email",
        ),
        Index("idx_users_family", "family_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username}>"
