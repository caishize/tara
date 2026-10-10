"""
Pydantic schemas for Trip Detail Context endpoint.

Provides resolved participant info, weather alerts, and preparation items
so the mobile client never needs to hardcode or display raw UUIDs.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID


class ParticipantInfo(BaseModel):
    """Resolved participant with name, location, and action context."""
    id: UUID
    name: str
    nickname: Optional[str] = None
    relation: Optional[str] = None
    age: Optional[int] = None
    is_child: bool = False
    context_label: Optional[str] = Field(
        None, description="e.g. '住虹桥 · 约晚餐'"
    )
    action_tags: List[str] = Field(
        default_factory=list, description="e.g. ['约晚餐', '喜欢普洱茶']"
    )


class WeatherAlert(BaseModel):
    """Real weather data for the trip destination."""
    destination: str
    condition: str
    temperature: int
    high_temp: Optional[int] = None
    low_temp: Optional[int] = None
    alert_message: Optional[str] = Field(
        None, description="e.g. '上海这两天有雨，记得带伞'"
    )
    advice: Optional[str] = Field(
        None, description="e.g. '最低温 5°C，带件薄外套就行'"
    )


class TripPreparationItem(BaseModel):
    """A preparation checklist item from the curated event."""
    key: str
    text: str
    done: bool = False
    source: str = "manual"
    action_label: Optional[str] = Field(
        None, description="CTA label, e.g. '去看看'. Only for undone items."
    )


class SideActivityItem(BaseModel):
    """A 'thing you can do along the way' from event graph associations."""
    id: str
    title: str
    reason: Optional[str] = None
    priority: str = "convenient"
    target_type: str = "task"
    icon: Optional[str] = None


class RecommendationHighlight(BaseModel):
    """A structured highlight from the trip's recommendation context."""
    icon: str = "lightbulb"
    label: str
    detail: str = ""
    category: str = "general"


class TripContextResponse(BaseModel):
    """Aggregated trip context for the detail page."""
    trip_id: UUID
    participants: List[ParticipantInfo] = Field(default_factory=list)
    weather: Optional[WeatherAlert] = None
    preparation_items: List[TripPreparationItem] = Field(default_factory=list)
    curated_event_id: Optional[UUID] = Field(
        None, description="The linked CuratedEvent ID (for prep item toggle)"
    )
    insight_text: Optional[str] = Field(
        None,
        description="AI-composed insight paragraph for the overview card",
    )
    side_activities: List[SideActivityItem] = Field(
        default_factory=list,
        description="Things you can do along the way (event associations)",
    )
    recommendation_highlights: List[RecommendationHighlight] = Field(
        default_factory=list,
        description="Structured highlights from smart itinerary planning",
    )


class AssociationSummary(BaseModel):
    """Summary of an event association."""
    id: str
    title: Optional[str] = None
    reason: Optional[str] = None
    target_type: str = "task"
    priority: Optional[str] = None


class RelatedMemorySummary(BaseModel):
    """Summary of a related memory."""
    id: str
    summary: Optional[str] = None
    memory_type: Optional[str] = None
    created_at: Optional[str] = None


class TripDetailResponse(BaseModel):
    """Aggregated response for the trip detail page.

    Combines trip plan, itineraries, expenses, budget status,
    context, and event associations into a single response.
    """
    # Core trip data
    plan: dict
    itinerary: List[dict] = Field(default_factory=list)
    expenses: List[dict] = Field(default_factory=list)
    expense_total: int = 0

    # Budget
    budget_status: Optional[dict] = None

    # Context (participants, weather, prep items, etc.)
    context: Optional[TripContextResponse] = None

    # Event associations (from linked curated event)
    associations: List[AssociationSummary] = Field(default_factory=list)
    related_memories: List[RelatedMemorySummary] = Field(default_factory=list)
