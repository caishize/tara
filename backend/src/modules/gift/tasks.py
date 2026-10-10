"""Unified Celery tasks for the gift module.

Merges tasks from:
  - gift_orchestration/jobs/gift_jobs.py (gift.* tasks)
  - trending_gifts/tasks/update_tasks.py (trending_gifts.* tasks)
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from celery import shared_task

from ...core.scheduler._async_compat import run_async
from ...core.utils.timezone import utc_now
from ...db.session import async_session_maker

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50


# ═══════════════════════════════════════════════════════════════════════════════
# Gift task processing (from gift_orchestration/jobs/gift_jobs.py)
# ═══════════════════════════════════════════════════════════════════════════════


async def _process_pending_tasks(
    system_user_id: Optional[UUID] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, Any]:
    """Process all due pending gift tasks."""
    logger.info("Starting process_pending_tasks job")
    processed = 0
    failed = 0

    async with async_session_maker() as session:
        from .task_service import GiftTaskService

        task_service = GiftTaskService(session)
        due_tasks = await task_service.get_due_tasks(limit=batch_size)
        total = len(due_tasks)
        logger.info("Found %d due tasks to process", total)

        if not due_tasks:
            return {"processed": 0, "failed": 0, "total": 0}

        from ...core.llm import OpenAIAdapter
        from ...config.settings import settings
        from .recommendation_service import SmartRecommendationService

        llm_provider = OpenAIAdapter(settings.openai_api_key)
        smart_service = SmartRecommendationService(session, llm_provider)

        for task in due_tasks:
            try:
                requester_id = system_user_id or task.family_id
                result = await smart_service.generate_for_task(
                    task=task, requester_user_id=requester_id
                )
                processed += 1
                logger.info("Processed task %s: generated recommendation %s", task.id, result["id"])
            except Exception as e:
                failed += 1
                logger.error("Failed to process task %s: %s", task.id, e)

        await session.commit()

    logger.info("Completed process_pending_tasks: processed=%d, failed=%d", processed, failed)
    return {"processed": processed, "failed": failed, "total": processed + failed}


async def _expire_old_tasks() -> Dict[str, Any]:
    """Expire old tasks that are past their occasion date."""
    logger.info("Starting expire_old_tasks job")

    async with async_session_maker() as session:
        from .task_service import GiftTaskService

        task_service = GiftTaskService(session)
        expired = await task_service.expire_old_tasks()
        await session.commit()

    logger.info("Expired %d old tasks", expired)
    return {"expired": expired}


async def _decay_preferences() -> Dict[str, Any]:
    """Decay confidence of old preference records."""
    logger.info("Starting decay_preferences job")

    async with async_session_maker() as session:
        from .recommendation_service import PreferenceLearningService

        preference_service = PreferenceLearningService(session)
        decayed = await preference_service.decay_old_preferences(days_threshold=730)
        await session.commit()

    logger.info("Decayed %d old preferences", decayed)
    return {"decayed": decayed}


async def _retry_failed_tasks() -> Dict[str, Any]:
    """Retry failed tasks that are eligible for retry."""
    logger.info("Starting retry_failed_tasks job")

    async with async_session_maker() as session:
        from .task_service import GiftTaskService

        task_service = GiftTaskService(session)
        retried = await task_service.retry_failed_tasks()
        await session.commit()

    logger.info("Reset %d failed tasks for retry", retried)
    return {"retried": retried}


async def _process_single_gift_task_async(task_id_str: str) -> dict:
    """Async implementation of single gift task processing."""
    from sqlalchemy import select
    from .models import GiftTask

    task_uuid = UUID(task_id_str)

    async with async_session_maker() as session:
        result = await session.execute(
            select(GiftTask).where(
                GiftTask.id == task_uuid,
                GiftTask.is_deleted == False,  # noqa: E712
            )
        )
        task = result.scalar_one_or_none()

        if task is None:
            return {"status": "skipped", "reason": "not_found"}

        if task.status != "pending":
            return {"status": "skipped", "reason": f"status={task.status}"}

        from .task_service import GiftTaskService

        task_service = GiftTaskService(session)

        try:
            from ...core.llm import OpenAIAdapter
            from ...config.settings import settings
            from .recommendation_service import SmartRecommendationService

            llm_provider = OpenAIAdapter(settings.openai_api_key)
            smart_service = SmartRecommendationService(session, llm_provider)

            result = await smart_service.generate_for_task(
                task=task, requester_user_id=task.family_id
            )
            await session.commit()

            return {
                "task_id": task_id_str,
                "recommendation_id": str(result.get("id", "")),
                "status": "completed",
            }
        except Exception as e:
            logger.error("Failed to process gift task %s: %s", task_id_str, e)
            await task_service.mark_failed(task_uuid, str(e))
            await session.commit()
            raise


# ─── Celery shared_tasks (gift.*) ─────────────────────────────────────────────

@shared_task(name="gift.process_single_task")
def process_single_gift_task(task_id: str) -> dict:
    """Process a single gift recommendation task by ID.

    Called by the unified dispatcher when the task's scheduled_time
    is reached in the Redis sorted set.
    """
    logger.info("Processing single gift task %s", task_id)
    return run_async(_process_single_gift_task_async(task_id))


@shared_task(name="gift.expire_old_tasks")
def expire_old_tasks_beat() -> dict:
    """Celery Beat task: expire old gift tasks daily at 3:00 AM."""
    return run_async(_expire_old_tasks())


@shared_task(name="gift.decay_preferences")
def decay_preferences_beat() -> dict:
    """Celery Beat task: decay old preferences weekly on Sundays at 4:00 AM."""
    return run_async(_decay_preferences())


@shared_task(name="gift.retry_failed_tasks")
def retry_failed_tasks_beat() -> dict:
    """Celery Beat task: retry failed gift tasks daily at 5:00 AM."""
    return run_async(_retry_failed_tasks())


# ═══════════════════════════════════════════════════════════════════════════════
# Trending gifts tasks (from trending_gifts/tasks/update_tasks.py)
# ═══════════════════════════════════════════════════════════════════════════════


def _get_sync_db_session():
    """Get synchronous database session for Celery tasks."""
    from ...db.session import SessionLocal
    return SessionLocal()


def _get_redis_client():
    """Get Redis client — imported lazily."""
    from ...core.cache import get_redis_client
    return get_redis_client()


async def _run_scrapers(
    categories=None,
) -> list:
    """Run all configured scrapers and collect results."""
    from .scrapers import JDScraper, SMZDMScraper

    all_gifts: list = []

    async with JDScraper() as jd:
        if categories:
            for cat in categories:
                try:
                    gifts = await jd.scrape_category(cat, limit=30)
                    all_gifts.extend(gifts)
                except Exception as e:
                    logger.error("JD scraper failed for %s: %s", cat, e)
        else:
            try:
                gifts = await jd.scrape_trending(limit=50)
                all_gifts.extend(gifts)
            except Exception as e:
                logger.error("JD trending scrape failed: %s", e)

    async with SMZDMScraper() as smzdm:
        if categories:
            for cat in categories:
                try:
                    gifts = await smzdm.scrape_category(cat, limit=30)
                    all_gifts.extend(gifts)
                except Exception as e:
                    logger.error("SMZDM scraper failed for %s: %s", cat, e)
        else:
            try:
                gifts = await smzdm.scrape_trending(limit=50)
                all_gifts.extend(gifts)
            except Exception as e:
                logger.error("SMZDM trending scrape failed: %s", e)

    return all_gifts


async def _save_gifts_to_db(gifts: list, db_session) -> int:
    """Save scraped gifts to database using upsert."""
    from .repositories import TrendingGiftRepository

    repo = TrendingGiftRepository(db_session)
    saved_count = 0

    for gift in gifts:
        try:
            await repo.upsert(gift.to_dict())
            saved_count += 1
        except Exception as e:
            logger.error("Failed to save gift %s: %s", gift.external_id, e)

    db_session.commit()
    return saved_count


async def _update_cache(categories=None):
    """Update Redis cache for gift rankings."""
    from .models import GiftCategory

    redis = _get_redis_client()
    if not redis:
        logger.warning("Redis not available, skipping cache update")
        return

    from ...db.session import create_celery_async_session
    engine, session_factory = create_celery_async_session()

    try:
        from .repositories import TrendingGiftRepository
        import json

        async with session_factory() as db:
            repo = TrendingGiftRepository(db)
            cats = categories or list(GiftCategory)

            for cat in cats:
                gifts, _ = await repo.list_by_category(cat, page_size=50)
                cache_key = f"trending_gifts:{cat.value}"
                cache_data = [
                    {
                        "id": str(g.id),
                        "name": g.name,
                        "price": float(g.price) if g.price is not None else None,
                        "image_url": g.image_url,
                        "rank": g.rank,
                    }
                    for g in gifts
                ]
                redis.setex(cache_key, 86400, json.dumps(cache_data))

            logger.debug("Updated cache for %d categories", len(cats))
    finally:
        await engine.dispose()


# ─── Celery shared_tasks (trending_gifts.*) ───────────────────────────────────

@shared_task(
    name="trending_gifts.daily_update",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def daily_update_trending_gifts(self):
    """Daily task to update all trending gifts (runs at 03:00 via Celery Beat)."""
    logger.debug("Starting daily trending gifts update")

    db = _get_sync_db_session()
    update_log = None

    try:
        from .models import UpdateLog, UpdateStatus

        update_log = UpdateLog(
            task_id=self.request.id or str(uuid.uuid4()),
            started_at=utc_now(),
            status=UpdateStatus.RUNNING.value,
        )
        db.add(update_log)
        db.commit()
        db.refresh(update_log)

        gifts = run_async(_run_scrapers())
        logger.debug("Scraped %d total gifts", len(gifts))

        saved_count = run_async(_save_gifts_to_db(gifts, db))
        logger.debug("Saved %d gifts to database", saved_count)

        run_async(_update_cache())

        update_log.status = UpdateStatus.SUCCESS.value
        update_log.completed_at = utc_now()
        update_log.gifts_added = saved_count
        db.commit()

        logger.debug("Daily trending gifts update completed successfully")
        return {"status": "success", "items_processed": saved_count}

    except Exception as e:
        logger.error("Daily update failed: %s", e)
        db.rollback()

        if update_log and update_log.id:
            try:
                db.merge(update_log)
                update_log.status = UpdateStatus.FAILED.value
                update_log.completed_at = utc_now()
                update_log.error_message = str(e)[:500]
                db.commit()
            except Exception:
                db.rollback()

        raise self.retry(exc=e)
    finally:
        db.close()


@shared_task(name="trending_gifts.update_category")
def update_category_gifts(category: str):
    """Update gifts for a specific category."""
    logger.debug("Updating category: %s", category)

    from .models import GiftCategory

    try:
        cat = GiftCategory(category)
    except ValueError:
        logger.error("Invalid category: %s", category)
        return {"status": "error", "message": f"Invalid category: {category}"}

    db = _get_sync_db_session()
    try:
        gifts = run_async(_run_scrapers([cat]))
        saved_count = run_async(_save_gifts_to_db(gifts, db))
        run_async(_update_cache([cat]))
        logger.debug("Category %s update: %d items", category, saved_count)
        return {"status": "success", "category": category, "items": saved_count}
    finally:
        db.close()


@shared_task(name="trending_gifts.update_occasion")
def update_occasion_gifts(occasion_id: str):
    """Update gifts for a specific occasion."""
    logger.debug("Updating occasion: %s", occasion_id)

    from .models import GiftCategory

    db = _get_sync_db_session()
    try:
        from .repositories import OccasionRepository

        repo = OccasionRepository(db)
        occasion = repo.get_by_id(occasion_id)

        if not occasion:
            logger.error("Occasion not found: %s", occasion_id)
            return {"status": "error", "message": "Occasion not found"}

        categories = occasion.recommended_categories or list(GiftCategory)

        gifts = run_async(_run_scrapers(categories))
        saved_count = run_async(_save_gifts_to_db(gifts, db))

        from .repositories import OccasionRepository
        og_repo = OccasionRepository(db)

        for i, gift in enumerate(gifts[:50]):
            og_repo.link_gift(
                occasion_id=occasion_id,
                gift_id=str(gift.external_id),
                rank=i + 1,
            )

        db.commit()

        logger.debug("Occasion %s update: %d items", occasion_id, saved_count)
        return {"status": "success", "occasion": occasion_id, "items": saved_count}
    finally:
        db.close()


@shared_task(name="trending_gifts.refresh_cache")
def refresh_gift_cache(categories: Optional[List[str]] = None):
    """Refresh Redis cache for gift rankings."""
    logger.debug("Refreshing gift cache")

    from .models import GiftCategory

    cats = None
    if categories:
        try:
            cats = [GiftCategory(c) for c in categories]
        except ValueError as e:
            logger.error("Invalid category in list: %s", e)
            return {"status": "error", "message": str(e)}

    run_async(_update_cache(cats))
    logger.debug("Cache refresh completed")
    return {"status": "success"}
