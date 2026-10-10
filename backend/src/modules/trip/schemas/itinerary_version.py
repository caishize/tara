"""
Pydantic schemas for ItineraryVersion entity.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class VersionGenerationConfig(BaseModel):
    """Schema for version generation config."""
    styles: List[str] = Field(default_factory=list)
    family_composition: Optional[dict] = None
    preferences: Optional[dict] = None


class ItineraryVersionBase(BaseModel):
    """Base schema for ItineraryVersion."""
    version_name: Optional[str] = Field(None, max_length=200)
    style_tags: List[str] = Field(default_factory=list)


class ItineraryVersionCreate(ItineraryVersionBase):
    """Schema for creating a new ItineraryVersion."""
    trip_id: UUID
    schedules: List[dict] = Field(default_factory=list)
    generation_config: Optional[dict] = None
    total_estimated_cost: Optional[Decimal] = None


class ItineraryVersionUpdate(BaseModel):
    """Schema for updating an existing ItineraryVersion."""
    version_name: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None


class ItineraryVersionResponse(BaseModel):
    """Schema for ItineraryVersion response."""
    version_id: UUID
    trip_id: UUID
    version_number: int
    version_name: Optional[str] = None
    style_tags: List[str] = Field(default_factory=list)
    is_active: bool
    total_estimated_cost: Optional[Decimal] = None
    schedules: List[dict] = Field(default_factory=list)
    generation_config: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Computed fields
    total_days: Optional[int] = None
    total_activities: Optional[int] = None

    class Config:
        from_attributes = True


class ItineraryVersionSummaryResponse(BaseModel):
    """Schema for ItineraryVersion summary (for list display)."""
    version_id: UUID
    version_number: int
    version_name: Optional[str] = None
    style_tags: List[str] = Field(default_factory=list)
    is_active: bool
    total_estimated_cost: Optional[Decimal] = None
    total_days: int = 0
    total_activities: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ItineraryVersionListResponse(BaseModel):
    """Schema for list of ItineraryVersions."""
    items: List[ItineraryVersionSummaryResponse]
    total: int
    active_version_id: Optional[UUID] = None


class ActivateVersionRequest(BaseModel):
    """Schema for activating a version."""
    version_id: UUID
