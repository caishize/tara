"""Family ORM model.

The families table is the root entity for multi-family isolation.
Every member, event, and resource belongs to exactly one family.
"""
import uuid

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from ....db.session import Base


class Family(Base):
    """Family entity -- root of the multi-tenancy hierarchy."""

    __tablename__ = "families"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    name = Column(String(200), nullable=False)
    owner_user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    settings = Column(JSONB, nullable=False, server_default="{}")
    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Family id={self.id} name={self.name}>"
