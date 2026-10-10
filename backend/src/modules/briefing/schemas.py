"""Briefing module Pydantic schemas (response / request models)."""
from typing import Any, Dict, List, Optional
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

from ...core.utils.timezone import utc_now


class InsightEntityRefItem(BaseModel):
    """Lightweight entity reference for insight items."""
    entity_type: str
    entity_id: str


class InsightItem(BaseModel):
    """Insight item used by briefing and API responses."""
    id: str
    insight_type: str
    title: str
    content: str
    importance_score: int = Field(ge=0, le=100)
    urgency_score: int = Field(ge=0, le=100)
    status: str
    suggested_action: Optional[str] = None
    related_event_id: Optional[str] = None
    related_important_date_id: Optional[str] = None
    related_trip_id: Optional[str] = None
    created_at: datetime
    # PLAN-013: Typed action chips (ActionSpec dicts).  Optional/nullable for
    # backward compatibility with old mobile clients that ignore unknown fields.
    # Each dict has keys: label (str), action_type (str), action_payload (dict).
    # The legacy ``label`` field in each dict preserves NR-7 compat.
    action_options: List[Dict[str, Any]] = Field(default_factory=list)
    entity_refs: List[InsightEntityRefItem] = Field(default_factory=list)

    class Config:
        from_attributes = True


class InsightListResponse(BaseModel):
    """Insight list response."""
    insights: List[InsightItem]
    total: int = 0
    unread_count: int = 0


class InsightFeedbackEnum(str, Enum):
    """User feedback type for insights."""
    USEFUL = "useful"
    IGNORED = "ignored"
    NEVER_AGAIN = "never_again"


class InsightFeedbackRequest(BaseModel):
    """Insight feedback request."""
    feedback: InsightFeedbackEnum


class InsightActionRequest(BaseModel):
    """Insight action request."""
    action: str = Field(description="read, dismiss, action_taken")


class InsightQueryParams(BaseModel):
    """Insight query parameters."""
    unread_only: bool = Field(default=False)
    min_importance: int = Field(default=0, ge=0, le=100)
    insight_type: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=50)


class BriefingEvent(BaseModel):
    """A single event in the daily briefing."""
    id: str
    title: str
    time: Optional[str] = None
    icon: str
    description: Optional[str] = None
    action_label: Optional[str] = None
    event_type: str = "general"
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    trip_id: Optional[str] = None


class BriefingEntityRef(BaseModel):
    """Lightweight entity reference for cross-view navigation."""
    entity_type: str
    entity_id: str


class BriefingInsight(BaseModel):
    """An AI-generated insight in the daily briefing."""
    id: str
    insight_type: str
    title: str
    content: str
    priority: int = 5
    urgency: str = "normal"
    action_options: List[str] = []
    action_data: dict = {}
    entity_refs: List[BriefingEntityRef] = Field(default_factory=list)


class HouseholdStatus(BaseModel):
    """Household status item for daily briefing."""
    id: str
    title: str
    description: str
    icon: str = "house"
    urgency: str = "normal"
    action_label: Optional[str] = None


class UpcomingTrip(BaseModel):
    """Upcoming trip for daily briefing."""
    trip_id: str
    trip_name: Optional[str] = None
    destination: str
    start_date: date
    end_date: date
    trip_type: str = "leisure"
    status: str = "planning"


class BriefingAlert(BaseModel):
    """Secretary-style urgent alert for daily briefing."""
    id: str
    alert_type: str
    severity: str = "warning"
    title: str
    description: str
    related_event_ids: List[str] = []
    action_label: Optional[str] = None
    icon: str = "warning"


class BriefingSuggestion(BaseModel):
    """A structured suggestion chip in the daily briefing."""
    label: str
    action_type: str
    action_data: dict = Field(default_factory=dict)


class BriefingPeriod:
    """Briefing period constants."""
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"

    @staticmethod
    def from_hour(hour: int) -> str:
        if 6 <= hour < 12:
            return BriefingPeriod.MORNING
        elif 12 <= hour < 18:
            return BriefingPeriod.AFTERNOON
        else:
            return BriefingPeriod.EVENING


class TimeSlotSchema(BaseModel):
    """A time slot in the orchestrated day schedule."""
    start: str          # HH:MM format
    end: str            # HH:MM format
    event_id: Optional[str] = None
    slot_type: str = "event"  # event | buffer | travel | free | preparation | recovery
    note: Optional[str] = None


class SecretaryAnnotationSchema(BaseModel):
    """A contextual annotation from the secretary orchestration layer."""
    event_id: str
    text: str
    source: str = "context_enricher"


class DayThemeSchema(BaseModel):
    """Today's attention navigation theme."""
    title: str
    primary_event_id: Optional[str] = None
    focus: str
    prep_note: Optional[str] = None
    evening_forward: Optional[str] = None


class DeferralSuggestionSchema(BaseModel):
    """E5: Suggestion to defer a low-priority event on overloaded days."""
    event_id: str
    event_title: str
    reason: str
    suggested_new_date: Optional[date] = None
    priority_level: str = "P3"


class DailyBriefing(BaseModel):
    """Daily briefing response model."""
    date: date
    greeting: str
    period: str = BriefingPeriod.MORNING
    today_event_count: int
    today_events: List[BriefingEvent]
    preparation_reminders: List[str]
    week_remaining_count: int
    smart_suggestions: List[BriefingSuggestion]
    insights: List[BriefingInsight] = []
    household_status: List[HouseholdStatus] = []
    upcoming_trips: List[UpcomingTrip] = []
    alerts: List[BriefingAlert] = []
    tomorrow_preview: List[BriefingEvent] = []
    # Orchestration layer enrichments
    density_level: str = "STANDARD"
    density_score: float = 0.0
    annotations: List[SecretaryAnnotationSchema] = []
    secretary_summary: Optional[str] = None
    # Day theme (attention navigation)
    day_theme: Optional[DayThemeSchema] = None
    # Suggested event order for FOCUSED mode (event IDs in priority order)
    suggested_reorder: Optional[List[str]] = None
    # Complete day structure with buffers/recovery slots
    time_slots: List[TimeSlotSchema] = []
    # E5: Deferral suggestions for overloaded days
    deferral_suggestions: List[DeferralSuggestionSchema] = []
    # Clean desk deferred content count (UI can show "查看更多 (N)")
    deferred_count: int = 0


# ---------------------------------------------------------------------------
# Insight type enum
# ---------------------------------------------------------------------------

class InsightTypeEnum(str, Enum):
    """Insight type classification."""
    TIME = "time"
    RELATIONSHIP = "relationship"
    FAVOR = "favor"
    EFFICIENCY = "efficiency"
    HEALTH = "health"
    FINANCE = "finance"
    MEMORY = "memory"


# ---------------------------------------------------------------------------
# Suggestion response schemas
# ---------------------------------------------------------------------------

class SuggestionResponse(BaseModel):
    """Response model for a single suggestion."""
    id: str
    type: str
    title: str
    content: str
    icon: str = "lightbulb"
    related_event_ids: List[str] = Field(default_factory=list)
    related_member_ids: List[str] = Field(default_factory=list)
    related_trip_ids: List[str] = Field(default_factory=list)
    action_options: List[str] = Field(default_factory=list)
    action_data: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    urgency: str = "normal"
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SuggestionListResponse(BaseModel):
    """Response model for a list of suggestions."""
    suggestions: List[SuggestionResponse]
    total: int
    generated_at: datetime = Field(default_factory=utc_now)


class SuggestionActionRequest(BaseModel):
    """Request model for executing a suggestion action."""
    suggestion_id: str
    action: str
    params: Optional[Dict[str, Any]] = None


class SuggestionActionResponse(BaseModel):
    """Response model for a suggestion action execution."""
    success: bool
    action: str
    message: str
    next_step: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Work report schemas
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    """Curation job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerType(str, Enum):
    """Types of curation triggers."""
    SCHEDULED = "scheduled"
    EVENT = "event"
    MANUAL = "manual"
    TRIP_CANCELLED = "trip_cancelled"
    TRIP_CREATED = "trip_created"
    TRIP_UPDATED = "trip_updated"


class CurationJobSummaryItem(BaseModel):
    """Summary of a single curation job for the work report list."""
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
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class CuratedEventItem(BaseModel):
    """A curated event within a curation job detail."""
    id: str
    title: str
    event_type: Optional[str] = None
    source_types: List[str] = Field(default_factory=list)
    merged_count: int = 1
    dedup_reason: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "pending"

    class Config:
        from_attributes = True


class AssociationItem(BaseModel):
    """An association within a curation job detail."""
    id: str
    title: str
    association_type: str
    target_type: str
    reason: str
    priority: str = "convenient"
    confidence: float = 0.8

    class Config:
        from_attributes = True


class CurationJobDetailResponse(BaseModel):
    """Detailed view of a single curation job with events and associations."""
    job: CurationJobSummaryItem
    curated_events: List[CuratedEventItem] = Field(default_factory=list)
    associations: List[AssociationItem] = Field(default_factory=list)


class HygieneRunLogItem(BaseModel):
    """Summary of a single hygiene run."""
    id: str
    family_id: str
    inactive_deleted: int = 0
    cancelled_deleted: int = 0
    dismissed_deleted: int = 0
    auto_completed: int = 0
    jobs_purged: int = 0
    total_actions: int = 0
    status: str = "completed"
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkReportSummary(BaseModel):
    """Aggregate summary statistics for the work report."""
    total_curation_runs: int = 0
    successful_curation_runs: int = 0
    failed_curation_runs: int = 0
    total_events_curated: int = 0
    total_associations_created: int = 0
    total_hygiene_runs: int = 0
    total_hygiene_actions: int = 0


class WorkReportResponse(BaseModel):
    """Top-level work report response with summary and recent jobs."""
    summary: WorkReportSummary
    curation_jobs: List[CurationJobSummaryItem] = Field(default_factory=list)
    hygiene_logs: List[HygieneRunLogItem] = Field(default_factory=list)


class HygieneRunLogListResponse(BaseModel):
    """Response for listing hygiene run logs."""
    logs: List[HygieneRunLogItem] = Field(default_factory=list)
    total: int = 0
