"""Collect urgent commitment signals (deadline within 7 days).

Extracted from InsightSignalCollector._collect_protected_signals (commitment half).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.utils.timezone import utc_now


async def collect_commitment_signals(
    db: AsyncSession,
    user_id: UUID,
    family_id: UUID,
) -> List[Dict[str, Any]]:
    """Return pending commitments whose deadline is within 7 days."""
    from ...memory.commitment_models import CommitmentItemRecord

    deadline_cutoff = utc_now() + timedelta(days=7)
    stmt = (
        select(CommitmentItemRecord)
        .where(
            and_(
                CommitmentItemRecord.user_id == user_id,
                CommitmentItemRecord.family_id == family_id,
                CommitmentItemRecord.status == "pending",
                CommitmentItemRecord.deadline.isnot(None),
                CommitmentItemRecord.deadline <= deadline_cutoff,
            )
        )
        .order_by(CommitmentItemRecord.deadline.asc())
        .limit(10)
    )
    result = await db.execute(stmt)

    return [
        {
            "signal_type": "commitment",
            "commitment_id": str(c.id),
            "who": c.who,
            "what": c.what,
            "to_whom": c.to_whom,
            "deadline": c.deadline.isoformat() if c.deadline else None,
            "commitment_type": c.commitment_type,
        }
        for c in result.scalars().all()
    ]
