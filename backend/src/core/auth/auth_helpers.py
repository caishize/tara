"""
Authorization helper functions for cross-entity ownership checks.

Provides utility functions to verify that resources belong to the
requesting user's family, preventing cross-family data access.
"""
import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...modules.member.models.member import Member


logger = logging.getLogger(__name__)


async def verify_member_belongs_to_family(
    member_id: UUID,
    family_id: UUID,
    db: AsyncSession,
) -> Member:
    """
    Verify that a member belongs to the given family.

    Args:
        member_id: The member to check.
        family_id: The family the member should belong to.
        db: Database session.

    Returns:
        The Member object if verification passes.

    Raises:
        HTTPException 404: If the member does not exist.
        HTTPException 403: If the member belongs to a different family.
    """
    result = await db.execute(
        select(Member).where(Member.id == member_id)
    )
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Member {member_id} not found",
        )

    if member.family_id != family_id:
        logger.warning(
            "Cross-family access attempt: family_id=%s tried to access member=%s (family=%s)",
            family_id, member_id, member.family_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member does not belong to your family",
        )

    return member
