"""
Member repository - Data access layer for Member entity.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date
from sqlalchemy import select, update, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import uuid as uuid_module

from ..models.member import Member


class MemberRepository:
    """Repository for Member CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, member_data: Dict[str, Any]) -> Member:
        """Create a new member."""
        # Convert date string to date object if needed
        if 'date_of_birth' in member_data and isinstance(member_data['date_of_birth'], str):
            member_data['date_of_birth'] = datetime.strptime(member_data['date_of_birth'], '%Y-%m-%d').date()

        # Keep gender as a string value, not enum (database has enum type but SQLAlchemy uses string)
        if 'gender' in member_data and member_data['gender']:
            g = member_data['gender']
            # Handle Python enum (str(enum) differs between 3.9 and 3.11)
            member_data['gender'] = g.value if hasattr(g, 'value') else str(g).lower()

        # Generate ID for new member
        if 'id' not in member_data:
            member_data['id'] = uuid_module.uuid4()

        # Use raw SQL with CAST to insert gender as enum
        # This avoids SQLAlchemy's type conversion issues
        gender_val = member_data.pop('gender', None)

        member = Member(**member_data)

        # Calculate age if date_of_birth is provided
        if member.date_of_birth:
            calculated_age = member.calculate_age()
            # Set age to None if it's negative (future date of birth)
            member.age = calculated_age if calculated_age and calculated_age >= 0 else None

        # Set gender after ORM initialization to avoid type issues
        if gender_val:
            member.gender = gender_val

        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def get_by_id(
        self,
        member_id: UUID,
        include_deleted: bool = False
    ) -> Optional[Member]:
        """Get member by ID."""
        stmt = select(Member).where(Member.id == member_id)
        if not include_deleted:
            stmt = stmt.where(Member.is_deleted == False)

        stmt = stmt.options(selectinload(Member.profile))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_family(
        self,
        family_id: UUID,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Member]:
        """List members by family with filters."""
        stmt = select(Member).where(
            and_(
                Member.family_id == family_id,
                Member.is_deleted == False
            )
        )

        if filters:
            if filters.get('relation_type'):
                # TODO: Join with member_relations
                pass
            if filters.get('min_profile_completion'):
                stmt = stmt.where(
                    Member.profile_completion >= filters['min_profile_completion']
                )

        stmt = stmt.options(selectinload(Member.profile))
        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        member_id: UUID,
        member_data: Dict[str, Any]
    ) -> Optional[Member]:
        """Update member (partial updates supported)."""
        stmt = (
            update(Member)
            .where(Member.id == member_id)
            .values(**member_data)
            .returning(Member)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def soft_delete(self, member_id: UUID) -> bool:
        """Soft delete member by setting is_deleted=True."""
        stmt = (
            update(Member)
            .where(Member.id == member_id)
            .values(is_deleted=True)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def calculate_profile_completion(self, member_id: UUID) -> int:
        """
        Calculate profile completion percentage.

        Key fields (25% each):
        - name (always present)
        - date_of_birth
        - phone
        - has_relation
        """
        member = await self.get_by_id(member_id)
        if not member:
            return 0

        completion = 25  # name is always present

        if member.date_of_birth:
            completion += 25
        if member.phone:
            completion += 25

        # Check if member has any relations
        from ..models.member import MemberRelation
        stmt = select(MemberRelation).where(
            or_(
                MemberRelation.from_member_id == member_id,
                MemberRelation.to_member_id == member_id
            )
        ).limit(1)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            completion += 25

        # Update member's profile_completion
        await self.update(member_id, {'profile_completion': completion})

        return completion

    async def search_by_name(
        self,
        family_id: UUID,
        name_query: str,
        limit: int = 10
    ) -> List[Member]:
        """Search members by name or nickname (fuzzy search)."""
        # Search by name or nickname
        stmt = select(Member).where(
            and_(
                Member.family_id == family_id,
                Member.is_deleted == False,
                or_(
                    Member.name.ilike(f'%{name_query}%'),
                    Member.nickname.ilike(f'%{name_query}%')
                )
            )
        ).options(selectinload(Member.profile)).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_family_members(
        self,
        family_id: UUID,
        limit: int = 100
    ) -> List[Member]:
        """Get all members of a family (alias for list_by_family)."""
        return await self.list_by_family(family_id, limit=limit)

    async def get_family_only_members(
        self,
        family_id: UUID,
        user_id: UUID,
        limit: int = 100,
    ) -> List[Member]:
        """Get only family-related members (exclude colleagues, friends, etc.).

        Returns members who have a family-type relationship with the user,
        plus the user's own member record ("我").
        """
        from ..models.member import MemberRelation
        from ..models.enums import FAMILY_RELATION_TYPES

        # Find the user's own member record (created_by == user_id, name == "我")
        self_stmt = select(Member).where(
            and_(
                Member.family_id == family_id,
                Member.is_deleted == False,
                Member.created_by == user_id,
                Member.name == "我",
            )
        )
        self_result = await self.session.execute(self_stmt)
        self_member = self_result.scalar_one_or_none()

        family_type_values = [rt.value for rt in FAMILY_RELATION_TYPES]

        # Find member IDs that have a family-type relation with any member in this family
        related_ids_stmt = (
            select(MemberRelation.from_member_id, MemberRelation.to_member_id)
            .where(
                and_(
                    MemberRelation.family_id == family_id,
                    MemberRelation.relation_type.in_(family_type_values),
                )
            )
        )
        rel_result = await self.session.execute(related_ids_stmt)
        rel_rows = rel_result.all()

        family_member_ids = set()
        for row in rel_rows:
            family_member_ids.add(row[0])
            family_member_ids.add(row[1])

        # Include the user's own record
        if self_member:
            family_member_ids.add(self_member.id)

        if not family_member_ids:
            # No relations found — fall back to all members
            return await self.list_by_family(family_id, limit=limit)

        stmt = (
            select(Member)
            .where(
                and_(
                    Member.family_id == family_id,
                    Member.is_deleted == False,
                    Member.id.in_(family_member_ids),
                )
            )
            .options(selectinload(Member.profile))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
