"""EventContextService — facade that delegates to focused kanban services.

Preserves the original EventContextService API surface so that secretary
API routes continue to work without changes.  Each method delegates to
the appropriate focused service (KanbanService, MemoryLaneService, etc.).
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..kanban_schemas import (
    EventDetailResponse,
    EventSearchResponse,
    KanbanEvent,
    KanbanResponse,
    MemoryLaneResponse,
    OnThisDayResponse,
    PreparationItem,
)
from .kanban_service import KanbanService
from .memory_lane_service import MemoryLaneService
from .event_detail_service import EventDetailService
from .preparation_service import PreparationService
from .search_service import SearchService


class EventContextService:
    """Unified context layer — facade over focused kanban services."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -- Kanban view --

    async def get_kanban_view(
        self,
        family_id: UUID,
        user_id: UUID,
        limit: int = 100,
    ) -> KanbanResponse:
        svc = KanbanService(self.session)
        return await svc.get_kanban_view(family_id=family_id, user_id=user_id, limit=limit)

    # -- Memory lane --

    async def get_memory_lane(
        self,
        family_id: UUID,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        year: Optional[int] = None,
    ) -> MemoryLaneResponse:
        svc = MemoryLaneService(self.session)
        return await svc.get_memory_lane(
            family_id=family_id, user_id=user_id,
            limit=limit, offset=offset, year=year,
        )

    # -- On this day --

    async def get_on_this_day(
        self,
        family_id: UUID,
        user_id: UUID,
    ) -> OnThisDayResponse:
        svc = MemoryLaneService(self.session)
        return await svc.get_on_this_day(family_id=family_id, user_id=user_id)

    # -- Preparation CRUD --

    async def update_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item_key: str,
        done: bool,
        item_index: Optional[int] = None,
    ) -> Optional[List[PreparationItem]]:
        svc = PreparationService(self.session)
        return await svc.update_preparation_item(
            event_id=event_id, family_id=family_id,
            item_key=item_key, done=done, item_index=item_index,
        )

    async def add_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item: str,
        source: str = "manual",
    ) -> Optional[List[PreparationItem]]:
        svc = PreparationService(self.session)
        return await svc.add_preparation_item(
            event_id=event_id, family_id=family_id,
            item=item, source=source,
        )

    async def remove_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item_key: str,
        item_index: Optional[int] = None,
    ) -> Optional[List[PreparationItem]]:
        svc = PreparationService(self.session)
        return await svc.remove_preparation_item(
            event_id=event_id, family_id=family_id,
            item_key=item_key, item_index=item_index,
        )

    # -- Search --

    async def search_events(
        self,
        family_id: UUID,
        query: str,
        event_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> EventSearchResponse:
        svc = SearchService(self.session)
        return await svc.search_events(
            family_id=family_id, query=query,
            event_types=event_types, limit=limit,
        )

    # -- Event detail --

    async def get_event_detail(
        self,
        event_id: UUID,
        family_id: UUID,
    ) -> Optional[EventDetailResponse]:
        svc = EventDetailService(self.session)
        return await svc.get_event_detail(event_id=event_id, family_id=family_id)

    # -- Upcoming events --

    async def get_upcoming_events(
        self,
        family_id: UUID,
        user_id: UUID,
        days: int = 7,
    ) -> List[KanbanEvent]:
        svc = KanbanService(self.session)
        return await svc.get_upcoming_events(family_id=family_id, user_id=user_id, days=days)
