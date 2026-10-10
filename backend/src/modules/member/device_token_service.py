"""
DeviceToken Service - CRUD for FCM device token management.

Handles registration, lookup, and deactivation of device tokens
used for push notification fallback.
"""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DeviceToken


logger = logging.getLogger(__name__)


class DeviceTokenService:
    """Service for managing FCM device tokens."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_token(
        self,
        user_id: UUID,
        fcm_token: str,
        device_type: str,
        device_name: Optional[str] = None,
        app_version: Optional[str] = None,
    ) -> DeviceToken:
        """
        Register or update a device token (upsert).

        If the token already exists, updates user_id, device info, and re-activates it.
        """
        stmt = pg_insert(DeviceToken).values(
            user_id=user_id,
            fcm_token=fcm_token,
            device_type=device_type,
            device_name=device_name,
            app_version=app_version,
            is_active=True,
        ).on_conflict_do_update(
            index_elements=["fcm_token"],
            set_={
                "user_id": user_id,
                "device_type": device_type,
                "device_name": device_name,
                "app_version": app_version,
                "is_active": True,
            },
        ).returning(DeviceToken)

        result = await self.db.execute(stmt)
        await self.db.commit()
        token = result.scalar_one()
        await self.db.refresh(token)

        logger.info(
            f"Registered device token: user={user_id}, "
            f"device_type={device_type}, device_name={device_name}"
        )
        return token

    async def get_active_tokens(self, user_id: UUID) -> List[DeviceToken]:
        """Return all active FCM tokens for a user."""
        result = await self.db.execute(
            select(DeviceToken).where(
                and_(
                    DeviceToken.user_id == user_id,
                    DeviceToken.is_active == True,
                )
            )
        )
        return list(result.scalars().all())

    async def deactivate_token(
        self,
        fcm_token: str,
        user_id: Optional[UUID] = None,
    ) -> bool:
        """
        Deactivate a specific token (logout or invalid).

        Args:
            fcm_token: The FCM token to deactivate.
            user_id: If provided, only deactivate if token belongs to this user.

        Returns True if a token was deactivated.
        """
        conditions = [DeviceToken.fcm_token == fcm_token]
        if user_id is not None:
            conditions.append(DeviceToken.user_id == user_id)

        result = await self.db.execute(
            update(DeviceToken)
            .where(and_(*conditions))
            .values(is_active=False)
        )
        await self.db.commit()

        deactivated = result.rowcount > 0
        if deactivated:
            logger.info(f"Deactivated device token: {fcm_token[:20]}...")
        return deactivated

    async def deactivate_tokens(self, fcm_tokens: List[str]) -> int:
        """
        Deactivate multiple tokens (batch cleanup for invalid tokens).

        Returns number of tokens deactivated.
        """
        if not fcm_tokens:
            return 0

        result = await self.db.execute(
            update(DeviceToken)
            .where(DeviceToken.fcm_token.in_(fcm_tokens))
            .values(is_active=False)
        )
        await self.db.commit()

        count = result.rowcount
        if count > 0:
            logger.info(f"Deactivated {count} invalid device tokens")
        return count
