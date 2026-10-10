"""
Per-job ordered message log backed by Redis ZSET.

Each chat job gets its own sorted set keyed by ``job_log:{job_id}``.
Messages are scored by their sequence number so that a reconnecting
client can request all messages after a given seq and receive them in
the correct order.

This complements the user-level OfflineMessageQueue by providing a
*job-scoped* recovery mechanism that works regardless of whether
the PubSub subscriber was connected at publish time.
"""
import json
import logging
from typing import Dict, List, Optional

import redis.asyncio as redis

from ...config.settings import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "job_log"
DEFAULT_TTL = 3600  # 1 hour


class JobMessageLog:
    """Redis ZSET-backed per-job message log.

    Key format: ``job_log:{job_id}``
    Score: message sequence number (int)
    Member: JSON-serialized message dict
    """

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

    def _key(self, job_id: str) -> str:
        return f"{KEY_PREFIX}:{job_id}"

    async def append(self, job_id: str, seq: int, message: Dict) -> None:
        """Append a message to the job log.

        Args:
            job_id: The chat job identifier.
            seq: Monotonically increasing sequence number.
            message: Serializable message dict (PubSubMessage.to_dict()).
        """
        r = await self._get_redis()
        key = self._key(job_id)
        serialized = json.dumps(message, ensure_ascii=False)

        pipe = r.pipeline(transaction=False)
        pipe.zadd(key, {serialized: seq})
        pipe.expire(key, DEFAULT_TTL)
        await pipe.execute()

    async def get_after(self, job_id: str, after_seq: int) -> List[Dict]:
        """Retrieve all messages with seq > after_seq, ordered by seq.

        Args:
            job_id: The chat job identifier.
            after_seq: Exclusive lower bound on sequence number.

        Returns:
            List of message dicts ordered by ascending seq.
        """
        r = await self._get_redis()
        key = self._key(job_id)

        # ZRANGEBYSCORE with exclusive lower bound: "(after_seq" means > after_seq
        raw_members: List[str] = await r.zrangebyscore(
            key, f"({after_seq}", "+inf"
        )

        messages: List[Dict] = []
        for raw in raw_members:
            try:
                messages.append(json.loads(raw))
            except json.JSONDecodeError:
                logger.warning(
                    "Skipping invalid job_log entry: job=%s, raw=%s",
                    job_id, raw[:100],
                )
        return messages


# Module-level singleton
_job_message_log: Optional[JobMessageLog] = None


def get_job_message_log() -> JobMessageLog:
    """Get or create the global JobMessageLog instance."""
    global _job_message_log
    if _job_message_log is None:
        _job_message_log = JobMessageLog()
    return _job_message_log
