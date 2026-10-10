"""Gift module Pydantic schemas.

Merged from:
  - gift_orchestration/schemas/task_schemas.py
  - gift_orchestration/schemas/dashboard_schemas.py
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Task Schemas (from gift_orchestration/schemas/task_schemas.py)
# ============================================================================

class GiftTaskCreate(BaseModel):
    """Create gift task request."""
    important_date_id: Optional[UUID] = Field(None, description="Related important date ID")
    member_id: UUID = Field(..., description="Recipient member ID")
    occasion: str = Field(..., description="Gift occasion")
    occasion_date: date = Field(..., description="Occasion date")
    occasion_title: Optional[str] = Field(None, description="Date title")
    budget_min: Optional[int] = Field(None, description="Min budget")
    budget_max: Optional[int] = Field(None, description="Max budget")
    notes: Optional[str] = Field(None, description="Notes")

    class Config:
        json_schema_extra = {
            "example": {
                "member_id": "123e4567-e89b-12d3-a456-426614174001",
                "occasion": "birthday",
                "occasion_date": "2024-05-20",
                "occasion_title": "Wife birthday",
                "budget_min": 200,
                "budget_max": 500,
            }
        }


class GiftTaskUpdate(BaseModel):
    """Update gift task request."""
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    notes: Optional[str] = None
    occasion_date: Optional[date] = None


class GiftTaskResponse(BaseModel):
    """Gift task response."""
    id: UUID
    family_id: UUID
    important_date_id: Optional[UUID] = None
    member_id: UUID
    member_name: Optional[str] = None

    occasion: str
    occasion_date: date
    occasion_title: Optional[str]
    days_until: int

    scheduled_time: datetime
    trigger_source: str
    status: str

    budget_min: Optional[int]
    budget_max: Optional[int]

    recommendation_id: Optional[UUID]
    has_recommendation: bool

    error_message: Optional[str]
    retry_count: int

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GiftTaskListResponse(BaseModel):
    """Gift task list response."""
    items: List[GiftTaskResponse]
    total: int
    page: int
    page_size: int


class GenerateRecommendationRequest(BaseModel):
    """Manual recommendation generation request."""
    budget_min: Optional[int] = Field(None, description="Min budget")
    budget_max: Optional[int] = Field(None, description="Max budget")
    user_preferences: Optional[str] = Field(None, description="User preference description")


class RegenerateRecommendationRequest(BaseModel):
    """Regenerate recommendation request."""
    budget_min: Optional[int] = Field(None, description="New min budget")
    budget_max: Optional[int] = Field(None, description="New max budget")
    additional_preferences: Optional[str] = Field(None, description="Additional preferences")
    exclude_categories: Optional[List[str]] = Field(None, description="Categories to exclude")
    exclude_previous: bool = Field(True, description="Exclude previously recommended gifts")


class GenerateRecommendationResponse(BaseModel):
    """Recommendation generation response."""
    recommendation_id: UUID
    task_id: UUID
    member_name: str
    occasion: str
    options_count: int
    personalization_score: float
    processing_time_ms: int
    dedup_warnings: List[dict]


# ============================================================================
# Dashboard Schemas (from gift_orchestration/schemas/dashboard_schemas.py)
# ============================================================================

class TaskSummary(BaseModel):
    """Task summary."""
    id: UUID
    member_id: UUID
    member_name: str
    occasion: str
    occasion_title: Optional[str]
    occasion_date: date
    days_until: int
    status: str
    has_recommendation: bool
    recommendation_id: Optional[UUID]
    scheduled_time: Optional[datetime]
    urgency: str  # low, medium, high, critical, overdue


class RecommendationSummary(BaseModel):
    """Recommendation summary."""
    id: UUID
    member_id: UUID
    member_name: str
    occasion: str
    occasion_date: Optional[date]
    status: str
    options_count: int
    recommendations: List[Dict[str, Any]]
    dedup_warnings: Optional[List[Dict[str, Any]]]
    created_at: datetime
    expires_at: Optional[datetime]
    expires_in_days: Optional[int]
    budget_min: Optional[float]
    budget_max: Optional[float]


class HistorySummary(BaseModel):
    """History summary."""
    id: UUID
    member_id: UUID
    member_name: str
    gift_name: str
    gift_category: str
    occasion: str
    occasion_date: date
    feedback_rating: Optional[str]
    feedback_text: Optional[str]
    has_feedback: bool
    image_url: Optional[str]
    created_at: datetime


class MemberInfo(BaseModel):
    """Member info."""
    id: UUID
    name: str
    gift_count: int


class StatsResponse(BaseModel):
    """Stats response."""
    total_gifts_this_year: int
    total_spent: float
    most_gifted_member: Optional[MemberInfo]
    favorite_category: Optional[str]
    pending_tasks: int
    completed_tasks: int
    adoption_rate: float
    year: int


class DashboardResponse(BaseModel):
    """Dashboard full response."""
    upcoming_tasks: List[TaskSummary]
    pending_recommendations: List[RecommendationSummary]
    recent_history: List[HistorySummary]
    stats: StatsResponse
    generated_at: datetime


class YearlyStats(BaseModel):
    """Yearly stats."""
    year: int
    count: int


class CategoryStats(BaseModel):
    """Category stats."""
    category: str
    count: int


class OccasionStats(BaseModel):
    """Occasion stats."""
    occasion: str
    count: int


class RecentGift(BaseModel):
    """Recent gift."""
    gift_name: str
    category: str
    occasion: str
    date: date
    feedback: Optional[str]


class UpcomingOccasion(BaseModel):
    """Upcoming occasion."""
    occasion: str
    date: date
    days_until: int


class MemberBasicInfo(BaseModel):
    """Member basic info."""
    id: UUID
    name: str
    gender: Optional[str]
    age: Optional[int]


class MemberGiftSummary(BaseModel):
    """Member gift summary."""
    member: MemberBasicInfo
    total_gifts: int
    yearly_stats: Dict[int, int]
    category_stats: Dict[str, int]
    occasion_stats: Dict[str, int]
    recent_gifts: List[RecentGift]
    pending_tasks: int
    upcoming_occasions: List[UpcomingOccasion]


class PreferenceSummaryResponse(BaseModel):
    """Preference summary response."""
    member_id: UUID
    total_preferences: int
    positive_categories: List[str]
    negative_categories: List[str]
    neutral_categories: List[str]
    high_confidence_count: int
    last_updated: Optional[datetime]


class DedupWarningResponse(BaseModel):
    """Dedup warning response."""
    level: str  # info, warning, critical
    category: str
    message: str
    count: int
    last_date: Optional[date]
    similar_items: List[str]


class DedupAnalysisResponse(BaseModel):
    """Dedup analysis response."""
    category_stats: Dict[str, Any]
    excluded_categories: List[str]
    warnings: List[DedupWarningResponse]
    total_history_count: int
    time_weighted_stats: Dict[str, float]
