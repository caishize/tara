"""
Entity lifecycle hooks -- schedule / unschedule entities
when users or families are activated / deactivated.
"""

import logging
from typing import List
from uuid import UUID

from .redis_scheduler import RedisScheduleStore, ScheduleType, calculate_next_run
from .dispatcher import TASK_CONFIGS

logger = logging.getLogger(__name__)


def _task_names_for(entity_type: str) -> List[str]:
    """Return recurring task names for the given entity type."""
    return [
        name
        for name, cfg in TASK_CONFIGS.items()
        if cfg.entity_type == entity_type and cfg.schedule_type != ScheduleType.ONCE
    ]


def _resolve_redis(redis_client):
    """Resolve the async Redis client, falling back to the global singleton."""
    if redis_client is not None:
        return redis_client
    from ..cache import redis_client as _rc
    return _rc.client


async def _schedule_entity(
    entity_id: UUID,
    task_names: List[str],
    redis_client=None,
) -> int:
    """Schedule an entity into all given sorted sets (NX)."""
    client = _resolve_redis(redis_client)
    if client is None:
        logger.error("Redis unavailable for scheduling entity %s", entity_id)
        return 0

    store = RedisScheduleStore(client)
    added = 0
    for task_name in task_names:
        config = TASK_CONFIGS.get(task_name)
        if config is None:
            continue
        next_run = calculate_next_run(config)
        if await store.schedule_nx(task_name, str(entity_id), next_run):
            added += 1
    return added


async def _unschedule_entity(
    entity_id: UUID,
    task_names: List[str],
    redis_client=None,
) -> int:
    """Remove an entity from all given sorted sets."""
    client = _resolve_redis(redis_client)
    if client is None:
        logger.error("Redis unavailable for unscheduling entity %s", entity_id)
        return 0

    store = RedisScheduleStore(client)
    removed = 0
    for task_name in task_names:
        if await store.unschedule(task_name, str(entity_id)):
            removed += 1
    return removed


async def on_user_activated(user_id: UUID, redis_client=None) -> int:
    """Schedule a user into all user-scoped sorted sets (NX)."""
    added = await _schedule_entity(user_id, _task_names_for("user"), redis_client)
    logger.info("on_user_activated user=%s added=%d schedules", user_id, added)
    return added


async def on_user_deactivated(user_id: UUID, redis_client=None) -> int:
    """Remove a user from all user-scoped sorted sets."""
    removed = await _unschedule_entity(user_id, _task_names_for("user"), redis_client)
    logger.info("on_user_deactivated user=%s removed=%d schedules", user_id, removed)
    return removed


async def on_family_activated(family_id: UUID, redis_client=None) -> int:
    """Schedule a family into all family-scoped sorted sets (NX)."""
    added = await _schedule_entity(family_id, _task_names_for("family"), redis_client)
    logger.info("on_family_activated family=%s added=%d schedules", family_id, added)
    return added


async def on_family_deactivated(family_id: UUID, redis_client=None) -> int:
    """Remove a family from all family-scoped sorted sets."""
    removed = await _unschedule_entity(family_id, _task_names_for("family"), redis_client)
    logger.info("on_family_deactivated family=%s removed=%d schedules", family_id, removed)
    return removed
