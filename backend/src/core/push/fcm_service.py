"""
FCM Push Notification Service.

Sends push notifications via Firebase Cloud Messaging when
WebSocket delivery fails (user offline).
"""

import logging
import os
from typing import Any, Dict, List, Optional

from ...config.settings import settings

logger = logging.getLogger(__name__)

_firebase_app = None


def _get_firebase_app():
    """Lazily initialize Firebase Admin SDK."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    if not settings.fcm_enabled:
        return None

    if not settings.firebase_service_account_path:
        logger.warning("FCM enabled but FIREBASE_SERVICE_ACCOUNT_PATH not set")
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials

        sa_path = os.path.realpath(settings.firebase_service_account_path)
        if not os.path.isfile(sa_path):
            logger.error(f"Firebase service account file not found: {sa_path}")
            return None
        if not sa_path.endswith(".json"):
            logger.error("Firebase service account path must be a .json file")
            return None

        cred = credentials.Certificate(sa_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized")
        return _firebase_app
    except ImportError:
        logger.warning("firebase-admin not installed; FCM push disabled")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        return None


async def send_to_user(
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
) -> List[str]:
    """
    Send a push notification to a user's devices.

    Args:
        tokens: List of FCM tokens to send to.
        title: Notification title.
        body: Notification body text.
        data: Optional data payload (all values must be strings).

    Returns:
        List of invalid/expired tokens that should be deactivated.
    """
    app = _get_firebase_app()
    if app is None:
        return []

    if not tokens:
        return []

    try:
        from firebase_admin import messaging

        invalid_tokens: List[str] = []

        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                    ),
                ),
            ),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="pending_actions",
                    sound="default",
                ),
            ),
        )

        response = messaging.send_each_for_multicast(message, app=app)

        for i, send_response in enumerate(response.responses):
            if send_response.exception is not None:
                error_code = getattr(
                    send_response.exception, "code", "unknown"
                )
                if error_code in (
                    "NOT_FOUND",
                    "UNREGISTERED",
                    "INVALID_ARGUMENT",
                ):
                    invalid_tokens.append(tokens[i])
                logger.warning(
                    f"FCM send failed for token {tokens[i][:20]}...: "
                    f"{send_response.exception}"
                )

        logger.info(
            f"FCM multicast: {response.success_count} success, "
            f"{response.failure_count} failures, "
            f"{len(invalid_tokens)} invalid tokens"
        )

        return invalid_tokens

    except ImportError:
        logger.warning("firebase-admin not installed; skipping push")
        return []
    except Exception as e:
        logger.error(f"FCM send failed: {e}")
        return []
