"""Views API routes - /api/v1/views/*

Compatibility routing layer that maps view-oriented paths to underlying
services.  The canonical endpoints live under /kanban, but some clients
use /views paths — this module ensures both work identically.
"""
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import require_auth
from ...db.session import get_db
from ...modules.views.kanban_schemas import TimelineResponse
from ...modules.views.services.timeline_service import TimelineService

router = APIRouter(prefix="/views", tags=["Views"])


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    direction: Literal["past", "future"] = Query("future"),
    days: int = Query(14, ge=1, le=30),
    cursor: Optional[str] = Query(None, description="Date cursor (YYYY-MM-DD)"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get directional timeline with day groups (past or future).

    Compatibility alias for /kanban/directional-timeline.
    """
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = TimelineService(db)
    return await service.get_timeline(
        user_id=user_id,
        family_id=effective_family_id,
        direction=direction,
        days=days,
        cursor=cursor,
    )
