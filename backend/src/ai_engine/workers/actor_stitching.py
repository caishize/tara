"""Stitching context and session reset operations for ReactiveSessionActor.

Manages breakpoint snapshots (StitchingContext) saved to Redis for crash recovery
and context continuity across interruptions. Also handles session reset when the
intervention budget is exceeded, and proactive context compression.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ...core.pubsub.types import MessageType, PubSubMessage
from ...core.utils.timezone import utc_now
from ..intervention.types import (
    GenerationState,
    StitchingContext,
    _STITCH_PARTIAL_TEXT_MAX_CHARS,
    STITCH_TTL_SECONDS,
    session_stitch_key,
)
from ..sdk.agent_runner import RunResult

if TYPE_CHECKING:
    from .reactive_session_actor import _StreamingRequest, ReactiveSessionActor

logger = logging.getLogger(__name__)

_RESET_CONTEXT_TTL_SECONDS: int = 600


class ActorStitchingMixin:
    """Mixin providing stitching context persistence and session reset."""

    # ------------------------------------------------------------------
    # Stitching context creation (single canonical builder)
    # ------------------------------------------------------------------

    def _create_stitching_context(
        self: "ReactiveSessionActor", reason: str
    ) -> Optional[StitchingContext]:
        """Create a StitchingContext in-memory from current state.

        Also appends to ``_stitch_history`` for context compression.
        The caller is responsible for persisting to Redis separately.
        """
        if not self._pending:
            return None

        req = self._pending[0]
        partial_text = "".join(req.all_text)
        thinking = ""
        if hasattr(req.sdk_stream_handler, "final_thinking"):
            thinking = req.sdk_stream_handler.final_thinking

        completed_tools = [tc.get("name", "") for tc in req.all_tool_calls]

        stitch = StitchingContext(
            partial_text=partial_text,
            partial_thinking=thinking,
            interrupted_at=utc_now(),
            reason=reason,
            original_input=req.task.user_input,
            completed_tools=completed_tools,
            partial_tool=(
                self._build_partial_tool_info(req)
                if self._active_tool
                else None
            ),
        )
        self._stitch_history.append(stitch)
        return stitch

    def _build_partial_tool_info(
        self: "ReactiveSessionActor", req: "_StreamingRequest"
    ) -> Dict[str, Any]:
        """Build partial_tool dict with name and input from last tool call."""
        info: Dict[str, Any] = {"name": self._active_tool}
        if req.all_tool_calls:
            last_call = req.all_tool_calls[-1]
            if last_call.get("name") == self._active_tool and "input" in last_call:
                info["input"] = last_call["input"]
        return info

    # ------------------------------------------------------------------
    # Redis persistence (unified save method)
    # ------------------------------------------------------------------

    async def _persist_stitch_to_redis(
        self: "ReactiveSessionActor", stitch: StitchingContext
    ) -> None:
        """Save a StitchingContext to Redis for crash recovery."""
        try:
            redis = self._signal_redis
            if redis is None:
                return
            key = session_stitch_key(self.session_id)
            await redis.setex(key, STITCH_TTL_SECONDS, stitch.to_json())
        except Exception:
            logger.warning(
                "Failed to save stitching context: session=%s",
                self.session_id,
                exc_info=True,
            )

    # Keep legacy names as aliases for backward compatibility
    async def _save_stitching_context_direct(
        self: "ReactiveSessionActor", stitch: StitchingContext
    ) -> None:
        await self._persist_stitch_to_redis(stitch)

    async def _save_stitching_context_from_obj(
        self: "ReactiveSessionActor", stitch: StitchingContext
    ) -> None:
        await self._persist_stitch_to_redis(stitch)

    async def _save_stitching_context(
        self: "ReactiveSessionActor",
        signal: Any,
        reason: str,
    ) -> None:
        """Create and persist stitching context in one call."""
        stitch = self._create_stitching_context(reason)
        if stitch is not None:
            await self._persist_stitch_to_redis(stitch)

    async def _load_stitching_context(
        self: "ReactiveSessionActor",
    ) -> Optional[StitchingContext]:
        """Load and consume stitching context from Redis."""
        try:
            redis = self._signal_redis
            if redis is None:
                return None
            key = session_stitch_key(self.session_id)
            raw = await redis.get(key)
            if raw:
                await redis.delete(key)
                return StitchingContext.from_json(raw)
        except Exception:
            logger.warning(
                "Failed to load stitching context: session=%s",
                self.session_id,
                exc_info=True,
            )
        return None

    # ------------------------------------------------------------------
    # Reset summary
    # ------------------------------------------------------------------

    def _build_reset_summary(self: "ReactiveSessionActor") -> str:
        """Build a compressed context summary from pending request and stitch history."""
        summary_parts: List[str] = []

        if self._pending:
            req = self._pending[0]
            if req.task.user_input:
                summary_parts.append(
                    f"最近的用户请求: {req.task.user_input[:200]}"
                )
            accumulated_text = "".join(req.all_text)
            if accumulated_text:
                summary_parts.append(
                    f"已生成的回复片段: {accumulated_text[-300:]}"
                )

        if self._stitch_history:
            parts: List[str] = []
            all_tools: List[str] = []
            for stitch in self._stitch_history:
                if stitch.partial_text:
                    parts.append(stitch.partial_text[-100:])
                all_tools.extend(stitch.completed_tools)
            if parts:
                summary_parts.append("Previous context: " + " ... ".join(parts))
            if all_tools:
                unique_tools = list(dict.fromkeys(all_tools))
                summary_parts.append("Tools completed: " + ", ".join(unique_tools))

        return "\n\n".join(summary_parts) if summary_parts else ""

    async def _check_reset_context(
        self: "ReactiveSessionActor",
    ) -> Optional[str]:
        """Check for a stored reset context summary, consuming the key."""
        try:
            redis = self._signal_redis
            if redis is None:
                return None
            reset_key = f"session:reset:{self.session_id}"
            raw = await redis.get(reset_key)
            if raw:
                await redis.delete(reset_key)
                return raw
        except Exception:
            logger.warning(
                "Failed to check reset context: session=%s",
                self.session_id,
                exc_info=True,
            )
        return None

    # ------------------------------------------------------------------
    # Session reset (budget exceeded)
    # ------------------------------------------------------------------

    async def _reset_session(self: "ReactiveSessionActor") -> None:
        """Reset session state when intervention budget is exceeded."""
        if self._pending:
            req = self._pending[0]
            stitch = StitchingContext(
                partial_text="".join(req.all_text)[-_STITCH_PARTIAL_TEXT_MAX_CHARS:],
                partial_thinking="",
                interrupted_at=utc_now(),
                reason="budget_exceeded",
                original_input=req.task.user_input or "",
                completed_tools=[tc.get("name", "") for tc in req.all_tool_calls],
                partial_tool=None,
            )
            await self._persist_stitch_to_redis(stitch)

        await self._interrupt_sdk()

        summary = self._build_reset_summary()
        if summary:
            try:
                redis = self._signal_redis
                if redis is not None:
                    reset_key = f"session:reset:{self.session_id}"
                    await redis.setex(
                        reset_key, _RESET_CONTEXT_TTL_SECONDS, summary
                    )
            except Exception:
                logger.warning(
                    "Failed to store reset context summary: session=%s",
                    self.session_id,
                    exc_info=True,
                )

        self._reset_intervention_counters()

        last_user_id = None
        last_job_id = None
        last_pubsub = None
        if self._pending:
            req = self._pending[0]
            last_user_id = req.task.user_id
            last_job_id = req.task.job_id
            last_pubsub = req.pubsub
            msg = PubSubMessage(
                user_id=req.task.user_id,
                message_type=MessageType.COMPLETE,
                payload={
                    "content": "",
                    "is_final": True,
                    "session_reset": True,
                    "reason": "intervention_budget_exceeded",
                    "session_id": self.session_id,
                },
                trace_id=req.task.job_id or "",
                job_id=req.task.job_id,
            )
            try:
                await req.pubsub.publish(req.task.user_id, msg)
            except Exception:
                logger.warning("Failed to emit session reset", exc_info=True)

            result = RunResult(
                text="".join(req.all_text),
                tool_calls=req.all_tool_calls,
                stop_reason="session_reset",
                turns_used=req.turns_used,
                total_cost_usd=req.total_cost_usd,
                usage=req.usage,
                session_id=req.sdk_session_id,
            )
            if not req.future.done():
                req.future.set_result(result)
            self._pending.popleft()

        await self._teardown_client(mark_disconnected=True)
        self._set_state(
            GenerationState.IDLE,
            _user_id=last_user_id,
            _job_id=last_job_id,
            _pubsub=last_pubsub,
        )

    def _reset_intervention_counters(self: "ReactiveSessionActor") -> None:
        """Reset all intervention-related counters and buffers."""
        self._intervention_count = 0
        self._correction_count = 0
        self._additive_this_turn = 0
        self._stitch_history.clear()
        self._buffered_confirms.clear()
        self._buffered_sidekicks.clear()
        self._buffered_additives.clear()
        self._sidekick_count_session = 0
        self._sidekick_count_turn = 0
        self._last_sidekick_time = None

    # ------------------------------------------------------------------
    # Context compression
    # ------------------------------------------------------------------

    async def _compress_context_if_needed(
        self: "ReactiveSessionActor",
    ) -> None:
        """Proactively compress context when intervention threshold is reached."""
        try:
            summary = self._build_reset_summary()
            if summary:
                redis = self._signal_redis
                if redis is not None:
                    compressed_key = f"session:compressed:{self.session_id}"
                    await redis.setex(
                        compressed_key, _RESET_CONTEXT_TTL_SECONDS, summary
                    )
                    logger.info(
                        "Context compressed after threshold: session=%s summary_len=%d",
                        self.session_id,
                        len(summary),
                    )
            await self._invalidate_ctx_cache()
        except Exception:
            logger.warning(
                "Failed to compress context: session=%s",
                self.session_id,
                exc_info=True,
            )
