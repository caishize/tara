"""Conversation module public interface.

Defines abstract contracts for chat session management,
pending actions, and context retrieval.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ChatSessionEntry:
    """A chat session."""
    id: str
    user_id: str
    family_id: str
    title: Optional[str] = None
    status: str = "active"
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class PendingActionEntry:
    """A pending user action."""
    id: str
    action_type: str
    description: str
    status: str = "pending"
    created_at: Optional[datetime] = None


class IChatSessionService(ABC):
    """Manage chat sessions."""

    @abstractmethod
    async def create_session(
        self,
        user_id: str,
        family_id: str,
        title: Optional[str] = None,
    ) -> ChatSessionEntry:
        """Create a new chat session."""
        ...

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[ChatSessionEntry]:
        """Get a session by ID."""
        ...

    @abstractmethod
    async def list_sessions(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ChatSessionEntry]:
        """List sessions for a user."""
        ...


class IPendingActionService(ABC):
    """Manage pending user actions (human-in-the-loop)."""

    @abstractmethod
    async def create_pending_action(
        self,
        user_id: str,
        family_id: str,
        action_type: str,
        description: str,
        action_data: Optional[Dict[str, Any]] = None,
    ) -> PendingActionEntry:
        """Create a new pending action."""
        ...

    @abstractmethod
    async def confirm_action(self, action_id: str) -> bool:
        """Confirm and execute a pending action."""
        ...

    @abstractmethod
    async def reject_action(self, action_id: str) -> bool:
        """Reject a pending action."""
        ...
