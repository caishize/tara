"""
EventGraph schemas for the graph module.

Defines request/response models for event graph API endpoints.
Extracted from secretary/schemas/event_graph.py.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class TripSummary(BaseModel):
    """Trip summary (for switching between trips)."""
    id: str
    title: str
    start_date: date
    end_date: date
    location: Optional[str] = None
    priority: str = Field(default="normal")
    status: str = Field(default="upcoming")
    event_count: int = Field(default=0)
    is_current: bool = Field(default=False, description="Whether trip is in progress")
    trip_ids: List[str] = Field(default_factory=list, description="All related trip_ids in this group")

    class Config:
        from_attributes = True


class GraphNode(BaseModel):
    """Graph node."""
    id: str
    type: str = Field(description="trip, category, person, favor, reminder, task, location, history")
    label: str
    icon: Optional[str] = None
    status: Optional[str] = None
    data: Optional[dict] = None
    layer: Optional[str] = Field(
        default=None,
        description="core_trips, must_do, convenient, background"
    )
    urgency: Optional[str] = Field(
        default=None,
        description="blocking, recommended, reference - DEPRECATED, use layer instead"
    )
    action_required: bool = Field(default=False, description="Whether user action is needed")
    available_actions: List[str] = Field(
        default_factory=list,
        description="Contextual actions the user can take on this node"
    )

    class Config:
        from_attributes = True


class GraphEdge(BaseModel):
    """Graph edge."""
    source: str
    target: str
    type: str = Field(description="has_category, contains, related")

    class Config:
        from_attributes = True


class EventGraphResponse(BaseModel):
    """Event graph response."""
    trip: Optional[TripSummary] = None
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    events: List[dict] = Field(default_factory=list, description="All events under the trip")

    class Config:
        from_attributes = True


class AssociationDetail(BaseModel):
    """Association detail."""
    id: str
    title: str
    reason: str
    target_type: str
    target_id: str
    association_type: str
    priority: str
    confidence: float
    is_confirmed: bool = False
    is_dismissed: bool = False
    source_event_title: Optional[str] = None

    class Config:
        from_attributes = True


class CreateAssociationRequest(BaseModel):
    """Create association request."""
    event_id: str = Field(description="Source event UUID")
    target_type: str = Field(description="person, memory, place, task, date, gift")
    target_id: str
    association_type: str = Field(description="location, temporal, person, semantic, memory, task")
    title: str
    reason: str
    priority: str = Field(default="convenient", description="strongly_recommend, convenient, optional")


class AssociationActionRequest(BaseModel):
    """Association action request (confirm/dismiss)."""
    action: str = Field(description="confirm or dismiss")
