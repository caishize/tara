"""Transactional Outbox — SQLAlchemy model and helper.

Domain events are written to the `event_outbox` table within the same
DB transaction as the business operation, guaranteeing atomicity.
A separate relay task polls unpublished rows and publishes them to
Redis Streams.
"""

import json
import logging
import uuid
from typing import Optional

from sqlalchemy import Column, String, DateTime, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import Base
from ..utils.timezone import utc_now
from .event_bus import DomainEvent

logger = logging.getLogger(__name__)


class OutboxEvent(Base):
    """SQLAlchemy model for the event_outbox table."""

    __tablename__ = "event_outbox"
    __table_args__ = (
        Index(
            "idx_outbox_unpublished",
            "created_at",
            postgresql_where=text("published_at IS NULL"),
        ),
        {"extend_existing": True},
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    correlation_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Correlates outbox event to the originating user action",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    published_at = Column(DateTime(timezone=True), nullable=True)


async def save_to_outbox(
    db: AsyncSession,
    event: DomainEvent,
    *,
    correlation_id: Optional['uuid.UUID'] = None,
    flush: bool = True,
) -> OutboxEvent:
    """Persist a domain event to the outbox within the caller's transaction.

    The caller is responsible for committing the session. By writing the
    outbox row in the same transaction as the business data, we guarantee
    that the event is only visible after the business operation succeeds.

    Args:
        db: The async session (must be inside a transaction).
        event: The domain event to persist.
        correlation_id: Optional UUID linking this event to the originating
            user action (for tracing/debugging).
        flush: Whether to flush immediately (default True). Set False if
               the caller will flush/commit soon.

    Returns:
        The persisted OutboxEvent row.
    """
    row = OutboxEvent(
        event_type=event.event_type,
        payload=event.to_dict(),
        correlation_id=correlation_id,
    )
    db.add(row)
    if flush:
        await db.flush()
    logger.debug("Saved event to outbox: %s (id=%s)", event.event_type, row.id)
    return row
