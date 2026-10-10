"""Curation module SQLAlchemy models.

Canonical model definitions for the curation engine.

Tables:
    - curated_events: AI-processed and deduplicated events
    - event_associations: AI-discovered relationships between events
    - curation_jobs: curation job tracking
    - hygiene_run_logs: hygiene run records
    - preparation_items: preparation checklists
    - social_intents: user-expressed social intentions
"""
import uuid
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey,
    Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from ...core.utils.timezone import local_today
from ...db.session import Base


class CuratedEvent(Base):
    """CuratedEvent entity. Stores AI-processed and deduplicated events."""

    __tablename__ = "curated_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=True, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    trip_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("trips.trip_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    trip_name = Column(String(200), nullable=True)
    trip_day_label = Column(String(100), nullable=True)

    original_event_ids = Column(
        JSONB, nullable=False,
        comment="Array of original event IDs that were merged",
    )
    source_types = Column(
        JSONB, nullable=False,
        comment="Array of source types: travel_plan, calendar, extracted_schedule",
    )

    title = Column(String(500), nullable=False)
    normalized_start = Column(DateTime(timezone=True), nullable=False)
    normalized_end = Column(DateTime(timezone=True), nullable=True)
    location = Column(String(200), nullable=True)
    city = Column(
        String(100), nullable=True, index=True,
        comment="City-level location for trip grouping (LLM normalized)",
    )
    event_type = Column(
        String(50), nullable=True,
        comment="business_trip, travel, meeting, appointment, reminder",
    )

    timeline_items = Column(
        JSONB, nullable=True, default=list,
        comment="Array of timeline items: [{time, item, confirmed, note}]",
    )

    dedup_reason = Column(Text, nullable=True, comment="AI explanation of merge")
    enrichments = Column(JSONB, nullable=True, comment="AI-added context")
    confidence = Column(Float, nullable=False, default=0.8)

    status = Column(
        String(20), nullable=False, default="pending",
        comment="pending, confirmed, completed, cancelled, placeholder, expired",
    )
    priority = Column(
        String(10), nullable=False, default="normal",
        comment="low, normal, high, critical",
    )
    visibility_tier = Column(
        String(20), nullable=False, default="standard",
        server_default="standard",
        comment="focus | standard | detail",
    )

    notes = Column(Text, nullable=True, comment="Secretary notes")

    # Pre-generated warm content from Curation Enrichment Phase (Haiku at curation time)
    life_context_hint = Column(
        String(200), nullable=True,
        comment="Pre-generated warm context hint (Haiku at curation time)",
    )
    secretary_note = Column(
        Text, nullable=True,
        comment="Pre-generated secretary annotation (Haiku at curation time)",
    )
    prep_hint = Column(
        String(200), nullable=True,
        comment="Pre-generated preparation hint (Haiku at curation time)",
    )
    enrichment_generated_at = Column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp when enrichment fields were last generated",
    )

    tags = Column(JSONB, nullable=True, default=list, comment="Array of tags for filtering")

    stable_key = Column(
        String(500), nullable=True, unique=True, index=True,
        comment="Deterministic identity key: event_type + entity IDs for cross-curation dedup",
    )
    source_fingerprint = Column(
        String(64), nullable=True,
        comment="MD5 of source data that produced this event",
    )
    semantic_fingerprint = Column(
        String(64), nullable=True,
        comment="MD5 of semantic content (title+start+end+location+type)",
    )

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    associations = relationship(
        "EventAssociation", back_populates="source_event", cascade="all, delete-orphan"
    )
    preparation_item_rows = relationship(
        "PreparationItem",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="PreparationItem.sort_order",
        lazy="selectin",
    )
    trip_plan = relationship(
        "TripPlan",
        backref=backref("curated_events", lazy="dynamic"),
        foreign_keys=[trip_id],
    )

    def __repr__(self):
        return (
            f"<CuratedEvent(id={self.id}, title={self.title}, "
            f"event_type={self.event_type})>"
        )

    @property
    def merged_count(self) -> int:
        if self.original_event_ids:
            return len(self.original_event_ids)
        return 0

    @property
    def is_multi_day(self) -> bool:
        if self.normalized_start and self.normalized_end:
            return self.normalized_start.date() != self.normalized_end.date()
        return False

    @property
    def start_time(self):
        return self.normalized_start

    @property
    def end_time(self):
        return self.normalized_end

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def is_past(self) -> bool:
        if self.normalized_start:
            return self.normalized_start.date() < local_today()
        return False

    def get_trip_label(self) -> Optional[str]:
        if self.trip_plan and self.normalized_start:
            return self.trip_plan.get_day_label(self.normalized_start.date())
        return None


class EventAssociation(Base):
    """EventAssociation entity. AI-discovered relationships between events."""

    __tablename__ = "event_associations"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    source_event_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("curated_events.id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="ID of the curated event",
    )
    target_id = Column(String(100), nullable=False, comment="ID of the associated entity")
    target_type = Column(
        String(50), nullable=False,
        comment="person, memory, place, task, date",
    )

    association_type = Column(
        String(50), nullable=False,
        comment="location, temporal, person, semantic, memory",
    )
    title = Column(String(200), nullable=True)
    reason = Column(Text, nullable=True, comment="AI-generated explanation")

    priority = Column(
        String(50), nullable=False, default="convenient",
        comment="strongly_recommend, convenient, optional",
    )
    confidence = Column(Float, nullable=False, default=0.8)

    is_dismissed = Column(Boolean, nullable=False, default=False)
    is_confirmed = Column(Boolean, nullable=False, default=False)
    dismiss_reason = Column(Text, nullable=True, comment="User correction when dismissing")

    stable_key = Column(
        String(500), nullable=True, unique=True, index=True,
        comment="Deterministic identity key: source_event + target + types",
    )
    source_fingerprint = Column(
        String(64), nullable=True,
        comment="MD5 of source data that produced this association",
    )
    semantic_fingerprint = Column(
        String(64), nullable=True,
        comment="MD5 of semantic content (title+reason+priority+confidence)",
    )

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    source_event = relationship("CuratedEvent", back_populates="associations")

    def __repr__(self):
        return (
            f"<EventAssociation(id={self.id}, title={self.title}, "
            f"type={self.association_type})>"
        )


class CurationJob(Base):
    """CurationJob entity. Tracks curation job execution and results."""

    __tablename__ = "curation_jobs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    trigger_type = Column(
        String(50), nullable=False, comment="scheduled, event, manual"
    )
    status = Column(
        String(50), nullable=False, default="pending",
        comment="pending, running, completed, failed",
    )

    date_range_start = Column(Date, nullable=True)
    date_range_end = Column(Date, nullable=True)

    events_processed = Column(Integer, nullable=False, default=0)
    events_curated = Column(Integer, nullable=False, default=0)
    associations_created = Column(Integer, nullable=False, default=0)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return (
            f"<CurationJob(id={self.id}, status={self.status}, "
            f"trigger={self.trigger_type})>"
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_complete(self) -> bool:
        return self.status in ("completed", "failed")


class HygieneRunLog(Base):
    """HygieneRunLog entity. Persists hygiene run results."""

    __tablename__ = "hygiene_run_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)

    inactive_deleted = Column(Integer, nullable=False, default=0)
    cancelled_deleted = Column(Integer, nullable=False, default=0)
    dismissed_deleted = Column(Integer, nullable=False, default=0)
    auto_completed = Column(Integer, nullable=False, default=0)
    jobs_purged = Column(Integer, nullable=False, default=0)
    total_actions = Column(Integer, nullable=False, default=0)

    status = Column(
        String(20), nullable=False, default="completed",
        comment="completed, failed",
    )
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return (
            f"<HygieneRunLog(id={self.id}, family_id={self.family_id}, "
            f"total_actions={self.total_actions})>"
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class PreparationItem(Base):
    """PreparationItem entity. Independent preparation checklists."""

    __tablename__ = "preparation_items"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("curated_events.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    key = Column(PGUUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True)

    text = Column(String(500), nullable=False)
    source = Column(
        String(50), nullable=False, default="manual",
        comment="manual, ai, travel, memory",
    )
    done = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    event = relationship("CuratedEvent", back_populates="preparation_item_rows")

    def __repr__(self):
        return (
            f"<PreparationItem(id={self.id}, text={self.text!r}, done={self.done})>"
        )


class SocialIntent(Base):
    """SocialIntent entity. User-expressed social intentions from conversations."""

    __tablename__ = "social_intents"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(
        PGUUID(as_uuid=True), nullable=False, index=True,
        comment="Family ID this intent belongs to",
    )
    user_id = Column(
        PGUUID(as_uuid=True), nullable=True,
        comment="User who expressed this intent",
    )

    intent_type = Column(
        String(50), nullable=False,
        comment="Type: meet_person, send_gift, visit_place, call_person, etc.",
    )
    target_person_id = Column(PGUUID(as_uuid=True), nullable=True)
    target_person_name = Column(String(200), nullable=True)
    action_description = Column(Text, nullable=False)

    trigger_type = Column(
        String(50), nullable=False, comment="Trigger type: location, date, event"
    )
    trigger_location = Column(String(200), nullable=True, index=True)
    trigger_date = Column(Date, nullable=True, index=True)
    trigger_event_type = Column(String(50), nullable=True)

    source_memory_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("conversation_memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    confidence = Column(Float, nullable=False, default=0.8)
    status = Column(String(20), nullable=False, default="active", index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return (
            f"<SocialIntent(id={self.id}, intent_type={self.intent_type}, "
            f"target={self.target_person_name}, trigger={self.trigger_type})>"
        )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_fulfilled(self) -> bool:
        return self.status == "fulfilled"

    def mark_fulfilled(self):
        self.status = "fulfilled"
        self.fulfilled_at = func.now()


class ExclusionRule(Base):
    """ExclusionRule entity. Entity-level exclusion for context filtering.

    Persists user decisions to exclude specific entities (memories, members,
    events) from the ContextAssembler pipeline. Supports optional cooldown
    periods after which the exclusion expires automatically.
    """

    __tablename__ = "exclusion_rules"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False)

    entity_type = Column(
        String(50), nullable=False,
        comment="Target entity type: memory, member, event, insight",
    )
    entity_id = Column(
        String(100), nullable=False, index=True,
        comment="UUID string of the excluded entity",
    )

    reason = Column(Text, nullable=True, comment="User or system explanation")
    cooldown_until = Column(
        DateTime(timezone=True), nullable=True,
        comment="If set, rule expires after this timestamp",
    )

    status = Column(
        String(20), nullable=False, default="active", server_default="active",
        comment="active, inactive",
    )
    override_count = Column(
        Integer, nullable=False, default=0, server_default="0",
        comment="Number of times the user overrode (bypassed) this rule",
    )

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return (
            f"<ExclusionRule(id={self.id}, entity_type={self.entity_type}, "
            f"entity_id={self.entity_id}, status={self.status})>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if the cooldown period has passed."""
        if self.cooldown_until is None:
            return False
        from ...core.utils.timezone import utc_now as _utc_now
        return _utc_now() > self.cooldown_until

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "family_id": str(self.family_id),
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "reason": self.reason,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "status": self.status,
            "override_count": self.override_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FamilyPreference(Base):
    """Family personalization preferences -- learned from user behavior.

    Single row per family. JSONB columns store per-dimension preferences.
    All optimization components load this record once per curation run.
    """

    __tablename__ = "family_preferences"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Priority dimension weights (learned from PRIORITY_OVERRIDE feedback)
    # e.g. {"urgency": 0.30, "severity": 0.25, "stakeholder": 0.25, "irrecoverability": 0.20}
    priority_weights = Column(JSONB, nullable=False, server_default="{}")

    # Event type severity overrides (learned)
    # e.g. {"meeting": 0.5, "medical": 0.95, "travel": 0.6}
    event_type_severity = Column(JSONB, nullable=False, server_default="{}")

    # Buffer time preferences (learned from BUFFER_ADJUSTED feedback)
    # e.g. {"default": 15, "location_change": 45, "meeting": 10}
    buffer_minutes = Column(JSONB, nullable=False, server_default="{}")

    # Recommendation type weights (learned from insight/suggestion feedback)
    # e.g. {"relationship_maintenance": 1.3, "gift_reminder": 0.7}
    recommendation_weights = Column(JSONB, nullable=False, server_default="{}")

    # Suppressed recommendation types (from NEVER_AGAIN feedback)
    suppressed_types = Column(JSONB, nullable=False, server_default="[]")

    # Association type effectiveness (from CONTACT_INITIATED/SKIPPED feedback)
    association_weights = Column(JSONB, nullable=False, server_default="{}")

    # Info density preferences
    density_preferences = Column(JSONB, nullable=False, server_default="{}")

    # Secretary annotation preferences
    annotation_preferences = Column(JSONB, nullable=False, server_default="{}")

    # Learning metadata
    last_learned_at = Column(DateTime(timezone=True), nullable=True)
    learning_events_count = Column(Integer, nullable=False, server_default="0")

    # Inferred meal windows from event time distribution (Phase 6)
    inferred_meal_windows = Column(
        JSONB,
        nullable=True,
        comment='{"lunch": [h_start, m_start, h_end, m_end], "dinner": [...]}',
    )
    meal_windows_inferred_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Active load reduction fatigue tracking (E5)
    fatigue_state = Column(
        JSONB,
        nullable=True,
        server_default="{}",
        comment="Active-load-reduction fatigue tracking state",
    )

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    def __repr__(self):
        return (
            f"<FamilyPreference(id={self.id}, family_id={self.family_id}, "
            f"events={self.learning_events_count})>"
        )


class PreferenceSignal(Base):
    """Collects user preference signals (defer, never, dismiss) for batch extraction.

    Part of E2 (Preference Extraction): 3-layer architecture where signals are
    collected here, then batch-extracted into UserPreferenceRule by a daily Celery task.
    """

    __tablename__ = "preference_signals"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )

    signal_type = Column(
        String(32), nullable=False,
        comment="defer, never, dismiss, too_frequent, not_relevant, confirm",
    )
    source_type = Column(
        String(32), nullable=False,
        comment="insight, suggestion, association, curation",
    )
    source_id = Column(PGUUID(as_uuid=True), nullable=False)
    source_context = Column(
        JSONB, nullable=False, server_default="{}",
        comment="Snapshot of source metadata at signal time",
    )
    user_reason = Column(Text, nullable=True)

    category_key = Column(
        String(128), nullable=False,
        comment="Normalized category for batch grouping",
    )
    processed = Column(Boolean, nullable=False, server_default="false")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_preference_signals_user_category", "user_id", "category_key", "processed"),
    )

    def __repr__(self):
        return (
            f"<PreferenceSignal(id={self.id}, signal_type={self.signal_type}, "
            f"category_key={self.category_key})>"
        )


class UserPreferenceRule(Base):
    """LLM-extracted conditional suppression rules from preference signals.

    Part of E2 (Preference Extraction): Haiku batch extraction task reads
    unprocessed PreferenceSignal rows, extracts rules, and stores them here.
    Curation and insight pipelines check active rules before surfacing content.
    """

    __tablename__ = "user_preference_rules"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Condition fields (any combination, all nullable for flexible matching)
    condition_event_type = Column(
        String(64), nullable=True,
        comment="Matches curated_event.event_type",
    )
    condition_suggestion_type = Column(
        String(64), nullable=True,
        comment="Matches insight_type or suggestion category",
    )
    condition_person_id = Column(
        PGUUID(as_uuid=True), nullable=True,
        comment="Matches target member_id",
    )
    condition_location = Column(
        String(128), nullable=True,
        comment="Matches event location",
    )

    # Rule action and metadata
    action = Column(
        String(32), nullable=False,
        comment="suppress, deprioritize",
    )
    confidence = Column(Float, nullable=False, comment="Extraction confidence from LLM")
    explanation = Column(Text, nullable=False, comment="LLM-generated human-readable explanation")
    scope = Column(String(32), nullable=False, comment="event_type, person, global")

    source_signal_count = Column(
        Integer, nullable=False, server_default="3",
        comment="Number of signals that produced this rule",
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_preference_rules_user_active", "user_id", "is_active"),
    )

    def __repr__(self):
        return (
            f"<UserPreferenceRule(id={self.id}, action={self.action}, "
            f"active={self.is_active})>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if the rule has expired."""
        from ...core.utils.timezone import utc_now as _utc_now
        return _utc_now() > self.expires_at


__all__ = [
    "CuratedEvent",
    "EventAssociation",
    "CurationJob",
    "HygieneRunLog",
    "PreparationItem",
    "SocialIntent",
    "ExclusionRule",
    "FamilyPreference",
    "PreferenceSignal",
    "UserPreferenceRule",
]
