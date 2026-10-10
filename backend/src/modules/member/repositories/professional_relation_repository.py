"""
ProfessionalRelation repository - Data access layer for ProfessionalRelation entity.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.professional import ProfessionalRelation
from ..models.enums import ProfessionalRelationType


class ProfessionalRelationRepository:
    """Repository for ProfessionalRelation CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, relation_data: Dict[str, Any]) -> ProfessionalRelation:
        """Create a new professional relation."""
        relation = ProfessionalRelation(**relation_data)
        self.session.add(relation)
        await self.session.flush()
        await self.session.refresh(relation)
        return relation

    async def create_bidirectional(
        self,
        from_id: UUID,
        to_id: UUID,
        relation_type: ProfessionalRelationType,
        family_id: UUID,
        company_name: Optional[str] = None,
        is_current: bool = True
    ) -> List[ProfessionalRelation]:
        """
        Create bidirectional professional relation.

        Returns both forward and reverse relations.
        """
        forward = await self.create({
            'family_id': family_id,
            'from_member_id': from_id,
            'to_member_id': to_id,
            'relation_type': relation_type,
            'company_name': company_name,
            'is_current': is_current
        })

        # Infer reverse relation type
        reverse_type = self._infer_reverse_relation(relation_type)

        reverse = await self.create({
            'family_id': family_id,
            'from_member_id': to_id,
            'to_member_id': from_id,
            'relation_type': reverse_type,
            'company_name': company_name,
            'is_current': is_current
        })

        return [forward, reverse]

    def _infer_reverse_relation(self, relation_type: ProfessionalRelationType) -> ProfessionalRelationType:
        """Infer reverse relation type for professional relationships."""
        reverse_map = {
            ProfessionalRelationType.BOSS: ProfessionalRelationType.SUBORDINATE,
            ProfessionalRelationType.SUBORDINATE: ProfessionalRelationType.BOSS,
            ProfessionalRelationType.PEER: ProfessionalRelationType.PEER,
            ProfessionalRelationType.MENTOR: ProfessionalRelationType.MENTEE,
            ProfessionalRelationType.MENTEE: ProfessionalRelationType.MENTOR,
            ProfessionalRelationType.CLIENT: ProfessionalRelationType.VENDOR,
            ProfessionalRelationType.VENDOR: ProfessionalRelationType.CLIENT,
            ProfessionalRelationType.PARTNER: ProfessionalRelationType.PARTNER,
        }
        return reverse_map.get(relation_type, ProfessionalRelationType.OTHER)

    async def get_by_id(self, relation_id: UUID) -> Optional[ProfessionalRelation]:
        """Get professional relation by ID."""
        stmt = select(ProfessionalRelation).where(ProfessionalRelation.id == relation_id)
        stmt = stmt.options(
            selectinload(ProfessionalRelation.from_member),
            selectinload(ProfessionalRelation.to_member)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_member(
        self,
        member_id: UUID,
        direction: str = 'both',
        include_past: bool = True
    ) -> List[ProfessionalRelation]:
        """
        Get professional relations for a member.

        Args:
            member_id: Member ID
            direction: 'outgoing', 'incoming', or 'both'
            include_past: Include past relations (default True)
        """
        if direction == 'outgoing':
            stmt = select(ProfessionalRelation).where(
                ProfessionalRelation.from_member_id == member_id
            )
        elif direction == 'incoming':
            stmt = select(ProfessionalRelation).where(
                ProfessionalRelation.to_member_id == member_id
            )
        else:  # both
            stmt = select(ProfessionalRelation).where(
                or_(
                    ProfessionalRelation.from_member_id == member_id,
                    ProfessionalRelation.to_member_id == member_id
                )
            )

        if not include_past:
            stmt = stmt.where(ProfessionalRelation.is_current == True)

        stmt = stmt.options(
            selectinload(ProfessionalRelation.from_member),
            selectinload(ProfessionalRelation.to_member)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_family(
        self,
        family_id: UUID,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ProfessionalRelation]:
        """List all professional relations in a family."""
        stmt = select(ProfessionalRelation).where(ProfessionalRelation.family_id == family_id)

        if filters:
            if filters.get('relation_type'):
                stmt = stmt.where(ProfessionalRelation.relation_type == filters['relation_type'])
            if filters.get('company_name'):
                stmt = stmt.where(ProfessionalRelation.company_name.ilike(f"%{filters['company_name']}%"))
            if filters.get('is_current') is not None:
                stmt = stmt.where(ProfessionalRelation.is_current == filters['is_current'])

        stmt = stmt.options(
            selectinload(ProfessionalRelation.from_member),
            selectinload(ProfessionalRelation.to_member)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_type(
        self,
        member_id: UUID,
        relation_type: ProfessionalRelationType
    ) -> List[ProfessionalRelation]:
        """List relations by type for a member."""
        stmt = select(ProfessionalRelation).where(
            and_(
                ProfessionalRelation.from_member_id == member_id,
                ProfessionalRelation.relation_type == relation_type
            )
        ).options(
            selectinload(ProfessionalRelation.to_member)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        relation_id: UUID,
        relation_data: Dict[str, Any]
    ) -> Optional[ProfessionalRelation]:
        """Update professional relation."""
        stmt = (
            update(ProfessionalRelation)
            .where(ProfessionalRelation.id == relation_id)
            .values(**relation_data)
            .returning(ProfessionalRelation)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def delete(self, relation_id: UUID) -> bool:
        """Delete professional relation."""
        stmt = delete(ProfessionalRelation).where(ProfessionalRelation.id == relation_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def find_by_company(
        self,
        family_id: UUID,
        company_name: str
    ) -> List[ProfessionalRelation]:
        """Find all professional relations at a specific company."""
        stmt = select(ProfessionalRelation).where(
            and_(
                ProfessionalRelation.family_id == family_id,
                ProfessionalRelation.company_name.ilike(f"%{company_name}%")
            )
        ).options(
            selectinload(ProfessionalRelation.from_member),
            selectinload(ProfessionalRelation.to_member)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_existing_relation(
        self,
        from_member_id: UUID,
        to_member_id: UUID,
        company_name: Optional[str] = None
    ) -> Optional[ProfessionalRelation]:
        """Find existing relation between two members, optionally at a specific company."""
        stmt = select(ProfessionalRelation).where(
            and_(
                ProfessionalRelation.from_member_id == from_member_id,
                ProfessionalRelation.to_member_id == to_member_id
            )
        )

        if company_name:
            stmt = stmt.where(ProfessionalRelation.company_name == company_name)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
