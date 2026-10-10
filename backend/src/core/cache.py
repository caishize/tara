"""
Redis cache client.
"""
import redis.asyncio as redis
from typing import Optional, Any
import json
from ..config.settings import settings


class RedisClient:
    """Async Redis client wrapper."""

    def __init__(self):
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> Optional[redis.Redis]:
        """Expose the underlying Redis connection for advanced operations."""
        return self._client

    async def connect(self):
        """Initialize Redis connection pool."""
        self._client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20
        )

    async def disconnect(self):
        """Close Redis connections."""
        if self._client:
            await self._client.close()

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if not self._client:
            return None
        return await self._client.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set key-value pair.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized if dict/list)
            ttl: Time-to-live in seconds (None = no expiration)
        """
        if not self._client:
            return False

        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)

        if ttl:
            return await self._client.setex(key, ttl, value)
        else:
            return await self._client.set(key, value)

    async def delete(self, key: str) -> int:
        """Delete key."""
        if not self._client:
            return 0
        return await self._client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._client:
            return False
        return await self._client.exists(key) > 0

    async def ping(self) -> bool:
        """Health check."""
        if not self._client:
            return False
        try:
            return await self._client.ping()
        except Exception:
            return False


# Global Redis client instance
redis_client = RedisClient()


def get_redis_client():
    """
    Get a synchronous Redis client for Celery tasks.

    This is a sync client for use in Celery workers that don't use
    the async event loop.

    Returns:
        redis.Redis or None if connection fails
    """
    import redis as sync_redis
    try:
        return sync_redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    except Exception:
        return None
