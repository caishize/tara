"""SDK - Claude Agent SDK client pool and PooledToolContext management.

Provides:
- AgentRunner: Executes the agentic loop via Claude Agent SDK (ClaudeSDKClient)
- AgentFactory: Creates immutable AgentConfig for different use cases
- AgentConfig: Frozen dataclass holding model, prompt, tools, and limits
- ToolPersistenceHandler: 3-layer tool execution persistence
- SDKStreamHandler: Handles SDK message types -> Redis PubSub
- create_secretary_mcp_server: Wraps ToolBridge as in-process MCP server
- create_sensitive_action_hook: SDK hook for sensitive operation interception

Lazy Imports:
    Most exports require ``claude_agent_sdk`` at runtime.  To allow other
    modules to import lightweight helpers (e.g. ``ToolPersistenceHandler``,
    ``SDKStreamHandler``) without the SDK installed, we use ``__getattr__``
    for heavy SDK-dependent symbols.
"""

# These do NOT depend on claude_agent_sdk at import time
from .tool_persistence import ToolPersistenceHandler
from .sdk_stream_handler import SDKStreamHandler
from .pooled_context import PooledToolContext
from .idle_timeout import IdleTimeoutError, iter_with_idle_timeout

# Lazy imports for SDK-dependent modules
_LAZY_IMPORTS = {
    "create_secretary_mcp_server": ".mcp_tool_server",
    "create_pooled_mcp_server": ".mcp_tool_server",
    "get_allowed_tool_names": ".mcp_tool_server",
    "create_sensitive_action_hook": ".hooks",
    "create_sub_agent_intercept_hook": ".hooks",
    "create_ask_user_question_hook": ".hooks",
    "create_builtin_tool_persistence_hook": ".hooks",
    "AgentFactory": ".agent_factory",
    "AgentConfig": ".agent_factory",
    "AgentRunner": ".agent_runner",
    "RunResult": ".agent_runner",
}


def __getattr__(name: str):
    module_path = _LAZY_IMPORTS.get(name)
    if module_path is not None:
        import importlib
        mod = importlib.import_module(module_path, __package__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ToolPersistenceHandler",
    "SDKStreamHandler",
    "PooledToolContext",
    "IdleTimeoutError",
    "iter_with_idle_timeout",
    "create_secretary_mcp_server",
    "create_pooled_mcp_server",
    "get_allowed_tool_names",
    "create_sensitive_action_hook",
    "AgentFactory",
    "AgentConfig",
    "AgentRunner",
    "RunResult",
]
