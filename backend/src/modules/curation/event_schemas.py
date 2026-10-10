"""
Event CRUD schemas for Secretary API.

Request/response models for user-created event management endpoints.
"""
from typing import List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

VALID_PRIORITIES = Literal["low", "normal", "high", "critical"]
VALID_STATUSES = Literal["pending", "confirmed", "completed", "cancelled"]


class CreateEventRequest(BaseModel):
    """Request to create a user event."""
    title: str = Field(..., min_length=1, max_length=500, description="Event title")
    start_time: datetime = Field(..., description="Event start time (ISO 8601 UTC)")
    end_time: Optional[datetime] = Field(None, description="Event end time (ISO 8601 UTC)")
    event_type: Optional[str] = Field(None, description="Event type: meeting, appointment, reminder, etc.")
    location: Optional[str] = Field(None, max_length=200, description="Event location")
    priority: VALID_PRIORITIES = Field("normal", description="Priority: low, normal, high, critical")
    notes: Optional[str] = Field(None, description="Additional notes")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    trip_id: Optional[str] = Field(None, description="Associated trip ID")

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_time is not None and self.end_time < self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class UpdateEventRequest(BaseModel):
    """Request to update a user event. All fields optional."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    event_type: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    priority: Optional[VALID_PRIORITIES] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[VALID_STATUSES] = Field(None, description="pending, confirmed, completed, cancelled")

    @model_validator(mode="after")
    def end_after_start(self):
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise ValueError("end_time must be after start_time")
        return self


class EventResponse(BaseModel):
    """Response for a single event."""
    id: str
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    event_type: Optional[str] = None
    location: Optional[str] = None
    status: str = "pending"
    priority: str = "normal"
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    source_types: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    trip_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Response for event list with pagination."""
    events: List[EventResponse]
    total: int = 0
    limit: int = 100
    offset: int = 0
    has_more: bool = False
