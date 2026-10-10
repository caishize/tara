"""
Reschedule helpers -- called at the end of every per-entity task
to put the entity back into the sorted set for its next run.
"""

import logging
from typing import Optional

from .redis_scheduler import (
    SyncRedisScheduleStore,
    RedisScheduleStore,
    TaskScheduleConfig,
    calculate_next_run,
    ScheduleType,
)
from .dispatcher import TASK_CONFIGS

logger = logging.getLogger(__name__)


def _get_recurring_config(task_name: str) -> Optional[TaskScheduleConfig]:
    """Look up a task config and return None for unknown or one-shot tasks."""
    config = TASK_CONFIGS.get(task_name)
    if config is None:
        logger.warning("Unknown task %s, skipping reschedule", task_name)
        return None
    if config.schedule_type == ScheduleType.ONCE:
        return None
    return config


def reschedule_sync(
    task_name: str,
    entity_id: str,
    custom_hour: Optional[int] = None,
    custom_minute: Optional[int] = None,
    custom_interval: Optional[int] = None,
) -> bool:
    """
    Synchronous reschedule for use inside Celery tasks.

    Computes the next run time from the task config and
    writes it back to the sorted set.
    """
    config = _get_recurring_config(task_name)
    if config is None:
        return False

    from ...core.cache import get_redis_client

    redis = get_redis_client()
    if redis is None:
        logger.error("Redis unavailable, cannot reschedule %s", task_name)
        return False

    store = SyncRedisScheduleStore(redis)
    next_run = calculate_next_run(
        config,
        custom_hour=custom_hour,
        custom_minute=custom_minute,
        custom_interval=custom_interval,
    )
    store.schedule(task_name, entity_id, next_run)
    logger.debug(
        "Rescheduled %s entity=%s next_run=%s",
        task_name,
        entity_id,
        next_run.isoformat(),
    )
    return True


async def reschedule_async(
    task_name: str,
    entity_id: str,
    redis_client=None,
    custom_hour: Optional[int] = None,
    custom_minute: Optional[int] = None,
    custom_interval: Optional[int] = None,
) -> bool:
    """Async reschedule for use in FastAPI / async contexts."""
    config = _get_recurring_config(task_name)
    if config is None:
        return False

    if redis_client is None:
        from ...core.cache import redis_client as _rc
        redis_client = _rc.client

    if redis_client is None:
        logger.error("Redis unavailable, cannot reschedule %s", task_name)
        return False

    store = RedisScheduleStore(redis_client)
    next_run = calculate_next_run(
        config,
        custom_hour=custom_hour,
        custom_minute=custom_minute,
        custom_interval=custom_interval,
    )
    await store.schedule(task_name, entity_id, next_run)
    logger.debug(
        "Rescheduled (async) %s entity=%s next_run=%s",
        task_name,
        entity_id,
        next_run.isoformat(),
    )
    return True
