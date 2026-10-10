"""
Pydantic schemas for TripExpense entity.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


class TripExpenseBase(BaseModel):
    """Base schema for TripExpense."""
    expense_date: date
    category: str = Field(..., max_length=50)
    amount: Decimal = Field(..., ge=0)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    payment_method: Optional[str] = Field(None, max_length=100)
    receipt_url: Optional[str] = Field(None, max_length=500)
    itinerary_item_id: Optional[UUID] = None


class TripExpenseCreate(TripExpenseBase):
    """Schema for creating a new TripExpense.

    Note: trip_id is not included here as it comes from the URL path parameter.
    """
    pass


class TripExpenseUpdate(BaseModel):
    """Schema for updating an existing TripExpense."""
    expense_date: Optional[date] = None
    category: Optional[str] = Field(None, max_length=50)
    amount: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    payment_method: Optional[str] = Field(None, max_length=100)
    receipt_url: Optional[str] = Field(None, max_length=500)
    itinerary_item_id: Optional[UUID] = None


class TripExpenseResponse(TripExpenseBase):
    """Schema for TripExpense response."""
    expense_id: UUID
    trip_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TripExpenseListResponse(BaseModel):
    """Schema for paginated list of TripExpenses."""
    items: List[TripExpenseResponse]
    total: int
    page: int
    page_size: int


class BudgetStatusResponse(BaseModel):
    """Schema for budget status response."""
    trip_id: UUID
    total_budget: Optional[Decimal]
    total_spent: Decimal
    remaining_budget: Optional[Decimal]
    budget_used_percentage: Optional[float]
    category_breakdown: dict  # {category: {budgeted: X, spent: Y, remaining: Z}}
    is_over_budget: bool
    warning_threshold_reached: bool  # True if >= 90% used
