"""
PendingAction Service - Business logic for action confirmation flow.

Handles the lifecycle of pending actions:
1. Create: Agent generates action
2. Confirm/Reject: User decides
3. Execute: Tool Gateway performs action
4. Expire: Cleanup stale actions
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.utils.timezone import utc_now
from .pending_action import (
    PendingAction,
    ActionStatus,
    ActionType,
)


logger = logging.getLogger(__name__)


class PendingActionError(Exception):
    """Base exception for pending action errors."""
    pass


class ActionNotFoundError(PendingActionError):
    """Action not found."""
    pass


class ActionExpiredError(PendingActionError):
    """Action has expired."""
    pass


class ActionAlreadyProcessedError(PendingActionError):
    """Action has already been processed."""
    pass


class PendingActionService:
    """
    Service for managing pending action lifecycle.

    Usage:
        service = PendingActionService(db)

        # Create action (from AgentWorker)
        action = await service.create(
            user_id=user_id,
            family_id=family_id,
            action_type=ActionType.PURCHASE,
            payload={"item": "滤芯", "price": 129},
            display_data={"title": "确认购买", "details": [...]},
        )

        # Confirm action (from API)
        action = await service.confirm(action_id, user_id)

        # Execute action (from API or worker)
        result = await service.execute(action_id)
    """

    # Default TTL for pending actions
    DEFAULT_TTL_MINUTES = 15

    def __init__(self, db: AsyncSession):
        self.db = db
        self._tool_gateway = None

    @property
    def tool_gateway(self):
        """Lazy-load tool gateway."""
        if self._tool_gateway is None:
            from ...ai_engine.gateway import ToolGateway
            self._tool_gateway = ToolGateway()
        return self._tool_gateway

    async def create(
        self,
        user_id: UUID,
        family_id: UUID,
        action_type: str,
        payload: Dict[str, Any],
        display_data: Optional[Dict[str, Any]] = None,
        job_id: Optional[UUID] = None,
        ttl_minutes: int = DEFAULT_TTL_MINUTES,
    ) -> PendingAction:
        """
        Create a new pending action.

        Args:
            user_id: User who will confirm the action
            family_id: Family ID
            action_type: Type of action
            payload: Action parameters
            display_data: Human-readable display data
            job_id: Optional job ID from agent task
            ttl_minutes: Time until expiration

        Returns:
            Created PendingAction
        """
        expires_at = utc_now() + timedelta(minutes=ttl_minutes)

        action = PendingAction(
            user_id=user_id,
            family_id=family_id,
            job_id=job_id,
            action_type=action_type,
            payload=payload,
            display_data=display_data or {},
            status=ActionStatus.PENDING.value,
            expires_at=expires_at,
        )

        self.db.add(action)
        await self.db.commit()
        await self.db.refresh(action)

        logger.info(
            f"Created pending action: id={action.id}, type={action_type}, "
            f"user={user_id}, expires={expires_at}"
        )

        return action

    async def get(
        self,
        action_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[PendingAction]:
        """
        Get a pending action by ID.

        Args:
            action_id: Action ID
            user_id: Optional user ID for authorization

        Returns:
            PendingAction if found
        """
        query = select(PendingAction).where(PendingAction.id == action_id)

        if user_id:
            query = query.where(PendingAction.user_id == user_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_pending(
        self,
        user_id: UUID,
        limit: int = 20,
    ) -> List[PendingAction]:
        """
        List pending actions for a user.

        Returns only non-expired pending actions.
        """
        now = utc_now()

        result = await self.db.execute(
            select(PendingAction)
            .where(
                and_(
                    PendingAction.user_id == user_id,
                    PendingAction.status == ActionStatus.PENDING.value,
                    PendingAction.expires_at > now,
                )
            )
            .order_by(PendingAction.created_at.desc())
            .limit(limit)
        )

        return list(result.scalars().all())

    async def confirm(
        self,
        action_id: UUID,
        user_id: UUID,
    ) -> PendingAction:
        """
        Confirm a pending action.

        Args:
            action_id: Action to confirm
            user_id: User confirming (must match action's user_id)

        Returns:
            Updated PendingAction

        Raises:
            ActionNotFoundError: Action not found
            ActionExpiredError: Action has expired
            ActionAlreadyProcessedError: Action already processed
        """
        action = await self.get(action_id, user_id)

        if not action:
            raise ActionNotFoundError(f"Action {action_id} not found")

        if action.is_expired:
            # Update status to expired
            action.status = ActionStatus.EXPIRED.value
            await self.db.commit()
            raise ActionExpiredError(f"Action {action_id} has expired")

        if action.status != ActionStatus.PENDING.value:
            raise ActionAlreadyProcessedError(
                f"Action {action_id} already {action.status}"
            )

        # Update to confirmed
        action.status = ActionStatus.CONFIRMED.value
        action.confirmed_at = utc_now()
        await self.db.commit()
        await self.db.refresh(action)

        logger.info(f"Confirmed action: id={action_id}, user={user_id}")

        return action

    async def reject(
        self,
        action_id: UUID,
        user_id: UUID,
    ) -> PendingAction:
        """
        Reject a pending action.

        Args:
            action_id: Action to reject
            user_id: User rejecting

        Returns:
            Updated PendingAction
        """
        action = await self.get(action_id, user_id)

        if not action:
            raise ActionNotFoundError(f"Action {action_id} not found")

        if action.status != ActionStatus.PENDING.value:
            raise ActionAlreadyProcessedError(
                f"Action {action_id} already {action.status}"
            )

        action.status = ActionStatus.REJECTED.value
        await self.db.commit()
        await self.db.refresh(action)

        logger.info(f"Rejected action: id={action_id}, user={user_id}")

        return action

    async def execute(
        self,
        action_id: UUID,
        internal_token: Optional[str] = None,
        payload_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a confirmed action via Tool Gateway.

        Args:
            action_id: Action to execute
            internal_token: Optional internal JWT for gateway auth
            payload_overrides: Optional dict to merge into payload before execution

        Returns:
            Execution result

        Raises:
            ActionNotFoundError: Action not found
            ActionAlreadyProcessedError: Action not in confirmed status
        """
        action = await self.get(action_id)

        if not action:
            raise ActionNotFoundError(f"Action {action_id} not found")

        if action.status != ActionStatus.CONFIRMED.value:
            raise ActionAlreadyProcessedError(
                f"Action {action_id} cannot be executed (status: {action.status})"
            )

        try:
            # Merge overrides into payload (e.g. user-chosen new_start/new_end)
            payload = {**action.payload, **(payload_overrides or {})}

            # suggest_* actions are soft suggestions (draft messages).
            # They don't require external execution — just mark as executed
            # and return the draft content for the user to send manually.
            if action.action_type.startswith("suggest_"):
                result = {
                    "status": "completed",
                    "action_type": action.action_type,
                    "draft_content": action.draft_content or "",
                    "message": "建议已确认，请手动发送消息给对方",
                }
            else:
                # Execute via Tool Gateway
                result = await self.tool_gateway.execute(
                    action_type=action.action_type,
                    payload=payload,
                    user_id=str(action.user_id),
                    trace_id=str(action.job_id) if action.job_id else str(action.id),
                )

            # Update action with result
            action.status = ActionStatus.EXECUTED.value
            action.executed_at = utc_now()
            action.execution_result = result
            await self.db.commit()

            logger.info(
                f"Executed action: id={action_id}, type={action.action_type}"
            )

            return result

        except Exception as e:
            # Update action with error
            action.status = ActionStatus.FAILED.value
            action.error_message = str(e)
            await self.db.commit()

            logger.error(f"Action execution failed: id={action_id}, error={e}")
            raise

    async def confirm_and_execute(
        self,
        action_id: UUID,
        user_id: UUID,
        payload_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Confirm and immediately execute an action.

        Convenience method for atomic confirm + execute.

        Args:
            action_id: Action to confirm and execute
            user_id: User confirming
            payload_overrides: Optional dict to merge into payload before execution
        """
        await self.confirm(action_id, user_id)
        return await self.execute(action_id, payload_overrides=payload_overrides)

    async def expire_stale(self) -> int:
        """
        Mark expired pending actions.

        Should be called periodically (e.g., every minute).

        Returns:
            Number of actions expired
        """
        now = utc_now()

        result = await self.db.execute(
            update(PendingAction)
            .where(
                and_(
                    PendingAction.status == ActionStatus.PENDING.value,
                    PendingAction.expires_at <= now,
                )
            )
            .values(status=ActionStatus.EXPIRED.value)
        )
        await self.db.commit()

        count = result.rowcount
        if count > 0:
            logger.info(f"Expired {count} pending actions")

        return count
