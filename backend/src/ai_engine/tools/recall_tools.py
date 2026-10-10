"""
Recall Tools - Register tool execution recall and detail viewing tools.

These tools allow the agent to:
1. View details of a specific tool execution (view_tool_details)
2. Search historical tool executions across sessions (recall_tool_result)
"""

from ..tools.registry import ToolCategory, ToolRegistry
from ..tools.shared.wrap import wrap_method
from .executors.recall_executor import RecallToolExecutor


def register_recall_tools(
    registry: ToolRegistry,
    executor: RecallToolExecutor,
) -> None:
    """Register tool execution recall tools."""

    registry.register(
        name="view_tool_details",
        description=(
            "查看某次工具执行的详细结果。"
            "当你需要回顾之前执行过的工具的具体返回内容时使用。"
            "execution_id 可以从上下文中的工具调用记录 [#xxx] 获取完整 UUID。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "execution_id": {
                    "type": "string",
                    "description": (
                        "工具执行记录的完整 UUID "
                        "(从上下文中 [#a1b2c3d4] 对应的完整 UUID 获取)"
                    ),
                },
                "detail_level": {
                    "type": "string",
                    "enum": ["key_results", "full"],
                    "description": "key_results=关键结果 (推荐), full=完整原始返回",
                    "default": "key_results",
                },
            },
            "required": ["execution_id"],
        },
        executor=wrap_method(executor.view_tool_details),
        category=ToolCategory.CORE,
        always_available=True,
    )

    registry.register(
        name="recall_tool_result",
        description=(
            "搜索之前会话中的工具执行结果。"
            "当用户提到之前查过或做过的事情，"
            "或需要参考历史操作结果时使用。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，匹配工具参数和摘要",
                },
                "tool_name": {
                    "type": "string",
                    "description": "过滤特定工具名 (可选，如 web_search, query_trips, add_trip_itinerary)",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量 (默认5，最大20)",
                    "default": 5,
                },
            },
            "required": ["keyword"],
        },
        executor=wrap_method(executor.recall_tool_result),
        category=ToolCategory.CORE,
        always_available=True,
    )
