"""Signal handler implementations for ReactiveSessionActor.

Each handler method corresponds to one InterventionType and implements the
state x type operation matrix described in the architecture docs.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ...core.pubsub.types import MessageType, PubSubMessage
from ...core.utils.timezone import utc_now
from ..intervention.types import (
    GenerationState,
    InterventionSignal,
    InterventionType,
    NON_INTERRUPTIBLE_TOOLS,
    StitchingContext,
    _STITCH_PARTIAL_TEXT_MAX_CHARS,
)
from ..queue import TaskPayload
from ..sdk.agent_runner import RunResult
from .actor_buffers import build_confirm_prompt

if TYPE_CHECKING:
    from .reactive_session_actor import _StreamingRequest, ReactiveSessionActor

logger = logging.getLogger(__name__)

# Actor-side sidekick rate limits (defense-in-depth)
_MAX_SIDEKICK_PER_SESSION: int = 3
_MAX_SIDEKICK_PER_TURN: int = 1
_MIN_SIDEKICK_INTERVAL_SECONDS: float = 60.0


class ActorSignalHandlersMixin:
    """Mixin providing signal dispatch and per-type handler implementations."""

    # ------------------------------------------------------------------
    # Signal dispatch (state x type operation matrix)
    # ------------------------------------------------------------------

    async def _dispatch_signal(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> None:
        """Route signal to the appropriate handler based on current state."""
        state = self._generation_state
        sig_type = signal.type

        logger.info(
            "Dispatching signal: type=%s state=%s session=%s job=%s",
            sig_type,
            state.value,
            self.session_id,
            signal.job_id,
        )

        # CANCEL always executes regardless of budget
        if sig_type == InterventionType.CANCEL.value:
            try:
                await self._do_cancel(signal)
            except Exception:
                logger.warning(
                    "Signal handler error: type=%s session=%s",
                    sig_type,
                    self.session_id,
                    exc_info=True,
                )
            self._fire_audit(signal, state.value, "cancelled")
            return

        # Budget check
        if (
            self._intervention_count >= self._budget.max_interventions_per_session
            or self._correction_count >= self._budget.max_correction_per_session
        ):
            logger.warning(
                "Budget exceeded, rejecting %s: interventions=%d corrections=%d session=%s",
                sig_type,
                self._intervention_count,
                self._correction_count,
                self.session_id,
            )
            await self._reset_session()
            return

        self._intervention_count += 1
        if sig_type == InterventionType.CORRECTION.value:
            self._correction_count += 1

        # Dispatch by type
        handler = {
            InterventionType.CORRECTION.value: self._do_correction,
            InterventionType.ADDITIVE.value: self._do_additive,
            InterventionType.CONFIRM.value: self._do_confirm,
            InterventionType.DIGRESSION.value: self._do_digression,
            InterventionType.SIDEKICK_INSIGHT.value: self._do_sidekick,
        }.get(sig_type)

        if handler is None:
            logger.warning(
                "Unknown signal type: %s session=%s", sig_type, self.session_id
            )
            return

        try:
            action = await handler(signal)
        except Exception:
            logger.warning(
                "Signal handler error: type=%s session=%s",
                sig_type,
                self.session_id,
                exc_info=True,
            )
            return

        logger.info(
            "AQ signal_action: session=%s signal_id=%s type=%s prev_state=%s "
            "action=%s pending_len=%d pending_head_job=%s",
            self.session_id,
            signal.signal_id,
            sig_type,
            state.value,
            action,
            len(self._pending),
            self._pending_head_job_id(),
        )

        # Context compression threshold check
        if self._intervention_count == self._budget.context_compression_threshold:
            logger.info(
                "Intervention compression threshold reached (%d), triggering context compression: session=%s",
                self._budget.context_compression_threshold,
                self.session_id,
            )
            asyncio.create_task(self._compress_context_if_needed())

        # Invalidate context cache after direction-changing interventions
        if sig_type in (
            InterventionType.CORRECTION.value,
            InterventionType.CANCEL.value,
            InterventionType.DIGRESSION.value,
        ):
            try:
                await self._invalidate_ctx_cache()
            except Exception:
                logger.warning(
                    "Failed to invalidate context cache after intervention: session=%s",
                    self.session_id,
                    exc_info=True,
                )

        self._fire_audit(signal, state.value, action or "dispatched")

    def _fire_audit(
        self: "ReactiveSessionActor",
        signal: InterventionSignal,
        generation_state: str,
        action: str,
    ) -> None:
        """Fire-and-forget audit log write."""
        audit_task = asyncio.create_task(
            self._write_audit_log(signal, generation_state, action),
            name=f"audit:{signal.signal_id[:8]}",
        )
        self._audit_tasks.add(audit_task)
        audit_task.add_done_callback(self._audit_tasks.discard)

    # ------------------------------------------------------------------
    # Shared helper: generation rotation
    # ------------------------------------------------------------------

    async def _rotate_generation(
        self: "ReactiveSessionActor",
        signal_source: str,
        continues_from: Optional[str] = None,
    ) -> str:
        """Create a new generation ID, emit bridging event, and update stream handler.

        Returns the new generation_id.
        """
        old_generation_id = continues_from or self._current_generation_id
        new_generation_id = str(uuid.uuid4())
        self._current_generation_id = new_generation_id

        asyncio.create_task(
            self._increment_generation_count(),
            name=f"gen-count:{self.session_id}",
        )
        await self._emit_bridging(
            signal_source, new_generation_id, continues_from=old_generation_id
        )

        if self._pending:
            handler = self._pending[0].sdk_stream_handler
            if handler:
                handler.set_generation_context(
                    generation_id=new_generation_id,
                    signal_source=signal_source,
                    continues_from=old_generation_id,
                )

        return new_generation_id

    # ------------------------------------------------------------------
    # SDK operation helpers
    # ------------------------------------------------------------------

    async def _query_sdk(
        self: "ReactiveSessionActor",
        prompt: str,
        *,
        source: str = "internal_unknown",
        change_state: bool = True,
    ) -> None:
        """Send a query to the SDK client.

        Args:
            prompt: The message to send.
            source: Observability tag for logging.
            change_state: If True (default), transition to GENERATING before
                sending.  Set to False for supplementary injects during
                TOOL_EXECUTING — the CLI merges the message into the current
                turn, so the actor state should remain unchanged until the
                CLI's own response triggers the next state transition.
        """
        if self._pooled is None:
            logger.warning(
                "Cannot query SDK: no pooled client session=%s",
                self.session_id,
            )
            return

        # When _pending is empty, signal-initiated queries need a synthetic
        # request so _handle_message can route SDK responses correctly.
        synthetic_created = False
        if not self._pending and change_state:
            synthetic_req = self._build_signal_request(source=source)
            if synthetic_req is None:
                logger.warning(
                    "Cannot create synthetic request for signal query: "
                    "source=%s session=%s",
                    source,
                    self.session_id,
                )
                return
            self._pending.append(synthetic_req)
            self._activate_request(synthetic_req)
            synthetic_created = True

        prev_state = self._generation_state
        owner_job_id = self._pending_head_job_id()
        aq_id = self._register_query_submit(
            source=source,
            prompt=prompt or "",
            owner_job_id=owner_job_id,
        )
        try:
            if change_state:
                self._set_state(GenerationState.GENERATING)
            await self._pooled.client.query(prompt)
            logger.info(
                "AQ internal_query_submitted: qid=%s source=%s session=%s owner_job=%s "
                "state_before=%s pending_len=%d pending_head_job=%s synthetic=%s",
                aq_id,
                source,
                self.session_id,
                owner_job_id,
                prev_state.value,
                len(self._pending),
                self._pending_head_job_id(),
                synthetic_created,
            )
        except Exception:
            self._mark_query_submit_failed(aq_id, reason="query_exception")
            if synthetic_created and self._pending:
                self._pending.pop()
            if change_state:
                self._set_state(prev_state)
            logger.warning(
                "_query_sdk failed, reverted state to %s: session=%s synthetic=%s",
                prev_state,
                self.session_id,
                synthetic_created,
                exc_info=True,
            )

    async def _interrupt_sdk(self: "ReactiveSessionActor") -> None:
        """Interrupt the current SDK generation."""
        if self._pooled is None:
            return
        try:
            await self._pooled.client.interrupt()
            logger.info(
                "SDK interrupted: session=%s", self.session_id
            )
        except Exception:
            logger.warning(
                "SDK interrupt failed: session=%s",
                self.session_id,
                exc_info=True,
            )

    def _is_non_interruptible(self: "ReactiveSessionActor") -> bool:
        """Check if the currently active tool is non-interruptible."""
        return (
            self._active_tool is not None
            and self._active_tool in NON_INTERRUPTIBLE_TOOLS
        )

    # ------------------------------------------------------------------
    # Deferred intervention
    # ------------------------------------------------------------------

    def _defer_intervention(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> None:
        """Defer an intervention with priority-based comparison."""
        existing = self._deferred_intervention
        if existing is None:
            self._deferred_intervention = signal
            return

        # CANCEL always wins
        if signal.type == InterventionType.CANCEL.value:
            logger.info(
                "CANCEL overwriting deferred %s: session=%s",
                existing.type,
                self.session_id,
            )
            self._deferred_intervention = signal
            return

        if existing.type == InterventionType.CANCEL.value:
            logger.info(
                "Dropping deferred %s: existing CANCEL takes precedence: session=%s",
                signal.type,
                self.session_id,
            )
            return

        if signal.priority <= existing.priority:
            if signal.priority < existing.priority:
                logger.info(
                    "Higher-priority %s (p=%d) overwriting deferred %s (p=%d): session=%s",
                    signal.type,
                    signal.priority,
                    existing.type,
                    existing.priority,
                    self.session_id,
                )
            self._deferred_intervention = signal
        else:
            logger.info(
                "Dropping lower-priority %s (p=%d): deferred %s (p=%d) kept: session=%s",
                signal.type,
                signal.priority,
                existing.type,
                existing.priority,
                self.session_id,
            )

    async def _handle_deferred_intervention(
        self: "ReactiveSessionActor",
    ) -> None:
        """Process a deferred intervention after tool completion."""
        deferred = self._deferred_intervention
        if deferred is None:
            return
        self._deferred_intervention = None

        if (
            self._intervention_count >= self._budget.max_interventions_per_session
            or self._correction_count >= self._budget.max_correction_per_session
        ):
            self._intervention_count = max(0, self._intervention_count - 1)
            if deferred.type == InterventionType.CORRECTION.value:
                self._correction_count = max(0, self._correction_count - 1)
            logger.info(
                "Deferred intervention dropped: budget exceeded during deferral"
            )
            return

        handler = {
            InterventionType.CANCEL.value: self._do_cancel,
            InterventionType.CORRECTION.value: self._do_correction,
            InterventionType.ADDITIVE.value: self._do_additive,
            InterventionType.CONFIRM.value: self._do_confirm,
            InterventionType.DIGRESSION.value: self._do_digression,
            InterventionType.SIDEKICK_INSIGHT.value: self._do_sidekick,
        }.get(deferred.type)

        if handler:
            logger.info(
                "Executing deferred intervention: type=%s session=%s",
                deferred.type,
                self.session_id,
            )
            try:
                await handler(deferred)
            except Exception:
                logger.error(
                    "Failed to execute deferred intervention: type=%s session=%s",
                    deferred.type,
                    self.session_id,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # CORRECTION
    # ------------------------------------------------------------------

    async def _do_correction(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> str:
        state = self._generation_state
        correction_text = self._extract_signal_text(signal)

        if state == GenerationState.IDLE:
            self._current_generation_id = str(uuid.uuid4())
            asyncio.create_task(
                self._increment_generation_count(),
                name=f"gen-count:{self.session_id}",
            )
            await self._query_sdk(
                correction_text,
                source="signal_correction_idle",
            )
            return "query"

        if state == GenerationState.TOOL_EXECUTING and self._is_non_interruptible():
            self._defer_intervention(signal)
            logger.info(
                "Deferring CORRECTION during non-interruptible tool: %s",
                self._active_tool,
            )
            return "deferred"

        if state == GenerationState.WAITING_USER:
            if self._pending:
                self._pending[0].correction_resubmitted = True
            await self._interrupt_sdk()
            self._set_state(GenerationState.IDLE)
            stitch = self._create_stitching_context(reason="correction")
            if stitch:
                asyncio.create_task(self._save_stitching_context_from_obj(stitch))
            await self._emit_partial_content(
                generation_id=self._current_generation_id,
                interrupted_by="correction",
            )
            await self._rotate_generation("correction")
            prompt = self._build_correction_prompt(correction_text, stitch)
            await self._query_sdk(
                prompt,
                source="signal_correction_waiting_user_interrupt_and_query",
            )
            return "interrupt_and_query"

        # GENERATING or interruptible TOOL_EXECUTING
        if state not in (GenerationState.GENERATING, GenerationState.TOOL_EXECUTING):
            return "ignored"

        # Mark the pending request so _complete_request absorbs the
        # interrupted ResultMessage instead of resolving the future.
        if self._pending:
            self._pending[0].correction_resubmitted = True

        await self._interrupt_sdk()
        self._set_state(GenerationState.IDLE)
        stitch = self._create_stitching_context(reason="correction")
        asyncio.create_task(self._save_stitching_context_from_obj(stitch))
        await self._emit_partial_content(
            generation_id=self._current_generation_id,
            interrupted_by="correction",
        )
        prompt = self._build_correction_prompt(correction_text, stitch)
        await self._rotate_generation("correction")
        await self._query_sdk(
            prompt,
            source="signal_correction_active_interrupt_and_query",
        )
        return "interrupt_and_query"

    def _build_correction_prompt(
        self: "ReactiveSessionActor",
        correction: str,
        stitch: Optional[StitchingContext],
    ) -> str:
        """Build a factual correction prompt using embedded context."""
        parts: List[str] = []

        if stitch is not None:
            if stitch.partial_text:
                truncated_text = stitch.partial_text[-_STITCH_PARTIAL_TEXT_MAX_CHARS:]
                parts.append(f"你已经回复了以下内容：{truncated_text}")
            if stitch.completed_tools:
                tool_summaries = self._format_completed_tool_results(
                    stitch.completed_tools,
                )
                parts.append(f"你已经完成了以下操作的结果：{tool_summaries}")
            if stitch.partial_tool and isinstance(stitch.partial_tool, dict):
                tool_name = stitch.partial_tool.get("name", "")
                tool_input = stitch.partial_tool.get("input")
                if tool_input:
                    input_summary = str(tool_input)[:200]
                    parts.append(
                        f"你之前尝试调用了 {tool_name}（参数：{input_summary}），"
                        f"但操作未完成，请在需要时重新调用。"
                    )
                elif tool_name:
                    parts.append(
                        f"你之前尝试调用了 {tool_name}，但操作未完成，请在需要时重新调用。"
                    )
            elif stitch.partial_tool:
                parts.append(
                    f"你之前尝试调用了 {stitch.partial_tool}，但操作未完成，请在需要时重新调用。"
                )

        parts.append(f"用户的最新指示：{correction}")
        return "\n\n".join(parts)

    def _format_completed_tool_results(
        self: "ReactiveSessionActor", completed_tools: List[str]
    ) -> str:
        """Format completed tool names with input summaries from the request."""
        if not self._pending:
            return "、".join(completed_tools)

        req = self._pending[0]
        tool_call_map: Dict[str, Dict[str, Any]] = {}
        for tc in req.all_tool_calls:
            name = tc.get("name", "")
            if name and name not in tool_call_map:
                tool_call_map[name] = tc

        summaries: List[str] = []
        for name in completed_tools:
            tc = tool_call_map.get(name)
            if tc and tc.get("input"):
                input_brief = str(tc["input"])[:100]
                summaries.append(f"{name}({input_brief})")
            else:
                summaries.append(name)
        return "、".join(summaries)

    # ------------------------------------------------------------------
    # ADDITIVE
    # ------------------------------------------------------------------

    async def _do_additive(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> str:
        state = self._generation_state
        text = self._extract_signal_text(signal)

        if (
            state != GenerationState.IDLE
            and self._additive_this_turn >= self._budget.max_additive_per_turn
        ):
            logger.warning(
                "Additive per-turn budget reached: count=%d max=%d session=%s (buffering)",
                self._additive_this_turn,
                self._budget.max_additive_per_turn,
                self.session_id,
            )
            self._buffered_additives.append(signal)
            return "buffer"

        if state == GenerationState.IDLE:
            await self._query_sdk(text, source="signal_additive_idle")
            self._additive_this_turn += 1
            return "query"

        if state == GenerationState.GENERATING:
            self._buffered_additives.append(signal)
            logger.debug(
                "Buffered additive signal: session=%s buffered=%d",
                self.session_id,
                len(self._buffered_additives),
            )
            return "buffer"

        if state == GenerationState.TOOL_EXECUTING:
            wrapped = (
                "[SUPPLEMENTARY_INFO]\n"
                "用户补充了以下信息（请纳入当前任务的考虑，无需单独回复此条）:\n"
                f"{text}\n"
                "[/SUPPLEMENTARY_INFO]"
            )
            # change_state=False: the CLI merges this message into the
            # current turn internally.  The actor state should stay
            # TOOL_EXECUTING until the CLI's own stream transitions it
            # (e.g. a ToolResult or the next AssistantMessage).
            await self._query_sdk(
                wrapped,
                source="signal_additive_tool_executing_inject",
                change_state=False,
            )
            self._additive_this_turn += 1
            return "inject"

        if state == GenerationState.WAITING_USER:
            self._buffered_additives.append(signal)
            return "buffer"

        return "ignored"

    # ------------------------------------------------------------------
    # CANCEL
    # ------------------------------------------------------------------

    async def _do_cancel(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> str:
        state = self._generation_state

        if state == GenerationState.IDLE:
            return "ignored"

        if state == GenerationState.TOOL_EXECUTING and self._is_non_interruptible():
            self._defer_intervention(signal)
            logger.info(
                "Deferring CANCEL during non-interruptible tool: %s",
                self._active_tool,
            )
            return "deferred"

        await self._interrupt_sdk()
        self._set_state(GenerationState.IDLE)
        stitch = self._create_stitching_context(reason="cancel")
        if stitch:
            asyncio.create_task(self._save_stitching_context_from_obj(stitch))
        await self._emit_partial_content(interrupted_by="cancel")
        await self._emit_done_for_cancel()

        self._buffered_additives.clear()
        self._buffered_confirms.clear()
        self._buffered_sidekicks.clear()

        try:
            await self._invalidate_ctx_cache()
        except Exception:
            logger.warning(
                "Failed to invalidate context cache after cancel: session=%s",
                self.session_id,
                exc_info=True,
            )

        return "cancelled"

    async def _emit_done_for_cancel(self: "ReactiveSessionActor") -> None:
        """Emit a COMPLETE event indicating cancellation."""
        if not self._pending:
            return
        req = self._pending[0]
        msg = PubSubMessage(
            user_id=req.task.user_id,
            message_type=MessageType.COMPLETE,
            payload={
                "content": "",
                "is_final": True,
                "cancelled": True,
                "session_id": self.session_id,
            },
            trace_id=req.task.job_id or "",
            job_id=req.task.job_id,
        )
        try:
            await req.pubsub.publish(req.task.user_id, msg)
        except Exception:
            logger.warning(
                "Failed to publish cancel done: session=%s",
                self.session_id,
                exc_info=True,
            )

        result = RunResult(
            text="".join(req.all_text),
            tool_calls=req.all_tool_calls,
            stop_reason="cancelled",
            turns_used=req.turns_used,
            total_cost_usd=req.total_cost_usd,
            usage=req.usage,
            session_id=req.sdk_session_id,
        )
        if not req.future.done():
            req.future.set_result(result)

        cancelled_req = self._pending[0]
        self._pending.popleft()
        if self._pending:
            self._activate_request(self._pending[0])
            self._set_state(GenerationState.GENERATING)
        else:
            self._set_state(
                GenerationState.IDLE,
                _user_id=cancelled_req.task.user_id,
                _job_id=cancelled_req.task.job_id,
                _pubsub=cancelled_req.pubsub,
            )

    # ------------------------------------------------------------------
    # CONFIRM
    # ------------------------------------------------------------------

    async def _do_confirm(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> str:
        state = self._generation_state
        action_id = signal.payload.get("pending_action_id", "")
        confirmation = signal.payload.get("confirmation", "approve")
        is_ambiguous = signal.payload.get("is_ambiguous", False)

        confirmation_prompt = (
            "[USER_CONFIRMATION]\n"
            + build_confirm_prompt(
                action_id=action_id,
                confirmation=confirmation,
                is_ambiguous=is_ambiguous,
                user_text=signal.payload.get("text", ""),
            )
            + "\n[/USER_CONFIRMATION]"
        )

        if state == GenerationState.IDLE:
            await self._query_sdk(
                confirmation_prompt, source="signal_confirm_idle"
            )
            return "query"

        if state == GenerationState.GENERATING:
            self._buffered_confirms.append(signal)
            return "buffer"

        if state == GenerationState.TOOL_EXECUTING:
            await self._query_sdk(
                confirmation_prompt,
                source="signal_confirm_tool_executing_query",
                change_state=False,
            )
            return "query"

        if state == GenerationState.WAITING_USER:
            await self._interrupt_sdk()
            await self._rotate_generation("confirm")
            await self._query_sdk(
                confirmation_prompt,
                source="signal_confirm_waiting_user_interrupt_and_query",
            )
            return "interrupt_and_query"

        return "ignored"

    # ------------------------------------------------------------------
    # DIGRESSION
    # ------------------------------------------------------------------

    async def _do_digression(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> str:
        state = self._generation_state
        text = self._extract_signal_text(signal)

        if state == GenerationState.IDLE:
            await self._query_sdk(text, source="signal_digression_idle")
            return "query"

        if state == GenerationState.WAITING_USER:
            await self._interrupt_sdk()
            await self._emit_partial_content(
                generation_id=self._current_generation_id,
                interrupted_by="digression",
            )
            await self._rotate_generation("digression")

            if self._pending:
                interrupted_req = self._pending[0]
                digression_req = self._create_digression_request(
                    interrupted_req, text
                )
                result = RunResult(
                    text="".join(interrupted_req.all_text),
                    tool_calls=interrupted_req.all_tool_calls,
                    stop_reason="digression_interrupt",
                    turns_used=interrupted_req.turns_used,
                    total_cost_usd=interrupted_req.total_cost_usd,
                    usage=interrupted_req.usage,
                    session_id=interrupted_req.sdk_session_id,
                )
                if not interrupted_req.future.done():
                    interrupted_req.future.set_result(result)
                self._pending.popleft()
                await self._queue.put(digression_req)
            return "interrupt_and_queue"

        # For any active state, queue as a new request
        if self._pending:
            req = self._pending[0]
            digression_req = self._create_digression_request(req, text)
            await self._queue.put(digression_req)
            logger.info(
                "Digression queued as new request: session=%s",
                self.session_id,
            )

        return "queue"

    def _create_digression_request(
        self: "ReactiveSessionActor",
        source_req: "_StreamingRequest",
        text: str,
    ) -> "_StreamingRequest":
        """Build a new _StreamingRequest from an existing one for a digression."""
        from .reactive_session_actor import _StreamingRequest

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        return _StreamingRequest(
            worker=source_req.worker,
            runner=source_req.runner,
            run_config=source_req.run_config,
            task=TaskPayload(
                job_id=str(uuid.uuid4()),
                user_id=source_req.task.user_id,
                family_id=source_req.task.family_id,
                session_id=source_req.task.session_id,
                user_input=text,
                route_type=source_req.task.route_type,
            ),
            bridge=source_req.bridge,
            persistence=source_req.persistence,
            pubsub=source_req.pubsub,
            sdk_stream_handler=source_req.sdk_stream_handler,
            keepalive=source_req.keepalive,
            hook_builder=source_req.hook_builder,
            future=future,
        )

    # ------------------------------------------------------------------
    # SIDEKICK
    # ------------------------------------------------------------------

    async def _do_sidekick(
        self: "ReactiveSessionActor", signal: InterventionSignal
    ) -> str:
        # Check expiry
        expires_at_str = signal.payload.get("expires_at")
        if expires_at_str:
            try:
                from datetime import datetime as _dt

                expiry = _dt.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                if utc_now() > expiry:
                    logger.info(
                        "Sidekick signal expired (expires_at=%s), rejecting",
                        expires_at_str,
                    )
                    return "reject_expired"
            except (ValueError, TypeError):
                logger.warning("Invalid expires_at format: %s", expires_at_str)

        state = self._generation_state
        urgency = signal.payload.get("urgency", "low")

        if urgency in ("low", "medium") and state != GenerationState.IDLE:
            logger.debug(
                "Rejecting %s-urgency sidekick during %s: session=%s",
                urgency,
                state.value,
                self.session_id,
            )
            return "reject"

        if urgency != "high" and not self._check_sidekick_rate_limit():
            return "reject"

        wrapped = signal.payload.get("injection_prompt")
        if not wrapped:
            insight = signal.payload.get("insight_text", "")
            wrapped = f"[SYSTEM_INSIGHT]\n{insight}\n[/SYSTEM_INSIGHT]"

        if state == GenerationState.IDLE:
            await self._query_sdk(
                wrapped, source="signal_sidekick_idle_inject"
            )
            self._record_sidekick_injection()
            return "inject"

        if state in (GenerationState.WAITING_USER, GenerationState.GENERATING):
            self._buffer_sidekick_signal(signal, wrapped)
            return "buffer"

        if state == GenerationState.TOOL_EXECUTING:
            await self._query_sdk(
                wrapped,
                source="signal_sidekick_tool_executing_inject",
                change_state=False,
            )
            self._record_sidekick_injection()
            return "inject"

        return "ignored"

    def _buffer_sidekick_signal(
        self: "ReactiveSessionActor",
        signal: InterventionSignal,
        wrapped_text: str,
    ) -> None:
        """Buffer a sidekick signal with pre-wrapped text."""
        buffer_signal = InterventionSignal(
            signal_id=signal.signal_id,
            type=signal.type,
            session_id=signal.session_id,
            job_id=signal.job_id,
            user_id=signal.user_id,
            timestamp=signal.timestamp,
            payload={"text": wrapped_text},
            priority=signal.priority,
        )
        self._buffered_sidekicks.append(buffer_signal)

    # ------------------------------------------------------------------
    # Sidekick rate limiting
    # ------------------------------------------------------------------

    def _check_sidekick_rate_limit(self: "ReactiveSessionActor") -> bool:
        """Check actor-side sidekick rate limits. Returns True if allowed."""
        if self._sidekick_count_session >= _MAX_SIDEKICK_PER_SESSION:
            logger.warning(
                "Sidekick session limit exceeded: count=%d max=%d session=%s",
                self._sidekick_count_session,
                _MAX_SIDEKICK_PER_SESSION,
                self.session_id,
            )
            return False
        if self._sidekick_count_turn >= _MAX_SIDEKICK_PER_TURN:
            logger.warning(
                "Sidekick turn limit exceeded: count=%d max=%d session=%s",
                self._sidekick_count_turn,
                _MAX_SIDEKICK_PER_TURN,
                self.session_id,
            )
            return False
        if self._last_sidekick_time is not None:
            elapsed = time.monotonic() - self._last_sidekick_time
            if elapsed < _MIN_SIDEKICK_INTERVAL_SECONDS:
                logger.warning(
                    "Sidekick interval too short: elapsed=%.1fs min=%.1fs session=%s",
                    elapsed,
                    _MIN_SIDEKICK_INTERVAL_SECONDS,
                    self.session_id,
                )
                return False
        return True

    def _record_sidekick_injection(
        self: "ReactiveSessionActor", count: int = 1
    ) -> None:
        """Record sidekick injection(s) for rate limiting counters."""
        self._sidekick_count_session += count
        self._sidekick_count_turn += count
        self._last_sidekick_time = time.monotonic()
