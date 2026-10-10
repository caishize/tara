"""Trip module public interface.

Defines abstract contracts for trip planning,
itinerary management, and budget tracking.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TripPlanDTO:
    """A travel plan summary."""
    id: str
    family_id: str
    destination: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    trip_name: Optional[str] = None
    category: str = "personal"
    trip_type: str = "leisure"
    status: str = "planning"
    budget: Optional[float] = None
    actual_expense: Optional[float] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class ItineraryDayDTO:
    """One day of an itinerary."""
    day_number: int
    schedule: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class ExpenseSummaryDTO:
    """Expense summary for a trip."""
    total: float = 0.0
    budget: Optional[float] = None
    categories: Optional[Dict[str, float]] = None


class ITripService(ABC):
    """Travel plan CRUD and deduplication."""

    @abstractmethod
    async def create_plan(
        self, family_id: str, user_id: str,
        destination: str, start_date: date, end_date: date,
        category: str = "personal", trip_type: str = "leisure",
        budget: Optional[float] = None, notes: Optional[str] = None,
        participants: Optional[List[str]] = None,
    ) -> TripPlanDTO:
        """Create a travel plan (auto-dedup by destination + overlapping dates)."""
        ...

    @abstractmethod
    async def get_plan(
        self, trip_id: str, family_id: str,
    ) -> Optional[TripPlanDTO]:
        """Get a single plan by ID."""
        ...

    @abstractmethod
    async def list_plans(
        self, family_id: str,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20, offset: int = 0,
    ) -> List[TripPlanDTO]:
        """List travel plans for a family."""
        ...

    @abstractmethod
    async def update_plan(
        self, trip_id: str, family_id: str,
        updates: Dict[str, Any],
    ) -> TripPlanDTO:
        """Update a travel plan."""
        ...

    @abstractmethod
    async def delete_plan(
        self, trip_id: str, family_id: str,
    ) -> bool:
        """Delete a travel plan. Returns True if deleted."""
        ...


class IItineraryService(ABC):
    """Itinerary generation and day-by-day management."""

    @abstractmethod
    async def get_itinerary(
        self, trip_id: str, family_id: str,
    ) -> List[ItineraryDayDTO]:
        """Get itinerary for a trip."""
        ...

    @abstractmethod
    async def generate_itinerary(
        self, trip_id: str, family_id: str,
        style: str = "relaxed",
        interests: Optional[List[str]] = None,
        constraints: Optional[str] = None,
    ) -> List[ItineraryDayDTO]:
        """AI-generate itinerary for a trip."""
        ...

    @abstractmethod
    async def add_activity(
        self, trip_id: str, day_number: int,
        activity: Dict[str, Any],
    ) -> ItineraryDayDTO:
        """Add an activity to a day."""
        ...


class IBudgetService(ABC):
    """Trip budget and expense tracking."""

    @abstractmethod
    async def get_expenses(
        self, trip_id: str, family_id: str,
    ) -> List[Dict[str, Any]]:
        """Get expenses for a trip."""
        ...

    @abstractmethod
    async def add_expense(
        self, trip_id: str, family_id: str,
        amount: float, category: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an expense."""
        ...

    @abstractmethod
    async def get_summary(
        self, trip_id: str, family_id: str,
    ) -> ExpenseSummaryDTO:
        """Get expense summary for a trip."""
        ...
