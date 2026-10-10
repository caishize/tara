"""
Important date management tools for Claude Agent.

Provides tools for adding, updating, and querying important dates
like birthdays, anniversaries, and holidays.
"""

from .registry import ToolCategory, ToolRegistry
from .shared.wrap import wrap_method as _wrap_method
from .executors.date_executor import DateToolExecutor


def register_date_tools(
    registry: ToolRegistry,
    executor: DateToolExecutor,
) -> None:
    """Register date management tools with the registry."""

    # Add important date
    registry.register(
        name="add_important_date",
        description="添加重要日期，如生日、纪念日等。支持农历和公历。⚠️ 重要：只有当用户明确提供了具体日期时才能调用此工具！如果用户只是说'XX生日快到了'但没有说具体是哪天，绝对不要调用此工具，而是先询问具体日期。",
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "日期标题，如'爸爸生日'、'结婚纪念日'",
                },
                "date_type": {
                    "type": "string",
                    "enum": ["birthday", "anniversary", "holiday", "other"],
                    "description": "日期类型",
                },
                "month": {
                    "type": "integer",
                    "description": "月份 (1-12)。必须是用户明确提供的！",
                },
                "day": {
                    "type": "integer",
                    "description": "日期 (1-31)。必须是用户明确提供的！",
                },
                "is_lunar": {
                    "type": "boolean",
                    "description": "是否为农历日期",
                    "default": False,
                },
                "person": {
                    "type": "string",
                    "description": "关联的人物名称（可选）",
                },
                "reminder_days": {
                    "type": "integer",
                    "description": "提前几天提醒",
                    "default": 3,
                },
            },
            "required": ["title", "month", "day"],
        },
        executor=_wrap_method(executor.add_important_date),
        category=ToolCategory.DATES,
        is_stateful=True,
    )

    # Query upcoming dates
    registry.register(
        name="query_upcoming_dates",
        description="查询即将到来的重要日期。默认显示未来30天内的日期。",
        parameters={
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "查询未来多少天内的日期",
                    "default": 30,
                },
                "date_type": {
                    "type": "string",
                    "enum": ["birthday", "anniversary", "holiday", "other", "all"],
                    "description": "筛选日期类型",
                    "default": "all",
                },
                "person": {
                    "type": "string",
                    "description": "筛选特定人物的日期",
                },
            },
        },
        executor=_wrap_method(executor.query_upcoming_dates),
        category=ToolCategory.DATES,
    )

    # Update important date
    registry.register(
        name="update_important_date",
        description="更新重要日期信息。",
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "日期标题，用于查找",
                },
                "updates": {
                    "type": "object",
                    "properties": {
                        "new_title": {"type": "string"},
                        "month": {"type": "integer"},
                        "day": {"type": "integer"},
                        "is_lunar": {"type": "boolean"},
                        "reminder_days": {"type": "integer"},
                    },
                },
            },
            "required": ["title", "updates"],
        },
        executor=_wrap_method(executor.update_important_date),
        category=ToolCategory.DATES,
        is_stateful=True,
    )

    # Delete important date
    registry.register(
        name="delete_important_date",
        description="删除重要日期。",
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "要删除的日期标题",
                },
            },
            "required": ["title"],
        },
        executor=_wrap_method(executor.delete_important_date),
        category=ToolCategory.DATES,
        is_stateful=True,
    )

    # Lunar ↔ Solar calendar conversion
    registry.register(
        name="convert_lunar_date",
        description=(
            "农历↔公历日期转换工具。⚠️ 重要：当用户提到农历日期（如'初二'、'腊月廿三'、'正月十五'）时，"
            "必须使用此工具进行精确转换，不要自己推算！LLM 无法准确计算农历日期。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["lunar_to_solar", "solar_to_lunar"],
                    "description": "转换方向: lunar_to_solar=农历转公历, solar_to_lunar=公历转农历",
                },
                "year": {
                    "type": "integer",
                    "description": "年份，如 2026",
                },
                "month": {
                    "type": "integer",
                    "description": "月份 (1-12)。农历转公历时为农历月，公历转农历时为公历月",
                },
                "day": {
                    "type": "integer",
                    "description": "日 (1-31)。农历转公历时为农历日，公历转农历时为公历日",
                },
                "is_leap": {
                    "type": "boolean",
                    "description": "是否闰月（仅农历转公历时需要）",
                    "default": False,
                },
            },
            "required": ["direction", "year", "month", "day"],
        },
        executor=_wrap_method(executor.convert_lunar_date),
        category=ToolCategory.DATES,
    )
