"""UserDataConnection ORM model.

Stores OAuth/API connections for external data sources (calendar, email,
smart-home, etc.) that a user has linked to their account.
"""
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer,
    LargeBinary, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func, text

from ....db.session import Base


class UserDataConnection(Base):
    """A user's connection to an external data provider."""

    __tablename__ = "user_data_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id = Column(
        UUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Provider identification
    provider_type = Column(String(50), nullable=False)
    provider_name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    icon_url = Column(String(500), nullable=True)

    # Auth state
    connection_status = Column(String(20), nullable=False, server_default="disconnected")
    auth_type = Column(String(20), nullable=False, server_default="oauth2")

    # Credentials (AES-256-GCM encrypted JSON blob)
    encrypted_credentials = Column(LargeBinary, nullable=True)
    scopes = Column(JSONB, nullable=False, server_default="[]")

    # MCP server integration
    mcp_server_url = Column(String(500), nullable=True)
    mcp_server_config = Column(JSONB, nullable=True)

    # Sync state
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    sync_frequency_minutes = Column(Integer, nullable=False, server_default="60")
    metadata_ = Column("metadata", JSONB, nullable=False, server_default="{}")

    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider_name", name="uq_user_provider"),
        Index(
            "ix_user_data_connections_user_status",
            "user_id",
            "connection_status",
            postgresql_where=text("is_active = true"),
        ),
        Index("ix_user_data_connections_family", "family_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserDataConnection(id={self.id}, user={self.user_id}, "
            f"provider={self.provider_name}, status={self.connection_status})>"
        )
