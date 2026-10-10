"""
Helper to get current work info from work_histories table.

Single source of truth for current company/position — replaces
the redundant columns on the members table.
"""
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .models.professional import WorkHistory


async def get_current_work(
    session: AsyncSession,
    member_id: UUID,
) -> Optional[Dict[str, Optional[str]]]:
    """Get the current work history entry for a member.

    Returns dict with company_name, position, department or None.
    """
    stmt = (
        select(WorkHistory)
        .where(
            and_(
                WorkHistory.member_id == member_id,
                WorkHistory.is_current.is_(True),
            )
        )
        .order_by(WorkHistory.updated_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    wh = result.scalar_one_or_none()
    if wh is None:
        return None
    return {
        "company_name": wh.company_name,
        "position": wh.position,
        "department": wh.department,
    }


async def get_current_work_batch(
    session: AsyncSession,
    member_ids: List[UUID],
) -> Dict[UUID, Dict[str, Optional[str]]]:
    """Batch-fetch current work for multiple members (prevents N+1).

    Returns a dict keyed by member_id.
    Uses PostgreSQL DISTINCT ON to guarantee one row per member.
    """
    if not member_ids:
        return {}

    stmt = (
        select(WorkHistory)
        .where(
            and_(
                WorkHistory.member_id.in_(member_ids),
                WorkHistory.is_current.is_(True),
            )
        )
        .order_by(WorkHistory.member_id, WorkHistory.updated_at.desc())
        .distinct(WorkHistory.member_id)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return {
        wh.member_id: {
            "company_name": wh.company_name,
            "position": wh.position,
            "department": wh.department,
        }
        for wh in rows
    }
