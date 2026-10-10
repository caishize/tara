"""
Shared utilities for curation Celery tasks.
"""
from typing import List
from uuid import UUID

from sqlalchemy import select


async def get_active_families(session_factory) -> List[UUID]:
    """Get all active families that have at least one active user.

    Used by curation, hygiene, and other family-scoped tasks.
    """
    async with session_factory() as db:
        from ..member.models import User

        result = await db.execute(
            select(User.family_id)
            .where(User.is_active == True)
            .where(User.family_id.isnot(None))
            .distinct()
        )
        family_ids = result.scalars().all()
        return [fid for fid in family_ids if fid is not None]
