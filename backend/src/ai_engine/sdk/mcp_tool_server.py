"""
MCP Tool Server - Wraps ToolBridge executors as an in-process MCP server.

Uses the Claude Agent SDK's @tool decorator and create_sdk_mcp_server()
to expose all registered tools to the SDK's query()/ClaudeSDKClient.

Architecture:
    Claude Agent SDK (ClaudeSDKClient)
        ↓ MCP tool call (mcp__secretary__<tool_name>)
    MCP Server handler (this file)
        ↓ calls executor via persistence handler
    ToolBridge.execute_tool() → Domain Executors
        ↓ result
    ToolPersistenceHandler.execute_with_persistence()
        ↓ 3-layer DB persist
    Return MCP-format result
"""

import logging
from typing import Any, Dict, List

try:
    from claude_agent_sdk import tool as sdk_tool, create_sdk_mcp_server
    from claude_agent_sdk.types import McpSdkServerConfig
except ImportError as _import_err:
    raise ImportError(
        "claude-agent-sdk is required for MCPToolServer. "
        "Install it with: pip install claude-agent-sdk>=0.1.0"
    ) from _import_err

from ..tools.registry import ToolExecutionContext
from ..tools.tool_bridge import ToolBridge
from .pooled_context import PooledToolContext
from .tool_persistence import ToolPersistenceHandler

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "secretary"
MCP_SERVER_VERSION = "1.0.0"


def _build_input_schema(tool_def: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Anthropic tool input_schema to SDK-compatible format.

    The Claude Agent SDK @tool decorator accepts either a simple type
    mapping or a full JSON Schema dict.  We pass through the Anthropic
    input_schema (which is already JSON Schema) directly.

    Falls back to a permissive schema if the definition is missing or malformed.
    """
    schema = tool_def.get("input_schema")
    if not isinstance(schema, dict) or "type" not in schema:
        return {"type": "object", "properties": {}}
    return schema


def _make_tool_handler(
    tool_name: str,
    tool_bridge: ToolBridge,
    persistence: ToolPersistenceHandler,
):
    """Create an async handler for a single tool.

    The handler calls the ToolBridge executor via ToolPersistenceHandler
    so that every execution is persisted with 3-layer context.
    """
    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        import time as _time

        context = ToolExecutionContext(
            family_id=persistence.family_id,
            user_id=persistence.user_id,
            session_id=persistence.session_id,
        )

        t0 = _time.monotonic()
        logger.info("MCP tool start: %s (session=%s)", tool_name, persistence.session_id)

        result = await persistence.execute_with_persistence(
            tool_name=tool_name,
            arguments=args,
            executor=tool_bridge.execute_tool,
            context=context,
        )

        elapsed_ms = (_time.monotonic() - t0) * 1000
        is_error = result.get("is_error", False)
        content_text = result.get("content", "")
        log_fn = logger.warning if elapsed_ms > 5000 else logger.info
        log_fn(
            "MCP tool done: %s (elapsed_ms=%.0f, is_error=%s, "
            "result_len=%d, session=%s)",
            tool_name, elapsed_ms, is_error,
            len(content_text), persistence.session_id,
        )

        response: Dict[str, Any] = {
            "content": [{"type": "text", "text": content_text}],
        }
        if is_error:
            response["is_error"] = True

        return response

    return handler


def create_secretary_mcp_server(
    tool_bridge: ToolBridge,
    persistence: ToolPersistenceHandler,
) -> Any:
    """Create an in-process MCP server wrapping all ToolBridge tools.

    Args:
        tool_bridge: Initialized ToolBridge with all domain executors
        persistence: ToolPersistenceHandler for 3-layer DB persistence

    Returns:
        McpSdkServerConfig suitable for ClaudeAgentOptions.mcp_servers
    """
    tool_definitions = tool_bridge.get_tool_definitions()
    sdk_tools = []

    for tool_def in tool_definitions:
        name = tool_def["name"]
        description = tool_def.get("description", f"Tool: {name}")
        input_schema = _build_input_schema(tool_def)
        handler = _make_tool_handler(name, tool_bridge, persistence)

        decorated = sdk_tool(name, description, input_schema)(handler)
        sdk_tools.append(decorated)

    logger.info(
        "Created MCP server '%s' with %d tools",
        MCP_SERVER_NAME, len(sdk_tools),
    )

    return create_sdk_mcp_server(
        name=MCP_SERVER_NAME,
        version=MCP_SERVER_VERSION,
        tools=sdk_tools,
    )


def create_pooled_mcp_server(ctx: PooledToolContext) -> Any:
    """Create a dynamic MCP server whose tool list tracks PooledToolContext.

    Unlike the static ``create_secretary_mcp_server``, this version:

    - **``list_tools``** reads from ``ctx.tool_map`` at call time, so tool
      renames / additions are picked up after ``ctx.refresh_tool_map()``.
    - **``call_tool``** resolves the tool name from ``ctx.tool_map`` and
      dispatches through ``ctx.bridge.execute_tool()`` / ``ctx.persistence``.
    - **Session capture**: the first ``list_tools`` call captures the
      ``ServerSession`` into ``ctx._mcp_session`` so that the REUSE path
      can later send ``tools/list_changed`` notifications to the CLI.

    On first pool request the tool_map is populated from the bridge.
    On subsequent requests ``ctx.update(...)`` swaps bridge/persistence,
    and if tool names changed the caller sends ``tools/list_changed``
    which triggers the CLI to re-call ``list_tools``.

    Args:
        ctx: Mutable execution context (must have ``bridge`` set)

    Returns:
        McpSdkServerConfig suitable for ClaudeAgentOptions.mcp_servers
    """
    from mcp.server import Server
    from mcp.types import CallToolResult, Tool, TextContent

    # Populate initial tool_map from bridge
    ctx.refresh_tool_map()

    server = Server(MCP_SERVER_NAME, version=MCP_SERVER_VERSION)

    # ---- list_tools: dynamic, reads ctx.tool_map ----
    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def _list_tools() -> list:
        # Capture session for later notifications (only once)
        if ctx._mcp_session is None:
            try:
                ctx._mcp_session = server.request_context.session
            except LookupError:
                pass

        tool_list = []
        for name, tool_def in ctx.tool_map.items():
            schema = _build_input_schema(tool_def)
            tool_list.append(Tool(
                name=name,
                description=tool_def.get("description", f"Tool: {name}"),
                inputSchema=schema,
            ))
        return tool_list

    # ---- call_tool: dynamic, resolves from ctx.tool_map + ctx.bridge ----
    @server.call_tool()  # type: ignore[untyped-decorator]
    async def _call_tool(name: str, arguments: dict) -> Any:
        import time as _time

        if name not in ctx.tool_map:
            raise ValueError(f"Tool '{name}' not found")

        context = ToolExecutionContext(
            family_id=ctx.persistence.family_id,
            user_id=ctx.persistence.user_id,
            session_id=ctx.persistence.session_id,
        )

        t0 = _time.monotonic()
        logger.info(
            "MCP pooled tool start: %s (session=%s)",
            name, ctx.persistence.session_id,
        )

        result = await ctx.persistence.execute_with_persistence(
            tool_name=name,
            arguments=arguments,
            executor=ctx.bridge.execute_tool,
            context=context,
        )

        elapsed_ms = (_time.monotonic() - t0) * 1000
        content_text = result.get("content", "")
        is_error = result.get("is_error", False)
        log_fn = logger.warning if elapsed_ms > 5000 else logger.info
        log_fn(
            "MCP pooled tool done: %s (elapsed_ms=%.0f, is_error=%s, "
            "result_len=%d, session=%s)",
            name, elapsed_ms, is_error,
            len(content_text), ctx.persistence.session_id,
        )

        content = [TextContent(type="text", text=content_text)] if content_text else []
        if is_error:
            return CallToolResult(content=content, isError=True)
        return content

    logger.info(
        "Created dynamic pooled MCP server '%s' with %d tools",
        MCP_SERVER_NAME, len(ctx.tool_map),
    )

    return McpSdkServerConfig(type="sdk", name=MCP_SERVER_NAME, instance=server)


def get_allowed_tool_names(
    tool_bridge: ToolBridge,
    server_key: str = "secretary",
) -> List[str]:
    """Get the SDK allowed_tools list for all registered tools.

    SDK MCP tools are named: mcp__<server_key>__<tool_name>
    """
    tool_definitions = tool_bridge.get_tool_definitions()
    return [
        f"mcp__{server_key}__{t['name']}"
        for t in tool_definitions
    ]


def get_allowed_tool_names_for_subset(
    tool_names: List[str],
    server_key: str = "secretary",
) -> List[str]:
    """Get SDK allowed_tools for a subset of tool names."""
    return [f"mcp__{server_key}__{name}" for name in tool_names]
