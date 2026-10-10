"""
MCP (Model Context Protocol) tools for Claude Agent.

Provides tools for calling external MCP servers and listing available MCP tools.
"""

from .registry import ToolCategory, ToolRegistry
from .shared.wrap import wrap_method as _wrap_method
from .executors.mcp_executor import McpToolExecutor


def register_mcp_tools(
    registry: ToolRegistry,
    executor: McpToolExecutor,
) -> None:
    """Register MCP tools with the registry."""

    # Call MCP tool
    registry.register(
        name="call_mcp_tool",
        description=(
            "调用已连接的 MCP 服务器提供的工具。MCP (Model Context Protocol) 是一种开放协议，"
            "允许连接外部工具服务器。当需要使用外部服务提供的特定功能时使用。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "connector_id": {
                    "type": "string",
                    "description": "MCP 连接器 ID，如 generic_mcp、filesystem_mcp、fetch_mcp"
                },
                "tool_name": {
                    "type": "string",
                    "description": "要调用的 MCP 工具名称"
                },
                "arguments": {
                    "type": "object",
                    "description": "工具参数（JSON 对象）"
                }
            },
            "required": ["connector_id", "tool_name"]
        },
        executor=_wrap_method(executor.call_mcp_tool),
        category=ToolCategory.CORE,
        always_available=False,
        required_connectors=["generic_mcp", "filesystem_mcp", "fetch_mcp"],
        is_stateful=True,
    )

    # List MCP tools
    registry.register(
        name="list_mcp_tools",
        description="列出已连接的 MCP 服务器提供的所有可用工具。当用户想知道有哪些外部工具可用时使用。",
        parameters={
            "type": "object",
            "properties": {
                "connector_id": {
                    "type": "string",
                    "description": "MCP 连接器 ID，不填则列出所有已连接 MCP 服务器的工具"
                }
            }
        },
        executor=_wrap_method(executor.list_mcp_tools),
        category=ToolCategory.CORE,
        always_available=False,
        required_connectors=["generic_mcp", "filesystem_mcp", "fetch_mcp"],
    )
