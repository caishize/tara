"""
Curation Scheduled Tasks - AI Secretary Event Processing

Runs every 15 minutes (Celery Beat) to check which families need curation.
Actual execution depends on each family's curation_interval_minutes setting
and a cooldown check against the last completed curation job.

Also supports event-driven triggers when new data is added.
"""
import logging
import os
from typing import List, Optional
from datetime import date, datetime, timedelta, timezone as dt_tz
from uuid import UUID

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.scheduler._async_compat import run_async
from ...core.scheduler.reschedule import reschedule_sync
from ...core.utils.timezone import (
    local_today,
    set_active_timezone,
    reset_active_timezone,
    utc_now,
)
from ...db.session import create_celery_async_session
from .task_utils import get_active_families
from .services.family_settings import get_family_curation_settings

logger = logging.getLogger(__name__)

# Configurable constants - can be overridden via environment variables
DAILY_CURATION_DAYS_AHEAD = int(os.getenv("CURATION_DAYS_AHEAD", "7"))
DEFAULT_CURATION_DAYS_AHEAD = int(os.getenv("DEFAULT_CURATION_DAYS_AHEAD", "14"))
DEFAULT_CURATION_INTERVAL_MINUTES = 60


def _ensure_curation_orm_models_loaded() -> None:
    """Load interdependent ORM model modules to stabilize mapper resolution.

    Celery workers can execute curation tasks in a minimal import context where
    cross-module relationship targets are not yet registered (e.g.
    ConversationMemory -> AssistantChatSession). Importing these modules once
    avoids non-deterministic mapper initialization failures during collection.
    """
    from ..conversation import models as _conversation_models  # noqa: F401
    from ..memory import models as _memory_models  # noqa: F401
    from ..trip import models as _trip_models  # noqa: F401
    from . import models as _curation_models  # noqa: F401


async def _get_family_curation_interval(
    family_id: UUID,
    db: Optional[AsyncSession] = None,
    session_factory=None,
) -> int:
    """
    Get the curation interval setting for a family.

    Looks up the first user in the family with custom insight settings,
    falls back to DEFAULT_CURATION_INTERVAL_MINUTES.
    """
    from sqlalchemy import select
    from ..insight.models import UserInsightSettings

    async def _do_query(session: AsyncSession) -> int:
        result = await session.execute(
            select(UserInsightSettings.curation_interval_minutes)
            .where(UserInsightSettings.family_id == family_id)
            .limit(1)
        )
        interval = result.scalar_one_or_none()
        return interval if interval is not None else DEFAULT_CURATION_INTERVAL_MINUTES

    if db is not None:
        return await _do_query(db)
    if session_factory is not None:
        async with session_factory() as session:
            return await _do_query(session)
    raise ValueError("_get_family_curation_interval requires db or session_factory")


async def _should_skip_curation(
    family_id: UUID,
    min_interval_minutes: int,
    db: Optional[AsyncSession] = None,
    session_factory=None,
) -> bool:
    """
    Check whether curation should be skipped based on cooldown.

    Queries the CurationJob table for the most recent completed job
    for this family and checks whether enough time has elapsed.
    """
    from sqlalchemy import select, desc
    from .models import CurationJob

    async def _do_query(session: AsyncSession) -> bool:
        result = await session.execute(
            select(CurationJob.completed_at)
            .where(CurationJob.family_id == family_id)
            .where(CurationJob.status == "completed")
            .order_by(desc(CurationJob.completed_at))
            .limit(1)
        )
        last_completed = result.scalar_one_or_none()

        if last_completed is None:
            return False

        from ...core.utils.timezone import utc_now
        now = utc_now()
        if last_completed.tzinfo is None:
            last_completed = last_completed.replace(tzinfo=dt_tz.utc)

        elapsed = now - last_completed
        return elapsed < timedelta(minutes=min_interval_minutes)

    if db is not None:
        return await _do_query(db)
    if session_factory is not None:
        async with session_factory() as session:
            return await _do_query(session)
    raise ValueError("_should_skip_curation requires db or session_factory")


async def _check_auto_curate_setting(
    family_id: UUID,
    setting_name: str,
    db: Optional[AsyncSession] = None,
    session_factory=None,
) -> bool:
    """Check whether an auto-curate boolean setting is enabled for a family (defaults to True)."""
    from sqlalchemy import select
    from ..insight.models import UserInsightSettings

    column = getattr(UserInsightSettings, setting_name, None)
    if column is None:
        return True

    async def _do_query(query_db: AsyncSession) -> bool:
        result = await query_db.execute(
            select(column)
            .where(UserInsightSettings.family_id == family_id)
            .limit(1)
        )
        value = result.scalar_one_or_none()
        return value if value is not None else True

    if db is not None:
        return await _do_query(db)
    if session_factory is not None:
        async with session_factory() as session:
            return await _do_query(session)
    raise ValueError("_check_auto_curate_setting requires db or session_factory")


# Trigger types that use the full pipeline (not incremental)
_FULL_PIPELINE_TRIGGERS = {
    "manual",
    "event_requested",
    "event",
    "event_created",
    "event_updated",
    "event_deleted",
}

# Trigger types routed to incremental handlers
_INCREMENTAL_TRIGGERS = {
    "trip_created", "trip_updated", "trip_cancelled", "trip_deleted",
    "itinerary_updated", "memory_extracted", "date_approaching",
}

_DB_SAFE_JOB_TRIGGERS = {
    "scheduled",
    "event",
    "manual",
    "trip_created",
    "trip_updated",
    "trip_cancelled",
}


def _normalize_job_trigger_type(trigger_type: str) -> str:
    """Normalize trigger_type to values accepted by curation_jobs constraint."""
    if trigger_type in {"event_requested", "event_created", "event_updated", "event_deleted"}:
        return "event"
    if trigger_type == "trip_deleted":
        return "trip_cancelled"
    if trigger_type == "itinerary_updated":
        return "trip_updated"
    if trigger_type in _DB_SAFE_JOB_TRIGGERS:
        return trigger_type
    return "event"


async def _run_curation_for_family(
    family_id: UUID,
    date_range: tuple,
    trigger_type: str = "scheduled",
    session_factory=None,
    payload: Optional[dict] = None,
    existing_job_id: Optional[UUID] = None,
) -> dict:
    """
    Run curation for a single family.

    Routes to either:
    - TriggerDispatcher for incremental triggers (trip_*, memory_*, date_*)
    - Reconciliation for scheduled triggers
    - Full pipeline for manual/event_requested triggers

    Args:
        family_id: Family ID
        date_range: (start_date, end_date) tuple
        trigger_type: scheduled, event, manual, trip_created, etc.
        session_factory: Optional async session factory for Celery context
        payload: Event-specific data for incremental handlers
        existing_job_id: Existing curation_jobs.id to reuse (manual API trigger)

    Returns:
        dict with curation results
    """
    _ensure_curation_orm_models_loaded()

    if session_factory is None:
        raise ValueError("_run_curation_for_family requires session_factory")

    # Incremental path: use TriggerDispatcher
    if trigger_type in _INCREMENTAL_TRIGGERS:
        from .services.trigger_dispatcher import TriggerDispatcher
        from ...core.llm.haiku_client import get_haiku_client

        async with session_factory() as db:
            dispatcher = TriggerDispatcher(db, llm_provider=get_haiku_client())
            result = await dispatcher.dispatch(
                family_id, trigger_type, payload or {}
            )
            result["family_id"] = str(family_id)
            result["trigger_type"] = trigger_type
            return result

    # Scheduled path: use diff-based reconciliation
    if trigger_type == "scheduled":
        from .services.trigger_dispatcher import TriggerDispatcher
        from ...core.llm.haiku_client import get_haiku_client

        async with session_factory() as db:
            dispatcher = TriggerDispatcher(db, llm_provider=get_haiku_client())
            result = await dispatcher.reconcile(family_id, date_range)
            result["family_id"] = str(family_id)
            result["trigger_type"] = "scheduled"
            return result

    # Full pipeline path: manual, event_requested, or fallback
    from sqlalchemy import select
    from .services.curation_service import SecretaryCurationService
    from ..member.models import User

    async with session_factory() as db:
        user_stmt = select(User.id).where(User.family_id == family_id).limit(1)
        user_result = await db.execute(user_stmt)
        user_id = user_result.scalar_one_or_none()

        service = SecretaryCurationService(db)
        job_trigger_type = _normalize_job_trigger_type(trigger_type)
        result = await service.curate_family_events(
            family_id=family_id,
            date_range=date_range,
            trigger_type=job_trigger_type,
            user_id=user_id,
            existing_job_id=existing_job_id,
        )

        return {
            "family_id": str(family_id),
            "job_id": str(result.job_id),
            "events_processed": result.events_processed,
            "events_curated": result.events_curated,
            "associations_created": result.associations_created,
            "unconfirmed_count": len(result.unconfirmed_items),
            "conflicts_detected": result.conflicts_detected,
        }


async def _mark_existing_curation_job_skipped(
    existing_job_id: Optional[UUID],
    reason: str,
    session_factory=None,
) -> None:
    """Best-effort update for an existing curation_jobs row when execution is skipped."""
    if existing_job_id is None:
        return

    if session_factory is None:
        from ...db.session import AsyncSessionLocal
        session_factory = AsyncSessionLocal

    try:
        async with session_factory() as skip_db:
            from .models import CurationJob

            job = await skip_db.get(CurationJob, existing_job_id)
            if job is None:
                return
            job.status = "completed"
            if job.started_at is None:
                job.started_at = utc_now()
            job.completed_at = utc_now()
            job.error_message = f"Skipped curation: {reason}"
            await skip_db.commit()
    except Exception:
        logger.debug("Failed to mark curation job %s as skipped", existing_job_id, exc_info=True)


async def _run_periodic_curation() -> dict:
    """
    Run curation for all active families that have exceeded their interval.

    Called every 15 minutes by Celery Beat. Each family's actual execution
    is gated by its curation_interval_minutes setting + cooldown check.

    Returns:
        Summary of curation results
    """
    today = local_today()

    engine, session_factory = create_celery_async_session()
    try:
        families = await get_active_families(session_factory)

        if not families:
            logger.info("No active families to curate")
            return {"status": "no_families", "count": 0}

        logger.info(f"Periodic curation check for {len(families)} families")

        results = []
        skipped = 0
        errors = []

        async with session_factory() as db:
            from .services.should_run_service import CurationShouldRunService

            decision_service = CurationShouldRunService(db)
            for family_id in families:
                try:
                    interval = await _get_family_curation_interval(family_id, db=db)
                    family_settings = await get_family_curation_settings(
                        db,
                        family_id,
                        fallback_days_ahead=DAILY_CURATION_DAYS_AHEAD,
                    )
                    family_today = local_today(family_settings.timezone)
                    date_range = (
                        family_today,
                        family_today + timedelta(days=family_settings.curation_days_ahead),
                    )

                    if await _should_skip_curation(family_id, interval, db=db):
                        logger.debug(
                            "Skipping family %s: cooldown not elapsed (interval=%dmin)",
                            family_id,
                            interval,
                        )
                        skipped += 1
                        continue

                    decision = await decision_service.evaluate(
                        family_id=family_id,
                        date_range=date_range,
                        trigger_type="scheduled",
                        payload=None,
                    )
                    if not decision.should_run:
                        logger.debug(
                            "Skipping family %s: should_run=false (%s)",
                            family_id,
                            decision.reason,
                        )
                        skipped += 1
                        continue

                    # Curation itself uses its own session (heavy operation)
                    result = await _run_curation_for_family(
                        family_id=family_id,
                        date_range=date_range,
                        trigger_type="scheduled",
                        session_factory=session_factory,
                    )
                    results.append(result)
                    logger.debug(f"Curation completed for family {family_id}")

                except Exception as e:
                    error_msg = f"Curation failed for family {family_id}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        summary = {
            "status": "completed",
            "date": str(today),
            "date_range": "per_family",
            "total_families": len(families),
            "success_count": len(results),
            "skipped_count": skipped,
            "error_count": len(errors),
            "total_events_processed": sum(
                int(
                    r.get(
                        "events_processed",
                        (r.get("new_events", 0) + r.get("updated_events", 0) + r.get("orphaned_events", 0)),
                    )
                )
                for r in results
            ),
            "total_events_curated": sum(
                int(r.get("events_curated", (r.get("new_events", 0) + r.get("updated_events", 0))))
                for r in results
            ),
            "total_associations": sum(int(r.get("associations_created", 0)) for r in results),
            "errors": errors[:10] if errors else [],
        }

        logger.info(
            "Periodic curation completed: "
            "%d/%d executed, %d skipped, "
            "%d events curated, %d associations",
            summary['success_count'],
            summary['total_families'],
            summary['skipped_count'],
            summary['total_events_curated'],
            summary['total_associations'],
        )

        return summary
    finally:
        await engine.dispose()


@shared_task(
    name="secretary.daily_curation",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=10,
)
def daily_curation_task(self):
    """
    Celery task to run periodic curation for all families.

    Runs every 15 minutes via Celery Beat. Each family's execution
    is gated by its curation_interval_minutes setting and cooldown check.
    """
    logger.info("Starting periodic curation task")
    return run_async(_run_periodic_curation())


@shared_task(
    name="secretary.curate_family",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=10,
)
def curate_family_task(
    self, family_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    trigger_type: str = "event",
    respect_cooldown: bool = True,
    payload: Optional[dict] = None,
    existing_job_id: Optional[str] = None,
):
    """
    Celery task to curate events for a specific family.

    Can be called:
    - On-demand when user requests curation (respect_cooldown=False)
    - Event-driven when new trip/calendar data is added
    - As part of the periodic batch

    Args:
        payload: Event-specific data (trip_id, memory_id, etc.) for
                 incremental handlers via TriggerDispatcher.
    """
    logger.info(f"Starting curation for family {family_id} (trigger={trigger_type})")

    # Parse dates with error handling
    try:
        if start_date:
            start = date.fromisoformat(start_date)
        else:
            start = local_today()

        if end_date:
            end = date.fromisoformat(end_date)
        else:
            end = start + timedelta(days=DEFAULT_CURATION_DAYS_AHEAD)
    except ValueError as e:
        logger.error(f"Invalid date format: start_date={start_date}, end_date={end_date}, error={e}")
        raise ValueError(f"Invalid date format. Expected YYYY-MM-DD. Error: {e}")

    family_uuid = UUID(family_id)
    parsed_existing_job_id: Optional[UUID] = None
    if existing_job_id:
        try:
            parsed_existing_job_id = UUID(existing_job_id)
        except ValueError:
            logger.warning(
                "Invalid existing_job_id for curation task: %s",
                existing_job_id,
            )
    try:
        return run_async(
            _curate_family_with_cooldown(
                family_uuid, (start, end), trigger_type, respect_cooldown,
                payload=payload,
                existing_job_id=parsed_existing_job_id,
            )
        )
    finally:
        reschedule_sync("secretary.curate_family", family_id)


def _acquire_curation_lock(family_id: UUID, ttl_seconds: int = 300) -> bool:
    """Acquire a Redis distributed lock for curation of a specific family.

    Returns True if lock acquired, False if another curation is already running.
    Lock auto-expires after ttl_seconds as a safety net.
    """
    try:
        from ...core.cache import get_redis_client
        redis = get_redis_client()
        if redis is None:
            return True  # No Redis → allow (fallback to cooldown only)
        lock_key = f"curation:lock:{family_id}"
        acquired = redis.set(lock_key, "1", nx=True, ex=ttl_seconds)
        return bool(acquired)
    except Exception as e:
        logger.debug("Redis lock acquisition failed, proceeding anyway: %s", e)
        return True


def _release_curation_lock(family_id: UUID) -> None:
    """Release the Redis distributed lock for curation."""
    try:
        from ...core.cache import get_redis_client
        redis = get_redis_client()
        if redis is None:
            return
        lock_key = f"curation:lock:{family_id}"
        redis.delete(lock_key)
    except Exception as e:
        logger.debug("Redis lock release failed: %s", e)


async def _curate_family_with_cooldown(
    family_id: UUID,
    date_range: tuple,
    trigger_type: str,
    respect_cooldown: bool,
    payload: Optional[dict] = None,
    existing_job_id: Optional[UUID] = None,
) -> dict:
    """Single async entry point for curate_family_task."""
    # Distributed lock: only one curation per family at a time
    if not _acquire_curation_lock(family_id):
        await _mark_existing_curation_job_skipped(existing_job_id, "lock_held")
        logger.info(
            "Skipping family %s curation: another curation is already running",
            family_id,
        )
        return {
            "family_id": str(family_id),
            "status": "skipped",
            "reason": "lock_held",
        }

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            from .services.should_run_service import CurationShouldRunService

            decision_service = CurationShouldRunService(db)
            decision = await decision_service.evaluate(
                family_id=family_id,
                date_range=date_range,
                trigger_type=trigger_type,
                payload=payload,
            )
            if not decision.should_run:
                await _mark_existing_curation_job_skipped(
                    existing_job_id,
                    decision.reason,
                    session_factory=session_factory,
                )
                logger.info(
                    "Skipping family %s curation: should_run=false (%s)",
                    family_id,
                    decision.reason,
                )
                return {
                    "family_id": str(family_id),
                    "status": "skipped",
                    "reason": decision.reason,
                }

            # Cooldown is only applied to scheduled periodic runs.
            if respect_cooldown and trigger_type == "scheduled":
                interval = await _get_family_curation_interval(family_id, db=db)
                should_skip = await _should_skip_curation(family_id, interval, db=db)
                if should_skip:
                    await _mark_existing_curation_job_skipped(
                        existing_job_id,
                        "cooldown",
                        session_factory=session_factory,
                    )
                    logger.info(
                        "Skipping family %s curation: cooldown not elapsed (interval=%dmin)",
                        family_id,
                        interval,
                    )
                    return {
                        "family_id": str(family_id),
                        "status": "skipped",
                        "reason": "cooldown",
                    }

        return await _run_curation_for_family(
            family_id=family_id,
            date_range=date_range,
            trigger_type=trigger_type,
            session_factory=session_factory,
            payload=payload,
            existing_job_id=existing_job_id,
        )
    finally:
        _release_curation_lock(family_id)
        await engine.dispose()


def trigger_curation_async(
    family_id: UUID,
    trigger_type: str = "event",
    respect_cooldown: bool = True,
    payload: Optional[dict] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    existing_job_id: Optional[UUID] = None,
) -> bool:
    """
    Helper function to trigger async curation from other modules.

    Call this when:
    - A new trip plan is created/updated/deleted
    - Events are created/updated/deleted
    - Calendar data is synced
    - Schedule memories are extracted from conversations

    Args:
        payload: Event-specific data (trip_id, memory_id, etc.) passed
                 through to incremental handlers via TriggerDispatcher.
        start_date: Optional explicit curation range start.
        end_date: Optional explicit curation range end.
        existing_job_id: Existing curation_jobs.id to reuse for status tracking.

    Returns:
        True if the task was successfully dispatched, False on broker error.
    """
    try:
        curate_family_task.delay(
            family_id=str(family_id),
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            trigger_type=trigger_type,
            respect_cooldown=respect_cooldown,
            payload=payload,
            existing_job_id=str(existing_job_id) if existing_job_id else None,
        )
        logger.info(f"Triggered curation for family {family_id} (type: {trigger_type})")
        return True
    except Exception as e:
        logger.error(
            "Failed to dispatch curation task for family %s: %s",
            family_id,
            e,
        )
        return False


@shared_task(name="secretary.discover_associations_for_event")
def discover_associations_for_event_task(event_id: str, family_id: str) -> dict:
    """Run association discovery for a single curated event (post mini_curate)."""
    return run_async(_discover_associations_for_event_async(event_id, family_id))


async def _discover_associations_for_event_async(event_id: str, family_id: str) -> dict:
    """Async implementation of single-event association discovery."""
    from .services.curation_service import SecretaryCurationService

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            from sqlalchemy import select
            from .models import CuratedEvent

            ev_uuid = UUID(event_id)
            fam_uuid = UUID(family_id)

            result = await db.execute(
                select(CuratedEvent).where(CuratedEvent.id == ev_uuid)
            )
            event = result.scalar_one_or_none()
            if not event:
                return {"status": "skipped", "reason": "event_not_found"}

            service = SecretaryCurationService(db)
            family_settings = await get_family_curation_settings(db, fam_uuid)
            tz_token = set_active_timezone(family_settings.timezone)
            today = local_today(family_settings.timezone)
            date_range = (
                today,
                today + timedelta(days=family_settings.curation_days_ahead),
            )
            try:
                associations = await service._discover_associations(
                    fam_uuid, [event], date_range
                )
                await service._store_associations(associations)
                await db.commit()
            finally:
                reset_active_timezone(tz_token)

            return {
                "event_id": event_id,
                "associations_created": len(associations),
            }
    except Exception as e:
        logger.error("Association discovery failed for event %s: %s", event_id, e)
        return {"status": "error", "error": str(e)}
    finally:
        await engine.dispose()


async def trigger_curation_if_enabled(
    family_id: UUID,
    setting_name: str,
    trigger_type: str,
    payload: Optional[dict] = None,
    respect_cooldown: bool = True,
    db: Optional[AsyncSession] = None,
    session_factory=None,
) -> None:
    """
    Check an auto-curate setting and trigger curation if enabled.

    Shared helper for trip_plan and event_service modules.
    Failures are logged but never propagated.
    """
    try:
        if db is None and session_factory is None:
            raise ValueError("trigger_curation_if_enabled requires db or session_factory")

        enabled = await _check_auto_curate_setting(
            family_id,
            setting_name,
            db=db,
            session_factory=session_factory,
        )
        if not enabled:
            logger.debug("%s disabled for family %s, skipping", setting_name, family_id)
            return
        trigger_curation_async(
            family_id,
            trigger_type=trigger_type,
            respect_cooldown=respect_cooldown,
            payload=payload,
        )
    except Exception as e:
        logger.warning("Failed to trigger curation (%s) for family %s: %s", trigger_type, family_id, e)


# ---------------------------------------------------------------------------
# Dirty-bit patrol — flush orphaned queues whose timers expired
# ---------------------------------------------------------------------------

async def _patrol_dirty_timers() -> dict:
    """Scan Redis for dirty:{family_id} keys without matching timers.

    When the anti-starvation timer expires (TTL-based), queued entries can
    remain orphaned if no new mark_dirty() call re-triggers the threshold
    check.  This patrol runs every 5 minutes to catch those orphans and
    flush them into curation tasks.
    """
    from ...core.cache import RedisClient
    from .services.dirty_bit_manager import DirtyBitManager

    # Create a fresh Redis connection bound to the CURRENT task loop.
    # Avoid reusing global async clients in Celery task code to keep
    # loop-bound resources isolated and teardown-safe.
    _redis = RedisClient()
    try:
        await _redis.connect()
    except Exception as e:
        logger.warning("patrol_dirty_timers: Redis connect failed: %s", e)
        return {"status": "skipped", "reason": "no_redis"}

    if _redis.client is None:
        logger.warning("patrol_dirty_timers: Redis not available, skipping")
        return {"status": "skipped", "reason": "no_redis"}

    try:
        manager = DirtyBitManager(_redis)
        stale_families = await manager.get_stale_families()

        if not stale_families:
            return {"status": "ok", "flushed": 0}

        flushed = 0
        errors = []
        for family_id in stale_families:
            try:
                entries = await manager.flush_dirty(family_id)
                if entries:
                    flushed += 1
                    logger.info(
                        "patrol_dirty_timers: flushed %d entries for family=%s",
                        len(entries), family_id,
                    )
                    # Dispatch curation for the flushed family
                    try:
                        trigger_curation_async(
                            family_id=UUID(family_id),
                            trigger_type="event",
                            respect_cooldown=True,
                        )
                    except Exception as dispatch_err:
                        logger.warning(
                            "patrol_dirty_timers: dispatch failed for family=%s: %s",
                            family_id, dispatch_err,
                        )
            except Exception as e:
                logger.warning(
                    "patrol_dirty_timers: flush failed for family=%s: %s",
                    family_id, e,
                )
                errors.append(str(e))

        return {
            "status": "ok",
            "stale_families": len(stale_families),
            "flushed": flushed,
            "errors": errors[:5] if errors else [],
        }
    finally:
        await _redis.disconnect()


@shared_task(
    name="secretary.patrol_dirty_timers",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=1,
    default_retry_delay=10,
)
def patrol_dirty_timers_task(self):
    """Celery task: scan for dirty queues with expired timers and flush them."""
    logger.info("Starting patrol_dirty_timers")
    return run_async(_patrol_dirty_timers())


# ---------------------------------------------------------------------------
# T0 Proactive trigger scan
# ---------------------------------------------------------------------------

def _format_trigger_text(trigger) -> str:
    """Format trigger as natural language text."""
    t = trigger.trigger_type
    d = trigger.data if hasattr(trigger, "data") else {}
    if t == "approaching_date":
        return "%s还有%s天，需要准备什么吗？" % (
            d.get("title", "重要日期"),
            d.get("days_until", "?"),
        )
    if t == "cold_relationship":
        return "好久没和%s联系了，要不要问候一下？" % d.get("member_name", "对方")
    if t == "stale_commitment":
        return "您之前说要%s，需要跟进吗？" % d.get("what", "...")
    if t == "user_rhythm":
        return "今天还没看到您，一切都好吗？"
    return "有一件事想提醒您。"


async def _deliver_proactive_trigger(
    family_id: UUID,
    trigger,
    db: AsyncSession,
) -> None:
    """Deliver proactive trigger through three channels:
    1. Push notification (immediate)
    2. BriefingAccumulator (daily briefing)
    3. Redis cache (conversation context)
    """
    text = _format_trigger_text(trigger)

    # Channel 1: Push notification
    try:
        from ...core.push.notification_provider import app_notification_provider
        from ...core.interfaces.notification_provider import (
            NotificationChannel,
            NotificationPriority,
        )
        from ...modules.member.models import Member
        from sqlalchemy import select as sa_select

        stmt = sa_select(Member.user_id).where(
            Member.family_id == family_id
        )
        result = await db.execute(stmt)
        user_ids = [row[0] for row in result.fetchall()]
        for user_id in user_ids:
            if user_id:
                push_priority = (
                    NotificationPriority.HIGH
                    if trigger.priority == "P0"
                    else NotificationPriority.NORMAL
                )
                await app_notification_provider.send_notification(
                    channel=NotificationChannel.PUSH,
                    recipient=str(user_id),
                    title="秘书提醒",
                    content=text,
                    priority=push_priority,
                    metadata={
                        "trigger_type": trigger.trigger_type,
                        "family_id": str(family_id),
                        "trigger_data": trigger.data if hasattr(trigger, "data") and isinstance(trigger.data, dict) else {},
                    },
                )
    except Exception as e:
        logger.debug("Push notification failed: %s", e)

    # Channel 2: BriefingAccumulator
    try:
        from ...modules.briefing.services.accumulator import BriefingAccumulator

        acc = BriefingAccumulator()
        await acc.on_proactive_trigger(
            family_id=family_id,
            trigger_type=trigger.trigger_type,
            trigger_data=trigger.data if hasattr(trigger, "data") else {},
            priority=trigger.priority,
        )
    except Exception as e:
        logger.debug("BriefingAccumulator failed: %s", e)

    # Channel 3: Redis cache for conversation context
    # Use a fresh RedisClient to avoid "Event loop is closed" errors
    # when running inside Celery workers (same pattern as _patrol_dirty_timers).
    _redis = None
    try:
        import json as _json

        from ...core.cache import RedisClient

        _redis = RedisClient()
        await _redis.connect()
        client = _redis.client
        if client is not None:
            key = "curation:proactive:%s" % str(family_id)
            item = _json.dumps(
                {
                    "type": trigger.trigger_type,
                    "text": text,
                    "priority": trigger.priority,
                    "data": trigger.data if hasattr(trigger, "data") else {},
                },
                ensure_ascii=False,
                default=str,
            )
            await client.lpush(key, item)
            await client.ltrim(key, 0, 9)  # Keep last 10
            await client.expire(key, 86400)  # 24h TTL
    except Exception as e:
        logger.debug("Redis cache failed: %s", e)
    finally:
        if _redis is not None:
            try:
                await _redis.disconnect()
            except Exception:
                pass


async def _run_proactive_scan() -> dict:
    """Run proactive trigger scan for all active families.

    Returns summary of discovered triggers.
    """
    from .services.proactive_triggerer import ProactiveTriggerer

    engine, session_factory = create_celery_async_session()
    try:
        families = await get_active_families(session_factory)
        if not families:
            logger.info("proactive_scan: no active families")
            return {"status": "no_families", "total_triggers": 0}

        total_triggers = 0
        families_with_triggers = 0
        errors: List[str] = []

        for family_id in families:
            try:
                async with session_factory() as db:
                    triggerer = ProactiveTriggerer(db)
                    triggers = await triggerer.scan_for_triggers(family_id)
                    if triggers:
                        families_with_triggers += 1
                        total_triggers += len(triggers)
                        logger.info(
                            "proactive_scan: family %s -> %d triggers",
                            family_id, len(triggers),
                        )
                        # Dispatch each trigger as a curation task with
                        # the appropriate trigger type
                        for trigger in triggers:
                            try:
                                trigger_curation_async(
                                    family_id=family_id,
                                    trigger_type="date_approaching"
                                    if trigger.trigger_type == "approaching_date"
                                    else "event",
                                    payload=trigger.data,
                                    respect_cooldown=False,
                                )
                            except Exception as dispatch_err:
                                logger.warning(
                                    "proactive_scan: dispatch failed for trigger %s: %s",
                                    trigger.trigger_type, dispatch_err,
                                )

                            # Path 2: User notification -- only for P0/P1
                            if trigger.priority in ("P0", "P1"):
                                try:
                                    await _deliver_proactive_trigger(
                                        family_id, trigger, db,
                                    )
                                except Exception as notify_err:
                                    logger.warning(
                                        "proactive_scan: notification failed "
                                        "for trigger %s: %s",
                                        trigger.trigger_type, notify_err,
                                    )
            except Exception as e:
                error_msg = f"proactive_scan failed for family {family_id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        summary = {
            "status": "completed",
            "total_families": len(families),
            "families_with_triggers": families_with_triggers,
            "total_triggers": total_triggers,
            "errors": errors[:5] if errors else [],
        }
        logger.info(
            "proactive_scan: %d families, %d triggers from %d families",
            len(families), total_triggers, families_with_triggers,
        )
        return summary
    finally:
        await engine.dispose()


@shared_task(
    name="secretary.proactive_scan",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=30,
)
def proactive_scan_task(self):
    """Celery task: T0 proactive trigger scan for all families.

    Runs daily at 08:00 via Celery Beat to discover situations where
    the secretary should proactively reach out.
    """
    logger.info("Starting proactive trigger scan")
    return run_async(_run_proactive_scan())


# ---------------------------------------------------------------------------
# Preference learning — consolidate feedback into FamilyPreference
# ---------------------------------------------------------------------------

async def _run_preference_consolidation() -> dict:
    """Consolidate feedback signals into FamilyPreference for all families."""
    engine, session_factory = create_celery_async_session()
    try:
        families = await get_active_families(session_factory)
        if not families:
            logger.info("consolidate_preferences: no active families")
            return {"status": "no_families", "families": 0}

        success = 0
        errors: List[str] = []

        for family_id in families:
            try:
                async with session_factory() as db:
                    from .services.preference_learner import PreferenceLearner

                    learner = PreferenceLearner(db)
                    await learner.consolidate(family_id)
                    await db.commit()
                    success += 1
            except Exception as e:
                error_msg = (
                    f"consolidate_preferences failed for family {family_id}: {e}"
                )
                logger.error(error_msg)
                errors.append(error_msg)

        summary = {
            "status": "completed",
            "families": len(families),
            "success": success,
            "errors": errors[:5] if errors else [],
        }
        logger.info(
            "consolidate_preferences: %d/%d families succeeded",
            success, len(families),
        )
        return summary
    finally:
        await engine.dispose()


@shared_task(
    name="curation.consolidate_preferences",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=30,
)
def consolidate_preferences_task(self):
    """Daily Celery task: consolidate feedback into FamilyPreference rules.

    Reads insight_feedbacks and event_associations from the last 90 days,
    applies exponential-decay weighting, and updates the JSONB columns in
    family_preferences.
    """
    logger.info("Starting preference consolidation")
    return run_async(_run_preference_consolidation())


# ---------------------------------------------------------------------------
# INSIGHT_IGNORED auto-detection -- 24h with no action
# ---------------------------------------------------------------------------

_INSIGHT_IGNORED_THRESHOLD_HOURS = 24


async def _run_check_ignored_insights() -> dict:
    """Scan unified insights table for stale pending/active entries.

    For each insight older than 24h still in 'pending' or 'active' status
    with no feedback, emit INSIGHT_IGNORED to the FeedbackBus and mark
    as 'expired'.
    """
    from sqlalchemy import select, and_, update

    from ..insight.models import Insight, InsightStatus
    from ...core.feedback.feedback_bus import (
        FeedbackBus,
        FeedbackSignal,
        FeedbackEvent,
    )

    engine, session_factory = create_celery_async_session()
    try:
        now = utc_now()
        cutoff = now - timedelta(hours=_INSIGHT_IGNORED_THRESHOLD_HOURS)

        async with session_factory() as db:
            bus = FeedbackBus.get_instance()

            stmt = (
                select(Insight)
                .where(
                    and_(
                        Insight.created_at < cutoff,
                        Insight.status.in_([
                            InsightStatus.PENDING.value,
                            InsightStatus.ACTIVE.value,
                        ]),
                        Insight.feedback.is_(None),
                    ),
                )
                .limit(500)
            )
            result = await db.execute(stmt)
            stale = result.scalars().all()

            if not stale:
                return {"status": "ok", "expired_count": 0}

            events: List = []
            stale_ids: List[UUID] = []
            for insight in stale:
                events.append(FeedbackEvent(
                    signal=FeedbackSignal.INSIGHT_IGNORED,
                    family_id=insight.family_id,
                    user_id=insight.user_id,
                    data={
                        "insight_id": str(insight.id),
                        "insight_type": insight.insight_type,
                        "title": insight.title,
                        "created_at": insight.created_at.isoformat()
                        if insight.created_at else None,
                    },
                    source="check_ignored_insights",
                ))
                stale_ids.append(insight.id)

            await db.execute(
                update(Insight)
                .where(Insight.id.in_(stale_ids))
                .values(status=InsightStatus.EXPIRED.value)
            )

            await bus.emit_batch(events)
            await db.commit()

            logger.info(
                "check_ignored_insights: marked %d insights as expired",
                len(stale_ids),
            )
            return {
                "status": "completed",
                "expired_count": len(stale_ids),
            }
    except Exception as e:
        logger.error("check_ignored_insights failed: %s", e, exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        await engine.dispose()


@shared_task(
    name="curation.check_ignored_insights",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=30,
)
def check_ignored_insights_task(self):
    """Celery task: detect insights that have been ignored for 24h.

    Runs every 6 hours via Celery Beat. Scans the unified insights table for
    entries older than 24h still in 'pending' or 'active' status with no
    feedback, emits INSIGHT_IGNORED to the FeedbackBus, and marks them as
    'expired'.
    """
    logger.info("Starting check_ignored_insights scan")
    return run_async(_run_check_ignored_insights())


@shared_task(
    name="secretary.post_session_reflection",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def post_session_reflection_task(
    self, session_id: str, user_id: str, family_id: str
) -> dict:
    """Celery task: immediately reflect on a freshly archived session.

    Extracts entities (trip_ids, member_names, important_dates) from the
    session and triggers focused curation for each, eliminating the up-to-24h
    delay of the daily scheduler.
    """
    logger.info(
        "Starting post_session_reflection for session=%s user=%s family=%s",
        session_id,
        user_id,
        family_id,
    )
    return run_async(
        _run_post_session_reflection(session_id, user_id, family_id)
    )


async def _run_post_session_reflection(
    session_id: str,
    user_id: str,
    family_id: str,
) -> dict:
    """Async implementation of post-session reflection."""
    _ensure_curation_orm_models_loaded()

    from ...core.llm.haiku_client import get_haiku_client
    from .services.reflection_service import PostSessionReflectionService

    session_uuid = UUID(session_id)
    user_uuid = UUID(user_id)
    family_uuid = UUID(family_id)

    client = get_haiku_client()
    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            service = PostSessionReflectionService(db, llm_provider=client)
            await service.reflect(session_uuid, user_uuid, family_uuid)
            return {
                "status": "completed",
                "session_id": session_id,
                "family_id": family_id,
            }
    except Exception as exc:
        logger.error(
            "post_session_reflection task failed for session %s: %s",
            session_id,
            exc,
        )
        return {"status": "error", "error": str(exc)}
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Phase 6 — Meal window inference tasks
# ---------------------------------------------------------------------------

@shared_task(
    name="secretary.infer_meal_windows",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def infer_meal_windows_task(self, family_id: str) -> dict:
    """Infer meal windows for a single family from historical event timing."""
    logger.info("Starting meal window inference for family=%s", family_id)
    return run_async(_run_infer_meal_windows(family_id))


@shared_task(
    name="secretary.infer_all_meal_windows",
    bind=True,
)
def infer_all_meal_windows_task(self) -> dict:
    """Weekly task (Sunday 3 AM): infer meal windows for all active families."""
    logger.info("Starting meal window inference for all families")
    return run_async(_run_infer_all_meal_windows())


async def _run_infer_meal_windows(family_id: str) -> dict:
    """Async implementation: infer meal windows for one family."""
    _ensure_curation_orm_models_loaded()

    from .services.meal_window_service import MealWindowInferenceService

    family_uuid = UUID(family_id)
    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            service = MealWindowInferenceService(db)
            updated = await service.infer_and_save(family_uuid)
            await db.commit()
            return {
                "status": "completed",
                "family_id": family_id,
                "updated": updated,
            }
    except Exception as exc:
        logger.error(
            "infer_meal_windows task failed for family %s: %s", family_id, exc,
        )
        return {"status": "error", "family_id": family_id, "error": str(exc)}
    finally:
        await engine.dispose()


async def _run_infer_all_meal_windows() -> dict:
    """Async implementation: iterate all active families and infer meal windows."""
    _ensure_curation_orm_models_loaded()

    from .services.meal_window_service import MealWindowInferenceService

    engine, session_factory = create_celery_async_session()
    total = updated = errors = 0
    try:
        async with session_factory() as db:
            families = await get_active_families(db)
            for family in families:
                total += 1
                try:
                    service = MealWindowInferenceService(db)
                    was_updated = await service.infer_and_save(family.id)
                    await db.flush()
                    if was_updated:
                        updated += 1
                except Exception as exc:
                    logger.error(
                        "meal window inference failed for family %s: %s",
                        family.id, exc,
                    )
                    errors += 1
            await db.commit()
        return {
            "status": "completed",
            "total_families": total,
            "updated": updated,
            "errors": errors,
        }
    except Exception as exc:
        logger.error("infer_all_meal_windows task failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# E2 — Preference extraction tasks
# ---------------------------------------------------------------------------

@shared_task(
    name="secretary.extract_preference_rules",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def extract_preference_rules_task(self) -> dict:
    """Daily task (05:00): extract preference rules from accumulated signals."""
    logger.info("Starting preference rule extraction for all users")
    return run_async(_run_extract_preference_rules())


async def _run_extract_preference_rules() -> dict:
    """Async implementation: extract preference rules from all pending signals."""
    _ensure_curation_orm_models_loaded()

    from .services.preference_extraction_service import PreferenceExtractionService

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            service = PreferenceExtractionService(db)
            total_rules = await service.extract_all_pending()
            await db.commit()
            return {
                "status": "completed",
                "rules_created": total_rules,
            }
    except Exception as exc:
        logger.error("extract_preference_rules task failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# E5 — Fatigue state refresh
# ---------------------------------------------------------------------------

@shared_task(
    name="secretary.refresh_fatigue_state",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def refresh_fatigue_state_task(self) -> dict:
    """Daily task (05:30): update fatigue_state for all families (E5)."""
    logger.info("Starting fatigue state refresh for all families")
    return run_async(_run_refresh_fatigue_state())


async def _run_refresh_fatigue_state() -> dict:
    """Compute and update fatigue_state for all families with preferences."""
    _ensure_curation_orm_models_loaded()

    from sqlalchemy import select, and_, func

    from .models import CuratedEvent, FamilyPreference
    from ..memory.models import ConversationMemory, MemoryStatus

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            # Get all family IDs with preferences
            stmt = select(FamilyPreference.family_id)
            result = await db.execute(stmt)
            family_ids = [row[0] for row in result.all()]

            if not family_ids:
                return {"status": "ok", "families_updated": 0}

            updated = 0
            errors_list: List[str] = []
            for fid in family_ids:
                try:
                    await _update_family_fatigue(db, fid)
                    updated += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to update fatigue for family %s: %s",
                        fid, exc,
                    )
                    errors_list.append(f"{fid}: {exc}")

            await db.commit()
            return {
                "status": "completed",
                "families_updated": updated,
                "errors": errors_list[:5] if errors_list else [],
            }
    except Exception as exc:
        logger.error("refresh_fatigue_state task failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        await engine.dispose()


async def _update_family_fatigue(
    session: AsyncSession,
    family_id: UUID,
) -> None:
    """Compute fatigue state for a single family.

    Metrics collected:
    - consecutive_high_density_days: number of consecutive days (up to 7)
      with >= 5 active curated events (7:00-23:00 window)
    - health_negative_7d: count of health-type memories in the last 7 days
    """
    from sqlalchemy import select, and_, func, literal_column
    from .models import CuratedEvent, FamilyPreference
    from ..memory.models import ConversationMemory, MemoryStatus

    now = utc_now()
    today = now.date()

    # Count consecutive high-density days (up to 7) — single GROUP BY query
    seven_days_ago = today - timedelta(days=6)
    all_start = datetime.combine(seven_days_ago, datetime.min.time()).replace(
        hour=7, tzinfo=dt_tz.utc,
    )
    all_end = datetime.combine(today, datetime.min.time()).replace(
        hour=23, tzinfo=dt_tz.utc,
    )

    # Use literal_column so 'day' renders as a SQL literal, not a bind param.
    # Otherwise PostgreSQL sees $1 in SELECT vs $5 in GROUP BY and can't match.
    day_trunc = func.date_trunc(literal_column("'day'"), CuratedEvent.normalized_start)
    density_stmt = (
        select(
            day_trunc.label('day'),
            func.count(CuratedEvent.id).label('cnt'),
        )
        .where(
            and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.normalized_start >= all_start,
                CuratedEvent.normalized_start <= all_end,
            )
        )
        .group_by(day_trunc)
    )
    density_result = await session.execute(density_stmt)
    day_counts = {
        row.day.date() if hasattr(row.day, 'date') else row.day: row.cnt
        for row in density_result
    }

    consecutive = 0
    for offset in range(7):
        check_date = today - timedelta(days=offset)
        if day_counts.get(check_date, 0) >= 5:
            consecutive += 1
        else:
            break

    # Count health-related memories in the last 7 days
    since_7d = now - timedelta(days=7)
    health_stmt = (
        select(func.count())
        .select_from(ConversationMemory)
        .where(
            and_(
                ConversationMemory.family_id == family_id,
                ConversationMemory.status == MemoryStatus.ACTIVE.value,
                ConversationMemory.memory_type == "health",
                ConversationMemory.created_at >= since_7d,
            )
        )
    )
    health_result = await session.execute(health_stmt)
    health_neg = health_result.scalar() or 0

    # Update fatigue_state on the FamilyPreference row
    pref_stmt = (
        select(FamilyPreference)
        .where(FamilyPreference.family_id == family_id)
        .with_for_update()
    )
    pref_result = await session.execute(pref_stmt)
    pref = pref_result.scalar_one_or_none()
    if pref is None:
        return

    pref.fatigue_state = {
        "consecutive_high_density_days": consecutive,
        "health_negative_7d": health_neg,
        "updated_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# E8 — Placeholder event auto-expiry
# ---------------------------------------------------------------------------

@shared_task(
    name="secretary.expire_stale_placeholders",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def expire_stale_placeholders_task(self) -> dict:
    """Expire placeholder events whose source event ended >24h ago (E8)."""
    logger.info("Starting stale placeholder expiry scan")
    return run_async(_run_expire_stale_placeholders())


async def _run_expire_stale_placeholders() -> dict:
    """Async implementation: expire placeholders whose source events have ended."""
    _ensure_curation_orm_models_loaded()

    from sqlalchemy import select, and_

    from .models import CuratedEvent

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            now = utc_now()
            cutoff = now - timedelta(hours=24)

            # Find all active placeholder events
            placeholder_stmt = (
                select(CuratedEvent)
                .where(
                    and_(
                        CuratedEvent.status == "placeholder",
                        CuratedEvent.is_active.is_(True),
                    )
                )
            )
            result = await db.execute(placeholder_stmt)
            placeholders = result.scalars().all()

            expired_count = 0

            # Pre-fetch all source events in one batch query
            all_source_ids = set()
            for ph in placeholders:
                if ph.original_event_ids:
                    for sid in ph.original_event_ids:
                        try:
                            all_source_ids.add(UUID(str(sid)))
                        except (ValueError, TypeError):
                            pass

            source_events_map = {}
            if all_source_ids:
                source_stmt = select(CuratedEvent).where(
                    CuratedEvent.id.in_(list(all_source_ids))
                )
                source_result = await db.execute(source_stmt)
                for ev in source_result.scalars().all():
                    source_events_map[ev.id] = ev

            for ph in placeholders:
                should_expire = False

                # Case 1: placeholder itself has passed (>24h after its end)
                if ph.normalized_end is not None and ph.normalized_end < cutoff:
                    should_expire = True

                # Case 2: source event ended >24h ago
                if not should_expire and ph.original_event_ids:
                    for sid in ph.original_event_ids:
                        try:
                            src_uuid = UUID(str(sid))
                        except (ValueError, TypeError):
                            continue
                        src_event = source_events_map.get(src_uuid)
                        if (
                            src_event is not None
                            and src_event.normalized_end is not None
                            and src_event.normalized_end < cutoff
                        ):
                            should_expire = True
                            break

                if should_expire:
                    ph.is_active = False
                    ph.status = "expired"
                    expired_count += 1

            await db.commit()
            logger.info(
                "Placeholder expiry complete: expired=%d, total_checked=%d",
                expired_count, len(placeholders),
            )
            return {"status": "completed", "expired_count": expired_count}

    except Exception as exc:
        logger.error("expire_stale_placeholders task failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        await engine.dispose()
