"""Collect unprocessed preference signals (orphan obligations).

Extracted from InsightSignalCollector._collect_preference_signals.
"""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession


async def collect_preference_signals(
    db: AsyncSession,
    user_id: UUID,
) -> List[Dict[str, Any]]:
    """Return unprocessed orphan-obligation preference signals."""
    from ...curation.models import PreferenceSignal

    stmt = (
        select(PreferenceSignal)
        .where(
            and_(
                PreferenceSignal.user_id == user_id,
                PreferenceSignal.signal_type == "orphan_obligation",
                PreferenceSignal.processed.is_(False),
            )
        )
        .order_by(PreferenceSignal.created_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)

    return [
        {
            "signal_id": str(ps.id),
            "signal_type": ps.signal_type,
            "source_type": ps.source_type,
            "source_id": str(ps.source_id) if ps.source_id else None,
            "source_context": ps.source_context or {},
            "category_key": ps.category_key,
            "created_at": ps.created_at.isoformat() if ps.created_at else None,
        }
        for ps in result.scalars().all()
    ]
