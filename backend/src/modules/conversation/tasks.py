"""
Conversation Tasks - Celery tasks for PendingAction lifecycle.

Provides scheduled tasks for:
- Expiring stale pending actions (every 2 minutes)
- Generating daily conversation summaries (daily at 05:35)
"""

from typing import Any, Dict

from celery import shared_task

from ...config.logging import get_logger
from ...core.scheduler._async_compat import run_async
from ...db.session import create_celery_async_session

logger = get_logger(__name__)


@shared_task(
    name="assistant.expire_stale_pending_actions",
    bind=True,
    autoretry_for=(OSError,),
    max_retries=2,
    default_retry_delay=5,
)
def expire_stale_actions_task(self) -> Dict[str, Any]:
    """
    Expire stale pending actions that have exceeded their TTL.

    Scheduled to run every 2 minutes via Celery beat.
    """
    return run_async(_expire_stale_actions_async())


async def _expire_stale_actions_async() -> Dict[str, Any]:
    """Async implementation of stale action expiration."""
    from .pending_action_service import PendingActionService

    results: Dict[str, Any] = {
        "actions_expired": 0,
        "errors": [],
    }

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as session:
            try:
                service = PendingActionService(session)
                count = await service.expire_stale()
                results["actions_expired"] = count
            except Exception as e:
                await session.rollback()
                logger.error("Expire stale actions failed: %s", e, exc_info=True)
                results["errors"].append(str(e))
    finally:
        await engine.dispose()

    if results["actions_expired"] > 0:
        logger.info("Expire stale actions complete: %s", results)
    return results


@shared_task(
    name="secretary.generate_daily_summaries",
    bind=True,
    autoretry_for=(OSError,),
    max_retries=2,
    default_retry_delay=30,
)
def generate_daily_summaries_task(self) -> Dict[str, Any]:
    """Generate and cache daily conversation summaries for all active sessions.

    Scheduled to run daily at 05:35 via Celery beat.
    """
    return run_async(_generate_daily_summaries_async())


async def _generate_daily_summaries_async() -> Dict[str, Any]:
    """Async implementation of daily summaries generation."""
    from sqlalchemy import select

    from .daily_summary_service import DailySummaryService
    from .models import AssistantChatSession

    results: Dict[str, Any] = {
        "sessions_processed": 0,
        "summaries_generated": 0,
        "errors": [],
    }

    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as db:
            try:
                sessions_result = await db.execute(
                    select(AssistantChatSession.id).where(
                        AssistantChatSession.status == "active",
                        AssistantChatSession.message_count >= 5,
                    )
                )
                session_ids = [row[0] for row in sessions_result.all()]

                for session_id in session_ids:
                    try:
                        svc = DailySummaryService(db)
                        count = await svc.generate_and_cache(session_id)
                        results["sessions_processed"] += 1
                        results["summaries_generated"] += count
                        await db.commit()
                    except Exception as e:
                        await db.rollback()
                        logger.warning(
                            "Failed to process session %s: %s", session_id, e
                        )
                        results["errors"].append(str(e))
            except Exception as e:
                await db.rollback()
                logger.error(
                    "Daily summaries task failed: %s", e, exc_info=True
                )
                results["errors"].append(str(e))
    finally:
        await engine.dispose()

    logger.info("Daily summaries complete: %s", results)
    return results
