"""
Proactive Insight Tasks - Celery tasks for memory system background jobs

This module provides scheduled tasks for:
- Daily proactive insight generation (6:00 AM)
- Weekly memory consolidation (Sunday 3:00 AM)
- Secretary note generation (after consolidation)
"""

from datetime import date, datetime
from typing import Any, Callable, Coroutine, Dict, List

from celery import shared_task

from ...config.logging import get_logger
from ...core.scheduler._async_compat import run_async
from ...core.scheduler.reschedule import reschedule_sync
from ...core.utils.timezone import local_today, utc_now
from ...db.session import create_celery_async_session

logger = get_logger(__name__)


async def _run_for_all_active_users(
    task_name: str,
    per_user_fn: Callable,
    result_keys: Dict[str, str],
) -> Dict[str, Any]:
    """Run an async function for each active user with standard error handling.

    Args:
        task_name: Human-readable name for logging.
        per_user_fn: Async callable ``(session, user) -> dict`` executed per user.
            The returned dict is merged into results via *result_keys*.
        result_keys: Mapping from per-user result key to aggregate result key.
            Values are summed across users.

    Returns:
        Aggregated results dict with users_processed, errors, and summed keys.
    """
    from ..member.models import User
    from sqlalchemy import select

    results: Dict[str, Any] = {
        "users_processed": 0,
        "errors": [],
    }
    for key in result_keys.values():
        results[key] = 0

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as session:
            try:
                query = select(User).where(User.is_active == True)
                result = await session.execute(query)
                users = list(result.scalars().all())

                for user in users:
                    try:
                        user_result = await per_user_fn(session, user)
                        results["users_processed"] += 1
                        for src_key, dst_key in result_keys.items():
                            results[dst_key] += user_result.get(src_key, 0)
                        if user_result.get("errors"):
                            results["errors"].extend(user_result["errors"])
                    except Exception as e:
                        logger.error(
                            "%s failed for user %s: %s",
                            task_name, user.id, e,
                        )
                        results["errors"].append(
                            "User %s: %s" % (user.id, str(e))
                        )

                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("%s failed: %s", task_name, e)
                results["errors"].append(str(e))
    finally:
        await engine.dispose()

    logger.info("%s complete: %s", task_name, results)
    return results


@shared_task(
    name="assistant.generate_proactive_insights",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=10,
)
def generate_proactive_insights_task(self) -> Dict[str, Any]:
    """DEPRECATED (PLAN-004): No-op. Beat schedule entry kept for one release cycle.

    Proactive insights are now generated exclusively via
    ``secretary.prepare_daily_content`` → ``InsightOrchestrator.generate_all()``.
    This task created a duplicate generation path (06:00 + 08:00) writing to
    two separate tables. Hard-remove in Group E (PLAN-016) after one release cycle.

    Caller chain audit:
    - ``secretary.proactive_scan`` → ``InsightOrchestrator.generate_all()`` — unaffected
    - ``recommendation_engine.py`` → ``InsightOrchestrator.generate_all()`` — unaffected
    """
    logger.warning(
        "DEPRECATED: assistant.generate_proactive_insights is a no-op. "
        "Proactive insight generation is handled by secretary.prepare_daily_content. "
        "Remove this beat schedule entry after one release cycle (PLAN-016)."
    )
    return {"status": "deprecated", "insights_generated": 0}


@shared_task(
    name="assistant.consolidate_memories",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=10,
)
def consolidate_memories_task(self) -> Dict[str, Any]:
    """
    Consolidate memories for all active users.

    Scheduled to run at 3:00 AM on Sundays (weekly consolidation).

    Returns:
        Summary of consolidation results
    """
    return run_async(_consolidate_memories_async())


async def _consolidate_memories_async() -> Dict[str, Any]:
    """Async implementation of memory consolidation."""
    from .consolidation_service import MemoryConsolidationService

    async def _per_user(session, user):
        svc = MemoryConsolidationService(session)
        r = await svc.consolidate_weekly_memories(
            user_id=user.id,
            family_id=user.family_id,
            days_back=7,
        )
        return {
            "memories_count": r.get("memories_processed", 0),
            "profiles_count": r.get("person_profiles_updated", 0),
            "summaries_count": r.get("summaries_created", 0),
            "errors": r.get("errors", []),
        }

    return await _run_for_all_active_users(
        "Memory consolidation",
        _per_user,
        {
            "memories_count": "memories_consolidated",
            "profiles_count": "profiles_updated",
            "summaries_count": "summaries_created",
        },
    )


@shared_task(
    name="assistant.generate_secretary_notes",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=10,
)
def generate_secretary_notes_task(self) -> Dict[str, Any]:
    """
    Generate secretary notes for all active users.

    Can be triggered after memory consolidation or on demand.

    Returns:
        Summary of note generation results
    """
    return run_async(_generate_secretary_notes_async())


async def _generate_secretary_notes_async() -> Dict[str, Any]:
    """Async implementation of secretary note generation."""
    from .secretary_note_service import SecretaryNoteService

    async def _per_user(session, user):
        svc = SecretaryNoteService(session)
        notes = await svc.generate_notes_from_memories(
            user_id=user.id,
            family_id=user.family_id,
            days_back=30,
        )
        return {"notes_count": len(notes)}

    return await _run_for_all_active_users(
        "Secretary note generation",
        _per_user,
        {"notes_count": "notes_generated"},
    )


@shared_task(
    name="assistant.cleanup_expired_insights",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=10,
)
def cleanup_expired_insights_task(self) -> Dict[str, Any]:
    """
    Clean up expired proactive insights.

    Scheduled to run daily at 4:00 AM.

    Returns:
        Summary of cleanup results
    """
    return run_async(_cleanup_expired_insights_async())


async def _cleanup_expired_insights_async() -> Dict[str, Any]:
    """Async implementation of insight cleanup.

    Delegates to InsightHygiene which handles all 9 cleanup steps
    for the unified insights table.
    """
    from ..insight.models import Insight, InsightStatus
    from sqlalchemy import update, and_

    results = {
        "insights_expired": 0,
        "errors": [],
    }

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as session:
            try:
                now = utc_now()

                # Expire insights past their expires_at
                result = await session.execute(
                    update(Insight)
                    .where(
                        and_(
                            Insight.expires_at.isnot(None),
                            Insight.expires_at < now,
                            Insight.status.in_([
                                InsightStatus.PENDING.value,
                                InsightStatus.ACTIVE.value,
                            ]),
                        )
                    )
                    .values(status=InsightStatus.EXPIRED.value)
                )
                results["insights_expired"] = result.rowcount

                await session.commit()

            except Exception as e:
                await session.rollback()
                logger.error("Insight cleanup failed: %s", e)
                results["errors"].append(str(e))
    finally:
        await engine.dispose()

    logger.info("Insight cleanup complete: %s", results)
    return results


@shared_task(
    name="assistant.compress_daily_memories",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=10,
)
def compress_daily_memories_task(self) -> Dict[str, Any]:
    """
    Compress memories from 7 days ago for all active users.

    Scheduled to run daily at 4:30 AM.
    """
    return run_async(_compress_daily_memories_async())


async def _compress_daily_memories_async() -> Dict[str, Any]:
    """Async implementation of daily memory compression."""
    from .compression_service import MemoryCompressionService

    results: Dict[str, Any] = {
        "users_processed": 0,
        "total_compressed": 0,
        "errors": [],
    }

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as session:
            try:
                service = MemoryCompressionService(session)
                user_results = await service.run_daily_compression(days_ago=7)

                for user_id, cr in user_results.items():
                    results["users_processed"] += 1
                    results["total_compressed"] += cr.memories_compressed
                    if cr.errors:
                        results["errors"].append(f"User {user_id}: {cr.errors} error(s)")

                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error("Daily memory compression failed: %s", e)
                results["errors"].append(str(e))
    finally:
        await engine.dispose()

    logger.info("Daily memory compression complete: %s", results)
    return results


# ============ Agentic Extraction Cache Tasks ============


@shared_task(name="assistant.warmup_extraction_cache")
def warmup_extraction_cache_task() -> Dict[str, Any]:
    """
    Warm up the agentic extraction cache with common phrases.

    Scheduled to run at startup and periodically to ensure
    common intents are cached for fast response times.

    Returns:
        Summary of cache warmup results
    """
    return run_async(_warmup_extraction_cache_async())


async def _warmup_extraction_cache_async() -> Dict[str, Any]:
    """Async implementation of cache warmup."""
    from .extraction import get_extractor

    # Common phrases to pre-cache
    common_phrases = [
        # Greetings
        "你好",
        "早上好",
        "晚上好",
        # Member queries
        "我家有谁",
        "家庭成员",
        # Date queries
        "最近有什么生日",
        "近期有什么纪念日",
        # Reminders
        "我有什么提醒",
        "今天有什么安排",
        # Shopping
        "购物清单有什么",
        "要买什么",
        # Schedule
        "今天有什么事",
        "今天的安排",
        # Help
        "你能做什么",
        "帮助",
    ]

    results = {
        "phrases_cached": 0,
        "cache_hits": 0,
        "errors": [],
    }

    try:
        extractor = get_extractor()

        for phrase in common_phrases:
            try:
                result = await extractor.extract(phrase)
                if result.from_cache:
                    results["cache_hits"] += 1
                else:
                    results["phrases_cached"] += 1
            except Exception as e:
                results["errors"].append(f"{phrase}: {str(e)}")

    except Exception as e:
        logger.error("Cache warmup failed: %s", e)
        results["errors"].append(str(e))

    logger.info("Cache warmup complete: %s", results)
    return results


@shared_task(name="assistant.cleanup_extraction_cache")
def cleanup_extraction_cache_task() -> Dict[str, Any]:
    """
    Clean up old entries from the agentic extraction cache.

    Scheduled to run weekly to manage cache size.

    Returns:
        Summary of cache cleanup results
    """
    return run_async(_cleanup_extraction_cache_async())


async def _cleanup_extraction_cache_async() -> Dict[str, Any]:
    """Async implementation of cache cleanup."""
    from .extraction import get_extraction_cache

    results = {
        "memory_cleared": False,
        "redis_keys_deleted": 0,
        "embedding_cache_cleared": False,
        "stats_before": {},
        "stats_after": {},
        "errors": [],
    }

    try:
        cache = get_extraction_cache()
        results["stats_before"] = await cache.stats()

        # Clear memory cache (it will repopulate naturally)
        await cache.memory_cache.clear()
        results["memory_cleared"] = True

        # Clear old Redis entries (keep entries from last 24 hours)
        if cache.redis:
            try:
                import time
                cursor = 0
                keys_to_delete = []

                # Scan for old keys
                while True:
                    cursor, keys = await cache.redis.scan(
                        cursor, match=f"{cache.redis_prefix}*", count=100
                    )
                    for key in keys:
                        # Check TTL - if very low, it's old enough to delete
                        ttl = await cache.redis.ttl(key)
                        if ttl < 3600:  # Less than 1 hour remaining
                            keys_to_delete.append(key)

                    if cursor == 0:
                        break

                # Delete old keys
                if keys_to_delete:
                    await cache.redis.delete(*keys_to_delete)
                    results["redis_keys_deleted"] = len(keys_to_delete)

            except Exception as e:
                results["errors"].append(f"Redis cleanup error: {str(e)}")

        # Clear embedding cache (keep last 100 most recent)
        if len(cache._embedding_cache) > 100:
            oldest_keys = list(cache._embedding_cache.keys())[:-100]
            for key in oldest_keys:
                del cache._embedding_cache[key]
            results["embedding_cache_cleared"] = True

        results["stats_after"] = await cache.stats()

    except Exception as e:
        logger.error("Cache cleanup failed: %s", e)
        results["errors"].append(str(e))

    logger.info("Cache cleanup complete: %s", results)
    return results


@shared_task(name="assistant.get_extraction_cache_stats")
def get_extraction_cache_stats_task() -> Dict[str, Any]:
    """
    Get statistics about the agentic extraction cache.

    Useful for monitoring and debugging.

    Returns:
        Cache statistics
    """
    try:
        from .extraction import get_extraction_cache

        cache = get_extraction_cache()
        return cache.stats_sync()

    except Exception as e:
        logger.error("Failed to get cache stats: %s", e)
        return {"error": str(e)}


# ============ Per-User Tasks (Unified Dispatcher) ============


async def _resolve_user_family(user_id_str: str, session_factory):
    """Resolve user and family_id for a per-user task."""
    from uuid import UUID
    from sqlalchemy import select
    from ..member.models import User

    uid = UUID(user_id_str)
    async with session_factory() as session:
        result = await session.execute(
            select(User.id, User.family_id).where(User.id == uid)
        )
        row = result.one_or_none()
        if row is None:
            return None, None
        return row[0], row[1]


@shared_task(name="assistant.check_trip_memory_triggers")
def check_trip_memory_triggers_task(
    family_id: str,
    user_id: str,
    destination: str,
    trip_id: str,
    start_date: str,
    end_date: str = "",
) -> Dict[str, Any]:
    """
    Check memory triggers when a trip plan is created/updated.

    Finds location_mention triggers matching the destination and
    generates Insight records proactively.
    """
    return run_async(
        _check_trip_memory_triggers_async(
            family_id, user_id, destination, trip_id, start_date, end_date,
        )
    )


async def _check_trip_memory_triggers_async(
    family_id: str,
    user_id: str,
    destination: str,
    trip_id: str,
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    from uuid import UUID
    from datetime import date as date_type
    from sqlalchemy import select
    from .repository import MemoryRepository
    from ..insight.insight_pipeline import InsightPipeline

    if not trip_id or not trip_id.strip():
        return {"status": "skipped", "reason": "empty_trip_id"}

    try:
        fam_uuid = UUID(family_id)
        uid = UUID(user_id)
        tid = UUID(trip_id)
    except ValueError as e:
        logger.warning("Invalid UUID in trip memory trigger: %s", e)
        return {"status": "skipped", "reason": f"invalid_uuid: {e}"}

    try:
        start = date_type.fromisoformat(start_date) if start_date else local_today()
    except ValueError:
        start = local_today()
    end = date_type.fromisoformat(end_date) if end_date else None

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as session:
            repo = MemoryRepository(session)

            # 1. Check location_mention triggers
            triggered = await repo.get_triggered_memories(
                user_id=uid,
                trigger_type="location_mention",
                trigger_value=destination,
                limit=10,
            )

            if triggered:
                triggered_ids = [m.id for m in triggered]
                await repo.mark_memories_triggered_batch(triggered_ids)
                logger.info(
                    "Trip to %s triggered %d memories for user %s",
                    destination, len(triggered), user_id,
                )

            # 2. Generate trip-correlated insights via unified pipeline
            # The pipeline's reactive path handles trip events with
            # context enrichment, dedup, and persistence in one call.
            from ..curation.models import CuratedEvent

            trip_event_stmt = (
                select(CuratedEvent)
                .where(
                    CuratedEvent.trip_id == tid,
                    CuratedEvent.status != "cancelled",
                )
                .order_by(CuratedEvent.normalized_start)
                .limit(1)
            )
            trip_event_result = await session.execute(trip_event_stmt)
            trip_event = trip_event_result.scalar_one_or_none()

            insights_generated = 0
            if trip_event:
                pipeline = InsightPipeline(session)
                insight_ids = await pipeline.run_reactive(
                    event=trip_event,
                    family_id=fam_uuid,
                )
                insights_generated = len(insight_ids) if insight_ids else 0

            await session.commit()

            return {
                "family_id": family_id,
                "user_id": user_id,
                "destination": destination,
                "triggered_memories": len(triggered),
                "insights_generated": insights_generated,
            }
    except Exception as e:
        logger.error(
            "check_trip_memory_triggers failed for %s -> %s: %s",
            user_id, destination, e,
        )
        return {"status": "error", "error": str(e)}
    finally:
        await engine.dispose()


def trigger_memory_check_for_trip(
    family_id: str,
    user_id: str,
    destination: str,
    trip_id: str,
    start_date: str,
    end_date: str = "",
) -> bool:
    """
    Helper to dispatch trip memory trigger check from other modules.

    Call this after a TripPlan is created or updated with a new destination.
    Failures are logged but never propagated.
    """
    if not destination or not destination.strip():
        return False
    if not trip_id or not trip_id.strip():
        logger.debug("Skipping trip memory trigger: empty trip_id")
        return False
    try:
        check_trip_memory_triggers_task.delay(
            family_id=family_id,
            user_id=user_id,
            destination=destination,
            trip_id=trip_id,
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(
            "Dispatched trip memory trigger check: %s -> %s",
            user_id, destination,
        )
        return True
    except Exception as e:
        logger.warning(
            "Failed to dispatch trip memory trigger check: %s", e,
        )
        return False


@shared_task(name="assistant.consolidate_user_memories")
def consolidate_user_memories_task(user_id: str) -> Dict[str, Any]:
    """
    Consolidate memories for a single user (weekly).

    Called by the unified dispatcher.
    """
    try:
        result = run_async(_consolidate_user_memories_async(user_id))
        return result
    finally:
        reschedule_sync("assistant.consolidate_user_memories", user_id)


async def _consolidate_user_memories_async(user_id: str) -> Dict[str, Any]:
    from .consolidation_service import MemoryConsolidationService

    engine, session_factory = create_celery_async_session()
    try:
        uid, family_id = await _resolve_user_family(user_id, session_factory)
        if uid is None:
            return {"status": "skipped", "reason": "user_not_found"}

        async with session_factory() as session:
            service = MemoryConsolidationService(session)
            result = await service.consolidate_weekly_memories(
                user_id=uid,
                family_id=family_id,
                days_back=7,
            )
            await session.commit()

        return {
            "user_id": user_id,
            "memories_consolidated": result.get("memories_processed", 0),
            "profiles_updated": result.get("person_profiles_updated", 0),
            "summaries_created": result.get("summaries_created", 0),
        }
    except Exception as e:
        logger.error("consolidate_user_memories failed for %s: %s", user_id, e)
        raise
    finally:
        await engine.dispose()


@shared_task(name="assistant.generate_user_secretary_notes")
def generate_user_secretary_notes_task(user_id: str) -> Dict[str, Any]:
    """
    Generate secretary notes for a single user (weekly).

    Called by the unified dispatcher.
    """
    try:
        result = run_async(_generate_user_secretary_notes_async(user_id))
        return result
    finally:
        reschedule_sync("assistant.generate_user_secretary_notes", user_id)


async def _generate_user_secretary_notes_async(user_id: str) -> Dict[str, Any]:
    from .secretary_note_service import SecretaryNoteService

    engine, session_factory = create_celery_async_session()
    try:
        uid, family_id = await _resolve_user_family(user_id, session_factory)
        if uid is None:
            return {"status": "skipped", "reason": "user_not_found"}

        async with session_factory() as session:
            service = SecretaryNoteService(session)
            notes = await service.generate_notes_from_memories(
                user_id=uid,
                family_id=family_id,
                days_back=30,
            )
            await session.commit()

        return {
            "user_id": user_id,
            "notes_generated": len(notes),
        }
    except Exception as e:
        logger.error("generate_user_secretary_notes failed for %s: %s", user_id, e)
        raise
    finally:
        await engine.dispose()
