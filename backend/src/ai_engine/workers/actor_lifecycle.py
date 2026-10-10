"""Session lifecycle operations for ReactiveSessionActor.

Heartbeat loop, signal listener, teardown, cleanup, and pubsub emission helpers.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import redis.asyncio as aioredis

from ...config.settings import settings
from ...core.pubsub.types import MessageType, PubSubMessage
from ...core.utils.timezone import utc_now
from ..intervention.types import (
    GenerationState,
    InterventionSignal,
    InterventionType,
    SessionStatus,
    session_signal_channel,
    session_status_key,
)

if TYPE_CHECKING:
    from .reactive_session_actor import ReactiveSessionActor

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_SECONDS: int = 10
_STATUS_TTL_SECONDS: int = 600

# Internal error patterns that must never reach the client.
_INTERNAL_ERROR_MARKERS = (
    "stream ended unexpectedly",
    "receive iterator not initialized",
    "cli_alive=",
    "cli_rc=",
    "query_closed=",
    "pending_len=",
    "Actor failed before request",
)


def _sanitize_error_for_client(raw: str) -> str:
    """Replace internal diagnostic errors with user-friendly messages.

    Raw details are already captured by logger.info in _emit_request_error;
    only a clean, actionable message should reach the WebSocket client.
    """
    lower = raw.lower()
    if "idle timed out" in lower or "timeout" in lower:
        return "请求超时，请稍后重试"
    if any(marker in raw for marker in _INTERNAL_ERROR_MARKERS):
        return "处理出错了，请重新发送"
    # Heuristic: long messages or those containing session UUIDs are internal
    if len(raw) > 120:
        return "后台处理失败，请重试"
    return raw


class ActorLifecycleMixin:
    """Mixin providing heartbeat, signal listener, teardown, and pubsub emission."""

    # ------------------------------------------------------------------
    # Signal listener (Redis PubSub -> _pending_interventions queue)
    # ------------------------------------------------------------------

    async def _start_signal_listener(self: "ReactiveSessionActor") -> None:
        try:
            self._signal_redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            self._signal_pubsub = self._signal_redis.pubsub()
            channel = session_signal_channel(self.session_id)
            await self._signal_pubsub.subscribe(channel)
            self._signal_listener_task = asyncio.create_task(
                self._signal_listen_loop(),
                name=f"signal-listener:{self.session_id}",
            )
            logger.info(
                "Signal listener started: channel=%s session=%s",
                channel,
                self.session_id,
            )
        except Exception:
            logger.warning(
                "Failed to start signal listener: session=%s",
                self.session_id,
                exc_info=True,
            )

    async def _signal_listen_loop(self: "ReactiveSessionActor") -> None:
        try:
            async for raw_msg in self._signal_pubsub.listen():
                if raw_msg["type"] != "message":
                    continue
                try:
                    signal = InterventionSignal.from_json(raw_msg["data"])
                except Exception:
                    logger.warning(
                        "Invalid signal JSON: session=%s",
                        self.session_id,
                        exc_info=True,
                    )
                    continue

                if not self._should_accept_signal(signal):
                    continue

                dispatched = await self._debouncer.submit(signal)
                if dispatched is not None:
                    await self._enqueue_signal(dispatched)

        except asyncio.CancelledError:
            return
        except Exception:
            logger.warning(
                "Signal listener error: session=%s",
                self.session_id,
                exc_info=True,
            )

    def _should_accept_signal(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> bool:
        """Check job_id match and signal_id dedup."""
        if self._current_job_id and signal.job_id != self._current_job_id:
            logger.debug(
                "Rejecting stale signal: signal_job=%s current_job=%s",
                signal.job_id,
                self._current_job_id,
            )
            return False
        if signal.signal_id in self._signal_dedup:
            return False
        self._signal_dedup.append(signal.signal_id)
        return True

    async def _enqueue_signal(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> None:
        """Put signal onto queue, evicting lowest-priority if full."""
        self._signal_sequence += 1
        entry = (signal.priority, self._signal_sequence, signal)

        if signal.type == InterventionType.CANCEL.value:
            if self._pending_interventions.full():
                self._evict_lowest_priority()
            try:
                self._pending_interventions.put_nowait(entry)
            except asyncio.QueueFull:
                logger.warning(
                    "Signal queue still full after eviction, forcing CANCEL"
                )
                self._evict_lowest_priority()
                self._pending_interventions.put_nowait(entry)
            return

        if self._pending_interventions.full():
            self._evict_lowest_priority()

        try:
            self._pending_interventions.put_nowait(entry)
        except asyncio.QueueFull:
            logger.warning(
                "Dropping signal (queue full): type=%s signal_id=%s",
                signal.type,
                signal.signal_id,
            )

    def _evict_lowest_priority(self: "ReactiveSessionActor") -> None:
        """Remove the lowest-priority (highest number) item from queue."""
        items: List[tuple] = []
        while not self._pending_interventions.empty():
            try:
                items.append(self._pending_interventions.get_nowait())
            except asyncio.QueueEmpty:
                break

        if not items:
            return

        items.sort(key=lambda entry: (entry[0], entry[1]))
        evicted = items.pop()
        evicted_signal = evicted[2]
        logger.debug(
            "Evicted signal: type=%s signal_id=%s priority=%d",
            evicted_signal.type,
            evicted_signal.signal_id,
            evicted_signal.priority,
        )
        for item in items:
            try:
                self._pending_interventions.put_nowait(item)
            except asyncio.QueueFull:
                break

    async def _stop_signal_listener(self: "ReactiveSessionActor") -> None:
        if self._signal_listener_task is not None:
            self._signal_listener_task.cancel()
            try:
                await self._signal_listener_task
            except (asyncio.CancelledError, Exception):
                pass
            self._signal_listener_task = None

        if self._signal_pubsub is not None:
            try:
                await self._signal_pubsub.unsubscribe()
                await self._signal_pubsub.close()
            except Exception:
                pass
            self._signal_pubsub = None

        if self._signal_redis is not None:
            try:
                await self._signal_redis.close()
            except Exception:
                pass
            self._signal_redis = None

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _set_state(
        self: "ReactiveSessionActor",
        new_state: GenerationState,
        *,
        _user_id: Optional[str] = None,
        _job_id: Optional[str] = None,
        _pubsub: Optional[Any] = None,
    ) -> None:
        old = self._generation_state
        if old == new_state:
            return
        self._generation_state = new_state
        logger.debug(
            "State transition: %s -> %s session=%s",
            old.value,
            new_state.value,
            self.session_id,
        )
        self._emit_state_change_nowait(
            new_state, user_id=_user_id, job_id=_job_id, pubsub=_pubsub
        )

    def _emit_state_change_nowait(
        self: "ReactiveSessionActor",
        state: GenerationState,
        *,
        user_id: Optional[str] = None,
        job_id: Optional[str] = None,
        pubsub: Optional[Any] = None,
    ) -> None:
        """Best-effort publish of state change via first pending request's pubsub."""
        # Use explicit params if provided, else fall back to _pending[0]
        if user_id is None or pubsub is None:
            if not self._pending:
                return
            req = self._pending[0]
            user_id = user_id or req.task.user_id
            job_id = job_id if job_id is not None else req.task.job_id
            pubsub = pubsub or req.pubsub
        msg = PubSubMessage(
            user_id=user_id,
            message_type=MessageType.GENERATION_STATE,
            payload={
                "state": state.value,
                "session_id": self.session_id,
                "job_id": self._current_job_id or job_id or "",
                "active_tool": self._active_tool,
            },
            trace_id=job_id or "",
            job_id=job_id,
        )
        asyncio.create_task(
            pubsub.publish(user_id, msg),
            name=f"state-change:{self.session_id}",
        )

    # ------------------------------------------------------------------
    # PubSub emission helpers
    # ------------------------------------------------------------------

    async def _emit_partial_content(
        self: "ReactiveSessionActor",
        generation_id: Optional[str] = None,
        interrupted_by: Optional[str] = None,
    ) -> None:
        """Emit PARTIAL_CONTENT event before interruption."""
        if not self._pending:
            return
        req = self._pending[0]
        partial_text = "".join(req.all_text)
        if not partial_text:
            return

        payload: Dict[str, Any] = {
            "content": partial_text,
            "session_id": self.session_id,
            "job_id": self._current_job_id or "",
            "is_partial": True,
        }
        if generation_id is not None:
            payload["generation_id"] = generation_id
        if interrupted_by is not None:
            payload["interrupted_by"] = interrupted_by

        msg = PubSubMessage(
            user_id=req.task.user_id,
            message_type=MessageType.PARTIAL_CONTENT,
            payload=payload,
            trace_id=req.task.job_id or "",
            job_id=req.task.job_id,
        )
        try:
            await req.pubsub.publish(req.task.user_id, msg)
        except Exception:
            logger.warning(
                "Failed to emit partial content: session=%s",
                self.session_id,
                exc_info=True,
            )

    async def _emit_bridging(
        self: "ReactiveSessionActor",
        signal_type: str,
        new_generation_id: str,
        continues_from: Optional[str] = None,
    ) -> None:
        """Emit BRIDGING event to signal transition between generations."""
        if not self._pending:
            return
        req = self._pending[0]
        payload: Dict[str, Any] = {
            "signal_type": signal_type,
            "new_generation_id": new_generation_id,
        }
        if continues_from is not None:
            payload["continues_from"] = continues_from
        msg = PubSubMessage(
            user_id=req.task.user_id,
            message_type=MessageType.BRIDGING,
            payload=payload,
            trace_id=req.task.job_id or "",
            job_id=req.task.job_id,
        )
        try:
            await req.pubsub.publish(req.task.user_id, msg)
        except Exception:
            logger.warning(
                "Failed to emit bridging event: session=%s",
                self.session_id,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Heartbeat loop
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self: "ReactiveSessionActor") -> None:
        """Publish session status every _HEARTBEAT_INTERVAL_SECONDS."""
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)
                await self._publish_heartbeat()
        except asyncio.CancelledError:
            return
        except Exception:
            logger.warning(
                "Heartbeat loop error: session=%s",
                self.session_id,
                exc_info=True,
            )

    async def _publish_heartbeat(self: "ReactiveSessionActor") -> None:
        """Write SessionStatus to Redis."""
        sdk_session_id = ""
        task_summary = ""
        user_id = ""
        if self._pending:
            req = self._pending[0]
            sdk_session_id = req.sdk_session_id or ""
            task_summary = (req.task.user_input or "")[:100]
            user_id = str(req.task.user_id) if req.task.user_id else ""

        status = SessionStatus(
            state=self._generation_state.value,
            job_id=self._current_job_id or "",
            worker_id=self._worker_id,
            sdk_session_id=sdk_session_id,
            last_heartbeat=utc_now().isoformat(),
            task_summary=task_summary,
            active_tool=self._active_tool,
            user_id=user_id,
        )

        try:
            redis = self._signal_redis
            if redis is None:
                return
            key = session_status_key(self.session_id)
            await redis.setex(key, _STATUS_TTL_SECONDS, status.to_json())
            if user_id:
                await redis.setex(
                    f"user:active_session:{user_id}",
                    _STATUS_TTL_SECONDS,
                    self.session_id,
                )
        except Exception:
            logger.debug(
                "Heartbeat publish failed: session=%s",
                self.session_id,
                exc_info=True,
            )

    async def _stop_heartbeat(self: "ReactiveSessionActor") -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except (asyncio.CancelledError, Exception):
                pass
            self._heartbeat_task = None

    # ------------------------------------------------------------------
    # Cleanup helpers
    # ------------------------------------------------------------------

    async def _cleanup_audit_tasks(self: "ReactiveSessionActor") -> None:
        """Wait for in-flight audit log tasks to finish cleanly."""
        if not self._audit_tasks:
            return
        # Give tasks a short grace period to finish naturally so asyncpg
        # connections are returned to the pool cleanly.  Only cancel if
        # they don't complete in time.
        tasks = list(self._audit_tasks)
        _done, pending = await asyncio.wait(tasks, timeout=3.0)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._audit_tasks.clear()

    async def _cleanup_reverse_index(self: "ReactiveSessionActor") -> None:
        """Remove the user:active_session reverse index on shutdown."""
        if not self._pending:
            return
        user_id = (
            str(self._pending[0].task.user_id)
            if self._pending[0].task.user_id
            else ""
        )
        if not user_id:
            return
        try:
            redis = self._signal_redis
            if redis is not None:
                await redis.delete(f"user:active_session:{user_id}")
        except Exception:
            pass

    async def _teardown_client(
        self: "ReactiveSessionActor", *, mark_disconnected: bool
    ) -> None:
        # Cancel any in-flight __anext__() task before closing the iterator
        # to prevent it from holding a reference to the closed generator.
        if self._pending_anext_task is not None:
            self._pending_anext_task.cancel()
            try:
                await self._pending_anext_task
            except (asyncio.CancelledError, Exception):
                pass
            self._pending_anext_task = None

        if self._receive_iter is not None:
            try:
                await self._receive_iter.aclose()
            except Exception:
                logger.warning(
                    "Error closing receive_iter during teardown: session=%s",
                    self.session_id,
                    exc_info=True,
                )
            self._receive_iter = None

        # Capture pool reference and clear actor state BEFORE disconnect.
        # This ensures cleanup state is set even if disconnect() raises
        # BaseException (e.g. CancelledError during task cancellation).
        # The finally block in _run() may call _teardown_client again,
        # but it will find self._pool=None and skip the disconnect.
        pool = self._pool
        self._pool = None
        self._pooled = None
        self._ctx = None
        self._options_hash = None

        if pool is not None and mark_disconnected:
            try:
                # Use disconnect_inline (not mark_disconnected) so that the
                # SDK's disconnect() runs in the SAME asyncio task that entered
                # its anyio cancel scope.  Spawning a background task for
                # disconnect causes "Attempted to exit cancel scope in a
                # different task" errors which leak CancelledError back here.
                await pool.disconnect_inline(self.session_id)
            except BaseException:
                logger.warning(
                    "Failed to disconnect session during teardown: session=%s",
                    self.session_id,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    async def _emit_request_error(
        self: "ReactiveSessionActor", request: Any, error: Exception
    ) -> None:
        raw = str(error)
        logger.info(
            "ReactiveSessionActor emit_request_error: session=%s job_id=%s "
            "error_type=%s error=%s",
            self.session_id,
            request.task.job_id,
            type(error).__name__,
            raw,
        )
        try:
            user_message = _sanitize_error_for_client(raw)
            await request.sdk_stream_handler.emit_error(user_message)
        except Exception:
            pass
        if not request.future.done():
            request.future.set_exception(error)

    async def _fail_all(
        self: "ReactiveSessionActor",
        error: Exception,
        *,
        mark_disconnected: bool = True,
    ) -> None:
        logger.warning(
            "ReactiveSessionActor fail_all: session=%s error_type=%s error=%s "
            "mark_disconnected=%s pending_len=%d queue_size=%d signal_queue=%d "
            "stop_requested=%s state=%s current_job=%s",
            self.session_id,
            type(error).__name__,
            error,
            mark_disconnected,
            len(self._pending),
            self._queue.qsize(),
            self._pending_interventions.qsize(),
            self._stop_requested,
            self._generation_state.value,
            self._current_job_id,
        )
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
        self._set_state(GenerationState.IDLE)
        await self._teardown_client(mark_disconnected=mark_disconnected)

    # ------------------------------------------------------------------
    # Audit log (best-effort, fire-and-forget)
    # ------------------------------------------------------------------

    async def _write_audit_log(
        self: "ReactiveSessionActor",
        signal: InterventionSignal,
        generation_state: str,
        action_taken: str,
        confidence: Optional[float] = None,
        latency_ms: Optional[int] = None,
    ) -> None:
        """Best-effort write to intervention_audit_log table."""
        try:
            from ...db.session import AsyncSessionLocal
            from ...modules.conversation.models import InterventionAuditLog

            async with AsyncSessionLocal() as session:
                log = InterventionAuditLog(
                    id=uuid.uuid4(),
                    session_id=uuid.UUID(signal.session_id),
                    signal_id=uuid.UUID(signal.signal_id),
                    signal_type=signal.type,
                    job_id=signal.job_id,
                    user_id=uuid.UUID(signal.user_id),
                    generation_state=generation_state,
                    action_taken=action_taken,
                    payload=signal.payload,
                    classification_confidence=confidence,
                    latency_ms=latency_ms,
                )
                session.add(log)
                await session.commit()
        except Exception:
            logger.debug(
                "Audit log write failed (non-fatal): signal_id=%s",
                signal.signal_id,
                exc_info=True,
            )

    async def _increment_generation_count(
        self: "ReactiveSessionActor",
    ) -> None:
        """Best-effort increment of generation_count on the chat session."""
        try:
            from sqlalchemy import text as sa_text

            from ...db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                await db.execute(
                    sa_text(
                        "UPDATE assistant_chat_sessions "
                        "SET generation_count = COALESCE(generation_count, 0) + 1 "
                        "WHERE id = :sid"
                    ),
                    {"sid": self.session_id},
                )
                await db.commit()
        except Exception:
            logger.debug(
                "generation_count increment failed (non-fatal): session=%s",
                self.session_id,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Context cache invalidation
    # ------------------------------------------------------------------

    async def _invalidate_ctx_cache(self: "ReactiveSessionActor") -> None:
        """Delete all context cache keys for this session using SCAN."""
        redis = self._signal_redis
        if redis is None:
            return
        cache_key_prefix = f"ctx_cache:{self.session_id}:"
        cursor = "0"
        while True:
            cursor, keys = await redis.scan(
                cursor=cursor, match=cache_key_prefix + "*", count=100
            )
            if keys:
                await redis.delete(*keys)
            if cursor == 0 or cursor == "0":
                break
