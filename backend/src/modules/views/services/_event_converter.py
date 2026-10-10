"""Shared helpers for kanban services.

Contains:
- to_kanban_event: Convert CuratedEvent ORM → KanbanEvent schema
- get_user_timezone: Load per-user timezone from settings

Eliminates duplication of these helpers that were previously copy-pasted
across kanban_service.py, memory_lane_service.py, and event_detail_service.py.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.utils.timezone import DEFAULT_TIMEZONE
from ...curation.models import CuratedEvent
from ...trip.services.trip_status import compute_trip_status
from ..kanban_schemas import KanbanEvent, PreparationItem

logger = logging.getLogger(__name__)


def to_kanban_event(
    ev: CuratedEvent,
    effective_start: Optional[datetime] = None,
    effective_end: Optional[datetime] = None,
) -> KanbanEvent:
    """Convert a CuratedEvent ORM instance to a KanbanEvent schema.

    Args:
        ev: The CuratedEvent ORM instance.
        effective_start: Override for start datetime (e.g. from TripPlan).
        effective_end: Override for end datetime (e.g. from TripPlan).

    Returns:
        A KanbanEvent Pydantic model.
    """
    prep_items: List[PreparationItem] = [
        PreparationItem(
            key=str(row.key),
            item=row.text,
            source=row.source,
            done=row.done,
        )
        for row in (ev.preparation_item_rows or [])
    ]

    start_dt = effective_start or ev.normalized_start
    end_dt = effective_end or ev.normalized_end

    effective_status = ev.status
    if start_dt and end_dt:
        effective_status = compute_trip_status(
            ev.status,
            start_dt.date(),
            end_dt.date(),
        )

    return KanbanEvent(
        id=str(ev.id),
        title=ev.title,
        event_type=ev.event_type,
        start_time=start_dt,
        end_time=end_dt,
        location=ev.location,
        status=effective_status,
        priority=ev.priority,
        notes=ev.notes,
        trip_id=str(ev.trip_id) if ev.trip_id else None,
        trip_name=ev.trip_name,
        preparation_items=prep_items,
        tags=ev.tags,
        visibility_tier=ev.visibility_tier,
    )


async def get_user_timezone(session: AsyncSession, user_id: UUID) -> ZoneInfo:
    """Load per-user timezone from user_insight_settings.

    Falls back to DEFAULT_TIMEZONE if not found or invalid.
    """
    from ...insight.models import UserInsightSettings

    stmt = select(UserInsightSettings.timezone).where(
        UserInsightSettings.user_id == user_id
    )
    try:
        table_exists = await session.execute(
            text("SELECT to_regclass('public.user_insight_settings')")
        )
        if table_exists.scalar_one_or_none() is None:
            return DEFAULT_TIMEZONE
        result = await session.execute(stmt)
    except SQLAlchemyError as exc:
        logger.warning(
            "Failed to load user timezone for user %s, using default: %s",
            user_id,
            exc,
        )
        return DEFAULT_TIMEZONE
    tz_name = result.scalar_one_or_none()

    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except (KeyError, ValueError):
            logger.warning(
                "Invalid timezone '%s' for user %s, using default",
                tz_name,
                user_id,
            )

    return DEFAULT_TIMEZONE
