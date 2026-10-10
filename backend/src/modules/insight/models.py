"""Insight module SQLAlchemy models.

Canonical model definitions for the insight system.
Tables:
    - memory_insights: AI-generated insights (legacy, migration period)
    - insight_feedbacks: user feedback on insights (legacy, migration period)
    - user_insight_settings: configurable insight cycle parameters
    - insights: unified insight table (new)
    - insight_entities: many-to-many entity associations (new)

Note: MemoryInsight and InsightFeedback have foreign keys to the
conversation_memories table (memory module), but logically belong
to the insight domain.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from ...core.utils.timezone import utc_now
from ...db.session import Base


# ---------------------------------------------------------------------------
# Enums (legacy — kept for migration period)
# ---------------------------------------------------------------------------


class InsightType(str, Enum):
    """Types of insights that can be generated."""
    # Core types (memory_insights table)
    REMINDER = "reminder"
    SUGGESTION = "suggestion"
    OBSERVATION = "observation"
    CORRELATION = "correlation"
    FOLLOWUP = "followup"
    # Proactive sub-types (memory_insights table)
    RELATIONSHIP_MAINTENANCE = "relationship_maintenance"
    FAVOR_REMINDER = "favor_reminder"
    PATTERN_OBSERVATION = "pattern_observation"
    EVENT_PREPARATION = "event_preparation"
    # Briefing domain types (user_insights table)
    TIME = "time"
    RELATIONSHIP = "relationship"
    FAVOR = "favor"
    EFFICIENCY = "efficiency"
    HEALTH = "health"
    FINANCE = "finance"
    MEMORY = "memory"
    # Engine v2 types
    SOCIAL_OBLIGATION = "social_obligation"
    POSITIVE_AFFIRMATION = "positive_affirmation"
    TREND_ALERT = "trend_alert"
    PREP_CHAIN = "prep_chain"
    LIFE_ADMIN = "life_admin"
    WEATHER_CARE = "weather_care"
    FAMILY_CLIMATE = "family_climate"
    HABIT_TRACKING = "habit_tracking"


class FeedbackType(str, Enum):
    """Types of user feedback on insights."""
    USEFUL = "useful"
    NOT_USEFUL = "not_useful"
    TOO_FREQUENT = "too_frequent"
    NOT_RELEVANT = "not_relevant"
    INCORRECT = "incorrect"
    DEFER = "defer"          # User wants to defer this type of insight temporarily
    NEVER = "never"          # User never wants this type of insight again
    NOT_NOW = "not_now"      # Not the right time (merged with defer on backend)
    ACKNOWLEDGED = "acknowledged"  # User confirms awareness, 90-day snooze


class ActionType(str, Enum):
    """Typed action dispatch for insight action chips (PLAN-002).

    Maps to concrete user flows on the mobile client:
    - OPEN_CHAT: Open message compose with recipient pre-filled
    - CREATE_PENDING_ACTION: Create a PendingAction card with context
    - OPEN_DETAIL: Open insight detail view
    - DISMISS: Record dismissal and remove insight
    - GENERATE_GREETING: Generate a greeting/blessing message
    - SNOOZE: Snooze the insight for later
    - SEND_CARE_MESSAGE: Send a care message to a person
    - ACKNOWLEDGE: Acknowledge awareness of the insight
    - SHARE: Share the insight content
    - CREATE_MEMORY: Create a memory record from the insight
    - SET_REMINDER: Set a reminder related to the insight
    """
    OPEN_CHAT = "open_chat"
    CREATE_PENDING_ACTION = "create_pending_action"
    OPEN_DETAIL = "open_detail"
    DISMISS = "dismiss"
    GENERATE_GREETING = "generate_greeting"
    SNOOZE = "snooze"
    SEND_CARE_MESSAGE = "send_care_message"
    ACKNOWLEDGE = "acknowledge"
    SHARE = "share"
    CREATE_MEMORY = "create_memory"
    SET_REMINDER = "set_reminder"


# ---------------------------------------------------------------------------
# Enums (new unified insight system)
# ---------------------------------------------------------------------------


class ImplicitFeedbackType(str, Enum):
    """Types of implicit user feedback inferred from behavior."""
    VIEWED_NO_ACTION = "viewed_no_action"       # Saw insight, didn't act
    ACTION_ABANDONED = "action_abandoned"        # Started action, didn't complete
    TOPIC_MENTIONED = "topic_mentioned"          # Mentioned related topic in conversation
    SUGGESTION_FOLLOWED = "suggestion_followed"  # Actually did what was suggested


class InsightStatus(str, Enum):
    """Lifecycle status of a unified insight."""
    PENDING = "pending"
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    ACTED = "acted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class InsightSource(str, Enum):
    """Origin of an insight."""
    SCHEDULED = "scheduled"
    TRIP_EVENT = "trip_event"
    REFLECTION = "reflection"
    MANUAL = "manual"


class GenerationLevel(str, Enum):
    """Tier of generation engine used."""
    L1_RULE = "L1"
    L2_HAIKU = "L2"
    L3_SONNET = "L3"


class InformationTier(str, Enum):
    """Information delivery tier for triage."""
    L0_AUTO = "L0_AUTO"       # Handled automatically, no user notification
    L1_PASSIVE = "L1_PASSIVE"  # Mentioned in passing when user is available
    L2_FORMAL = "L2_FORMAL"   # Explicit notification with action options


class ThreadStatus(str, Enum):
    """Status of a tracked information thread."""
    MONITORING = "monitoring"
    APPROACHING = "approaching"
    ACTIVE = "active"
    RESOLVED = "resolved"


# ---------------------------------------------------------------------------
# Status transition rules
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: Dict[InsightStatus, frozenset] = {
    InsightStatus.PENDING: frozenset({
        InsightStatus.ACTIVE,
        InsightStatus.DISMISSED,
        InsightStatus.EXPIRED,
    }),
    InsightStatus.ACTIVE: frozenset({
        InsightStatus.ACKNOWLEDGED,
        InsightStatus.ACTED,
        InsightStatus.DISMISSED,
        InsightStatus.EXPIRED,
    }),
    InsightStatus.ACKNOWLEDGED: frozenset({
        InsightStatus.ACTIVE,
        InsightStatus.ACTED,
        InsightStatus.DISMISSED,
        InsightStatus.EXPIRED,
    }),
    InsightStatus.ACTED: frozenset(),
    InsightStatus.DISMISSED: frozenset(),
    InsightStatus.EXPIRED: frozenset(),
}


# ---------------------------------------------------------------------------
# Suppression & TTL configuration
# ---------------------------------------------------------------------------

SUPPRESSION_WINDOWS: Dict[str, timedelta] = {
    "favor": timedelta(days=30),
    "relationship": timedelta(days=30),
    "memory": timedelta(days=14),
    "time": timedelta(days=14),
    "efficiency": timedelta(days=60),
    "finance": timedelta(days=60),
    "health": timedelta(days=14),
}

SUPPRESSION_THRESHOLDS: Dict[str, int] = {
    "favor": 5,
    "relationship": 5,
    "health": 4,
    "efficiency": 3,
    "finance": 3,
    "time": 3,
    "memory": 3,
}

ACKNOWLEDGED_SNOOZE_DAYS = 90

TYPE_TTL_OVERRIDES: Dict[str, Optional[timedelta]] = {
    "favor": None,
    "relationship": timedelta(days=60),
    "memory": timedelta(days=30),
    "time": None,
    "efficiency": timedelta(days=7),
    "finance": timedelta(days=14),
    "health": timedelta(days=3),
}


# ---------------------------------------------------------------------------
# Pydantic models (serialization / pipeline data)
# ---------------------------------------------------------------------------


class SourceContext(BaseModel):
    """Structured provenance metadata attached to an Insight."""
    signal_ids: List[str] = Field(default_factory=list)
    ea_ids: List[str] = Field(default_factory=list)
    generation_batch_id: Optional[str] = None
    person_profile_ids: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    health_subtype: Optional[str] = None
    health_event: Optional[bool] = None
    reactivated_from: Optional[str] = None
    reactivation_depth: int = 0
    commitment_type: Optional[str] = None
    social_intent: Optional[bool] = None
    reason: Optional[str] = None

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidTransitionError(ValueError):
    """Raised when an insight status transition is not allowed."""
    pass


class InsightNotActionableError(ValueError):
    """Raised when an action is attempted on a non-actionable insight."""
    pass


# ---------------------------------------------------------------------------
# Dataclasses (pipeline internal use)
# ---------------------------------------------------------------------------


@dataclass
class EntitySpec:
    """Typed entity reference with role for InsightEntity creation.

    entity_type: person, trip, event, important_date, event_association,
                 favor, commitment, memory
    role: primary, related, mentioned, source (must match CHECK constraint)
    """
    entity_type: str
    entity_id: str  # UUID as string
    role: str = "related"


@dataclass
class InsightCandidate:
    """Pre-persistence insight candidate produced by LLM, consumed by the pipeline."""
    insight_type: str
    title: str
    content: str
    importance: int = 50  # 0-100 (design spec)
    urgency: int = 50  # 0-100
    entities: List[EntitySpec] = field(default_factory=list)
    source_context: Dict[str, Any] = field(default_factory=dict)
    suggested_action: Optional[str] = None
    action_options: Optional[list] = None
    dedup_key: str = ""
    expires_at: Optional[datetime] = None
    # Engine v2 metadata
    context_hint: Optional[str] = None
    best_action_window: Optional[str] = None
    information_tier: str = InformationTier.L2_FORMAL.value
    generation_level: str = GenerationLevel.L2_HAIKU.value

    # LLM-aware dedup disposition: NEW (default), KEEP, or UPDATE
    disposition: str = "NEW"
    existing_id: Optional[str] = None

    # Populated by pipeline after generation
    user_id: Optional[UUID] = None
    family_id: Optional[UUID] = None

    # --- Backward-compat helpers for signal-based entity access ---
    @property
    def person_ids(self) -> List[str]:
        return [e.entity_id for e in self.entities if e.entity_type == "person"]

    @property
    def event_ids(self) -> List[str]:
        return [e.entity_id for e in self.entities if e.entity_type == "event"]

    @property
    def source_entity_ids(self) -> List[str]:
        return [e.entity_id for e in self.entities if e.role == "source"]


# ---------------------------------------------------------------------------
# ORM Models (legacy — kept for migration period)
# ---------------------------------------------------------------------------


class MemoryInsight(Base):
    """AI-generated insights based on memories."""

    __tablename__ = "memory_insights"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    # Insight content
    insight_type = Column(String(30), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)

    # Priority and timing
    priority = Column(Integer, default=5)
    urgency = Column(String(20), default="normal")

    # Source memory
    source_memory_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("conversation_memories.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Related entities
    related_memory_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)
    related_event_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)
    related_trip_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)
    related_member_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)

    # Action suggestions
    action_options = Column(ARRAY(String), default=list)
    action_data = Column(JSONB, default=dict)

    # Status
    status = Column(String(20), default="pending")
    shown_at = Column(DateTime(timezone=True), nullable=True)
    acted_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    is_promoted = Column(Boolean, default=False, comment="Whether promoted to user_insights")

    # Relationships
    source_memory = relationship("ConversationMemory", back_populates="insights")

    __table_args__ = (
        Index("ix_memory_insights_user_status", "user_id", "status"),
        Index("ix_memory_insights_user_type", "user_id", "insight_type"),
        Index("ix_memory_insights_priority", "priority"),
        Index(
            "ix_memory_insights_trip_ids",
            "related_trip_ids",
            postgresql_using="gin",
        ),
        Index(
            "ix_memory_insights_member_ids",
            "related_member_ids",
            postgresql_using="gin",
        ),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "insight_type": self.insight_type,
            "title": self.title,
            "content": self.content,
            "priority": self.priority,
            "urgency": self.urgency,
            "related_memory_ids": [
                str(mid) for mid in (self.related_memory_ids or [])
            ],
            "action_options": self.action_options,
            "action_data": self.action_data,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class InsightFeedback(Base):
    """User feedback on insights for learning and improvement."""

    __tablename__ = "insight_feedbacks"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    insight_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("memory_insights.id", ondelete="CASCADE"),
        nullable=False,
    )

    feedback_type = Column(String(30), nullable=False)
    comment = Column(Text, nullable=True)

    source_memory_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("conversation_memories.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    insight = relationship("MemoryInsight", backref="feedbacks")
    source_memory = relationship("ConversationMemory", backref="feedbacks")

    __table_args__ = (
        Index("ix_insight_feedback_user", "user_id"),
        Index("ix_insight_feedback_insight", "insight_id"),
        Index("ix_insight_feedback_type", "feedback_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "insight_id": str(self.insight_id),
            "feedback_type": self.feedback_type,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# ORM Models (new unified insight system)
# ---------------------------------------------------------------------------


class Insight(Base):
    """Unified insight record replacing MemoryInsight + UserInsight."""

    __tablename__ = "insights"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    # Content
    insight_type = Column(String(30), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    suggested_action = Column(Text, nullable=True)
    action_options = Column(JSONB, nullable=True, default=None,
                            comment="List[ActionSpec] as JSON for typed action dispatch")

    # Scoring
    importance = Column(Integer, nullable=False, default=50)
    urgency = Column(Integer, nullable=False, default=50)

    # Lifecycle
    status = Column(
        String(20), nullable=False, default=InsightStatus.PENDING.value,
        comment="pending, active, acknowledged, acted, dismissed, expired",
    )
    source = Column(
        String(30), nullable=False, default=InsightSource.SCHEDULED.value,
        comment="scheduled, trip_event, reflection, manual",
    )

    # Feedback
    feedback = Column(String(20), nullable=True)
    feedback_at = Column(DateTime(timezone=True), nullable=True)
    feedback_source = Column(
        String(30), nullable=False, default="user", server_default="user",
        comment="user, cascade_dismiss, cascade_preserved, cascade_reactivated, "
                "hygiene_event_past, hygiene_entity_deleted, hygiene_date_past",
    )

    # Deduplication
    dedup_key = Column(String(255), nullable=True,
                       comment="Obligation identity key: favor:{favor_id}, "
                               "relationship:{person_id}, commitment:{commitment_id}, "
                               "time:{important_date_id}:{event_id}")

    # Provenance
    source_context = Column(JSONB, nullable=False, default=dict,
                            server_default=text("'{}'::jsonb"),
                            comment="SourceContext serialized as JSON")

    # Delivery tracking
    shown_at = Column(DateTime(timezone=True), nullable=True)
    delivered_via_briefing = Column(Boolean, nullable=False, default=False)
    delivered_via_sidekick = Column(Boolean, nullable=False, default=False)
    delivered_via_kanban = Column(Boolean, nullable=False, default=False)
    delivered_via_push = Column(Boolean, nullable=False, default=False)

    # Snooze / suppression
    snoozed_until = Column(DateTime(timezone=True), nullable=True)
    regen_suppressed_until = Column(DateTime(timezone=True), nullable=True)

    # Engine v2 metadata
    context_hint = Column(Text, nullable=True)
    best_action_window = Column(String(100), nullable=True)
    information_tier = Column(String(20), nullable=True, default=InformationTier.L2_FORMAL.value)
    generation_level = Column(String(10), nullable=True, default=GenerationLevel.L2_HAIKU.value)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acted_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    pushed_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    entities = relationship(
        "InsightEntity",
        back_populates="insight",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        # Kanban: active insight list sorted by importance/urgency (DESC for top-N queries)
        Index("ix_insights_kanban", "user_id",
              text("importance DESC"), text("urgency DESC"), text("created_at DESC"),
              postgresql_where=text("status IN ('pending', 'active')")),
        # Briefing: high-importance pending insights (DESC for top-N queries)
        Index("ix_insights_briefing", "user_id", text("importance DESC"),
              postgresql_where=text("status = 'pending' AND importance >= 60")),
        # Dedup: one active record per user+dedup_key (UNIQUE)
        Index("ix_insights_dedup", "user_id", "dedup_key", unique=True,
              postgresql_where=text("dedup_key IS NOT NULL AND status NOT IN ('dismissed', 'acted', 'expired')")),
        # Family dimension queries
        Index("ix_insights_family", "family_id", "status"),
        # Lifecycle: expiry + snooze + suppression cleanup
        Index("ix_insights_lifecycle", "expires_at", "snoozed_until", "regen_suppressed_until",
              postgresql_where=text("status IN ('pending', 'active', 'dismissed')")),
        # Supplementary indexes
        Index("ix_insights_user_status", "user_id", "status"),
        Index("ix_insights_created", "created_at"),
    )


class InsightEntity(Base):
    """Many-to-many association between insights and domain entities."""

    __tablename__ = "insight_entities"

    insight_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("insights.id", ondelete="CASCADE"),
        primary_key=True,
    )
    entity_type = Column(String(30), primary_key=True)
    entity_id = Column(PGUUID(as_uuid=True), primary_key=True)
    role = Column(String(30), nullable=False, default="related")
    adopted_at = Column(DateTime(timezone=True), nullable=True)
    done_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    insight = relationship("Insight", back_populates="entities")

    __table_args__ = (
        # Reverse lookup: which insights reference a given entity
        Index("ix_insight_entities_entity", "entity_type", "entity_id"),
        # Source reverse lookup: domain entity → insight
        Index("ix_ie_source", "entity_type", "entity_id",
              postgresql_where=text("role = 'source'")),
        # adopted_at only on primary/related entities
        CheckConstraint(
            "adopted_at IS NULL OR role IN ('primary', 'related')",
            name="chk_adopt_role",
        ),
        # done_at only on adopted entities
        CheckConstraint(
            "done_at IS NULL OR adopted_at IS NOT NULL",
            name="chk_done_adopt",
        ),
    )


class TrackedThread(Base):
    """Persistent tracking thread for an evolving information stream."""

    __tablename__ = "tracked_threads"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    thread_type = Column(String(50), nullable=False, index=True)
    status = Column(
        String(30), nullable=False,
        default=ThreadStatus.MONITORING.value,
        index=True,
    )
    entity_refs = Column(
        JSONB, nullable=False, default=dict,
        server_default=text("'{}'::jsonb"),
    )
    checkpoints = Column(
        JSONB, nullable=False, default=list,
        server_default=text("'[]'::jsonb"),
    )
    context_log = Column(
        JSONB, nullable=False, default=list,
        server_default=text("'[]'::jsonb"),
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        default=utc_now, onupdate=utc_now,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Re-exports
# ---------------------------------------------------------------------------

# Re-exported from dedicated model file (canonical definition)
from .insight_settings_model import UserInsightSettings  # noqa: F401


__all__ = [
    # Enums (legacy)
    "InsightType",
    "FeedbackType",
    "ActionType",
    # Enums (new)
    "ImplicitFeedbackType",
    "InsightStatus",
    "InsightSource",
    "GenerationLevel",
    "InformationTier",
    "ThreadStatus",
    # Transition rules
    "VALID_TRANSITIONS",
    # Suppression & TTL
    "ACKNOWLEDGED_SNOOZE_DAYS",
    "SUPPRESSION_WINDOWS",
    "SUPPRESSION_THRESHOLDS",
    "TYPE_TTL_OVERRIDES",
    # Pydantic models
    "SourceContext",
    # Exceptions
    "InvalidTransitionError",
    "InsightNotActionableError",
    # Dataclasses
    "EntitySpec",
    "InsightCandidate",
    # ORM Models (legacy)
    "MemoryInsight",
    "InsightFeedback",
    "UserInsightSettings",
    # ORM Models (new)
    "Insight",
    "InsightEntity",
    "TrackedThread",
]
