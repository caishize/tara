"""Graph module public interface.

Defines abstract contracts for graph construction,
event context, and association management.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID


class IGraphService(ABC):
    """Graph construction and node operations."""

    @abstractmethod
    async def get_upcoming_trips(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> List[Any]:
        """Get upcoming trips for the graph trip selector."""
        ...

    @abstractmethod
    async def get_event_graph(
        self,
        trip_id: UUID,
        user_id: UUID,
        family_id: Optional[UUID] = None,
        trip_ids: Optional[List[UUID]] = None,
    ) -> Any:
        """Build graph for a trip (aggregates all trip events).

        Despite the name, this is trip-centered. The trip_id can be either
        a curated_event ID or a trip plan trip_id.
        """
        ...

    @abstractmethod
    async def get_event_centered_graph(
        self,
        event_id: UUID,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> Any:
        """Build graph centered on a single event (non-trip)."""
        ...


class IAssociationManager(ABC):
    """Association creation, confirmation, and dismissal."""

    @abstractmethod
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
    ) -> Any:
        """Create a new association. Returns the EventAssociation ORM object."""
        ...

    @abstractmethod
    async def confirm_association(self, association_id: UUID) -> bool:
        """Confirm a suggested association."""
        ...

    @abstractmethod
    async def dismiss_association(self, association_id: UUID) -> bool:
        """Dismiss a suggested association."""
        ...

    @abstractmethod
    async def get_association_detail(
        self,
        association_id: UUID,
    ) -> Optional[Any]:
        """Get association detail with source event title."""
        ...
