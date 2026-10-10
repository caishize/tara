"""Favor suggestion strategy — renqing/favor-based reciprocity reminders (PRD 4.4)."""
from typing import List, Optional
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, and_

from .....config.logging import get_logger
from .....core.utils.timezone import utc_now
from ....curation.services.query_utils import escape_like
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


class FavorStrategy(SuggestionStrategy):
    """Find suggestions based on favor/renqing memories (PRD 4.4)."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []

        try:
            from ....memory.models import (
                ConversationMemory,
                MemoryType,
                MemoryStatus,
            )

            one_month_ago = utc_now() - timedelta(days=30)

            favor_query = select(ConversationMemory).where(
                and_(
                    ConversationMemory.user_id == user_id,
                    ConversationMemory.memory_type == MemoryType.FAVOR.value,
                    ConversationMemory.status == MemoryStatus.ACTIVE.value,
                    ConversationMemory.created_at >= one_month_ago,
                )
            ).order_by(ConversationMemory.importance.desc()).limit(5)

            result = await self.db.execute(favor_query)
            favor_memories = result.scalars().all()

            for favor in favor_memories:
                entities = favor.entities or {}
                person = entities.get("person")
                favor_direction = entities.get("favor_direction")
                favor_type = entities.get("favor_type", "帮忙")

                if favor_direction != "received" or not person:
                    continue

                days_since = (utc_now() - favor.created_at).days

                if days_since >= 14:
                    title = f"该回礼了：{person}"
                    content = f"{person}{favor_type}已过{days_since}天，可考虑送礼或请客答谢"
                    priority = 80
                    urgency = "high"
                elif days_since >= 7:
                    title = f"人情提醒：{person}"
                    content = f"{person}之前{favor_type}，可适时回礼"
                    priority = 65
                    urgency = "normal"
                else:
                    continue

                # Check if we have preference info for this person
                pref_query = select(ConversationMemory).where(
                    and_(
                        ConversationMemory.user_id == user_id,
                        ConversationMemory.memory_type == MemoryType.PREFERENCE.value,
                        ConversationMemory.entities["person"].astext.ilike(f"%{escape_like(person)}%", escape="\\"),
                    )
                ).limit(1)

                pref_result = await self.db.execute(pref_query)
                pref_memory = pref_result.scalars().first()

                if pref_memory:
                    content += f"\n{person}的喜好：{pref_memory.summary[:40]}"

                suggestions.append(Suggestion(
                    type=SuggestionType.GIFT_REMINDER,
                    title=title,
                    content=content,
                    icon="favorite",
                    action_options=["prepare_gift", "schedule_meeting", "set_reminder", "ignore"],
                    action_data={
                        "memory_id": str(favor.id),
                        "person": person,
                        "favor_type": favor_type,
                        "days_since": days_since,
                        "has_preference": pref_memory is not None,
                    },
                    priority=priority,
                    urgency=urgency,
                ))

        except ImportError as e:
            logger.debug(f"Memory models not available: {e}")
        except Exception as e:
            logger.error(f"Error finding favor suggestions: {e}")

        return suggestions
