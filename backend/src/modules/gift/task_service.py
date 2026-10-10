"""Gift task management service.

Manages the gift recommendation task lifecycle:
discovered -> scheduled -> generating -> completed/failed/expired/cancelled.

Merged from gift_orchestration/services/task_service.py
           + gift_orchestration/repositories/task_repository.py
"""
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import GiftTask, TaskStatus, TriggerSource
from ...core.utils.timezone import utc_now
from ...core.events import (
    get_event_bus,
    GiftTaskCreated,
    GiftTaskStatusChanged,
    GIFTABLE_DATE_TYPES,
    DATE_TYPE_TO_OCCASION,
)

logger = logging.getLogger(__name__)

DEFAULT_ADVANCE_DAYS = 30

DATE_TYPE_OCCASION_MAP = {
    "birthday": "birthday",
    "anniversary": "anniversary",
    "holiday": "holiday",
    "graduation": "graduation",
    "wedding": "wedding",
    "newborn": "newborn",
    "housewarming": "housewarming",
    "promotion": "promotion",
    "custom": "custom",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Repository (inlined — was gift_orchestration/repositories/task_repository.py)
# ═══════════════════════════════════════════════════════════════════════════════

class GiftTaskRepository:
    """Data access layer for GiftTask."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, task: GiftTask) -> GiftTask:
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def get_by_id(self, task_id: UUID, family_id: UUID) -> Optional[GiftTask]:
        result = await self.session.execute(
            select(GiftTask).where(
                and_(
                    GiftTask.id == task_id,
                    GiftTask.family_id == family_id,
                    GiftTask.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_date_id(
        self, date_id: UUID, family_id: UUID, include_completed: bool = False
    ) -> List[GiftTask]:
        conditions = [
            GiftTask.important_date_id == date_id,
            GiftTask.family_id == family_id,
            GiftTask.is_deleted == False,
        ]
        if not include_completed:
            conditions.append(
                GiftTask.status.notin_([
                    TaskStatus.COMPLETED.value,
                    TaskStatus.CANCELLED.value,
                    TaskStatus.EXPIRED.value,
                ])
            )
        result = await self.session.execute(
            select(GiftTask).where(and_(*conditions)).order_by(GiftTask.occasion_date.desc())
        )
        return list(result.scalars().all())

    async def get_pending_tasks(
        self, family_id: Optional[UUID] = None, limit: int = 100
    ) -> List[GiftTask]:
        conditions = [GiftTask.status == TaskStatus.PENDING.value, GiftTask.is_deleted == False]
        if family_id:
            conditions.append(GiftTask.family_id == family_id)
        result = await self.session.execute(
            select(GiftTask).where(and_(*conditions)).order_by(GiftTask.scheduled_time.asc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_due_tasks(self, limit: int = 100) -> List[GiftTask]:
        now = utc_now()
        result = await self.session.execute(
            select(GiftTask)
            .where(and_(
                GiftTask.status == TaskStatus.PENDING.value,
                GiftTask.scheduled_time <= now,
                GiftTask.is_deleted == False,
            ))
            .order_by(GiftTask.scheduled_time.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_failed_tasks_for_retry(self, limit: int = 50) -> List[GiftTask]:
        result = await self.session.execute(
            select(GiftTask)
            .where(and_(
                GiftTask.status == TaskStatus.FAILED.value,
                GiftTask.retry_count < GiftTask.max_retries,
                GiftTask.is_deleted == False,
            ))
            .order_by(GiftTask.updated_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_member(
        self,
        member_id: UUID,
        family_id: UUID,
        status: Optional[TaskStatus] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[GiftTask]:
        conditions = [
            GiftTask.member_id == member_id,
            GiftTask.family_id == family_id,
            GiftTask.is_deleted == False,
        ]
        if status:
            conditions.append(GiftTask.status == status.value)
        if from_date:
            conditions.append(GiftTask.occasion_date >= from_date)
        if to_date:
            conditions.append(GiftTask.occasion_date <= to_date)
        result = await self.session.execute(
            select(GiftTask).where(and_(*conditions)).order_by(GiftTask.occasion_date.desc())
        )
        return list(result.scalars().all())

    async def get_upcoming_tasks(
        self, family_id: UUID, days: int = 60, include_overdue: bool = False
    ) -> List[GiftTask]:
        today = date.today()
        end_date = today + timedelta(days=days)
        conditions = [GiftTask.family_id == family_id, GiftTask.is_deleted == False]
        if include_overdue:
            conditions.append(
                or_(
                    and_(
                        GiftTask.status.in_([TaskStatus.PENDING.value, TaskStatus.FAILED.value]),
                        GiftTask.occasion_date < today,
                    ),
                    and_(
                        GiftTask.occasion_date >= today,
                        GiftTask.occasion_date <= end_date,
                        GiftTask.status.in_([
                            TaskStatus.PENDING.value,
                            TaskStatus.SCHEDULED.value,
                            TaskStatus.COMPLETED.value,
                        ]),
                    ),
                )
            )
        else:
            conditions.extend([
                GiftTask.occasion_date >= today,
                GiftTask.occasion_date <= end_date,
                GiftTask.status.in_([
                    TaskStatus.PENDING.value,
                    TaskStatus.SCHEDULED.value,
                    TaskStatus.COMPLETED.value,
                ]),
            ])
        result = await self.session.execute(
            select(GiftTask).where(and_(*conditions)).order_by(GiftTask.occasion_date.asc())
        )
        return list(result.scalars().all())

    async def update_status(self, task_id: UUID, status: TaskStatus, **kwargs) -> Optional[GiftTask]:
        update_data = {"status": status.value, "updated_at": utc_now()}
        update_data.update(kwargs)
        await self.session.execute(
            update(GiftTask).where(GiftTask.id == task_id).values(**update_data)
        )
        await self.session.flush()
        result = await self.session.execute(select(GiftTask).where(GiftTask.id == task_id))
        return result.scalar_one_or_none()

    async def mark_completed(
        self, task_id: UUID, recommendation_id: UUID, processing_time_ms: int
    ) -> Optional[GiftTask]:
        return await self.update_status(
            task_id,
            TaskStatus.COMPLETED,
            recommendation_id=recommendation_id,
            completed_at=utc_now(),
            processing_time_ms=processing_time_ms,
        )

    async def mark_failed(self, task_id: UUID, error_message: str) -> Optional[GiftTask]:
        result = await self.session.execute(select(GiftTask).where(GiftTask.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            return await self.update_status(
                task_id,
                TaskStatus.FAILED,
                error_message=error_message,
                retry_count=task.retry_count + 1,
            )
        return None

    async def mark_generating(self, task_id: UUID) -> Optional[GiftTask]:
        return await self.update_status(
            task_id, TaskStatus.GENERATING, started_at=utc_now()
        )

    async def cancel(self, task_id: UUID, family_id: UUID) -> bool:
        result = await self.session.execute(
            update(GiftTask)
            .where(and_(
                GiftTask.id == task_id,
                GiftTask.family_id == family_id,
                GiftTask.status.in_([TaskStatus.PENDING.value, TaskStatus.SCHEDULED.value]),
            ))
            .values(status=TaskStatus.CANCELLED.value, updated_at=utc_now())
        )
        return result.rowcount > 0

    async def soft_delete(self, task_id: UUID, family_id: UUID) -> bool:
        result = await self.session.execute(
            update(GiftTask)
            .where(and_(GiftTask.id == task_id, GiftTask.family_id == family_id))
            .values(is_deleted=True, updated_at=utc_now())
        )
        return result.rowcount > 0

    async def expire_old_tasks(self, before_date: date) -> int:
        result = await self.session.execute(
            update(GiftTask)
            .where(and_(
                GiftTask.occasion_date < before_date,
                GiftTask.status.in_([
                    TaskStatus.PENDING.value,
                    TaskStatus.SCHEDULED.value,
                    TaskStatus.FAILED.value,
                ]),
                GiftTask.is_deleted == False,
            ))
            .values(status=TaskStatus.EXPIRED.value, updated_at=utc_now())
        )
        return result.rowcount

    async def exists_for_date_year(self, date_id: UUID, occasion_date: date, family_id: UUID) -> bool:
        result = await self.session.execute(
            select(func.count(GiftTask.id)).where(and_(
                GiftTask.important_date_id == date_id,
                GiftTask.occasion_date == occasion_date,
                GiftTask.family_id == family_id,
                GiftTask.is_deleted == False,
            ))
        )
        return result.scalar() > 0

    async def get_stats(self, family_id: UUID) -> Dict[str, int]:
        result = await self.session.execute(
            select(GiftTask.status, func.count(GiftTask.id).label("count"))
            .where(and_(GiftTask.family_id == family_id, GiftTask.is_deleted == False))
            .group_by(GiftTask.status)
        )
        stats: Dict[str, int] = {"total": 0}
        for row in result:
            stats[row.status] = row.count
            stats["total"] += row.count
        return stats


# ═══════════════════════════════════════════════════════════════════════════════
# Service
# ═══════════════════════════════════════════════════════════════════════════════

class GiftTaskService:
    """Gift task lifecycle management."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GiftTaskRepository(session)
        self.event_bus = get_event_bus()

    async def create_task_for_date(
        self,
        family_id: UUID,
        date_id: UUID,
        member_id: UUID,
        date_type: str,
        occasion_date: date,
        title: str,
        reminder_offsets: Optional[List[int]] = None,
        trigger_source: TriggerSource = TriggerSource.AUTO_DATE,
        budget_min: Optional[int] = None,
        budget_max: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Optional[GiftTask]:
        if date_type not in GIFTABLE_DATE_TYPES:
            logger.debug("Date type %s is not giftable, skipping task creation", date_type)
            return None

        exists = await self.repo.exists_for_date_year(date_id, occasion_date, family_id)
        if exists:
            logger.debug("Task already exists for date %s on %s", date_id, occasion_date)
            return None

        scheduled_time = self._calculate_scheduled_time(occasion_date, reminder_offsets)
        occasion = DATE_TYPE_OCCASION_MAP.get(date_type, "custom")

        task = GiftTask(
            family_id=family_id,
            important_date_id=date_id,
            member_id=member_id,
            occasion=occasion,
            occasion_date=occasion_date,
            occasion_title=title,
            scheduled_time=scheduled_time,
            trigger_source=trigger_source.value,
            budget_min=budget_min,
            budget_max=budget_max,
            status=TaskStatus.PENDING.value,
            notes=notes,
        )

        task = await self.repo.create(task)
        logger.info("Created gift task %s for date %s, scheduled at %s", task.id, date_id, scheduled_time)

        await self._register_in_sorted_set(task.id, scheduled_time)

        await self.event_bus.publish(GiftTaskCreated(
            task_id=task.id,
            family_id=family_id,
            important_date_id=date_id,
            member_id=member_id,
            occasion=occasion,
            occasion_date=occasion_date,
            scheduled_time=scheduled_time,
        ))

        return task

    async def _register_in_sorted_set(self, task_id: UUID, scheduled_time: datetime) -> None:
        try:
            from ...core.cache import redis_client
            if redis_client.client is None:
                return
            from ...core.scheduler.redis_scheduler import RedisScheduleStore
            store = RedisScheduleStore(redis_client.client)
            await store.schedule("gift.process_single_task", str(task_id), scheduled_time)
        except Exception as e:
            logger.warning("Failed to register gift task %s in sorted set: %s", task_id, e)

    def _calculate_scheduled_time(
        self, occasion_date: date, reminder_offsets: Optional[List[int]] = None
    ) -> datetime:
        if reminder_offsets:
            earliest_reminder_days = abs(min(reminder_offsets))
            advance_days = earliest_reminder_days + 3
        else:
            advance_days = DEFAULT_ADVANCE_DAYS
        advance_days = max(advance_days, 7)
        recommendation_date = occasion_date - timedelta(days=advance_days)
        return datetime.combine(recommendation_date, time(2, 0), tzinfo=timezone.utc)

    async def get_task(self, task_id: UUID, family_id: UUID) -> Optional[GiftTask]:
        return await self.repo.get_by_id(task_id, family_id)

    async def get_tasks_for_date(
        self, date_id: UUID, family_id: UUID, include_completed: bool = False
    ) -> List[GiftTask]:
        return await self.repo.get_by_date_id(date_id, family_id, include_completed)

    async def get_pending_tasks(
        self, family_id: Optional[UUID] = None, limit: int = 100
    ) -> List[GiftTask]:
        return await self.repo.get_pending_tasks(family_id, limit)

    async def get_due_tasks(self, limit: int = 100) -> List[GiftTask]:
        return await self.repo.get_due_tasks(limit)

    async def get_upcoming_tasks(self, family_id: UUID, days: int = 60) -> List[GiftTask]:
        return await self.repo.get_upcoming_tasks(family_id, days)

    async def _publish_status_changed(
        self, task: GiftTask, old_status: str, new_status: str
    ) -> None:
        """Publish GiftTaskStatusChanged event (best-effort)."""
        try:
            await self.event_bus.publish(GiftTaskStatusChanged(
                task_id=task.id,
                family_id=task.family_id,
                old_status=old_status,
                new_status=new_status,
                gift_name=task.occasion_title,
            ))
        except Exception as e:
            logger.warning("Failed to publish GiftTaskStatusChanged: %s", e)

    async def _get_task_status(self, task_id: UUID) -> str:
        """Get current task status for event publishing."""
        result = await self.session.execute(
            select(GiftTask.status).where(GiftTask.id == task_id)
        )
        row = result.scalar_one_or_none()
        return row or ""

    async def mark_generating(self, task_id: UUID) -> Optional[GiftTask]:
        old_status = await self._get_task_status(task_id)
        result = await self.repo.mark_generating(task_id)
        if result:
            await self._publish_status_changed(result, old_status, TaskStatus.GENERATING.value)
        return result

    async def mark_completed(
        self, task_id: UUID, recommendation_id: UUID, processing_time_ms: int
    ) -> Optional[GiftTask]:
        old_status = await self._get_task_status(task_id)
        result = await self.repo.mark_completed(task_id, recommendation_id, processing_time_ms)
        if result:
            await self._publish_status_changed(result, old_status, TaskStatus.COMPLETED.value)
        return result

    async def mark_failed(self, task_id: UUID, error_message: str) -> Optional[GiftTask]:
        old_status = await self._get_task_status(task_id)
        task = await self.repo.mark_failed(task_id, error_message)
        if task:
            logger.error("Task %s failed: %s", task_id, error_message)
            await self._publish_status_changed(task, old_status, TaskStatus.FAILED.value)
        return task

    async def cancel_task(self, task_id: UUID, family_id: UUID) -> bool:
        old_status = await self._get_task_status(task_id)
        task = await self.repo.get_by_id(task_id, family_id)
        success = await self.repo.cancel(task_id, family_id)
        if success:
            await self._unregister_from_sorted_set(task_id)
            logger.info("Cancelled task %s", task_id)
            if task:
                await self._publish_status_changed(task, old_status, TaskStatus.CANCELLED.value)
        return success

    async def _unregister_from_sorted_set(self, task_id: UUID) -> None:
        try:
            from ...core.cache import redis_client
            if redis_client.client is None:
                return
            from ...core.scheduler.redis_scheduler import RedisScheduleStore
            store = RedisScheduleStore(redis_client.client)
            await store.unschedule("gift.process_single_task", str(task_id))
        except Exception as e:
            logger.warning("Failed to unregister gift task %s from sorted set: %s", task_id, e)

    async def delete_task(self, task_id: UUID, family_id: UUID) -> bool:
        return await self.repo.soft_delete(task_id, family_id)

    async def expire_old_tasks(self) -> int:
        yesterday = date.today() - timedelta(days=1)
        count = await self.repo.expire_old_tasks(yesterday)
        if count > 0:
            logger.info("Expired %d old gift tasks", count)
        return count

    async def retry_failed_tasks(self) -> int:
        tasks = await self.repo.get_failed_tasks_for_retry()
        retried = 0
        for task in tasks:
            await self.repo.update_status(task.id, TaskStatus.PENDING)
            retried += 1
            logger.info("Reset failed task %s for retry (%d/%d)", task.id, task.retry_count + 1, task.max_retries)
        return retried

    async def get_stats(self, family_id: UUID) -> Dict[str, Any]:
        return await self.repo.get_stats(family_id)

    async def update_task_for_date_change(
        self,
        date_id: UUID,
        family_id: UUID,
        new_occasion_date: Optional[date] = None,
        new_member_id: Optional[UUID] = None,
    ) -> Optional[GiftTask]:
        tasks = await self.repo.get_by_date_id(date_id, family_id, include_completed=False)
        for task in tasks:
            updates: Dict[str, Any] = {}
            if new_occasion_date and new_occasion_date != task.occasion_date:
                updates["occasion_date"] = new_occasion_date
                updates["scheduled_time"] = self._calculate_scheduled_time(new_occasion_date)
            if new_member_id and new_member_id != task.member_id:
                updates["member_id"] = new_member_id
            if updates:
                await self.repo.update_status(task.id, TaskStatus(task.status), **updates)
                logger.info("Updated task %s due to date change", task.id)
        return tasks[0] if tasks else None

    async def cancel_tasks_for_date(self, date_id: UUID, family_id: UUID) -> int:
        tasks = await self.repo.get_by_date_id(date_id, family_id, include_completed=False)
        cancelled = 0
        for task in tasks:
            if await self.repo.cancel(task.id, family_id):
                cancelled += 1
        if cancelled > 0:
            logger.info("Cancelled %d tasks for date %s", cancelled, date_id)
        return cancelled
