"""
反馈事件处理器

处理礼物反馈事件，触发偏好学习。
"""
import logging
from typing import Optional
from uuid import UUID

from ..event_bus import event_handler
from ..domain_events import GiftFeedbackReceived

logger = logging.getLogger(__name__)


def create_feedback_received_handler(preference_learning_service, history_repo):
    """创建反馈接收事件处理器"""

    @event_handler(GiftFeedbackReceived)
    async def on_feedback_received(event: GiftFeedbackReceived):
        """
        处理礼物反馈接收事件

        当用户对送出的礼物添加反馈时，自动更新偏好学习。
        """
        logger.info(
            f"Handling GiftFeedbackReceived event: history {event.history_id}, "
            f"rating {event.feedback_rating}"
        )

        try:
            # 更新偏好
            preference = await preference_learning_service.update_from_feedback(
                member_id=event.recipient_member_id,
                family_id=event.family_id,
                gift_category=event.gift_category,
                feedback_rating=event.feedback_rating,
                history_id=event.history_id
            )

            logger.info(
                f"Updated preference for member {event.recipient_member_id}, "
                f"category {event.gift_category}: score={preference.preference_score:.2f}, "
                f"confidence={preference.confidence:.2f}"
            )

        except Exception as e:
            logger.error(f"Failed to update preference from feedback: {e}")

    return on_feedback_received
