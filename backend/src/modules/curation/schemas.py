"""
Curation schemas for API responses.

Provides request/response models for curated timeline and graph endpoints.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of curated events."""
    BUSINESS_TRIP = "business_trip"
    TRAVEL = "travel"
    MEETING = "meeting"
    APPOINTMENT = "appointment"
    REMINDER = "reminder"
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"
    HOLIDAY = "holiday"
    HOLIDAY_SOLAR_TERM = "holiday_solar_term"
    SOLAR_TERM = "solar_term"
    OTHER = "other"


class AssociationType(str, Enum):
    """Types of event associations."""
    LOCATION = "location"
    TEMPORAL = "temporal"
    PERSON = "person"
    SEMANTIC = "semantic"
    MEMORY = "memory"
    TASK = "task"


class AssociationPriority(str, Enum):
    """Priority levels for associations."""
    STRONGLY_RECOMMEND = "strongly_recommend"
    CONVENIENT = "convenient"
    OPTIONAL = "optional"


class TargetType(str, Enum):
    """Types of association targets."""
    PERSON = "person"
    MEMORY = "memory"
    PLACE = "place"
    TASK = "task"
    DATE = "date"
    GIFT = "gift"


class TriggerType(str, Enum):
    """Types of curation triggers."""
    SCHEDULED = "scheduled"
    EVENT = "event"
    MANUAL = "manual"
    TRIP_CANCELLED = "trip_cancelled"
    TRIP_CREATED = "trip_created"
    TRIP_UPDATED = "trip_updated"


class JobStatus(str, Enum):
    """Curation job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Timeline Item Models ---

class TimelineItem(BaseModel):
    """A single item in a multi-day event timeline."""
    time: str = Field(..., description="ISO datetime or time string")
    item: str = Field(..., description="Description of the timeline item")
    confirmed: bool = Field(True, description="Whether this item is confirmed")
    note: Optional[str] = Field(None, description="Additional note for the item")


class UnconfirmedItem(BaseModel):
    """An item that needs user confirmation."""
    event_id: str
    item: str
    question: str = Field(..., description="Question to ask user for confirmation")


# --- Curated Event Models ---

class CuratedTimelineEvent(BaseModel):
    """A curated event for timeline display."""
    id: str
    title: str
    event_type: Optional[EventType] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[str] = None
    timeline_items: List[TimelineItem] = Field(default_factory=list)
    source_types: List[str] = Field(default_factory=list)
    merged_count: int = 1
    dedup_reason: Optional[str] = None
    confidence: float = 0.8
    enrichments: Optional[Dict[str, Any]] = None
    original_event_ids: List[str] = Field(default_factory=list)
    trip_id: Optional[str] = None
    trip_name: Optional[str] = None
    trip_day_label: Optional[str] = None
    visibility_tier: str = "standard"

    class Config:
        from_attributes = True


# --- Association Models ---

class ConflictPriority(str, Enum):
    """Priority levels for schedule conflicts."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConflictAlert(BaseModel):
    """A schedule conflict detected between curated events."""
    id: str
    title: str = "日程冲突"
    description: str
    suggestion: str
    conflicting_event_ids: List[str] = Field(default_factory=list)
    priority: ConflictPriority = ConflictPriority.HIGH
    pending_action_id: Optional[str] = None
    auto_resolved: bool = False
    resolution_note: Optional[str] = None


class AssociationItem(BaseModel):
    """An AI-discovered association for graph display."""
    id: str
    title: str
    target_id: str
    target_type: TargetType
    association_type: AssociationType
    reason: str = Field(..., description="AI-generated explanation of the association")
    priority: AssociationPriority = AssociationPriority.CONVENIENT
    confidence: float = 0.8
    is_dismissed: bool = False
    is_confirmed: bool = False
    related_member_id: Optional[str] = None
    related_member_name: Optional[str] = None

    class Config:
        from_attributes = True


# --- Response Models ---

class CuratedTimelineResponse(BaseModel):
    """Response for curated timeline endpoint."""
    events: List[CuratedTimelineEvent]
    last_curated_at: Optional[datetime] = None
    has_unconfirmed: bool = False
    unconfirmed_count: int = 0
    unconfirmed_items: List[UnconfirmedItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0
    has_more: bool = False


class CuratedGraphResponse(BaseModel):
    """Response for curated graph endpoint."""
    core_event: Optional[CuratedTimelineEvent] = None
    associations: List[AssociationItem] = Field(default_factory=list)
    conflicts: List[ConflictAlert] = Field(default_factory=list)
    last_curated_at: Optional[datetime] = None


class CurationJobResponse(BaseModel):
    """Response for curation job status."""
    job_id: str
    status: JobStatus
    trigger_type: TriggerType
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    events_processed: int = 0
    events_curated: int = 0
    associations_created: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class CurationRequestResponse(BaseModel):
    """Response for manual curation request."""
    job_id: str
    status: str
    message: str = "Curation job started"


# --- Request Models ---

class DismissAssociationRequest(BaseModel):
    """Request to dismiss an association."""
    association_id: str


class ConfirmAssociationRequest(BaseModel):
    """Request to confirm an association."""
    association_id: str


class SnoozeAssociationRequest(BaseModel):
    """Request to snooze an association."""
    association_id: str
    snooze_until: datetime


# --- LLM Response Models (for parsing LLM output) ---

class LLMCuratedEvent(BaseModel):
    """LLM output format for a curated event."""
    merged_from: List[str] = Field(..., description="List of original event IDs")
    title: str
    event_type: str
    start_time: str
    end_time: Optional[str] = None
    city: Optional[str] = Field(None, description="City-level location for trip grouping")
    location: Optional[str] = None
    timeline_items: List[TimelineItem] = Field(default_factory=list)
    dedup_reason: str
    confidence: float = 0.8
    trip_source_id: Optional[str] = None
    secretary_notes: Optional[str] = Field(None, description="Secretary-style contextual note")


class LLMDeduplicationResponse(BaseModel):
    """LLM output format for deduplication."""
    curated_events: List[LLMCuratedEvent]
    unconfirmed_items: List[UnconfirmedItem] = Field(default_factory=list)


class LLMAssociation(BaseModel):
    """LLM output format for an association."""
    source_event_id: str = Field(..., description="ID of the event this association relates to")
    target_id: str
    target_type: str
    association_type: str
    title: str
    reason: str
    priority: str = "convenient"
    confidence: float = 0.8


class LLMAssociationResponse(BaseModel):
    """LLM output format for associations."""
    associations: List[LLMAssociation]
