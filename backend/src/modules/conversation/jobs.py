"""
Assistant Jobs - Scheduled tasks for proactive intelligent secretary services.

Uses the unified scheduler framework for:
- Smart reminder processing
- Preparation plan generation
- Today view synchronization
- Holiday planning
- AI suggestion generation
"""

import logging
from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.scheduler import (
    IntervalScheduler,
    MultiCronScheduler,
    ScheduledJob,
    JobPriority,
)
from ...core.utils.timezone import utc_now
from ...db.session import async_session_maker
from ..date_manager.models import SmartReminder, ReminderStatus, ChineseHolidayPlan, HolidayPlanStatus
from ..views.models import TodayItem, TodayItemStatus
from ..briefing.models import PreparationPlan, PreparationStatus

# HOLIDAY_CONFIG is a class attribute on ChineseHolidayPlan
HOLIDAY_CONFIG = ChineseHolidayPlan.HOLIDAY_CONFIG
from .scheduler_support import AssistantReminderService, PreparationService
from .today_service import TodayService
from .holiday_service import HolidayService


logger = logging.getLogger(__name__)


# ============ Smart Reminder Jobs ============

async def process_smart_reminders() -> Dict[str, Any]:
    """
    Process pending smart reminders that are due.

    This job:
    1. Queries smart reminders with reminder_time <= now
    2. Determines optimal delivery channel based on user behavior
    3. Sends reminders through appropriate channels
    4. Updates reminder status

    Returns:
        Summary with sent, failed, skipped counts
    """
    logger.info("Starting process_smart_reminders job")

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    try:
        async with async_session_maker() as session:
            # Get due reminders
            now = utc_now()
            result = await session.execute(
                select(SmartReminder).where(
                    and_(
                        SmartReminder.status == ReminderStatus.PENDING,
                        SmartReminder.reminder_time <= now,
                        SmartReminder.is_deleted == False
                    )
                ).limit(100)
            )
            reminders = result.scalars().all()

            if not reminders:
                logger.debug("No pending smart reminders to process")
                return {
                    "sent": 0,
                    "failed": 0,
                    "skipped": 0,
                    "time": now.isoformat()
                }

            logger.debug(f"Processing {len(reminders)} smart reminders")

            reminder_service = AssistantReminderService(session)

            for reminder in reminders:
                try:
                    # Check if should skip (e.g., quiet hours)
                    if await reminder_service.should_skip_reminder(reminder):
                        skipped_count += 1
                        continue

                    # Send reminder
                    success = await reminder_service.send_smart_reminder(reminder)

                    if success:
                        reminder.status = ReminderStatus.SENT
                        reminder.sent_at = utc_now()
                        sent_count += 1
                    else:
                        reminder.retry_count += 1
                        if reminder.retry_count >= reminder.max_retries:
                            reminder.status = ReminderStatus.FAILED
                        failed_count += 1

                except Exception as e:
                    logger.error(f"Error processing reminder {reminder.id}: {e}")
                    failed_count += 1

            await session.commit()

    except Exception as e:
        logger.error(f"Error in process_smart_reminders job: {e}", exc_info=True)
        raise

    logger.info(
        f"Smart reminder job complete - sent={sent_count}, "
        f"failed={failed_count}, skipped={skipped_count}"
    )

    return {
        "sent": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "time": utc_now().isoformat()
    }


async def optimize_reminder_times() -> Dict[str, Any]:
    """
    Analyze user behavior and optimize reminder delivery times.

    This job runs weekly to:
    1. Analyze user activity patterns
    2. Calculate optimal reminder windows
    3. Update user activity pattern records

    Returns:
        Summary with patterns updated count
    """
    logger.info("Starting optimize_reminder_times job")

    patterns_updated = 0

    try:
        async with async_session_maker() as session:
            reminder_service = AssistantReminderService(session)

            # Get all families with smart reminders
            result = await session.execute(
                select(SmartReminder.family_id).where(
                    SmartReminder.is_deleted == False
                ).distinct()
            )
            family_ids = [row[0] for row in result.all()]

            for family_id in family_ids:
                try:
                    updated = await reminder_service.update_activity_patterns(family_id)
                    if updated:
                        patterns_updated += 1
                except Exception as e:
                    logger.error(f"Error updating patterns for family {family_id}: {e}")

            await session.commit()

    except Exception as e:
        logger.error(f"Error in optimize_reminder_times job: {e}", exc_info=True)
        raise

    logger.info(f"Reminder optimization complete - patterns_updated={patterns_updated}")

    return {
        "patterns_updated": patterns_updated,
        "time": utc_now().isoformat()
    }


# ============ Preparation Plan Jobs ============

async def generate_preparation_plans() -> Dict[str, Any]:
    """
    Generate preparation plans for upcoming important events.

    This job:
    1. Scans upcoming important dates (30-60 days ahead)
    2. Creates preparation plans for birthdays, anniversaries, etc.
    3. Generates preparation tasks with appropriate timing

    Returns:
        Summary with plans created count
    """
    logger.info("Starting generate_preparation_plans job")

    plans_created = 0
    tasks_created = 0

    try:
        async with async_session_maker() as session:
            prep_service = PreparationService(session)

            # Get upcoming important dates that need preparation plans
            plans_needed = await prep_service.get_events_needing_preparation(
                days_ahead=60,
                min_days_to_event=7
            )

            for event in plans_needed:
                try:
                    plan = await prep_service.create_preparation_plan(
                        family_id=event["family_id"],
                        event_type=event["event_type"],
                        event_id=event["event_id"],
                        event_date=event["event_date"],
                        member_id=event.get("member_id"),
                        member_name=event.get("member_name")
                    )

                    if plan:
                        plans_created += 1
                        # Create tasks for the plan
                        tasks = await prep_service.generate_preparation_tasks(plan)
                        tasks_created += len(tasks)

                except Exception as e:
                    logger.error(f"Error creating plan for event {event}: {e}")

            await session.commit()

    except Exception as e:
        logger.error(f"Error in generate_preparation_plans job: {e}", exc_info=True)
        raise

    logger.info(
        f"Preparation plan generation complete - "
        f"plans={plans_created}, tasks={tasks_created}"
    )

    return {
        "plans_created": plans_created,
        "tasks_created": tasks_created,
        "time": utc_now().isoformat()
    }


async def update_preparation_progress() -> Dict[str, Any]:
    """
    Update progress of active preparation plans.

    This job:
    1. Checks task completion status
    2. Updates plan progress percentage
    3. Escalates overdue tasks
    4. Sends progress reminders

    Returns:
        Summary with plans updated count
    """
    logger.info("Starting update_preparation_progress job")

    plans_updated = 0
    tasks_escalated = 0

    try:
        async with async_session_maker() as session:
            prep_service = PreparationService(session)

            # Get active preparation plans
            result = await session.execute(
                select(PreparationPlan).where(
                    and_(
                        PreparationPlan.status.in_([
                            PreparationStatus.ACTIVE,
                            PreparationStatus.IN_PROGRESS
                        ]),
                        PreparationPlan.is_deleted == False
                    )
                )
            )
            plans = result.scalars().all()

            for plan in plans:
                try:
                    # Update progress
                    progress = await prep_service.calculate_plan_progress(plan.id)
                    plan.progress_percentage = progress

                    # Check for overdue tasks
                    escalated = await prep_service.escalate_overdue_tasks(plan.id)
                    tasks_escalated += escalated

                    # Update status based on progress
                    if progress >= 100:
                        plan.status = PreparationStatus.COMPLETED
                    elif progress > 0:
                        plan.status = PreparationStatus.IN_PROGRESS

                    plans_updated += 1

                except Exception as e:
                    logger.error(f"Error updating plan {plan.id}: {e}")

            await session.commit()

    except Exception as e:
        logger.error(f"Error in update_preparation_progress job: {e}", exc_info=True)
        raise

    logger.info(
        f"Preparation progress update complete - "
        f"plans={plans_updated}, escalated={tasks_escalated}"
    )

    return {
        "plans_updated": plans_updated,
        "tasks_escalated": tasks_escalated,
        "time": utc_now().isoformat()
    }


# ============ Today View Jobs ============

async def sync_today_items() -> Dict[str, Any]:
    """
    Synchronize today's items from all modules.

    This job aggregates items from:
    - Important dates (birthdays, anniversaries)
    - Shopping items (urgent/expiring)
    - Health checkups (appointments)
    - Preparation tasks (due soon)
    - Family tasks (assigned/overdue)

    Returns:
        Summary with items synced by source
    """
    logger.info("Starting sync_today_items job")

    items_synced = {}
    total_synced = 0

    try:
        async with async_session_maker() as session:
            today_service = TodayService(session)

            # Get all families
            # Note: In production, this should be optimized to only process
            # families that have been active recently
            from ..member.models import User
            result = await session.execute(
                select(User.family_id).where(User.is_active == True).distinct()
            )
            family_ids = [row[0] for row in result.all()]

            for family_id in family_ids:
                try:
                    synced = await today_service.sync_items_for_family(family_id)
                    for source, count in synced.items():
                        items_synced[source] = items_synced.get(source, 0) + count
                        total_synced += count
                except Exception as e:
                    logger.error(f"Error syncing items for family {family_id}: {e}")

            await session.commit()

    except Exception as e:
        logger.error(f"Error in sync_today_items job: {e}", exc_info=True)
        raise

    logger.info(f"Today items sync complete - total={total_synced}, by_source={items_synced}")

    return {
        "total_synced": total_synced,
        "by_source": items_synced,
        "time": utc_now().isoformat()
    }


async def cleanup_old_today_items() -> Dict[str, Any]:
    """
    Clean up old today items that are completed or dismissed.

    This job:
    1. Archives completed items older than 7 days
    2. Permanently deletes dismissed items older than 30 days
    3. Clears stale suggestions

    Returns:
        Summary with archived and deleted counts
    """
    logger.info("Starting cleanup_old_today_items job")

    archived = 0
    deleted = 0

    try:
        async with async_session_maker() as session:
            now = utc_now()

            # Archive completed items older than 7 days
            archive_cutoff = now - timedelta(days=7)
            result = await session.execute(
                select(TodayItem).where(
                    and_(
                        TodayItem.status == TodayItemStatus.COMPLETED,
                        TodayItem.updated_at < archive_cutoff,
                        TodayItem.is_deleted == False
                    )
                )
            )
            items_to_archive = result.scalars().all()

            for item in items_to_archive:
                item.is_deleted = True
                archived += 1

            # Permanently delete dismissed items older than 30 days
            delete_cutoff = now - timedelta(days=30)
            result = await session.execute(
                select(TodayItem).where(
                    and_(
                        TodayItem.status == TodayItemStatus.DISMISSED,
                        TodayItem.updated_at < delete_cutoff
                    )
                )
            )
            items_to_delete = result.scalars().all()

            for item in items_to_delete:
                await session.delete(item)
                deleted += 1

            await session.commit()

    except Exception as e:
        logger.error(f"Error in cleanup_old_today_items job: {e}", exc_info=True)
        raise

    logger.info(f"Today items cleanup complete - archived={archived}, deleted={deleted}")

    return {
        "archived": archived,
        "deleted": deleted,
        "time": utc_now().isoformat()
    }


# ============ Holiday Planning Jobs ============

async def generate_holiday_plans() -> Dict[str, Any]:
    """
    Generate holiday preparation plans for upcoming Chinese holidays.

    This job:
    1. Identifies holidays within the planning window (60 days)
    2. Creates comprehensive holiday plans for each family
    3. Generates red envelope budgets, shopping lists, etc.

    Returns:
        Summary with plans generated count
    """
    logger.info("Starting generate_holiday_plans job")

    plans_created = 0

    try:
        async with async_session_maker() as session:
            holiday_service = HolidayService(session)

            # Get upcoming holidays
            upcoming = await holiday_service.get_upcoming_holidays(days=60)

            # Get all families
            from ..member.models import User
            result = await session.execute(
                select(User.family_id).where(User.is_active == True).distinct()
            )
            family_ids = [row[0] for row in result.all()]

            for holiday in upcoming:
                for family_id in family_ids:
                    try:
                        # Check if plan already exists
                        existing = await holiday_service.get_holiday_plan(
                            family_id=family_id,
                            holiday_type=holiday["type"],
                            year=holiday["year"]
                        )

                        if not existing:
                            plan = await holiday_service.generate_holiday_plan(
                                family_id=family_id,
                                holiday_type=holiday["type"],
                                year=holiday["year"],
                                region=None  # Use family's region if available
                            )
                            if plan:
                                plans_created += 1

                    except Exception as e:
                        logger.error(
                            f"Error generating plan for {holiday['type']} "
                            f"for family {family_id}: {e}"
                        )

            await session.commit()

    except Exception as e:
        logger.error(f"Error in generate_holiday_plans job: {e}", exc_info=True)
        raise

    logger.info(f"Holiday plan generation complete - plans_created={plans_created}")

    return {
        "plans_created": plans_created,
        "time": utc_now().isoformat()
    }


async def send_holiday_reminders() -> Dict[str, Any]:
    """
    Send reminders for upcoming holiday preparations.

    This job sends reminders at key milestones:
    - 30 days before: Start planning
    - 14 days before: Shopping reminder
    - 7 days before: Final preparations
    - 3 days before: Last minute tasks

    Returns:
        Summary with reminders sent count
    """
    logger.info("Starting send_holiday_reminders job")

    reminders_sent = 0

    try:
        async with async_session_maker() as session:
            holiday_service = HolidayService(session)

            # Get active holiday plans
            result = await session.execute(
                select(ChineseHolidayPlan).where(
                    and_(
                        ChineseHolidayPlan.status.in_([
                            HolidayPlanStatus.DRAFT,
                            HolidayPlanStatus.ACTIVE,
                            HolidayPlanStatus.IN_PROGRESS
                        ]),
                        ChineseHolidayPlan.is_deleted == False
                    )
                )
            )
            plans = result.scalars().all()

            now = utc_now().date()

            for plan in plans:
                days_until = (plan.holiday_date - now).days

                # Determine if reminder is needed
                reminder_type = None
                if days_until == 30:
                    reminder_type = "planning"
                elif days_until == 14:
                    reminder_type = "shopping"
                elif days_until == 7:
                    reminder_type = "preparation"
                elif days_until == 3:
                    reminder_type = "final"

                if reminder_type:
                    try:
                        sent = await holiday_service.send_holiday_reminder(
                            plan=plan,
                            reminder_type=reminder_type
                        )
                        if sent:
                            reminders_sent += 1
                    except Exception as e:
                        logger.error(f"Error sending reminder for plan {plan.id}: {e}")

            await session.commit()

    except Exception as e:
        logger.error(f"Error in send_holiday_reminders job: {e}", exc_info=True)
        raise

    logger.info(f"Holiday reminders complete - sent={reminders_sent}")

    return {
        "reminders_sent": reminders_sent,
        "time": utc_now().isoformat()
    }


# ============ AI Suggestion Jobs ============

async def generate_daily_suggestions() -> Dict[str, Any]:
    """
    Generate personalized AI suggestions for each family.

    This job:
    1. Analyzes family data and patterns
    2. Generates proactive suggestions
    3. Prioritizes suggestions by relevance

    Returns:
        Summary with suggestions generated count
    """
    logger.info("Starting generate_daily_suggestions job")

    suggestions_created = 0

    try:
        async with async_session_maker() as session:
            today_service = TodayService(session)

            # Get all families
            from ..member.models import User
            result = await session.execute(
                select(User.family_id).where(User.is_active == True).distinct()
            )
            family_ids = [row[0] for row in result.all()]

            for family_id in family_ids:
                try:
                    suggestions = await today_service.generate_suggestions(family_id)
                    suggestions_created += len(suggestions)
                except Exception as e:
                    logger.error(f"Error generating suggestions for family {family_id}: {e}")

            await session.commit()

    except Exception as e:
        logger.error(f"Error in generate_daily_suggestions job: {e}", exc_info=True)
        raise

    logger.info(f"Daily suggestions complete - created={suggestions_created}")

    return {
        "suggestions_created": suggestions_created,
        "time": utc_now().isoformat()
    }


# ============ Scheduler Factory Functions ============

def create_assistant_scheduler() -> MultiCronScheduler:
    """
    Create and configure the intelligent assistant scheduler.

    Combines multiple job types:
    - Frequent: Smart reminders (every 5 minutes)
    - Hourly: Today sync, preparation progress
    - Daily: Preparation plans, suggestions, holiday reminders
    - Weekly: Reminder optimization, cleanup

    Returns:
        Configured MultiCronScheduler with all assistant jobs
    """
    scheduler = MultiCronScheduler(
        name="assistant_scheduler",
        check_interval=60  # Check every minute
    )

    # Smart reminder processing - every 5 minutes
    scheduler.register_cron_job(
        name="process_smart_reminders",
        func=process_smart_reminders,
        cron_expression="*/5 * * * *",
        description="Process pending smart reminders",
        priority=JobPriority.HIGH,
        timeout_seconds=300,
        max_retries=3,
        tags=["assistant", "reminders", "frequent"]
    )

    # Today items sync - every hour at :05
    scheduler.register_cron_job(
        name="sync_today_items",
        func=sync_today_items,
        cron_expression="5 * * * *",
        description="Synchronize today items from all modules",
        priority=JobPriority.NORMAL,
        timeout_seconds=600,
        max_retries=2,
        tags=["assistant", "today", "hourly"]
    )

    # Preparation progress update - every hour at :15
    scheduler.register_cron_job(
        name="update_preparation_progress",
        func=update_preparation_progress,
        cron_expression="15 * * * *",
        description="Update preparation plan progress",
        priority=JobPriority.NORMAL,
        timeout_seconds=300,
        max_retries=2,
        tags=["assistant", "preparation", "hourly"]
    )

    # Generate preparation plans - daily at 06:00
    scheduler.register_cron_job(
        name="generate_preparation_plans",
        func=generate_preparation_plans,
        cron_expression="0 6 * * *",
        description="Generate preparation plans for upcoming events",
        priority=JobPriority.NORMAL,
        timeout_seconds=900,
        max_retries=2,
        tags=["assistant", "preparation", "daily"]
    )

    # Generate holiday plans - daily at 07:00
    scheduler.register_cron_job(
        name="generate_holiday_plans",
        func=generate_holiday_plans,
        cron_expression="0 7 * * *",
        description="Generate holiday preparation plans",
        priority=JobPriority.NORMAL,
        timeout_seconds=600,
        max_retries=2,
        tags=["assistant", "holiday", "daily"]
    )

    # Send holiday reminders - daily at 08:00
    scheduler.register_cron_job(
        name="send_holiday_reminders",
        func=send_holiday_reminders,
        cron_expression="0 8 * * *",
        description="Send holiday preparation reminders",
        priority=JobPriority.HIGH,
        timeout_seconds=300,
        max_retries=3,
        tags=["assistant", "holiday", "reminders", "daily"]
    )

    # Generate daily suggestions - daily at 06:30
    scheduler.register_cron_job(
        name="generate_daily_suggestions",
        func=generate_daily_suggestions,
        cron_expression="30 6 * * *",
        description="Generate personalized daily suggestions",
        priority=JobPriority.NORMAL,
        timeout_seconds=600,
        max_retries=2,
        tags=["assistant", "suggestions", "daily"]
    )

    # Optimize reminder times - weekly on Sunday at 04:00
    scheduler.register_cron_job(
        name="optimize_reminder_times",
        func=optimize_reminder_times,
        cron_expression="0 4 * * 0",
        description="Optimize reminder delivery times based on user behavior",
        priority=JobPriority.LOW,
        timeout_seconds=1800,
        max_retries=1,
        tags=["assistant", "reminders", "optimization", "weekly"]
    )

    # Cleanup old today items - weekly on Saturday at 03:00
    scheduler.register_cron_job(
        name="cleanup_old_today_items",
        func=cleanup_old_today_items,
        cron_expression="0 3 * * 6",
        description="Archive and cleanup old today items",
        priority=JobPriority.LOW,
        timeout_seconds=600,
        max_retries=1,
        tags=["assistant", "cleanup", "weekly"]
    )

    return scheduler


# Default scheduler instance (created on demand)
_assistant_scheduler: Optional[MultiCronScheduler] = None


def get_assistant_scheduler() -> MultiCronScheduler:
    """Get or create the default assistant scheduler."""
    global _assistant_scheduler
    if _assistant_scheduler is None:
        _assistant_scheduler = create_assistant_scheduler()
    return _assistant_scheduler
