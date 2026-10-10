"""
礼物事件处理器

处理礼物选择、历史记录等事件。
"""
import logging
from ...utils.timezone import utc_now
from typing import Optional
from uuid import UUID

from ..event_bus import event_handler
from ..domain_events import (
    GiftOptionSelected,
    GiftHistoryRecorded,
    GiftRecommendationGenerated,
)

logger = logging.getLogger(__name__)


def create_option_selected_handler(history_service, recommendation_repo):
    """创建礼物选择事件处理器"""

    @event_handler(GiftOptionSelected)
    async def on_option_selected(event: GiftOptionSelected):
        """
        处理礼物方案选择事件

        当用户选择一个礼物方案时，自动创建历史记录。
        """
        logger.info(
            f"Handling GiftOptionSelected event: recommendation {event.recommendation_id}, "
            f"option {event.option_index}"
        )

        try:
            # 获取推荐记录以获取详细信息
            rec = await recommendation_repo.get_by_id(event.recommendation_id)
            if not rec:
                logger.error(f"Recommendation {event.recommendation_id} not found")
                return

            # 获取选择的方案
            if event.option_index >= len(rec.recommendations):
                logger.error(f"Invalid option index {event.option_index}")
                return

            selected = rec.recommendations[event.option_index]

            # 创建历史记录
            history_data = {
                "family_id": event.family_id,
                "giver_user_id": event.user_id,
                "recipient_member_id": event.member_id,
                "recommendation_id": event.recommendation_id,
                "related_date_id": rec.related_date_id,
                "gift_name": selected.get("name", event.gift_name),
                "gift_category": selected.get("category", event.gift_category),
                "gift_description": selected.get("reason", ""),
                "occasion": rec.occasion,
                "occasion_date": rec.occasion_date or utc_now().date(),
                "gift_price": str(selected.get("price", "")) if selected.get("price") else None,
                "purchase_link": selected.get("purchase_link"),
                "image_url": selected.get("image_url"),
                "source": "recommendation"
            }

            history = await history_service.create_history(history_data)
            logger.info(f"Created gift history {history.id} from recommendation selection")

        except Exception as e:
            logger.error(f"Failed to create history from selection: {e}")

    return on_option_selected


def create_recommendation_generated_handler():
    """创建推荐生成完成事件处理器"""

    @event_handler(GiftRecommendationGenerated)
    async def on_recommendation_generated(event: GiftRecommendationGenerated):
        """
        处理推荐生成完成事件

        可用于发送通知、更新统计等。
        """
        logger.info(
            f"Recommendation {event.recommendation_id} generated for member {event.member_id}, "
            f"{event.options_count} options, personalization score: {event.personalization_score:.2f}"
        )

        # TODO: 发送App内通知给用户
        # TODO: 更新统计metrics

    return on_recommendation_generated
