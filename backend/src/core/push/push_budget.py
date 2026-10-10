"""Daily push notification budget per user.

Tracks how many push notifications a user has received today and enforces
a configurable daily limit.  P0 notifications always bypass the budget.

Uses Redis for fast atomic counting with automatic 24h TTL.

V8 architecture: docs/architecture-v8-secretary-brain.md section 5.3
"""
import logging
from datetime import date
from uuid import UUID

from ..cache import redis_client

logger = logging.getLogger(__name__)

DEFAULT_DAILY_LIMIT = 5

# Redis key prefix for push counts
_KEY_PREFIX = "push_count"
_TTL_SECONDS = 86400  # 24 hours


def _budget_key(user_id: UUID, day: date) -> str:
    """Build the Redis key for a user's daily push count."""
    return f"{_KEY_PREFIX}:{user_id}:{day.isoformat()}"


async def can_push(
    user_id: UUID,
    priority_level: str = "P3",
    daily_limit: int = DEFAULT_DAILY_LIMIT,
) -> bool:
    """Check whether we may send another push notification today.

    Args:
        user_id: Target user.
        priority_level: P0-P3 from PriorityScore.  P0 always bypasses.
        daily_limit: Maximum notifications per day (default 5).

    Returns:
        True if the push is allowed.
    """
    if priority_level == "P0":
        return True

    try:
        key = _budget_key(user_id, date.today())
        count = await redis_client.get(key)
        current = int(count) if count is not None else 0
        return current < daily_limit
    except Exception:
        logger.warning("push_budget: failed to check budget, allowing push", exc_info=True)
        return True  # fail open


async def record_push(user_id: UUID) -> int:
    """Increment today's push count for a user.

    Returns:
        New count after increment, or -1 on failure.
    """
    try:
        key = _budget_key(user_id, date.today())
        client = redis_client.client
        if client is None:
            logger.warning("push_budget: Redis client not connected")
            return -1

        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, _TTL_SECONDS)
        results = await pipe.execute()
        new_count = int(results[0])
        return new_count
    except Exception:
        logger.warning("push_budget: failed to record push", exc_info=True)
        return -1


async def get_remaining(
    user_id: UUID,
    daily_limit: int = DEFAULT_DAILY_LIMIT,
) -> int:
    """Return how many push notifications remain in today's budget.

    Returns:
        Non-negative integer, or daily_limit on error (fail open).
    """
    try:
        key = _budget_key(user_id, date.today())
        count = await redis_client.get(key)
        current = int(count) if count is not None else 0
        return max(0, daily_limit - current)
    except Exception:
        logger.warning("push_budget: failed to get remaining", exc_info=True)
        return daily_limit
