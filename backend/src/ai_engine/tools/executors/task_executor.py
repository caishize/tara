"""Task domain tool executor — 5 tools for task management."""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union
from uuid import UUID

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now
from ..shared.errors import ToolErrorType, tool_error
from ..shared.progress import ProgressCallback
from .base import BaseToolExecutor

logger = get_logger(__name__)


class TaskToolExecutor(BaseToolExecutor):
    """Handles create/query/update/delete/complete for tasks."""

    async def _resolve_task(
        self,
        args: Dict[str, Any],
        family_id: UUID,
    ) -> Union[Any, Dict[str, Any]]:
        """Resolve a task from args containing task_id or task_title.

        Returns the task object on success, or an error dict on failure.
        """
        from ....modules.views.repositories import FamilyTaskRepository

        repo = FamilyTaskRepository(self.db)

        task_id_str = args.get("task_id")
        task_title = args.get("task_title")

        if task_id_str:
            try:
                task_id = UUID(task_id_str)
            except ValueError:
                return tool_error(ToolErrorType.VALIDATION, f"无效的任务ID: {task_id_str}")
            task = await repo.get_task(task_id)
            if not task or task.family_id != family_id:
                return tool_error(ToolErrorType.NOT_FOUND, "任务未找到")
            return task

        if task_title:
            matches = await repo.search_tasks(family_id, task_title, limit=5)
            exact = [t for t in matches if t.title == task_title]
            if exact:
                return exact[0]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                titles = [f"- {t.title} (id: {t.id})" for t in matches]
                return tool_error(
                    ToolErrorType.VALIDATION,
                    f"找到多个匹配任务，请指定 task_id:\n" + "\n".join(titles),
                )
            return tool_error(ToolErrorType.NOT_FOUND, "任务未找到")

        return tool_error(ToolErrorType.VALIDATION, "缺少参数: 需要 task_id 或 task_title")

    async def create_task(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.views.repositories import FamilyTaskRepository

        repo = FamilyTaskRepository(self.db)

        due_date_str = args.get("due_date")
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        priority_map = {"high": "high", "medium": "normal", "low": "low"}
        priority = priority_map.get(args.get("priority", "medium"), "normal")

        task = await repo.create_task(
            family_id=family_id,
            title=args.get("title"),
            description=args.get("description"),
            creator_id=user_id,
            due_date=due_date,
            priority=priority,
        )

        await self.db.commit()

        return {
            "success": True,
            "task_id": str(task.id),
            "title": args.get("title"),
        }

    async def query_tasks(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.views.repositories import FamilyTaskRepository

        repo = FamilyTaskRepository(self.db)

        status = args.get("status", "pending")
        if status == "all":
            status = None

        priority = args.get("priority")
        if priority == "all":
            priority = None

        due_within_days = args.get("due_within_days")

        if due_within_days is not None:
            tasks = await repo.get_upcoming_tasks(family_id, days=due_within_days)
        elif status == "overdue":
            tasks = await repo.get_overdue_tasks(family_id)
        elif status == "pending":
            tasks = await repo.get_pending_tasks(family_id, limit=20)
        else:
            tasks = await repo.get_family_tasks(
                family_id=family_id,
                status=status,
                limit=20,
            )

        filtered_tasks = []
        for task in tasks:
            if priority and task.priority != priority:
                continue
            filtered_tasks.append(task)

        return {
            "success": True,
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "status": t.status,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                    "priority": t.priority,
                    "description": t.description,
                    "is_overdue": t.is_overdue,
                }
                for t in filtered_tasks
            ],
            "count": len(filtered_tasks),
        }

    async def update_task(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        result = await self._resolve_task(args, family_id)
        if isinstance(result, dict):
            return result
        task = result

        updates = args.get("updates", {})

        if "title" in updates:
            task.title = updates["title"]
        if "description" in updates:
            task.description = updates["description"]
        if "priority" in updates:
            task.priority = updates["priority"]
        if "due_date" in updates:
            try:
                task.due_date = datetime.strptime(updates["due_date"], "%Y-%m-%d").date()
            except ValueError:
                pass

        await self.db.commit()

        return {
            "success": True,
            "task_id": str(task.id),
            "title": task.title,
            "message": f"已更新任务: {task.title}",
        }

    async def delete_task(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        result = await self._resolve_task(args, family_id)
        if isinstance(result, dict):
            return result
        task = result

        task.status = "cancelled"
        await self.db.commit()

        return {
            "success": True,
            "task_id": str(task.id),
            "message": f"已取消任务: {task.title}",
        }

    async def complete_task(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        result = await self._resolve_task(args, family_id)
        if isinstance(result, dict):
            return result
        task = result

        task.status = "completed"
        task.completed_at = utc_now()
        await self.db.commit()

        return {
            "success": True,
            "task_id": str(task.id),
            "message": f"已完成任务: {task.title}",
        }
