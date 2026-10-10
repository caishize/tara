"""Memory module SQLAlchemy models.

Canonical model definitions for the memory system.
Tables:
    - conversation_memories: family knowledge entries
    - memory_associations: inter-memory associations
    - memory_summaries: compressed long-term memory summaries
    - secretary_notes: high-level preference and routine notes

Insight-related models (memory_insights, insight_feedbacks,
user_insight_settings) are canonically defined in the insight module
and re-exported here for backward compatibility.
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import UserDefinedType


class _PgVector(UserDefinedType):
    """Lightweight SQLAlchemy type for pgvector ``vector(N)`` columns.

    Used so that the ORM model declares the column without requiring the
    ``pgvector`` Python package as a runtime dependency.  All actual
    vector operations (cosine distance, casts) are performed via raw SQL
    in the repository layer.

    The actual ``vector(1536)`` column is created by Alembic migrations
    (048 / 090) which handle pgvector extension availability gracefully.
    This type emits ``TEXT`` in DDL so that ``Base.metadata.create_all()``
    (used in tests) never fails due to a missing pgvector extension.
    Repository code uses ``::vector`` casts in raw SQL, so the stored
    column type on disk is irrelevant to the ORM.
    """

    cache_ok = True

    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    def get_col_spec(self) -> str:
        # Emit TEXT so create_all works without pgvector; real column is
        # created via migration DDL as ``vector(1536)``.
        return "TEXT"

    def result_processor(self, dialect, coltype):  # type: ignore[override]
        return None

from ...core.utils.timezone import utc_now
from ...db.session import Base

# Insight enums and models: canonical definitions live in the insight module.
# Re-exported here for backward compatibility.
from ..insight.models import InsightType, FeedbackType, MemoryInsight, InsightFeedback  # noqa: F401


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MemoryType(str, Enum):
    """Types of memories that can be extracted from conversations."""
    EMOTION = "emotion"
    PLAN = "plan"
    SCHEDULE = "schedule"
    RELATIONSHIP = "relationship"
    PREFERENCE = "preference"
    LIFE_EVENT = "life_event"
    LOCATION = "location"
    HEALTH = "health"
    WORK = "work"
    FAVOR = "favor"
    GENERAL = "general"


class MemoryStatus(str, Enum):
    """Status of a memory."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


class SensitivityLevel(str, Enum):
    """Privacy sensitivity levels for memories.

    Controls how a memory may be surfaced:
    - PUBLIC: can freely enter LLM context
    - FAMILY: visible only to same family members
    - PRIVATE: visible only to the creator
    - SENSITIVE: never enters LLM context, UI display only
    """
    PUBLIC = "public"
    FAMILY = "family"
    PRIVATE = "private"
    SENSITIVE = "sensitive"


# Regex patterns for detecting sensitive financial/medical content
_FINANCIAL_PATTERNS = re.compile(
    r"(?i)"
    r"(?:bank\s*account|credit\s*card|debit\s*card|salary|income|"
    r"loan|mortgage|debt|password|pin\s*code|cvv|account\s*number|"
    r"银行|账户|信用卡|贷款|股票|基金|理财|薪资|工资|收入|"
    r"存款|转账|余额|社保|公积金|密码|账号)",
)
_MEDICAL_PATTERNS = re.compile(
    r"(?i)"
    r"(?:diagnosis|prescription|medical\s*record|surgery|chemotherapy|"
    r"psychiatric|depression|anxiety|genetic\s*test|blood\s*test\s*result|"
    r"诊断|处方|病历|手术|化疗|放疗|住院|药物|症状|血压|血糖|CT|MRI|"
    r"精神|抑郁|焦虑|基因检测|验血)",
)


def _flatten_entity_values(entities: Dict[str, Any]) -> List[str]:
    """Recursively flatten entity dict into a list of string tokens for scanning."""
    tokens: List[str] = []
    for key, val in entities.items():
        tokens.append(str(key))
        if isinstance(val, dict):
            tokens.extend(_flatten_entity_values(val))
        elif isinstance(val, (list, tuple)):
            for item in val:
                tokens.append(str(item))
        else:
            tokens.append(str(val))
    return tokens


def classify_sensitivity(
    memory_type: str,
    content: str,
    entities: Optional[Dict[str, Any]] = None,
) -> "SensitivityLevel":
    """Classify the sensitivity level of a memory based on type and content.

    Rules (in priority order):
    1. Content or entity values containing financial/medical keywords → SENSITIVE
    2. HEALTH type → PRIVATE
    3. EMOTION type → PRIVATE
    4. FAVOR type → FAMILY
    5. Everything else → PUBLIC
    """
    # Check content text
    if _FINANCIAL_PATTERNS.search(content) or _MEDICAL_PATTERNS.search(content):
        return SensitivityLevel.SENSITIVE

    # Check entity values if provided
    if entities:
        entity_text = " ".join(_flatten_entity_values(entities))
        if _FINANCIAL_PATTERNS.search(entity_text) or _MEDICAL_PATTERNS.search(entity_text):
            return SensitivityLevel.SENSITIVE

    if memory_type == MemoryType.HEALTH.value:
        return SensitivityLevel.PRIVATE
    if memory_type == MemoryType.EMOTION.value:
        return SensitivityLevel.PRIVATE
    if memory_type == MemoryType.FAVOR.value:
        return SensitivityLevel.FAMILY
    return SensitivityLevel.PUBLIC


class SummaryType(str, Enum):
    """Types of memory summaries."""
    PERSON_PROFILE = "person_profile"
    TOPIC_SUMMARY = "topic_summary"
    PERIOD_SUMMARY = "period_summary"
    EVENT_SUMMARY = "event_summary"
    PREFERENCE_SUMMARY = "preference_summary"


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class ConversationMemory(Base):
    """Stores extracted memories from user conversations."""

    __tablename__ = "conversation_memories"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    # Memory content
    memory_type = Column(String(30), nullable=False, index=True)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)

    # Extracted entities (structured data)
    entities = Column(JSONB, default=dict)

    # Tags for quick filtering
    tags = Column(ARRAY(String), default=list)

    # Importance and confidence
    importance = Column(Integer, default=5)
    confidence = Column(Float, default=0.8)

    # Status and lifecycle
    status = Column(String(20), default=MemoryStatus.ACTIVE.value, index=True)
    sensitivity_level = Column(
        String(20),
        default=SensitivityLevel.PUBLIC.value,
        nullable=False,
    )
    superseded_by = Column(PGUUID(as_uuid=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Trigger conditions for conditional memories
    trigger_conditions = Column(JSONB, default=dict)
    trigger_count = Column(Integer, default=0)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)

    # Vector embedding for semantic search
    embedding = Column(ARRAY(Float), nullable=True)
    # pgvector column for O(log n) HNSW similarity search (mirrors embedding)
    embedding_v = Column(_PgVector(1536), nullable=True)

    # User feedback learning
    feedback_weight = Column(Float, default=1.0)
    dismiss_count = Column(Integer, default=0)
    useful_count = Column(Integer, default=0)

    # Source tracking
    source_session_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("assistant_chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_message_id = Column(PGUUID(as_uuid=True), nullable=True)

    # Idempotent write guard — md5(content + memory_type + sorted entities)
    content_hash = Column(String(64), nullable=True, index=True)

    # Consolidation tracking
    is_consolidated = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    last_recalled_at = Column(DateTime(timezone=True), nullable=True)
    recall_count = Column(Integer, default=0)

    # Relationships
    source_session = relationship(
        "AssistantChatSession", foreign_keys=[source_session_id]
    )
    insights = relationship(
        "MemoryInsight", back_populates="source_memory", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_conv_memories_user_type", "user_id", "memory_type"),
        Index("ix_conv_memories_user_status", "user_id", "status"),
        Index("ix_conv_memories_family_type", "family_id", "memory_type"),
        Index("ix_conv_memories_created", "created_at"),
        Index("ix_conv_memories_user_sensitivity", "user_id", "sensitivity_level"),
        Index("ix_conv_memories_tags", "tags", postgresql_using="gin"),
        Index("ix_conv_memories_entities", "entities", postgresql_using="gin"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "memory_type": self.memory_type,
            "content": self.content,
            "summary": self.summary,
            "entities": self.entities,
            "tags": self.tags,
            "importance": self.importance,
            "confidence": self.confidence,
            "status": self.status,
            "sensitivity_level": self.sensitivity_level,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "recall_count": self.recall_count,
            "trigger_conditions": self.trigger_conditions,
            "trigger_count": self.trigger_count,
            "last_triggered_at": (
                self.last_triggered_at.isoformat()
                if self.last_triggered_at
                else None
            ),
            "content_hash": self.content_hash,
            "has_embedding": self.embedding is not None,
            "has_embedding_v": self.embedding_v is not None,
            "feedback_weight": self.feedback_weight,
            "dismiss_count": self.dismiss_count,
            "useful_count": self.useful_count,
        }

    def has_trigger(self) -> bool:
        """Check if this memory has trigger conditions set."""
        return bool(self.trigger_conditions)

    def matches_trigger(self, trigger_type: str, trigger_value: str) -> bool:
        """Check if the given trigger matches this memory's conditions."""
        if not self.trigger_conditions:
            return False
        cond_type = self.trigger_conditions.get("type")
        cond_value = self.trigger_conditions.get("value", "").lower()
        if cond_type != trigger_type:
            return False
        return cond_value in trigger_value.lower() or trigger_value.lower() in cond_value

    def is_expired(self) -> bool:
        """Check if memory has expired."""
        if self.expires_at is None:
            return False
        return utc_now() > self.expires_at

    def mark_recalled(self):
        """Mark this memory as recalled (increases recall count)."""
        self.last_recalled_at = utc_now()
        self.recall_count += 1


class MemoryAssociation(Base):
    """Links between related memories for building knowledge graph."""

    __tablename__ = "memory_associations"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    memory_id_a = Column(
        PGUUID(as_uuid=True),
        ForeignKey("conversation_memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    memory_id_b = Column(
        PGUUID(as_uuid=True),
        ForeignKey("conversation_memories.id", ondelete="CASCADE"),
        nullable=False,
    )

    association_type = Column(String(30), nullable=False)
    strength = Column(Float, default=0.5)
    reason = Column(Text)
    is_auto_generated = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_memory_assoc_a", "memory_id_a"),
        Index("ix_memory_assoc_b", "memory_id_b"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "memory_id_a": str(self.memory_id_a),
            "memory_id_b": str(self.memory_id_b),
            "association_type": self.association_type,
            "strength": self.strength,
            "reason": self.reason,
        }


class MemorySummary(Base):
    """Consolidated memory summaries for long-term storage."""

    __tablename__ = "memory_summaries"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    summary_type = Column(String(30), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)

    source_memory_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list)
    consolidated_entities = Column(JSONB, default=dict)
    tags = Column(ARRAY(String), default=list)

    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)

    importance = Column(Integer, default=5)
    confidence_score = Column(Float, nullable=True)

    last_updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "summary_type": self.summary_type,
            "title": self.title,
            "content": self.content,
            "source_memory_ids": [
                str(mid) for mid in (self.source_memory_ids or [])
            ],
            "consolidated_entities": self.consolidated_entities,
            "tags": self.tags,
            "period_start": (
                self.period_start.isoformat() if self.period_start else None
            ),
            "period_end": (
                self.period_end.isoformat() if self.period_end else None
            ),
            "importance": self.importance,
            "confidence_score": self.confidence_score,
            "last_updated_at": (
                self.last_updated_at.isoformat() if self.last_updated_at else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def add_source_memory(self, memory_id: UUID) -> None:
        """Add a source memory ID to the list."""
        if self.source_memory_ids is None:
            self.source_memory_ids = []
        if memory_id not in self.source_memory_ids:
            self.source_memory_ids = [*self.source_memory_ids, memory_id]

    def merge_entities(self, new_entities: Dict[str, Any]) -> None:
        """Merge new entities into consolidated entities."""
        if self.consolidated_entities is None:
            self.consolidated_entities = {}

        for key, value in new_entities.items():
            if key not in self.consolidated_entities:
                self.consolidated_entities[key] = value
            elif isinstance(value, list) and isinstance(
                self.consolidated_entities[key], list
            ):
                existing = set(self.consolidated_entities[key])
                self.consolidated_entities[key] = list(existing | set(value))
            else:
                self.consolidated_entities[key] = value

        self.updated_at = utc_now()


# ---------------------------------------------------------------------------
# Re-exported from dedicated model files (canonical definitions)
# ---------------------------------------------------------------------------
from .secretary_note_model import NoteCategory, NoteLifeType, NoteStatus, SecretaryNote  # noqa: F401
from ..insight.insight_settings_model import UserInsightSettings  # noqa: F401

# Ensure AssistantChatSession is registered in the SQLAlchemy mapper registry
# before any mapper configuration runs. ConversationMemory.source_session
# references it via string ("AssistantChatSession").
from ..conversation.models import AssistantChatSession as _AssistantChatSession  # noqa: F401


__all__ = [
    # Memory Enums
    "MemoryType",
    "MemoryStatus",
    "SensitivityLevel",
    "classify_sensitivity",
    "_flatten_entity_values",
    "SummaryType",
    "NoteCategory",
    "NoteLifeType",
    "NoteStatus",
    # Insight Enums (re-exported from insight module)
    "InsightType",
    "FeedbackType",
    # Memory ORM Models
    "ConversationMemory",
    "MemoryAssociation",
    "MemorySummary",
    "SecretaryNote",
    # Insight ORM Models (re-exported from insight module)
    "MemoryInsight",
    "InsightFeedback",
    "UserInsightSettings",
]
