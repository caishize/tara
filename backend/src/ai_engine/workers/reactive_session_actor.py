"""
Reactive session actor with full-duplex intervention support.

Replaces ``_SessionStreamingActor`` with a three-way asyncio.wait loop
that adds an intervention signal channel alongside the existing request
queue and SDK message stream.

State machine: IDLE -> GENERATING -> TOOL_EXECUTING -> IDLE
               IDLE -> GENERATING -> WAITING_USER -> GENERATING -> IDLE

Signal priority:  CANCEL (1) > CORRECTION (1) > ADDITIVE (2) = CONFIRM (2)
                  > DIGRESSION (3) = SIDEKICK (3)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Deque, Dict, List, Optional, Set

import redis.asyncio as aioredis

from ...core.pubsub import RedisPubSubManager
from ..intervention.debouncer import InterventionDebouncer
from ..intervention.types import (
    GenerationState,
    InterventionBudget,
    InterventionSignal,
    StitchingContext,
)
from ..queue import TaskPayload
from ..sdk.agent_factory import AgentConfig
from ..sdk.agent_runner import AgentRunner, RunResult
from ..sdk.pooled_context import PooledToolContext
from ..sdk.sdk_client_pool import SDKClientPool, get_sdk_client_pool
from ..sdk.sdk_stream_handler import SDKStreamHandler
from ..sdk.tool_persistence import ToolPersistenceHandler
from .actor_buffers import ActorBuffersMixin
from .actor_lifecycle import ActorLifecycleMixin
from .actor_signal_handlers import ActorSignalHandlersMixin
from .actor_stitching import ActorStitchingMixin

try:
    from claude_agent_sdk import (
        AssistantMessage,
        HookMatcher,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
    )
except ImportError as _import_err:
    raise ImportError(
        "claude-agent-sdk is required. Install with: pip install claude-agent-sdk>=0.1.0"
    ) from _import_err

# The SDK does not export a dedicated ToolResultMessage type as of v0.1.x.
try:
    from claude_agent_sdk import ToolResultMessage as _ToolResultMessage  # type: ignore[attr-defined]
except ImportError:
    _ToolResultMessage = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (re-exported for backward compatibility with tests)
# ---------------------------------------------------------------------------
_HEARTBEAT_INTERVAL_SECONDS: int = 10
_STATUS_TTL_SECONDS: int = 600
_RESET_CONTEXT_TTL_SECONDS: int = 600
_SIGNAL_DEDUP_SIZE: int = 100
_MAX_INTERVENTION_QUEUE: int = 10
_STREAM_POLL_TIMEOUT_SECONDS: float = 0.05

_MAX_SIDEKICK_PER_SESSION: int = 3
_MAX_SIDEKICK_PER_TURN: int = 1
_MIN_SIDEKICK_INTERVAL_SECONDS: float = 60.0
_WORKER_ID: str = str(uuid.uuid4())[:8]

_SDK_EMPTY_CONTENT_SENTINELS: frozenset = frozenset({
    "(no content)",
    "(No content)",
    "",
})

HookBuilder = Callable[[Any, PooledToolContext, Any], Dict[str, List[HookMatcher]]]


@dataclass
class _StreamingRequest:
    """A queued job request with all dependencies needed for SDK execution."""

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
    correction_resubmitted: bool = False

    @property
    def options_hash(self) -> str:
        return f"{self.run_config.model or ''}:"


class ReactiveSessionActor(
    ActorLifecycleMixin,
    ActorStitchingMixin,
    ActorBuffersMixin,
    ActorSignalHandlersMixin,
):
    """Single-session actor with intervention-aware three-way event loop.

    Behavior is split across mixin classes for maintainability:
    - ActorLifecycleMixin: heartbeat, signal listener, teardown, pubsub emission
    - ActorStitchingMixin: stitching context, session reset, context compression
    - ActorBuffersMixin: signal buffer flushing
    - ActorSignalHandlersMixin: signal dispatch, per-type handlers, SDK operations
    """

    def __init__(
        self,
        session_id: str,
        idle_seconds: int,
        on_exit: Callable[[str, "ReactiveSessionActor"], Awaitable[None]],
    ) -> None:
        self.session_id = session_id
        self._idle_seconds = max(1, int(idle_seconds))
        self._on_exit = on_exit
        self._queue: asyncio.Queue[_StreamingRequest] = asyncio.Queue()
        self._pending: Deque[_StreamingRequest] = deque()
        self._task: Optional[asyncio.Task] = None
        self._closed = asyncio.Event()
        self._stop_requested = False

        # SDK client pool state
        self._pool: Optional[SDKClientPool] = None
        self._pooled: Any = None
        self._ctx: Optional[PooledToolContext] = None
        self._receive_iter: Any = None
        self._pending_anext_task: Optional[asyncio.Task] = None
        self._options_hash: Optional[str] = None

        # --- Intervention state ---
        self._generation_state = GenerationState.IDLE
        self._active_tool: Optional[str] = None
        self._pending_interventions: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=_MAX_INTERVENTION_QUEUE
        )
        self._signal_sequence: int = 0
        self._signal_dedup: Deque[str] = deque(maxlen=_SIGNAL_DEDUP_SIZE)
        self._debouncer = InterventionDebouncer(on_dispatch=self._enqueue_signal)
        self._deferred_intervention: Optional[InterventionSignal] = None
        self._buffered_additives: List[InterventionSignal] = []
        self._buffered_confirms: List[InterventionSignal] = []
        self._buffered_sidekicks: List[InterventionSignal] = []
        self._budget = InterventionBudget()
        self._intervention_count: int = 0
        self._correction_count: int = 0
        self._additive_this_turn: int = 0
        self._current_generation_id: Optional[str] = None

        # Actor-side sidekick rate limiting (defense-in-depth)
        self._sidekick_count_session: int = 0
        self._sidekick_count_turn: int = 0
        self._last_sidekick_time: Optional[float] = None

        # Stitching history for context compression
        self._stitch_history: List[StitchingContext] = []

        # Current job ID for stale-signal rejection
        self._current_job_id: Optional[str] = None

        # Tracked fire-and-forget tasks (audit logs, etc.)
        self._audit_tasks: Set[asyncio.Task] = set()

        # Redis signal subscription
        self._signal_redis: Optional[aioredis.Redis] = None
        self._signal_pubsub: Any = None
        self._signal_listener_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Observability-only query tracking (no business logic impact)
        self._obs_query_seq: int = 0
        self._obs_query_queue: Deque[Dict[str, Any]] = deque()

        # Idle-exit flag
        self._idle_exit: bool = False

        # Worker ID for heartbeat
        self._worker_id: str = _WORKER_ID

        # Last completed request context — used by _build_signal_request()
        # to construct synthetic _StreamingRequest entries for signal-initiated
        # SDK queries that occur when self._pending is empty.
        self._last_runner: Any = None
        self._last_run_config: Any = None
        self._last_hook_builder: Any = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def done(self) -> bool:
        return self._task is None or self._task.done()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(
            self._run(),
            name=f"reactive-session-actor:{self.session_id}",
        )

    async def submit(self, request: _StreamingRequest) -> RunResult:
        if self._stop_requested:
            raise RuntimeError(f"Session actor is stopping: {self.session_id}")
        await self._queue.put(request)
        return await request.future

    def request_stop(self, reason: str = "unspecified") -> None:
        logger.info(
            "ReactiveSessionActor request_stop: session=%s reason=%s "
            "already_stop=%s state=%s pending_len=%d queue_size=%d signal_queue=%d current_job=%s",
            self.session_id,
            reason,
            self._stop_requested,
            self._generation_state.value,
            len(self._pending),
            self._queue.qsize(),
            self._pending_interventions.qsize(),
            self._current_job_id,
        )
        self._stop_requested = True
        if self._task is not None and not self._task.done():
            logger.info(
                "ReactiveSessionActor cancelling task: session=%s task_name=%s",
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

    # ------------------------------------------------------------------
    # Core event loop (three-way: queue + SDK messages + signals)
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        logger.info(
            "ReactiveSessionActor started: session=%s", self.session_id
        )
        try:
            await self._start_signal_listener()
            self._heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(),
                name=f"heartbeat:{self.session_id}",
            )

            while True:
                if self._stop_requested and self._queue.empty() and not self._pending:
                    break

                if not self._pending:
                    should_continue = await self._run_idle_phase()
                    if should_continue is None:
                        break  # idle timeout
                    continue

                await self._run_active_phase()

        except asyncio.CancelledError:
            logger.warning(
                "ReactiveSessionActor run cancelled: session=%s stop_requested=%s "
                "state=%s pending_len=%d queue_size=%d signal_queue=%d current_job=%s",
                self.session_id,
                self._stop_requested,
                self._generation_state.value,
                len(self._pending),
                self._queue.qsize(),
                self._pending_interventions.qsize(),
                self._current_job_id,
            )
            await self._fail_all(
                RuntimeError("ReactiveSessionActor cancelled"),
                mark_disconnected=True,
            )
            raise
        finally:
            await self._stop_signal_listener()
            await self._stop_heartbeat()
            await self._cleanup_audit_tasks()
            await self._cleanup_reverse_index()
            await self._teardown_client(mark_disconnected=not self._idle_exit)
            self._closed.set()
            await self._on_exit(self.session_id, self)
            logger.info(
                "ReactiveSessionActor closed: session=%s", self.session_id
            )

    async def _run_idle_phase(self) -> Optional[bool]:
        """Phase 1: No pending SDK work -- wait for queue or signal.

        Returns True to continue the loop, or None for idle timeout exit.
        """
        queue_task = asyncio.create_task(self._queue.get())
        signal_task = asyncio.create_task(self._pending_interventions.get())
        done, pending_tasks = await asyncio.wait(
            {queue_task, signal_task},
            timeout=self._idle_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending_tasks:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        if signal_task in done:
            _, _, sig = signal_task.result()
            await self._dispatch_signal(sig)
            return True

        if queue_task in done:
            req = queue_task.result()
            try:
                await self._accept_request(req)
            except Exception as e:
                await self._emit_request_error(req, e)
                await self._fail_all(e)
            finally:
                self._queue.task_done()
            return True

        # Timeout: neither queue nor signal received
        if self._queue.empty():
            self._idle_exit = True
            return None
        return True

    async def _run_active_phase(self) -> None:
        """Phase 2: Three-way wait (queue + SDK messages + signals)."""
        queue_task = asyncio.create_task(self._queue.get())
        message_task = asyncio.create_task(self._next_message())
        signal_task = asyncio.create_task(self._pending_interventions.get())

        done, pending_tasks = await asyncio.wait(
            {queue_task, message_task, signal_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        failed = False

        # Priority: signal > message > queue
        if signal_task in done:
            try:
                signal_entry = signal_task.result()
                await self._dispatch_signal(signal_entry[2])
            except Exception:
                logger.debug(
                    "Signal task error (non-fatal): session=%s",
                    self.session_id,
                    exc_info=True,
                )

        if message_task in done:
            try:
                message = message_task.result()
            except Exception as e:
                await self._fail_all(e)
                failed = True
            else:
                await self._handle_message(message)
        elif signal_task in done or queue_task in done:
            # Give stream a short chance to avoid starving SDK
            try:
                message = await asyncio.wait_for(
                    message_task, timeout=_STREAM_POLL_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                await self._fail_all(e)
                failed = True
            else:
                await self._handle_message(message)

        # Skip queue processing if _fail_all already tore down the client.
        # Accepting a new request after failure would create a new CLI
        # process in an inconsistent actor state.
        if queue_task in done and not failed:
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
        elif queue_task in done:
            # Drain the queue item so task_done() is called, but don't
            # process it — re-enqueue so next actor incarnation picks it up.
            try:
                req = queue_task.result()
                await self._emit_request_error(
                    req,
                    RuntimeError("Actor failed before request could be processed"),
                )
            except Exception:
                pass
            finally:
                self._queue.task_done()

        for p in pending_tasks:
            p.cancel()
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)

    # ------------------------------------------------------------------
    # Request acceptance
    # ------------------------------------------------------------------

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
            self._activate_request(request)

        self._current_job_id = request.task.job_id
        self._current_generation_id = str(uuid.uuid4())
        self._set_state(GenerationState.GENERATING)
        _gen_task = asyncio.create_task(
            self._increment_generation_count(),
            name=f"gen-count:{self.session_id}",
        )
        self._audit_tasks.add(_gen_task)
        _gen_task.add_done_callback(self._audit_tasks.discard)

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

        aq_id = self._register_query_submit(
            source="user_request",
            prompt=prompt or "",
            owner_job_id=request.task.job_id or "",
        )
        try:
            await self._pooled.client.query(prompt)
            logger.info(
                "Streaming query submitted: session=%s job_id=%s pending=%d qid=%s cold_start=%s",
                self.session_id,
                request.task.job_id,
                len(self._pending),
                aq_id,
                was_cold_start,
            )
        except Exception as e:
            self._mark_query_submit_failed(aq_id, reason=type(e).__name__)
            failed_user_id = request.task.user_id
            failed_job_id = request.task.job_id
            failed_pubsub = request.pubsub
            try:
                self._pending.remove(request)
            except ValueError:
                pass
            if self._pending:
                self._activate_request(self._pending[0])
            else:
                self._set_state(
                    GenerationState.IDLE,
                    _user_id=failed_user_id,
                    _job_id=failed_job_id,
                    _pubsub=failed_pubsub,
                )
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
        self._pending_anext_task = None  # new iterator, discard stale task
        self._options_hash = request.options_hash
        logger.info(
            "ReactiveSessionActor connected pooled client: session=%s",
            self.session_id,
        )

    def _activate_request(self, request: _StreamingRequest) -> None:
        if self._ctx is None:
            return
        self._ctx.update(
            bridge=request.bridge,
            persistence=request.persistence,
            task=request.task,
            pubsub=request.pubsub,
            sdk_stream_handler=request.sdk_stream_handler,
            worker=request.worker,
        )
        self._ctx.keepalive = request.keepalive or asyncio.Event()

    # ------------------------------------------------------------------
    # Synthetic request for signal-initiated queries
    # ------------------------------------------------------------------

    def _build_signal_request(
        self, *, source: str = "signal"
    ) -> Optional[_StreamingRequest]:
        """Create a synthetic ``_StreamingRequest`` for signal-initiated queries.

        When a signal handler calls ``_query_sdk()`` while ``self._pending`` is
        empty, the SDK response is never consumed because ``_handle_message``
        drops messages when there is no head request.  This method constructs a
        lightweight request using the context preserved from the last completed
        user request so the existing streaming infrastructure works unchanged.

        Returns ``None`` if essential context is unavailable (no prior request
        has completed yet).
        """
        ctx = self._ctx
        if (
            ctx is None
            or ctx.worker is None
            or ctx.task is None
            or ctx.pubsub is None
            or self._last_runner is None
        ):
            logger.warning(
                "Cannot build signal request: missing context "
                "ctx=%s runner=%s session=%s",
                ctx is not None,
                self._last_runner is not None,
                self.session_id,
            )
            return None

        # Build a fresh SDKStreamHandler using the same publish function
        # factory the normal flow uses (_make_pubsub_publish_fn returns a
        # closure, not an SDKStreamHandler).
        publish_fn = ctx.worker._make_pubsub_publish_fn(ctx.pubsub, ctx.task)
        sdk_stream_handler = SDKStreamHandler(
            publish_fn=publish_fn,
            channel=f"agent:result:{ctx.task.job_id}",
            job_id=ctx.task.job_id,
        )

        # Mark the response as signal-sourced for client-side differentiation
        sdk_stream_handler.set_generation_context(
            generation_id=self._current_generation_id or str(uuid.uuid4()),
            signal_source=source,
            continues_from=None,
        )

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        # Suppress "Future exception was never retrieved" — no caller
        # awaits a synthetic request's future; _complete_request sets it
        # but the result is intentionally unused.
        future.add_done_callback(
            lambda f: f.exception() if not f.cancelled() else None
        )

        return _StreamingRequest(
            worker=ctx.worker,
            runner=self._last_runner,
            run_config=self._last_run_config,
            task=ctx.task,
            bridge=ctx.bridge,
            persistence=ctx.persistence,
            pubsub=ctx.pubsub,
            sdk_stream_handler=sdk_stream_handler,
            keepalive=ctx.keepalive,
            hook_builder=self._last_hook_builder,
            future=future,
        )

    # ------------------------------------------------------------------
    # SDK message handling
    # ------------------------------------------------------------------

    async def _next_message(self) -> Any:
        if self._receive_iter is None:
            raise RuntimeError(
                f"Session {self.session_id} receive iterator not initialized"
            )
        # Reuse or create the inner __anext__() task, then shield it so
        # that asyncio.wait_for() timeouts in _run_active_phase() cancel
        # only the outer await — not the inner task.  Without shielding,
        # CancelledError propagates into the async generator via athrow()
        # and finalises it, causing every subsequent __anext__() to raise
        # StopAsyncIteration (the "stream ended unexpectedly" bug).
        if self._pending_anext_task is None:
            self._pending_anext_task = asyncio.ensure_future(
                self._receive_iter.__anext__()
            )
        try:
            result = await asyncio.shield(self._pending_anext_task)
            self._pending_anext_task = None  # consumed successfully
            return result
        except asyncio.CancelledError:
            # The outer await was cancelled (e.g. wait_for timeout or
            # pending_tasks cleanup), but the inner task continues thanks
            # to shield().  Re-raise so the caller sees the cancellation.
            raise
        except StopAsyncIteration as e:
            self._pending_anext_task = None
            # Collect diagnostic info to help debug CLI exit reasons.
            cli_alive = False
            cli_returncode: Optional[int] = None
            query_closed = "unknown"
            in_pool = "unknown"
            try:
                client = getattr(self._pooled, "client", None)
                transport = getattr(client, "_transport", None)
                if transport is not None:
                    proc = getattr(transport, "_process", None)
                    if proc is not None:
                        cli_returncode = proc.returncode
                        cli_alive = cli_returncode is None
                # Check if the SDK Query was explicitly closed
                query = getattr(client, "_query", None)
                if query is not None:
                    query_closed = str(getattr(query, "_closed", "n/a"))
            except Exception:
                pass
            try:
                if self._pool is not None:
                    in_pool = str(self._pool.peek(self.session_id) is not None)
            except Exception:
                pass
            raise RuntimeError(
                f"Session {self.session_id} stream ended unexpectedly "
                f"(state={self._generation_state.value} "
                f"cli_alive={cli_alive} cli_rc={cli_returncode} "
                f"query_closed={query_closed} in_pool={in_pool} "
                f"pending_len={len(self._pending)})"
            ) from e

    async def _handle_message(self, message: Any) -> None:
        self._observe_stream_message(message)

        if not self._pending:
            head_qid = ""
            head_source = ""
            if self._obs_query_queue:
                head_qid = str(self._obs_query_queue[0].get("query_id", ""))
                head_source = str(self._obs_query_queue[0].get("source", ""))
            logger.info(
                "AQ drop_no_pending: session=%s msg_type=%s state=%s "
                "head_qid=%s head_source=%s queue_depth=%d",
                self.session_id,
                type(message).__name__,
                self._generation_state.value,
                head_qid,
                head_source,
                len(self._obs_query_queue),
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
            self._process_assistant_message(message, req)
            return

        if not isinstance(message, ResultMessage):
            await self._process_non_result_message(message)
            return

        # ResultMessage: generation turn complete
        await self._complete_request(message, req)

    def _process_assistant_message(
        self, message: AssistantMessage, req: _StreamingRequest
    ) -> None:
        """Track state changes from an AssistantMessage."""
        for block in message.content:
            if isinstance(block, TextBlock):
                if block.text and block.text.strip() not in _SDK_EMPTY_CONTENT_SENTINELS:
                    req.all_text.append(block.text)
            elif isinstance(block, ToolUseBlock):
                req.all_tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
                self._active_tool = block.name
                if block.name in ("ask_user_question", "AskUserQuestion"):
                    self._set_state(GenerationState.WAITING_USER)
                else:
                    self._set_state(GenerationState.TOOL_EXECUTING)

    async def _process_non_result_message(self, message: Any) -> None:
        """Handle tool result messages (non-ResultMessage, non-AssistantMessage)."""
        is_tool_result = (
            (_ToolResultMessage is not None and isinstance(message, _ToolResultMessage))
            or "ToolResult" in type(message).__name__
        )
        if is_tool_result:
            self._set_state(GenerationState.GENERATING)
            self._active_tool = None
            await self._handle_deferred_intervention()

    async def _complete_request(
        self, message: Any, req: _StreamingRequest
    ) -> None:
        """Handle a ResultMessage completing the current generation turn."""
        req.stop_reason = message.subtype
        req.turns_used = getattr(message, "num_turns", 0)
        req.total_cost_usd = getattr(message, "total_cost_usd", None)
        req.usage = getattr(message, "usage", None)
        req.sdk_session_id = getattr(message, "session_id", None)

        # If a CORRECTION was submitted, the first ResultMessage is for the
        # interrupted generation (error).  Keep the request alive so the
        # correction's response streams into the same request / future.
        if req.correction_resubmitted:
            req.correction_resubmitted = False
            req.all_text = []
            req.all_tool_calls = []
            req.stop_reason = None
            req.msg_count = 0
            req.sdk_stream_handler.reset()
            self._set_state(GenerationState.GENERATING)
            logger.info(
                "Correction resubmit: absorbed interrupted ResultMessage, "
                "keeping request alive: session=%s job=%s",
                self.session_id,
                req.task.job_id,
            )
            return

        try:
            await req.sdk_stream_handler.emit_missing_thinking()
        except Exception as e:
            await self._emit_request_error(req, e)
            failed_req = self._pending[0]
            self._pending.popleft()
            if self._pending:
                self._activate_request(self._pending[0])
            else:
                self._set_state(
                    GenerationState.IDLE,
                    _user_id=failed_req.task.user_id,
                    _job_id=failed_req.task.job_id,
                    _pubsub=failed_req.pubsub,
                )
            return

        try:
            req.sdk_stream_handler.set_generation_context(
                generation_id="",
                signal_source=None,
                continues_from=None,
            )
        except Exception:
            pass

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

        # Preserve request context for signal-initiated synthetic requests
        self._last_runner = req.runner
        self._last_run_config = req.run_config
        self._last_hook_builder = req.hook_builder

        completed_req = self._pending[0]
        self._pending.popleft()
        if self._pool is not None:
            await self._pool.mark_used(self.session_id)

        if self._pending:
            self._activate_request(self._pending[0])
            self._set_state(GenerationState.GENERATING)
        else:
            self._set_state(
                GenerationState.IDLE,
                _user_id=completed_req.task.user_id,
                _job_id=completed_req.task.job_id,
                _pubsub=completed_req.pubsub,
            )
            self._additive_this_turn = 0
            self._sidekick_count_turn = 0
            await self._flush_all_buffered()

    # ------------------------------------------------------------------
    # Observability tracking (no business logic impact)
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_prompt_tag(prompt: str) -> str:
        text = (prompt or "").lstrip()
        if text.startswith("[SYSTEM_INSIGHT]"):
            return "SYSTEM_INSIGHT"
        if text.startswith("[USER_CONFIRMATION]"):
            return "USER_CONFIRMATION"
        if text.startswith("[SUPPLEMENTARY_INFO]"):
            return "SUPPLEMENTARY_INFO"
        return "plain"

    def _next_obs_query_id(self) -> str:
        self._obs_query_seq += 1
        return f"{self.session_id[:8]}-{self._obs_query_seq}"

    def _pending_head_job_id(self) -> str:
        if not self._pending:
            return ""
        return self._pending[0].task.job_id or ""

    def _register_query_submit(
        self,
        *,
        source: str,
        prompt: str,
        owner_job_id: str,
    ) -> str:
        qid = self._next_obs_query_id()
        now = time.monotonic()
        meta = {
            "query_id": qid,
            "source": source,
            "owner_job_id": owner_job_id,
            "submitted_at": now,
            "prompt_len": len(prompt or ""),
            "prompt_tag": self._classify_prompt_tag(prompt),
            "first_msg_seen": False,
            "state_at_submit": self._generation_state.value,
        }
        self._obs_query_queue.append(meta)
        logger.info(
            "AQ submit: qid=%s source=%s session=%s state=%s pending_len=%d "
            "pending_head_job=%s owner_job=%s prompt_len=%d prompt_tag=%s",
            qid,
            source,
            self.session_id,
            self._generation_state.value,
            len(self._pending),
            self._pending_head_job_id(),
            owner_job_id,
            meta["prompt_len"],
            meta["prompt_tag"],
        )
        return qid

    def _mark_query_submit_failed(
        self,
        query_id: str,
        *,
        reason: str,
    ) -> None:
        for idx in range(len(self._obs_query_queue) - 1, -1, -1):
            item = self._obs_query_queue[idx]
            if item.get("query_id") != query_id:
                continue
            del self._obs_query_queue[idx]
            logger.info(
                "AQ submit_failed: qid=%s source=%s session=%s reason=%s queue_depth=%d",
                query_id,
                item.get("source", ""),
                self.session_id,
                reason,
                len(self._obs_query_queue),
            )
            return
        logger.info(
            "AQ submit_failed_missing: qid=%s session=%s reason=%s queue_depth=%d",
            query_id,
            self.session_id,
            reason,
            len(self._obs_query_queue),
        )

    def _observe_stream_message(self, message: Any) -> None:
        msg_type = type(message).__name__
        if not self._obs_query_queue:
            logger.info(
                "AQ stream_no_query: session=%s msg_type=%s state=%s pending_len=%d "
                "pending_head_job=%s",
                self.session_id,
                msg_type,
                self._generation_state.value,
                len(self._pending),
                self._pending_head_job_id(),
            )
            return

        head = self._obs_query_queue[0]
        submitted_at = float(head.get("submitted_at", time.monotonic()))
        delta_ms = (time.monotonic() - submitted_at) * 1000
        qid = str(head.get("query_id", ""))
        source = str(head.get("source", ""))
        owner_job = str(head.get("owner_job_id", ""))

        if not head.get("first_msg_seen", False):
            head["first_msg_seen"] = True
            logger.info(
                "AQ first_msg: qid=%s source=%s session=%s owner_job=%s msg_type=%s "
                "first_msg_ms=%.0f pending_head_job=%s pending_len=%d state=%s",
                qid,
                source,
                self.session_id,
                owner_job,
                msg_type,
                delta_ms,
                self._pending_head_job_id(),
                len(self._pending),
                self._generation_state.value,
            )

        if isinstance(message, ResultMessage):
            logger.info(
                "AQ result: qid=%s source=%s session=%s owner_job=%s total_ms=%.0f "
                "pending_head_job=%s pending_len=%d state=%s",
                qid,
                source,
                self.session_id,
                owner_job,
                delta_ms,
                self._pending_head_job_id(),
                len(self._pending),
                self._generation_state.value,
            )
            self._obs_query_queue.popleft()
