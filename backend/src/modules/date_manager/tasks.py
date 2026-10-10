"""
Date Manager Tasks - Celery tasks for:
- Reminder sending
- Holiday sync
- Holiday preparation
"""

import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_

from ...core.scheduler import (
    IntervalScheduler,
    ScheduledJob,
    CronScheduler,
    CronJob,
    JobPriority,
)
from ...core.scheduler._async_compat import run_async
from ...config.settings import settings
from ...core.utils.timezone import local_now
from ...db.session import create_celery_async_session

from .models import (
    ImportantDate,
    DateReminder,
    DateType,
    ReminderStatus,
    get_reminder_offsets,
    is_lunar_holiday,
    is_solar_term,
)
from ...core.constants import SYSTEM_FAMILY_ID, SYSTEM_USER_ID


logger = logging.getLogger(__name__)

# Batch size for processing reminders
REMINDER_BATCH_SIZE = 100


# ─── Reminder Tasks ───────────────────────────────────────────────────────────


async def send_pending_reminders() -> Dict[str, Any]:
    """
    Send all pending reminders that are due.

    This job:
    1. Queries for pending reminders with reminder_time <= now
    2. Sends each reminder through the notification provider
    3. Handles failures with retry logic

    Returns:
        Summary dict with sent_count, failed_count, and total
    """
    from .reminder_service import ReminderService

    # Create database session
    engine = create_async_engine(settings.database_url, echo=False, connect_args=settings.database_connect_args)
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    sent_count = 0
    failed_count = 0
    total = 0

    try:
        async with async_session_factory() as session:
            # Create service
            reminder_service = ReminderService(session)

            # Get pending reminders
            current_time = local_now()
            pending_reminders = await reminder_service.get_pending_reminders(
                before_time=current_time
            )

            total = len(pending_reminders)

            if total == 0:
                logger.debug("No pending reminders to send")
                return {
                    "sent": 0,
                    "failed": 0,
                    "total": 0,
                    "time": current_time.isoformat()
                }

            logger.info(
                f"Processing {total} pending reminders "
                f"(time: {current_time.isoformat()})"
            )

            # Process reminders in batch
            for reminder in pending_reminders[:REMINDER_BATCH_SIZE]:
                success = await reminder_service.send_reminder_with_fallback(
                    reminder,
                    max_retries=3
                )

                if success:
                    sent_count += 1
                else:
                    failed_count += 1

            # Commit all changes
            await session.commit()

            logger.info(
                f"Reminder batch complete - "
                f"Sent: {sent_count}, Failed: {failed_count}"
            )

    except Exception as e:
        logger.error(f"Error in send_pending_reminders job: {e}", exc_info=True)
        raise

    finally:
        await engine.dispose()

    return {
        "sent": sent_count,
        "failed": failed_count,
        "total": total,
        "time": local_now().isoformat()
    }


def create_reminder_scheduler(
    check_interval: int = 60,
    batch_size: int = 100
) -> IntervalScheduler:
    """
    Create and configure the reminder scheduler.

    Args:
        check_interval: How often to check for pending reminders (seconds)
        batch_size: Maximum reminders to process per batch

    Returns:
        Configured IntervalScheduler instance
    """
    scheduler = IntervalScheduler(
        name="reminder_scheduler",
        interval_seconds=check_interval,
        batch_size=batch_size,
        run_immediately=True  # Send any missed reminders on startup
    )

    # Register the reminder sending job
    scheduler.register_job(ScheduledJob(
        name="send_pending_reminders",
        func=send_pending_reminders,
        description="Send pending date reminders",
        priority=JobPriority.HIGH,  # Reminders are time-sensitive
        timeout_seconds=300,  # 5 minutes max
        max_retries=3,
        retry_delay_seconds=60,
        enabled=True,
        tags=["reminders", "notifications"]
    ))

    return scheduler


# Default scheduler instance (created on demand)
_reminder_scheduler: Optional[IntervalScheduler] = None


def get_reminder_scheduler() -> IntervalScheduler:
    """Get or create the default reminder scheduler."""
    global _reminder_scheduler
    if _reminder_scheduler is None:
        _reminder_scheduler = create_reminder_scheduler()
    return _reminder_scheduler


@shared_task(name="reminder.send_single")
def send_single_reminder_task(reminder_id: str) -> dict:
    """
    Send a single reminder by ID.

    Called by the unified dispatcher when the reminder's
    scheduled time is reached in the Redis sorted set.
    """
    logger.info("Sending single reminder %s", reminder_id)
    return run_async(_send_single_reminder_async(reminder_id))


async def _send_single_reminder_async(reminder_id_str: str) -> dict:
    """Async implementation of single reminder send."""
    from .reminder_service import ReminderService

    reminder_uuid = UUID(reminder_id_str)
    engine, session_factory = create_celery_async_session()
    try:
        async with session_factory() as session:
            result = await session.execute(
                select(DateReminder).where(DateReminder.id == reminder_uuid)
            )
            reminder = result.scalar_one_or_none()

            if reminder is None:
                return {"status": "skipped", "reason": "not_found"}

            if reminder.status != ReminderStatus.PENDING.value:
                return {"status": "skipped", "reason": f"status={reminder.status}"}

            service = ReminderService(session)
            success = await service.send_reminder_with_fallback(
                reminder, max_retries=3
            )

            # Write reminder into conversation timeline for unified display
            if success:
                try:
                    await _write_reminder_to_timeline(session, reminder)
                except Exception as e:
                    logger.warning(
                        "Failed to save reminder %s to timeline: %s",
                        reminder_id_str, e,
                    )

                # Publish DateApproaching event
                try:
                    from ...core.events import get_event_bus
                    from ...core.events.domain_events import DateApproaching

                    date_result = await session.execute(
                        select(ImportantDate).where(ImportantDate.id == reminder.date_id)
                    )
                    imp_date = date_result.scalar_one_or_none()
                    if imp_date:
                        event_bus = get_event_bus()
                        await event_bus.publish(DateApproaching(
                            date_id=imp_date.id,
                            family_id=imp_date.family_id,
                            days_until=abs(reminder.reminder_offset) if reminder.reminder_offset else 0,
                            date_type=imp_date.date_type or "",
                            title=imp_date.title or "",
                            member_id=imp_date.member_id,
                        ))
                except Exception as e:
                    logger.warning(
                        "Failed to publish DateApproaching event for reminder %s: %s",
                        reminder_id_str, e,
                    )

            await session.commit()

            return {
                "reminder_id": reminder_id_str,
                "success": success,
            }
    finally:
        await engine.dispose()


async def _write_reminder_to_timeline(session, reminder) -> None:
    """Write a triggered reminder to the conversation timeline."""
    from ..member.models.user import User

    # Resolve family_id from the reminder's date
    date_result = await session.execute(
        select(ImportantDate.family_id, ImportantDate.title)
        .where(ImportantDate.id == reminder.date_id)
    )
    row = date_result.one_or_none()
    if row is None:
        return

    family_id, date_title = row

    # Find an active user in this family to write the message for
    user_result = await session.execute(
        select(User.id)
        .where(User.family_id == family_id, User.is_active == True)
        .limit(1)
    )
    user_id = user_result.scalar_one_or_none()
    if user_id is None:
        return

    from ...modules.conversation import SessionService
    manager = SessionService(session)
    content = f"**提醒**: {date_title or '日期提醒'}"
    if reminder.reminder_content:
        content += f"\n{reminder.reminder_content}"

    await manager.save_async_push_message(
        user_id=user_id,
        family_id=family_id,
        content=content,
        async_source="reminder",
    )


# ─── Holiday Sync Tasks ──────────────────────────────────────────────────────


def _holiday_type_to_date_type(holiday_type) -> DateType:
    """Convert HolidayType to DateType enum."""
    from .calendar_adapter import HolidayType
    mapping = {
        HolidayType.LEGAL: DateType.HOLIDAY_LEGAL,
        HolidayType.LUNAR: DateType.HOLIDAY_LUNAR,
        HolidayType.SOLAR_TERM: DateType.HOLIDAY_SOLAR_TERM,
    }
    return mapping.get(holiday_type, DateType.HOLIDAY)


async def sync_chinese_holidays() -> Dict[str, Any]:
    """
    Synchronize Chinese holidays from calendar adapter.

    This job runs daily at midnight and:
    1. Fetches holidays for current year and next year
    2. Deduplicates against existing records
    3. Creates new ImportantDate records with appropriate reminders

    Returns:
        Summary dict with synced count, skipped count, and errors
    """
    from .calendar_adapter import baidu_calendar_adapter, HolidayData, HolidayType
    from .date_service import DateService
    from .reminder_service import ReminderService
    # Import Member to ensure SQLAlchemy mapper is properly initialized
    from ..member.models.member import Member

    # Create database session
    engine = create_async_engine(settings.database_url, echo=False, connect_args=settings.database_connect_args)
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    synced_count = 0
    skipped_count = 0
    error_count = 0
    years_processed: List[int] = []

    current_year = local_now().year
    years_to_sync = [current_year, current_year + 1]

    try:
        async with async_session_factory() as session:
            try:
                # Initialize services
                reminder_service = ReminderService(session)
                date_service = DateService(session)

                for year in years_to_sync:
                    logger.info(f"Syncing holidays for year {year}")
                    years_processed.append(year)

                    try:
                        # Fetch all holidays for this year
                        holidays = await baidu_calendar_adapter.fetch_holidays(year)

                        # Get existing holidays to avoid duplicates
                        existing_holidays = await _get_existing_holidays(
                            session, year
                        )

                        for holiday in holidays:
                            # Create unique key for deduplication
                            holiday_key = (holiday.name, holiday.date)

                            if holiday_key in existing_holidays:
                                skipped_count += 1
                                logger.debug(
                                    f"Skipping existing holiday: {holiday.name} "
                                    f"on {holiday.date}"
                                )
                                continue

                            try:
                                await _create_holiday_date(
                                    date_service,
                                    holiday,
                                )
                                synced_count += 1
                                logger.info(
                                    f"Created holiday: {holiday.name} on {holiday.date}"
                                )
                            except Exception as e:
                                error_count += 1
                                logger.error(
                                    f"Failed to create holiday {holiday.name}: {e}"
                                )

                    except Exception as e:
                        error_count += 1
                        logger.error(f"Failed to sync holidays for year {year}: {e}")

                # Commit all changes
                await session.commit()

                logger.info(
                    f"Holiday sync complete - "
                    f"Synced: {synced_count}, Skipped: {skipped_count}, "
                    f"Errors: {error_count}"
                )

            except Exception as e:
                # Rollback on any error during processing
                await session.rollback()
                logger.error(f"Error during holiday sync, rolled back: {e}", exc_info=True)
                raise

    except Exception as e:
        logger.error(f"Error in sync_chinese_holidays job: {e}", exc_info=True)
        raise

    finally:
        await engine.dispose()

    return {
        "synced": synced_count,
        "skipped": skipped_count,
        "errors": error_count,
        "years": years_processed,
        "time": local_now().isoformat()
    }


async def _get_existing_holidays(
    session: AsyncSession,
    year: int,
) -> Set[tuple]:
    """
    Get existing holidays for a year to avoid duplicates.

    Returns a set of (name, date) tuples.
    """
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    stmt = select(ImportantDate).where(
        and_(
            ImportantDate.family_id == SYSTEM_FAMILY_ID,
            ImportantDate.solar_date >= start_date,
            ImportantDate.solar_date <= end_date,
            ImportantDate.date_type.in_([
                DateType.HOLIDAY_LEGAL.value,
                DateType.HOLIDAY_LUNAR.value,
                DateType.HOLIDAY_SOLAR_TERM.value,
            ])
        )
    )

    result = await session.execute(stmt)
    existing = result.scalars().all()

    return {(h.title, h.solar_date) for h in existing}


async def _create_holiday_date(
    date_service,
    holiday,
) -> ImportantDate:
    """
    Create an ImportantDate record for a holiday.

    Uses the appropriate reminder offsets based on holiday type/importance.
    """
    from .calendar_adapter import HolidayType

    dt = _holiday_type_to_date_type(holiday.holiday_type)
    reminder_offsets_list = get_reminder_offsets(holiday.name)

    # Determine if this is a lunar-based date
    lunar = is_lunar_holiday(holiday.name)

    # Build notes with preparation tips
    notes = holiday.description or ""
    if holiday.lunar_date:
        notes = f"农历{holiday.lunar_date}\n{notes}"

    return await date_service.create_date(
        family_id=SYSTEM_FAMILY_ID,
        title=holiday.name,
        date_value=holiday.date,
        date_type=dt.value,
        created_by=SYSTEM_USER_ID,
        linked_member_id=None,
        recurrence="yearly",
        reminder_days=reminder_offsets_list,
        notes=notes,
        is_lunar=lunar,
        lunar_year=holiday.date.year if lunar else None,
        source="holiday_sync",
        importance_level=5 if holiday.holiday_type == HolidayType.LEGAL else 3,
    )


def create_holiday_sync_scheduler() -> CronScheduler:
    """
    Create and configure the holiday sync scheduler.

    Runs daily at midnight (00:00).

    Returns:
        Configured CronScheduler instance
    """
    scheduler = CronScheduler(name="holiday_sync_scheduler")

    # Register the holiday sync job
    scheduler.register_job(CronJob(
        name="sync_chinese_holidays",
        func=sync_chinese_holidays,
        cron_expression="0 0 * * *",  # Daily at midnight
        description="Sync Chinese holidays from calendar sources",
        priority=JobPriority.NORMAL,
        timeout_seconds=600,  # 10 minutes max
        max_retries=3,
        retry_delay_seconds=300,  # 5 minutes between retries
        enabled=True,
        tags=["holidays", "sync", "daily"]
    ))

    return scheduler


# Default scheduler instance (created on demand)
_holiday_sync_scheduler: Optional[CronScheduler] = None


def get_holiday_sync_scheduler() -> CronScheduler:
    """Get or create the default holiday sync scheduler."""
    global _holiday_sync_scheduler
    if _holiday_sync_scheduler is None:
        _holiday_sync_scheduler = create_holiday_sync_scheduler()
    return _holiday_sync_scheduler


@shared_task(name="scheduler.holiday_sync")
def holiday_sync_beat_task() -> dict:
    """
    Celery Beat task: sync Chinese holidays daily at 00:00.

    Migrated from in-process CronScheduler.
    """
    return run_async(sync_chinese_holidays())


# ─── Holiday Preparation Tasks ────────────────────────────────────────────────


async def create_holiday_preparations() -> Dict[str, Any]:
    """
    Daily job to create holiday preparation tasks.

    Checks for upcoming holidays within their trigger windows and creates
    preparation task hierarchies (parent + subtasks) for each.

    Trigger windows:
    - Major holidays (春节, 国庆, 中秋): 30 days before
    - Minor holidays (元旦, 清明, 端午, etc.): 7 days before
    - Solar terms: 3 days before

    Returns:
        Summary dict with created, skipped, and failed counts
    """
    from .holiday_preparation_service import HolidayPreparationService

    logger.info("Starting create_holiday_preparations job")

    # Create database session
    engine = create_async_engine(settings.database_url, echo=False, connect_args=settings.database_connect_args)
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    result = {
        "created": 0,
        "skipped": 0,
        "failed": 0,
        "total_checked": 0,
        "time": local_now().isoformat(),
    }

    try:
        async with async_session_factory() as session:
            try:
                # Initialize service
                service = HolidayPreparationService(session)

                # Process all upcoming holidays
                summary = await service.process_all_upcoming_preparations(
                    family_id=SYSTEM_FAMILY_ID,
                    creator_id=SYSTEM_USER_ID,
                )

                result.update(summary)

                # Commit all changes
                await session.commit()

                logger.info(
                    f"Holiday preparation job complete - "
                    f"Created: {result['created']}, "
                    f"Skipped: {result['skipped']}, "
                    f"Failed: {result['failed']}"
                )

            except Exception as e:
                await session.rollback()
                logger.error(
                    f"Error in create_holiday_preparations job, rolled back: {e}",
                    exc_info=True
                )
                raise

    except Exception as e:
        logger.error(f"Error in create_holiday_preparations job: {e}", exc_info=True)
        raise

    finally:
        await engine.dispose()

    return result


def create_holiday_preparation_scheduler() -> CronScheduler:
    """
    Create and configure the holiday preparation scheduler.

    Runs daily at 00:30 (after holiday sync at 00:00).

    Returns:
        Configured CronScheduler instance
    """
    scheduler = CronScheduler(name="holiday_preparation_scheduler")

    # Register the preparation job
    scheduler.register_job(CronJob(
        name="create_holiday_preparations",
        func=create_holiday_preparations,
        cron_expression="30 0 * * *",  # Daily at 00:30
        description="Create preparation tasks for upcoming holidays",
        priority=JobPriority.NORMAL,
        timeout_seconds=600,  # 10 minutes max
        max_retries=2,
        retry_delay_seconds=300,  # 5 minutes between retries
        enabled=True,
        tags=["holiday", "preparation", "daily"]
    ))

    return scheduler


# Default scheduler instance (created on demand)
_holiday_preparation_scheduler: Optional[CronScheduler] = None


def get_holiday_preparation_scheduler() -> CronScheduler:
    """Get or create the default holiday preparation scheduler."""
    global _holiday_preparation_scheduler
    if _holiday_preparation_scheduler is None:
        _holiday_preparation_scheduler = create_holiday_preparation_scheduler()
    return _holiday_preparation_scheduler


@shared_task(name="scheduler.holiday_preparation")
def holiday_preparation_beat_task() -> dict:
    """
    Celery Beat task: create holiday preparations daily at 06:00.

    Migrated from in-process CronScheduler.
    """
    return run_async(create_holiday_preparations())


__all__ = [
    "send_single_reminder_task",
    "holiday_sync_beat_task",
    "holiday_preparation_beat_task",
    "send_pending_reminders",
    "sync_chinese_holidays",
    "create_holiday_preparations",
]
