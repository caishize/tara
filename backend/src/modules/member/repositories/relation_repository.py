"""
MemberRelation repository - Data access layer.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.member import MemberRelation
from ..models.enums import RelationType


class RelationRepository:
    """Repository for MemberRelation CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, relation_data: Dict[str, Any]) -> MemberRelation:
        """Create a new relation."""
        relation = MemberRelation(**relation_data)
        self.session.add(relation)
        await self.session.flush()
        await self.session.refresh(relation)
        return relation

    async def create_bidirectional(
        self,
        from_id: UUID,
        to_id: UUID,
        relation_type: RelationType,
        intimacy_level: int = 5,
        family_id: UUID = None
    ) -> List[MemberRelation]:
        """
        Create bidirectional relation (e.g., spouse, sibling).

        Returns both forward and reverse relations.
        """
        forward = await self.create({
            'family_id': family_id,
            'from_member_id': from_id,
            'to_member_id': to_id,
            'relation_type': relation_type,
            'intimacy_level': intimacy_level
        })

        # Infer reverse relation type
        reverse_type = self._infer_reverse_relation(relation_type)

        reverse = await self.create({
            'family_id': family_id,
            'from_member_id': to_id,
            'to_member_id': from_id,
            'relation_type': reverse_type,
            'intimacy_level': intimacy_level
        })

        return [forward, reverse]

    def _infer_reverse_relation(self, relation_type: RelationType) -> RelationType:
        """Infer reverse relation type."""
        reverse_map = {
            RelationType.SPOUSE: RelationType.SPOUSE,
            RelationType.PARENT: RelationType.CHILD,
            RelationType.CHILD: RelationType.PARENT,
            RelationType.SIBLING: RelationType.SIBLING,
            RelationType.GRANDPARENT: RelationType.GRANDCHILD,
            RelationType.GRANDCHILD: RelationType.GRANDPARENT,
            RelationType.UNCLE_AUNT: RelationType.NEPHEW_NIECE,
            RelationType.NEPHEW_NIECE: RelationType.UNCLE_AUNT,
            RelationType.COUSIN: RelationType.COUSIN,
        }
        return reverse_map.get(relation_type, RelationType.OTHER)

    async def get_by_id(self, relation_id: UUID) -> Optional[MemberRelation]:
        """Get relation by ID."""
        stmt = select(MemberRelation).where(MemberRelation.id == relation_id)
        stmt = stmt.options(
            selectinload(MemberRelation.from_member),
            selectinload(MemberRelation.to_member)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_member(
        self,
        member_id: UUID,
        direction: str = 'both'
    ) -> List[MemberRelation]:
        """
        Get member's relations.

        Args:
            member_id: Member ID
            direction: 'outgoing', 'incoming', or 'both'
        """
        if direction == 'outgoing':
            stmt = select(MemberRelation).where(
                MemberRelation.from_member_id == member_id
            )
        elif direction == 'incoming':
            stmt = select(MemberRelation).where(
                MemberRelation.to_member_id == member_id
            )
        else:  # both
            stmt = select(MemberRelation).where(
                or_(
                    MemberRelation.from_member_id == member_id,
                    MemberRelation.to_member_id == member_id
                )
            )

        stmt = stmt.options(
            selectinload(MemberRelation.from_member),
            selectinload(MemberRelation.to_member)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_family(
        self,
        family_id: UUID,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemberRelation]:
        """List all relations in a family."""
        stmt = select(MemberRelation).where(MemberRelation.family_id == family_id)

        if filters and filters.get('relation_type'):
            stmt = stmt.where(MemberRelation.relation_type == filters['relation_type'])

        stmt = stmt.options(
            selectinload(MemberRelation.from_member),
            selectinload(MemberRelation.to_member)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        relation_id: UUID,
        relation_data: Dict[str, Any]
    ) -> Optional[MemberRelation]:
        """Update relation properties."""
        stmt = (
            update(MemberRelation)
            .where(MemberRelation.id == relation_id)
            .values(**relation_data)
            .returning(MemberRelation)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def delete(self, relation_id: UUID) -> bool:
        """Delete relation."""
        stmt = delete(MemberRelation).where(MemberRelation.id == relation_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def get_relation_graph(
        self,
        member_id: UUID,
        max_degree: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get multi-degree relation graph using recursive CTE.

        Returns list of {member_id, degree, path}.
        """
        # SQL recursive CTE query
        query = f"""
        WITH RECURSIVE relation_graph AS (
            -- Base case: direct relations
            SELECT
                CASE
                    WHEN from_member_id = '{member_id}' THEN to_member_id
                    ELSE from_member_id
                END as member_id,
                relation_type,
                1 as degree,
                ARRAY['{member_id}', CASE
                    WHEN from_member_id = '{member_id}' THEN CAST(to_member_id AS TEXT)
                    ELSE CAST(from_member_id AS TEXT)
                END] as path
            FROM member_relations
            WHERE from_member_id = '{member_id}' OR to_member_id = '{member_id}'

            UNION ALL

            -- Recursive case
            SELECT
                CASE
                    WHEN mr.from_member_id = rg.member_id THEN mr.to_member_id
                    ELSE mr.from_member_id
                END as member_id,
                mr.relation_type,
                rg.degree + 1,
                rg.path || CASE
                    WHEN mr.from_member_id = rg.member_id THEN CAST(mr.to_member_id AS TEXT)
                    ELSE CAST(mr.from_member_id AS TEXT)
                END
            FROM member_relations mr
            INNER JOIN relation_graph rg
                ON mr.from_member_id = rg.member_id OR mr.to_member_id = rg.member_id
            WHERE rg.degree < {max_degree}
                AND NOT (CASE
                    WHEN mr.from_member_id = rg.member_id THEN CAST(mr.to_member_id AS TEXT)
                    ELSE CAST(mr.from_member_id AS TEXT)
                END = ANY(rg.path))
        )
        SELECT DISTINCT member_id, MIN(degree) as degree
        FROM relation_graph
        GROUP BY member_id
        ORDER BY degree, member_id
        """

        result = await self.session.execute(query)
        rows = result.fetchall()

        return [{'member_id': str(row[0]), 'degree': row[1]} for row in rows]
