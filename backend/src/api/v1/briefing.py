"""Briefing API routes - /api/v1/briefing/*

Thin routing layer for daily briefings and smart suggestions.
Delegates to briefing module services.
"""
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import require_auth
from ...core.utils.timezone import local_today
from ...db.session import get_db
from ...modules.briefing.schemas import DailyBriefing

router = APIRouter(prefix="/briefing", tags=["Briefing"])


class BriefingSettingsRequest(BaseModel):
    """Request body for PUT /briefing/settings."""
    morning_hour: Optional[int] = Field(None, ge=0, le=23)
    afternoon_hour: Optional[int] = Field(None, ge=0, le=23)
    evening_hour: Optional[int] = Field(None, ge=0, le=23)
    timezone: Optional[str] = Field(None, max_length=50)
    enabled_modules: Optional[List[str]] = None


# ==================== Daily Briefing ====================


@router.get("/daily", response_model=DailyBriefing)
async def get_daily_briefing(
    target_date: Optional[date] = Query(None, description="Target date (defaults to today)"),
    period: Optional[str] = Query(None, description="Briefing period: morning/afternoon/evening"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    force_refresh: bool = Query(False, description="Bypass cache and regenerate"),
    db: AsyncSession = Depends(get_db),
):
    """Get AI-generated daily briefing with events, insights, and suggestions."""
    from ...modules.briefing.services.briefing_service import DailyBriefingService

    user_id, effective_family_id = require_auth(family_id=family_id)

    if target_date is None:
        target_date = local_today()

    days_diff = abs((target_date - local_today()).days)
    if days_diff > 90:
        raise HTTPException(
            status_code=400,
            detail="Target date must be within 90 days of today",
        )

    service = DailyBriefingService(db)
    return await service.get_or_generate_briefing(
        user_id=user_id,
        family_id=effective_family_id,
        target_date=target_date,
        period=period,
        force_refresh=force_refresh,
    )


# ==================== Smart Suggestions ====================


@router.get("/suggestions")
async def get_suggestions(
    limit: int = Query(10, ge=1, le=50, description="Maximum suggestions"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get smart suggestions based on schedules, memories, and relationships."""
    from ...modules.briefing.services.suggestion_service import SmartSuggestionService

    user_id, effective_family_id = require_auth(family_id=family_id)

    service = SmartSuggestionService(db)
    suggestions = await service.generate_suggestions(
        user_id=user_id,
        family_id=effective_family_id,
        limit=limit,
    )

    return {"suggestions": [s.model_dump() if hasattr(s, 'model_dump') else s for s in suggestions]}


class SuggestionActionRequest(BaseModel):
    """Request body for suggestion action."""
    action: str = Field(..., description="Action to execute (e.g., schedule_meeting, send_message)")
    params: Optional[dict] = Field(None, description="Optional action parameters")


@router.post("/suggestions/{suggestion_id}/action")
async def execute_suggestion_action(
    suggestion_id: str,
    body: SuggestionActionRequest = Body(...),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Execute/acknowledge a suggestion action."""
    from ...modules.briefing.services.suggestion_service import SmartSuggestionService

    user_id, _ = require_auth(family_id=family_id)

    service = SmartSuggestionService(db)
    result = await service.execute_suggestion_action(
        suggestion_id=suggestion_id,
        action=body.action,
        user_id=user_id,
        action_params=body.params,
    )
    await _emit_suggestion_signal(
        "SUGGESTION_ACTED",
        suggestion_id=suggestion_id,
        user_id=user_id,
        family_id=family_id,
        source="suggestion_action",
    )
    return result


@router.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(
    suggestion_id: str,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss a suggestion."""
    from ...modules.briefing.services.suggestion_service import SmartSuggestionService

    user_id, _ = require_auth(family_id=family_id)

    service = SmartSuggestionService(db)
    dismissed = await service.dismiss_suggestion(suggestion_id, user_id)
    if not dismissed:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    await _emit_suggestion_signal(
        "SUGGESTION_DISMISSED",
        suggestion_id=suggestion_id,
        user_id=user_id,
        family_id=family_id,
        source="suggestion_dismiss",
    )
    return {"success": True, "suggestion_id": suggestion_id, "message": "Suggestion dismissed"}


# ==================== Feedback Bus Helpers ====================


import logging as _logging

_logger = _logging.getLogger(__name__)


async def _emit_suggestion_signal(
    signal_name: str,
    suggestion_id: str,
    user_id: UUID,
    family_id: Optional[UUID],
    source: str,
) -> None:
    """Emit a FeedbackBus signal for suggestion-related user actions."""
    if not family_id:
        return
    try:
        from ...core.feedback import get_feedback_bus, FeedbackSignal

        bus = get_feedback_bus()
        signal = FeedbackSignal[signal_name]
        await bus.emit(
            signal=signal,
            data={"suggestion_id": suggestion_id},
            family_id=family_id,
            user_id=user_id,
            source=source,
        )
    except Exception:
        _logger.warning("FeedbackBus emit failed for %s", signal_name, exc_info=True)


# ==================== Briefing Settings ====================


@router.get("/settings")
async def get_briefing_settings(
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get briefing schedule settings for the current user."""
    from ...modules.briefing.models import UserBriefingSettings
    from sqlalchemy import select

    user_id, _ = require_auth(family_id=family_id)

    result = await db.execute(
        select(UserBriefingSettings).where(UserBriefingSettings.user_id == user_id)
    )
    row = result.scalar_one_or_none()

    if row is None:
        return {
            "morning_hour": 7,
            "afternoon_hour": 12,
            "evening_hour": 20,
            "timezone": None,
            "enabled_modules": ["today_events", "preparation", "weather", "favor"],
        }

    return {
        "morning_hour": row.morning_hour,
        "afternoon_hour": row.afternoon_hour,
        "evening_hour": row.evening_hour,
        "timezone": row.timezone,
        "enabled_modules": row.enabled_modules or [],
    }


@router.put("/settings")
async def update_briefing_settings(
    body: BriefingSettingsRequest,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Update briefing schedule settings for the current user."""
    from ...modules.briefing.models import UserBriefingSettings
    from sqlalchemy import select

    user_id, _ = require_auth(family_id=family_id)

    result = await db.execute(
        select(UserBriefingSettings).where(UserBriefingSettings.user_id == user_id)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = UserBriefingSettings(user_id=user_id)
        db.add(row)

    if body.morning_hour is not None:
        row.morning_hour = body.morning_hour
    if body.afternoon_hour is not None:
        row.afternoon_hour = body.afternoon_hour
    if body.evening_hour is not None:
        row.evening_hour = body.evening_hour
    if body.timezone is not None:
        row.timezone = body.timezone
    if body.enabled_modules is not None:
        row.enabled_modules = body.enabled_modules

    await db.commit()

    return {
        "morning_hour": row.morning_hour,
        "afternoon_hour": row.afternoon_hour,
        "evening_hour": row.evening_hour,
        "timezone": row.timezone,
        "enabled_modules": row.enabled_modules or [],
    }
