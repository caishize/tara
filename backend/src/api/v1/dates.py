"""
Date management API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import date

from ...db.session import get_db
from ...core.auth import get_current_user, get_current_family, verify_member_belongs_to_family
from ...modules.date_manager.date_service import DateService
from ...modules.date_manager.lunar_provider import lunar_calendar_provider


router = APIRouter(prefix="/dates", tags=["Dates"])


def _dto_to_response(d) -> "DateResponse":
    """Convert ImportantDateDTO to DateResponse."""
    return DateResponse(
        id=d.id,
        title=d.title,
        date_type=d.date_type,
        date_value=d.date_value.isoformat() if d.date_value else "",
        calendar_type='lunar' if d.is_lunar else 'solar',
        is_lunar=d.is_lunar,
        is_recurring=d.is_recurring,
        importance_level=d.importance_level,
        member_id=d.linked_member_id,
        lunar_month=d.lunar_month if d.is_lunar else None,
        lunar_day=d.lunar_day if d.is_lunar else None,
        reminder_offsets=d.reminder_days,
        days_until=d.days_until,
    )


def _dto_to_detail_response(d) -> "DateDetailResponse":
    """Convert ImportantDateDTO to DateDetailResponse."""
    return DateDetailResponse(
        id=d.id,
        title=d.title,
        date_type=d.date_type,
        date_value=d.date_value.isoformat() if d.date_value else "",
        calendar_type='lunar' if d.is_lunar else 'solar',
        is_lunar=d.is_lunar,
        is_recurring=d.is_recurring,
        importance_level=d.importance_level,
        reminder_offsets=d.reminder_days,
        member_id=d.linked_member_id,
        lunar_year=d.lunar_year,
        lunar_month=d.lunar_month,
        lunar_day=d.lunar_day,
        reminder_time=d.reminder_time,
        notes=d.notes,
        created_at=d.created_at or "",
    )


# Request/Response Models
class CreateDateRequest(BaseModel):
    """Create date request."""
    title: str
    date_type: str
    solar_date: str  # ISO format: YYYY-MM-DD
    member_id: Optional[str] = None
    is_lunar: bool = False
    lunar_year: Optional[int] = None
    lunar_month: Optional[int] = None
    lunar_day: Optional[int] = None
    is_recurring: bool = False
    reminder_offsets: Optional[List[int]] = None
    reminder_time: Optional[str] = None
    notes: Optional[str] = None


class DateResponse(BaseModel):
    """Date response."""
    id: str
    title: str
    date_type: str
    date_value: str  # Renamed from solar_date to match frontend
    calendar_type: str  # 'solar' or 'lunar'
    is_lunar: bool
    is_recurring: bool
    importance_level: int
    member_id: Optional[str] = None  # Associated member ID
    lunar_month: Optional[int] = None  # Lunar month for lunar dates
    lunar_day: Optional[int] = None  # Lunar day for lunar dates
    reminder_offsets: Optional[List[int]] = None
    days_until: Optional[int] = None  # Days until next occurrence


class DateDetailResponse(DateResponse):
    """Detailed date response."""
    member_id: Optional[str]
    lunar_year: Optional[int]
    lunar_month: Optional[int]
    lunar_day: Optional[int]
    reminder_offsets: Optional[List[int]]
    reminder_time: Optional[str]
    notes: Optional[str]
    created_at: str


class UpdateDateRequest(BaseModel):
    """Update date request - all fields optional."""
    title: Optional[str] = None
    date_type: Optional[str] = None
    solar_date: Optional[str] = None  # ISO format: YYYY-MM-DD
    member_id: Optional[str] = None
    is_lunar: Optional[bool] = None
    lunar_year: Optional[int] = None
    lunar_month: Optional[int] = None
    lunar_day: Optional[int] = None
    is_recurring: Optional[bool] = None
    reminder_offsets: Optional[List[int]] = None
    reminder_time: Optional[str] = None
    notes: Optional[str] = None


class ConvertSolarToLunarRequest(BaseModel):
    """Request to convert solar date to lunar."""
    solar_date: str  # ISO format: YYYY-MM-DD


class ConvertSolarToLunarResponse(BaseModel):
    """Response with lunar date."""
    lunar_date: str  # Chinese format: YYYY年M月D日


class ConvertLunarToSolarRequest(BaseModel):
    """Request to convert lunar date to solar."""
    lunar_date: str  # ISO format: YYYY-MM-DD (year, month, day as lunar values)


class ConvertLunarToSolarResponse(BaseModel):
    """Response with solar date."""
    solar_date: str  # ISO format: YYYY-MM-DD


@router.post("", response_model=DateResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=DateResponse, status_code=status.HTTP_201_CREATED)
async def create_date(
    request: CreateDateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family)
):
    """Create a new important date."""
    if request.member_id:
        await verify_member_belongs_to_family(UUID(request.member_id), family_id, db)

    service = DateService(db)

    try:
        from datetime import datetime
        solar_date = datetime.fromisoformat(request.solar_date).date()

        recurrence = "yearly" if request.is_recurring else None

        date_obj = await service.create_date(
            family_id=str(family_id),
            date_type=request.date_type,
            date_value=solar_date,
            title=request.title,
            recurrence=recurrence,
            linked_member_id=str(request.member_id) if request.member_id else None,
            reminder_days=request.reminder_offsets,
            notes=request.notes,
            created_by=str(user_id),
        )

        return _dto_to_response(date_obj)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=List[DateResponse], include_in_schema=False)
@router.get("/", response_model=List[DateResponse])
async def list_dates(
    member_id: Optional[str] = None,
    date_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family)
):
    """List important dates."""
    service = DateService(db)

    try:
        from datetime import datetime
        dates = await service.list_dates(
            family_id=str(family_id),
            member_id=UUID(member_id) if member_id else None,
            date_type=date_type,
            from_date=datetime.fromisoformat(from_date).date() if from_date else None,
            to_date=datetime.fromisoformat(to_date).date() if to_date else None
        )

        return [_dto_to_response(d) for d in dates]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/upcoming", response_model=List[DateResponse])
async def get_upcoming_dates(
    days_ahead: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family)
):
    """Get upcoming dates in the next N days."""
    service = DateService(db)

    try:
        dates = await service.get_upcoming_dates(str(family_id), days_ahead)

        return [_dto_to_response(d) for d in dates]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{date_id}", response_model=DateDetailResponse)
async def get_date(
    date_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get date details."""
    service = DateService(db)

    date_obj = await service.get_date(str(date_id), str(family_id))
    if not date_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Date not found"
        )

    return _dto_to_detail_response(date_obj)


@router.put("/{date_id}", response_model=DateDetailResponse)
async def update_date(
    date_id: UUID,
    request: UpdateDateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Update an existing date."""
    service = DateService(db)

    # Build updates dict from non-None fields
    updates = {}
    if request.title is not None:
        updates['title'] = request.title
    if request.date_type is not None:
        updates['date_type'] = request.date_type
    if request.solar_date is not None:
        from datetime import datetime
        updates['solar_date'] = datetime.fromisoformat(request.solar_date).date()
    if request.member_id is not None:
        updates['member_id'] = UUID(request.member_id) if request.member_id else None
    if request.is_lunar is not None:
        updates['is_lunar'] = request.is_lunar
    if request.lunar_year is not None:
        updates['lunar_year'] = request.lunar_year
    if request.lunar_month is not None:
        updates['lunar_month'] = request.lunar_month
    if request.lunar_day is not None:
        updates['lunar_day'] = request.lunar_day
    if request.is_recurring is not None:
        updates['is_recurring'] = request.is_recurring
    if request.reminder_offsets is not None:
        updates['reminder_offsets'] = request.reminder_offsets
    if request.reminder_time is not None:
        updates['reminder_time'] = request.reminder_time
    if request.notes is not None:
        updates['notes'] = request.notes

    try:
        # Verify ownership before updating
        existing = await service.get_date(str(date_id), str(family_id))
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Date not found"
            )

        date_obj = await service.update_date(str(date_id), str(family_id), updates)
        if not date_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Date not found"
            )

        return _dto_to_detail_response(date_obj)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{date_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_date(
    date_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Delete date."""
    service = DateService(db)

    # Verify ownership before deleting
    existing = await service.get_date(str(date_id), str(family_id))
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Date not found"
        )

    result = await service.delete_date(str(date_id), str(family_id))
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Date not found"
        )


@router.post("/convert/solar-to-lunar", response_model=ConvertSolarToLunarResponse)
async def convert_solar_to_lunar(
    request: ConvertSolarToLunarRequest,
    user_id: UUID = Depends(get_current_user),
):
    """Convert solar (Gregorian) date to lunar date."""
    try:
        # Parse the solar date string
        solar_date = date.fromisoformat(request.solar_date)

        # Convert to lunar date
        lunar_date = await lunar_calendar_provider.solar_to_lunar(solar_date)

        # Format as Chinese string
        lunar_str = str(lunar_date)

        return ConvertSolarToLunarResponse(lunar_date=lunar_str)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert date: {str(e)}"
        )


@router.post("/convert/lunar-to-solar", response_model=ConvertLunarToSolarResponse)
async def convert_lunar_to_solar(
    request: ConvertLunarToSolarRequest,
    user_id: UUID = Depends(get_current_user),
):
    """Convert lunar date to solar (Gregorian) date."""
    try:
        # Parse the lunar date string (YYYY-MM-DD format)
        parts = request.lunar_date.split('-')
        if len(parts) != 3:
            raise ValueError("Lunar date must be in YYYY-MM-DD format")

        lunar_year = int(parts[0])
        lunar_month = int(parts[1])
        lunar_day = int(parts[2])

        # Convert to solar date
        solar_date = await lunar_calendar_provider.lunar_to_solar(
            year=lunar_year,
            month=lunar_month,
            day=lunar_day,
            is_leap=False  # Default to non-leap month
        )

        return ConvertLunarToSolarResponse(solar_date=solar_date.isoformat())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid lunar date format: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert lunar date: {str(e)}"
        )


# =============================================================================
# Holidays Endpoints
# =============================================================================

class HolidayResponse(BaseModel):
    """Holiday response."""
    id: str
    title: str
    date: Optional[str] = None
    type: str


class HolidayPlanRequest(BaseModel):
    """Request to create a holiday preparation plan."""
    occurrence_date: str  # ISO format YYYY-MM-DD
    trigger_days_before: Optional[int] = None


@router.get("/holidays", response_model=List[HolidayResponse])
async def get_holidays(
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Get public holidays for a given year."""
    service = DateService(db)
    holidays = await service.get_holidays(year=year)
    return holidays


@router.post("/holidays/{holiday_type}/plan")
async def create_holiday_plan(
    holiday_type: str,
    request: HolidayPlanRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Create a preparation plan for a holiday.

    holiday_type is the holiday name (e.g. "春节", "中秋节").
    """
    from ...modules.date_manager.holiday_preparation_service import (
        HolidayPreparationService,
    )

    occurrence = date.fromisoformat(request.occurrence_date)

    service = HolidayPreparationService(db)
    result = await service.create_holiday_preparation(
        family_id=family_id,
        holiday_name=holiday_type,
        occurrence_date=occurrence,
        creator_id=user_id,
        trigger_days_before=request.trigger_days_before,
    )
    await db.commit()

    return {
        "success": result.success,
        "holiday_name": result.holiday_name,
        "occurrence_date": result.occurrence_date.isoformat(),
        "tasks_created": result.tasks_created,
        "message": result.message,
    }
