"""Expense tracking API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from decimal import Decimal

from ....db.session import get_db
from ....core.auth import get_current_user, get_current_family
from ..models.trip_expense import TripExpense
from ..schemas.expense import (
    TripExpenseCreate,
    TripExpenseUpdate,
    TripExpenseResponse,
    TripExpenseListResponse,
    BudgetStatusResponse
)
from ..services.budget_tracker import BudgetTracker

router = APIRouter(prefix="/trips/plans/{trip_id}/expenses", tags=["trip-expenses"])


@router.post("", response_model=TripExpenseResponse)
async def create_expense(
    trip_id: UUID,
    expense_data: TripExpenseCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Create a new travel expense."""
    try:
        # Create expense directly instead of using BudgetTracker
        # to ensure we get the full model with all fields
        from ..models.trip_plan import TripPlan
        from datetime import date

        # Validate category
        valid_categories = ["transportation", "accommodation", "tickets", "food", "shopping", "other"]
        if expense_data.category not in valid_categories:
            raise ValueError(f"Invalid category: {expense_data.category}")

        # Get trip
        trip_result = await db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = trip_result.scalar_one_or_none()
        if not trip:
            raise HTTPException(status_code=404, detail=f"Trip {trip_id} not found")

        # Create expense record
        expense = TripExpense(
            trip_id=trip_id,
            expense_date=expense_data.expense_date or date.today(),
            category=expense_data.category,
            amount=expense_data.amount,
            description=expense_data.description,
            location=expense_data.location,
            payment_method=expense_data.payment_method,
            receipt_url=expense_data.receipt_url
        )

        db.add(expense)

        # Update trip actual expense
        trip.actual_expense += expense_data.amount

        await db.commit()
        await db.refresh(expense)

        return expense
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=TripExpenseListResponse)
async def list_expenses(
    trip_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """List all expenses for a trip."""
    query = select(TripExpense).where(TripExpense.trip_id == trip_id)
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(TripExpense.expense_date.desc())

    result = await db.execute(query)
    expenses = result.scalars().all()

    count_query = select(func.count(TripExpense.expense_id)).where(
        TripExpense.trip_id == trip_id
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    items = [TripExpenseResponse.model_validate(exp) for exp in expenses]

    return TripExpenseListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/budget-status", response_model=BudgetStatusResponse)
async def get_budget_status(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get budget usage status for a trip."""
    try:
        tracker = BudgetTracker(db)
        status = await tracker.get_budget_status(trip_id)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{expense_id}")
async def delete_expense(
    trip_id: UUID,
    expense_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Delete an expense."""
    result = await db.execute(
        select(TripExpense)
        .where(TripExpense.expense_id == expense_id)
        .where(TripExpense.trip_id == trip_id)
    )
    expense = result.scalar_one_or_none()

    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    await db.delete(expense)
    await db.commit()

    return {"message": "Expense deleted", "expense_id": str(expense_id)}
