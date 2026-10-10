"""Concrete MemberService wrapping legacy member_management."""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .interface import (
    IMemberService,
    FamilyInfo,
    MemberInfo,
    MemberProfileInfo,
)

logger = logging.getLogger(__name__)


class MemberService(IMemberService):
    """MemberService delegates to legacy member_management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Family
    # ------------------------------------------------------------------

    async def get_family(self, family_id: str) -> Optional[FamilyInfo]:
        from ..member.models.member import Member

        # families table may not exist in legacy; derive from members
        result = await self.session.execute(
            select(Member).where(
                Member.family_id == UUID(family_id),
                Member.is_deleted.is_(False),
            ).limit(1)
        )
        member = result.scalar_one_or_none()
        if member is None:
            return None
        return FamilyInfo(
            id=family_id,
            name="",
            owner_user_id=str(member.created_by),
        )

    # ------------------------------------------------------------------
    # Members CRUD
    # ------------------------------------------------------------------

    async def list_members(self, family_id: str) -> List[MemberInfo]:
        from ..member.models.member import Member

        result = await self.session.execute(
            select(Member).where(
                Member.family_id == UUID(family_id),
                Member.is_deleted.is_(False),
            )
        )
        members = result.scalars().all()
        return [self._to_info(m) for m in members]

    async def get_member(
        self, member_id: str, family_id: str,
    ) -> Optional[MemberInfo]:
        from ..member.models.member import Member

        result = await self.session.execute(
            select(Member).where(
                Member.id == UUID(member_id),
                Member.family_id == UUID(family_id),
                Member.is_deleted.is_(False),
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            return None
        return self._to_info(member)

    async def create_member(
        self, family_id: str, name: str,
        relation: Optional[str] = None, **kwargs: Any,
    ) -> MemberInfo:
        from ..member.models.member import Member

        member = Member(
            family_id=UUID(family_id),
            name=name,
            **kwargs,
        )
        if relation:
            member.tags = [relation]
        self.session.add(member)
        await self.session.flush()
        return self._to_info(member)

    async def update_member(
        self, member_id: str, family_id: str,
        updates: Dict[str, Any],
    ) -> MemberInfo:
        from ..member.models.member import Member

        result = await self.session.execute(
            select(Member).where(
                Member.id == UUID(member_id),
                Member.family_id == UUID(family_id),
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            raise ValueError(f"Member {member_id} not found")

        for key, value in updates.items():
            if hasattr(member, key):
                setattr(member, key, value)
        await self.session.flush()
        return self._to_info(member)

    async def delete_member(
        self, member_id: str, family_id: str,
    ) -> bool:
        from ..member.models.member import Member

        result = await self.session.execute(
            select(Member).where(
                Member.id == UUID(member_id),
                Member.family_id == UUID(family_id),
                Member.is_deleted.is_(False),
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            return False
        member.is_deleted = True
        await self.session.flush()
        return True

    # ------------------------------------------------------------------
    # Extended profile
    # ------------------------------------------------------------------

    async def get_member_profile(
        self, member_id: str, family_id: str,
    ) -> Optional[MemberProfileInfo]:
        from ..member.models.member import Member
        from ..member.models.member import MemberProfile

        # Verify member belongs to family
        mem_result = await self.session.execute(
            select(Member).where(
                Member.id == UUID(member_id),
                Member.family_id == UUID(family_id),
            )
        )
        member = mem_result.scalar_one_or_none()
        if member is None:
            return None

        result = await self.session.execute(
            select(MemberProfile).where(
                MemberProfile.member_id == UUID(member_id),
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return MemberProfileInfo(member_id=member_id)
        return self._to_profile_info(profile)

    async def update_member_profile(
        self, member_id: str, family_id: str,
        updates: Dict[str, Any],
    ) -> MemberProfileInfo:
        from ..member.models.member import Member
        from ..member.models.member import MemberProfile

        # Verify member belongs to family
        mem_result = await self.session.execute(
            select(Member).where(
                Member.id == UUID(member_id),
                Member.family_id == UUID(family_id),
            )
        )
        member = mem_result.scalar_one_or_none()
        if member is None:
            raise ValueError(f"Member {member_id} not found in family")

        result = await self.session.execute(
            select(MemberProfile).where(
                MemberProfile.member_id == UUID(member_id),
            )
        )
        profile = result.scalar_one_or_none()

        if profile is None:
            profile = MemberProfile(member_id=UUID(member_id))
            self.session.add(profile)

        for key, value in updates.items():
            if hasattr(profile, key) and key != "member_id":
                setattr(profile, key, value)
        await self.session.flush()
        return self._to_profile_info(profile)

    # ------------------------------------------------------------------
    # Converters
    # ------------------------------------------------------------------

    @staticmethod
    def _to_info(member: Any) -> MemberInfo:
        return MemberInfo(
            id=str(member.id),
            user_id=str(member.user_id) if getattr(member, "user_id", None) else None,
            family_id=str(member.family_id),
            name=member.name,
            relation=(member.tags[0] if member.tags else None),
            birthday=member.date_of_birth,
            locations=member.locations,
            preferences=None,
            tags=member.tags or [],
        )

    @staticmethod
    def _to_profile_info(profile: Any) -> MemberProfileInfo:
        return MemberProfileInfo(
            member_id=str(profile.member_id),
            preferences=profile.preferences,
            habits=profile.habits,
            health_summary=profile.health_summary,
            personality_traits=profile.personality_traits,
            special_notes=profile.special_notes,
        )
