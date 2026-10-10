"""Curation write delegate.

Centralizes all writes to curated_events, preparation_items, and
event_associations tables.  Other modules (views, trip) MUST
use this delegate instead of writing directly, enforcing the
single-writer principle.
"""
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ..models import CuratedEvent, EventAssociation, PreparationItem

logger = get_logger(__name__)


class CurationWriteDelegate:
    """Delegate for modules that need to write to curation-owned tables.

    All mutations to ``curated_events``, ``preparation_items``, and
    ``event_associations`` tables MUST go through this class (except for
    the curation pipeline itself, which uses CurationStorageMixin).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Preparation items (preparation_items independent table)
    # ------------------------------------------------------------------

    async def add_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        label: str,
        source: str = "manual",
    ) -> Optional[List[dict]]:
        """Add a preparation item to a curated event.

        Returns the updated preparation_items list, or None if the event
        was not found.
        """
        event = await self._get_event_if_exists(event_id, family_id)
        if not event:
            return None

        max_order = await self._max_sort_order(event_id)
        item = PreparationItem(
            event_id=event_id,
            key=uuid4(),
            text=label,
            source=source,
            done=False,
            sort_order=max_order + 1,
        )
        self.db.add(item)
        await self.db.flush()

        return await self._list_items(event_id)

    async def toggle_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item_key: str,
        done: bool,
        item_index: Optional[int] = None,
    ) -> Optional[List[dict]]:
        """Toggle preparation item completion.

        Row-level update -- no lock on the parent curated_events row.
        Returns the updated preparation_items list, or None if not found.
        """
        event = await self._get_event_if_exists(event_id, family_id)
        if not event:
            return None

        if item_key:
            stmt = (
                update(PreparationItem)
                .where(and_(
                    PreparationItem.event_id == event_id,
                    PreparationItem.key == UUID(item_key),
                ))
                .values(done=done)
            )
            result = await self.db.execute(stmt)
            if result.rowcount == 0:
                return None
        else:
            return None

        return await self._list_items(event_id)

    async def remove_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item_key: str,
        item_index: Optional[int] = None,
    ) -> Optional[List[dict]]:
        """Remove a preparation item.

        Returns the updated preparation_items list, or None if not found.
        """
        event = await self._get_event_if_exists(event_id, family_id)
        if not event:
            return None

        if item_key:
            stmt = (
                delete(PreparationItem)
                .where(and_(
                    PreparationItem.event_id == event_id,
                    PreparationItem.key == UUID(item_key),
                ))
            )
            result = await self.db.execute(stmt)
            if result.rowcount == 0:
                return None
        else:
            return None

        return await self._list_items(event_id)

    async def get_preparation_items(
        self, event_id: UUID,
    ) -> List[dict]:
        """Return all preparation items for an event as dicts."""
        return await self._list_items(event_id)

    # ------------------------------------------------------------------
    # Associations (event_associations table)
    # ------------------------------------------------------------------

    async def create_association(
        self,
        source_event_id: UUID,
        family_id: UUID,
        target_type: str,
        target_id: str,
        association_type: str,
        title: str,
        reason: str,
        priority: str = "convenient",
        confidence: float = 0.8,
    ) -> EventAssociation:
        """Create an event association.

        Raises ValueError if the source event is not found.
        """
        event = await self.db.get(CuratedEvent, source_event_id)
        if not event:
            raise ValueError("Event not found")

        association = EventAssociation(
            family_id=family_id or event.family_id,
            source_event_id=source_event_id,
            target_type=target_type,
            target_id=target_id,
            association_type=association_type,
            title=title,
            reason=reason,
            priority=priority,
            confidence=confidence,
        )

        self.db.add(association)
        await self.db.flush()
        await self.db.refresh(association)

        return association

    async def update_association_status(
        self,
        association_id: UUID,
        is_confirmed: Optional[bool] = None,
        is_dismissed: Optional[bool] = None,
    ) -> bool:
        """Confirm or dismiss an association.

        Returns True if the association was found and updated.
        """
        query = select(EventAssociation).where(
            EventAssociation.id == association_id
        )
        result = await self.db.execute(query)
        association = result.scalar_one_or_none()

        if not association:
            return False

        if is_confirmed is not None:
            association.is_confirmed = is_confirmed
        if is_dismissed is not None:
            association.is_dismissed = is_dismissed

        await self.db.flush()
        return True

    # ------------------------------------------------------------------
    # Event status (curated_events table)
    # ------------------------------------------------------------------

    async def deactivate_events_for_trip(
        self,
        trip_id: UUID,
        family_id: UUID,
    ) -> int:
        """Mark curated events as inactive for a cancelled trip.

        Uses a two-pass approach:
        1. By FK trip_id (direct link)
        2. By original_event_ids containing the trip UUID (lineage link)

        Returns the number of rows affected.
        """
        trip_id_str = str(trip_id)
        stmt = (
            update(CuratedEvent)
            .where(
                and_(
                    CuratedEvent.family_id == family_id,
                    or_(
                        CuratedEvent.trip_id == trip_id,
                        CuratedEvent.original_event_ids.contains([trip_id_str]),
                    ),
                )
            )
            .values(is_active=False, status="cancelled")
        )
        result = await self.db.execute(stmt)
        return result.rowcount

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_event_if_exists(
        self, event_id: UUID, family_id: UUID
    ) -> Optional[CuratedEvent]:
        """Check event exists and belongs to family (no row lock)."""
        stmt = (
            select(CuratedEvent.id)
            .where(and_(
                CuratedEvent.id == event_id,
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
            ))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _max_sort_order(self, event_id: UUID) -> int:
        """Get max sort_order for items of an event."""
        result = await self.db.execute(
            select(func.coalesce(func.max(PreparationItem.sort_order), -1))
            .where(PreparationItem.event_id == event_id)
        )
        return result.scalar() or 0

    async def _list_items(self, event_id: UUID) -> List[dict]:
        """Return all preparation items as serializable dicts."""
        result = await self.db.execute(
            select(PreparationItem)
            .where(PreparationItem.event_id == event_id)
            .order_by(PreparationItem.sort_order)
        )
        rows = result.scalars().all()
        return [
            {
                "key": str(row.key),
                "item": row.text,
                "source": row.source,
                "done": row.done,
                "sort_order": row.sort_order,
            }
            for row in rows
        ]
