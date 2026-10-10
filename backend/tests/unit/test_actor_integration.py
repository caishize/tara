"""Integration and scenario tests for ReactiveSessionActor.

Covers bridging event emission, continues_from propagation,
digression queuing across states, WAITING_USER handler behaviors,
crash fixes, sidekick rate limiting, separate buffer flush,
and _query_sdk state revert.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from claude_agent_sdk import ResultMessage

from src.ai_engine.intervention.types import (
    GenerationState,
    InterventionType,
)

from tests.unit.reactive_actor_helpers import _make_pending_req, _make_signal


# ---------------------------------------------------------------------------
# Boundary: Bridging event emission during CORRECTION
# ---------------------------------------------------------------------------


class TestBridgingEventEmission:
    @pytest.mark.asyncio
    async def test_correction_during_generating_emits_partial_and_bridging(self, actor):
        """_do_correction during GENERATING should emit PARTIAL_CONTENT
        and BRIDGING events."""
        actor._set_state(GenerationState.GENERATING)
        actor._interrupt_sdk = AsyncMock()
        actor._create_stitching_context = MagicMock(return_value=None)
        actor._save_stitching_context_from_obj = AsyncMock()
        actor._emit_partial_content = AsyncMock()
        actor._emit_bridging = AsyncMock()
        actor._query_sdk = AsyncMock()
        actor._current_generation_id = "gen-old-123"

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"text": "change to Shanghai"},
        )
        await actor._do_correction(signal)

        # Verify interrupt was called first
        actor._interrupt_sdk.assert_called_once()

        # Verify stitching context was created in-memory
        actor._create_stitching_context.assert_called_once_with(reason="correction")

        # Verify partial content emitted with old generation_id and interrupted_by
        actor._emit_partial_content.assert_called_once_with(
            generation_id="gen-old-123",
            interrupted_by="correction",
        )

        # Verify bridging emitted with signal_type="correction", a NEW generation_id,
        # and continues_from carrying the OLD generation_id
        actor._emit_bridging.assert_called_once()
        bridging_args = actor._emit_bridging.call_args
        assert bridging_args[0][0] == "correction"
        new_gen_id = bridging_args[0][1]
        assert new_gen_id != "gen-old-123"  # Must be a new ID
        assert bridging_args[1].get("continues_from") == "gen-old-123"

        # Verify SDK was queried with the correction text
        actor._query_sdk.assert_called_once()

    @pytest.mark.asyncio
    async def test_correction_during_interruptible_tool_emits_events(self, actor):
        """_do_correction during TOOL_EXECUTING (interruptible) should also
        emit partial content and bridging events."""
        actor._set_state(GenerationState.TOOL_EXECUTING)
        actor._active_tool = "query_weather"  # Interruptible
        actor._interrupt_sdk = AsyncMock()
        actor._create_stitching_context = MagicMock(return_value=None)
        actor._save_stitching_context_from_obj = AsyncMock()
        actor._emit_partial_content = AsyncMock()
        actor._emit_bridging = AsyncMock()
        actor._query_sdk = AsyncMock()
        actor._current_generation_id = "gen-tool-456"

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"text": "no, check Beijing instead"},
        )
        await actor._do_correction(signal)

        actor._interrupt_sdk.assert_called_once()
        actor._emit_partial_content.assert_called_once_with(
            generation_id="gen-tool-456",
            interrupted_by="correction",
        )
        actor._emit_bridging.assert_called_once()
        bridging_args = actor._emit_bridging.call_args
        assert bridging_args[1].get("continues_from") == "gen-tool-456"


# ---------------------------------------------------------------------------
# FIX 1: continues_from in bridging events
# ---------------------------------------------------------------------------


class TestContinuesFromInBridging:
    @pytest.mark.asyncio
    async def test_correction_during_generating_passes_continues_from(self, actor):
        """Bridging event from CORRECTION during GENERATING should carry continues_from."""
        actor._set_state(GenerationState.GENERATING)
        actor._interrupt_sdk = AsyncMock()
        actor._create_stitching_context = MagicMock(return_value=None)
        actor._save_stitching_context_from_obj = AsyncMock()
        actor._emit_partial_content = AsyncMock()
        actor._emit_bridging = AsyncMock()
        actor._query_sdk = AsyncMock()
        actor._current_generation_id = "old-gen-id"

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"text": "fix it"},
        )
        await actor._do_correction(signal)

        actor._emit_bridging.assert_called_once()
        call_kwargs = actor._emit_bridging.call_args
        assert call_kwargs[1].get("continues_from") == "old-gen-id"

    @pytest.mark.asyncio
    async def test_correction_during_waiting_user_passes_continues_from(self, actor):
        """Bridging event from CORRECTION during WAITING_USER should carry continues_from."""
        actor._set_state(GenerationState.WAITING_USER)
        actor._emit_bridging = AsyncMock()
        actor._current_generation_id = "waiting-gen-id"

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"text": "correct it"},
        )
        await actor._do_correction(signal)

        actor._emit_bridging.assert_called_once()
        call_kwargs = actor._emit_bridging.call_args
        assert call_kwargs[1].get("continues_from") == "waiting-gen-id"

    @pytest.mark.asyncio
    async def test_confirm_during_waiting_user_passes_continues_from(self, actor):
        """Bridging event from CONFIRM during WAITING_USER should carry continues_from."""
        actor._set_state(GenerationState.WAITING_USER)
        actor._emit_bridging = AsyncMock()
        actor._current_generation_id = "confirm-gen-id"

        signal = _make_signal(
            signal_type=InterventionType.CONFIRM.value,
            payload={"pending_action_id": "act-1", "confirmation": "approve"},
        )
        await actor._do_confirm(signal)

        actor._emit_bridging.assert_called_once()
        call_kwargs = actor._emit_bridging.call_args
        assert call_kwargs[1].get("continues_from") == "confirm-gen-id"

    @pytest.mark.asyncio
    async def test_digression_during_waiting_user_passes_continues_from(self, actor):
        """Bridging event from DIGRESSION during WAITING_USER should carry continues_from."""
        actor._set_state(GenerationState.WAITING_USER)
        actor._emit_bridging = AsyncMock()
        actor._current_generation_id = "digression-gen-id"

        mock_req = _make_pending_req()
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.DIGRESSION.value,
            payload={"text": "new topic"},
        )
        await actor._do_digression(signal)

        actor._emit_bridging.assert_called_once()
        call_kwargs = actor._emit_bridging.call_args
        assert call_kwargs[1].get("continues_from") == "digression-gen-id"


# ---------------------------------------------------------------------------
# Boundary: DIGRESSION queuing during GENERATING
# ---------------------------------------------------------------------------


class TestDigressionDuringGenerating:
    @pytest.mark.asyncio
    async def test_digression_during_generating_queues_new_request(self, actor):
        """DIGRESSION during GENERATING should queue as a new request,
        not process immediately. _interrupt_sdk should NOT be called."""
        actor._set_state(GenerationState.GENERATING)
        actor._interrupt_sdk = AsyncMock()

        mock_req = _make_pending_req()
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.DIGRESSION.value,
            payload={"text": "what time is it?"},
        )
        await actor._do_digression(signal)

        # Should be queued, not processed via SDK directly
        assert not actor._queue.empty()
        actor._interrupt_sdk.assert_not_called()
        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_digression_during_tool_executing_queues_new_request(self, actor):
        """DIGRESSION during TOOL_EXECUTING should also queue as a new request."""
        actor._set_state(GenerationState.TOOL_EXECUTING)
        actor._active_tool = "query_weather"
        actor._interrupt_sdk = AsyncMock()

        mock_req = _make_pending_req()
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.DIGRESSION.value,
            payload={"text": "what about dinner?"},
        )
        await actor._do_digression(signal)

        assert not actor._queue.empty()
        actor._interrupt_sdk.assert_not_called()
        actor._pooled.client.query.assert_not_called()


# ---------------------------------------------------------------------------
# DIGRESSION during WAITING_USER now queues (Fix 1)
# ---------------------------------------------------------------------------


class TestDigressionWaitingUserQueues:
    @pytest.mark.asyncio
    async def test_digression_during_waiting_user_queues_not_direct(self, actor):
        """DIGRESSION during WAITING_USER should interrupt, emit bridging,
        and queue as new request -- not call query_sdk directly."""
        actor._set_state(GenerationState.WAITING_USER)
        actor._emit_bridging = AsyncMock()

        mock_req = _make_pending_req()
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.DIGRESSION.value,
            payload={"text": "what time is it?"},
        )
        await actor._do_digression(signal)

        # Should interrupt SDK
        actor._pooled.client.interrupt.assert_called_once()
        # Should emit bridging event
        actor._emit_bridging.assert_called_once()
        bridging_args = actor._emit_bridging.call_args[0]
        assert bridging_args[0] == "digression"
        # Should queue a new request
        assert not actor._queue.empty()
        # Should NOT call query_sdk directly
        actor._pooled.client.query.assert_not_called()


# ---------------------------------------------------------------------------
# Digression WAITING_USER resolves future (M-6)
# ---------------------------------------------------------------------------


class TestDigressionWaitingUserResolvesFuture:
    @pytest.mark.asyncio
    async def test_digression_waiting_user_resolves_interrupted_future(self, actor):
        """DIGRESSION during WAITING_USER should resolve the interrupted
        request's future with stop_reason='digression_interrupt'."""
        actor._set_state(GenerationState.WAITING_USER)
        actor._emit_bridging = AsyncMock()

        loop = asyncio.get_event_loop()
        mock_future = loop.create_future()
        mock_req = _make_pending_req(
            future=mock_future,
            user_input="original question",
            all_text=["partial response"],
            turns_used=1,
            total_cost_usd=0.01,
            usage={},
            sdk_session_id="sdk-123",
        )
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.DIGRESSION.value,
            payload={"new_input": "what time is it?"},
        )
        await actor._do_digression(signal)

        # Future should be resolved
        assert mock_future.done()
        result = mock_future.result()
        assert result.stop_reason == "digression_interrupt"
        assert result.text == "partial response"

        # Original request should be popped from pending
        assert len(actor._pending) == 0

        # Digression should be queued
        assert not actor._queue.empty()


# ---------------------------------------------------------------------------
# Boundary: WAITING_USER handler tests
# ---------------------------------------------------------------------------


class TestWaitingUserHandlers:
    @pytest.mark.asyncio
    async def test_correction_during_waiting_user(self, actor):
        """CORRECTION during WAITING_USER should interrupt + query SDK."""
        actor._set_state(GenerationState.WAITING_USER)
        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"text": "actually change it to Shanghai"},
        )
        await actor._do_correction(signal)

        actor._pooled.client.interrupt.assert_called_once()
        actor._pooled.client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_digression_during_waiting_user_interrupts_and_queues(self, actor):
        """DIGRESSION during WAITING_USER should interrupt + queue (not direct query)."""
        actor._set_state(GenerationState.WAITING_USER)
        actor._emit_bridging = AsyncMock()

        mock_req = _make_pending_req()
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.DIGRESSION.value,
            payload={"text": "how is the weather?"},
        )
        await actor._do_digression(signal)

        actor._pooled.client.interrupt.assert_called_once()
        # Now queues instead of direct query
        assert not actor._queue.empty()
        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sidekick_during_waiting_user(self, actor):
        """SIDEKICK during WAITING_USER should be buffered (not query SDK directly)."""
        actor._set_state(GenerationState.WAITING_USER)
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"insight_text": "User has a meeting tomorrow", "urgency": "high"},
        )
        await actor._do_sidekick(signal)

        # Should be buffered, NOT queried directly
        actor._pooled.client.query.assert_not_called()
        assert len(actor._buffered_sidekicks) == 1
        assert "[SYSTEM_INSIGHT]" in actor._buffered_sidekicks[0].payload["text"]


# ---------------------------------------------------------------------------
# WAITING_USER crash fixes (P1 additive, P1 confirm, P1 sidekick)
# ---------------------------------------------------------------------------


class TestWaitingUserCrashFixes:
    @pytest.mark.asyncio
    async def test_additive_during_waiting_user_buffers_not_queries(self, actor):
        """ADDITIVE during WAITING_USER should buffer, not call _query_sdk."""
        actor._set_state(GenerationState.WAITING_USER)

        signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"text": "extra info while waiting"},
        )
        await actor._do_additive(signal)

        actor._pooled.client.query.assert_not_called()
        assert len(actor._buffered_additives) == 1
        assert actor._buffered_additives[0] is signal

    @pytest.mark.asyncio
    async def test_confirm_during_waiting_user_interrupts_then_queries(self, actor):
        """CONFIRM during WAITING_USER should interrupt SDK before querying."""
        actor._set_state(GenerationState.WAITING_USER)
        actor._emit_bridging = AsyncMock()

        signal = _make_signal(
            signal_type=InterventionType.CONFIRM.value,
            payload={"pending_action_id": "action-xyz", "confirmation": "approve"},
        )
        await actor._do_confirm(signal)

        # interrupt must be called BEFORE query
        actor._pooled.client.interrupt.assert_called_once()
        actor._pooled.client.query.assert_called_once()
        # bridging emitted with "confirm"
        actor._emit_bridging.assert_called_once()
        bridging_args = actor._emit_bridging.call_args[0]
        assert bridging_args[0] == "confirm"

    @pytest.mark.asyncio
    async def test_sidekick_during_waiting_user_buffers_all_urgencies(self, actor):
        """SIDEKICK during WAITING_USER: high urgency is buffered,
        low/medium are rejected (filtered by the early return guard)."""
        actor._set_state(GenerationState.WAITING_USER)

        for urgency in ("high", "medium", "low"):
            signal = _make_signal(
                signal_type=InterventionType.SIDEKICK_INSIGHT.value,
                payload={"insight_text": f"{urgency} insight", "urgency": urgency},
            )
            await actor._do_sidekick(signal)

        # None should call query directly
        actor._pooled.client.query.assert_not_called()
        # Only high urgency reaches the WAITING_USER branch and gets buffered;
        # low/medium are rejected by the early guard
        assert len(actor._buffered_sidekicks) == 1
        assert "[SYSTEM_INSIGHT]" in actor._buffered_sidekicks[0].payload["text"]
        assert "high insight" in actor._buffered_sidekicks[0].payload["text"]


# ---------------------------------------------------------------------------
# Boundary: Medium urgency sidekick rejection during non-IDLE
# ---------------------------------------------------------------------------


class TestMediumUrgencySidekickRejection:
    @pytest.mark.asyncio
    async def test_medium_urgency_rejected_during_generating(self, actor):
        """Medium urgency sidekick should be rejected during GENERATING."""
        actor._set_state(GenerationState.GENERATING)
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"insight_text": "some info", "urgency": "medium"},
        )
        await actor._do_sidekick(signal)

        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_medium_urgency_rejected_during_tool_executing(self, actor):
        """Medium urgency sidekick should be rejected during TOOL_EXECUTING."""
        actor._set_state(GenerationState.TOOL_EXECUTING)
        actor._active_tool = "query_weather"
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"insight_text": "some info", "urgency": "medium"},
        )
        await actor._do_sidekick(signal)

        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_high_urgency_accepted_during_generating(self, actor):
        """High urgency sidekick should be buffered during GENERATING
        (not rejected like medium/low)."""
        actor._set_state(GenerationState.GENERATING)
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"insight_text": "urgent info", "urgency": "high"},
        )
        await actor._do_sidekick(signal)

        # High urgency during GENERATING gets buffered (not rejected)
        assert len(actor._buffered_sidekicks) == 1

    @pytest.mark.asyncio
    async def test_high_urgency_accepted_during_tool_executing(self, actor):
        """High urgency sidekick should be accepted during TOOL_EXECUTING."""
        actor._set_state(GenerationState.TOOL_EXECUTING)
        actor._active_tool = "query_weather"
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"insight_text": "urgent info", "urgency": "high"},
        )
        await actor._do_sidekick(signal)

        actor._pooled.client.query.assert_called_once()


# ---------------------------------------------------------------------------
# FIX 4: CONFIRM interruptibility check during TOOL_EXECUTING
# ---------------------------------------------------------------------------


class TestConfirmInterruptibilityCheck:
    @pytest.mark.asyncio
    async def test_confirm_proceeds_during_interruptible_tool(self, actor):
        """CONFIRM during TOOL_EXECUTING with interruptible tool should proceed."""
        actor._set_state(GenerationState.TOOL_EXECUTING)
        actor._active_tool = "query_weather"  # Interruptible

        signal = _make_signal(
            signal_type=InterventionType.CONFIRM.value,
            payload={"pending_action_id": "act-1", "confirmation": "approve"},
        )
        await actor._do_confirm(signal)

        assert actor._deferred_intervention is None
        actor._pooled.client.query.assert_called_once()


# ---------------------------------------------------------------------------
# FIX 5: Separate buffer flush for CONFIRM and SIDEKICK
# ---------------------------------------------------------------------------


class TestSeparateBufferFlush:
    @pytest.mark.asyncio
    async def test_flush_buffered_confirms_sends_without_supplementary_wrapper(self, actor):
        """Flushed confirms should NOT be wrapped in [SUPPLEMENTARY_INFO]."""
        confirmation_prompt = (
            "[USER_CONFIRMATION]\nAction: a-1\nDecision: confirmed\n[/USER_CONFIRMATION]"
        )
        actor._buffered_confirms = [
            _make_signal(payload={"text": confirmation_prompt}),
        ]
        await actor._flush_buffered_confirms()

        call_args = actor._pooled.client.query.call_args[0][0]
        assert "[USER_CONFIRMATION]" in call_args
        assert "[SUPPLEMENTARY_INFO]" not in call_args

    @pytest.mark.asyncio
    async def test_flush_buffered_sidekicks_sends_without_supplementary_wrapper(self, actor):
        """Flushed sidekicks should NOT be wrapped in [SUPPLEMENTARY_INFO]."""
        insight_text = "[SYSTEM_INSIGHT]\nSome insight\n[/SYSTEM_INSIGHT]"
        actor._buffered_sidekicks = [
            _make_signal(payload={"text": insight_text}),
        ]
        await actor._flush_buffered_sidekicks()

        call_args = actor._pooled.client.query.call_args[0][0]
        assert "[SYSTEM_INSIGHT]" in call_args
        assert "[SUPPLEMENTARY_INFO]" not in call_args

    @pytest.mark.asyncio
    async def test_flush_empty_buffers_noop(self, actor):
        """Flushing empty confirm/sidekick buffers should not call query."""
        await actor._flush_buffered_confirms()
        await actor._flush_buffered_sidekicks()
        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_all_three_buffers_flushed_on_idle_transition(self, actor):
        """All three buffers should be combined into a single query on IDLE transition."""
        actor._set_state(GenerationState.GENERATING)
        actor._pool = MagicMock()
        actor._pool.mark_used = AsyncMock()

        mock_future = asyncio.get_event_loop().create_future()
        mock_req = _make_pending_req(
            future=mock_future,
            all_text=["text"],
        )
        actor._pending.append(mock_req)

        # Populate all three buffers
        actor._buffered_confirms = [
            _make_signal(
                signal_type=InterventionType.CONFIRM.value,
                payload={"pending_action_id": "act-1", "confirmation": "approve"},
            )
        ]
        actor._buffered_sidekicks = [_make_signal(payload={"text": "sidekick insight"})]
        actor._buffered_additives = [_make_signal(payload={"text": "additive info"})]

        result_msg = MagicMock(spec=ResultMessage)
        result_msg.subtype = "end_turn"
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.01
        result_msg.usage = {}
        result_msg.session_id = "sdk-session"

        await actor._handle_message(result_msg)

        # All buffers should be cleared
        assert len(actor._buffered_confirms) == 0
        assert len(actor._buffered_sidekicks) == 0
        assert len(actor._buffered_additives) == 0
        # _flush_all_buffered combines all buffers into 1 query call
        assert actor._pooled.client.query.call_count == 1
        combined_prompt = actor._pooled.client.query.call_args[0][0]
        assert "[USER_CONFIRMATION]" in combined_prompt
        assert "[SYSTEM_INSIGHT]" in combined_prompt
        # Additive text is sent as plain user message (no SUPPLEMENTARY_INFO wrapper)
        assert "[SUPPLEMENTARY_INFO]" not in combined_prompt
        assert "请回复用户" in combined_prompt
        assert "additive info" in combined_prompt


# ---------------------------------------------------------------------------
# _query_sdk state revert on failure (P5)
# ---------------------------------------------------------------------------


class TestQuerySdkStateRevert:
    @pytest.mark.asyncio
    async def test_query_sdk_reverts_state_on_failure(self, actor):
        """_query_sdk should revert state to previous value when client.query raises."""
        actor._set_state(GenerationState.WAITING_USER)
        actor._pooled.client.query = AsyncMock(side_effect=RuntimeError("SDK error"))

        await actor._query_sdk("test prompt")

        # State should be reverted back to WAITING_USER, not stuck at GENERATING
        assert actor._generation_state == GenerationState.WAITING_USER


# ---------------------------------------------------------------------------
# FIX 7: Actor-side sidekick rate limiting
# ---------------------------------------------------------------------------


class TestActorSidekickRateLimiting:
    @pytest.mark.asyncio
    async def test_sidekick_session_limit(self, actor):
        """Sidekick should be rejected when session limit is exceeded.
        Uses low urgency because high urgency bypasses rate limits."""
        actor._set_state(GenerationState.IDLE)
        actor._sidekick_count_session = 3  # At limit

        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"insight_text": "blocked", "urgency": "low"},
        )
        await actor._do_sidekick(signal)

        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sidekick_turn_limit(self, actor):
        """Sidekick should be rejected when turn limit is exceeded.
        Uses low urgency because high urgency bypasses rate limits."""
        actor._set_state(GenerationState.IDLE)
        actor._sidekick_count_turn = 1  # At limit

        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"insight_text": "blocked", "urgency": "low"},
        )
        await actor._do_sidekick(signal)

        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sidekick_interval_limit(self, actor):
        """Sidekick should be rejected when interval is too short.
        Uses low urgency because high urgency bypasses rate limits."""
        import time
        actor._set_state(GenerationState.IDLE)
        actor._last_sidekick_time = time.monotonic()  # Just now

        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"insight_text": "too soon", "urgency": "low"},
        )
        await actor._do_sidekick(signal)

        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sidekick_records_injection(self, actor):
        """Successful sidekick injection should update counters."""
        actor._set_state(GenerationState.IDLE)
        assert actor._sidekick_count_session == 0
        assert actor._sidekick_count_turn == 0

        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"insight_text": "good info", "urgency": "high"},
        )
        await actor._do_sidekick(signal)

        assert actor._sidekick_count_session == 1
        assert actor._sidekick_count_turn == 1
        assert actor._last_sidekick_time is not None

    @pytest.mark.asyncio
    async def test_sidekick_turn_counter_resets_on_idle(self, actor):
        """_sidekick_count_turn should reset to 0 on IDLE transition."""
        actor._sidekick_count_turn = 1
        actor._set_state(GenerationState.GENERATING)
        actor._pool = MagicMock()
        actor._pool.mark_used = AsyncMock()

        mock_future = asyncio.get_event_loop().create_future()
        mock_req = _make_pending_req(
            future=mock_future,
            all_text=["text"],
        )
        actor._pending.append(mock_req)

        result_msg = MagicMock(spec=ResultMessage)
        result_msg.subtype = "end_turn"
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.01
        result_msg.usage = {}
        result_msg.session_id = "sdk-session"

        await actor._handle_message(result_msg)

        assert actor._sidekick_count_turn == 0


# ---------------------------------------------------------------------------
# CANCEL during WAITING_USER emits bridging event (M-4)
# ---------------------------------------------------------------------------


class TestCancelWaitingUserBridging:
    @pytest.mark.asyncio
    async def test_cancel_during_waiting_user_emits_partial_and_done(self, actor):
        """CANCEL during WAITING_USER should interrupt, create stitch context,
        emit partial content, and emit done for cancel."""
        actor._set_state(GenerationState.WAITING_USER)
        actor._current_generation_id = "gen-waiting-123"
        actor._create_stitching_context = MagicMock(return_value=None)
        actor._save_stitching_context_from_obj = AsyncMock()
        actor._emit_partial_content = AsyncMock()
        actor._emit_done_for_cancel = AsyncMock()

        signal = _make_signal(signal_type=InterventionType.CANCEL.value)
        await actor._do_cancel(signal)

        actor._pooled.client.interrupt.assert_called_once()
        actor._create_stitching_context.assert_called_once_with(reason="cancel")
        actor._emit_partial_content.assert_called_once_with(interrupted_by="cancel")
        actor._emit_done_for_cancel.assert_called_once()
