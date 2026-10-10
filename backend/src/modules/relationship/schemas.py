"""Pydantic schemas for favor records.

Canonical location. Moved from relationship_management/schemas/favor_schema.py.
"""
from datetime import date
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class FavorBase(BaseModel):
    """Base schema for favor records."""
    contact_name: str = Field(..., min_length=1, max_length=100)
    event_type: str = Field(..., min_length=1, max_length=50)
    amount: Decimal = Field(..., gt=0, le=1000000)
    direction: str = Field(..., pattern="^(give|receive)$")
    gift_type: str = Field(default="cash", pattern="^(cash|gift|service)$")
    recorded_at: date
    note: Optional[str] = None
    is_private: bool = False


class FavorCreate(FavorBase):
    """Schema for creating a favor record."""
    family_id: UUID
    contact_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    status: str = Field(default="pending", pattern="^(pending|returned|settled)$")

    @field_validator('recorded_at')
    @classmethod
    def date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError('记录日期不能是未来')
        return v


class FavorQuickCreate(BaseModel):
    """Schema for quick favor entry (minimal fields)."""
    family_id: UUID
    contact_id: Optional[UUID] = None  # Link to member if available
    contact_name: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0, le=1000000)
    direction: str = Field(..., pattern="^(give|receive)$")
    event_type: str = Field(default="other")
    recorded_at: Optional[date] = None  # Defaults to today

    @field_validator('recorded_at', mode='before')
    @classmethod
    def set_default_date(cls, v):
        return v or date.today()


class FavorUpdate(BaseModel):
    """Schema for updating a favor record."""
    contact_name: Optional[str] = Field(None, min_length=1, max_length=100)
    event_type: Optional[str] = Field(None, min_length=1, max_length=50)
    amount: Optional[Decimal] = Field(None, gt=0, le=1000000)
    direction: Optional[str] = Field(None, pattern="^(give|receive)$")
    gift_type: Optional[str] = Field(None, pattern="^(cash|gift|service)$")
    status: Optional[str] = Field(None, pattern="^(pending|returned|settled)$")
    recorded_at: Optional[date] = None
    note: Optional[str] = None
    is_private: Optional[bool] = None
    contact_id: Optional[UUID] = None
    event_id: Optional[UUID] = None


class FavorResponse(BaseModel):
    """Schema for favor record response."""
    id: UUID
    family_id: UUID
    contact_id: Optional[UUID] = None
    contact_name: str
    event_type: str
    event_id: Optional[UUID] = None
    amount: float
    direction: str
    gift_type: str
    status: str
    recorded_at: date
    note: Optional[str] = None
    is_private: bool
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class FavorListParams(BaseModel):
    """Query parameters for listing favors."""
    family_id: UUID
    contact_id: Optional[UUID] = None
    direction: Optional[str] = None
    status: Optional[str] = None
    event_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class FavorStatistics(BaseModel):
    """Schema for favor statistics."""
    total_given: float
    total_received: float
    net_balance: float  # received - given
    count_given: int
    count_received: int
    pending_count: int = 0  # Number of received favors pending return
    by_event_type: dict  # event_type -> {given, received, count}
    by_month: List[dict]  # [{month, given, received}]
    top_contacts: List[dict]  # [{contact_name, given, received, balance}]


class FavorPrediction(BaseModel):
    """Schema for return gift prediction."""
    contact_id: Optional[UUID] = None
    contact_name: str
    event_type: str
    min_amount: float
    suggested_amount: float
    max_amount: float
    basis: str  # Explanation of prediction basis
    historical_records: List[dict]  # Recent history used for prediction
