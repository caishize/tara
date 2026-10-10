"""Member module public interface.

Defines abstract contracts for family member management,
person profile CRUD, and profile enrichment.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MemberInfo:
    """A family member."""
    id: str
    user_id: Optional[str]
    family_id: str
    name: str
    relation: Optional[str] = None
    birthday: Optional[date] = None
    locations: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


@dataclass(frozen=True)
class MemberProfileInfo:
    """Extended member profile (sizes, health, etc.)."""
    member_id: str
    preferences: Optional[Dict[str, Any]] = None
    habits: Optional[Dict[str, Any]] = None
    health_summary: Optional[str] = None
    personality_traits: Optional[Dict[str, Any]] = None
    special_notes: Optional[str] = None


@dataclass(frozen=True)
class PersonProfile:
    """Unified person profile (family member or external contact)."""
    id: str
    family_id: str
    name: str
    member_id: Optional[str] = None
    aliases: Optional[List[str]] = None
    relationship: Optional[str] = None
    relationship_context: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    favor_balance: float = 0.0
    mention_count: int = 0
    last_mentioned_at: Optional[datetime] = None
    importance: float = 0.0
    status: str = "active"

    @property
    def needs_contact(self) -> bool:
        """Important person not contacted in 90+ days."""
        if self.importance < 5 or self.last_mentioned_at is None:
            return False
        from ...core.utils.timezone import utc_now
        delta = utc_now() - self.last_mentioned_at
        return delta.days >= 90

    @property
    def owes_favor(self) -> bool:
        """We owe this person (negative balance)."""
        return self.favor_balance < -0.5


@dataclass(frozen=True)
class FamilyInfo:
    """Family summary."""
    id: str
    name: str
    owner_user_id: str
    settings: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Service interfaces
# ---------------------------------------------------------------------------

class IMemberService(ABC):
    """Family member CRUD and family relationship management."""

    @abstractmethod
    async def get_family(self, family_id: str) -> Optional[FamilyInfo]:
        """Get family info."""
        ...

    @abstractmethod
    async def list_members(self, family_id: str) -> List[MemberInfo]:
        """List all family members."""
        ...

    @abstractmethod
    async def get_member(
        self, member_id: str, family_id: str,
    ) -> Optional[MemberInfo]:
        """Get a member by ID."""
        ...

    @abstractmethod
    async def create_member(
        self, family_id: str, name: str,
        relation: Optional[str] = None, **kwargs: Any,
    ) -> MemberInfo:
        """Create a family member."""
        ...

    @abstractmethod
    async def update_member(
        self, member_id: str, family_id: str,
        updates: Dict[str, Any],
    ) -> MemberInfo:
        """Update a family member."""
        ...

    @abstractmethod
    async def delete_member(
        self, member_id: str, family_id: str,
    ) -> bool:
        """Soft-delete a family member. Returns True if deleted."""
        ...

    @abstractmethod
    async def get_member_profile(
        self, member_id: str, family_id: str,
    ) -> Optional[MemberProfileInfo]:
        """Get extended profile for a member."""
        ...

    @abstractmethod
    async def update_member_profile(
        self, member_id: str, family_id: str,
        updates: Dict[str, Any],
    ) -> MemberProfileInfo:
        """Update extended profile for a member."""
        ...


class IPersonService(ABC):
    """Person profile CRUD (family members + external contacts)."""

    @abstractmethod
    async def get_profile(
        self, person_id: str, family_id: str,
    ) -> Optional[PersonProfile]:
        """Get a person profile."""
        ...

    @abstractmethod
    async def list_people(
        self, family_id: str,
        min_importance: Optional[float] = None,
        relationship: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PersonProfile]:
        """List all people (members + contacts)."""
        ...

    @abstractmethod
    async def create_profile(
        self, family_id: str, name: str,
        relationship: Optional[str] = None, **kwargs: Any,
    ) -> PersonProfile:
        """Create a new person profile."""
        ...

    @abstractmethod
    async def update_profile(
        self, person_id: str, family_id: str,
        updates: Dict[str, Any],
    ) -> PersonProfile:
        """Update a person profile."""
        ...

    @abstractmethod
    async def get_neglected(
        self, family_id: str,
        threshold_days: int = 90,
        min_importance: float = 5.0,
    ) -> List[PersonProfile]:
        """Get important people who haven't been contacted recently."""
        ...

    @abstractmethod
    async def get_people_with_favors(
        self, family_id: str,
    ) -> List[PersonProfile]:
        """Get people who have non-zero favor balances."""
        ...

    @abstractmethod
    async def search_contacts(
        self, family_id: str, query: str,
        limit: int = 20,
    ) -> List[PersonProfile]:
        """Search person profiles by name, alias, or organization."""
        ...

    @abstractmethod
    async def update_favor_balance(
        self, person_id: str, family_id: str,
        new_balance: float,
    ) -> None:
        """Update favor_balance on a person profile (called by relationship module)."""
        ...


class IProfileEnrichment(ABC):
    """Auto-enrich person profiles from conversations."""

    @abstractmethod
    async def enrich_from_conversation(
        self, family_id: str, person_id: str,
        extracted_data: Dict[str, Any],
    ) -> None:
        """Enrich a person profile with data extracted from conversation."""
        ...

    @abstractmethod
    async def find_or_create_profile(
        self, family_id: str, name: str,
        user_id: str,
        hints: Optional[Dict[str, Any]] = None,
    ) -> PersonProfile:
        """Find existing profile by name/alias or create a new one."""
        ...
