"""
Task management tools for Claude Agent.

Provides tools for creating, updating, and managing tasks and reminders.
"""

from .registry import ToolCategory, ToolRegistry
from .shared.wrap import wrap_method as _wrap_method
from .executors.task_executor import TaskToolExecutor
from .executors.reminder_executor import ReminderToolExecutor


def register_task_tools(
    registry: ToolRegistry,
    executor: TaskToolExecutor,
    reminder_executor: ReminderToolExecutor,
) -> None:
    """Register task management tools with the registry."""

    # Create task
    registry.register(
        name="create_task",
        description="创建待办任务。可以设置截止日期、优先级和提醒。",
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "任务标题"
                },
                "description": {
                    "type": "string",
                    "description": "任务描述"
                },
                "due_date": {
                    "type": "string",
                    "description": "截止日期，格式: YYYY-MM-DD"
                },
                "due_time": {
                    "type": "string",
                    "description": "截止时间，格式: HH:MM"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                    "description": "优先级",
                    "default": "normal"
                },
                "category": {
                    "type": "string",
                    "description": "任务分类"
                },
                "reminder": {
                    "type": "boolean",
                    "description": "是否设置提醒",
                    "default": True
                },
                "reminder_before_minutes": {
                    "type": "integer",
                    "description": "提前多少分钟提醒",
                    "default": 30
                }
            },
            "required": ["title"]
        },
        executor=_wrap_method(executor.create_task),
        category=ToolCategory.TASKS,
        is_stateful=True,
    )

    # Query tasks
    registry.register(
        name="query_tasks",
        description="查询待办任务列表。",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "completed", "overdue", "all"],
                    "description": "筛选状态",
                    "default": "pending"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent", "all"],
                    "description": "筛选优先级"
                },
                "category": {
                    "type": "string",
                    "description": "筛选分类"
                },
                "due_within_days": {
                    "type": "integer",
                    "description": "筛选未来N天内到期的任务"
                }
            }
        },
        executor=_wrap_method(executor.query_tasks),
        category=ToolCategory.TASKS,
    )

    # Complete task
    registry.register(
        name="complete_task",
        description="标记任务为已完成。可通过 task_id 精确匹配，或通过 task_title 模糊匹配。",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "任务ID（UUID），优先使用"
                },
                "task_title": {
                    "type": "string",
                    "description": "任务标题，当没有 task_id 时按标题模糊匹配"
                },
                "notes": {
                    "type": "string",
                    "description": "完成备注"
                }
            },
        },
        executor=_wrap_method(executor.complete_task),
        category=ToolCategory.TASKS,
        is_stateful=True,
    )

    # Update task
    registry.register(
        name="update_task",
        description="更新任务信息。可通过 task_id 精确匹配，或通过 task_title 模糊匹配。",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "任务ID（UUID），优先使用"
                },
                "task_title": {
                    "type": "string",
                    "description": "任务标题，当没有 task_id 时按标题模糊匹配"
                },
                "updates": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "due_date": {"type": "string"},
                        "due_time": {"type": "string"},
                        "priority": {"type": "string"},
                        "category": {"type": "string"}
                    }
                }
            },
            "required": ["updates"]
        },
        executor=_wrap_method(executor.update_task),
        category=ToolCategory.TASKS,
        is_stateful=True,
    )

    # Delete task
    registry.register(
        name="delete_task",
        description="删除任务。可通过 task_id 精确删除，或通过 task_title 模糊匹配删除。",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "任务ID（UUID），优先使用"
                },
                "task_title": {
                    "type": "string",
                    "description": "任务标题，当没有 task_id 时按标题模糊匹配"
                }
            },
        },
        executor=_wrap_method(executor.delete_task),
        category=ToolCategory.TASKS,
        is_stateful=True,
    )

    # Set reminder (implemented in reminder_executor)
    registry.register(
        name="set_reminder",
        description="设置提醒。可以是一次性提醒或重复提醒。",
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "提醒标题"
                },
                "remind_at": {
                    "type": "string",
                    "description": "提醒时间，格式: YYYY-MM-DD HH:MM"
                },
                "message": {
                    "type": "string",
                    "description": "提醒内容"
                },
                "repeat": {
                    "type": "string",
                    "enum": ["none", "daily", "weekly", "monthly"],
                    "description": "重复频率",
                    "default": "none"
                }
            },
            "required": ["title", "remind_at"]
        },
        executor=_wrap_method(reminder_executor.set_reminder),
        category=ToolCategory.TASKS,
        is_stateful=True,
    )
