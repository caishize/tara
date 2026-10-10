"""
Preparation Repository
"""

from datetime import datetime, date, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
# selectinload removed - tasks relationship no longer exists

from .models import PreparationPlan, PreparationTask
from ...core.utils.timezone import utc_now, local_today


class PreparationRepository:
    """准备方案仓库"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # PreparationPlan methods
    async def create_plan(
        self,
        family_id: UUID,
        event_type: str,
        event_id: UUID,
        event_date: date,
        title: str,
        plan_content: dict,
        member_id: Optional[UUID] = None,
    ) -> PreparationPlan:
        """创建准备方案"""
        plan = PreparationPlan(
            family_id=family_id,
            event_type=event_type,
            event_id=event_id,
            event_date=event_date,
            member_id=member_id,
            title=title,
            plan_content=plan_content,
        )
        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def get_plan(self, plan_id: UUID) -> Optional[PreparationPlan]:
        """获取方案"""
        result = await self.db.execute(
            select(PreparationPlan)
            .where(PreparationPlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def get_plan_by_event(
        self,
        family_id: UUID,
        event_type: str,
        event_id: UUID,
    ) -> Optional[PreparationPlan]:
        """根据事件获取方案"""
        result = await self.db.execute(
            select(PreparationPlan)
            .where(
                PreparationPlan.family_id == family_id,
                PreparationPlan.event_type == event_type,
                PreparationPlan.event_id == event_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_family_plans(
        self,
        family_id: UUID,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[PreparationPlan]:
        """获取家庭方案列表"""
        query = select(PreparationPlan).where(
            PreparationPlan.family_id == family_id
        )
        if status:
            query = query.where(PreparationPlan.status == status)

        query = query.order_by(PreparationPlan.event_date.asc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_upcoming_plans(
        self,
        family_id: UUID,
        days: int = 30,
    ) -> List[PreparationPlan]:
        """获取即将到来的方案"""
        end_date = local_today() + timedelta(days=days)
        result = await self.db.execute(
            select(PreparationPlan)
            .where(
                PreparationPlan.family_id == family_id,
                PreparationPlan.event_date >= local_today(),
                PreparationPlan.event_date <= end_date,
                PreparationPlan.status.in_(["draft", "sent", "adopted"]),
            )
            .order_by(PreparationPlan.event_date.asc())
        )
        return list(result.scalars().all())

    async def update_plan(
        self,
        plan_id: UUID,
        **kwargs,
    ) -> Optional[PreparationPlan]:
        """更新方案"""
        kwargs["updated_at"] = utc_now()
        await self.db.execute(
            update(PreparationPlan)
            .where(PreparationPlan.id == plan_id)
            .values(**kwargs)
        )
        await self.db.commit()
        return await self.get_plan(plan_id)

    async def adopt_plan(
        self,
        plan_id: UUID,
        selections: dict,
    ) -> Optional[PreparationPlan]:
        """采纳方案"""
        return await self.update_plan(
            plan_id,
            status="adopted",
            adopted_selections=selections,
            adopted_at=utc_now(),
        )

    async def mark_notified(self, plan_id: UUID) -> Optional[PreparationPlan]:
        """标记已通知"""
        return await self.update_plan(
            plan_id,
            status="sent",
            notified_at=utc_now(),
        )

    # PreparationTask methods
    async def create_task(
        self,
        plan_id: UUID,
        title: str,
        task_type: Optional[str] = None,
        assignee_id: Optional[UUID] = None,
        due_date: Optional[date] = None,
        metadata: Optional[dict] = None,
    ) -> PreparationTask:
        """创建准备任务"""
        task = PreparationTask(
            plan_id=plan_id,
            title=title,
            task_type=task_type,
            assignee_id=assignee_id,
            due_date=due_date,
            metadata=metadata,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_task(self, task_id: UUID) -> Optional[PreparationTask]:
        """获取任务"""
        result = await self.db.execute(
            select(PreparationTask).where(PreparationTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_plan_tasks(self, plan_id: UUID) -> List[PreparationTask]:
        """获取方案的所有任务"""
        result = await self.db.execute(
            select(PreparationTask)
            .where(PreparationTask.plan_id == plan_id)
            .order_by(PreparationTask.due_date.asc().nullslast())
        )
        return list(result.scalars().all())

    async def update_task(
        self,
        task_id: UUID,
        **kwargs,
    ) -> Optional[PreparationTask]:
        """更新任务"""
        kwargs["updated_at"] = utc_now()
        await self.db.execute(
            update(PreparationTask)
            .where(PreparationTask.id == task_id)
            .values(**kwargs)
        )
        await self.db.commit()
        return await self.get_task(task_id)

    async def complete_task(self, task_id: UUID) -> Optional[PreparationTask]:
        """完成任务"""
        return await self.update_task(
            task_id,
            status="completed",
            completed_at=utc_now(),
        )

    async def get_overdue_tasks(self, family_id: UUID) -> List[PreparationTask]:
        """获取逾期任务"""
        result = await self.db.execute(
            select(PreparationTask)
            .join(PreparationPlan)
            .where(
                PreparationPlan.family_id == family_id,
                PreparationTask.status == "pending",
                PreparationTask.due_date < local_today(),
            )
        )
        return list(result.scalars().all())
