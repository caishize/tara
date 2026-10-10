"""Push service — delivers briefings as async conversation messages."""
from typing import Optional

from ....config.logging import get_logger
from ....core.push.notification_provider import app_notification_provider
from ....core.interfaces.notification_provider import (
    NotificationChannel,
    NotificationPriority,
)
from ..interface import Briefing, IPushService

logger = get_logger(__name__)


class PushService(IPushService):
    """Push a briefing to the user as an async notification."""

    async def push_briefing(
        self,
        user_id: str,
        briefing: Briefing,
    ) -> None:
        """Push a briefing as an async message.

        Uses the in-app notification provider to deliver the briefing.
        """
        title = f"{'早间' if briefing.period == 'morning' else '午间' if briefing.period == 'afternoon' else '晚间'}简报"
        section_count = len(briefing.sections)
        content = f"您有 {section_count} 条{title}内容"

        result = await app_notification_provider.send_notification(
            channel=NotificationChannel.APP,
            recipient=user_id,
            title=title,
            content=content,
            priority=NotificationPriority.NORMAL,
            metadata={
                "briefing_id": briefing.id,
                "period": briefing.period,
                "section_count": section_count,
            },
        )

        if result.get("success"):
            logger.info(
                f"Briefing pushed to user {user_id}: "
                f"period={briefing.period}, message_id={result.get('message_id')}"
            )
        else:
            logger.error(
                f"Failed to push briefing to user {user_id}: {result.get('error')}"
            )
