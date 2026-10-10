"""Views module public interface.

Defines abstract contracts for kanban board, timeline,
event graph, and search functionality.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TaskEntry:
    """A kanban task."""
    id: str
    family_id: str
    title: str
    status: str = "pending"
    priority: int = 5
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class TimelineEntry:
    """A timeline event."""
    id: str
    title: str
    event_date: Optional[date] = None
    category: Optional[str] = None


class IKanbanService(ABC):
    """Kanban board operations."""

    @abstractmethod
    async def get_tasks(
        self,
        family_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[TaskEntry]:
        """Get tasks for a family."""
        ...

    @abstractmethod
    async def update_task_status(
        self,
        task_id: str,
        status: str,
    ) -> TaskEntry:
        """Update a task's status."""
        ...


class ITimelineService(ABC):
    """Timeline view operations."""

    @abstractmethod
    async def get_timeline(
        self,
        family_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[TimelineEntry]:
        """Get timeline entries for a date range."""
        ...


class ISearchService(ABC):
    """Cross-module search."""

    @abstractmethod
    async def search(
        self,
        family_id: str,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search across all modules."""
        ...
