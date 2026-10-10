"""Preparation item CRUD service.

Delegates all writes to CurationWriteDelegate (single-writer principle).
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ...curation.models import CuratedEvent
from ...curation.services.write_delegate import CurationWriteDelegate
from ..kanban_schemas import PreparationItem

logger = get_logger(__name__)


class PreparationService:
    """CRUD operations on preparation items attached to curated events.

    All DB mutations are delegated to CurationWriteDelegate so that the
    curation module remains the single writer to the curated_events table.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self._delegate = CurationWriteDelegate(session)

    async def update_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item_key: str,
        done: bool,
        item_index: Optional[int] = None,
    ) -> Optional[List[PreparationItem]]:
        """Toggle done status of a preparation item by key (or legacy index)."""
        result = await self._delegate.toggle_preparation_item(
            event_id=event_id,
            family_id=family_id,
            item_key=item_key,
            done=done,
            item_index=item_index,
        )
        if result is None:
            return None
        return [PreparationItem(**i) for i in result]

    async def add_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item: str,
        source: str = "manual",
    ) -> Optional[List[PreparationItem]]:
        """Append a new preparation item to an event."""
        result = await self._delegate.add_preparation_item(
            event_id=event_id,
            family_id=family_id,
            label=item,
            source=source,
        )
        if result is None:
            return None
        return [PreparationItem(**i) for i in result]

    async def update_preparation_item_by_trip(
        self,
        trip_id: UUID,
        family_id: UUID,
        item_key: str,
        done: bool,
    ) -> Optional[List[PreparationItem]]:
        """Toggle done status by trip_id + item_key.

        Finds the CuratedEvent linked to the trip that contains the item,
        then delegates to the standard toggle logic.
        """
        stmt = select(CuratedEvent.id).where(and_(
            CuratedEvent.family_id == family_id,
            CuratedEvent.trip_id == trip_id,
            CuratedEvent.is_active.is_(True),
        ))
        result = await self.session.execute(stmt)
        event_ids = list(result.scalars().all())

        for event_id in event_ids:
            items = await self.update_preparation_item(
                event_id=event_id,
                family_id=family_id,
                item_key=item_key,
                done=done,
            )
            if items is not None:
                return items

        return None

    async def remove_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item_key: str,
        item_index: Optional[int] = None,
    ) -> Optional[List[PreparationItem]]:
        """Remove a preparation item by key (or legacy index)."""
        result = await self._delegate.remove_preparation_item(
            event_id=event_id,
            family_id=family_id,
            item_key=item_key,
            item_index=item_index,
        )
        if result is None:
            return None
        return [PreparationItem(**i) for i in result]
