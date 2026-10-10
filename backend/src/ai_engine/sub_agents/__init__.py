"""
Sub-Agent Registry - Specialized agents for complex domain tasks.

Sub-agents are invoked by the main agent via the "delegate_to_sub_agent" tool.
Each sub-agent has:
- Independent system prompt optimized for its domain
- Curated tool subset relevant to its task
- Higher max_turns (30 vs main agent's 20)
- Idle timeout (only triggers when no messages received)

SDK Integration:
- Sub-agents execute via independent ClaudeSDKClient sessions
- Tools are exposed via the same MCP server pattern
- execute_sub_agent_via_sdk() provides the new entry point
"""

import logging
from typing import Any, Dict, List, Optional

from .travel_planner import TRAVEL_PLANNER_CONFIG
from .deep_researcher import DEEP_RESEARCHER_CONFIG
from .gift_advisor import GIFT_ADVISOR_CONFIG
from ..sdk.idle_timeout import IdleTimeoutError, iter_with_idle_timeout

_logger = logging.getLogger(__name__)

# Registry of all available sub-agents
SUB_AGENT_REGISTRY: Dict[str, dict] = {
    "travel_planner": TRAVEL_PLANNER_CONFIG,
    "deep_researcher": DEEP_RESEARCHER_CONFIG,
    "gift_advisor": GIFT_ADVISOR_CONFIG,
}


def get_sub_agent_config(name: str) -> Optional[dict]:
    """Get a sub-agent configuration by name."""
    return SUB_AGENT_REGISTRY.get(name)


def list_sub_agent_names() -> List[str]:
    """List all registered sub-agent names."""
    return list(SUB_AGENT_REGISTRY.keys())


def validate_sub_agent_tools(registry) -> List[str]:
    """Validate that all sub-agent tool names exist in the tool registry.

    Args:
        registry: ToolRegistry or ToolBridge with get_all_tool_names()

    Returns:
        List of missing tool names (empty if all valid).
    """
    available = set()
    try:
        available = set(registry.get_all_tool_names())
    except AttributeError:
        _logger.warning("Cannot validate sub-agent tools: registry has no get_all_tool_names()")
        return []

    missing = []
    for agent_name, config in SUB_AGENT_REGISTRY.items():
        for tool_name in config.get("tools", []):
            if tool_name not in available:
                missing.append(f"{agent_name}/{tool_name}")
                _logger.warning(
                    "Sub-agent '%s' references unknown tool '%s'", agent_name, tool_name
                )
    return missing


def get_delegate_tool_definition() -> dict:
    """
    Build the "delegate_to_sub_agent" tool definition for the main agent.

    The main agent uses this tool to delegate complex tasks to specialized sub-agents.
    """
    agent_descriptions = "\n".join(
        f"- {name}: {config['description']}"
        for name, config in SUB_AGENT_REGISTRY.items()
    )

    return {
        "name": "delegate_to_sub_agent",
        "description": (
            "将复杂任务委派给专业子Agent处理。子Agent有独立的推理能力和专业工具，"
            "适合处理需要多步推理的复杂任务。\n\n"
            f"可用的子Agent:\n{agent_descriptions}\n\n"
            "使用时机:\n"
            "- 行程规划 (多日旅行方案) → travel_planner\n"
            "- 深度调研 (需要搜索+分析) → deep_researcher\n"
            "- 礼物推荐 (需要了解偏好+搜索) → gift_advisor"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "enum": list(SUB_AGENT_REGISTRY.keys()),
                    "description": "要委派的子Agent名称",
                },
                "task_description": {
                    "type": "string",
                    "description": "详细的任务描述，包含所有相关上下文和要求",
                },
                "context": {
                    "type": "object",
                    "description": "传递给子Agent的额外上下文信息",
                    "properties": {
                        "destination": {"type": "string"},
                        "days": {"type": "integer"},
                        "budget": {"type": "string"},
                        "preferences": {"type": "string"},
                        "person": {"type": "string"},
                        "occasion": {"type": "string"},
                    },
                },
            },
            "required": ["agent_name", "task_description"],
        },
    }


async def execute_sub_agent_via_sdk(
    agent_name: str,
    task_description: str,
    mcp_server: Any,
    sdk_stream_handler: Any,
    extra_context: Optional[Dict[str, Any]] = None,
    server_key: str = "secretary",
) -> str:
    """Execute a sub-agent via an independent SDK ClaudeSDKClient session.

    Args:
        agent_name: Name of the sub-agent (must be in SUB_AGENT_REGISTRY)
        task_description: Task description to pass to the sub-agent
        mcp_server: MCP server config (same as main agent)
        sdk_stream_handler: SDKStreamHandler for PubSub dispatch
        extra_context: Optional extra context to append to system prompt
        server_key: MCP server key for tool naming

    Returns:
        Sub-agent's text response, or error message
    """
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ClaudeSDKClient,
        AssistantMessage,
        ResultMessage,
        TextBlock,
    )
    from ..sdk.mcp_tool_server import get_allowed_tool_names_for_subset

    sub_config = get_sub_agent_config(agent_name)
    if not sub_config:
        return f"未知的子Agent: {agent_name}"

    sub_tool_names = sub_config.get("tools", [])
    allowed_tools = get_allowed_tool_names_for_subset(sub_tool_names, server_key)

    # Add builtin tools (WebSearch, WebFetch) without MCP prefix — but only
    # when using the official Anthropic API.  Proxies like DashScope do not
    # support server-side search connectors; the MCP web_search tool (backed
    # by Tavily/Serper) is used instead and is already in the MCP tool list.
    from ..sdk.agent_factory import AgentFactory

    builtin_tools = sub_config.get("builtin_tools", ())
    if not AgentFactory._is_using_api_proxy():
        for builtin in builtin_tools:
            allowed_tools.append(builtin)

    sub_system = sub_config["system_prompt"]
    if extra_context:
        context_lines = [f"- {k}: {v}" for k, v in extra_context.items() if v]
        if context_lines:
            sub_system += "\n\n## 任务上下文\n" + "\n".join(context_lines)

    from ..sdk.agent_runner import AgentRunner

    options = ClaudeAgentOptions(
        model=None,  # inherit default
        system_prompt=sub_system,
        max_turns=sub_config.get("max_turns", 30),
        mcp_servers={server_key: mcp_server},
        allowed_tools=allowed_tools,
        disallowed_tools=AgentRunner._build_disallowed_tools(),
        permission_mode="bypassPermissions",
    )

    try:
        from ...config.settings import settings
        default_idle_timeout = int(settings.agent_idle_timeout_seconds)
    except Exception:
        default_idle_timeout = 0
    idle_timeout = int(sub_config.get("idle_timeout_seconds", default_idle_timeout))
    all_text: List[str] = []

    # Use duck-typing for handler dispatch (avoids isinstance issues
    # with relative vs absolute imports creating different class identities)
    has_handler = (
        sdk_stream_handler is not None
        and hasattr(sdk_stream_handler, "handle_sub_agent_message")
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(task_description)

            async for message in iter_with_idle_timeout(
                client.receive_response(), idle_timeout,
            ):
                # Dispatch via the public sub-agent API which handles
                # AssistantMessage and StreamEvent but skips ResultMessage
                # to avoid corrupting parent handler state.
                if has_handler:
                    try:
                        await sdk_stream_handler.handle_sub_agent_message(message)
                    except Exception as stream_err:
                        _logger.warning(
                            "Sub-agent %s stream dispatch error: %s",
                            agent_name, stream_err,
                        )

                # Still accumulate text for tool result return value
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            all_text.append(block.text)
                elif isinstance(message, ResultMessage):
                    if message.is_error:
                        error = getattr(message, "result", "Unknown error")
                        _logger.error(
                            "Sub-agent %s SDK error: %s", agent_name, error,
                        )

    except IdleTimeoutError:
        _logger.error(
            "Sub-agent %s idle timeout: no messages for %ds",
            agent_name, idle_timeout,
        )
        partial = "".join(all_text)
        if partial:
            return partial + "\n\n[注意: 子Agent因空闲超时中断，以上为部分结果]"
        return "子Agent执行超时（无响应），请稍后重试"

    except Exception as e:
        _logger.error("Sub-agent %s execution failed: %s", agent_name, e, exc_info=True)
        return "子Agent执行失败，请稍后重试"

    return "".join(all_text) or "子Agent未返回结果"


__all__ = [
    "SUB_AGENT_REGISTRY",
    "get_sub_agent_config",
    "list_sub_agent_names",
    "get_delegate_tool_definition",
    "execute_sub_agent_via_sdk",
]
