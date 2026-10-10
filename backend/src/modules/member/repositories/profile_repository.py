"""
MemberProfile repository - Data access layer.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from ..models.member import MemberProfile


class ProfileRepository:
    """Repository for MemberProfile CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, profile_data: Dict[str, Any]) -> MemberProfile:
        """Create a new profile."""
        profile = MemberProfile(**profile_data)
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def get_by_member_id(self, member_id: UUID) -> Optional[MemberProfile]:
        """Get profile by member ID."""
        stmt = select(MemberProfile).where(MemberProfile.member_id == member_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        member_id: UUID,
        profile_data: Dict[str, Any]
    ) -> Optional[MemberProfile]:
        """Update profile fields (merge JSONB)."""
        existing = await self.get_by_member_id(member_id)
        if not existing:
            return None

        # Merge JSONB fields
        if 'preferences' in profile_data and existing.preferences:
            profile_data['preferences'] = {
                **existing.preferences,
                **profile_data['preferences']
            }
        if 'habits' in profile_data and existing.habits:
            profile_data['habits'] = {
                **existing.habits,
                **profile_data['habits']
            }
        if 'personality_traits' in profile_data and existing.personality_traits:
            profile_data['personality_traits'] = {
                **existing.personality_traits,
                **profile_data['personality_traits']
            }

        stmt = (
            update(MemberProfile)
            .where(MemberProfile.member_id == member_id)
            .values(**profile_data)
            .returning(MemberProfile)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def upsert(
        self,
        member_id: UUID,
        profile_data: Dict[str, Any]
    ) -> MemberProfile:
        """Create or update profile."""
        profile_data['member_id'] = member_id

        stmt = insert(MemberProfile).values(**profile_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=['member_id'],
            set_=profile_data
        ).returning(MemberProfile)

        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one()

    async def update_embedding(
        self,
        member_id: UUID,
        embedding_vector: List[float]
    ) -> bool:
        """Update semantic embedding vector."""
        stmt = (
            update(MemberProfile)
            .where(MemberProfile.member_id == member_id)
            .values(embedding=embedding_vector)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0
