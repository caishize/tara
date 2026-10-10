"""
WorkHistoryService - Business logic for work history management.
"""
from datetime import date
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .repositories.work_history_repository import WorkHistoryRepository
from .repositories.member_repository import MemberRepository
from ...core.auth.permission_service import permission_service
from ...core.interfaces.permission import Operation
from ...config.logging import get_logger


logger = get_logger(__name__)


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Convert string date to Python date object."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


class WorkHistoryService:
    """Work history management business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.work_history_repo = WorkHistoryRepository(session)
        self.member_repo = MemberRepository(session)

    async def create_work_history(
        self,
        member_id: UUID,
        work_history_data: Dict[str, Any],
        requester_id: UUID
    ) -> Dict[str, Any]:
        """
        Create a new work history entry for a member.

        Args:
            member_id: Member UUID
            work_history_data: Work history data
            requester_id: User creating the entry

        Returns:
            Created work history data
        """
        # Get member to verify access
        member = await self.member_repo.get_by_id(member_id)
        if not member:
            raise ValueError("Member not found")

        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            member.family_id,
            "member_management",
            Operation.EDIT_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to edit member work history")

        # Add metadata
        work_history_data['member_id'] = member_id
        work_history_data['family_id'] = member.family_id

        # Convert string dates to Python date objects (asyncpg requires date objects)
        if 'start_date' in work_history_data:
            work_history_data['start_date'] = _parse_date(work_history_data['start_date'])
        if 'end_date' in work_history_data:
            work_history_data['end_date'] = _parse_date(work_history_data['end_date'])

        # Create work history
        work_history = await self.work_history_repo.create(work_history_data)

        logger.info(f"Work history created: {work_history.id} for member {member_id}")

        return self._to_dict(work_history)

    async def get_work_history(
        self,
        work_history_id: UUID,
        requester_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get work history by ID."""
        work_history = await self.work_history_repo.get_by_id(work_history_id)
        if not work_history:
            return None

        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            work_history.family_id,
            "member_management",
            Operation.VIEW_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to view work history")

        return self._to_dict(work_history)

    async def list_work_history(
        self,
        member_id: UUID,
        requester_id: UUID,
        include_past: bool = True
    ) -> List[Dict[str, Any]]:
        """List all work history for a member."""
        # Get member to verify access
        member = await self.member_repo.get_by_id(member_id)
        if not member:
            raise ValueError("Member not found")

        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            member.family_id,
            "member_management",
            Operation.VIEW_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to view work history")

        work_histories = await self.work_history_repo.list_by_member(member_id, include_past)

        return [self._to_dict(wh) for wh in work_histories]

    async def update_work_history(
        self,
        work_history_id: UUID,
        updates: Dict[str, Any],
        requester_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Update work history entry."""
        work_history = await self.work_history_repo.get_by_id(work_history_id)
        if not work_history:
            return None

        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            work_history.family_id,
            "member_management",
            Operation.EDIT_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to edit work history")

        # Convert string dates to Python date objects (asyncpg requires date objects)
        if 'start_date' in updates:
            updates['start_date'] = _parse_date(updates['start_date'])
        if 'end_date' in updates:
            updates['end_date'] = _parse_date(updates['end_date'])

        # Update work history
        updated = await self.work_history_repo.update(work_history_id, updates)

        logger.info(f"Work history updated: {work_history_id}")

        return self._to_dict(updated) if updated else None

    async def delete_work_history(
        self,
        work_history_id: UUID,
        requester_id: UUID
    ) -> bool:
        """Delete work history entry."""
        work_history = await self.work_history_repo.get_by_id(work_history_id)
        if not work_history:
            return False

        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            work_history.family_id,
            "member_management",
            Operation.EDIT_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to delete work history")

        result = await self.work_history_repo.delete(work_history_id)

        logger.info(f"Work history deleted: {work_history_id}")

        return result

    async def search_by_company(
        self,
        family_id: UUID,
        company_name: str,
        requester_id: UUID
    ) -> List[Dict[str, Any]]:
        """Search work histories by company name."""
        # Check permission
        has_permission = await permission_service.check_permission(
            requester_id,
            family_id,
            "member_management",
            Operation.VIEW_MEMBER
        )
        if not has_permission:
            raise PermissionError("User does not have permission to search work history")

        work_histories = await self.work_history_repo.search_by_company(family_id, company_name)

        return [self._to_dict(wh) for wh in work_histories]

    def _to_dict(self, work_history) -> Dict[str, Any]:
        """Convert WorkHistory model to dict."""
        return {
            'id': str(work_history.id),
            'member_id': str(work_history.member_id),
            'family_id': str(work_history.family_id),
            'company_name': work_history.company_name,
            'position': work_history.position,
            'department': work_history.department,
            'start_date': work_history.start_date.isoformat() if work_history.start_date else None,
            'end_date': work_history.end_date.isoformat() if work_history.end_date else None,
            'is_current': work_history.is_current,
            'notes': work_history.notes,
            'created_at': work_history.created_at.isoformat(),
            'updated_at': work_history.updated_at.isoformat(),
        }
