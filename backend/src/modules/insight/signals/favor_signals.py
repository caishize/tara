"""Collect protected favor signals (pending social obligations).

Extracted from InsightSignalCollector._collect_protected_signals (favor half).
"""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession


async def collect_favor_signals(
    db: AsyncSession,
    family_id: UUID,
) -> List[Dict[str, Any]]:
    """Return pending inbound favors that may need a return gift."""
    from ...relationship.models import FavorRecord

    stmt = (
        select(FavorRecord)
        .where(
            and_(
                FavorRecord.family_id == family_id,
                FavorRecord.status == "pending",
                FavorRecord.direction == "receive",
            )
        )
        .order_by(FavorRecord.recorded_at.asc())
        .limit(10)
    )
    result = await db.execute(stmt)

    return [
        {
            "signal_type": "favor",
            "favor_record_id": str(favor.id),
            "contact_name": favor.contact_name,
            "contact_id": str(favor.contact_id) if favor.contact_id else None,
            "event_type": favor.event_type,
            "amount": str(favor.amount),
            "direction": favor.direction,
            "recorded_at": (
                favor.recorded_at.isoformat() if favor.recorded_at else None
            ),
            "note": favor.note,
        }
        for favor in result.scalars().all()
    ]
