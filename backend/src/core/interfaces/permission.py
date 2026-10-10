"""
IPermissionService interface.
"""
from abc import ABC, abstractmethod
from uuid import UUID
from enum import Enum


class Operation(str, Enum):
    """Member management operations."""
    CREATE_MEMBER = "CREATE_MEMBER"
    VIEW_MEMBER = "VIEW_MEMBER"
    EDIT_MEMBER = "EDIT_MEMBER"
    DELETE_MEMBER = "DELETE_MEMBER"
    VIEW_CONFIDENTIAL_INFO = "VIEW_CONFIDENTIAL_INFO"
    VIEW_RESTRICTED_INFO = "VIEW_RESTRICTED_INFO"
    CREATE_RELATION = "CREATE_RELATION"
    DELETE_RELATION = "DELETE_RELATION"


class ToolOperation(str, Enum):
    """Tool gateway operations."""
    PURCHASE = "purchase"
    BOOK_TICKET = "book_ticket"
    TRANSFER_MONEY = "transfer_money"
    SEND_MESSAGE = "send_message"
    CANCEL_BOOKING = "cancel_booking"
    CREATE_CALENDAR_EVENT = "create_calendar_event"
    RESCHEDULE_EVENT = "reschedule_event"


class SubscriptionLevel(str, Enum):
    """User subscription levels for feature gating."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class FamilyRole(str, Enum):
    """Family member roles."""
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    GUEST = "GUEST"


class IPermissionService(ABC):
    """Interface for permission checking."""

    @abstractmethod
    async def check_permission(
        self,
        user_id: UUID,
        family_id: UUID,
        module: str,
        operation: Operation,
        resource_owner_id: UUID = None
    ) -> bool:
        """
        Check if user has permission to perform operation.

        Args:
            user_id: User performing the operation
            family_id: Target family
            module: Module name (e.g., "member_management")
            operation: Operation to perform
            resource_owner_id: Owner of the resource (for CONFIDENTIAL data)

        Returns:
            True if permitted, False otherwise
        """
        pass

    @abstractmethod
    async def get_user_role(self, user_id: UUID, family_id: UUID) -> FamilyRole:
        """Get user's role in family."""
        pass
