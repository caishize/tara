"""RelationshipEdge and ProactiveInsight ORM models."""
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship as orm_relationship

from ....core.utils.timezone import utc_now
from ....db.session import Base


class RelationshipEdge(Base):
    """Edge in the knowledge graph connecting two person profiles."""

    __tablename__ = "relationship_edges"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    person_a_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("person_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_b_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("person_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    relationship_type = Column(String(50), nullable=False)
    strength = Column(Float, default=0.5)
    context = Column(Text, nullable=True)
    bidirectional = Column(Boolean, default=True)

    source_memory_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    person_a = orm_relationship(
        "PersonProfile", foreign_keys=[person_a_id], backref="outgoing_relationships"
    )
    person_b = orm_relationship(
        "PersonProfile", foreign_keys=[person_b_id], backref="incoming_relationships"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "person_a_id": str(self.person_a_id),
            "person_b_id": str(self.person_b_id),
            "relationship_type": self.relationship_type,
            "strength": self.strength,
            "context": self.context,
            "bidirectional": self.bidirectional,
            "source_memory_ids": [str(mid) for mid in (self.source_memory_ids or [])],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def involves_person(self, person_id: UUID) -> bool:
        """Check if this edge involves a specific person."""
        return self.person_a_id == person_id or self.person_b_id == person_id

    def get_other_person_id(self, person_id: UUID) -> Optional[UUID]:
        """Get the ID of the other person in this edge."""
        if self.person_a_id == person_id:
            return self.person_b_id
        elif self.person_b_id == person_id:
            return self.person_a_id
        return None

    def add_source_memory(self, memory_id: UUID) -> None:
        """Add a source memory that supports this relationship."""
        if self.source_memory_ids is None:
            self.source_memory_ids = []
        if memory_id not in self.source_memory_ids:
            self.source_memory_ids = [*self.source_memory_ids, memory_id]
        self.updated_at = utc_now()

    def strengthen(self, amount: float = 0.1) -> None:
        """Strengthen this relationship connection."""
        self.strength = min(1.0, (self.strength or 0.5) + amount)
        self.updated_at = utc_now()

    def weaken(self, amount: float = 0.1) -> None:
        """Weaken this relationship connection."""
        self.strength = max(0.0, (self.strength or 0.5) - amount)
        self.updated_at = utc_now()


class ProactiveInsight(Base):
    """Proactively generated insights from the memory system."""

    __tablename__ = "proactive_insights"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    insight_type = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)

    priority = Column(Integer, default=5)
    urgency = Column(String(20), default="normal")

    related_person_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)
    related_memory_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)
    related_event_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)

    action_options = Column(ARRAY(String), default=list)
    action_data = Column(JSONB, default=dict)

    status = Column(String(20), default="pending")
    shown_at = Column(DateTime(timezone=True), nullable=True)
    acted_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)

    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "insight_type": self.insight_type,
            "title": self.title,
            "content": self.content,
            "priority": self.priority,
            "urgency": self.urgency,
            "related_person_ids": [str(pid) for pid in (self.related_person_ids or [])],
            "related_memory_ids": [str(mid) for mid in (self.related_memory_ids or [])],
            "action_options": self.action_options,
            "status": self.status,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def is_expired(self) -> bool:
        """Check if this insight has expired."""
        if not self.expires_at:
            return False
        return utc_now() > self.expires_at

    def mark_shown(self) -> None:
        """Mark this insight as shown to user."""
        self.status = "shown"
        self.shown_at = utc_now()

    def mark_acted(self) -> None:
        """Mark this insight as acted upon."""
        self.status = "acted"
        self.acted_at = utc_now()

    def dismiss(self) -> None:
        """Dismiss this insight."""
        self.status = "dismissed"
        self.dismissed_at = utc_now()
