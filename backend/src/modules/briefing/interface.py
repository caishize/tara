"""Briefing module public interface.

Defines abstract contracts for briefing generation,
smart suggestions, and push delivery.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Briefing:
    """A generated briefing."""
    id: str
    user_id: str
    period: str  # morning, afternoon, evening
    sections: List[Dict[str, Any]]
    suggestions: Optional[List["BriefingSuggestion"]] = None


@dataclass(frozen=True)
class BriefingSuggestion:
    """A contextual suggestion within a briefing."""
    text: str
    action_type: str
    action_data: Optional[Dict[str, Any]] = None


class IBriefingService(ABC):
    """Three-period briefing generation."""

    @abstractmethod
    async def generate_briefing(
        self,
        user_id: str,
        family_id: str,
        period: str,
    ) -> Briefing:
        """Generate a briefing for the given period."""
        ...


class ISuggestionService(ABC):
    """Context-aware smart suggestions."""

    @abstractmethod
    async def get_suggestions(
        self,
        user_id: str,
        family_id: str,
        limit: int = 5,
    ) -> List[BriefingSuggestion]:
        """Generate contextual suggestions."""
        ...


class IPushService(ABC):
    """Async push to conversation (path_type=async)."""

    @abstractmethod
    async def push_briefing(
        self,
        user_id: str,
        briefing: Briefing,
    ) -> None:
        """Push a briefing as an async message."""
        ...
