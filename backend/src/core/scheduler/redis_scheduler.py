"""
Redis Sorted Set Scheduler Store

Provides O(log N) per-entity scheduling via Redis ZSET.
Each task type gets its own sorted set key: schedule:{task_name}
Score = Unix timestamp of next run.
Entity ID is the member value.

Lua script ensures atomic pop (ZRANGEBYSCORE + ZREM) for
multi-process safety — no duplicate dispatches.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..utils.timezone import utc_now
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    DAILY = "daily"
    INTERVAL = "interval"
    WEEKLY = "weekly"
    ONCE = "once"


@dataclass(frozen=True)
class TaskScheduleConfig:
    task_name: str
    entity_type: str
    schedule_type: ScheduleType
    default_hour: int = 0
    default_minute: int = 0
    default_interval_minutes: int = 60
    default_day_of_week: int = 0
    queue: str = "default"


# Lua script: atomically pop due items from a sorted set.
# KEYS[1] = sorted set key
# ARGV[1] = current timestamp (upper score bound)
# ARGV[2] = batch size
_LUA_POP_DUE = """
local key = KEYS[1]
local now_ts = tonumber(ARGV[1])
local batch = tonumber(ARGV[2])
local items = redis.call('ZRANGEBYSCORE', key, 0, now_ts, 'LIMIT', 0, batch)
if #items > 0 then
    redis.call('ZREM', key, unpack(items))
end
return items
"""

KEY_PREFIX = "schedule"


def _key(task_name: str) -> str:
    return f"{KEY_PREFIX}:{task_name}"


class RedisScheduleStore:
    """Redis Sorted Set schedule storage (async)."""

    def __init__(self, redis_client):
        self._redis = redis_client
        self._pop_script_sha: Optional[str] = None

    async def _ensure_script(self):
        if self._pop_script_sha is None:
            self._pop_script_sha = await self._redis.script_load(_LUA_POP_DUE)

    async def schedule(
        self,
        task_name: str,
        entity_id: str,
        next_run: datetime,
    ) -> bool:
        """Add or update an entity's next-run time."""
        ts = next_run.timestamp()
        result = await self._redis.zadd(_key(task_name), {entity_id: ts})
        return result is not None

    async def schedule_nx(
        self,
        task_name: str,
        entity_id: str,
        next_run: datetime,
    ) -> bool:
        """Add only if entity is not already scheduled (NX)."""
        ts = next_run.timestamp()
        result = await self._redis.zadd(_key(task_name), {entity_id: ts}, nx=True)
        return result is not None and result > 0

    async def unschedule(self, task_name: str, entity_id: str) -> bool:
        """Remove an entity from the schedule."""
        result = await self._redis.zrem(_key(task_name), entity_id)
        return result > 0

    async def pop_due(self, task_name: str, batch_size: int = 50) -> List[str]:
        """Atomically pop entities whose score <= now."""
        await self._ensure_script()
        now_ts = utc_now().timestamp()
        result = await self._redis.evalsha(
            self._pop_script_sha,
            1,
            _key(task_name),
            str(now_ts),
            str(batch_size),
        )
        return [item if isinstance(item, str) else item.decode() for item in (result or [])]

    async def get_next_run(
        self, task_name: str, entity_id: str
    ) -> Optional[datetime]:
        """Get the scheduled next-run time for an entity."""
        score = await self._redis.zscore(_key(task_name), entity_id)
        if score is None:
            return None
        return datetime.fromtimestamp(score, tz=timezone.utc)

    async def get_stats(self, task_name: str) -> dict:
        """Get stats for a task's schedule."""
        key = _key(task_name)
        total = await self._redis.zcard(key)

        now_ts = utc_now().timestamp()
        overdue = await self._redis.zcount(key, 0, now_ts)

        next_items = await self._redis.zrangebyscore(
            key, now_ts, "+inf", start=0, num=1, withscores=True
        )
        next_run = None
        if next_items:
            next_run = datetime.fromtimestamp(
                next_items[0][1], tz=timezone.utc
            ).isoformat()

        return {
            "task_name": task_name,
            "total_scheduled": total,
            "overdue": overdue,
            "next_run": next_run,
        }


class SyncRedisScheduleStore:
    """Synchronous Redis Sorted Set store for Celery workers."""

    def __init__(self, redis_client):
        self._redis = redis_client
        self._pop_script_sha: Optional[str] = None

    def _ensure_script(self):
        if self._pop_script_sha is None:
            self._pop_script_sha = self._redis.script_load(_LUA_POP_DUE)

    def schedule(self, task_name: str, entity_id: str, next_run: datetime) -> bool:
        ts = next_run.timestamp()
        result = self._redis.zadd(_key(task_name), {entity_id: ts})
        return result is not None

    def schedule_nx(self, task_name: str, entity_id: str, next_run: datetime) -> bool:
        ts = next_run.timestamp()
        result = self._redis.zadd(_key(task_name), {entity_id: ts}, nx=True)
        return result is not None and result > 0

    def unschedule(self, task_name: str, entity_id: str) -> bool:
        result = self._redis.zrem(_key(task_name), entity_id)
        return result > 0

    def pop_due(self, task_name: str, batch_size: int = 50) -> List[str]:
        """Atomically pop entities whose score <= now (sync version)."""
        self._ensure_script()
        now_ts = utc_now().timestamp()
        result = self._redis.evalsha(
            self._pop_script_sha,
            1,
            _key(task_name),
            str(now_ts),
            str(batch_size),
        )
        return [item if isinstance(item, str) else item.decode() for item in (result or [])]


def calculate_next_run(
    config: TaskScheduleConfig,
    now: Optional[datetime] = None,
    custom_hour: Optional[int] = None,
    custom_minute: Optional[int] = None,
    custom_interval: Optional[int] = None,
) -> datetime:
    """Calculate next run time based on schedule config."""
    if now is None:
        now = utc_now()

    hour = custom_hour if custom_hour is not None else config.default_hour
    minute = custom_minute if custom_minute is not None else config.default_minute

    if config.schedule_type == ScheduleType.DAILY:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if config.schedule_type == ScheduleType.WEEKLY:
        days_ahead = config.default_day_of_week - now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        candidate = now + timedelta(days=days_ahead)
        candidate = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(weeks=1)
        return candidate

    if config.schedule_type == ScheduleType.INTERVAL:
        interval = custom_interval if custom_interval is not None else config.default_interval_minutes
        return now + timedelta(minutes=interval)

    # ONCE — no reschedule
    return now
