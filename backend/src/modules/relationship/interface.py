"""Relationship module public interface.

Defines abstract contracts for favor tracking
and care suggestions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FavorRecord:
    """A favor exchange record."""
    id: str
    person_id: str
    family_id: str
    direction: str  # gave, received
    favor_type: str
    amount: Optional[float] = None
    description: Optional[str] = None
    weight: float = 1.0
    date: Optional[date] = None


@dataclass(frozen=True)
class FavorBalance:
    """Favor balance for a single person."""
    person_id: str
    person_name: str
    favor_balance: float
    owes_favor: bool
    is_owed_favor: bool
    last_interaction_days: Optional[int] = None


@dataclass(frozen=True)
class CareSuggestion:
    """A smart care suggestion."""
    person_id: str
    person_name: str
    suggestion_type: str
    content: str
    urgency: float = 0.5


@dataclass(frozen=True)
class RelationshipHealth:
    """Relationship health for a single contact."""
    person_id: str
    person_name: str
    favor_balance: float
    last_interaction_days: Optional[int]
    health_score: float
    suggestion: Optional[str] = None


class IFavorService(ABC):
    """Favor recording, balance tracking, and reminders."""

    @abstractmethod
    async def record_favor(
        self, family_id: str, person_id: str,
        direction: str, favor_type: str,
        amount: Optional[float] = None,
        description: Optional[str] = None,
        weight: float = 1.0,
        favor_date: Optional[date] = None,
    ) -> FavorRecord:
        """Record a favor exchange and update person_profile balance."""
        ...

    @abstractmethod
    async def get_balance(
        self, family_id: str,
        person_id: Optional[str] = None,
    ) -> List[FavorBalance]:
        """Get favor balance overview."""
        ...

    @abstractmethod
    async def list_favors(
        self, family_id: str,
        person_id: Optional[str] = None,
        direction: Optional[str] = None,
        limit: int = 20,
    ) -> List[FavorRecord]:
        """List favor records with optional direction filter."""
        ...


class ICareService(ABC):
    """Care suggestions and relationship health scoring."""

    @abstractmethod
    async def get_health_overview(
        self, family_id: str,
    ) -> Dict[str, Any]:
        """Get overall relationship health stats."""
        ...

    @abstractmethod
    async def get_contact_health(
        self, family_id: str,
    ) -> List[RelationshipHealth]:
        """Get per-contact relationship health scores."""
        ...

    @abstractmethod
    async def get_suggestions(
        self, family_id: str, limit: int = 5,
    ) -> List[CareSuggestion]:
        """Generate smart care suggestions."""
        ...
