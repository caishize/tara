"""Collect active event association signals.

Extracted from InsightSignalCollector._collect_association_signals.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession


async def collect_association_signals(
    db: AsyncSession,
    family_id: UUID,
    target_date: date,
) -> List[Dict[str, Any]]:
    """Return active event associations within 14 days of *target_date*."""
    from ...curation.models import EventAssociation, CuratedEvent

    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=14)

    stmt = (
        select(EventAssociation)
        .join(CuratedEvent, EventAssociation.source_event_id == CuratedEvent.id)
        .where(
            and_(
                EventAssociation.family_id == family_id,
                EventAssociation.is_dismissed.is_(False),
                CuratedEvent.is_active.is_(True),
                CuratedEvent.normalized_start >= start,
                CuratedEvent.normalized_start <= end,
            )
        )
        .limit(15)
    )
    result = await db.execute(stmt)

    return [
        {
            "association_id": str(assoc.id),
            "source_event_id": str(assoc.source_event_id),
            "target_id": assoc.target_id,
            "target_type": assoc.target_type,
            "association_type": assoc.association_type,
            "title": assoc.title,
            "reason": assoc.reason,
            "priority": assoc.priority,
        }
        for assoc in result.scalars().all()
    ]
