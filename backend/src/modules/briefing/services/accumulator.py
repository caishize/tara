"""BriefingAccumulator -- receives curation events and stores them in Redis ZSET for daily briefing.

Redis key design:
  briefing:items:{family_id}:{YYYY-MM-DD} -> ZSET
    score = priority_numeric (critical=100, high=80, normal=60, low=40)
    member = JSON {type, title, event_id, description, priority, created_at}
  TTL = 48h (172800 seconds)
"""
import json
from typing import Dict, List, Optional
from uuid import UUID

from ....config.logging import get_logger
from ....core.cache import redis_client
from ....core.utils.timezone import local_today, utc_now

logger = get_logger(__name__)

_PRIORITY_SCORES: Dict[str, float] = {
    "critical": 100.0,
    "high": 80.0,
    "normal": 60.0,
    "low": 40.0,
}

_TTL_SECONDS = 172800  # 48 hours


def _redis_key(family_id: UUID, date_str: str) -> str:
    return f"briefing:items:{family_id}:{date_str}"


class BriefingAccumulator:
    """Accumulates curation and proactive events into a Redis ZSET for daily briefing."""

    async def on_event_curated(
        self,
        family_id: UUID,
        event_id: UUID,
        event_type: str,
        priority: str,
        title: str,
    ) -> None:
        """Store a curated event for today's briefing."""
        client = redis_client.client
        if client is None:
            logger.warning("Redis not connected, skipping briefing accumulation")
            return

        today_str = local_today().isoformat()
        key = _redis_key(family_id, today_str)
        score = _PRIORITY_SCORES.get(priority, _PRIORITY_SCORES["normal"])

        item = json.dumps(
            {
                "type": "event_curated",
                "title": title,
                "event_id": str(event_id),
                "event_type": event_type,
                "priority": priority,
                "created_at": utc_now().isoformat(),
            },
            ensure_ascii=False,
            default=str,
        )

        await client.zadd(key, {item: score})
        await client.expire(key, _TTL_SECONDS)
        logger.debug("Accumulated curated event %s for family %s", event_id, family_id)

    async def on_proactive_trigger(
        self,
        family_id: UUID,
        trigger_type: str,
        trigger_data: dict,
        priority: str,
    ) -> None:
        """Store a proactive trigger (DateApproaching, InsightGenerated, etc.) for today's briefing."""
        client = redis_client.client
        if client is None:
            logger.warning("Redis not connected, skipping briefing accumulation")
            return

        today_str = local_today().isoformat()
        key = _redis_key(family_id, today_str)
        score = _PRIORITY_SCORES.get(priority, _PRIORITY_SCORES["normal"])

        title = trigger_data.get("title", trigger_type)
        description = trigger_data.get("description", "")

        item = json.dumps(
            {
                "type": trigger_type,
                "title": title,
                "description": description,
                "priority": priority,
                "trigger_data": trigger_data,
                "created_at": utc_now().isoformat(),
            },
            ensure_ascii=False,
            default=str,
        )

        await client.zadd(key, {item: score})
        await client.expire(key, _TTL_SECONDS)
        logger.debug("Accumulated proactive trigger %s for family %s", trigger_type, family_id)

    async def get_today_items(
        self,
        family_id: UUID,
        limit: int = 20,
    ) -> List[dict]:
        """Retrieve today's accumulated briefing items, highest priority first."""
        client = redis_client.client
        if client is None:
            return []

        today_str = local_today().isoformat()
        key = _redis_key(family_id, today_str)

        raw_items = await client.zrevrange(key, 0, limit - 1)
        items: List[dict] = []
        for raw in raw_items:
            try:
                items.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                logger.warning("Skipping malformed briefing item: %s", raw)
        return items
