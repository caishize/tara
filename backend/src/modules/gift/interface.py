"""Gift module public interface.

Defines abstract contracts for gift recommendations, task management,
trending discovery, and price tracking.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class GiftRecommendation:
    """A gift recommendation."""
    id: str
    recipient_id: str
    occasion: Optional[str] = None
    suggestions: Optional[List[Dict[str, Any]]] = None
    budget_range: Optional[str] = None


@dataclass(frozen=True)
class GiftTask:
    """A gift task with state machine lifecycle."""
    id: str
    family_id: str
    recipient_id: str
    gift_name: str
    status: str  # discovered, recommended, purchased, shipped, completed
    created_at: Optional[datetime] = None


class IRecommendationService(ABC):
    """Profile-based smart gift recommendations."""

    @abstractmethod
    async def recommend(
        self,
        family_id: str,
        recipient_id: str,
        occasion: Optional[str] = None,
        budget: Optional[float] = None,
    ) -> GiftRecommendation:
        """Generate gift recommendations."""
        ...


class ITaskService(ABC):
    """Gift task state machine (discovered -> recommended -> purchased -> shipped -> completed)."""

    @abstractmethod
    async def create_task(
        self,
        family_id: str,
        recipient_id: str,
        gift_name: str,
        **kwargs: Any,
    ) -> GiftTask:
        """Create a gift task."""
        ...

    @abstractmethod
    async def update_status(
        self,
        task_id: str,
        new_status: str,
    ) -> GiftTask:
        """Advance task to next status."""
        ...

    @abstractmethod
    async def list_tasks(
        self,
        family_id: str,
        status: Optional[str] = None,
    ) -> List[GiftTask]:
        """List gift tasks."""
        ...


class ITrendingService(ABC):
    """Trending/seasonal gift discovery."""

    @abstractmethod
    async def get_trending(
        self,
        occasion: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get trending gifts, optionally filtered by occasion."""
        ...


class IPriceTracker(ABC):
    """Price monitoring and promotion alerts."""

    @abstractmethod
    async def track_price(
        self,
        gift_task_id: str,
        url: str,
    ) -> None:
        """Start tracking price for a gift."""
        ...

    @abstractmethod
    async def check_prices(self) -> List[Dict[str, Any]]:
        """Check prices for all tracked items. Returns alerts."""
        ...
