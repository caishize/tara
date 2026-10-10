"""
Per-session streaming-input executor for pooled SDK clients.

This module provides a session actor that:
1. Owns the pooled ClaudeSDKClient receive loop (single consumer)
2. Accepts multiple queued task requests for the same session
3. Sends prompts to CLI immediately via query(), relying on SDK/CLI queueing
4. Routes streamed messages/result boundaries back to each request in FIFO order
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Deque, Dict, List, Optional

from ...config.settings import settings
from ...core.pubsub import RedisPubSubManager
from ..queue import TaskPayload
from ..sdk.agent_factory import AgentConfig
from ..sdk.agent_runner import AgentRunner, RunResult
from ..sdk.pooled_context import PooledToolContext
from ..sdk.sdk_client_pool import SDKClientPool, get_sdk_client_pool
from ..sdk.sdk_stream_handler import SDKStreamHandler
from ..sdk.tool_persistence import ToolPersistenceHandler
from .reactive_session_actor import (
    ReactiveSessionActor,
    _StreamingRequest as _ReactiveStreamingRequest,
)

try:
    from claude_agent_sdk import (
        HookMatcher,
        AssistantMessage,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )
except ImportError as _import_err:
    raise ImportError(
        "claude-agent-sdk is required. Install with: pip install claude-agent-sdk>=0.1.0"
    ) from _import_err


logger = logging.getLogger(__name__)

HookBuilder = Callable[[Any, PooledToolContext, Any], Dict[str, List[HookMatcher]]]


@dataclass
class _StreamingRequest:
    worker: Any
    runner: AgentRunner
    run_config: AgentConfig
    task: TaskPayload
    bridge: Any
    persistence: ToolPersistenceHandler
    pubsub: RedisPubSubManager
    sdk_stream_handler: SDKStreamHandler
    keepalive: Optional[asyncio.Event]
    hook_builder: HookBuilder
    future: asyncio.Future
    all_text: List[str] = field(default_factory=list)
    all_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    stop_reason: Optional[str] = None
    turns_used: int = 0
    total_cost_usd: Optional[float] = None
    usage: Optional[Dict[str, Any]] = None
    sdk_session_id: Optional[str] = None
    msg_count: int = 0
    last_msg_type: Optional[str] = None

    @property
    def options_hash(self) -> str:
        return f"{self.run_config.model or ''}:"


class _SessionStreamingActor:
    """Single-session actor multiplexing streamed SDK messages to queued jobs."""

    def __init__(
        self,
        session_id: str,
        idle_seconds: int,
        on_exit: Callable[[str, "_SessionStreamingActor"], Awaitable[None]],
    ) -> None:
        self.session_id = session_id
        self._idle_seconds = max(1, int(idle_seconds))
        self._on_exit = on_exit
        self._queue: asyncio.Queue[_StreamingRequest] = asyncio.Queue()
        self._pending: Deque[_StreamingRequest] = deque()
        self._task: Optional[asyncio.Task] = None
        self._closed = asyncio.Event()
        self._stop_requested = False

        self._pool: Optional[SDKClientPool] = None
        self._pooled = None
        self._ctx: Optional[PooledToolContext] = None
        self._receive_iter = None
        self._options_hash: Optional[str] = None

    @property
    def done(self) -> bool:
        return self._task is None or self._task.done()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(
            self._run(),
            name=f"session-streaming-actor:{self.session_id}",
        )

    async def submit(self, request: _StreamingRequest) -> RunResult:
        if self._stop_requested:
            raise RuntimeError(f"Session actor is stopping: {self.session_id}")
        await self._queue.put(request)
        return await request.future

    async def _run(self) -> None:
        logger.info("Session streaming actor started: session=%s", self.session_id)
        try:
            while True:
                if self._stop_requested:
                    if self._queue.empty() and not self._pending:
                        break

                if not self._pending:
                    try:
                        req = await asyncio.wait_for(
                            self._queue.get(),
                            timeout=self._idle_seconds,
                        )
                    except asyncio.TimeoutError:
                        if self._queue.empty():
                            break
                        continue
                    try:
                        await self._accept_request(req)
                    except Exception as e:
                        await self._emit_request_error(req, e)
                        await self._fail_all(e)
                    finally:
                        self._queue.task_done()
                    continue

                queue_task = asyncio.create_task(self._queue.get())
                message_task = asyncio.create_task(self._next_message())
                done, pending_tasks = await asyncio.wait(
                    {queue_task, message_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if queue_task in done:
                    try:
                        req = queue_task.result()
                    except Exception as e:
                        await self._fail_all(e)
                    else:
                        try:
                            await self._accept_request(req)
                        except Exception as e:
                            await self._emit_request_error(req, e)
                            await self._fail_all(e)
                        finally:
                            self._queue.task_done()

                if message_task in done:
                    try:
                        message = message_task.result()
                    except Exception as e:
                        await self._fail_all(e)
                    else:
                        await self._handle_message(message)
                elif queue_task in done:
                    # Give stream consumption a short chance even when queue
                    # remains hot, to avoid starving SDK receive loop.
                    try:
                        message = await asyncio.wait_for(message_task, timeout=0.01)
                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        await self._fail_all(e)
                    else:
                        await self._handle_message(message)

                for p in pending_tasks:
                    p.cancel()
                if pending_tasks:
                    await asyncio.gather(*pending_tasks, return_exceptions=True)

        except asyncio.CancelledError:
            await self._fail_all(
                RuntimeError("Session streaming actor cancelled"),
                mark_disconnected=False,
            )
            raise
        finally:
            await self._teardown_client(mark_disconnected=False)
            self._closed.set()
            await self._on_exit(self.session_id, self)
            logger.info("Session streaming actor closed: session=%s", self.session_id)

    async def _accept_request(self, request: _StreamingRequest) -> None:
        was_cold_start = self._pooled is None
        await self._ensure_client(request)

        if self._options_hash and request.options_hash != self._options_hash:
            err = RuntimeError(
                f"Session {self.session_id} model changed during active stream "
                f"({self._options_hash} -> {request.options_hash})"
            )
            await self._emit_request_error(request, err)
            return

        was_empty = not self._pending
        self._pending.append(request)
        if was_empty:
            await self._activate_request(request)

        # Cold-start: enrich prompt with conversation history from DB
        if was_cold_start:
            from .agent_pool_executor import _build_cold_start_prompt

            prompt = await _build_cold_start_prompt(
                request.task.session_id,
                request.task.user_id,
                request.task.family_id,
                request.task.user_input,
            )
        else:
            prompt = request.task.user_input

        try:
            await self._pooled.client.query(prompt)
            logger.info(
                "Streaming query submitted: session=%s job_id=%s pending=%d cold_start=%s",
                self.session_id,
                request.task.job_id,
                len(self._pending),
                was_cold_start,
            )
        except Exception as e:
            try:
                self._pending.remove(request)
            except ValueError:
                pass
            if self._pending:
                await self._activate_request(self._pending[0])
            await self._emit_request_error(request, e)
            await self._teardown_client(mark_disconnected=True)

    async def _ensure_client(self, request: _StreamingRequest) -> None:
        if self._pooled is not None and self._ctx is not None:
            return

        from ..sdk.mcp_tool_server import create_pooled_mcp_server

        pool = await get_sdk_client_pool()
        ctx = PooledToolContext()
        ctx.update(
            bridge=request.bridge,
            persistence=request.persistence,
            task=request.task,
            pubsub=request.pubsub,
            sdk_stream_handler=request.sdk_stream_handler,
            worker=request.worker,
        )
        ctx.keepalive = request.keepalive or asyncio.Event()

        pooled_mcp = create_pooled_mcp_server(ctx)
        pooled_hooks = request.hook_builder(request.worker, ctx, pooled_mcp)
        options = request.runner.build_options(
            config=request.run_config,
            mcp_server=pooled_mcp,
            hooks=pooled_hooks,
        )

        pooled = await pool.get_or_create(self.session_id, options)
        pooled.tool_context = ctx

        self._pool = pool
        self._pooled = pooled
        self._ctx = ctx
        self._receive_iter = pooled.client.receive_messages().__aiter__()
        self._options_hash = request.options_hash
        logger.info(
            "Session streaming actor connected pooled client: session=%s",
            self.session_id,
        )

    async def _activate_request(self, request: _StreamingRequest) -> None:
        if self._ctx is None:
            return
        tools_changed = self._ctx.tools_changed(request.bridge)
        self._ctx.update(
            bridge=request.bridge,
            persistence=request.persistence,
            task=request.task,
            pubsub=request.pubsub,
            sdk_stream_handler=request.sdk_stream_handler,
            worker=request.worker,
        )
        self._ctx.keepalive = request.keepalive or asyncio.Event()
        if tools_changed:
            refreshed = await self._ctx.notify_tools_changed()
            if refreshed:
                logger.info(
                    "Dynamic tool refresh (streaming): session=%s",
                    self.session_id,
                )
            else:
                logger.warning(
                    "Dynamic tool refresh failed (streaming), client may have stale tools: "
                    "session=%s",
                    self.session_id,
                )

    async def _next_message(self):
        if self._receive_iter is None:
            raise RuntimeError(
                f"Session {self.session_id} receive iterator not initialized"
            )
        try:
            return await self._receive_iter.__anext__()
        except StopAsyncIteration as e:
            raise RuntimeError(
                f"Session {self.session_id} stream ended unexpectedly"
            ) from e

    async def _handle_message(self, message: Any) -> None:
        if not self._pending:
            logger.debug(
                "Dropping SDK message with no pending request: session=%s type=%s",
                self.session_id,
                type(message).__name__,
            )
            return

        req = self._pending[0]
        req.msg_count += 1
        req.last_msg_type = type(message).__name__

        try:
            await req.sdk_stream_handler.handle_sdk_message(message)
        except Exception as e:
            await self._fail_all(e)
            return

        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    if block.text and block.text.strip() not in (
                        "(no content)",
                        "(No content)",
                        "",
                    ):
                        req.all_text.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    req.all_tool_calls.append(
                        {
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
            return

        if not isinstance(message, ResultMessage):
            return

        req.stop_reason = message.subtype
        req.turns_used = getattr(message, "num_turns", 0)
        req.total_cost_usd = getattr(message, "total_cost_usd", None)
        req.usage = getattr(message, "usage", None)
        req.sdk_session_id = getattr(message, "session_id", None)

        try:
            await req.sdk_stream_handler.emit_missing_thinking()
        except Exception as e:
            await self._emit_request_error(req, e)
            self._pending.popleft()
            if self._pending:
                await self._activate_request(self._pending[0])
            return

        result = RunResult(
            text="".join(req.all_text),
            tool_calls=req.all_tool_calls,
            stop_reason=req.stop_reason,
            turns_used=req.turns_used,
            total_cost_usd=req.total_cost_usd,
            usage=req.usage,
            session_id=req.sdk_session_id,
        )
        if not req.future.done():
            req.future.set_result(result)

        self._pending.popleft()
        if self._pool is not None:
            await self._pool.mark_used(self.session_id)

        if self._pending:
            self._activate_request(self._pending[0])

    async def _emit_request_error(self, request: _StreamingRequest, error: Exception) -> None:
        try:
            await request.sdk_stream_handler.emit_error(str(error))
        except Exception:
            pass
        if not request.future.done():
            request.future.set_exception(error)

    async def _fail_all(
        self,
        error: Exception,
        *,
        mark_disconnected: bool = True,
    ) -> None:
        if self._pending:
            logger.warning(
                "Failing %d pending request(s): session=%s error=%s",
                len(self._pending),
                self.session_id,
                error,
            )
        while self._pending:
            req = self._pending.popleft()
            await self._emit_request_error(req, error)
        await self._teardown_client(mark_disconnected=mark_disconnected)

    async def _teardown_client(self, *, mark_disconnected: bool) -> None:
        # Capture pool reference and clear state BEFORE disconnect.
        # Same pattern as ReactiveSessionActor._teardown_client.
        pool = self._pool
        self._pool = None
        self._pooled = None
        self._ctx = None
        self._receive_iter = None
        self._options_hash = None

        if pool is not None and mark_disconnected:
            try:
                await pool.disconnect_inline(self.session_id)
            except BaseException:
                logger.warning(
                    "Failed to disconnect session during teardown: session=%s",
                    self.session_id,
                    exc_info=True,
                )

    def request_stop(self, reason: str = "unspecified") -> None:
        logger.info(
            "Session streaming actor request_stop: session=%s reason=%s "
            "already_stop=%s pending_len=%d queue_size=%d",
            self.session_id,
            reason,
            self._stop_requested,
            len(self._pending),
            self._queue.qsize(),
        )
        self._stop_requested = True
        if self._task is not None and not self._task.done():
            logger.info(
                "Session streaming actor cancelling task: session=%s task_name=%s",
                self.session_id,
                self._task.get_name(),
            )
            self._task.cancel()

    async def wait_closed(self, timeout_seconds: Optional[float] = None) -> bool:
        if timeout_seconds is None:
            await self._closed.wait()
            return True
        try:
            await asyncio.wait_for(self._closed.wait(), timeout=timeout_seconds)
            return True
        except asyncio.TimeoutError:
            return False


class SessionStreamingExecutorManager:
    """Manager for per-session streaming-input actors.

    Creates ``ReactiveSessionActor`` instances that support full-duplex
    intervention signals.  Falls back to ``_SessionStreamingActor`` only
    if the reactive actor import fails (should never happen in production).
    """

    def __init__(self, idle_seconds: int) -> None:
        self._idle_seconds = idle_seconds
        self._actors: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def submit(
        self,
        worker: Any,
        runner: AgentRunner,
        run_config: AgentConfig,
        task: TaskPayload,
        bridge: Any,
        persistence: ToolPersistenceHandler,
        pubsub: RedisPubSubManager,
        sdk_stream_handler: SDKStreamHandler,
        keepalive: Optional[asyncio.Event],
        hook_builder: HookBuilder,
    ) -> RunResult:
        session_id = (task.session_id or "").strip()
        if not session_id:
            raise ValueError("Streaming session executor requires task.session_id")

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        req = _ReactiveStreamingRequest(
            worker=worker,
            runner=runner,
            run_config=run_config,
            task=task,
            bridge=bridge,
            persistence=persistence,
            pubsub=pubsub,
            sdk_stream_handler=sdk_stream_handler,
            keepalive=keepalive,
            hook_builder=hook_builder,
            future=future,
        )

        async with self._lock:
            actor = self._actors.get(session_id)
            if actor is None or actor.done:
                actor = self._create_actor(session_id)
                self._actors[session_id] = actor
                actor.start()

        return await actor.submit(req)

    def _create_actor(self, session_id: str) -> ReactiveSessionActor:
        """Create a ReactiveSessionActor for the given session."""
        return ReactiveSessionActor(
            session_id=session_id,
            idle_seconds=self._idle_seconds,
            on_exit=self._on_actor_exit,
        )

    async def stop(self, grace_seconds: float = 10.0) -> None:
        async with self._lock:
            actors = list(self._actors.values())
            session_ids = [
                getattr(actor, "session_id", "<unknown>") for actor in actors
            ]

        if not actors:
            logger.info(
                "SessionStreamingExecutorManager stop skipped: actor_count=0"
            )
            return

        logger.info(
            "SessionStreamingExecutorManager stop start: actor_count=%d "
            "grace_seconds=%.1f sessions=%s",
            len(actors),
            grace_seconds,
            session_ids,
        )
        for actor in actors:
            try:
                actor.request_stop(reason="manager.stop")
            except TypeError:
                actor.request_stop()

        await asyncio.gather(
            *(actor.wait_closed(timeout_seconds=grace_seconds) for actor in actors),
            return_exceptions=True,
        )
        logger.info(
            "SessionStreamingExecutorManager stop done: actor_count=%d",
            len(actors),
        )

    async def _on_actor_exit(
        self,
        session_id: str,
        actor: Any,
    ) -> None:
        async with self._lock:
            current = self._actors.get(session_id)
            if current is actor:
                self._actors.pop(session_id, None)


_manager: Optional[SessionStreamingExecutorManager] = None
_manager_lock = asyncio.Lock()


async def get_session_streaming_executor_manager() -> SessionStreamingExecutorManager:
    """Get or create global session streaming executor manager."""
    global _manager
    async with _manager_lock:
        if _manager is None:
            _manager = SessionStreamingExecutorManager(
                idle_seconds=settings.sdk_streaming_input_idle_seconds
            )
        return _manager


async def shutdown_session_streaming_executor_manager() -> None:
    """Stop and clear global session streaming executor manager."""
    global _manager
    async with _manager_lock:
        if _manager is not None:
            logger.info("Shutdown session streaming executor manager: start")
            await _manager.stop()
            _manager = None
            logger.info("Shutdown session streaming executor manager: done")
