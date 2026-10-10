"""
WebSocket endpoint for real-time communication.

Bridges Agent Workers results to connected WebSocket clients.
Uses Redis Pub/Sub for cross-process messaging.
Supports multiple devices per user.
"""

import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from jose import JWTError

from ...config.settings import settings
from ...core.websocket import get_websocket_manager
from ...core.pubsub import get_pubsub_manager


logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


def verify_websocket_token(token: str) -> dict:
    """Verify token for WebSocket connection using shared JWT decoder.

    Dev fallback (returning default user) is only allowed when BOTH conditions hold:
      - settings.environment == "development"
      - settings.strict_auth_enabled is False
    All other environments unconditionally reject invalid tokens with 401.
    """
    from ...core.auth.auth_service import decode_token

    try:
        payload = decode_token(token)
        return {
            "user_id": payload.get("sub"),
            "family_id": payload.get("family_id"),
        }
    except JWTError:
        if settings.strict_auth_enabled or settings.environment != "development":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
            )

        from ...core.auth import _DEFAULT_USER_ID, _DEFAULT_FAMILY_ID
        logger.warning(
            "WS dev-mode auth fallback: returning default user "
            "(env=%s, strict_auth=%s)",
            settings.environment, settings.strict_auth_enabled,
        )
        return {
            "user_id": str(_DEFAULT_USER_ID),
            "family_id": str(_DEFAULT_FAMILY_ID),
        }


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(..., description="JWT authentication token"),
    device_id: Optional[str] = Query(None, description="Optional device identifier"),
):
    """
    WebSocket connection for real-time updates.

    Supports multiple concurrent connections per user (multi-device).
    Each device maintains its own connection; messages are broadcast
    to all devices for the same user.

    Query params:
        token: JWT authentication token (required)
        device_id: Optional device identifier for logging

    Message types received:
    - content: Streaming response content from agent
    - progress: Processing progress updates
    - confirm_card: Action confirmation requests
    - ask_user_question: Agent asking user a question (requires answer)
    - error: Error notifications
    - complete: Task completion
    - keepalive: Connection keepalive
    """
    # Verify token
    try:
        logger.info(
            "WS Connection Attempt: user_id=%s, device_id=%s",
            user_id, device_id or "none",
        )
        payload = verify_websocket_token(token)
        token_user_id = payload.get("user_id") or payload.get("sub")

        if str(token_user_id) != user_id:
            logger.error(
                "WS Auth Failed: Mismatch token_user=%s vs path_user=%s",
                token_user_id, user_id,
            )
            await websocket.close(code=4003, reason="User ID mismatch")
            return
    except HTTPException as e:
        logger.error("WS Auth Error: %s", e.detail)
        await websocket.close(code=4001, reason=e.detail)
        return
    except Exception as e:
        logger.exception("WS Unexpected Error: %s", e)
        await websocket.close(code=4000, reason="Internal Error")
        return

    manager = get_websocket_manager()
    family_id = payload.get("family_id", "")

    connected = await manager.connect(websocket, user_id, family_id=family_id or "")
    if not connected:
        return

    logger.info(
        "WebSocket connected: user_id=%s, device_id=%s, total=%d",
        user_id, device_id or "none", manager.get_user_connection_count(user_id),
    )

    try:
        await manager.run_with_keepalive(
            user_id=user_id,
            websocket=websocket,
            keepalive_interval=30,
        )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user_id=%s, device_id=%s", user_id, device_id or "none")
    except Exception as e:
        logger.error("WebSocket error for user=%s: %s", user_id, e)
    finally:
        # Only remove this specific connection, not all connections for the user
        await manager.disconnect_one(user_id, websocket)


@router.get("/ws/status")
async def websocket_status():
    """
    Get WebSocket service status.

    Returns:
        Current connection count and service health
    """
    manager = get_websocket_manager()
    pubsub = get_pubsub_manager()

    return {
        "status": "ok",
        "connections": manager.get_connection_count(),
        "pubsub_healthy": await pubsub.health_check(),
    }
