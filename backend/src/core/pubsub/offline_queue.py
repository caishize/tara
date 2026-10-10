"""
Offline message queue for WebSocket gap recovery.

When a PubSub message is published but no WebSocket subscriber is connected,
messages are buffered in a Redis List per user. On reconnect, the client
can drain the queue to recover missed messages.
"""
import json
import logging
from typing import Dict, List, Optional

import redis.asyncio as redis

from ...config.settings import settings

logger = logging.getLogger(__name__)

# Eligible message types for offline buffering
_OFFLINE_ELIGIBLE_TYPES = frozenset({
    "content", "complete", "error", "confirm_card",
    "ask_user_question", "tool_execution", "thinking",
})

MAX_QUEUE_SIZE = 500
QUEUE_TTL_SECONDS = 86400  # 24 hours


class OfflineMessageQueue:
    """Redis List-backed offline message queue per user.

    Key format: ``offline:{user_id}``

    Messages are JSON-serialized dicts (same format as PubSubMessage.to_dict()).
    """

    KEY_PREFIX = "offline"

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis: Optional[redis.Redis] = redis_client

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=5,
            )
        return self._redis

    def _key(self, user_id: str) -> str:
        return f"{self.KEY_PREFIX}:{user_id}"

    async def push(self, user_id: str, message_dict: Dict) -> None:
        """Push a message to the user's offline queue.

        Only buffers message types that are useful for gap recovery.
        Trims the queue to MAX_QUEUE_SIZE and refreshes TTL.
        """
        msg_type = message_dict.get("message_type", "")
        if msg_type not in _OFFLINE_ELIGIBLE_TYPES:
            return

        r = await self._get_redis()
        key = self._key(user_id)
        serialized = json.dumps(message_dict, ensure_ascii=False)

        pipe = r.pipeline(transaction=False)
        pipe.rpush(key, serialized)
        pipe.ltrim(key, -MAX_QUEUE_SIZE, -1)
        pipe.expire(key, QUEUE_TTL_SECONDS)
        await pipe.execute()

        logger.debug(
            "Offline queue push: user=%s type=%s", user_id, msg_type
        )

    async def drain(self, user_id: str) -> List[Dict]:
        """Drain all messages from the user's offline queue.

        Returns all buffered messages and deletes the queue atomically.
        """
        r = await self._get_redis()
        key = self._key(user_id)

        pipe = r.pipeline(transaction=True)
        pipe.lrange(key, 0, -1)
        pipe.delete(key)
        results = await pipe.execute()

        raw_messages: List[str] = results[0] or []
        messages: List[Dict] = []
        for raw in raw_messages:
            try:
                messages.append(json.loads(raw))
            except json.JSONDecodeError:
                logger.warning("Skipping invalid offline message: %s", raw[:100])

        if messages:
            logger.info(
                "Offline queue drained: user=%s count=%d", user_id, len(messages)
            )
        return messages

    async def drain_for_job(
        self, user_id: str, job_id: str, after_seq: int
    ) -> List[Dict]:
        """Drain messages for a specific job_id with seq > after_seq.

        Unlike full drain, this preserves messages not matching the filter.
        """
        r = await self._get_redis()
        key = self._key(user_id)

        all_raw: List[str] = await r.lrange(key, 0, -1)
        if not all_raw:
            return []

        matched: List[Dict] = []
        remaining: List[str] = []

        for raw in all_raw:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_job_id = msg.get("job_id")
            msg_seq = msg.get("seq")

            if msg_job_id == job_id and isinstance(msg_seq, int) and msg_seq > after_seq:
                matched.append(msg)
            else:
                remaining.append(raw)

        if not matched:
            return []

        # Replace queue with non-matched messages
        pipe = r.pipeline(transaction=True)
        pipe.delete(key)
        if remaining:
            pipe.rpush(key, *remaining)
            pipe.expire(key, QUEUE_TTL_SECONDS)
        await pipe.execute()

        logger.info(
            "Offline queue filtered drain: user=%s job=%s after_seq=%d matched=%d",
            user_id, job_id, after_seq, len(matched),
        )
        return matched


# Module-level singleton
_offline_queue: Optional[OfflineMessageQueue] = None


def get_offline_queue() -> OfflineMessageQueue:
    """Get or create the global offline message queue."""
    global _offline_queue
    if _offline_queue is None:
        _offline_queue = OfflineMessageQueue()
    return _offline_queue
