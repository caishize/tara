"""
Trip planning tools for Claude Agent.

Provides tools for trip planning, itinerary management, and trip info.
"""

from .registry import ToolCategory, ToolRegistry
from .shared.wrap import wrap_method as _wrap_method
from .executors.trip_executor import TripToolExecutor


def register_trip_tools(
    registry: ToolRegistry,
    executor: TripToolExecutor,
) -> None:
    """Register trip planning tools with the registry."""

    # NOTE: plan_smart_trip has been replaced by the travel_planning Skill.
    # The main agent now uses web_search + add_trip_itinerary/update_trip
    # directly, guided by Skill prompt injection.

    # Create trip (spec name: create_trip)
    registry.register(
        name="create_trip",
        description=(
            "创建一个全新的、独立的旅行计划。\n"
            "⚠️ 使用前必须先调用 query_trips 确认没有时间重叠的已有行程！\n"
            "⚠️ 以下场景禁止使用 create_trip，必须用 add_trip_itinerary：\n"
            "  - 用户提到的活动属于已有行程的途经点/顺路活动/子行程"
            "（如：回程路上顺便去某地、行程某天加一个景点）\n"
            "  - 活动日期在已有行程的日期范围内\n"
            "  - 活动是已有行程的出发/返程/住宿安排\n"
            "如果用户提供了包含多个时间段的详细行程，请使用 add_trip_itinerary 工具。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "事件标题"
                },
                "location": {
                    "type": "string",
                    "description": "目的地/地点（必须提供）"
                },
                "event_date": {
                    "type": "string",
                    "description": "事件日期，格式: YYYY-MM-DD"
                },
                "start_time": {
                    "type": "string",
                    "description": "开始时间，格式: HH:MM"
                },
                "end_time": {
                    "type": "string",
                    "description": "结束时间，格式: HH:MM"
                },
                "description": {
                    "type": "string",
                    "description": "详细描述"
                },
                "category": {
                    "type": "string",
                    "enum": ["transportation", "accommodation", "activity", "meal", "other"],
                    "description": "事件类型"
                }
            },
            "required": ["title", "location", "event_date"]
        },
        executor=_wrap_method(executor.add_trip_event),
        category=ToolCategory.TRAVEL,
        is_stateful=True,
    )

    # Add trip itinerary (supports single-day and batch multi-day)
    _activity_schema = {
        "type": "object",
        "properties": {
            "start_time": {"type": "string", "description": "开始时间 HH:MM"},
            "end_time": {"type": "string", "description": "结束时间 HH:MM"},
            "title": {"type": "string", "description": "活动标题"},
            "location": {"type": "string", "description": "地点"},
            "category": {"type": "string", "description": "类别"},
            "description": {"type": "string", "description": "描述"},
        },
        "required": ["start_time", "title"],
    }
    registry.register(
        name="add_trip_itinerary",
        description=(
            "向已有行程添加日程安排，或创建新行程并添加日程。支持两种模式：\n"
            "1. **批量模式（推荐）**: 传入 days 数组一次添加多天行程\n"
            "2. **单天模式**: 传入 activities 数组添加一天行程，day_number 自动递增\n\n"
            "**适用场景（必须传入已有行程的 trip_id）**：\n"
            "- 为已有行程添加途经点、顺路活动（如：回程路上顺便探亲）\n"
            "- 为已有行程补充出发/返程/住宿安排\n"
            "- 为已有行程某一天追加活动\n\n"
            "首次调用不传 trip_id 时会自动创建旅行计划，返回值包含 trip_id。\n"
            "**重要**: 后续调用必须传入首次返回的 trip_id，否则会重复创建旅行计划。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "string",
                    "description": "已有旅行计划的ID。首次调用可不传（自动创建），但后续调用必须传入首次返回的 trip_id",
                },
                "trip_name": {
                    "type": "string",
                    "description": "旅行计划名称（仅创建新计划时需要）",
                },
                "destination": {
                    "type": "string",
                    "description": "目的地（创建新计划时必须提供）",
                },
                "event_date": {
                    "type": "string",
                    "description": "起始日期，格式: YYYY-MM-DD",
                },
                "days": {
                    "type": "array",
                    "description": "批量模式：多天行程数组（推荐用此方式一次性添加所有天）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day_number": {
                                "type": "integer",
                                "description": "第几天（可选，不传则自动递增）",
                            },
                            "activities": {
                                "type": "array",
                                "items": _activity_schema,
                            },
                        },
                        "required": ["activities"],
                    },
                },
                "activities": {
                    "type": "array",
                    "description": "单天模式：一天的活动列表",
                    "items": _activity_schema,
                },
                "day_number": {
                    "type": "integer",
                    "description": "第几天（单天模式，可选，不传则自动递增）",
                },
            },
            "required": ["trip_name", "destination", "event_date"],
        },
        executor=_wrap_method(executor.add_trip_itinerary),
        category=ToolCategory.TRAVEL,
        is_stateful=True,
    )

    # Query trips
    registry.register(
        name="query_trips",
        description="查询旅行计划列表。",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["upcoming", "ongoing", "completed", "all"],
                    "description": "筛选状态",
                    "default": "all"
                },
                "destination": {
                    "type": "string",
                    "description": "按目的地筛选"
                },
                "include_history": {
                    "type": "boolean",
                    "description": "是否包含历史/被 superseded 的行程。默认 false（仅返回当前 canonical 且 active 的行程）。",
                    "default": False,
                },
                "start_date": {
                    "type": "string",
                    "description": "筛选在此之后（含）开始的行程或包含此日期的行程，格式: YYYY-MM-DD",
                },
                "end_date": {
                    "type": "string",
                    "description": "筛选在此之前（含）结束的行程或包含此日期的行程，格式: YYYY-MM-DD",
                },
                "query_scene": {
                    "type": "string",
                    "enum": [
                        "default",
                        "current_plan",
                        "past_executed",
                        "past_planned",
                        "referenced_plan",
                    ],
                    "description": "语义场景过滤：当前行程、已执行结果、历史规划方案等。",
                }
            }
        },
        executor=_wrap_method(executor.query_trips),
        category=ToolCategory.TRAVEL,
    )

    # Update trip (spec name: update_trip)
    registry.register(
        name="merge_trips",
        description="合并重复行程：将多个次级行程标记为主行程的 superseded 历史版本。",
        parameters={
            "type": "object",
            "properties": {
                "primary_trip_id": {
                    "type": "string",
                    "description": "主行程ID（合并后的 canonical）",
                },
                "merge_trip_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "待合并到主行程的次级行程ID列表",
                },
                "reason": {
                    "type": "string",
                    "description": "合并原因（如：语义重复、用户确认合并）",
                },
            },
            "required": ["primary_trip_id", "merge_trip_ids"],
        },
        executor=_wrap_method(executor.merge_trips),
        category=ToolCategory.TRAVEL,
        is_stateful=True,
    )

    registry.register(
        name="update_trip",
        description="更新已有旅行计划的备注或状态。创建行程请使用 add_trip_itinerary。",
        parameters={
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "string",
                    "description": "旅行ID（通过 query_trips 获取）",
                },
                "notes": {
                    "type": "string",
                    "description": "备注信息",
                },
                "status": {
                    "type": "string",
                    "enum": ["planning", "confirmed", "completed"],
                    "description": "更新行程状态",
                },
            },
            "required": ["trip_id"],
        },
        executor=_wrap_method(executor.save_trip_plan),
        category=ToolCategory.TRAVEL,
        is_stateful=True,
    )

    # Cancel trip
    registry.register(
        name="cancel_trip",
        description="取消旅行计划。优先使用 trip_id 精确取消；如无 ID，可用 trip_name 模糊匹配。建议先通过 query_trips 获取行程列表和 ID。",
        parameters={
            "type": "object",
            "properties": {
                "trip_id": {
                    "type": "string",
                    "description": "行程ID（优先使用，可通过 query_trips 获取）"
                },
                "trip_name": {
                    "type": "string",
                    "description": "行程名称（模糊匹配，当无 trip_id 时使用）"
                },
                "reason": {
                    "type": "string",
                    "description": "取消原因"
                }
            },
        },
        executor=_wrap_method(executor.cancel_trip),
        category=ToolCategory.TRAVEL,
        is_stateful=True,
    )

    # NOTE: search_travel_info has been replaced by the travel_search Skill.
    # The main agent now uses WebSearch directly for destination info,
    # guided by Skill prompt injection.

    # Query trip bookings (from connected email)
    registry.register(
        name="query_trip_bookings",
        description="查询已连接邮箱中解析出的机票、酒店等行程预订信息。当用户询问即将到来的旅行、航班、酒店预订时使用。",
        parameters={
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "开始日期，格式: YYYY-MM-DD，默认今天"
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期，格式: YYYY-MM-DD，默认三个月后"
                },
                "booking_type": {
                    "type": "string",
                    "enum": ["flight", "hotel", "train", "all"],
                    "description": "预订类型",
                    "default": "all"
                }
            }
        },
        executor=_wrap_method(executor.query_trip_bookings),
        category=ToolCategory.TRAVEL,
        always_available=False,
        required_connectors=["email_gmail", "email_outlook"],
    )

    # Query external calendar
    registry.register(
        name="query_external_calendar",
        description="查询外部日历（Google Calendar / Outlook）中的日程。",
        parameters={
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "开始日期，格式: YYYY-MM-DD"
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期，格式: YYYY-MM-DD"
                },
                "calendar_id": {
                    "type": "string",
                    "description": "日历ID（可选）"
                }
            }
        },
        executor=_wrap_method(executor.query_external_calendar),
        category=ToolCategory.CALENDAR,
        always_available=False,
        required_connectors=["google_calendar", "outlook_calendar"],
    )
