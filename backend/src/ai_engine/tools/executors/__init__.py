"""Domain executor factory."""

from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseToolExecutor
from .date_executor import DateToolExecutor
from .event_executor import EventToolExecutor
from .member_executor import MemberToolExecutor
from .task_executor import TaskToolExecutor
from .reminder_executor import ReminderToolExecutor
from .memory_executor import MemoryToolExecutor
from .favor_gift_executor import FavorGiftExecutor
from .trip_executor import TripToolExecutor
from .mcp_executor import McpToolExecutor
from .recall_executor import RecallToolExecutor
from .search_executor import SearchToolExecutor


def create_domain_executors(
    db: AsyncSession,
    session_id: Optional[UUID] = None,
) -> Dict[str, BaseToolExecutor]:
    """Create all domain executor instances.

    Returns a dict keyed by domain name for easy lookup during registration.
    """
    return {
        "date": DateToolExecutor(db, session_id),
        "event": EventToolExecutor(db, session_id),
        "member": MemberToolExecutor(db, session_id),
        "task": TaskToolExecutor(db, session_id),
        "reminder": ReminderToolExecutor(db, session_id),
        "memory": MemoryToolExecutor(db, session_id),
        "favor_gift": FavorGiftExecutor(db, session_id),
        "trip": TripToolExecutor(db, session_id),
        "mcp": McpToolExecutor(db, session_id),
        "search": SearchToolExecutor(db, session_id),
    }


__all__ = [
    "BaseToolExecutor",
    "DateToolExecutor",
    "EventToolExecutor",
    "MemberToolExecutor",
    "TaskToolExecutor",
    "ReminderToolExecutor",
    "MemoryToolExecutor",
    "FavorGiftExecutor",
    "TripToolExecutor",
    "McpToolExecutor",
    "RecallToolExecutor",
    "SearchToolExecutor",
    "create_domain_executors",
]
