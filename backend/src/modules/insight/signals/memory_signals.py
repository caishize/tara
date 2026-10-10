"""Collect recent significant memory signals.

Extracted from InsightSignalCollector._collect_memory_signals.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.utils.timezone import utc_now


async def collect_memory_signals(
    db: AsyncSession,
    user_id: UUID,
) -> List[Dict[str, Any]]:
    """Return recent high-importance memories from the last 7 days."""
    from ...memory.models import ConversationMemory, MemoryStatus

    seven_days_ago = utc_now() - timedelta(days=7)
    stmt = (
        select(ConversationMemory)
        .where(
            and_(
                ConversationMemory.user_id == user_id,
                ConversationMemory.status == MemoryStatus.ACTIVE.value,
                ConversationMemory.importance >= 6,
                ConversationMemory.created_at >= seven_days_ago,
            )
        )
        .order_by(ConversationMemory.importance.desc())
        .limit(10)
    )
    result = await db.execute(stmt)

    return [
        {
            "memory_id": str(mem.id),
            "memory_type": mem.memory_type,
            "summary": mem.summary,
            "importance": mem.importance,
            "entities": mem.entities if isinstance(mem.entities, dict) else {},
            "created_at": mem.created_at.isoformat() if mem.created_at else None,
        }
        for mem in result.scalars().all()
    ]
