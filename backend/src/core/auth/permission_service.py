"""
Permission service implementation.
"""
from uuid import UUID
from typing import Dict, Set

from ..interfaces.permission import IPermissionService, Operation, FamilyRole
from ...config.logging import get_logger


logger = get_logger(__name__)


class UnifiedPermissionService(IPermissionService):
    """
    Unified permission service with role-based access control.

    Permission Matrix:
    - ADMIN: All operations
    - MEMBER: VIEW_MEMBER, EDIT_MEMBER, CREATE_MEMBER, CREATE_RELATION
             VIEW_CONFIDENTIAL_INFO (own data only)
    - GUEST: VIEW_MEMBER (read-only)
    """

    # Permission matrix
    PERMISSIONS: Dict[FamilyRole, Set[Operation]] = {
        FamilyRole.ADMIN: {
            Operation.CREATE_MEMBER,
            Operation.VIEW_MEMBER,
            Operation.EDIT_MEMBER,
            Operation.DELETE_MEMBER,
            Operation.VIEW_CONFIDENTIAL_INFO,
            Operation.VIEW_RESTRICTED_INFO,
            Operation.CREATE_RELATION,
            Operation.DELETE_RELATION,
        },
        FamilyRole.MEMBER: {
            Operation.CREATE_MEMBER,
            Operation.VIEW_MEMBER,
            Operation.EDIT_MEMBER,
            Operation.DELETE_MEMBER,
            Operation.CREATE_RELATION,
            Operation.DELETE_RELATION,
            # VIEW_CONFIDENTIAL_INFO requires ownership check
        },
        FamilyRole.GUEST: {
            Operation.VIEW_MEMBER,
        },
    }

    async def check_permission(
        self,
        user_id: UUID,
        family_id: UUID,
        module: str,
        operation: Operation,
        resource_owner_id: UUID = None
    ) -> bool:
        """Check if user has permission."""
        # Get user's role in family
        role = await self.get_user_role(user_id, family_id)

        # Check permission matrix
        if operation in self.PERMISSIONS.get(role, set()):
            # Special case: MEMBER can view CONFIDENTIAL info for own data
            if operation == Operation.VIEW_CONFIDENTIAL_INFO:
                if role == FamilyRole.MEMBER:
                    is_own_data = (resource_owner_id == user_id)
                    logger.info(
                        f"Permission check: user={user_id}, operation={operation}, "
                        f"resource_owner={resource_owner_id}, is_own_data={is_own_data}"
                    )
                    return is_own_data
                elif role == FamilyRole.ADMIN:
                    return True
                else:
                    return False

            return True

        return False

    async def get_user_role(self, user_id: UUID, family_id: UUID) -> FamilyRole:
        """
        Get user's role in family.

        TODO: Implement actual role lookup from database.
        For now, mock implementation.
        """
        # Mock: Assume all users are MEMBERs for testing
        # In production, query family_members table
        return FamilyRole.MEMBER


# Global instance
permission_service = UnifiedPermissionService()
