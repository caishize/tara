"""Devices API routes - /api/v1/devices/*

Push notification device token management.

Endpoints:
    POST   /devices/        - Register device token
    DELETE /devices/{token} - Unregister device token (on logout)
"""

import logging
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import get_current_user
from ...db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])


# --- Request / Response schemas ---

class RegisterDeviceRequest(BaseModel):
    """Register a device for push notifications."""
    token: str = Field(..., min_length=1, max_length=500, description="FCM or APNs token")
    platform: Literal["ios", "android"] = Field(..., description="Device platform")
    device_name: Optional[str] = Field(None, max_length=100, description="Human-readable device name")


class DeviceTokenResponse(BaseModel):
    """Response for device token operations."""
    success: bool
    message: str


# --- Endpoints ---

@router.post("/", response_model=DeviceTokenResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("", response_model=DeviceTokenResponse, status_code=status.HTTP_201_CREATED)
async def register_device_token(
    request: RegisterDeviceRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> DeviceTokenResponse:
    """Register or update a push notification device token.

    Called on app startup and when the token refreshes.
    The same token is upserted (no duplicates).
    """
    from ...modules.member.device_token_service import DeviceTokenService

    service = DeviceTokenService(db)
    try:
        await service.register_token(
            user_id=user_id,
            fcm_token=request.token,
            device_type=request.platform,
            device_name=request.device_name,
        )
        await db.commit()
        return DeviceTokenResponse(success=True, message="Device token registered")
    except Exception as e:
        logger.error("Failed to register device token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register device token",
        )


@router.delete("/{token}", response_model=DeviceTokenResponse)
async def unregister_device_token(
    token: str,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
) -> DeviceTokenResponse:
    """Unregister a push notification device token.

    Called on user logout or app uninstall.
    """
    from ...modules.member.device_token_service import DeviceTokenService

    service = DeviceTokenService(db)
    deactivated = await service.deactivate_token(
        fcm_token=token,
        user_id=user_id,
    )
    if not deactivated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device token not found",
        )

    await db.commit()
    return DeviceTokenResponse(success=True, message="Device token unregistered")
