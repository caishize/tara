"""
Family Task Service - Collaborative family task management

Migrated from assistant/services/task_service.py.

Provides:
- Task creation with intelligent defaults
- Task assignment and collaboration
- Progress tracking
- Integration with other modules
"""

from datetime import date, timedelta, time
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ...core.utils.timezone import local_today
from .repositories import FamilyTaskRepository
from .models import FamilyTask


class FamilyTaskService:
    """家庭协作任务服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_repo = FamilyTaskRepository(db)

    async def create_task(
        self,
        family_id: UUID,
        title: str,
        creator_id: UUID,
        description: Optional[str] = None,
        task_type: Optional[str] = None,
        assignee_id: Optional[UUID] = None,
        due_date: Optional[date] = None,
        due_time: Optional[time] = None,
        priority: str = "normal",
        parent_task_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
    ) -> FamilyTask:
        """创建任务"""
        # 自动推断任务类型
        if not task_type:
            task_type = self._infer_task_type(title)

        # 如果没有指定截止日期，根据任务类型设置默认
        if not due_date:
            due_date = self._get_default_due_date(task_type)

        from datetime import datetime
        return await self.task_repo.create_task(
            family_id=family_id,
            title=title,
            creator_id=creator_id,
            description=description,
            task_type=task_type,
            assignee_id=assignee_id,
            parent_task_id=parent_task_id,
            due_date=due_date,
            due_time=datetime.combine(due_date, due_time) if due_date and due_time else None,
            priority=priority,
            metadata=metadata,
        )

    def _infer_task_type(self, title: str) -> str:
        """根据标题推断任务类型"""
        title_lower = title.lower()

        type_keywords = {
            "shopping": ["买", "购买", "采购", "购物"],
            "health": ["体检", "看医生", "吃药", "健康", "检查"],
            "household": ["打扫", "清洁", "修理", "整理", "洗", "扫"],
            "preparation": ["准备", "预定", "预订", "安排"],
            "routine": ["每天", "每周", "定期", "日常"],
            "finance": ["交费", "缴费", "还款", "转账"],
        }

        for task_type, keywords in type_keywords.items():
            if any(kw in title_lower for kw in keywords):
                return task_type

        return "general"

    def _get_default_due_date(self, task_type: str) -> Optional[date]:
        """根据任务类型获取默认截止日期"""
        today = local_today()

        defaults = {
            "routine": today + timedelta(days=1),
            "shopping": today + timedelta(days=3),
            "health": today + timedelta(days=7),
            "household": today + timedelta(days=7),
            "preparation": today + timedelta(days=14),
            "finance": today + timedelta(days=7),
        }

        return defaults.get(task_type)

    async def create_from_preparation_plan(
        self,
        family_id: UUID,
        creator_id: UUID,
        plan_id: UUID,
        plan_title: str,
        tasks_data: List[Dict[str, Any]],
    ) -> List[FamilyTask]:
        """从准备方案创建任务"""
        created_tasks = []

        for task_data in tasks_data:
            task = await self.create_task(
                family_id=family_id,
                title=task_data.get("title", ""),
                creator_id=creator_id,
                description=task_data.get("description"),
                task_type="preparation",
                due_date=task_data.get("due_date"),
                priority=task_data.get("priority", "normal"),
                metadata={
                    "source": {
                        "type": "preparation_plan",
                        "id": str(plan_id),
                        "title": plan_title,
                    }
                },
            )
            created_tasks.append(task)

        return created_tasks

    async def create_subtasks(
        self,
        parent_task_id: UUID,
        family_id: UUID,
        creator_id: UUID,
        subtasks: List[str],
    ) -> List[FamilyTask]:
        """批量创建子任务"""
        parent_task = await self.task_repo.get_task(parent_task_id)
        if not parent_task:
            raise ValueError("Parent task not found")

        created_subtasks = []
        for title in subtasks:
            subtask = await self.create_task(
                family_id=family_id,
                title=title,
                creator_id=creator_id,
                parent_task_id=parent_task_id,
                task_type=parent_task.task_type,
                due_date=parent_task.due_date,
                priority="normal",
            )
            created_subtasks.append(subtask)

        return created_subtasks

    async def get_task(self, task_id: UUID) -> Optional[FamilyTask]:
        """获取任务详情"""
        return await self.task_repo.get_task(task_id)

    async def get_family_tasks(
        self,
        family_id: UUID,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        assignee_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[FamilyTask]:
        """获取家庭任务列表"""
        return await self.task_repo.get_family_tasks(
            family_id=family_id,
            status=status,
            task_type=task_type,
            assignee_id=assignee_id,
            limit=limit,
            offset=offset,
        )

    async def get_my_tasks(
        self,
        user_id: UUID,
        family_id: UUID,
        include_created: bool = False,
    ) -> Dict[str, List[FamilyTask]]:
        """获取我的任务（分组返回）"""
        all_tasks = await self.task_repo.get_user_tasks(
            user_id=user_id,
            family_id=family_id,
            include_created=include_created,
        )

        # 分组
        result = {
            "overdue": [],
            "today": [],
            "upcoming": [],
            "no_due_date": [],
        }

        today = local_today()

        for task in all_tasks:
            if task.status in ["completed", "cancelled"]:
                continue

            if not task.due_date:
                result["no_due_date"].append(task)
            elif task.due_date < today:
                result["overdue"].append(task)
            elif task.due_date == today:
                result["today"].append(task)
            else:
                result["upcoming"].append(task)

        return result

    async def get_today_tasks(
        self,
        family_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> List[FamilyTask]:
        """获取今日任务"""
        return await self.task_repo.get_today_tasks(family_id, user_id)

    async def get_overdue_tasks(
        self,
        family_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> List[FamilyTask]:
        """获取逾期任务"""
        return await self.task_repo.get_overdue_tasks(family_id, user_id)

    async def assign_task(
        self,
        task_id: UUID,
        assignee_id: UUID,
    ) -> Optional[FamilyTask]:
        """分配任务"""
        return await self.task_repo.assign_task(task_id, assignee_id)

    async def start_task(self, task_id: UUID) -> Optional[FamilyTask]:
        """开始任务"""
        return await self.task_repo.start_task(task_id)

    async def complete_task(self, task_id: UUID) -> Optional[FamilyTask]:
        """完成任务"""
        task = await self.task_repo.complete_task(task_id)

        if task and task.parent_task_id:
            # 检查是否所有子任务都已完成
            parent = await self.task_repo.get_task(task.parent_task_id)
            if parent:
                subtasks = await self.task_repo.get_subtasks(parent.id)
                all_completed = all(st.status == "completed" for st in subtasks)
                if all_completed:
                    # 自动完成父任务
                    await self.task_repo.complete_task(parent.id)

        return task

    async def cancel_task(self, task_id: UUID) -> Optional[FamilyTask]:
        """取消任务"""
        return await self.task_repo.cancel_task(task_id)

    async def update_task(
        self,
        task_id: UUID,
        **kwargs,
    ) -> Optional[FamilyTask]:
        """更新任务"""
        return await self.task_repo.update_task(task_id, **kwargs)

    async def delete_task(self, task_id: UUID) -> bool:
        """删除任务"""
        return await self.task_repo.delete_task(task_id)

    async def get_statistics(
        self,
        family_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """获取任务统计"""
        stats = await self.task_repo.get_task_statistics(family_id, user_id)

        # 计算完成率
        total_actionable = stats["pending"] + stats["in_progress"] + stats["completed"]
        completion_rate = (stats["completed"] / total_actionable * 100) if total_actionable > 0 else 0

        stats["completion_rate"] = round(completion_rate, 1)
        return stats

    async def search_tasks(
        self,
        family_id: UUID,
        keyword: str,
        limit: int = 20,
    ) -> List[FamilyTask]:
        """搜索任务"""
        return await self.task_repo.search_tasks(family_id, keyword, limit)

    async def suggest_task_assignment(
        self,
        family_id: UUID,
        task_title: str,
    ) -> Optional[UUID]:
        """智能建议任务分配人"""
        # 基于历史任务分配模式推荐
        # 简化实现：返回None，由用户手动分配
        return None

    async def generate_routine_tasks(
        self,
        family_id: UUID,
        creator_id: UUID,
        routine_type: str,
    ) -> List[FamilyTask]:
        """生成例行任务"""
        routine_tasks = {
            "weekly_cleaning": [
                {"title": "打扫客厅", "weekday": 6},
                {"title": "打扫卧室", "weekday": 6},
                {"title": "清洁厨房", "weekday": 0},
                {"title": "清洁卫生间", "weekday": 0},
            ],
            "grocery_shopping": [
                {"title": "采购蔬菜水果", "weekday": 5},
                {"title": "补充日用品", "weekday": 5},
            ],
        }

        tasks_config = routine_tasks.get(routine_type, [])
        created_tasks = []

        today = local_today()
        for config in tasks_config:
            # 计算下一个该星期几的日期
            target_weekday = config["weekday"]
            days_ahead = target_weekday - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7

            due_date = today + timedelta(days=days_ahead)

            task = await self.create_task(
                family_id=family_id,
                title=config["title"],
                creator_id=creator_id,
                task_type="routine",
                due_date=due_date,
                metadata={
                    "routine_type": routine_type,
                    "recurring": True,
                },
            )
            created_tasks.append(task)

        return created_tasks

    async def get_tasks_by_source(
        self,
        family_id: UUID,
        source_type: str,
        source_id: UUID,
    ) -> List[FamilyTask]:
        """获取关联到特定来源的任务"""
        return await self.task_repo.get_tasks_by_source(family_id, source_type, source_id)
