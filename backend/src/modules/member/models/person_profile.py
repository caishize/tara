"""PersonProfile ORM model - Aggregated person information from memories."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID

from ....core.utils.timezone import utc_now
from ....db.session import Base
from .enums import ProfileStatus


class PersonProfile(Base):
    """
    Aggregated profile of a person mentioned in conversations.

    Consolidates all information about a person from various memories:
    - Basic info (name, aliases, relationship)
    - Location and organization
    - Preferences (likes, dislikes)
    - Favor tracking
    - Contact frequency
    """
    __tablename__ = "person_profiles"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    member_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )

    name = Column(String(100), nullable=False)
    aliases = Column(ARRAY(String), default=list)

    relationship = Column(String(50), nullable=True)
    relationship_context = Column(Text, nullable=True)
    organization = Column(String(200), nullable=True)
    location = Column(String(100), nullable=True)

    preferences = Column(JSONB, default=dict)
    favor_balance = Column(Float, default=0.0)
    favor_history = Column(JSONB, default=list)

    mention_count = Column(Integer, default=0)
    last_mentioned_at = Column(DateTime(timezone=True), nullable=True)
    importance = Column(Integer, default=5)

    source_memory_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)

    status = Column(String(20), default=ProfileStatus.ACTIVE.value)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "member_id": str(self.member_id) if self.member_id else None,
            "name": self.name,
            "aliases": self.aliases,
            "relationship": self.relationship,
            "relationship_context": self.relationship_context,
            "organization": self.organization,
            "location": self.location,
            "preferences": self.preferences,
            "favor_balance": self.favor_balance,
            "favor_history": self.favor_history,
            "mention_count": self.mention_count,
            "last_mentioned_at": self.last_mentioned_at.isoformat() if self.last_mentioned_at else None,
            "importance": self.importance,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def add_alias(self, alias: str) -> bool:
        """Add a new alias if not already present. Returns True if added."""
        alias_lower = alias.lower()
        existing = [a.lower() for a in (self.aliases or [])]
        if alias_lower not in existing and alias.lower() != self.name.lower():
            self.aliases = [*(self.aliases or []), alias]
            return True
        return False

    def record_mention(self) -> None:
        """Record a new mention of this person."""
        self.mention_count = (self.mention_count or 0) + 1
        self.last_mentioned_at = utc_now()
        self.updated_at = utc_now()

    def record_favor(
        self,
        favor_type: str,
        description: str,
        weight: float = 1.0,
        date: Optional[datetime] = None,
    ) -> None:
        """Record a favor event."""
        if self.favor_history is None:
            self.favor_history = []

        event = {
            "date": (date or utc_now()).isoformat(),
            "type": favor_type,
            "description": description,
            "weight": weight,
        }
        self.favor_history = [*self.favor_history, event]

        if favor_type == "received":
            self.favor_balance = (self.favor_balance or 0) - weight
        elif favor_type == "given":
            self.favor_balance = (self.favor_balance or 0) + weight

        self.updated_at = utc_now()

    def update_preferences(self, new_prefs: Dict[str, Any]) -> None:
        """Merge new preferences into existing preferences."""
        if self.preferences is None:
            self.preferences = {}

        for key, value in new_prefs.items():
            if key not in self.preferences:
                self.preferences[key] = value
            elif isinstance(value, list) and isinstance(self.preferences[key], list):
                existing = set(self.preferences[key])
                self.preferences[key] = list(existing | set(value))
            else:
                self.preferences[key] = value

        self.updated_at = utc_now()

    def days_since_last_contact(self) -> Optional[int]:
        """Calculate days since last mention. Returns None if never mentioned."""
        if not self.last_mentioned_at:
            return None
        delta = utc_now() - self.last_mentioned_at
        return delta.days

    def needs_contact_reminder(self, threshold_days: int = 90) -> bool:
        """Check if this person hasn't been contacted in a while."""
        days = self.days_since_last_contact()
        if days is None:
            return False
        return days >= threshold_days and self.importance >= 5

    def owes_favor(self) -> bool:
        """Check if we owe this person a favor (negative balance)."""
        return (self.favor_balance or 0) < -0.5

    def is_owed_favor(self) -> bool:
        """Check if this person owes us a favor (positive balance)."""
        return (self.favor_balance or 0) > 0.5
