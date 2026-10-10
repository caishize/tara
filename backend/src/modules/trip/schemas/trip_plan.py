"""
Pydantic schemas for TripPlan entity.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


class TripPlanBase(BaseModel):
    """Base schema for TripPlan."""
    trip_name: Optional[str] = Field(None, max_length=200)
    destination: str = Field(..., max_length=500)
    start_date: date
    end_date: date
    category: str = Field("personal", pattern="^(personal|business)$")
    trip_type: Optional[str] = Field("leisure", max_length=50)
    budget: Optional[Decimal] = Field(None, ge=0)
    participants: List[UUID] = Field(default_factory=list)
    priority: str = Field("normal", pattern="^(low|normal|high|critical)$")
    notes: Optional[str] = None
    description: Optional[str] = None
    recommendation_context: Optional[dict] = None
    extra_data: Optional[dict] = None

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v, info):
        if "start_date" in info.data and v < info.data["start_date"]:
            raise ValueError("end_date must be >= start_date")
        return v


class TripPlanCreate(TripPlanBase):
    """Schema for creating a new TripPlan."""
    # Allow backend to inject from auth context when omitted
    family_id: Optional[UUID] = None
    created_by: Optional[UUID] = None

    # Optional itinerary data for assistant-confirmed plans
    itinerary: Optional[Any] = None
    people_to_meet: Optional[List[Any]] = None
    tasks: Optional[List[Any]] = None
    duration_days: Optional[int] = None
    style: Optional[str] = None


class TripPlanUpdate(BaseModel):
    """Schema for updating an existing TripPlan."""
    trip_name: Optional[str] = Field(None, max_length=200)
    destination: Optional[str] = Field(None, max_length=500)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category: Optional[str] = Field(None, pattern="^(personal|business)$")
    trip_type: Optional[str] = Field(None, max_length=50)
    budget: Optional[Decimal] = Field(None, ge=0)
    participants: Optional[List[UUID]] = None
    status: Optional[str] = Field(None, max_length=50)
    priority: Optional[str] = Field(None, pattern="^(low|normal|high|critical)$")
    notes: Optional[str] = None
    description: Optional[str] = None
    recommendation_context: Optional[dict] = None
    extra_data: Optional[dict] = None


class TripPlanResponse(TripPlanBase):
    """Schema for TripPlan response."""
    trip_id: UUID
    family_id: UUID
    created_by: UUID
    actual_expense: Decimal
    status: str
    priority: str
    description: Optional[str] = None
    extra_data: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    # Override date → datetime for UTC ISO 8601 API transmission (CLAUDE.md §时区处理规范)
    start_date: datetime  # type: ignore[assignment]
    end_date: datetime  # type: ignore[assignment]

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _date_to_utc_datetime(cls, v):
        """Convert DB Date to UTC datetime for API transmission.

        DB stores dates as UTC (CLAUDE.md §时区处理规范).
        date(2026-03-01) → 2026-03-01T00:00:00Z (midnight UTC).
        Mobile then converts to local timezone for display.
        """
        if isinstance(v, date) and not isinstance(v, datetime):
            from datetime import timezone as tz
            return datetime(v.year, v.month, v.day, tzinfo=tz.utc)
        return v

    # Computed fields
    duration_days: Optional[int] = None
    budget_used_percentage: Optional[float] = None
    remaining_budget: Optional[Decimal] = None

    class Config:
        from_attributes = True


class TripPlanListResponse(BaseModel):
    """Schema for paginated list of TripPlans."""
    items: List[TripPlanResponse]
    total: int
    page: int
    page_size: int
