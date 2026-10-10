"""
Pydantic schemas for TripItinerary entity.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from datetime import datetime
from enum import Enum


class ItineraryStyleEnum(str, Enum):
    """行程风格枚举"""
    INTENSIVE = "intensive"      # 紧凑型：景点密集，充分利用时间
    RELAXED = "relaxed"          # 轻松型：慢节奏，充足休息
    BUDGET = "budget"            # 经济型：控制花费，高性价比
    LUXURY = "luxury"            # 豪华型：高端体验，五星服务
    ADVENTURE = "adventure"      # 探险型：户外活动，自然风光
    CULTURAL = "cultural"        # 文化型：博物馆、历史遗迹


class ItineraryItemSchema(BaseModel):
    """Schema for a single itinerary item within a day."""
    time: str = Field(default="00:00", description="Time in HH:MM format")
    period: Optional[str] = Field(
        None,
        description="Time period label: 上午 / 下午 / 晚上. "
                    "Computed from time if not provided.",
    )
    activity_type: str = Field(default="other", description="transportation|accommodation|attraction|meal|other")
    title: str = Field(default="活动", max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    estimated_cost: Optional[float] = Field(None, ge=0)
    booking_info: Optional[dict] = None
    notes: Optional[str] = None
    # Extra fields from smart itinerary - allow them to pass through
    duration_minutes: Optional[int] = None
    professional_advice: Optional[dict] = None
    alternatives: Optional[list] = None

    model_config = {"extra": "allow"}  # Allow extra fields not defined in schema


class TripItineraryBase(BaseModel):
    """Base schema for TripItinerary."""
    day_number: int = Field(..., gt=0)
    schedule: List[ItineraryItemSchema] = Field(default_factory=list)
    packing_notes: Optional[Union[dict, str]] = None  # Support both dict and legacy string format

    @field_validator('packing_notes', mode='before')
    @classmethod
    def convert_packing_notes(cls, v):
        """Convert string packing_notes to dict if needed."""
        if isinstance(v, str):
            return {"notes": v}
        return v


class TripItineraryCreate(TripItineraryBase):
    """Schema for creating a new TripItinerary."""
    trip_id: UUID


class TripItineraryUpdate(BaseModel):
    """Schema for updating an existing TripItinerary."""
    schedule: Optional[List[ItineraryItemSchema]] = None
    packing_notes: Optional[dict] = None


class TripItineraryResponse(TripItineraryBase):
    """Schema for TripItinerary response."""
    itinerary_id: UUID
    trip_id: UUID
    created_at: datetime
    updated_at: datetime

    # Computed fields
    total_estimated_cost: Optional[float] = None
    activity_count: Optional[int] = None

    model_config = {
        "from_attributes": True,
        "extra": "allow",  # Allow extra fields from smart itinerary
    }


class TripItineraryListResponse(BaseModel):
    """Schema for list of itineraries (typically all days for a trip)."""
    items: List[TripItineraryResponse]
    total: int


# ============ Smart Itinerary Schemas ============

class FamilyMemberSchema(BaseModel):
    """家庭成员信息"""
    name: Optional[str] = None
    age: int = Field(..., ge=0, le=120)
    relation: Optional[str] = None  # 关系：child, elderly, adult


class FamilyCompositionSchema(BaseModel):
    """家庭组成信息"""
    children: List[FamilyMemberSchema] = Field(default_factory=list)
    elderly: List[FamilyMemberSchema] = Field(default_factory=list)
    special_needs: List[str] = Field(default_factory=list)


class ItineraryPreferencesSchema(BaseModel):
    """行程偏好设置"""
    enable_nap_time: bool = Field(
        default=True,
        description="是否为儿童/老人安排午休时间 (14:00-16:00)"
    )
    nap_time_start: str = Field(
        default="14:00",
        description="午休开始时间"
    )
    nap_time_end: str = Field(
        default="16:00",
        description="午休结束时间"
    )
    weather_aware: bool = Field(
        default=True,
        description="是否根据天气推荐室内/室外活动"
    )
    include_local_tips: bool = Field(
        default=True,
        description="是否包含当地人推荐"
    )
    include_alternatives: bool = Field(
        default=True,
        description="是否包含备选方案"
    )


class SmartItineraryRequest(BaseModel):
    """智能行程生成请求"""
    styles: List[ItineraryStyleEnum] = Field(
        default=[ItineraryStyleEnum.RELAXED],
        min_length=1,
        max_length=3,
        description="行程风格列表，最多选择3个"
    )
    family_composition: Optional[FamilyCompositionSchema] = None
    preferences: Optional[ItineraryPreferencesSchema] = Field(
        default=None,
        description="行程偏好设置"
    )


class ProfessionalAdviceSchema(BaseModel):
    """专业旅行建议"""
    why_chosen: str = Field(..., description="为什么推荐这个景点/活动")
    best_experience: str = Field(..., description="最佳体验方式")
    time_tips: str = Field(..., description="时间建议")
    cost_tips: str = Field(..., description="省钱技巧")
    warnings: List[str] = Field(default_factory=list, description="避坑提示")


class AlternativeSchema(BaseModel):
    """备选方案"""
    name: str
    reason: str


class EnhancedActivitySchema(BaseModel):
    """增强版活动信息"""
    time: str = Field(..., description="活动时间 HH:MM")
    duration_minutes: int = Field(..., ge=0)
    activity_type: str = Field(..., description="活动类型")
    title: str
    location: str
    description: str
    estimated_cost: float = Field(default=0, ge=0)
    professional_advice: Optional[ProfessionalAdviceSchema] = None
    alternatives: List[AlternativeSchema] = Field(default_factory=list)


class DaySummarySchema(BaseModel):
    """每日行程总结"""
    total_cost: float = Field(default=0, ge=0)
    walking_distance_km: float = Field(default=0, ge=0)
    activity_count: int = Field(default=0, ge=0)
    energy_level: str = Field(default="适中", description="轻松/适中/充实")


class DailyScheduleSchema(BaseModel):
    """每日行程安排"""
    day: int = Field(..., gt=0)
    date_label: str = ""
    theme: str = ""
    summary: str = ""
    activities: List[EnhancedActivitySchema] = Field(default_factory=list)
    day_summary: Optional[DaySummarySchema] = None
    sources: Optional[List[dict]] = None


class BackupPlanSchema(BaseModel):
    """备用计划"""
    scenario: str = Field(..., description="场景，如：下雨天")
    alternative: str = Field(..., description="替代方案")


class TripDesignRationaleSchema(BaseModel):
    """行程设计依据"""
    planning_philosophy: str = Field(..., description="整体规划理念")
    route_logic: str = Field(..., description="路线安排逻辑")
    highlights: List[str] = Field(default_factory=list)
    backup_plans: List[BackupPlanSchema] = Field(default_factory=list)
    local_tips: List[str] = Field(default_factory=list, description="当地人才知道的小贴士")


class BudgetItemSchema(BaseModel):
    """预算项目"""
    amount: float = Field(default=0, ge=0)
    percentage: float = Field(default=0, ge=0, le=100)


class BudgetAllocationSchema(BaseModel):
    """预算分配"""
    transportation: BudgetItemSchema = Field(default_factory=BudgetItemSchema)
    accommodation: BudgetItemSchema = Field(default_factory=BudgetItemSchema)
    food: BudgetItemSchema = Field(default_factory=BudgetItemSchema)
    tickets: BudgetItemSchema = Field(default_factory=BudgetItemSchema)
    other: BudgetItemSchema = Field(default_factory=BudgetItemSchema)
    total: float = Field(default=0, ge=0)


class SmartItineraryResponse(BaseModel):
    """智能行程生成响应"""
    trip_id: str
    destination: str
    duration_days: int
    styles: List[str]
    generated_at: str
    trip_design_rationale: Optional[TripDesignRationaleSchema] = None
    budget_allocation: Optional[BudgetAllocationSchema] = None
    daily_schedules: List[DailyScheduleSchema]
    sources: Optional[List[dict]] = None
    budget_total: Optional[float] = None
    tips: Optional[List[str]] = None


class ItineraryAdjustmentRequest(BaseModel):
    """行程调整请求"""
    adjustment_request: str = Field(..., description="用户的调整请求，如：今天想轻松一点")
    current_day: Optional[int] = Field(None, ge=1, description="当前是第几天")


class AdjustmentSuggestionSchema(BaseModel):
    """调整建议"""
    option: str
    description: str
    changes: List[str]
    impact: str


class ItineraryAdjustmentResponse(BaseModel):
    """行程调整响应"""
    understanding: str = Field(..., description="对用户请求的理解")
    suggestions: List[AdjustmentSuggestionSchema]
    recommended: str = Field(..., description="推荐的方案名称")
    reason: str = Field(..., description="推荐理由")


# ============ Incremental Update Schemas (FR-020) ============

class ActivityUpdateRequest(BaseModel):
    """更新单个活动请求"""
    activity_index: int = Field(..., ge=0, description="活动在当天列表中的索引")
    time: Optional[str] = Field(None, description="新的时间 HH:MM")
    duration_minutes: Optional[int] = Field(None, ge=0)
    title: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    estimated_cost: Optional[float] = Field(None, ge=0)


class ActivityCreateRequest(BaseModel):
    """添加新活动请求"""
    time: str = Field(..., description="活动时间 HH:MM")
    duration_minutes: int = Field(default=60, ge=0)
    activity_type: str = Field(default="other", description="activity类型")
    title: str = Field(..., max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    estimated_cost: Optional[float] = Field(default=0, ge=0)


class ActivityDeleteRequest(BaseModel):
    """删除活动请求"""
    activity_index: int = Field(..., ge=0, description="活动在当天列表中的索引")


class DaySwapRequest(BaseModel):
    """交换两天行程请求"""
    source_day: int = Field(..., ge=1, description="源日期（从1开始）")
    target_day: int = Field(..., ge=1, description="目标日期（从1开始）")


class IncrementalUpdateResponse(BaseModel):
    """增量更新响应"""
    success: bool
    message: str
    updated_day: Optional[int] = None
    updated_schedule: Optional[List[EnhancedActivitySchema]] = None
    new_day_summary: Optional[DaySummarySchema] = None
