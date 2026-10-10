"""Curation strategy -- surfaces today's curated events from the BriefingAccumulator."""
from typing import List, Optional
from uuid import UUID

from .....config.logging import get_logger
from ..accumulator import BriefingAccumulator
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)

_PRIORITY_MAP = {
    "critical": 100,
    "high": 85,
    "normal": 65,
    "low": 45,
}

_URGENCY_MAP = {
    "critical": "high",
    "high": "high",
    "normal": "normal",
    "low": "low",
}


class CurationStrategy(SuggestionStrategy):
    """Read accumulated curation items from Redis and convert to Suggestions."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        if family_id is None:
            return []

        suggestions: List[Suggestion] = []
        try:
            accumulator = BriefingAccumulator()
            items = await accumulator.get_today_items(family_id, limit=20)

            for item in items:
                priority_str = item.get("priority", "normal")
                event_id = item.get("event_id", "")

                suggestions.append(Suggestion(
                    type=SuggestionType.CURATION,
                    title=item.get("title", "策划事项"),
                    content=item.get("description", item.get("event_type", "")),
                    icon="auto_awesome",
                    related_event_ids=[event_id] if event_id else [],
                    action_options=["view_details", "ignore"],
                    action_data={
                        "source": item.get("type", "curation"),
                        "event_id": event_id,
                        "trigger_data": item.get("trigger_data", {}),
                    },
                    priority=_PRIORITY_MAP.get(priority_str, 65),
                    urgency=_URGENCY_MAP.get(priority_str, "normal"),
                ))
        except Exception as e:
            logger.error("CurationStrategy failed: %s", e)

        return suggestions
