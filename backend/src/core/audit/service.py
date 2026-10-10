"""Audit service for persisting structured event logs."""

from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from .models import AuditLog

logger = get_logger(__name__)


class AuditService:
    """Writes immutable audit log entries for key system events.

    Usage:
        audit = AuditService(db)
        await audit.log_event(user_id, family_id, "l1_note_created", {"note_id": "..."})
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_event(
        self,
        user_id: UUID,
        family_id: UUID,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Persist a single audit log entry.

        Args:
            user_id: The user who triggered the event.
            family_id: The family context.
            event_type: Short event identifier (e.g. "l1_note_created").
            event_data: Arbitrary JSON-serializable payload.

        Returns:
            The created AuditLog row.
        """
        entry = AuditLog(
            user_id=user_id,
            family_id=family_id,
            event_type=event_type,
            event_data=event_data or {},
        )
        self.db.add(entry)
        try:
            await self.db.flush()
        except Exception:
            logger.error(
                "Failed to write audit log event_type=%s for user=%s",
                event_type,
                user_id,
                exc_info=True,
            )
            raise
        return entry
