"""
日期事件处理器

处理重要日期创建、更新、删除事件，自动创建礼物推荐任务。
"""
import logging
from typing import Optional
from uuid import UUID

from ..event_bus import event_handler
from ..domain_events import (
    ImportantDateCreated,
    ImportantDateUpdated,
    ImportantDateDeleted,
    GIFTABLE_DATE_TYPES,
)

logger = logging.getLogger(__name__)


# 这些处理器将在应用启动时通过依赖注入获取服务实例
# 这里定义处理器工厂函数

def create_date_created_handler(task_service):
    """创建日期创建事件处理器"""

    @event_handler(ImportantDateCreated)
    async def on_date_created(event: ImportantDateCreated):
        """
        处理重要日期创建事件

        当创建可送礼类型的日期时，自动创建礼物推荐任务。
        """
        logger.info(f"Handling ImportantDateCreated event for date {event.date_id}")

        # 检查是否需要送礼
        if event.date_type not in GIFTABLE_DATE_TYPES:
            logger.debug(f"Date type {event.date_type} is not giftable, skipping")
            return

        # custom 类型需要检查 needs_gift 标记
        if event.date_type == "custom" and not event.needs_gift:
            logger.debug("Custom date does not need gift, skipping")
            return

        # 必须有关联成员才能送礼
        if event.member_id is None:
            logger.debug("Date has no associated member, skipping gift task creation")
            return

        try:
            # 创建礼物推荐任务
            task = await task_service.create_task_for_date(
                family_id=event.family_id,
                date_id=event.date_id,
                member_id=event.member_id,
                date_type=event.date_type,
                occasion_date=event.occasion_date,
                title=event.title,
                reminder_offsets=event.reminder_offsets
            )

            if task:
                logger.info(
                    f"Created gift task {task.id} for date {event.date_id}, "
                    f"scheduled at {task.scheduled_time}"
                )
            else:
                logger.debug(f"Gift task already exists or not created for date {event.date_id}")

        except Exception as e:
            logger.error(f"Failed to create gift task for date {event.date_id}: {e}")

    return on_date_created


def create_date_updated_handler(task_service):
    """创建日期更新事件处理器"""

    @event_handler(ImportantDateUpdated)
    async def on_date_updated(event: ImportantDateUpdated):
        """
        处理重要日期更新事件

        当日期或成员变更时，更新关联的礼物任务。
        """
        logger.info(f"Handling ImportantDateUpdated event for date {event.date_id}")

        # 检查是否有需要关注的变更
        relevant_changes = {"occasion_date", "member_id", "date_type"}
        changed_fields = set(event.changes.keys())

        if not changed_fields.intersection(relevant_changes):
            logger.debug("No relevant changes for gift task, skipping")
            return

        try:
            # 获取新值
            new_date = event.new_values.get("occasion_date")
            new_member = event.new_values.get("member_id")

            if new_date or new_member:
                await task_service.update_task_for_date_change(
                    date_id=event.date_id,
                    family_id=event.family_id,
                    new_occasion_date=new_date,
                    new_member_id=UUID(new_member) if new_member else None
                )
                logger.info(f"Updated gift tasks for date {event.date_id}")

        except Exception as e:
            logger.error(f"Failed to update gift tasks for date {event.date_id}: {e}")

    return on_date_updated


def create_date_deleted_handler(task_service):
    """创建日期删除事件处理器"""

    @event_handler(ImportantDateDeleted)
    async def on_date_deleted(event: ImportantDateDeleted):
        """
        处理重要日期删除事件

        当日期被删除时，取消所有关联的待处理礼物任务。
        """
        logger.info(f"Handling ImportantDateDeleted event for date {event.date_id}")

        try:
            cancelled = await task_service.cancel_tasks_for_date(
                date_id=event.date_id,
                family_id=event.family_id
            )

            if cancelled > 0:
                logger.info(f"Cancelled {cancelled} gift tasks for deleted date {event.date_id}")

        except Exception as e:
            logger.error(f"Failed to cancel gift tasks for date {event.date_id}: {e}")

    return on_date_deleted
