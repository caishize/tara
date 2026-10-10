"""
Pool-based SDK execution for AgentWorker.

Extracted from agent_worker.py to keep files under 800 lines.
Handles the pooled ClaudeSDKClient execution path, including
PooledToolContext creation, reuse, and hook wiring.
"""

import asyncio
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from uuid import UUID

from ...config.settings import settings
from ...core.pubsub import RedisPubSubManager
from ..queue import TaskPayload
from ..sdk.agent_factory import AgentConfig
from ..sdk.agent_runner import AgentRunner
from ..sdk.pooled_context import PooledToolContext
from ..sdk.sdk_client_pool import get_sdk_client_pool
from ..sdk.sdk_stream_handler import SDKStreamHandler
from ..sdk.tool_persistence import ToolPersistenceHandler
from .session_streaming_executor import get_session_streaming_executor_manager

try:
    from claude_agent_sdk import HookMatcher
except ImportError as _import_err:
    raise ImportError(
        "claude-agent-sdk is required. Install with: pip install claude-agent-sdk>=0.1.0"
    ) from _import_err


logger = logging.getLogger(__name__)

SANDBOX_BASE = "/tmp/secretary"

_SAFE_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _make_sandbox_dir(base: str, identifier: str) -> str:
    """Create and validate a sandbox directory path.

    Validates *identifier* against a safe character set to prevent
    path traversal, creates the directory with restrictive permissions,
    and verifies no symlinks were injected.

    Raises:
        ValueError: If identifier contains unsafe characters or
                    the resolved path contains symlinks.
    """
    if not _SAFE_SESSION_ID_RE.match(identifier):
        raise ValueError(f"Invalid identifier for sandbox path: {identifier!r}")
    sandbox_dir = os.path.join(base, identifier)
    os.makedirs(base, mode=0o700, exist_ok=True)
    os.makedirs(sandbox_dir, mode=0o700, exist_ok=True)
    # Verify no symlinks in the path
    resolved = os.path.realpath(sandbox_dir)
    if resolved != os.path.abspath(sandbox_dir):
        raise ValueError(f"Symlink detected in sandbox path: {sandbox_dir}")
    return sandbox_dir


_session_exec_locks: Dict[str, asyncio.Lock] = {}
_session_exec_ref_counts: Dict[str, int] = {}
_session_exec_guard = asyncio.Lock()


@asynccontextmanager
async def _acquire_session_execution_lock(session_id: str):
    """Serialize pooled SDK execution per session_id.

    A pooled ClaudeSDKClient must not process multiple concurrent query/receive
    streams for the same session. Without serialization, one request can starve
    another stream and trigger false idle timeouts.
    """
    wait_started = time.monotonic()
    async with _session_exec_guard:
        lock = _session_exec_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            _session_exec_locks[session_id] = lock
            _session_exec_ref_counts[session_id] = 0
        _session_exec_ref_counts[session_id] = (
            _session_exec_ref_counts.get(session_id, 0) + 1
        )

    await lock.acquire()
    wait_ms = (time.monotonic() - wait_started) * 1000
    if wait_ms > 50:
        logger.info(
            "Session execution lock wait: session=%s wait_ms=%.0f",
            session_id,
            wait_ms,
        )
    try:
        yield
    finally:
        lock.release()
        async with _session_exec_guard:
            remaining = _session_exec_ref_counts.get(session_id, 1) - 1
            if remaining <= 0 and not lock.locked():
                _session_exec_ref_counts.pop(session_id, None)
                _session_exec_locks.pop(session_id, None)
            else:
                _session_exec_ref_counts[session_id] = remaining


async def _build_cold_start_prompt(
    session_id: Optional[str],
    user_id: str,
    family_id: str,
    user_input: str,
) -> str:
    """Enrich *user_input* with conversation history for a cold-started CLI.

    On hot-path (reuse), the SDK already holds multi-turn state and this
    function should NOT be called.  On cold-path (new CLI), we rebuild
    the conversation context from DB so the model can map back-references
    (e.g. user sending "3" to pick from a numbered list).
    """
    if not session_id:
        return user_input
    try:
        from ...db.session import AsyncSessionLocal
        from ...modules.conversation.context_service import ContextService

        ctx_service = ContextService(session_factory=AsyncSessionLocal)
        result = await ctx_service.build_cold_start_conversation(
            session_id=session_id,
            user_id=UUID(user_id),
            family_id=UUID(family_id),
            current_user_input=user_input,
        )
        if result != user_input:
            logger.info(
                "Cold-start prompt built: session=%s original_len=%d enriched_len=%d",
                session_id, len(user_input), len(result),
            )
        return result
    except (ValueError, KeyError, OSError) as e:
        # Expected: invalid UUID, missing DB config, connection refused
        logger.warning(
            "Cold-start prompt build failed (expected): session=%s error=%s",
            session_id, e,
        )
        return user_input
    except Exception:
        # Unexpected: programming errors — log full traceback
        logger.error(
            "Cold-start prompt build failed (unexpected): session=%s",
            session_id,
            exc_info=True,
        )
        return user_input


async def execute_with_pool_or_fallback(
    worker: Any,
    runner: AgentRunner,
    run_config: AgentConfig,
    task: TaskPayload,
    bridge: Any,
    persistence: ToolPersistenceHandler,
    pubsub: RedisPubSubManager,
    mcp_server: Any,
    sdk_stream_handler: SDKStreamHandler,
    hooks: Dict[str, List[HookMatcher]],
    keepalive: Optional[asyncio.Event] = None,
):
    """
    Execute via pooled client if enabled, otherwise fallback to new client.

    The pool path uses PooledToolContext so that MCP handlers / hooks
    created on first connect transparently see the fresh DB session
    when the CLI process is reused.
    """
    use_pool = settings.sdk_client_pool_enabled and task.session_id
    use_streaming_input = (
        bool(task.session_id)
        and settings.sdk_streaming_input_enabled
        and task.route_type in {"slow", "hybrid_background"}
    )

    if use_pool:
        try:
            t0 = time.monotonic()
            if use_streaming_input:
                result = await _execute_with_streaming_input_pool(
                    worker=worker,
                    runner=runner,
                    run_config=run_config,
                    task=task,
                    bridge=bridge,
                    persistence=persistence,
                    pubsub=pubsub,
                    sdk_stream_handler=sdk_stream_handler,
                    keepalive=keepalive,
                )
            else:
                result = await _execute_with_pool(
                    worker=worker,
                    runner=runner,
                    run_config=run_config,
                    task=task,
                    bridge=bridge,
                    persistence=persistence,
                    pubsub=pubsub,
                    sdk_stream_handler=sdk_stream_handler,
                    keepalive=keepalive,
                )
            logger.info(
                "Pooled execution completed: job_id=%s (pool_exec_ms=%.0f)",
                task.job_id,
                (time.monotonic() - t0) * 1000,
            )
            if result.stop_reason == "timeout" and task.session_id and not use_streaming_input:
                # Prevent a timed-out pooled CLI client from being reused.
                # A stale in-flight tool call can otherwise publish late events.
                # Skip for streaming input: the ReactiveSessionActor owns the
                # client lifecycle and handles teardown via _fail_all/_teardown_client.
                try:
                    pool = await get_sdk_client_pool()
                    await pool.mark_disconnected(task.session_id)
                except Exception:
                    logger.warning(
                        "Failed to mark timed-out pooled client disconnected: session=%s",
                        task.session_id,
                        exc_info=True,
                    )
            return result
        except Exception as e:
            logger.warning(
                "Pooled execution failed, falling back to new client: "
                "job_id=%s error=%s streaming_input=%s",
                task.job_id,
                e,
                use_streaming_input,
            )
            if task.session_id and not use_streaming_input:
                # Only disconnect for non-streaming path.  When the streaming
                # input actor fails, it tears down the client itself via
                # _fail_all → _teardown_client → disconnect_inline.  Calling
                # mark_disconnected here races with the actor and can kill the
                # stream for OTHER pending requests still being processed.
                try:
                    pool = await get_sdk_client_pool()
                    await pool.mark_disconnected(task.session_id)
                except Exception:
                    pass

    # Fallback: use new client per request (creates new CLI process)
    # Cold-start: enrich prompt with conversation history from DB
    fallback_prompt = await _build_cold_start_prompt(
        task.session_id, task.user_id, task.family_id, task.user_input,
    )
    sandbox_dir = _make_sandbox_dir(SANDBOX_BASE, task.session_id or task.job_id)
    t0 = time.monotonic()
    try:
        result = await runner.run(
            config=run_config,
            prompt=fallback_prompt,
            mcp_server=mcp_server,
            sdk_stream_handler=sdk_stream_handler,
            hooks=hooks,
            resume_session_id=None,
            emit_error=True,
            keepalive=keepalive,
            sandbox_dir=sandbox_dir,
        )
        logger.info(
            "Fallback (new client) execution completed: job_id=%s (exec_ms=%.0f)",
            task.job_id,
            (time.monotonic() - t0) * 1000,
        )
        return result
    finally:
        from ..sdk.sdk_client_pool import _cleanup_sandbox
        _cleanup_sandbox(sandbox_dir)


async def _execute_with_streaming_input_pool(
    worker: Any,
    runner: AgentRunner,
    run_config: AgentConfig,
    task: TaskPayload,
    bridge: Any,
    persistence: ToolPersistenceHandler,
    pubsub: RedisPubSubManager,
    sdk_stream_handler: SDKStreamHandler,
    keepalive: Optional[asyncio.Event] = None,
):
    """Execute via per-session streaming-input actor for pooled clients."""
    manager = await get_session_streaming_executor_manager()
    return await manager.submit(
        worker=worker,
        runner=runner,
        run_config=run_config,
        task=task,
        bridge=bridge,
        persistence=persistence,
        pubsub=pubsub,
        sdk_stream_handler=sdk_stream_handler,
        keepalive=keepalive,
        hook_builder=build_pooled_sdk_hooks,
    )


async def _execute_with_pool(
    worker: Any,
    runner: AgentRunner,
    run_config: AgentConfig,
    task: TaskPayload,
    bridge: Any,
    persistence: ToolPersistenceHandler,
    pubsub: RedisPubSubManager,
    sdk_stream_handler: SDKStreamHandler,
    keepalive: Optional[asyncio.Event] = None,
):
    """Execute using a pooled ClaudeSDKClient with PooledToolContext.

    On **first** request for a session the method creates a
    ``PooledToolContext``, builds a pooled MCP server + hooks whose
    closures read from the context, and spins up a new CLI client.

    On **subsequent** requests it calls ``ctx.update(...)`` so that
    every existing closure (MCP handlers, PostToolUse hook, sensitive-
    action handler, sub-agent handler) transparently sees the fresh
    DB session, ToolBridge, PubSub manager, etc.
    """
    from ..sdk.mcp_tool_server import create_pooled_mcp_server

    pool = await get_sdk_client_pool()
    session_id = task.session_id
    if not session_id:
        raise ValueError("Pooled execution requires non-empty session_id")

    async with _acquire_session_execution_lock(session_id):
        # Check for existing reusable client with a PooledToolContext
        existing = pool.peek(session_id)
        current_hash = f"{run_config.model or ''}:"
        reuse = (
            existing is not None
            and existing.tool_context is not None
            and existing.options_hash == current_hash
        )

        active_keepalive = keepalive or asyncio.Event()

        if reuse:
            # -- REUSE path: update mutable context in-place --
            ctx = existing.tool_context
            tools_changed = ctx.tools_changed(bridge)
            ctx.update(
                bridge=bridge,
                persistence=persistence,
                task=task,
                pubsub=pubsub,
                sdk_stream_handler=sdk_stream_handler,
                worker=worker,
            )
            ctx.keepalive = active_keepalive

            # Dynamic tool refresh: send MCP tools/list_changed notification
            # so the CLI re-fetches the tool list without a ~80s cold restart.
            if tools_changed:
                refreshed = await ctx.notify_tools_changed()
                if not refreshed:
                    logger.warning(
                        "Dynamic tool refresh failed, invalidating warm client: "
                        "job_id=%s session=%s",
                        task.job_id, session_id,
                    )
                    reuse = False
                else:
                    logger.info(
                        "Dynamic tool refresh succeeded: job_id=%s session=%s",
                        task.job_id, session_id,
                    )

        if reuse:
            pooled = existing
            logger.info(
                "Reusing pooled client: job_id=%s session=%s requests=%d",
                task.job_id, session_id, pooled.request_count,
            )
        else:
            # -- CREATE path: new ctx + pooled MCP + pooled hooks --
            sandbox_dir = _make_sandbox_dir(SANDBOX_BASE, session_id)

            ctx = PooledToolContext()
            ctx.update(
                bridge=bridge,
                persistence=persistence,
                task=task,
                pubsub=pubsub,
                sdk_stream_handler=sdk_stream_handler,
                worker=worker,
            )
            ctx.keepalive = active_keepalive

            # create_pooled_mcp_server calls ctx.refresh_tool_map() internally
            pooled_mcp = create_pooled_mcp_server(ctx)
            pooled_hooks = build_pooled_sdk_hooks(worker, ctx, pooled_mcp)

            options = runner.build_options(
                config=run_config,
                mcp_server=pooled_mcp,
                hooks=pooled_hooks,
                sandbox_dir=sandbox_dir,
            )

            pooled = await pool.get_or_create(session_id, options)
            pooled.tool_context = ctx
            pooled.sandbox_dir = sandbox_dir
            logger.info(
                "Created new pooled client with ctx: job_id=%s session=%s sandbox=%s",
                task.job_id, session_id, sandbox_dir,
            )

        # Hot path (reuse): SDK already has multi-turn state
        # Cold path (create): enrich prompt with conversation history
        if reuse:
            prompt = task.user_input
        else:
            prompt = await _build_cold_start_prompt(
                task.session_id, task.user_id, task.family_id, task.user_input,
            )

        try:
            result = await runner.run_with_client(
                client=pooled.client,
                prompt=prompt,
                sdk_stream_handler=sdk_stream_handler,
                idle_timeout=run_config.idle_timeout_seconds,
                emit_error=True,
                keepalive=active_keepalive,
            )
            await pool.mark_used(session_id)
            return result
        except Exception:
            await pool.mark_disconnected(session_id)
            raise


def build_pooled_sdk_hooks(
    worker: Any,
    ctx: PooledToolContext,
    pooled_mcp_server: Any,
) -> Dict[str, List[HookMatcher]]:
    """Build SDK hooks whose closures read from PooledToolContext.

    All handler callbacks reference ``ctx`` at call time, so pool-reused
    CLI clients automatically see fresh task/pubsub/persistence objects.
    """
    from ..sdk.hooks import (
        create_sensitive_action_hook,
        create_sub_agent_intercept_hook,
        create_builtin_tool_persistence_hook_pooled,
        create_ask_user_question_hook,
    )
    from .pending_action_helpers import SENSITIVE_ACTIONS

    pre_tool_hooks: List[HookMatcher] = []

    # 1. Sensitive action hook -- reads ctx.task / ctx.pubsub / ctx.worker
    async def handle_sensitive(tool_name: str, tool_input: Dict[str, Any]) -> str:
        return await ctx.worker._create_pending_action(
            ctx.task, tool_name, tool_input, ctx.pubsub,
        )
    sensitive_hook = create_sensitive_action_hook(
        sensitive_actions=SENSITIVE_ACTIONS,
        handler_fn=handle_sensitive,
    )
    pre_tool_hooks.append(HookMatcher(hooks=[sensitive_hook]))

    # 2. Sub-agent hook -- reads ctx.sdk_stream_handler / ctx.keepalive
    async def handle_sub_agent(tool_input: Dict[str, Any]) -> str:
        from ..sub_agents import execute_sub_agent_via_sdk

        async def _signal_keepalive() -> None:
            """Periodically signal keepalive to prevent parent idle timeout."""
            while True:
                await asyncio.sleep(30)
                ka = ctx.keepalive
                if ka is not None:
                    ka.set()

        signal_task = asyncio.create_task(_signal_keepalive())
        try:
            return await execute_sub_agent_via_sdk(
                agent_name=tool_input.get("agent_name", ""),
                task_description=tool_input.get("task_description", ""),
                mcp_server=pooled_mcp_server,
                sdk_stream_handler=ctx.sdk_stream_handler,
                extra_context=tool_input.get("context", {}),
            )
        finally:
            signal_task.cancel()
    sub_agent_hook = create_sub_agent_intercept_hook(
        handler_fn=handle_sub_agent,
    )
    pre_tool_hooks.append(
        HookMatcher(matcher="delegate_to_sub_agent", hooks=[sub_agent_hook])
    )

    # 3. AskUserQuestion -- reads ctx.task / ctx.pubsub at call time
    async def _pooled_ask_publish(question_id: str, questions: list) -> int:
        return await ctx.pubsub.publish_ask_user_question(
            user_id=ctx.task.user_id,
            question_id=question_id,
            questions=questions,
            trace_id=ctx.task.job_id or "",
        )

    def _get_redis():
        from ...core.cache import redis_client
        return redis_client.client

    ask_user_hook = create_ask_user_question_hook(
        publish_fn=_pooled_ask_publish,
        redis_getter=_get_redis,
        user_id=ctx.task.user_id if ctx.task else "",
        trace_id=ctx.task.job_id if ctx.task else "",
    )
    pre_tool_hooks.append(
        HookMatcher(matcher="AskUserQuestion", hooks=[ask_user_hook])
    )

    hooks: Dict[str, List[HookMatcher]] = {"PreToolUse": pre_tool_hooks}

    # 4. PostToolUse: pooled builtin persistence
    builtin_hook = create_builtin_tool_persistence_hook_pooled(ctx)
    hooks["PostToolUse"] = [HookMatcher(hooks=[builtin_hook])]

    return hooks
