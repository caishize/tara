"""Collect upcoming curated event signals.

Extracted from InsightSignalCollector._collect_event_signals.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession


async def collect_event_signals(
    db: AsyncSession,
    family_id: UUID,
    target_date: date,
) -> List[Dict[str, Any]]:
    """Return upcoming curated events within 14 days of *target_date*."""
    from ...curation.models import CuratedEvent

    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=14)

    stmt = (
        select(CuratedEvent)
        .where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status.in_(["pending", "confirmed"]),
                CuratedEvent.normalized_start >= start,
                CuratedEvent.normalized_start <= end,
            )
        )
        .order_by(CuratedEvent.normalized_start.asc())
        .limit(20)
    )
    result = await db.execute(stmt)

    return [
        {
            "event_id": str(ev.id),
            "trip_id": str(ev.trip_id) if ev.trip_id else None,
            "title": ev.title,
            "event_type": ev.event_type,
            "start": (
                ev.normalized_start.isoformat() if ev.normalized_start else None
            ),
            "end": ev.normalized_end.isoformat() if ev.normalized_end else None,
            "location": ev.location,
            "priority": ev.priority,
            "life_context_hint": ev.life_context_hint,
        }
        for ev in result.scalars().all()
    ]
