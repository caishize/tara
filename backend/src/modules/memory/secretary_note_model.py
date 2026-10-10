"""
Secretary Note Model - High-level preferences and routines

Canonical definition for the memory module.
Provides:
- SecretaryNote: Records of high-level preferences, routines, and observations
- Used by the AI secretary to provide personalized assistance
- Surfaced based on context and trigger keywords
"""

from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import Column, ForeignKey, String, Text, DateTime, Float, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY

from ...core.utils.timezone import utc_now
from ...db.session import Base


class NoteCategory(str, Enum):
    """Categories of secretary notes."""
    PREFERENCE = "preference"    # User preferences (seating, food, etc.)
    ROUTINE = "routine"          # Regular patterns and habits
    IMPORTANT = "important"      # Important information to remember
    TODO = "todo"                # Tasks or things to follow up on
    OBSERVATION = "observation"  # Patterns observed by the secretary


class NoteStatus(str, Enum):
    """Status of a secretary note."""
    ACTIVE = "active"        # Currently relevant
    COMPLETED = "completed"  # Task completed (for TODO category)
    ARCHIVED = "archived"    # No longer relevant
    SUPERSEDED = "superseded"  # Replaced by newer information


class NoteLifeType(str, Enum):
    """Lifecycle type for secretary notes (L1 fact classification)."""
    PERMANENT = "permanent"    # Long-lived facts (e.g., "prefers aisle seats")
    TRANSIENT = "transient"    # Short-lived facts (e.g., "currently on a diet")


class SecretaryNote(Base):
    """
    High-level notes recorded by the AI secretary.

    These notes capture preferences, routines, and important information
    that help the secretary provide personalized assistance.

    Examples:
    - Preference: "User prefers aisle seats" (triggered when booking flights)
    - Routine: "Child finishes school at 4 PM" (triggered when discussing schedule)
    - Important: "Father-in-law has diabetes, avoid sweets" (triggered when selecting gifts)
    - Observation: "User mentioned work stress 3 weeks in a row" (for proactive care)
    """
    __tablename__ = "secretary_notes"
    __table_args__ = {"extend_existing": True}

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    # Note content
    category = Column(String(30), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)

    # Confidence and verification
    confidence = Column(Float, default=0.8)  # 0-1, how confident the extraction is
    is_user_confirmed = Column(Boolean, default=False)  # User explicitly confirmed

    # Source tracking
    source_memory_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)
    observation_count = Column(Integer, default=1)  # How many times observed

    # Priority and status
    priority = Column(Integer, default=5)  # 1-10 scale
    status = Column(String(20), default=NoteStatus.ACTIVE.value)

    # Fact lifecycle (L1 classification)
    life_type = Column(String(20), default=NoteLifeType.PERMANENT.value, nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=True)

    # Provenance chain — records source/confidence for each extraction
    provenance = Column(JSONB, default=list)

    # Fact version — incremented on each update for version chain tracking
    version = Column(Integer, default=1, nullable=False)

    # Points to the newer note that superseded this one
    superseded_by = Column(
        PGUUID(as_uuid=True),
        ForeignKey("secretary_notes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Detected contradictions with other notes
    contradiction_flags = Column(JSONB, default=list)

    # Contextual triggers - when to surface this note
    trigger_keywords = Column(ARRAY(String), default=list)

    trigger_contexts = Column(JSONB, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    last_surfaced_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "confidence": self.confidence,
            "is_user_confirmed": self.is_user_confirmed,
            "source_memory_ids": [str(mid) for mid in (self.source_memory_ids or [])],
            "observation_count": self.observation_count,
            "priority": self.priority,
            "status": self.status,
            "life_type": self.life_type,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "provenance": self.provenance,
            "version": self.version,
            "superseded_by": str(self.superseded_by) if self.superseded_by else None,
            "contradiction_flags": self.contradiction_flags,
            "trigger_keywords": self.trigger_keywords,
            "trigger_contexts": self.trigger_contexts,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_surfaced_at": self.last_surfaced_at.isoformat() if self.last_surfaced_at else None,
        }

    def matches_keywords(self, text: str) -> bool:
        """Check if the text matches any trigger keywords."""
        if not self.trigger_keywords:
            return False
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.trigger_keywords)

    def matches_context(self, context: Dict[str, Any]) -> bool:
        """Check if the context matches trigger contexts."""
        if not self.trigger_contexts:
            return False

        for key, values in self.trigger_contexts.items():
            if key in context:
                context_value = context[key]
                if isinstance(context_value, str):
                    if context_value in values:
                        return True
                elif isinstance(context_value, list):
                    if any(v in values for v in context_value):
                        return True
        return False

    def record_observation(self, memory_id: Optional[UUID] = None) -> None:
        """Record a new observation that supports this note."""
        self.observation_count = (self.observation_count or 1) + 1
        if memory_id and self.source_memory_ids is not None:
            if memory_id not in self.source_memory_ids:
                self.source_memory_ids = [*self.source_memory_ids, memory_id]
        # Increase confidence with more observations (asymptotic to 1.0)
        self.confidence = min(0.99, self.confidence + 0.05 * (1 - self.confidence))
        self.updated_at = utc_now()

    def mark_surfaced(self) -> None:
        """Mark this note as surfaced (shown to user)."""
        self.last_surfaced_at = utc_now()

    def confirm(self) -> None:
        """User confirmed this note is accurate."""
        self.is_user_confirmed = True
        self.confidence = 1.0
        self.updated_at = utc_now()

    def archive(self) -> None:
        """Archive this note."""
        self.status = NoteStatus.ARCHIVED.value
        self.updated_at = utc_now()

    def complete(self) -> None:
        """Mark TODO note as completed."""
        if self.category == NoteCategory.TODO.value:
            self.status = NoteStatus.COMPLETED.value
            self.updated_at = utc_now()

    def supersede(self, new_note_id: UUID) -> None:
        """Mark this note as superseded by a newer note."""
        self.superseded_by = new_note_id
        self.status = NoteStatus.SUPERSEDED.value
        self.updated_at = utc_now()

    def add_contradiction(self, conflicting_note_id: UUID, field: str = "content") -> None:
        """Record a detected contradiction with another note."""
        if self.contradiction_flags is None:
            self.contradiction_flags = []
        self.contradiction_flags = [
            *self.contradiction_flags,
            {
                "conflicting_note_id": str(conflicting_note_id),
                "field": field,
                "detected_at": utc_now().isoformat(),
            },
        ]
        self.updated_at = utc_now()

    def increment_version(self) -> None:
        """Increment the fact version number."""
        self.version = (self.version or 1) + 1
        self.updated_at = utc_now()

    def is_expired(self) -> bool:
        """Check if a transient note has expired."""
        if self.life_type != NoteLifeType.TRANSIENT.value:
            return False
        if self.valid_until is None:
            return False
        return utc_now() > self.valid_until
