"""
Daily Briefing Scheduled Tasks (PRD 4.3)

Generates and delivers daily briefings to all active users at 8:30 AM.
The briefing includes:
- Today's events and tasks
- Preparation reminders
- Smart suggestions
- AI-generated insights
"""
import logging
from typing import List
from datetime import date
from uuid import UUID

from celery import shared_task

from ...core.scheduler._async_compat import run_async
from ...core.scheduler.reschedule import reschedule_sync
from ...core.utils.timezone import local_today
from ...db.session import create_celery_async_session
from .services.briefing_service import DailyBriefingService

logger = logging.getLogger(__name__)


async def _generate_briefing_for_user(
    user_id: UUID,
    family_id: UUID,
    target_date: date,
    session_factory,
) -> dict:
    """
    Generate daily briefing for a single user.

    Args:
        user_id: User ID
        family_id: Family ID
        target_date: Date to generate briefing for
        session_factory: Async session factory

    Returns:
        dict with briefing summary
    """
    async with session_factory() as db:
        service = DailyBriefingService(db)
        briefing = await service.generate_briefing(
            user_id=user_id,
            family_id=family_id,
            target_date=target_date,
        )

        # Write briefing into conversation timeline for unified display
        try:
            from ..conversation import SessionService
            manager = SessionService(db)
            await manager.save_async_push_message(
                user_id=user_id,
                family_id=family_id,
                content=briefing.greeting,
                async_source="briefing",
            )
        except Exception as e:
            logger.warning("Failed to save briefing to timeline for user %s: %s", user_id, e)

        return {
            "user_id": str(user_id),
            "date": str(briefing.date),
            "greeting": briefing.greeting,
            "event_count": briefing.today_event_count,
            "reminder_count": len(briefing.preparation_reminders),
            "suggestion_count": len(briefing.smart_suggestions),
        }


async def _get_active_users(session_factory) -> List[dict]:
    """
    Get all active users who should receive daily briefings.

    Returns:
        List of dicts with user_id and family_id
    """
    async with session_factory() as db:
        from sqlalchemy import select
        from ..member.models.user import User

        result = await db.execute(
            select(User).where(User.is_active == True)
        )
        users = result.scalars().all()

        return [
            {
                "user_id": user.id,
                "family_id": user.family_id,
            }
            for user in users
            if user.family_id is not None
        ]


async def _generate_all_briefings() -> dict:
    """
    Generate daily briefings for all active users.

    Returns:
        Summary of generated briefings
    """
    today = local_today()

    engine, session_factory = create_celery_async_session()
    try:
        users = await _get_active_users(session_factory)

        if not users:
            logger.info("No active users to generate briefings for")
            return {"status": "no_users", "count": 0}

        logger.info(f"Generating daily briefings for {len(users)} users")

        results = []
        errors = []

        for user_data in users:
            try:
                result = await _generate_briefing_for_user(
                    user_id=user_data["user_id"],
                    family_id=user_data["family_id"],
                    target_date=today,
                    session_factory=session_factory,
                )
                results.append(result)
                logger.debug(f"Generated briefing for user {user_data['user_id']}")

            except Exception as e:
                error_msg = f"Failed to generate briefing for user {user_data['user_id']}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        summary = {
            "status": "completed",
            "date": str(today),
            "total_users": len(users),
            "success_count": len(results),
            "error_count": len(errors),
            "errors": errors[:10] if errors else [],
        }

        logger.info(
            f"Daily briefing generation completed: "
            f"{summary['success_count']}/{summary['total_users']} successful"
        )

        return summary
    finally:
        await engine.dispose()


@shared_task(
    name="secretary.generate_daily_briefings",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=10,
)
def generate_daily_briefings(self):
    """
    Celery task to generate daily briefings for all users.

    This task runs at 8:30 AM (PRD 4.3) and generates briefings
    containing:
    - Today's events (meetings, tasks, appointments)
    - Important reminders (birthdays, anniversaries)
    - Smart suggestions based on context
    - AI-generated insights from memory system

    The briefings are stored and can be:
    - Retrieved via API by the mobile app
    - Sent as push notifications (future enhancement)
    """
    logger.info("Starting daily briefing generation task")
    return run_async(_generate_all_briefings())


@shared_task(
    name="secretary.prepare_daily_content",
    bind=True,
    autoretry_for=(OSError, ConnectionError),
    max_retries=2,
    default_retry_delay=10,
)
def prepare_daily_content(self, user_id: str):
    """
    Unified daily content task: generate insights + briefing for a single user.

    Runs at 6:00 AM, writing insights to user_insights table
    and saving a summary to the conversation timeline.
    """
    logger.info("Preparing daily content for user %s", user_id)
    try:
        result = run_async(_prepare_daily_content_async(user_id))
        return result
    finally:
        reschedule_sync("secretary.prepare_daily_content", user_id)


async def _prepare_daily_content_async(user_id: str) -> dict:
    """Unified daily content: insights + briefing timeline entry."""
    engine, session_factory = create_celery_async_session()
    try:
        family_id = await _resolve_family_id(UUID(user_id), session_factory)
        if family_id is None:
            logger.warning("User %s has no family, skipping daily content", user_id)
            return {"status": "skipped", "reason": "no_family"}

        uid = UUID(user_id)
        insights = []

        # Step 1: Generate insights into user_insights table
        async with session_factory() as session:
            try:
                from .services.insight_orchestrator import InsightOrchestrator

                orchestrator = InsightOrchestrator(session)
                insights = await orchestrator.generate_all(
                    user_id=uid,
                    family_id=family_id,
                    target_date=local_today(),
                )
            except Exception as e:
                logger.error("Insight generation failed for user %s: %s", user_id, e)

        # Step 2: Generate briefing and save to conversation timeline
        briefing_result = await _generate_briefing_for_user(
            user_id=uid,
            family_id=family_id,
            target_date=local_today(),
            session_factory=session_factory,
        )

        # Step 3: Save insight summary to timeline (if any)
        if insights:
            async with session_factory() as session:
                try:
                    from ..conversation.session_service import SessionService

                    manager = SessionService(session)
                    insight_texts = []
                    for ins in insights[:5]:
                        title = getattr(ins, "title", None) or getattr(ins, "insight_type", "")
                        content = getattr(ins, "content", None) or getattr(ins, "description", "")
                        if title and content:
                            insight_texts.append(f"**{title}**: {content}")
                        elif content:
                            insight_texts.append(content)
                    if insight_texts:
                        summary_content = "\n".join(insight_texts)
                        await manager.save_async_push_message(
                            user_id=uid,
                            family_id=family_id,
                            content=summary_content,
                            async_source="discovery",
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to save insights to timeline for user %s: %s",
                        user_id, e,
                    )

        return {
            "user_id": user_id,
            "insights_generated": len(insights),
            "briefing": briefing_result,
        }
    finally:
        await engine.dispose()


async def _resolve_family_id(user_id: UUID, session_factory) -> UUID:
    """Look up the family_id for a user."""
    from sqlalchemy import select
    from ..member.models.user import User

    async with session_factory() as db:
        result = await db.execute(
            select(User.family_id).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
