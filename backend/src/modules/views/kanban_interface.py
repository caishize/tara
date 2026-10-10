"""Kanban module public interface.

Defines abstract contracts for kanban views, memory lane,
preparation checklists, and event search.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID


class IKanbanService(ABC):
    """Builds semantic kanban view from curated events."""

    @abstractmethod
    async def get_kanban_view(
        self,
        family_id: UUID,
        user_id: UUID,
        limit: int = 100,
    ) -> Any:
        """Get kanban view with semantic groups.

        Returns a KanbanResponse with groups:
        week_highlights, needs_preparation, this_month, further, ai_reminders.
        """
        ...

    @abstractmethod
    async def get_upcoming_events(
        self,
        family_id: UUID,
        user_id: UUID,
        days: int = 7,
    ) -> List[Any]:
        """Fetch upcoming active events within the next N days.

        Intended as the single query layer for briefing and graph modules.
        """
        ...


class IMemoryLaneService(ABC):
    """Memory lane: on-this-day, story aggregation, yearly fold."""

    @abstractmethod
    async def get_memory_lane(
        self,
        family_id: UUID,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        year: Optional[int] = None,
    ) -> Any:
        """Get memory lane items grouped by year and story."""
        ...

    @abstractmethod
    async def get_on_this_day(
        self,
        family_id: UUID,
        user_id: UUID,
    ) -> Any:
        """Get on-this-day memories from previous years."""
        ...


class IEventDetailService(ABC):
    """Enriched event context: event data + associations + related memories."""

    @abstractmethod
    async def get_event_detail(
        self,
        event_id: UUID,
        family_id: UUID,
    ) -> Optional[Any]:
        """Return enriched event context for graph detail view."""
        ...


class IPreparationService(ABC):
    """Preparation checklist CRUD (writes via curation module)."""

    @abstractmethod
    async def update_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item_key: str,
        done: bool,
        item_index: Optional[int] = None,
    ) -> Optional[List[Any]]:
        """Toggle done status of a preparation item."""
        ...

    @abstractmethod
    async def add_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item: str,
        source: str = "manual",
    ) -> Optional[List[Any]]:
        """Add a preparation item."""
        ...

    @abstractmethod
    async def remove_preparation_item(
        self,
        event_id: UUID,
        family_id: UUID,
        item_key: str,
        item_index: Optional[int] = None,
    ) -> Optional[List[Any]]:
        """Remove a preparation item."""
        ...


class ISearchService(ABC):
    """Event search."""

    @abstractmethod
    async def search_events(
        self,
        family_id: UUID,
        query: str,
        event_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> Any:
        """Search events by text query with optional type filters."""
        ...
