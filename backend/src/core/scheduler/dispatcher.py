"""
Unified Dispatcher — Celery Beat triggers this every 30 seconds.

For each registered task type, pops due entities from Redis sorted sets
and dispatches per-entity Celery tasks.
"""

import logging
from typing import Dict, Optional

from celery import shared_task

from .redis_scheduler import (
    TaskScheduleConfig,
    ScheduleType,
    SyncRedisScheduleStore,
    calculate_next_run,
)

logger = logging.getLogger(__name__)

# ─── Task Registry ───────────────────────────────────────────────────────────

TASK_CONFIGS: Dict[str, TaskScheduleConfig] = {}


def register_task(config: TaskScheduleConfig) -> None:
    """Register a task schedule config in the global registry."""
    TASK_CONFIGS[config.task_name] = config
    logger.debug("Registered schedule config: %s", config.task_name)


# ─── Registrations ───────────────────────────────────────────────────────────

def _register_all():
    """Register all per-entity task configs."""
    configs = [
        TaskScheduleConfig(
            task_name="secretary.prepare_daily_content",
            entity_type="user",
            schedule_type=ScheduleType.DAILY,
            default_hour=6,
            default_minute=0,
            queue="secretary",
        ),
        TaskScheduleConfig(
            task_name="secretary.curate_family",
            entity_type="family",
            schedule_type=ScheduleType.INTERVAL,
            default_interval_minutes=60,
            queue="secretary",
        ),
        TaskScheduleConfig(
            task_name="assistant.consolidate_user_memories",
            entity_type="user",
            schedule_type=ScheduleType.WEEKLY,
            default_day_of_week=6,
            default_hour=3,
            queue="assistant",
        ),
        TaskScheduleConfig(
            task_name="assistant.generate_user_secretary_notes",
            entity_type="user",
            schedule_type=ScheduleType.WEEKLY,
            default_day_of_week=6,
            default_hour=3,
            default_minute=30,
            queue="assistant",
        ),
        TaskScheduleConfig(
            task_name="secretary.run_family_hygiene",
            entity_type="family",
            schedule_type=ScheduleType.DAILY,
            default_hour=3,
            queue="secretary",
        ),
        TaskScheduleConfig(
            task_name="reminder.send_single",
            entity_type="reminder",
            schedule_type=ScheduleType.ONCE,
            queue="default",
        ),
        TaskScheduleConfig(
            task_name="gift.process_single_task",
            entity_type="gift_task",
            schedule_type=ScheduleType.ONCE,
            queue="default",
        ),
    ]
    for cfg in configs:
        register_task(cfg)


_register_all()


# ─── Dispatch Task ────────────────────────────────────────────────────────────

@shared_task(name="scheduler.dispatch")
def dispatch_due_tasks() -> dict:
    """
    Pop due entities from every registered sorted set and dispatch
    per-entity Celery tasks.

    Called every 30 seconds by Celery Beat.
    Uses the Lua pop script for atomic ZRANGEBYSCORE + ZREM.
    """
    from ...celery_app import celery_app
    from ...core.cache import get_redis_client

    redis = get_redis_client()
    if redis is None:
        logger.error("Redis unavailable, skipping dispatch")
        return {"error": "redis_unavailable"}

    store = SyncRedisScheduleStore(redis)
    total_dispatched = 0
    results = {}

    for task_name, config in TASK_CONFIGS.items():
        entity_ids = store.pop_due(task_name, batch_size=100)

        dispatched = 0
        for entity_id in entity_ids:
            try:
                celery_app.send_task(
                    config.task_name,
                    args=[entity_id],
                    queue=config.queue,
                )
                dispatched += 1
            except Exception as e:
                logger.error(
                    "Failed to dispatch %s for %s: %s",
                    config.task_name,
                    entity_id,
                    e,
                )

        if dispatched:
            results[task_name] = dispatched
            total_dispatched += dispatched

    if total_dispatched:
        logger.info("Dispatched %d tasks: %s", total_dispatched, results)

    return {"dispatched": total_dispatched, "details": results}


# ─── Backfill Task ────────────────────────────────────────────────────────────

@shared_task(name="scheduler.backfill")
def backfill_schedules(task_name: Optional[str] = None) -> dict:
    """
    Backfill sorted sets from the database.

    Uses NX (only-if-absent) so existing custom schedules are preserved.
    Called on beat startup or manually.
    """
    from ._async_compat import run_async
    return run_async(_backfill_async(task_name))


async def _backfill_async(filter_task_name: Optional[str] = None) -> dict:
    """Async backfill implementation."""
    from ...db.session import create_celery_async_session
    from ...core.cache import get_redis_client

    redis = get_redis_client()
    if redis is None:
        return {"error": "redis_unavailable"}

    store = SyncRedisScheduleStore(redis)
    engine, session_factory = create_celery_async_session()
    results = {}

    try:
        # Warm up the async DB connection pool.  On macOS with Celery's
        # prefork pool the first asyncpg operation in a forked worker can
        # fail with EINVAL due to inherited kqueue file descriptors.
        # A cheap SELECT 1 absorbs that transient failure before real work.
        try:
            async with session_factory() as _warmup:
                from sqlalchemy import text
                await _warmup.execute(text("SELECT 1"))
        except Exception:
            logger.debug("DB warmup failed (expected on macOS fork), retrying")
            async with session_factory() as _warmup:
                from sqlalchemy import text
                await _warmup.execute(text("SELECT 1"))

        configs_to_process = (
            {filter_task_name: TASK_CONFIGS[filter_task_name]}
            if filter_task_name and filter_task_name in TASK_CONFIGS
            else TASK_CONFIGS
        )

        for task_name, config in configs_to_process.items():
            # Skip one-shot tasks (reminders, gift tasks) -- they are
            # scheduled on creation, not backfilled.
            if config.schedule_type == ScheduleType.ONCE:
                continue

            try:
                entity_ids = await _get_active_entities(
                    config.entity_type, session_factory
                )
                added = 0
                for eid in entity_ids:
                    next_run = calculate_next_run(config)
                    if store.schedule_nx(task_name, str(eid), next_run):
                        added += 1
                results[task_name] = {
                    "entities": len(entity_ids),
                    "added": added,
                }
            except Exception as e:
                logger.error("Backfill failed for %s: %s", task_name, e, exc_info=True)
                results[task_name] = {"error": str(e)}

    finally:
        await engine.dispose()

    logger.info("Backfill complete: %s", results)
    return results


async def _get_active_entities(entity_type: str, session_factory) -> list:
    """Fetch active entity IDs from the database."""
    from sqlalchemy import select

    async with session_factory() as session:
        if entity_type == "user":
            from ...modules.member.models.user import User
            result = await session.execute(
                select(User.id).where(User.is_active == True)
            )
            return [str(row[0]) for row in result.all()]

        if entity_type == "family":
            from ...modules.member.models.user import User
            result = await session.execute(
                select(User.family_id)
                .where(User.is_active == True)
                .where(User.family_id.isnot(None))
                .distinct()
            )
            return [str(row[0]) for row in result.all()]

        return []
