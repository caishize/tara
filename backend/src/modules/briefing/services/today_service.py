"""
Today Service - Aggregates all today's items across modules

This is the core service for the "Today View" feature that aggregates:
- Important dates (birthdays, anniversaries, holidays)
- Overdue/due tasks
- Shopping reminders
- Health checkups
- Preparation plans
- AI suggestions
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from ...views.repositories import TodayRepository
from ..preparation_repository import PreparationRepository
from ...date_manager.reminder_repository import ReminderRepository
from ...views.models import TodayItem, AISuggestion
from ...views.kanban_schemas import (
    TodayViewResponse,
    TodayItemResponse,
    TodaySummary,
    AISuggestionResponse,
)
from ....core.utils.timezone import utc_now, local_now, local_today


class TodayService:
    """今日视图聚合服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.today_repo = TodayRepository(db)
        self.preparation_repo = PreparationRepository(db)
        self.reminder_repo = ReminderRepository(db)

    async def get_today_view(
        self,
        family_id: UUID,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """获取今日视图聚合数据"""
        # 1. 获取今日待办项
        today_items = await self._get_today_items(family_id, user_id)

        # 2. 获取AI建议
        suggestions = await self.today_repo.get_active_suggestions(family_id, user_id, limit=3)

        # 3. 获取汇总统计
        summary = await self._build_summary(family_id, user_id, today_items)

        # 4. 按紧急程度分组
        urgent_items = [i for i in today_items if i.urgency == "urgent"]
        important_items = [i for i in today_items if i.urgency == "important"]
        normal_items = [i for i in today_items if i.urgency == "normal"]

        def item_to_dict(item) -> Dict[str, Any]:
            return {
                "id": str(item.id),
                "source_type": item.source_type,
                "source_id": str(item.source_id),
                "title": item.title,
                "description": item.description,
                "urgency": item.urgency,
                "due_datetime": item.due_datetime.isoformat() if item.due_datetime else None,
                "actions": item.actions or [],
                "status": item.status or "pending",
            }

        def suggestion_to_dict(s) -> Dict[str, Any]:
            return {
                "id": str(s.id),
                "suggestion_type": s.suggestion_type,
                "content": s.content,
                "actions": s.actions or [],
                "priority": s.priority or 0,
            }

        return {
            "date": local_today().isoformat(),
            "greeting": await self._generate_greeting(user_id),
            "summary": {
                "total_items": summary.total_items,
                "urgent_count": summary.urgent_count,
                "important_count": summary.important_count,
                "normal_count": summary.normal_count,
                "source_breakdown": summary.source_breakdown,
            },
            "urgent_items": [item_to_dict(i) for i in urgent_items],
            "important_items": [item_to_dict(i) for i in important_items],
            "normal_items": [item_to_dict(i) for i in normal_items],
            "suggestions": [suggestion_to_dict(s) for s in suggestions],
        }

    async def _get_today_items(
        self,
        family_id: UUID,
        user_id: UUID,
    ) -> List[TodayItem]:
        """获取今日所有待办项"""
        # 从数据库获取已有的今日项
        items = await self.today_repo.get_user_items(user_id, family_id)

        # 自动同步其他模块的待办
        await self._sync_important_dates(family_id)
        await self._sync_tasks(family_id)
        await self._sync_shopping_reminders(family_id)
        await self._sync_health_reminders(family_id)
        await self._sync_preparation_tasks(family_id)

        # 重新获取更新后的待办
        return await self.today_repo.get_user_items(user_id, family_id)

    async def _sync_important_dates(self, family_id: UUID) -> None:
        """同步重要日期到今日视图"""
        # 查询今日及近3天的重要日期
        from ...date_manager.models import ImportantDate
        today = local_today()
        end_date = today + timedelta(days=3)

        result = await self.db.execute(
            select(ImportantDate).where(
                ImportantDate.family_id == family_id,
            )
        )
        dates = result.scalars().all()

        for d in dates:
            # 计算今年的日期
            try:
                this_year_date = d.get_next_occurrence()
            except Exception:
                continue

            if this_year_date and today <= this_year_date <= end_date:
                # 检查是否已有对应项
                existing = await self.today_repo.get_by_source("important_date", d.id)
                if not existing:
                    days_until = (this_year_date - today).days
                    urgency = "urgent" if days_until == 0 else "important" if days_until <= 1 else "normal"

                    await self.today_repo.create_item(
                        family_id=family_id,
                        source_type="important_date",
                        source_id=d.id,
                        title=f"{d.title}" + (f" - {d.member.nickname if d.member else ''}" if d.member_id else ""),
                        urgency=urgency,
                        description=f"{'今天' if days_until == 0 else f'{days_until}天后'}",
                        due_datetime=datetime.combine(this_year_date, datetime.min.time()),
                        actions=[
                            {"type": "view", "label": "查看详情"},
                            {"type": "prepare_gift", "label": "准备礼物"},
                            {"type": "send_wish", "label": "发送祝福"},
                        ],
                    )

    async def _sync_tasks(self, family_id: UUID) -> None:
        """同步任务到今日视图"""
        from ...views.repositories import FamilyTaskRepository
        task_repo = FamilyTaskRepository(self.db)

        # 获取今日和逾期任务
        today_tasks = await task_repo.get_today_tasks(family_id)
        overdue_tasks = await task_repo.get_overdue_tasks(family_id)

        for task in today_tasks + overdue_tasks:
            existing = await self.today_repo.get_by_source("family_task", task.id)
            if not existing:
                is_overdue = task.is_overdue
                urgency = "urgent" if is_overdue or task.priority == "urgent" else \
                         "important" if task.priority == "high" else "normal"

                await self.today_repo.create_item(
                    family_id=family_id,
                    source_type="family_task",
                    source_id=task.id,
                    title=task.title,
                    urgency=urgency,
                    user_id=task.assignee_id,
                    description=task.description,
                    due_datetime=task.due_datetime,
                    actions=[
                        {"type": "complete", "label": "完成"},
                        {"type": "snooze", "label": "延后"},
                        {"type": "view", "label": "查看"},
                    ],
                )

    async def _sync_shopping_reminders(self, family_id: UUID) -> None:
        """同步购物提醒到今日视图

        Note: ShoppingItem 通过 ShoppingList 关联 family。
        目前简化处理，跳过购物提醒同步。
        """
        # TODO: Implement proper shopping reminder sync through ShoppingList -> ShoppingItem join
        pass

    async def _sync_health_reminders(self, family_id: UUID) -> None:
        """同步健康提醒到今日视图

        Note: HealthCheckup 模型尚未实现。
        目前简化处理，跳过健康提醒同步。
        """
        # TODO: Implement health reminder sync when HealthCheckup model is available
        pass

    async def _sync_preparation_tasks(self, family_id: UUID) -> None:
        """同步准备方案任务到今日视图"""
        # 获取进行中的准备方案的待办任务
        plans = await self.preparation_repo.get_family_plans(
            family_id, status="adopted", limit=10
        )

        for plan in plans:
            tasks = await self.preparation_repo.get_plan_tasks(plan.id)
            for task in tasks:
                if task.status == "pending" and task.due_date:
                    existing = await self.today_repo.get_by_source("preparation_task", task.id)
                    if not existing:
                        today = local_today()
                        days_until = (task.due_date - today).days
                        if days_until <= 3:
                            urgency = "urgent" if days_until <= 0 else "important" if days_until <= 1 else "normal"

                            await self.today_repo.create_item(
                                family_id=family_id,
                                source_type="preparation_task",
                                source_id=task.id,
                                title=task.title,
                                urgency=urgency,
                                description=f"准备方案: {plan.title}",
                                due_datetime=datetime.combine(task.due_date, datetime.min.time()),
                                actions=[
                                    {"type": "complete", "label": "完成"},
                                    {"type": "view_plan", "label": "查看方案"},
                                ],
                            )

    async def _build_summary(
        self,
        family_id: UUID,
        user_id: UUID,
        items: List[TodayItem],
    ) -> TodaySummary:
        """构建今日汇总"""
        urgent_count = len([i for i in items if i.urgency == "urgent"])
        important_count = len([i for i in items if i.urgency == "important"])
        normal_count = len([i for i in items if i.urgency == "normal"])

        # 统计各来源数量
        source_counts = {}
        for item in items:
            source_counts[item.source_type] = source_counts.get(item.source_type, 0) + 1

        return TodaySummary(
            total_items=len(items),
            urgent_count=urgent_count,
            important_count=important_count,
            normal_count=normal_count,
            source_breakdown=source_counts,
        )

    async def _generate_greeting(self, user_id: UUID) -> str:
        """生成个性化问候语"""
        now = local_now()
        hour = now.hour

        if hour < 6:
            time_greeting = "夜深了"
        elif hour < 9:
            time_greeting = "早上好"
        elif hour < 12:
            time_greeting = "上午好"
        elif hour < 14:
            time_greeting = "中午好"
        elif hour < 18:
            time_greeting = "下午好"
        elif hour < 22:
            time_greeting = "晚上好"
        else:
            time_greeting = "夜深了"

        # 返回简单问候语
        return f"{time_greeting}！"

    async def complete_item(
        self,
        item_id: UUID,
        user_id: UUID,
    ) -> Optional[TodayItem]:
        """完成待办项"""
        item = await self.today_repo.get_item(item_id)
        if not item:
            return None

        # 完成原始任务（如果有）
        await self._complete_source_item(item)

        # 更新待办项状态
        return await self.today_repo.complete_item(item_id)

    async def _complete_source_item(self, item: TodayItem) -> None:
        """完成原始来源项"""
        if item.source_type == "family_task":
            from ...views.repositories import FamilyTaskRepository
            task_repo = FamilyTaskRepository(self.db)
            await task_repo.complete_task(item.source_id)
        elif item.source_type == "preparation_task":
            await self.preparation_repo.complete_task(item.source_id)
        elif item.source_type == "shopping_item":
            pass  # Shopping module removed

    async def snooze_item(
        self,
        item_id: UUID,
        hours: int = 24,
    ) -> Optional[TodayItem]:
        """延后待办项"""
        new_due = utc_now() + timedelta(hours=hours)
        return await self.today_repo.snooze_item(item_id, new_due)

    async def dismiss_item(self, item_id: UUID) -> bool:
        """忽略待办项"""
        return await self.today_repo.dismiss_item(item_id)

    async def create_ai_suggestion(
        self,
        family_id: UUID,
        suggestion_type: str,
        content: str,
        user_id: Optional[UUID] = None,
        actions: Optional[List[dict]] = None,
        context: Optional[dict] = None,
        priority: int = 0,
        valid_hours: int = 24,
    ) -> AISuggestion:
        """创建AI建议"""
        valid_until = utc_now() + timedelta(hours=valid_hours)
        return await self.today_repo.create_suggestion(
            family_id=family_id,
            suggestion_type=suggestion_type,
            content=content,
            user_id=user_id,
            actions=actions,
            context=context,
            priority=priority,
            valid_until=valid_until,
        )

    async def dismiss_suggestion(self, suggestion_id: UUID) -> bool:
        """忽略AI建议"""
        return await self.today_repo.dismiss_suggestion(suggestion_id)

    async def act_on_suggestion(self, suggestion_id: UUID) -> bool:
        """执行AI建议"""
        return await self.today_repo.mark_suggestion_acted(suggestion_id)
