"""
Agent Runner - SDK-based agentic execution using ClaudeSDKClient.

Replaces the hand-written while loop + messages.stream() with the
Claude Agent SDK's ClaudeSDKClient, which manages the agentic loop
internally (tool execution, turn management, streaming).

Design principles (from INTEGRATION_PLAN.md):
    - Ephemeral: each run() call is stateless, no long-lived agent
    - Streaming: events dispatched via SDKStreamHandler → Redis PubSub
    - Tool execution: delegated to MCP server with ToolPersistenceHandler
    - Sub-agent: delegate_to_sub_agent intercepted via PreToolUse hook
    - Sensitive actions: intercepted via PreToolUse hook

Usage:
    runner = AgentRunner()

    # Option 1: Create new client per request (old behavior)
    result = await runner.run(
        config=agent_config,
        prompt="user message",
        mcp_server=mcp_server,
        sdk_stream_handler=sdk_stream_handler,
        hooks=hooks,
    )

    # Option 2: Reuse pooled client (new, faster)
    from .sdk_client_pool import get_sdk_client_pool
    pool = await get_sdk_client_pool()
    pooled = await pool.get_or_create(session_id, options)
    result = await runner.run_with_client(
        client=pooled.client,
        prompt="user message",
        sdk_stream_handler=sdk_stream_handler,
        idle_timeout=0,
    )
"""

import asyncio
import inspect
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ClaudeSDKClient,
        HookMatcher,
        AssistantMessage,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )
except ImportError as _import_err:
    raise ImportError(
        "claude-agent-sdk is required for AgentRunner. "
        "Install it with: pip install claude-agent-sdk>=0.1.0"
    ) from _import_err

from .agent_factory import AgentConfig
from .idle_timeout import IdleTimeoutError, iter_with_idle_timeout
from .sdk_stream_handler import SDKStreamHandler

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    """Immutable result of an AgentRunner.run() execution."""

    text: str
    tool_calls: List[Dict[str, Any]]
    stop_reason: Optional[str]
    turns_used: int
    total_cost_usd: Optional[float] = None
    usage: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


class AgentRunner:
    """
    Executes the agentic reasoning loop using Claude Agent SDK.

    This class replaces the manual while-loop + messages.stream()
    with the SDK's ClaudeSDKClient which handles the agentic loop
    internally (tool calls, turn management, streaming).

    The runner is stateless between run() calls.
    """

    # Filesystem tools that require sandbox enforcement.  When a sandbox
    # directory is provided these are allowed (with a path-enforcement
    # hook); otherwise they are fully disallowed.
    _FILESYSTEM_TOOLS: List[str] = [
        "Bash", "Read", "Write", "Edit",
        "Grep", "Glob", "LS",
        "NotebookEdit", "NotebookRead",
    ]

    # SDK builtin tools that only work with the official Anthropic API.
    # When using a proxy (e.g. DashScope), these must also be disallowed
    # to prevent them from showing up and returning empty results.
    _PROXY_INCOMPATIBLE_TOOLS: List[str] = [
        "WebSearch", "WebFetch",
    ]

    def __init__(
        self,
        thinking_budget_tokens: int = 5000,
    ):
        self._thinking_budget_tokens = thinking_budget_tokens

    async def run(
        self,
        config: AgentConfig,
        prompt: str,
        mcp_server: Any,
        sdk_stream_handler: SDKStreamHandler,
        hooks: Optional[Dict[str, List[HookMatcher]]] = None,
        server_key: str = "secretary",
        resume_session_id: Optional[str] = None,
        emit_error: bool = True,
        keepalive: Optional[asyncio.Event] = None,
        sandbox_dir: Optional[str] = None,
    ) -> RunResult:
        """
        Execute the full agentic reasoning loop via SDK.

        Args:
            config: Immutable agent configuration
            prompt: Latest user message (SDK manages conversation internally)
            mcp_server: MCP server config from create_secretary_mcp_server()
            sdk_stream_handler: Handler for SDK messages → PubSub dispatch
            hooks: Optional SDK hooks dict (PreToolUse, PostToolUse, etc.)
            server_key: MCP server key used in allowed_tools naming
            resume_session_id: Optional SDK session id to resume
            emit_error: Whether to emit error events on failure

        Returns:
            RunResult with collected text, tool calls, and stop info
        """
        allowed_tools = self._build_allowed_tools(config, server_key)

        cli_env = self._build_cli_env()
        cli_settings = self._build_cli_settings()

        def _stderr_callback(line: str) -> None:
            """Capture Claude CLI stderr for debugging."""
            logger.warning("Claude CLI stderr: %s", line[:500])

        options_kwargs: Dict[str, Any] = {
            "model": config.model,
            "system_prompt": config.system_prompt,
            "max_turns": config.max_turns,
            "mcp_servers": {server_key: mcp_server},
            "allowed_tools": allowed_tools,
            "disallowed_tools": self._build_disallowed_tools(sandbox_dir),
            "permission_mode": "bypassPermissions",
            "hooks": hooks,
            "include_partial_messages": True,
            "env": cli_env,
            "stderr": _stderr_callback,
        }
        if sandbox_dir:
            options_kwargs["cwd"] = sandbox_dir
            # Inject sandbox path-enforcement hook
            merged_hooks = dict(hooks) if hooks else {}
            pre = list(merged_hooks.get("PreToolUse", []))
            from .hooks import create_sandbox_enforcement_hook
            pre.append(HookMatcher(hooks=[create_sandbox_enforcement_hook(sandbox_dir)]))
            merged_hooks["PreToolUse"] = pre
            options_kwargs["hooks"] = merged_hooks
        # Extended thinking disables StreamEvent partials in the SDK.
        # Only enable it when explicitly requested.
        try:
            from ...config.settings import settings
            if settings.claude_agent_thinking_enabled:
                options_kwargs["max_thinking_tokens"] = self._thinking_budget_tokens
        except Exception:
            logger.debug("Failed to read thinking_enabled setting", exc_info=True)
        if cli_settings:
            options_kwargs["settings"] = cli_settings

        if resume_session_id:
            if _supports_param(ClaudeAgentOptions, "resume"):
                options_kwargs["resume"] = resume_session_id
            elif _supports_param(ClaudeAgentOptions, "session_id"):
                options_kwargs["session_id"] = resume_session_id
            elif _supports_param(ClaudeAgentOptions, "resume_session_id"):
                options_kwargs["resume_session_id"] = resume_session_id

        options = ClaudeAgentOptions(**options_kwargs)

        all_text: List[str] = []
        all_tool_calls: List[Dict[str, Any]] = []
        stop_reason: Optional[str] = None
        turns_used: int = 0
        total_cost_usd: Optional[float] = None
        usage: Optional[Dict[str, Any]] = None
        sdk_session_id: Optional[str] = None
        msg_count = 0
        last_msg_type: Optional[str] = None

        idle_timeout = int(config.idle_timeout_seconds)

        try:
            t_cli_start = time.monotonic()
            async with ClaudeSDKClient(options=options) as client:
                t_cli_ready = time.monotonic()
                logger.info(
                    "CLI subprocess ready (startup_ms=%.0f, model=%s)",
                    (t_cli_ready - t_cli_start) * 1000,
                    config.model,
                )
                query_kwargs: Dict[str, Any] = {}
                if resume_session_id:
                    if _supports_param(client.query, "session_id"):
                        query_kwargs["session_id"] = resume_session_id
                    elif _supports_param(client.query, "resume"):
                        query_kwargs["resume"] = resume_session_id

                t_query_start = time.monotonic()
                await client.query(prompt, **query_kwargs)
                logger.info(
                    "Query sent to CLI (query_ms=%.0f, prompt_len=%d, model=%s)",
                    (time.monotonic() - t_query_start) * 1000,
                    len(prompt), config.model,
                )

                msg_count = 0
                last_msg_type = None
                async for message in iter_with_idle_timeout(
                    client.receive_response(), idle_timeout, keepalive,
                ):
                    msg_count += 1
                    last_msg_type = type(message).__name__
                    await sdk_stream_handler.handle_sdk_message(message)

                    if isinstance(message, AssistantMessage):
                        block_types = [type(b).__name__ for b in message.content]
                        logger.info(
                            "AssistantMessage #%d: blocks=%s",
                            msg_count, block_types,
                        )
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                if block.text and block.text.strip() not in ("(no content)", "(No content)", ""):
                                    all_text.append(block.text)
                            elif isinstance(block, ToolUseBlock):
                                all_tool_calls.append({
                                    "id": block.id,
                                    "name": block.name,
                                    "input": block.input,
                                })

                    elif isinstance(message, ResultMessage):
                        stop_reason = message.subtype
                        turns_used = getattr(message, "num_turns", 0)
                        total_cost_usd = getattr(message, "total_cost_usd", None)
                        usage = getattr(message, "usage", None)
                        sdk_session_id = getattr(message, "session_id", None)

                logger.info(
                    "SDK stream completed: total_messages=%d, turns=%d, "
                    "stop_reason=%s, elapsed_ms=%.0f",
                    msg_count, turns_used, stop_reason,
                    (time.monotonic() - t_query_start) * 1000,
                )

        except IdleTimeoutError as e:
            error_msg = (
                f"SDK execution idle timed out (no messages for {idle_timeout}s, "
                f"model={config.model}, max_turns={config.max_turns}, "
                f"messages_before_timeout={msg_count}, "
                f"last_message_type={last_msg_type})"
            )
            logger.error("AgentRunner idle timeout: %s | detail: %s", error_msg, e)
            if emit_error:
                await sdk_stream_handler.emit_error(error_msg)
            return RunResult(
                text="".join(all_text),
                tool_calls=all_tool_calls,
                stop_reason="timeout",
                turns_used=turns_used,
                total_cost_usd=total_cost_usd,
                usage=usage,
                session_id=sdk_session_id,
            )

        except Exception as e:
            logger.error(
                "SDK AgentRunner.run() failed: %s (model=%s, turns_used=%d)",
                e, config.model, turns_used, exc_info=True,
            )
            if emit_error:
                await sdk_stream_handler.emit_error(str(e))
            raise

        return RunResult(
            text="".join(all_text),
            tool_calls=all_tool_calls,
            stop_reason=stop_reason,
            turns_used=turns_used,
            total_cost_usd=total_cost_usd,
            usage=usage,
            session_id=sdk_session_id,
        )

    async def run_with_client(
        self,
        client: ClaudeSDKClient,
        prompt: str,
        sdk_stream_handler: SDKStreamHandler,
        idle_timeout: int = 0,
        emit_error: bool = True,
        keepalive: Optional[asyncio.Event] = None,
    ) -> RunResult:
        """
        Execute reasoning using an existing (pooled) ClaudeSDKClient.

        This method is used when reusing a persistent client connection,
        avoiding CLI startup overhead (~80s with DashScope API).

        Args:
            client: An already-connected ClaudeSDKClient
            prompt: User message to send
            sdk_stream_handler: Handler for SDK messages → PubSub dispatch
            idle_timeout: Seconds to wait for response before timeout (0 disables)
            emit_error: Whether to emit error events on failure

        Returns:
            RunResult with collected text, tool calls, and stop info
        """
        all_text: List[str] = []
        all_tool_calls: List[Dict[str, Any]] = []
        stop_reason: Optional[str] = None
        turns_used: int = 0
        total_cost_usd: Optional[float] = None
        usage: Optional[Dict[str, Any]] = None
        sdk_session_id: Optional[str] = None
        msg_count = 0
        last_msg_type: Optional[str] = None

        try:
            # Send query to existing client
            t_query_start = time.monotonic()
            await client.query(prompt)
            logger.info(
                "Pooled query sent (query_ms=%.0f, prompt_len=%d)",
                (time.monotonic() - t_query_start) * 1000,
                len(prompt),
            )

            async for message in iter_with_idle_timeout(
                client.receive_response(), idle_timeout, keepalive,
            ):
                msg_count += 1
                last_msg_type = type(message).__name__
                await sdk_stream_handler.handle_sdk_message(message)

                if isinstance(message, AssistantMessage):
                    block_types = [type(b).__name__ for b in message.content]
                    logger.info(
                        "Pooled AssistantMessage #%d: blocks=%s",
                        msg_count, block_types,
                    )
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            if block.text and block.text.strip() not in ("(no content)", "(No content)", ""):
                                all_text.append(block.text)
                        elif isinstance(block, ToolUseBlock):
                            all_tool_calls.append({
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            })

                elif isinstance(message, ResultMessage):
                    stop_reason = message.subtype
                    turns_used = getattr(message, "num_turns", 0)
                    total_cost_usd = getattr(message, "total_cost_usd", None)
                    usage = getattr(message, "usage", None)
                    sdk_session_id = getattr(message, "session_id", None)

            logger.info(
                "Pooled stream completed: total_messages=%d, turns=%d, "
                "stop_reason=%s, elapsed_ms=%.0f",
                msg_count, turns_used, stop_reason,
                (time.monotonic() - t_query_start) * 1000,
            )

        except IdleTimeoutError as e:
            error_msg = (
                f"SDK execution idle timed out (no messages for {idle_timeout}s, "
                f"messages_before_timeout={msg_count}, "
                f"last_message_type={last_msg_type})"
            )
            logger.error(
                "AgentRunner idle timeout (pooled client): %s | detail: %s",
                error_msg, e,
            )
            if emit_error:
                await sdk_stream_handler.emit_error(error_msg)
            return RunResult(
                text="".join(all_text),
                tool_calls=all_tool_calls,
                stop_reason="timeout",
                turns_used=turns_used,
                total_cost_usd=total_cost_usd,
                usage=usage,
                session_id=sdk_session_id,
            )

        except Exception as e:
            logger.error(
                "SDK AgentRunner.run_with_client() failed: %s",
                e, exc_info=True,
            )
            if emit_error:
                await sdk_stream_handler.emit_error(str(e))
            raise

        # Emit buffered thinking if SDK didn't stream it
        await sdk_stream_handler.emit_missing_thinking()

        return RunResult(
            text="".join(all_text),
            tool_calls=all_tool_calls,
            stop_reason=stop_reason,
            turns_used=turns_used,
            total_cost_usd=total_cost_usd,
            usage=usage,
            session_id=sdk_session_id,
        )

    def build_options(
        self,
        config: AgentConfig,
        mcp_server: Any,
        hooks: Optional[Dict[str, List[HookMatcher]]] = None,
        server_key: str = "secretary",
        sandbox_dir: Optional[str] = None,
    ) -> ClaudeAgentOptions:
        """
        Build ClaudeAgentOptions from AgentConfig.

        This is extracted for use with SDKClientPool, which needs
        the options to create/validate pooled clients.

        Args:
            config: Agent configuration
            mcp_server: MCP server config
            hooks: Optional SDK hooks
            server_key: MCP server key for tool naming
            sandbox_dir: Optional working directory for CLI sandbox

        Returns:
            ClaudeAgentOptions ready for ClaudeSDKClient
        """
        allowed_tools = self._build_allowed_tools(config, server_key)
        cli_env = self._build_cli_env()
        cli_settings = self._build_cli_settings()

        def _stderr_callback(line: str) -> None:
            logger.debug("Claude CLI stderr: %s", line[:500])

        options_kwargs: Dict[str, Any] = {
            "model": config.model,
            "system_prompt": config.system_prompt,
            "max_turns": config.max_turns,
            "mcp_servers": {server_key: mcp_server},
            "allowed_tools": allowed_tools,
            "disallowed_tools": self._build_disallowed_tools(sandbox_dir),
            "permission_mode": "bypassPermissions",
            "hooks": hooks,
            "include_partial_messages": True,
            "env": cli_env,
            "stderr": _stderr_callback,
        }

        if sandbox_dir:
            options_kwargs["cwd"] = sandbox_dir
            # Inject sandbox path-enforcement hook
            merged_hooks = dict(hooks) if hooks else {}
            pre = list(merged_hooks.get("PreToolUse", []))
            from .hooks import create_sandbox_enforcement_hook
            pre.append(HookMatcher(hooks=[create_sandbox_enforcement_hook(sandbox_dir)]))
            merged_hooks["PreToolUse"] = pre
            options_kwargs["hooks"] = merged_hooks

        # Extended thinking
        try:
            from ...config.settings import settings
            if settings.claude_agent_thinking_enabled:
                options_kwargs["max_thinking_tokens"] = self._thinking_budget_tokens
        except Exception:
            logger.debug("Failed to read thinking_enabled setting", exc_info=True)

        if cli_settings:
            options_kwargs["settings"] = cli_settings

        return ClaudeAgentOptions(**options_kwargs)

    @classmethod
    def _build_disallowed_tools(
        cls,
        sandbox_dir: Optional[str] = None,
    ) -> List[str]:
        """Build the list of disallowed builtin tools.

        When *sandbox_dir* is provided, filesystem tools are allowed
        (path enforcement is handled by a separate PreToolUse hook).
        When no sandbox is provided (e.g. sub-agents), all filesystem
        tools are disallowed for safety.

        Additionally disables WebSearch/WebFetch when using a proxy.
        """
        disallowed: List[str] = []
        if not sandbox_dir:
            # No sandbox → disable all filesystem tools
            disallowed.extend(cls._FILESYSTEM_TOOLS)
        try:
            from .agent_factory import AgentFactory
            if AgentFactory._is_using_api_proxy():
                disallowed.extend(cls._PROXY_INCOMPATIBLE_TOOLS)
        except Exception:
            logger.debug("Failed to check API proxy status", exc_info=True)
        return disallowed

    @staticmethod
    def _build_cli_env() -> Dict[str, str]:
        """Build environment variables for the Claude CLI subprocess.

        Forwards ANTHROPIC_BASE_URL and ANTHROPIC_API_KEY from settings
        so the CLI subprocess can connect to compatible API endpoints
        (e.g., Alibaba Cloud DashScope).
        """
        from ...config.settings import settings

        env: Dict[str, str] = {}
        if settings.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.anthropic_base_url:
            env["ANTHROPIC_BASE_URL"] = settings.anthropic_base_url
        return env

    @staticmethod
    def _build_cli_settings() -> Optional[str]:
        """Build Claude CLI settings JSON to control features like thinking."""
        try:
            from ...config.settings import settings
        except Exception:
            return None

        cli_settings: Dict[str, Any] = {}
        # Map SDK thinking flag to Claude Code's extended thinking setting.
        if hasattr(settings, "claude_agent_thinking_enabled"):
            cli_settings["alwaysThinkingEnabled"] = bool(
                settings.claude_agent_thinking_enabled
            )

        if not cli_settings:
            return None
        return json.dumps(cli_settings)

    @staticmethod
    def _build_allowed_tools(
        config: AgentConfig,
        server_key: str,
    ) -> List[str]:
        """Build SDK allowed_tools list from AgentConfig.

        MCP tools are named: mcp__<server_key>__<tool_name>
        Builtin tools (e.g. WebSearch, WebFetch) are added without prefix.
        """
        allowed = []
        for tool_def in config.tools:
            name = tool_def.get("name", "")
            if name:
                allowed.append(f"mcp__{server_key}__{name}")

        for builtin in config.builtin_tools:
            allowed.append(builtin)

        return allowed


def _supports_param(callable_obj: Any, name: str) -> bool:
    """Check if a callable accepts a given parameter name."""
    try:
        return name in inspect.signature(callable_obj).parameters
    except (TypeError, ValueError):
        return False
