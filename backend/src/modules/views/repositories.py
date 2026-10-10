"""
Kanban repositories — Family Task and Today View data access.

Migrated from assistant/repositories/task_repository.py and today_repository.py.
"""

from datetime import datetime, date, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import FamilyTask, TodayItem, AISuggestion
from ...core.utils.timezone import utc_now, local_today
from ..curation.services.query_utils import escape_like


class FamilyTaskRepository:
    """家庭协作任务仓库"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(
        self,
        family_id: UUID,
        title: str,
        creator_id: UUID,
        description: Optional[str] = None,
        task_type: Optional[str] = None,
        assignee_id: Optional[UUID] = None,
        parent_task_id: Optional[UUID] = None,
        due_date: Optional[date] = None,
        due_time: Optional[datetime] = None,
        priority: str = "normal",
        metadata: Optional[dict] = None,
    ) -> FamilyTask:
        """创建任务"""
        task = FamilyTask(
            family_id=family_id,
            title=title,
            creator_id=creator_id,
            description=description,
            task_type=task_type,
            assignee_id=assignee_id,
            parent_task_id=parent_task_id,
            due_date=due_date,
            due_time=due_time.time() if due_time else None,
            priority=priority,
            task_metadata=metadata,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_task(self, task_id: UUID) -> Optional[FamilyTask]:
        """获取任务"""
        result = await self.db.execute(
            select(FamilyTask)
            .where(FamilyTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_family_tasks(
        self,
        family_id: UUID,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        assignee_id: Optional[UUID] = None,
        parent_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> List[FamilyTask]:
        """获取家庭任务列表"""
        query = select(FamilyTask).where(FamilyTask.family_id == family_id)

        if status:
            query = query.where(FamilyTask.status == status)
        if task_type:
            query = query.where(FamilyTask.task_type == task_type)
        if assignee_id:
            query = query.where(FamilyTask.assignee_id == assignee_id)
        if parent_only:
            query = query.where(FamilyTask.parent_task_id.is_(None))

        # 按优先级和截止日期排序
        query = query.order_by(
            FamilyTask.due_date.asc().nullslast(),
            FamilyTask.priority.desc(),
        )

        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_user_tasks(
        self,
        user_id: UUID,
        family_id: UUID,
        status: Optional[str] = None,
        include_created: bool = False,
    ) -> List[FamilyTask]:
        """获取用户的任务（分配给我的或我创建的）"""
        conditions = [
            FamilyTask.family_id == family_id,
            FamilyTask.parent_task_id.is_(None),
        ]

        if include_created:
            conditions.append(
                or_(
                    FamilyTask.assignee_id == user_id,
                    FamilyTask.creator_id == user_id,
                )
            )
        else:
            conditions.append(FamilyTask.assignee_id == user_id)

        if status:
            conditions.append(FamilyTask.status == status)

        query = (
            select(FamilyTask)
            .where(and_(*conditions))
            .order_by(
                FamilyTask.due_date.asc().nullslast(),
                FamilyTask.priority.desc(),
            )
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_today_tasks(
        self,
        family_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> List[FamilyTask]:
        """获取今日任务"""
        today = local_today()
        query = select(FamilyTask).where(
            FamilyTask.family_id == family_id,
            FamilyTask.due_date == today,
            FamilyTask.status.in_(["pending", "in_progress"]),
        )

        if user_id:
            query = query.where(
                or_(
                    FamilyTask.assignee_id == user_id,
                    FamilyTask.assignee_id.is_(None),
                )
            )

        query = query.order_by(
            FamilyTask.due_time.asc().nullslast(),
            FamilyTask.priority.desc(),
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_overdue_tasks(
        self,
        family_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> List[FamilyTask]:
        """获取逾期任务"""
        today = local_today()
        query = select(FamilyTask).where(
            FamilyTask.family_id == family_id,
            FamilyTask.due_date < today,
            FamilyTask.status.in_(["pending", "in_progress"]),
        )

        if user_id:
            query = query.where(
                or_(
                    FamilyTask.assignee_id == user_id,
                    FamilyTask.assignee_id.is_(None),
                )
            )

        query = query.order_by(
            FamilyTask.due_date.asc(),
            FamilyTask.priority.desc(),
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_pending_tasks(
        self,
        family_id: UUID,
        user_id: Optional[UUID] = None,
        limit: int = 20,
    ) -> List[FamilyTask]:
        """获取当前待办任务（今天及以后 + 无截止日期），不含已逾期"""
        today = local_today()
        query = select(FamilyTask).where(
            FamilyTask.family_id == family_id,
            FamilyTask.status.in_(["pending", "in_progress"]),
            FamilyTask.parent_task_id.is_(None),
            or_(
                FamilyTask.due_date >= today,
                FamilyTask.due_date.is_(None),
            ),
        )

        if user_id:
            query = query.where(
                or_(
                    FamilyTask.assignee_id == user_id,
                    FamilyTask.assignee_id.is_(None),
                )
            )

        query = query.order_by(
            FamilyTask.due_date.asc().nullslast(),
            FamilyTask.priority.desc(),
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_upcoming_tasks(
        self,
        family_id: UUID,
        days: int = 7,
        user_id: Optional[UUID] = None,
    ) -> List[FamilyTask]:
        """获取即将到来的任务"""
        today = local_today()
        end_date = today + timedelta(days=days)

        query = select(FamilyTask).where(
            FamilyTask.family_id == family_id,
            FamilyTask.due_date > today,
            FamilyTask.due_date <= end_date,
            FamilyTask.status.in_(["pending", "in_progress"]),
        )

        if user_id:
            query = query.where(
                or_(
                    FamilyTask.assignee_id == user_id,
                    FamilyTask.assignee_id.is_(None),
                )
            )

        query = query.order_by(
            FamilyTask.due_date.asc(),
            FamilyTask.priority.desc(),
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_tasks(
        self,
        family_id: UUID,
        user_id: Optional[UUID] = None,
        limit: int = 10,
    ) -> List[FamilyTask]:
        """获取所有活跃任务（包括无日期的），用于上下文查询"""
        query = select(FamilyTask).where(
            FamilyTask.family_id == family_id,
            FamilyTask.status.in_(["pending", "in_progress"]),
            FamilyTask.parent_task_id.is_(None),
        )

        if user_id:
            query = query.where(
                or_(
                    FamilyTask.assignee_id == user_id,
                    FamilyTask.assignee_id.is_(None),
                )
            )

        # 按创建时间倒序（最新的任务优先），然后按优先级
        query = query.order_by(
            FamilyTask.created_at.desc(),
            FamilyTask.priority.desc(),
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_tasks_by_keyword(
        self,
        family_id: UUID,
        keyword: str,
        user_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> List[FamilyTask]:
        """根据关键词搜索任务（标题或描述）"""
        # Validate keyword
        if not keyword or not keyword.strip():
            return []

        # Limit keyword length to prevent performance issues
        keyword = keyword.strip()[:100]

        # Escape special SQL LIKE characters to prevent pattern manipulation
        escaped_keyword = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_pattern = f"%{escaped_keyword}%"
        query = select(FamilyTask).where(
            FamilyTask.family_id == family_id,
            FamilyTask.status.in_(["pending", "in_progress"]),
            or_(
                FamilyTask.title.ilike(search_pattern),
                FamilyTask.description.ilike(search_pattern),
            ),
        )

        if user_id:
            query = query.where(
                or_(
                    FamilyTask.assignee_id == user_id,
                    FamilyTask.assignee_id.is_(None),
                )
            )

        query = query.order_by(
            FamilyTask.created_at.desc(),
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_task(
        self,
        task_id: UUID,
        **kwargs,
    ) -> Optional[FamilyTask]:
        """更新任务"""
        kwargs["updated_at"] = utc_now()
        await self.db.execute(
            update(FamilyTask)
            .where(FamilyTask.id == task_id)
            .values(**kwargs)
        )
        await self.db.commit()
        return await self.get_task(task_id)

    async def assign_task(
        self,
        task_id: UUID,
        assignee_id: UUID,
    ) -> Optional[FamilyTask]:
        """分配任务"""
        return await self.update_task(task_id, assignee_id=assignee_id)

    async def start_task(self, task_id: UUID) -> Optional[FamilyTask]:
        """开始任务"""
        return await self.update_task(task_id, status="in_progress")

    async def complete_task(self, task_id: UUID) -> Optional[FamilyTask]:
        """完成任务"""
        return await self.update_task(
            task_id,
            status="completed",
            completed_at=utc_now(),
        )

    async def cancel_task(self, task_id: UUID) -> Optional[FamilyTask]:
        """取消任务"""
        return await self.update_task(task_id, status="cancelled")

    async def delete_task(self, task_id: UUID) -> bool:
        """删除任务（会级联删除子任务）"""
        result = await self.db.execute(
            delete(FamilyTask)
            .where(FamilyTask.id == task_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def get_subtasks(self, parent_task_id: UUID) -> List[FamilyTask]:
        """获取子任务"""
        result = await self.db.execute(
            select(FamilyTask)
            .where(FamilyTask.parent_task_id == parent_task_id)
            .order_by(
                FamilyTask.status.asc(),
                FamilyTask.due_date.asc().nullslast(),
            )
        )
        return list(result.scalars().all())

    async def complete_all_subtasks(self, parent_task_id: UUID) -> int:
        """完成所有子任务"""
        now = utc_now()
        result = await self.db.execute(
            update(FamilyTask)
            .where(
                FamilyTask.parent_task_id == parent_task_id,
                FamilyTask.status != "completed",
            )
            .values(
                status="completed",
                completed_at=now,
                updated_at=now,
            )
        )
        await self.db.commit()
        return result.rowcount

    async def get_task_statistics(
        self,
        family_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> dict:
        """获取任务统计"""
        base_query = select(FamilyTask).where(
            FamilyTask.family_id == family_id,
            FamilyTask.parent_task_id.is_(None),
        )

        if user_id:
            base_query = base_query.where(
                or_(
                    FamilyTask.assignee_id == user_id,
                    FamilyTask.assignee_id.is_(None),
                )
            )

        # 按状态统计
        status_result = await self.db.execute(
            select(FamilyTask.status, func.count(FamilyTask.id))
            .where(
                FamilyTask.family_id == family_id,
                FamilyTask.parent_task_id.is_(None),
            )
            .group_by(FamilyTask.status)
        )
        status_counts = dict(status_result.all())

        # 统计逾期任务
        today = local_today()
        overdue_result = await self.db.execute(
            select(func.count(FamilyTask.id))
            .where(
                FamilyTask.family_id == family_id,
                FamilyTask.due_date < today,
                FamilyTask.status.in_(["pending", "in_progress"]),
            )
        )
        overdue_count = overdue_result.scalar() or 0

        # 统计今日任务
        today_result = await self.db.execute(
            select(func.count(FamilyTask.id))
            .where(
                FamilyTask.family_id == family_id,
                FamilyTask.due_date == today,
                FamilyTask.status.in_(["pending", "in_progress"]),
            )
        )
        today_count = today_result.scalar() or 0

        return {
            "total": sum(status_counts.values()),
            "pending": status_counts.get("pending", 0),
            "in_progress": status_counts.get("in_progress", 0),
            "completed": status_counts.get("completed", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "overdue": overdue_count,
            "today": today_count,
        }

    async def search_tasks(
        self,
        family_id: UUID,
        keyword: str,
        limit: int = 20,
    ) -> List[FamilyTask]:
        """搜索任务"""
        if not keyword or not keyword.strip():
            return []
        keyword = keyword.strip()[:100]
        search_pattern = f"%{escape_like(keyword)}%"
        result = await self.db.execute(
            select(FamilyTask)
            .where(
                FamilyTask.family_id == family_id,
                or_(
                    FamilyTask.title.ilike(search_pattern, escape="\\"),
                    FamilyTask.description.ilike(search_pattern, escape="\\"),
                ),
            )
            .order_by(FamilyTask.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_tasks_by_source(
        self,
        family_id: UUID,
        source_type: str,
        source_id: UUID,
    ) -> List[FamilyTask]:
        """根据来源获取关联任务"""
        # 搜索metadata中的source字段
        result = await self.db.execute(
            select(FamilyTask)
            .where(
                FamilyTask.family_id == family_id,
                FamilyTask.task_metadata["source"]["type"].astext == source_type,
                FamilyTask.task_metadata["source"]["id"].astext == str(source_id),
            )
            .order_by(FamilyTask.created_at.desc())
        )
        return list(result.scalars().all())


class TodayRepository:
    """今日视图仓库"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # TodayItem methods
    async def create_item(
        self,
        family_id: UUID,
        source_type: str,
        source_id: UUID,
        title: str,
        urgency: str,
        user_id: Optional[UUID] = None,
        description: Optional[str] = None,
        due_datetime: Optional[datetime] = None,
        actions: Optional[List[dict]] = None,
    ) -> TodayItem:
        """创建待办项"""
        item = TodayItem(
            family_id=family_id,
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            title=title,
            description=description,
            urgency=urgency,
            due_datetime=due_datetime,
            actions=actions or [],
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def get_item(self, item_id: UUID) -> Optional[TodayItem]:
        """获取待办项"""
        result = await self.db.execute(
            select(TodayItem).where(TodayItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_by_source(
        self,
        source_type: str,
        source_id: UUID,
    ) -> Optional[TodayItem]:
        """根据来源获取待办项"""
        result = await self.db.execute(
            select(TodayItem).where(
                TodayItem.source_type == source_type,
                TodayItem.source_id == source_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_family_items(
        self,
        family_id: UUID,
        status: str = "pending",
        urgency: Optional[str] = None,
    ) -> List[TodayItem]:
        """获取家庭待办项"""
        query = select(TodayItem).where(
            TodayItem.family_id == family_id,
            TodayItem.status == status,
        )
        if urgency:
            query = query.where(TodayItem.urgency == urgency)

        query = query.order_by(TodayItem.due_datetime.asc().nullslast())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_user_items(
        self,
        user_id: UUID,
        family_id: UUID,
        status: str = "pending",
    ) -> List[TodayItem]:
        """获取用户待办项"""
        result = await self.db.execute(
            select(TodayItem).where(
                TodayItem.family_id == family_id,
                or_(
                    TodayItem.user_id == user_id,
                    TodayItem.user_id.is_(None),
                ),
                TodayItem.status == status,
            )
            .order_by(TodayItem.due_datetime.asc().nullslast())
        )
        return list(result.scalars().all())

    async def complete_item(
        self,
        item_id: UUID,
    ) -> Optional[TodayItem]:
        """完成待办项"""
        await self.db.execute(
            update(TodayItem)
            .where(TodayItem.id == item_id)
            .values(
                status="completed",
                completed_at=utc_now(),
                updated_at=utc_now(),
            )
        )
        await self.db.commit()
        return await self.get_item(item_id)

    async def snooze_item(
        self,
        item_id: UUID,
        new_due_datetime: datetime,
    ) -> Optional[TodayItem]:
        """延后待办项"""
        await self.db.execute(
            update(TodayItem)
            .where(TodayItem.id == item_id)
            .values(
                status="snoozed",
                due_datetime=new_due_datetime,
                updated_at=utc_now(),
            )
        )
        await self.db.commit()
        return await self.get_item(item_id)

    async def dismiss_item(self, item_id: UUID) -> bool:
        """忽略待办项"""
        result = await self.db.execute(
            update(TodayItem)
            .where(TodayItem.id == item_id)
            .values(status="dismissed", updated_at=utc_now())
        )
        await self.db.commit()
        return result.rowcount > 0

    async def delete_by_source(
        self,
        source_type: str,
        source_id: UUID,
    ) -> bool:
        """删除来源对应的待办项"""
        result = await self.db.execute(
            delete(TodayItem).where(
                TodayItem.source_type == source_type,
                TodayItem.source_id == source_id,
            )
        )
        await self.db.commit()
        return result.rowcount > 0

    # AISuggestion methods
    async def create_suggestion(
        self,
        family_id: UUID,
        suggestion_type: str,
        content: str,
        user_id: Optional[UUID] = None,
        actions: Optional[List[dict]] = None,
        context: Optional[dict] = None,
        priority: int = 0,
        valid_until: Optional[datetime] = None,
    ) -> AISuggestion:
        """创建AI建议"""
        suggestion = AISuggestion(
            family_id=family_id,
            user_id=user_id,
            suggestion_type=suggestion_type,
            content=content,
            actions=actions or [],
            context=context,
            priority=priority,
            valid_until=valid_until,
        )
        self.db.add(suggestion)
        await self.db.commit()
        await self.db.refresh(suggestion)
        return suggestion

    async def get_active_suggestions(
        self,
        family_id: UUID,
        user_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> List[AISuggestion]:
        """获取有效的AI建议"""
        now = utc_now()
        query = select(AISuggestion).where(
            AISuggestion.family_id == family_id,
            AISuggestion.dismissed_at.is_(None),
            or_(
                AISuggestion.valid_until.is_(None),
                AISuggestion.valid_until > now,
            ),
        )

        if user_id:
            query = query.where(
                or_(
                    AISuggestion.user_id == user_id,
                    AISuggestion.user_id.is_(None),
                )
            )

        query = query.order_by(
            AISuggestion.priority.desc(),
            AISuggestion.created_at.desc(),
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def dismiss_suggestion(self, suggestion_id: UUID) -> bool:
        """忽略建议"""
        result = await self.db.execute(
            update(AISuggestion)
            .where(AISuggestion.id == suggestion_id)
            .values(dismissed_at=utc_now())
        )
        await self.db.commit()
        return result.rowcount > 0

    async def mark_suggestion_acted(self, suggestion_id: UUID) -> bool:
        """标记建议已执行"""
        result = await self.db.execute(
            update(AISuggestion)
            .where(AISuggestion.id == suggestion_id)
            .values(acted_upon_at=utc_now())
        )
        await self.db.commit()
        return result.rowcount > 0
