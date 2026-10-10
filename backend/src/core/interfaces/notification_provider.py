"""
Notification provider interface for sending reminders through various channels.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum


class NotificationError(Exception):
    """Exception raised by notification provider."""
    pass


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    PUSH = "push"  # Push notification (in-app)
    SMS = "sms"  # SMS message
    EMAIL = "email"  # Email
    WECHAT = "wechat"  # WeChat service notification
    APP = "app"  # In-app notification


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class INotificationProvider(ABC):
    """
    Interface for sending notifications through various channels.

    Implementations should handle:
    - Channel-specific formatting
    - Delivery confirmation
    - Retry logic
    - Error handling
    """

    @abstractmethod
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
        Send a notification through the specified channel.

        Args:
            channel: Delivery channel (push, sms, email, etc.)
            recipient: Recipient identifier (user_id, phone, email, etc.)
            title: Notification title
            content: Notification content/body
            priority: Notification priority level
            metadata: Additional channel-specific data

        Returns:
            Dict containing:
            - success: bool
            - message_id: Optional[str]
            - error: Optional[str]
            - sent_at: datetime

        Raises:
            NotificationError: If sending fails
        """
        pass

    @abstractmethod
    async def send_batch(
        self,
        notifications: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Send multiple notifications in batch.

        Args:
            notifications: List of notification dictionaries

        Returns:
            List of send results
        """
        pass

    @abstractmethod
    async def get_delivery_status(
        self,
        message_id: str
    ) -> Dict[str, Any]:
        """
        Check delivery status of a sent notification.

        Args:
            message_id: Message ID returned from send_notification

        Returns:
            Dict containing:
            - status: str (sent, delivered, failed, pending)
            - delivered_at: Optional[datetime]
            - error: Optional[str]
        """
        pass
