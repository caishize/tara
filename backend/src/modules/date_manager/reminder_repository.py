"""
Smart Reminder Repository.

Canonical location for SmartReminder + UserActivityPattern CRUD.
The ORM classes are still defined in assistant/models/smart_reminder.py
during the coexistence period.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import SmartReminder, UserActivityPattern
from ...core.utils.timezone import utc_now


class ReminderRepository:
    """智能提醒仓库"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # SmartReminder methods
    async def create_reminder(
        self,
        user_id: UUID,
        family_id: UUID,
        source_type: str,
        source_id: UUID,
        title: str,
        content: str,
        urgency_level: str,
        next_send_at: Optional[datetime] = None,
        strategy: Optional[dict] = None,
    ) -> SmartReminder:
        """创建智能提醒"""
        reminder = SmartReminder(
            user_id=user_id,
            family_id=family_id,
            source_type=source_type,
            source_id=source_id,
            title=title,
            content=content,
            urgency_level=urgency_level,
            next_send_at=next_send_at or utc_now(),
            strategy=strategy,
        )
        self.db.add(reminder)
        await self.db.commit()
        await self.db.refresh(reminder)
        return reminder

    async def get_reminder(self, reminder_id: UUID) -> Optional[SmartReminder]:
        """获取提醒"""
        result = await self.db.execute(
            select(SmartReminder).where(SmartReminder.id == reminder_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_reminders(
        self,
        before: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[SmartReminder]:
        """获取待发送的提醒"""
        check_time = before or utc_now()
        result = await self.db.execute(
            select(SmartReminder)
            .where(
                SmartReminder.status == "pending",
                SmartReminder.next_send_at <= check_time,
            )
            .order_by(SmartReminder.next_send_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_reminders(
        self,
        user_id: UUID,
        status: Optional[str] = None,
    ) -> List[SmartReminder]:
        """获取用户提醒"""
        query = select(SmartReminder).where(SmartReminder.user_id == user_id)
        if status:
            query = query.where(SmartReminder.status == status)
        query = query.order_by(SmartReminder.next_send_at.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_reminder(
        self,
        reminder_id: UUID,
        **kwargs,
    ) -> Optional[SmartReminder]:
        """更新提醒"""
        kwargs["updated_at"] = utc_now()
        await self.db.execute(
            update(SmartReminder)
            .where(SmartReminder.id == reminder_id)
            .values(**kwargs)
        )
        await self.db.commit()
        return await self.get_reminder(reminder_id)

    async def mark_sent(self, reminder_id: UUID) -> Optional[SmartReminder]:
        """标记已发送"""
        return await self.update_reminder(
            reminder_id,
            status="sent",
            last_sent_at=utc_now(),
        )

    async def mark_acknowledged(self, reminder_id: UUID) -> Optional[SmartReminder]:
        """标记已确认"""
        return await self.update_reminder(
            reminder_id,
            status="acknowledged",
            acknowledged_at=utc_now(),
        )

    async def increment_retry(
        self,
        reminder_id: UUID,
        next_send_at: datetime,
    ) -> Optional[SmartReminder]:
        """增加重试次数"""
        reminder = await self.get_reminder(reminder_id)
        if not reminder:
            return None

        return await self.update_reminder(
            reminder_id,
            retry_count=reminder.retry_count + 1,
            next_send_at=next_send_at,
            status="pending",
        )

    async def cancel_reminder(self, reminder_id: UUID) -> Optional[SmartReminder]:
        """取消提醒"""
        return await self.update_reminder(reminder_id, status="cancelled")

    async def get_by_source(
        self,
        source_type: str,
        source_id: UUID,
    ) -> Optional[SmartReminder]:
        """根据来源获取提醒"""
        result = await self.db.execute(
            select(SmartReminder).where(
                SmartReminder.source_type == source_type,
                SmartReminder.source_id == source_id,
                SmartReminder.status.in_(["pending", "sent"]),
            )
        )
        return result.scalar_one_or_none()

    # UserActivityPattern methods
    async def get_user_pattern(self, user_id: UUID) -> Optional[UserActivityPattern]:
        """获取用户活跃模式"""
        result = await self.db.execute(
            select(UserActivityPattern).where(UserActivityPattern.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def save_user_pattern(
        self,
        user_id: UUID,
        weekday_active_hours: Optional[List[int]] = None,
        weekend_active_hours: Optional[List[int]] = None,
        preferred_reminder_times: Optional[dict] = None,
        busy_patterns: Optional[List[dict]] = None,
        response_rate: Optional[float] = None,
        avg_response_time_minutes: Optional[int] = None,
    ) -> UserActivityPattern:
        """保存用户活跃模式"""
        existing = await self.get_user_pattern(user_id)

        if existing:
            # 更新
            await self.db.execute(
                update(UserActivityPattern)
                .where(UserActivityPattern.user_id == user_id)
                .values(
                    weekday_active_hours=weekday_active_hours,
                    weekend_active_hours=weekend_active_hours,
                    preferred_reminder_times=preferred_reminder_times,
                    busy_patterns=busy_patterns,
                    response_rate=response_rate,
                    avg_response_time_minutes=avg_response_time_minutes,
                    last_analyzed_at=utc_now(),
                    updated_at=utc_now(),
                )
            )
            await self.db.commit()
            return await self.get_user_pattern(user_id)
        else:
            # 创建
            pattern = UserActivityPattern(
                user_id=user_id,
                weekday_active_hours=weekday_active_hours,
                weekend_active_hours=weekend_active_hours,
                preferred_reminder_times=preferred_reminder_times,
                busy_patterns=busy_patterns,
                response_rate=response_rate,
                avg_response_time_minutes=avg_response_time_minutes,
                last_analyzed_at=utc_now(),
            )
            self.db.add(pattern)
            await self.db.commit()
            await self.db.refresh(pattern)
            return pattern
