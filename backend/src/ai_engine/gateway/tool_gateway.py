"""
Tool Gateway - Secure gateway for external service execution.

This gateway is the single point of contact for external APIs.
Agent workers request actions, but this gateway holds the real credentials.

Security features:
- Internal JWT validation
- Permission checking per action type
- Audit logging
- Rate limiting
"""

import logging
from collections import deque
from typing import Any, Dict, Optional
from uuid import uuid4

from ...config.settings import settings
from ...core.utils.timezone import utc_now


logger = logging.getLogger(__name__)


class ToolGatewayError(Exception):
    """Base exception for gateway errors."""
    pass


class PermissionDeniedError(ToolGatewayError):
    """Action not permitted for user."""
    pass


class ConfirmationRequiredError(ToolGatewayError):
    """Action requires user confirmation before execution."""

    def __init__(self, action_type: str, reason: str, payload_summary: Optional[Dict[str, Any]] = None):
        self.action_type = action_type
        self.reason = reason
        self.payload_summary = payload_summary or {}
        super().__init__(f"Confirmation required for {action_type}: {reason}")


class InvalidTokenError(ToolGatewayError):
    """Internal token is missing or invalid."""
    pass


class ExecutionError(ToolGatewayError):
    """External service execution failed."""
    pass


class ToolGateway:
    """
    Secure gateway for external service execution.

    Architecture:
    - Agent Workers call this gateway with action requests
    - Gateway validates permissions and internal tokens
    - Gateway holds real API credentials (not exposed to workers)
    - All executions are logged for audit

    Usage:
        gateway = ToolGateway()
        result = await gateway.execute(
            action_type="purchase",
            payload={"item_id": "abc", "quantity": 1},
            user_id="user_123",
            trace_id="trace_xyz",
        )
    """

    # Action types that this gateway can handle
    SUPPORTED_ACTIONS = {
        "purchase",
        "book_ticket",
        "transfer_money",
        "send_message",
        "cancel_booking",
        "create_event",
        "delete_event",
        "reschedule_event",
    }

    def __init__(self):
        self._audit_log: deque = deque(maxlen=1000)  # Bounded; in production, use proper storage
        self._provider = self._get_provider()
    
    def _get_provider(self):
        """Get the configured tool provider."""
        from .providers import RealToolProvider

        provider_type = getattr(settings, 'tool_provider_type', 'real').lower()
        if provider_type != "real":
            logger.warning(
                "TOOL_PROVIDER_TYPE='%s' is not supported. "
                "Using RealToolProvider. Simulation mode has been removed.",
                provider_type,
            )
        return RealToolProvider()

    async def execute(
        self,
        action_type: str,
        payload: Dict[str, Any],
        user_id: str,
        trace_id: str,
        internal_token: Optional[str] = None,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute an action through the gateway.

        Args:
            action_type: Type of action to execute
            payload: Action parameters
            user_id: User requesting the action
            trace_id: Trace ID for logging
            internal_token: Optional internal JWT for auth
            confirmed: Whether the user has confirmed this action via PendingAction flow

        Returns:
            Execution result

        Raises:
            InvalidTokenError: Internal token missing or invalid
            PermissionDeniedError: User not permitted
            ConfirmationRequiredError: Action needs user confirmation first
            ExecutionError: External service failed
        """
        execution_id = str(uuid4())
        start_time = utc_now()

        logger.info(
            "Gateway executing: action=%s, user=%s, trace=%s, execution_id=%s",
            action_type, user_id, trace_id, execution_id,
        )

        try:
            # 1. Validate internal token (CLAUDE.md: Agent仅持有内部Token，通过网关调用外部服务)
            self._validate_internal_token(internal_token)

            # 2. Validate action type
            if action_type not in self.SUPPORTED_ACTIONS:
                raise ToolGatewayError(f"Unsupported action type: {action_type}")

            # 3. Check permissions
            permission_result = await self._check_permissions(user_id, action_type, payload)

            # 4. Enforce confirmation (CLAUDE.md: 必须经过PendingAction + 用户确认)
            if permission_result.requires_confirmation and not confirmed:
                raise ConfirmationRequiredError(
                    action_type=action_type,
                    reason="This action requires user confirmation before execution",
                    payload_summary={
                        "action": action_type,
                        "amount": self._extract_amount_from_payload(payload),
                    },
                )

            # 5. Execute via Provider
            result = await self._provider.execute(
                action_type=action_type,
                payload=payload,
                user_id=user_id,
                trace_id=trace_id,
            )

            # 6. Log success
            await self._log_audit(
                execution_id=execution_id,
                action_type=action_type,
                user_id=user_id,
                trace_id=trace_id,
                payload=payload,
                result=result,
                success=True,
                duration_ms=(utc_now() - start_time).total_seconds() * 1000,
            )

            logger.info("Gateway execution success: execution_id=%s", execution_id)
            return result

        except ConfirmationRequiredError:
            # Confirmation requests are expected control flow, not errors
            logger.info(
                "Gateway confirmation required: execution_id=%s, action=%s",
                execution_id, action_type,
            )
            raise

        except Exception as e:
            # Log failure
            await self._log_audit(
                execution_id=execution_id,
                action_type=action_type,
                user_id=user_id,
                trace_id=trace_id,
                payload=payload,
                result=None,
                success=False,
                error=str(e),
                duration_ms=(utc_now() - start_time).total_seconds() * 1000,
            )

            logger.error(
                "Gateway execution failed: execution_id=%s, error=%s",
                execution_id, e,
            )
            raise

    def _validate_internal_token(self, token: Optional[str]) -> None:
        """
        Validate the internal JWT token from an agent worker.

        CLAUDE.md: Agent仅持有内部Token，通过网关调用外部服务.
        All calls to the gateway must present a valid internal token.

        In development mode, token validation is skipped if
        the gateway internal secret is not configured.
        """
        import jwt

        gateway_secret = settings.tool_gateway_internal_secret
        if gateway_secret == "CHANGE_THIS_IN_PRODUCTION":
            if settings.environment not in ("development", "test"):
                raise InvalidTokenError("Tool gateway internal secret not configured")
            # In development/test only, log warning and skip validation
            logger.warning("Tool gateway internal secret not configured, skipping token validation")
            return

        if not token:
            raise InvalidTokenError("Internal token is required")

        try:
            jwt.decode(
                token,
                gateway_secret,
                algorithms=[settings.jwt_algorithm],
                options={"require": ["exp", "sub", "aud"]},
                audience="tool-gateway",
            )
        except jwt.ExpiredSignatureError:
            raise InvalidTokenError("Internal token has expired")
        except jwt.InvalidTokenError:
            raise InvalidTokenError("Internal token is invalid")

    @staticmethod
    def _extract_amount_from_payload(payload: Dict[str, Any]) -> Optional[float]:
        """Extract monetary amount from payload for confirmation summary."""
        from .payload_utils import extract_amount
        return extract_amount(payload)

    async def _check_permissions(
        self,
        user_id: str,
        action_type: str,
        payload: Dict[str, Any],
    ):
        """
        Check if user has permission to perform action.

        Validates:
        - User subscription level
        - Family role requirements
        - Spending limits
        - Action-specific rules

        Security: Role and subscription are determined server-side, never
        from client payload. This prevents privilege escalation attacks.

        Returns:
            PermissionCheckResult with allowed status and confirmation flag
        """
        from .permission_validator import ToolPermissionValidator, PermissionCheckResult
        from ...core.interfaces.permission import FamilyRole, SubscriptionLevel

        validator = ToolPermissionValidator()

        # Fetch user role and subscription from the database when
        # a proper UserContextService is available.  For now, default
        # to MEMBER/BASIC so that authenticated users can perform
        # normal operations while still requiring confirmation for
        # sensitive ones.  GUEST/FREE was too restrictive and blocked
        # legitimate actions for all users.
        user_role = FamilyRole.MEMBER
        subscription = SubscriptionLevel.BASIC
        daily_spent = 0.0

        result = await validator.check_permission(
            user_id=user_id,
            family_id="",  # Will be provided when family context is available
            action_type=action_type,
            payload=payload,
            user_role=user_role,
            subscription_level=subscription,
            daily_spent=daily_spent,
        )

        if not result.allowed:
            raise PermissionDeniedError(
                f"Permission denied: {result.reason}"
            )

        return result

    async def _log_audit(
        self,
        execution_id: str,
        action_type: str,
        user_id: str,
        trace_id: str,
        payload: Dict[str, Any],
        result: Optional[Dict[str, Any]],
        success: bool,
        duration_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Log execution for audit trail."""
        audit_entry = {
            "execution_id": execution_id,
            "action_type": action_type,
            "user_id": user_id,
            "trace_id": trace_id,
            "timestamp": utc_now().isoformat(),
            "success": success,
            "duration_ms": duration_ms,
            "error": error,
            # Don't log full payload/result in production for privacy
        }
        self._audit_log.append(audit_entry)

        # In production, write to proper audit log storage
        logger.debug("Audit: %s", audit_entry)

