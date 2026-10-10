"""
Permission Validator - Validates user permissions for tool gateway actions.

Implements role-based and subscription-based permission checking with
spending limits and action-specific rules.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...config.settings import settings
from ...core.interfaces.permission import FamilyRole, SubscriptionLevel, ToolOperation


logger = logging.getLogger(__name__)


def _spending_limits_from_settings() -> Dict[SubscriptionLevel, float]:
    """Build per-transaction spending limits from settings (env vars)."""
    return {
        SubscriptionLevel.FREE: settings.spending_limit_free,
        SubscriptionLevel.BASIC: settings.spending_limit_basic,
        SubscriptionLevel.PREMIUM: settings.spending_limit_premium,
        SubscriptionLevel.ENTERPRISE: (
            float('inf') if settings.spending_limit_enterprise == 0.0
            else settings.spending_limit_enterprise
        ),
    }


def _daily_spending_limits_from_settings() -> Dict[SubscriptionLevel, float]:
    """Build daily spending limits from settings (env vars)."""
    return {
        SubscriptionLevel.FREE: settings.daily_spending_limit_free,
        SubscriptionLevel.BASIC: settings.daily_spending_limit_basic,
        SubscriptionLevel.PREMIUM: settings.daily_spending_limit_premium,
        SubscriptionLevel.ENTERPRISE: (
            float('inf') if settings.daily_spending_limit_enterprise == 0.0
            else settings.daily_spending_limit_enterprise
        ),
    }


@dataclass(frozen=True)
class PermissionCheckResult:
    """Result of a permission check."""
    allowed: bool
    reason: Optional[str] = None
    requires_confirmation: bool = False
    spending_limit_remaining: Optional[float] = None


@dataclass(frozen=True)
class PermissionRequirement:
    """Permission requirements for an operation."""
    min_role: FamilyRole
    min_subscription: SubscriptionLevel
    requires_family_admin: bool = False
    max_amount: Optional[float] = None  # For financial operations


class ToolPermissionValidator:
    """
    Validates user permissions for tool gateway actions.

    Features:
    - Role-based access control (ADMIN, MEMBER, GUEST)
    - Subscription-based feature gates
    - Spending limits per subscription tier
    - Action-specific permission rules
    """

    # Permission matrix: action -> (min_role, min_subscription)
    PERMISSION_MATRIX: Dict[str, PermissionRequirement] = {
        ToolOperation.PURCHASE.value: PermissionRequirement(
            min_role=FamilyRole.MEMBER,
            min_subscription=SubscriptionLevel.BASIC,
            max_amount=settings.purchase_max_amount,
        ),
        ToolOperation.BOOK_TICKET.value: PermissionRequirement(
            min_role=FamilyRole.MEMBER,
            min_subscription=SubscriptionLevel.BASIC,
        ),
        ToolOperation.TRANSFER_MONEY.value: PermissionRequirement(
            min_role=FamilyRole.ADMIN,
            min_subscription=SubscriptionLevel.PREMIUM,
            requires_family_admin=True,
            max_amount=settings.transfer_max_amount,
        ),
        ToolOperation.SEND_MESSAGE.value: PermissionRequirement(
            min_role=FamilyRole.MEMBER,
            min_subscription=SubscriptionLevel.FREE,  # Available to all
        ),
        ToolOperation.CANCEL_BOOKING.value: PermissionRequirement(
            min_role=FamilyRole.MEMBER,
            min_subscription=SubscriptionLevel.BASIC,
        ),
        ToolOperation.CREATE_CALENDAR_EVENT.value: PermissionRequirement(
            min_role=FamilyRole.MEMBER,
            min_subscription=SubscriptionLevel.FREE,  # Available to all
        ),
        ToolOperation.RESCHEDULE_EVENT.value: PermissionRequirement(
            min_role=FamilyRole.GUEST,  # Non-financial; GUEST until role fetch is implemented
            min_subscription=SubscriptionLevel.FREE,
        ),
    }

    @staticmethod
    def _get_spending_limits() -> Dict[SubscriptionLevel, float]:
        """Per-transaction spending limits from env-driven settings."""
        return _spending_limits_from_settings()

    @staticmethod
    def _get_daily_spending_limits() -> Dict[SubscriptionLevel, float]:
        """Daily spending limits from env-driven settings."""
        return _daily_spending_limits_from_settings()

    @staticmethod
    def _get_confirmation_threshold() -> float:
        """Amount threshold (¥) above which user confirmation is required."""
        return settings.confirmation_amount_threshold

    # Role hierarchy for permission checking
    ROLE_HIERARCHY: Dict[FamilyRole, int] = {
        FamilyRole.GUEST: 0,
        FamilyRole.MEMBER: 1,
        FamilyRole.ADMIN: 2,
    }

    # Subscription hierarchy
    SUBSCRIPTION_HIERARCHY: Dict[SubscriptionLevel, int] = {
        SubscriptionLevel.FREE: 0,
        SubscriptionLevel.BASIC: 1,
        SubscriptionLevel.PREMIUM: 2,
        SubscriptionLevel.ENTERPRISE: 3,
    }

    async def check_permission(
        self,
        user_id: str,
        family_id: str,
        action_type: str,
        payload: Dict[str, Any],
        user_role: Optional[FamilyRole] = None,
        subscription_level: Optional[SubscriptionLevel] = None,
        daily_spent: float = 0.0,
    ) -> PermissionCheckResult:
        """
        Check if user has permission to perform an action.

        Args:
            user_id: The user ID
            family_id: The family ID
            action_type: The action being performed
            payload: Action parameters (may include amount)
            user_role: User's role in the family (if known)
            subscription_level: User's subscription level (if known)
            daily_spent: Amount already spent today

        Returns:
            PermissionCheckResult indicating if action is allowed
        """
        # Get permission requirements for this action
        requirement = self.PERMISSION_MATRIX.get(action_type)

        if not requirement:
            # Unknown action type - deny by default
            logger.warning("Unknown action type: %s", action_type)
            return PermissionCheckResult(
                allowed=False,
                reason=f"Unknown action type: {action_type}",
            )

        # Default to most restrictive if not provided
        if user_role is None:
            user_role = FamilyRole.GUEST
        if subscription_level is None:
            subscription_level = SubscriptionLevel.FREE

        # Check role requirement
        role_check = self._check_role_requirement(user_role, requirement.min_role)
        if not role_check.allowed:
            return role_check

        # Check subscription requirement
        sub_check = self._check_subscription_requirement(
            subscription_level, requirement.min_subscription
        )
        if not sub_check.allowed:
            return sub_check

        # Check family admin requirement
        if requirement.requires_family_admin:
            if user_role != FamilyRole.ADMIN:
                return PermissionCheckResult(
                    allowed=False,
                    reason="This operation requires family admin privileges",
                )

        # Check spending limits for financial operations
        amount = self._extract_amount(payload)
        if amount is not None and amount < 0:
            return PermissionCheckResult(
                allowed=False,
                reason="Negative amounts are not allowed",
            )
        if amount is not None and amount > 0:
            spending_check = self._check_spending_limits(
                amount=amount,
                subscription_level=subscription_level,
                requirement=requirement,
                daily_spent=daily_spent,
            )
            if not spending_check.allowed:
                return spending_check

        # All checks passed
        remaining_daily = self._get_daily_spending_limits().get(
            subscription_level, 0.0
        ) - daily_spent

        return PermissionCheckResult(
            allowed=True,
            requires_confirmation=self._requires_confirmation(action_type, payload),
            spending_limit_remaining=remaining_daily if remaining_daily != float('inf') else None,
        )

    def _check_role_requirement(
        self,
        user_role: FamilyRole,
        required_role: FamilyRole,
    ) -> PermissionCheckResult:
        """Check if user's role meets the minimum requirement."""
        user_level = self.ROLE_HIERARCHY.get(user_role, 0)
        required_level = self.ROLE_HIERARCHY.get(required_role, 0)

        if user_level < required_level:
            return PermissionCheckResult(
                allowed=False,
                reason=f"Requires {required_role.value} role or higher",
            )

        return PermissionCheckResult(allowed=True)

    def _check_subscription_requirement(
        self,
        subscription: SubscriptionLevel,
        required_subscription: SubscriptionLevel,
    ) -> PermissionCheckResult:
        """Check if user's subscription meets the minimum requirement."""
        user_level = self.SUBSCRIPTION_HIERARCHY.get(subscription, 0)
        required_level = self.SUBSCRIPTION_HIERARCHY.get(required_subscription, 0)

        if user_level < required_level:
            return PermissionCheckResult(
                allowed=False,
                reason=f"Requires {required_subscription.value} subscription or higher",
            )

        return PermissionCheckResult(allowed=True)

    def _check_spending_limits(
        self,
        amount: float,
        subscription_level: SubscriptionLevel,
        requirement: PermissionRequirement,
        daily_spent: float,
    ) -> PermissionCheckResult:
        """Check spending limits for financial operations."""
        # Check per-transaction limit from subscription
        per_tx_limit = self._get_spending_limits().get(subscription_level, 0.0)
        if amount > per_tx_limit:
            return PermissionCheckResult(
                allowed=False,
                reason=f"Amount ¥{amount} exceeds per-transaction limit of ¥{per_tx_limit}",
            )

        # Check action-specific limit
        if requirement.max_amount is not None and amount > requirement.max_amount:
            return PermissionCheckResult(
                allowed=False,
                reason=f"Amount ¥{amount} exceeds action limit of ¥{requirement.max_amount}",
            )

        # Check daily limit
        daily_limit = self._get_daily_spending_limits().get(subscription_level, 0.0)
        if daily_spent + amount > daily_limit:
            remaining = daily_limit - daily_spent
            return PermissionCheckResult(
                allowed=False,
                reason=f"Daily spending limit reached. Remaining: ¥{max(0, remaining)}",
                spending_limit_remaining=max(0, remaining),
            )

        return PermissionCheckResult(allowed=True)

    @staticmethod
    def _extract_amount(payload: Dict[str, Any]) -> Optional[float]:
        """Extract monetary amount from payload."""
        from .payload_utils import extract_amount
        return extract_amount(payload)

    def _requires_confirmation(
        self,
        action_type: str,
        payload: Dict[str, Any],
    ) -> bool:
        """Determine if action requires user confirmation."""
        # Financial operations always require confirmation
        financial_ops = {
            ToolOperation.PURCHASE.value,
            ToolOperation.BOOK_TICKET.value,
            ToolOperation.TRANSFER_MONEY.value,
        }

        if action_type in financial_ops:
            return True

        # Large amounts require confirmation
        amount = self._extract_amount(payload)
        if amount is not None and amount > self._get_confirmation_threshold():
            return True

        return False

    def get_user_limits(
        self,
        subscription_level: SubscriptionLevel,
    ) -> Dict[str, Any]:
        """Get spending limits for a subscription level."""
        return {
            "per_transaction": self._get_spending_limits().get(subscription_level, 0.0),
            "daily": self._get_daily_spending_limits().get(subscription_level, 0.0),
            "subscription": subscription_level.value,
        }
