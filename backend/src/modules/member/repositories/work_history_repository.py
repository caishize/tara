"""
WorkHistory repository - Data access layer for WorkHistory entity.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.professional import WorkHistory


class WorkHistoryRepository:
    """Repository for WorkHistory CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, work_history_data: Dict[str, Any]) -> WorkHistory:
        """Create a new work history entry."""
        work_history = WorkHistory(**work_history_data)
        self.session.add(work_history)
        await self.session.flush()
        await self.session.refresh(work_history)
        return work_history

    async def get_by_id(self, work_history_id: UUID) -> Optional[WorkHistory]:
        """Get work history by ID."""
        stmt = select(WorkHistory).where(WorkHistory.id == work_history_id)
        stmt = stmt.options(selectinload(WorkHistory.member))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_member(
        self,
        member_id: UUID,
        include_past: bool = True
    ) -> List[WorkHistory]:
        """
        Get all work history entries for a member.

        Args:
            member_id: Member ID
            include_past: Include past work history (default True)
        """
        stmt = select(WorkHistory).where(WorkHistory.member_id == member_id)

        if not include_past:
            stmt = stmt.where(WorkHistory.is_current == True)

        stmt = stmt.order_by(WorkHistory.is_current.desc(), WorkHistory.start_date.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_family(
        self,
        family_id: UUID,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[WorkHistory]:
        """List all work histories in a family."""
        stmt = select(WorkHistory).where(WorkHistory.family_id == family_id)

        if filters:
            if filters.get('company_name'):
                stmt = stmt.where(WorkHistory.company_name.ilike(f"%{filters['company_name']}%"))
            if filters.get('is_current') is not None:
                stmt = stmt.where(WorkHistory.is_current == filters['is_current'])

        stmt = stmt.options(selectinload(WorkHistory.member))
        stmt = stmt.order_by(WorkHistory.is_current.desc(), WorkHistory.start_date.desc())

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_current_by_member(self, member_id: UUID) -> Optional[WorkHistory]:
        """Get current work for a member."""
        stmt = select(WorkHistory).where(
            and_(
                WorkHistory.member_id == member_id,
                WorkHistory.is_current == True
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        work_history_id: UUID,
        work_history_data: Dict[str, Any]
    ) -> Optional[WorkHistory]:
        """Update work history entry."""
        stmt = (
            update(WorkHistory)
            .where(WorkHistory.id == work_history_id)
            .values(**work_history_data)
            .returning(WorkHistory)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def delete(self, work_history_id: UUID) -> bool:
        """Delete work history entry."""
        stmt = delete(WorkHistory).where(WorkHistory.id == work_history_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def find_shared_companies(
        self,
        member_id_a: UUID,
        member_id_b: UUID
    ) -> List[str]:
        """Find companies where both members have worked."""
        stmt_a = select(WorkHistory.company_name).where(WorkHistory.member_id == member_id_a)
        stmt_b = select(WorkHistory.company_name).where(WorkHistory.member_id == member_id_b)

        result_a = await self.session.execute(stmt_a)
        result_b = await self.session.execute(stmt_b)

        companies_a = set(result_a.scalars().all())
        companies_b = set(result_b.scalars().all())

        return list(companies_a.intersection(companies_b))

    async def search_by_company(
        self,
        family_id: UUID,
        company_name: str,
        limit: int = 20
    ) -> List[WorkHistory]:
        """Search work histories by company name."""
        stmt = select(WorkHistory).where(
            and_(
                WorkHistory.family_id == family_id,
                WorkHistory.company_name.ilike(f"%{company_name}%")
            )
        ).options(selectinload(WorkHistory.member)).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
