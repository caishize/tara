"""Curation module public interface.

Defines abstract contracts for event curation, deduplication,
association discovery, and storage.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CuratedEvent:
    """A curated event."""
    id: str
    family_id: str
    title: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    event_type: Optional[str] = None
    trip_id: Optional[str] = None
    priority: int = 0
    status: str = "active"
    tags: Optional[List[str]] = None


@dataclass(frozen=True)
class EventAssociation:
    """An association between events (person/place/task/memory)."""
    id: str
    source_event_id: str
    target_id: str
    association_type: str
    confidence: float = 1.0


class ICurationService(ABC):
    """Orchestrates the curation pipeline: collect -> dedup -> associate -> store."""

    @abstractmethod
    async def curate(
        self,
        family_id: str,
        source: str,
        raw_events: List[Dict[str, Any]],
    ) -> List[CuratedEvent]:
        """Run the curation pipeline on raw events."""
        ...


class IStorageService(ABC):
    """Read/write access to curated_events and event_associations."""

    @abstractmethod
    async def get_events(
        self,
        family_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CuratedEvent]:
        """Query curated events."""
        ...

    @abstractmethod
    async def get_event_by_id(
        self,
        event_id: str,
        family_id: str,
    ) -> Optional[CuratedEvent]:
        """Get a single event by ID."""
        ...

    @abstractmethod
    async def get_associations(
        self,
        event_id: str,
    ) -> List[EventAssociation]:
        """Get associations for an event."""
        ...


class IDeduplicationService(ABC):
    """Event deduplication and merging."""

    @abstractmethod
    async def deduplicate(
        self,
        family_id: str,
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Deduplicate a batch of events."""
        ...


class IAssociationService(ABC):
    """Discover associations between events."""

    @abstractmethod
    async def discover_associations(
        self,
        family_id: str,
        event_id: str,
    ) -> List[EventAssociation]:
        """Find associations for a newly curated event."""
        ...


# ---------------------------------------------------------------------------
# Convenience query interface (used by kanban / graph / briefing)
# ---------------------------------------------------------------------------

class ICurationQuery(ABC):
    """Read-only query interface exposed to other modules."""

    @abstractmethod
    async def get_upcoming_events(
        self,
        family_id: str,
        days: int = 30,
        limit: int = 50,
    ) -> List[CuratedEvent]:
        ...

    @abstractmethod
    async def get_event_detail(
        self,
        event_id: str,
        family_id: str,
    ) -> Optional[CuratedEvent]:
        ...

    @abstractmethod
    async def update_preparation(
        self,
        event_id: str,
        family_id: str,
        item_key: str,
        done: bool,
    ) -> Optional[List[dict]]:
        """Toggle a preparation item (delegates to write_delegate)."""
        ...

    @abstractmethod
    async def search_events(
        self,
        family_id: str,
        query: str,
        limit: int = 20,
    ) -> List[CuratedEvent]:
        ...
