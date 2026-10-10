"""
Callback factory methods for AgentWorker.

Extracted from agent_worker.py to reduce file size. These methods create
the async callbacks that bridge PubSub events with the SDK stream handler.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from ...core.pubsub import RedisPubSubManager
from ..queue import TaskPayload
from ..sdk.hooks import (
    create_ask_user_question_hook,
    generate_start_summary,
    generate_end_summary,
)
from ..sdk.sdk_stream_handler import SDKStreamHandler

logger = logging.getLogger(__name__)


class WorkerCallbacksMixin:
    """Mixin providing callback factory methods for AgentWorker.

    Requires the host class to have:
    - _pending_builtin_tools: list
    - _completed_builtin_tools: set
    - _collected_tool_calls: list
    - _check_cancel(session_id, expected_user_id=None) -> bool
    - _publish_cancelled(task, pubsub) -> None
    - _publish_content(task, pubsub, text, is_final) -> None
    - _publish_error(task, pubsub, message) -> None
    - _create_pending_action(task, tool_name, tool_input, pubsub) -> str
    - CARD_PRODUCING_TOOLS reference
    """

    def _make_pubsub_publish_fn(self, pubsub: RedisPubSubManager, task: TaskPayload):
        """Create the publish function for SDKStreamHandler.

        Tracks pending builtin tool calls (non-MCP tools) so that tools
        whose PostToolUse hook never fires (e.g. sub-agent builtin tools)
        get auto-completed when the next event arrives, preventing the
        mobile UI from showing a perpetual loading state. If SDK idle timeout
        has fired, suppresses non-error events to avoid duplicate/contradictory
        frontend messages.
        """
        self._pending_builtin_tools.clear()
        pending_builtin_tools = self._pending_builtin_tools
        completed_builtin_tools: set = self._completed_builtin_tools
        content_chunk_count = 0
        # For hybrid_background: suppress tool execution cards (fast worker
        # already responded) but allow content and thinking to stream so the
        # background enrichment doesn't appear as one abrupt batch.
        suppress_realtime_thinking = False
        suppress_realtime_content = False
        suppress_realtime_tools = task.route_type == "hybrid_background"

        def _mark_timeout() -> None:
            """Mark timeout state and clear pending tool queues."""
            self._timed_out = True
            self._pending_mcp_tools.clear()
            pending_builtin_tools.clear()

        async def _flush_pending(exclude_tool: Optional[str] = None) -> None:
            """Auto-complete any pending builtin tools that PostToolUse didn't cover.

            Publishes all pending tool completions in parallel to avoid
            sequential Redis round-trips that block the content stream.
            """
            to_flush = []
            while pending_builtin_tools:
                entry = pending_builtin_tools.pop(0)
                name = entry["name"]
                if name == exclude_tool:
                    continue
                if name in completed_builtin_tools:
                    continue
                if suppress_realtime_tools:
                    continue
                to_flush.append(entry)
            if not to_flush:
                return
            results = await asyncio.gather(
                *(
                    pubsub.publish_tool_execution(
                        user_id=task.user_id,
                        tool_name=entry["name"],
                        status="success",
                        trace_id=task.job_id,
                        session_id=task.session_id,
                        summary=generate_end_summary(
                            entry["name"], entry.get("arguments")
                        ),
                    )
                    for entry in to_flush
                ),
                return_exceptions=True,
            )
            for entry, result in zip(to_flush, results):
                if isinstance(result, Exception):
                    logger.warning(
                        "Failed to auto-complete tool %s for job %s: %s",
                        entry["name"], task.job_id, result,
                    )

        async def publish(channel: str, message: Dict[str, Any]) -> None:
            nonlocal content_chunk_count
            event_type = message.get("type", "")
            if self._timed_out and event_type != "error":
                logger.info(
                    "SDK event suppressed_after_timeout: job_id=%s session=%s "
                    "route=%s event=%s",
                    task.job_id,
                    task.session_id,
                    task.route_type,
                    event_type,
                )
                return

            if event_type == "content":
                if suppress_realtime_content:
                    await _flush_pending()
                    return
                content_chunk_count += 1
                if content_chunk_count == 1:
                    logger.info(
                        "SDK first_content_chunk: job_id=%s session=%s route=%s "
                        "text_len=%d",
                        task.job_id,
                        task.session_id,
                        task.route_type,
                        len(message.get("text", "") or ""),
                    )
                await _flush_pending()
                await self._publish_content(
                    task, pubsub, message.get("text", ""), is_final=False
                )
            elif event_type == "content_final":
                logger.info(
                    "SDK content_final event: job_id=%s session=%s route=%s",
                    task.job_id,
                    task.session_id,
                    task.route_type,
                )
                await _flush_pending()
            elif event_type == "tool_call":
                tool_name = message.get("tool_name", "")
                if tool_name and not tool_name.startswith("mcp__"):
                    arguments = message.get("arguments")
                    await _flush_pending(exclude_tool=tool_name)
                    pending_builtin_tools.append({
                        "name": tool_name,
                        "arguments": arguments,
                    })
                    if suppress_realtime_tools:
                        return
                    start_summary = generate_start_summary(tool_name, arguments)
                    await pubsub.publish_tool_execution(
                        user_id=task.user_id,
                        tool_name=tool_name,
                        status="start",
                        trace_id=task.job_id,
                        session_id=task.session_id,
                        arguments=arguments,
                        summary=start_summary,
                    )
            elif event_type == "thinking_start":
                logger.info(
                    "SDK thinking_start event: job_id=%s session=%s route=%s",
                    task.job_id,
                    task.session_id,
                    task.route_type,
                )
                if suppress_realtime_thinking:
                    return
                await pubsub.publish_thinking(
                    user_id=task.user_id,
                    content="",
                    trace_id=task.job_id,
                    session_id=task.session_id,
                    phase="start",
                )
            elif event_type == "thinking":
                if suppress_realtime_thinking:
                    return
                text = message.get("text", "")
                if text:
                    await pubsub.publish_thinking(
                        user_id=task.user_id,
                        content=text,
                        trace_id=task.job_id,
                        session_id=task.session_id,
                        phase="chunk",
                    )
            elif event_type == "thinking_end":
                logger.info(
                    "SDK thinking_end event: job_id=%s session=%s route=%s",
                    task.job_id,
                    task.session_id,
                    task.route_type,
                )
                if suppress_realtime_thinking:
                    return
                await pubsub.publish_thinking(
                    user_id=task.user_id,
                    content="",
                    trace_id=task.job_id,
                    session_id=task.session_id,
                    phase="end",
                )
            elif event_type == "error":
                error_message = message.get("message", "")
                logger.info(
                    "SDK error event: job_id=%s session=%s route=%s error=%s",
                    task.job_id,
                    task.session_id,
                    task.route_type,
                    error_message,
                )
                if "idle timed out" in error_message.lower():
                    _mark_timeout()
                from .actor_lifecycle import _sanitize_error_for_client
                sanitized = _sanitize_error_for_client(error_message)
                await self._publish_error(task, pubsub, sanitized)
        return publish

    def _make_thinking_callback(self, task: TaskPayload, pubsub: RedisPubSubManager):
        """Create async callback for thinking phase events."""
        async def on_thinking(content: str, phase: str) -> None:
            if task.route_type == "hybrid_background":
                return
            await pubsub.publish_thinking(
                user_id=task.user_id,
                content=content,
                trace_id=task.job_id,
                session_id=task.session_id,
                phase=phase,
            )
        return on_thinking

    def _make_tool_start_callback(self, task: TaskPayload, pubsub: RedisPubSubManager):
        """Create async callback for tool execution start events.

        Also checks the Redis cancel flag before each tool execution,
        tracks MCP tools for keepalive signaling, and signals keepalive
        to prevent SDK idle timeout during tool execution.
        """
        async def on_tool_start(execution_id: str, short_id: str, tool_name: str, **kwargs):
            if self._timed_out:
                logger.debug("Suppressing tool_start after timeout: %s", tool_name)
                return

            if await self._check_cancel(task.session_id, task.user_id):
                logger.info(
                    "Cancel detected at tool_start for job_id=%s, session=%s",
                    task.job_id, task.session_id,
                )
                await self._publish_cancelled(task, pubsub)
                raise asyncio.CancelledError("User cancelled generation")

            # Track MCP tool for heartbeat keepalive signaling
            self._pending_mcp_tools.append({
                "name": tool_name,
                "execution_id": execution_id,
            })
            # Signal keepalive immediately so the idle timer resets
            if self._keepalive is not None:
                self._keepalive.set()

            if task.route_type == "hybrid_background":
                return

            arguments = kwargs.get("arguments")
            start_summary = generate_start_summary(tool_name, arguments)
            await pubsub.publish_tool_execution(
                user_id=task.user_id,
                tool_name=tool_name,
                status="start",
                trace_id=task.job_id,
                session_id=task.session_id,
                execution_id=execution_id,
                arguments=arguments,
                summary=start_summary,
            )
        return on_tool_start

    def _make_tool_end_callback(self, task: TaskPayload, pubsub: RedisPubSubManager):
        """Create async callback for tool execution end events."""
        from ...modules.conversation.card_normalizer import CARD_PRODUCING_TOOLS

        async def on_tool_end(
            execution_id: str, short_id: str, tool_name: str,
            status: str, summary: str, duration_ms: int = 0,
            key_results: Optional[Dict] = None,
            full_result: Optional[Dict] = None,
            **kwargs,
        ):
            # Remove this execution from pending MCP tools first so heartbeat
            # stops progress spam as soon as the tool has ended.
            self._pending_mcp_tools = [
                entry
                for entry in self._pending_mcp_tools
                if entry.get("execution_id") != execution_id
            ]

            if self._timed_out:
                logger.debug("Suppressing tool_end after timeout: %s", tool_name)
                return

            entry: Dict[str, Any] = {
                "execution_id": execution_id,
                "short_id": short_id,
                "tool_name": tool_name,
                "summary": summary,
                "status": status,
            }
            if full_result and tool_name in CARD_PRODUCING_TOOLS:
                entry["full_result"] = full_result
            self._collected_tool_calls.append(entry)

            if not tool_name.startswith("mcp__"):
                self._completed_builtin_tools.add(tool_name)

            if task.route_type == "hybrid_background":
                return

            await pubsub.publish_tool_execution(
                user_id=task.user_id,
                tool_name=tool_name,
                status=status,
                trace_id=task.job_id,
                session_id=task.session_id,
                summary=summary,
                key_results=key_results,
                duration_ms=duration_ms,
                execution_id=execution_id,
            )
        return on_tool_end

    def _make_tool_progress_callback(self, task: TaskPayload, pubsub: RedisPubSubManager):
        """Create async callback for tool execution progress events."""
        async def on_tool_progress(
            execution_id: str, tool_name: str,
            stage: str, message: str, **kwargs,
        ):
            if self._timed_out:
                logger.debug("Suppressing tool_progress after timeout: %s", tool_name)
                return

            if self._keepalive is not None:
                self._keepalive.set()

            if task.route_type == "hybrid_background":
                return

            await pubsub.publish_tool_execution(
                user_id=task.user_id,
                tool_name=tool_name,
                status="progress",
                trace_id=task.job_id,
                session_id=task.session_id,
                summary=message,
                execution_id=execution_id,
            )
        return on_tool_progress

    def _make_sub_agent_sdk_handler(
        self,
        task: TaskPayload,
        mcp_server: Any,
        sdk_stream_handler: SDKStreamHandler,
        keepalive: Optional[asyncio.Event] = None,
    ):
        """Create handler for delegate_to_sub_agent calls (SDK-based)."""
        async def handle_sub_agent(tool_input: Dict[str, Any]) -> str:
            agent_name = tool_input.get("agent_name", "")
            task_description = tool_input.get("task_description", "")
            extra_context = tool_input.get("context", {})

            async def _signal_keepalive() -> None:
                while True:
                    await asyncio.sleep(30)
                    if keepalive is not None:
                        keepalive.set()

            signal_task = asyncio.create_task(_signal_keepalive())
            try:
                from ..sdk.sub_agents import execute_sub_agent_via_sdk
                return await execute_sub_agent_via_sdk(
                    agent_name=agent_name,
                    task_description=task_description,
                    mcp_server=mcp_server,
                    sdk_stream_handler=sdk_stream_handler,
                    extra_context=extra_context,
                )
            finally:
                signal_task.cancel()
        return handle_sub_agent

    def _make_sensitive_action_handler(
        self, task: TaskPayload, pubsub: RedisPubSubManager
    ):
        """Create handler for sensitive action tool calls."""
        async def handle_sensitive(tool_name: str, tool_input: Dict[str, Any]) -> str:
            return await self._create_pending_action(task, tool_name, tool_input, pubsub)
        return handle_sensitive

    def _make_ask_user_question_hook(
        self, task: TaskPayload, pubsub: RedisPubSubManager
    ):
        """Create AskUserQuestion hook for the non-pooled path."""
        async def publish_fn(question_id: str, questions: list) -> int:
            return await pubsub.publish_ask_user_question(
                user_id=task.user_id,
                question_id=question_id,
                questions=questions,
                trace_id=task.job_id or "",
            )

        def redis_getter():
            from ...core.cache import redis_client
            return redis_client.client

        return create_ask_user_question_hook(
            publish_fn=publish_fn,
            redis_getter=redis_getter,
            user_id=task.user_id,
            trace_id=task.job_id or "",
        )
