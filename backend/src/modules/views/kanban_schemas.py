"""Kanban module Pydantic response models.

Extracted from secretary/services/event_context_service.py.
Includes today_schemas (TodayViewResponse, etc.) from assistant/schemas/.
"""
from datetime import date, datetime
from typing import Dict, Any, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Today View schemas (from assistant/schemas/today_schemas.py)
# ---------------------------------------------------------------------------

class ActionResponse(BaseModel):
    """快捷操作"""
    type: str = Field(..., description="操作类型")
    label: str = Field(..., description="显示文本")
    url: Optional[str] = Field(None, description="跳转链接")
    data: Optional[Dict[str, Any]] = Field(None, description="操作数据")


class TodayItemResponse(BaseModel):
    """今日待办项"""
    id: UUID
    source_type: str
    source_id: UUID
    title: str
    description: Optional[str] = None
    urgency: str
    due_datetime: Optional[datetime] = None
    due_time_display: Optional[str] = None
    actions: List[ActionResponse] = []
    status: str = "pending"

    class Config:
        from_attributes = True


class AISuggestionResponse(BaseModel):
    """AI建议"""
    id: UUID
    suggestion_type: str
    content: str
    actions: List[ActionResponse] = []
    priority: int = 0

    class Config:
        from_attributes = True


class TodaySummary(BaseModel):
    """今日汇总统计"""
    total_items: int = 0
    urgent_count: int = 0
    important_count: int = 0
    normal_count: int = 0
    source_breakdown: Dict[str, int] = {}


class TodayViewResponse(BaseModel):
    """今日视图响应"""
    date: str
    weekday: Optional[str] = None
    lunar_date: Optional[str] = None
    summary: Optional[TodaySummary] = None
    urgent_items: List[TodayItemResponse] = []
    important_items: List[TodayItemResponse] = []
    normal_items: List[TodayItemResponse] = []
    suggestions: List[AISuggestionResponse] = []
    greeting: Optional[str] = None


class CompleteItemRequest(BaseModel):
    """完成待办请求"""
    note: Optional[str] = Field(None, max_length=500, description="完成备注")


class SnoozeItemRequest(BaseModel):
    """延后提醒请求"""
    snooze_minutes: int = Field(60, ge=5, le=1440, description="延后分钟数")
    reason: Optional[str] = Field(None, max_length=200, description="延后原因")


class PreparationItem(BaseModel):
    key: str = Field(default_factory=lambda: str(uuid4()))
    item: str
    source: str = "manual"
    done: bool = False


class KanbanEvent(BaseModel):
    id: str
    title: str
    event_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    status: str = "pending"
    priority: str = "normal"
    notes: Optional[str] = None
    trip_id: Optional[str] = None
    trip_name: Optional[str] = None
    preparation_items: List[PreparationItem] = Field(default_factory=list)
    tags: Optional[List[str]] = None
    visibility_tier: str = Field(
        default="standard",
        description="focus, standard, detail — controls visual prominence",
    )


class KanbanInsight(BaseModel):
    id: str
    title: str
    content: str
    insight_type: str
    priority: int = 5
    urgency: str = "normal"
    action_type: Optional[str] = None
    action_data: Optional[dict] = None
    action_options: List[Dict[str, Any]] = Field(default_factory=list)
    context_hint: Optional[str] = None
    created_at: Optional[datetime] = None


class KanbanResponse(BaseModel):
    this_week: List[KanbanEvent] = Field(default_factory=list)
    needs_preparation: List[KanbanEvent] = Field(default_factory=list)
    monthly: List[KanbanEvent] = Field(default_factory=list)
    later: List[KanbanEvent] = Field(default_factory=list)
    insights: List[KanbanInsight] = Field(default_factory=list)


class StoryGroup(BaseModel):
    trip_id: Optional[str] = None
    title: str
    events: List[KanbanEvent] = Field(default_factory=list)
    memory_summaries: List[str] = Field(default_factory=list)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    emotional_summary: Optional[str] = Field(
        default=None,
        description="Memory-derived emotional summary for this story group",
    )
    emotional_tag: Optional[str] = Field(
        default=None,
        description="Warm tag like '温馨旅途', '家庭时光', '成长记录'",
    )


class YearGroup(BaseModel):
    year: int
    stories: List[StoryGroup] = Field(default_factory=list)
    event_count: int = 0


class MemoryLaneResponse(BaseModel):
    years: List[YearGroup] = Field(default_factory=list)
    total_events: int = 0


class OnThisDayEvent(BaseModel):
    id: str
    title: str
    event_type: Optional[str] = None
    participants: List[str] = Field(default_factory=list)
    memory_fragments: List[str] = Field(default_factory=list)


class OnThisDayItem(BaseModel):
    year: int
    years_ago: int
    events: List[OnThisDayEvent] = Field(default_factory=list)
    narrative: str = Field(
        default="",
        description="Warm narrative framing text, e.g. '3年前的今天'",
    )


class OnThisDayResponse(BaseModel):
    items: List[OnThisDayItem] = Field(default_factory=list)
    month: int
    day: int


class EventSearchResult(BaseModel):
    id: str
    title: str
    event_type: Optional[str] = None
    start_time: Optional[datetime] = None
    location: Optional[str] = None
    status: str = "pending"
    trip_name: Optional[str] = None


class EventSearchResponse(BaseModel):
    results: List[EventSearchResult] = Field(default_factory=list)
    total: int = 0
    query: str = ""


class RelatedMemory(BaseModel):
    id: str
    memory_type: str
    summary: str
    content: Optional[str] = None
    created_at: Optional[datetime] = None


class AssociationSummary(BaseModel):
    id: str
    title: str
    association_type: str
    target_type: str
    reason: str
    priority: str = "convenient"
    is_confirmed: bool = False
    is_dismissed: bool = False


class EventDetailResponse(BaseModel):
    event: KanbanEvent
    associations: List[AssociationSummary] = Field(default_factory=list)
    related_memories: List[RelatedMemory] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Timeline schemas (merged from secretary/schemas/timeline.py)
# ---------------------------------------------------------------------------

class TimelineEventItem(BaseModel):
    """Timeline event item."""
    id: str
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    event_type: str = Field(description="meeting, social, trip, reminder, task, favor, other")
    status: str = Field(description="pending, confirmed, completed, cancelled")
    priority: str = Field(default="normal", description="low, normal, high, critical")
    location: Optional[str] = None
    notes: Optional[str] = None
    trip_id: Optional[str] = None
    trip_label: Optional[str] = None
    has_conflict: bool = Field(default=False)
    conflict_with: Optional[List[str]] = Field(default=None)
    sequence_of_day: Optional[int] = Field(default=None)
    visibility_tier: str = Field(
        default="standard",
        description="focus, standard, detail — controls visual prominence",
    )
    life_context_hint: Optional[str] = Field(
        default=None,
        description="Warm contextual hint, e.g. '和家人一起' or '记得带证件'",
    )

    class Config:
        from_attributes = True


class TimelineInsightItem(BaseModel):
    """A lightweight insight card embedded in a timeline day group (PLAN-014).

    Only date-anchored insights (those whose action_data contains an anchor
    date matching the day) are shown here.  Optional/nullable for backward
    compatibility — old mobile clients that ignore unknown fields will simply
    skip this field.
    """
    id: str
    insight_type: str
    title: str
    content: str
    urgency: str = Field(default="normal")
    # PLAN-013 ActionSpec dicts; each has keys: label, action_type, action_payload.
    # The legacy ``label`` field in each dict ensures NR-7 compat.
    action_options: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        from_attributes = True


class TimelineAlertItem(BaseModel):
    """A non-dismissable alert card in a timeline day group (PLAN-010).

    Distinct from insight items: alert cards represent schedule conflict
    warnings (GapWarnings) and expose no feedback/adopt actions.
    """
    alert_type: str = Field(description="gap_no_buffer, gap_meal_conflict, etc.")
    severity: str = Field(default="suggestion")
    title: str
    description: str = ""
    related_event_ids: List[str] = Field(default_factory=list)
    icon: str = Field(default="\U0001f4a1")

    class Config:
        from_attributes = True


class TimelineDayGroup(BaseModel):
    """Timeline day group."""
    date: date
    date_label: str
    events: List[TimelineEventItem]
    summary: str
    week_label: Optional[str] = None
    day_mood: Optional[str] = Field(
        default=None,
        description="Day character tag: 家庭日, 休闲周末, 纪念日, 出行日, 忙碌日, etc.",
    )
    highlight_event_id: Optional[str] = Field(
        default=None,
        description="ID of the most important event to emphasize",
    )
    # PLAN-014: date-anchored insight cards for this day.  Optional/nullable
    # for mobile client backward compatibility (new field, old clients ignore).
    insights: List[TimelineInsightItem] = Field(default_factory=list)
    # PLAN-010: schedule conflict alerts (GapWarnings) for cross-view parity.
    alerts: List[TimelineAlertItem] = Field(default_factory=list)


class TimelineResponse(BaseModel):
    """Timeline response."""
    direction: Literal["past", "future"]
    day_groups: List[TimelineDayGroup]
    next_cursor: Optional[str] = None
    has_more: bool = Field(default=False)


class TimelineQueryParams(BaseModel):
    """Timeline query parameters."""
    direction: Literal["past", "future"] = Field(default="future")
    days: int = Field(default=14, ge=1, le=30)
    cursor: Optional[str] = None
    family_id: Optional[str] = None


class UpdateEventStatusRequest(BaseModel):
    """Update event status request."""
    status: str = Field(description="pending, confirmed, completed, cancelled")
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Insight Feed schemas (insight-centric feed API)
# ---------------------------------------------------------------------------

class InsightRelatedEvent(BaseModel):
    """Lightweight event summary embedded in insight feed items."""
    id: str
    title: str
    event_type: Optional[str] = None
    start_time: Optional[datetime] = None
    location: Optional[str] = None
    status: str = "active"


class InsightRelatedMember(BaseModel):
    """Lightweight member summary embedded in insight feed items."""
    id: str
    name: str
    relationship: Optional[str] = None
    avatar_url: Optional[str] = None


class InsightRelatedTrip(BaseModel):
    """Lightweight trip summary embedded in insight feed items."""
    id: str
    name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None


class InsightFeedItem(BaseModel):
    """Primary content unit in the insight-centric feed."""
    id: str
    title: str
    content: str
    insight_type: str
    priority: int = 5
    urgency: str = "normal"
    action_type: Optional[str] = None
    action_data: Optional[dict] = None
    action_options: List[Dict[str, Any]] = Field(default_factory=list)
    context_hint: Optional[str] = None
    created_at: Optional[datetime] = None
    # Resolved entity relationships
    related_events: List[InsightRelatedEvent] = Field(default_factory=list)
    related_members: List[InsightRelatedMember] = Field(default_factory=list)
    related_trip: Optional[InsightRelatedTrip] = None
    source_context: Optional[str] = None


class InsightFeedResponse(BaseModel):
    """Response for the insight-centric feed endpoint."""
    insights: List[InsightFeedItem] = Field(default_factory=list)
    standalone_events: List[KanbanEvent] = Field(default_factory=list)
    later_events: List[KanbanEvent] = Field(default_factory=list)
    needs_preparation: List[KanbanEvent] = Field(default_factory=list)


class InsightGroup(BaseModel):
    """A semantically grouped cluster of insights."""
    group_id: str = Field(description="Stable group identifier")
    title: str = Field(description="Localized display title")
    subtitle: Optional[str] = Field(default=None, description="Optional summary line")
    insights: List[InsightFeedItem] = Field(default_factory=list)
    preparation_events: List[KanbanEvent] = Field(
        default_factory=list,
        description="Preparation events relevant to this group",
    )
    standalone_events: List[KanbanEvent] = Field(
        default_factory=list,
        description="Events in this group not referenced by any insight",
    )
    # PLAN-004: Server-driven display hints for client group presentation
    expanded_by_default: bool = Field(
        default=True,
        description="Whether client should expand this group on first load",
    )
    icon: Optional[str] = Field(
        default=None,
        description="Icon identifier (e.g. 'flash_on', 'favorite_outline')",
    )
    accent_color: Optional[str] = Field(
        default=None,
        description="Hex accent color (e.g. '#2D7A46')",
    )


class InsightFeedGroupedResponse(BaseModel):
    """Grouped response for the insight-centric feed endpoint."""
    groups: List[InsightGroup] = Field(default_factory=list)
    later_events: List[KanbanEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Future View schemas (V4 timeline redesign)
# ---------------------------------------------------------------------------

class FutureViewTripTask(BaseModel):
    """A task/preparation item within a trip card."""
    id: str
    title: str
    subtitle: str = ""
    done: bool = False
    action_label: str = ""
    action_type: str = ""
    is_primary_action: bool = False
    member_color: Optional[str] = None


class FutureViewTripParticipant(BaseModel):
    """A participant shown in a trip card."""
    id: str
    name: str
    color: str = "#3D8A5A"


class FutureViewTripInsight(BaseModel):
    """An insight card attached to a trip."""
    id: str
    insight_type: str = ""
    title: str
    content: str = ""
    importance: int = 50
    urgency: str = "normal"
    status: str = "pending"
    suggested_action: Optional[str] = None
    action_options: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    entities: List[Dict[str, Any]] = Field(default_factory=list)


class FutureViewTrip(BaseModel):
    """A trip card in the future view."""
    id: str
    name: str
    emoji: str = "✈️"
    category: str = Field(default="personal", description="business or personal")
    start_date: date
    end_date: date
    days_until: int = 0
    done_count: int = 0
    total_count: int = 0
    participants: List[FutureViewTripParticipant] = Field(default_factory=list)
    tasks: List[FutureViewTripTask] = Field(default_factory=list)
    insights: List[FutureViewTripInsight] = Field(default_factory=list)


class FutureViewSuggestionSubItem(BaseModel):
    """A sub-item within a suggestion card (e.g. a pending action)."""
    id: str
    label: str
    description: str = ""
    action_type: str = ""
    is_pending_action: bool = False


class FutureViewSuggestion(BaseModel):
    """An expandable AI suggestion card with optional sub-items."""
    id: str
    insight_id: str = ""
    title: str
    description: str = ""
    tag_emoji: str = "💡"
    tag_label: str = "建议"
    tag_color: str = "#3D8A5A"
    action_label: str = ""
    action_type: str = ""
    action_data: Optional[Dict[str, Any]] = None
    action_options: List[Dict[str, Any]] = Field(default_factory=list)
    related_trip_id: Optional[str] = None
    sub_items: List[FutureViewSuggestionSubItem] = Field(default_factory=list)
    group_key: str = ""
    group_label: str = ""


class FutureViewUpcoming(BaseModel):
    """An upcoming important date/event."""
    id: str
    title: str
    emoji: str = "📅"
    date_label: str = ""
    context_hint: str = ""
    days_until: int = 0
    dot_color: str = "#E65100"
    date_type: str = ""


class FutureViewMember(BaseModel):
    """A family member in the family pulse section."""
    id: str
    name: str
    relationship: str = ""
    status_line: str = ""
    avatar_color: str = "#3D8A5A"
    avatar_initial: str = ""


class FutureViewResponse(BaseModel):
    """Response for the V4 future timeline view."""
    trips: List[FutureViewTrip] = Field(default_factory=list)
    suggestions: List[FutureViewSuggestion] = Field(default_factory=list)
    upcoming: List[FutureViewUpcoming] = Field(default_factory=list)
    upcoming_has_more: bool = False
    family_members: List[FutureViewMember] = Field(default_factory=list)


class FutureViewUpcomingPage(BaseModel):
    """Paginated upcoming items."""
    items: List[FutureViewUpcoming] = Field(default_factory=list)
    has_more: bool = False
    total: int = 0
