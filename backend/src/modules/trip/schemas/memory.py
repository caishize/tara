"""
Pydantic schemas for TripMemory entity.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class TripMemoryBase(BaseModel):
    """Base schema for TripMemory."""
    content_type: str = Field(..., max_length=50)
    content_urls: List[str] = Field(default_factory=list)
    caption: Optional[str] = None
    ai_caption: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    latitude: Optional[str] = Field(None, max_length=50)
    longitude: Optional[str] = Field(None, max_length=50)
    memory_date: Optional[datetime] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    itinerary_item_id: Optional[UUID] = None
    tags: List[str] = Field(default_factory=list)


class TripMemoryCreate(TripMemoryBase):
    """Schema for creating a new TripMemory."""
    trip_id: UUID


class TripMemoryUpdate(BaseModel):
    """Schema for updating an existing TripMemory."""
    content_type: Optional[str] = Field(None, max_length=50)
    content_urls: Optional[List[str]] = None
    caption: Optional[str] = None
    ai_caption: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    latitude: Optional[str] = Field(None, max_length=50)
    longitude: Optional[str] = Field(None, max_length=50)
    memory_date: Optional[datetime] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    itinerary_item_id: Optional[UUID] = None
    tags: Optional[List[str]] = None


class TripMemoryResponse(TripMemoryBase):
    """Schema for TripMemory response."""
    memory_id: UUID
    trip_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TripMemoryListResponse(BaseModel):
    """Schema for paginated list of TripMemories."""
    items: List[TripMemoryResponse]
    total: int
    page: int
    page_size: int


class MemoryAlbumResponse(BaseModel):
    """Schema for memory album (trip highlights)."""
    trip_id: UUID
    trip_name: Optional[str]
    destination: str
    start_date: str
    end_date: str
    memories_by_day: dict  # {day_number: [TripMemoryResponse]}
    total_photos: int
    total_videos: int
    total_notes: int
    average_rating: Optional[float]
