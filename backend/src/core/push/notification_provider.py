"""
In-app notification provider implementation.
Stores notifications in database for user to view in the application.

Push budget enforcement (V8-Brain S7.2): max 5 proactive pushes/day/user,
P0 (URGENT) exempted.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import UUID, uuid4

from ..utils.timezone import utc_now
from ..interfaces.notification_provider import (
    INotificationProvider,
    NotificationChannel,
    NotificationPriority
)
from .push_budget import can_push, record_push
from ...config.logging import get_logger


logger = get_logger(__name__)

# Maps NotificationPriority to the P0-P3 levels used by push_budget / interruption_controller.
_PRIORITY_TO_LEVEL: Dict[str, str] = {
    NotificationPriority.URGENT.value: "P0",
    NotificationPriority.HIGH.value: "P1",
    NotificationPriority.NORMAL.value: "P2",
    NotificationPriority.LOW.value: "P3",
}


class AppNotificationProvider(INotificationProvider):
    """
    In-app notification provider.

    For MVP (P1), this stores notifications in memory/logs.
    Future: Store in database table for user inbox.
    """

    def __init__(self):
        # In-memory storage for MVP
        # Future: Replace with database table
        self._notifications: Dict[str, Dict[str, Any]] = {}

    async def send_notification(
        self,
        channel: NotificationChannel,
        recipient: str,
        title: str,
        content: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send an in-app notification.

        Args:
            channel: Must be APP or PUSH
            recipient: User ID (UUID string)
            title: Notification title
            content: Notification content
            priority: Priority level
            metadata: Additional data (date_id, reminder_id, etc.)

        Returns:
            Dict with success status and message_id
        """
        try:
            # Validate channel
            if channel not in [NotificationChannel.APP, NotificationChannel.PUSH]:
                raise ValueError(f"Unsupported channel: {channel}")

            # Enforce daily push budget (V8-Brain S7.2)
            priority_level = _PRIORITY_TO_LEVEL.get(priority.value, "P3")
            try:
                user_uuid = UUID(recipient)
                allowed = await can_push(user_uuid, priority_level=priority_level)
                if not allowed:
                    logger.info(
                        "Push budget exhausted for user %s (priority=%s), "
                        "notification suppressed: %s",
                        recipient, priority_level, title,
                    )
                    return {
                        "success": False,
                        "message_id": None,
                        "sent_at": utc_now(),
                        "error": "daily_push_budget_exhausted",
                    }
            except (ValueError, TypeError):
                # recipient is not a valid UUID — skip budget check
                pass

            # Generate message ID
            message_id = str(uuid4())
            sent_at = utc_now()

            # Store notification (MVP: in-memory)
            notification = {
                "message_id": message_id,
                "channel": channel.value,
                "recipient": recipient,
                "title": title,
                "content": content,
                "priority": priority.value,
                "metadata": metadata or {},
                "sent_at": sent_at.isoformat(),
                "status": "sent",
                "read": False
            }

            self._notifications[message_id] = notification

            # Record against budget (skip for P0 since they bypass anyway)
            if priority_level != "P0":
                try:
                    user_uuid = UUID(recipient)
                    await record_push(user_uuid)
                except (ValueError, TypeError):
                    pass

            # Log the notification
            logger.info(
                "Notification sent - ID: %s, Channel: %s, Recipient: %s, "
                "Title: %s, Priority: %s",
                message_id, channel.value, recipient, title, priority_level,
            )

            return {
                "success": True,
                "message_id": message_id,
                "sent_at": sent_at,
                "error": None
            }

        except Exception as e:
            logger.error("Failed to send notification: %s", e)
            return {
                "success": False,
                "message_id": None,
                "sent_at": utc_now(),
                "error": str(e)
            }

    async def send_batch(
        self,
        notifications: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Send multiple notifications in batch.

        Args:
            notifications: List of notification dicts with keys:
                - channel, recipient, title, content, priority, metadata

        Returns:
            List of send results
        """
        results = []

        for notif in notifications:
            result = await self.send_notification(
                channel=NotificationChannel(notif["channel"]),
                recipient=notif["recipient"],
                title=notif["title"],
                content=notif["content"],
                priority=NotificationPriority(notif.get("priority", "normal")),
                metadata=notif.get("metadata")
            )
            results.append(result)

        logger.info(f"Batch sent: {len(results)} notifications")
        return results

    async def get_delivery_status(
        self,
        message_id: str
    ) -> Dict[str, Any]:
        """
        Get delivery status of a notification.

        Args:
            message_id: Message ID

        Returns:
            Status dict
        """
        notification = self._notifications.get(message_id)

        if not notification:
            return {
                "status": "not_found",
                "delivered_at": None,
                "error": "Message ID not found"
            }

        return {
            "status": notification["status"],
            "delivered_at": notification["sent_at"],
            "read": notification["read"],
            "error": None
        }

    def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get notifications for a user (helper method for MVP).

        Args:
            user_id: User ID
            unread_only: Only return unread notifications

        Returns:
            List of notifications
        """
        user_notifs = [
            notif for notif in self._notifications.values()
            if notif["recipient"] == user_id
        ]

        if unread_only:
            user_notifs = [n for n in user_notifs if not n["read"]]

        # Sort by sent_at descending
        user_notifs.sort(key=lambda x: x["sent_at"], reverse=True)

        return user_notifs

    def mark_as_read(self, message_id: str) -> bool:
        """
        Mark notification as read.

        Args:
            message_id: Message ID

        Returns:
            Success status
        """
        notification = self._notifications.get(message_id)
        if notification:
            notification["read"] = True
            notification["read_at"] = utc_now().isoformat()
            logger.info(f"Notification marked as read: {message_id}")
            return True
        return False


# Global instance for MVP
app_notification_provider = AppNotificationProvider()
