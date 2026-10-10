"""
Event management tools for Claude Agent.

Provides tools for creating, updating, and deleting general-purpose events
(meetings, appointments, reminders, etc.) via the CuratedEvent table.
"""

from .registry import ToolCategory, ToolRegistry
from .shared.wrap import wrap_method as _wrap_method
from .executors.event_executor import EventToolExecutor


def register_event_tools(
    registry: ToolRegistry,
    executor: EventToolExecutor,
) -> None:
    """Register event management tools with the registry."""

    # Create event
    registry.register(
        name="create_event",
        description=(
            "创建通用日程事件，如会议、约会、提醒等。"
            "当用户说'帮我安排明天下午3点开会'、'约了周六看牙医'时使用此工具。"
            "⚠️ 必须包含明确的时间信息。如用户未提供具体时间，先询问再调用。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "事件标题，如'团队周会'、'看牙医'"
                },
                "start_time": {
                    "type": "string",
                    "description": "开始时间，ISO 8601 格式: YYYY-MM-DDTHH:MM:SS"
                },
                "end_time": {
                    "type": "string",
                    "description": "结束时间 (可选)，ISO 8601 格式"
                },
                "event_type": {
                    "type": "string",
                    "enum": [
                        "meeting", "appointment", "reminder",
                        "birthday", "anniversary", "holiday", "other"
                    ],
                    "description": "事件类型",
                    "default": "other"
                },
                "location": {
                    "type": "string",
                    "description": "地点 (可选)"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "critical"],
                    "description": "优先级",
                    "default": "normal"
                },
                "notes": {
                    "type": "string",
                    "description": "备注信息 (可选)"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表 (可选)"
                }
            },
            "required": ["title", "start_time"]
        },
        executor=_wrap_method(executor.create_event),
        category=ToolCategory.CALENDAR,
        is_stateful=True,
    )

    # Update event
    registry.register(
        name="update_event",
        description=(
            "修改已有日程信息，如更改时间、地点、标题等。"
            "需要提供事件ID。仅可修改用户创建的或已确认的事件。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "要修改的事件ID"
                },
                "updates": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "新标题"},
                        "start_time": {"type": "string", "description": "新开始时间"},
                        "end_time": {"type": "string", "description": "新结束时间"},
                        "event_type": {"type": "string", "description": "新事件类型"},
                        "location": {"type": "string", "description": "新地点"},
                        "priority": {"type": "string", "description": "新优先级"},
                        "notes": {"type": "string", "description": "新备注"},
                        "status": {"type": "string", "description": "新状态"}
                    }
                }
            },
            "required": ["event_id", "updates"]
        },
        executor=_wrap_method(executor.update_event),
        category=ToolCategory.CALENDAR,
        is_stateful=True,
    )

    # Cancel schedule (single event)
    registry.register(
        name="cancel_schedule",
        description=(
            "取消单个日程/事件。当用户说'取消XX日程'、'删除XX安排'、'不去XX了'时使用。"
            "会将事件标记为已取消而非物理删除。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "event_title": {
                    "type": "string",
                    "description": "事件标题或关键词，用于模糊匹配要取消的事件"
                },
                "event_date": {
                    "type": "string",
                    "description": "事件日期(YYYY-MM-DD)，可选。用于更精确匹配同名事件"
                },
                "reason": {
                    "type": "string",
                    "description": "取消原因（可选），如'时间冲突'、'计划变更'"
                }
            },
            "required": ["event_title"]
        },
        executor=_wrap_method(executor.cancel_schedule),
        category=ToolCategory.CALENDAR,
        is_stateful=True,
    )

    # Delete event
    registry.register(
        name="delete_event",
        description=(
            "删除日程事件（软删除，标记为已取消）。"
            "当用户说'取消明天的会议'时使用此工具。需要提供事件ID。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "要删除的事件ID"
                }
            },
            "required": ["event_id"]
        },
        executor=_wrap_method(executor.delete_event),
        category=ToolCategory.CALENDAR,
        is_stateful=True,
    )

    # Search events
    registry.register(
        name="search_events",
        description="搜索日程事件。支持关键词搜索、按类型和日期范围筛选。",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词（匹配标题、地点、备注）",
                },
                "event_type": {
                    "type": "string",
                    "enum": [
                        "meeting", "appointment", "reminder",
                        "birthday", "anniversary", "holiday", "other",
                    ],
                    "description": "按事件类型筛选（可选）",
                },
                "start_date": {
                    "type": "string",
                    "description": "起始日期筛选，ISO 格式 YYYY-MM-DD（可选）",
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期筛选，ISO 格式 YYYY-MM-DD（可选）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制，默认10，最大50",
                    "default": 10,
                },
            },
        },
        executor=_wrap_method(executor.search_events),
        category=ToolCategory.CALENDAR,
    )

    # Analyze event cascade
    registry.register(
        name="analyze_event_cascade",
        description=(
            "分析事件变更的级联影响。当用户说'航班延误2小时'、'会议取消了'、"
            "'地点改了'时使用此工具，分析对当天其他事件的影响。"
            "返回受影响的事件列表和建议操作。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "发生变更的事件ID",
                },
                "change_type": {
                    "type": "string",
                    "enum": ["delayed", "cancelled", "time_changed", "location_changed"],
                    "description": "变更类型: delayed(延误), cancelled(取消), time_changed(时间变更), location_changed(地点变更)",
                },
                "change_detail": {
                    "type": "object",
                    "properties": {
                        "delay_minutes": {
                            "type": "integer",
                            "description": "延误分钟数 (仅 delayed 类型需要)",
                        },
                        "new_location": {
                            "type": "string",
                            "description": "新地点 (仅 location_changed 类型)",
                        },
                        "new_start_time": {
                            "type": "string",
                            "description": "新开始时间 (仅 time_changed 类型)",
                        },
                    },
                    "description": "变更详情",
                },
            },
            "required": ["event_id", "change_type"],
        },
        executor=_wrap_method(executor.analyze_event_cascade),
        category=ToolCategory.CALENDAR,
        is_stateful=False,
    )
