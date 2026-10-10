"""Association management service.

Handles creation, confirmation, dismissal, and detail retrieval
of event associations. All writes are delegated to CurationWriteDelegate
(single-writer principle).

Extracted from graph_service.py per architecture design.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ....config.logging import get_logger
from ...curation.models import EventAssociation
from ...curation.services.write_delegate import CurationWriteDelegate
from ..graph_schemas import AssociationDetail

logger = get_logger(__name__)


class AssociationManager:
    """Association CRUD — create, confirm, dismiss, detail."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._write_delegate = CurationWriteDelegate(db)

    async def add_association(
        self,
        event_id: UUID,
        target_type: str,
        target_id: str,
        association_type: str,
        title: str,
        reason: str,
        priority: str = "convenient",
        confidence: float = 0.8,
        family_id: Optional[UUID] = None,
    ) -> EventAssociation:
        """Add an event association (delegates to CurationWriteDelegate)."""
        return await self._write_delegate.create_association(
            source_event_id=event_id,
            family_id=family_id,
            target_type=target_type,
            target_id=target_id,
            association_type=association_type,
            title=title,
            reason=reason,
            priority=priority,
            confidence=confidence,
        )

    async def dismiss_association(
        self,
        association_id: UUID,
    ) -> bool:
        """Dismiss an association (delegates to CurationWriteDelegate)."""
        return await self._write_delegate.update_association_status(
            association_id=association_id,
            is_dismissed=True,
        )

    async def confirm_association(
        self,
        association_id: UUID,
    ) -> bool:
        """Confirm an association (delegates to CurationWriteDelegate)."""
        return await self._write_delegate.update_association_status(
            association_id=association_id,
            is_confirmed=True,
        )

    async def get_association_detail(
        self,
        association_id: UUID,
    ) -> Optional[AssociationDetail]:
        """Get association detail with source event title."""
        query = (
            select(EventAssociation)
            .options(selectinload(EventAssociation.source_event))
            .where(EventAssociation.id == association_id)
        )

        result = await self.db.execute(query)
        assoc = result.scalar_one_or_none()

        if not assoc:
            return None

        return AssociationDetail(
            id=str(assoc.id),
            title=assoc.title,
            reason=assoc.reason,
            target_type=assoc.target_type,
            target_id=assoc.target_id,
            association_type=assoc.association_type,
            priority=assoc.priority,
            confidence=assoc.confidence,
            is_confirmed=assoc.is_confirmed,
            is_dismissed=assoc.is_dismissed,
            source_event_title=assoc.source_event.title if assoc.source_event else None,
        )
