"""Intervention handler tests for ReactiveSessionActor.

Covers:
- Deferred intervention during non-interruptible tool execution
- DIGRESSION queuing during GENERATING
- ADDITIVE buffering during GENERATING
- CONFIRM during WAITING_USER
- Buffered ADDITIVE flush on ResultMessage (IDLE transition)
- Sidekick urgency x state gating
- _build_correction_prompt and _format_completed_tool_results
- Session reset trigger when budget exceeded
"""

from collections import deque
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai_engine.intervention.types import (
    GenerationState,
    InterventionType,
    StitchingContext,
)

from tests.unit.reactive_actor_helpers import _make_pending_req, _make_signal


# ---------------------------------------------------------------------------
# Deferred intervention during non-interruptible tool execution
# ---------------------------------------------------------------------------


class TestDeferredIntervention:
    """Tests for deferred intervention flow when a non-interruptible tool
    is executing (MEDIUM #6)."""

    @pytest.mark.asyncio
    async def test_correction_deferred_during_non_interruptible_tool(self, actor):
        """CORRECTION during non-interruptible tool should defer, not interrupt."""
        actor._generation_state = GenerationState.TOOL_EXECUTING
        actor._active_tool = "send_message"
        actor._do_correction = AsyncMock()

        signal = _make_signal(signal_type=InterventionType.CORRECTION.value)
        await actor._dispatch_signal(signal)

        # The actual _do_correction handler is called by dispatch, which
        # internally checks the state and defers. We need to test the
        # handler directly to verify deferral.
        actor._do_correction.reset_mock()

        # Reset and call the real handler
        actor._do_correction = actor.__class__._do_correction.__get__(actor)
        actor._pooled.client.interrupt = AsyncMock()
        actor._pooled.client.query = AsyncMock()

        correction_signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"corrected_input": "fix this"},
        )
        await actor._do_correction(correction_signal)

        assert actor._deferred_intervention is correction_signal
        actor._pooled.client.interrupt.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_deferred_during_non_interruptible_tool(self, actor):
        """CANCEL during non-interruptible tool should also be deferred."""
        actor._generation_state = GenerationState.TOOL_EXECUTING
        actor._active_tool = "create_trip"

        cancel_signal = _make_signal(signal_type=InterventionType.CANCEL.value)
        await actor._do_cancel(cancel_signal)

        assert actor._deferred_intervention is cancel_signal

    @pytest.mark.asyncio
    async def test_additive_during_non_interruptible_tool_merges_directly(self, actor):
        """ADDITIVE during non-interruptible TOOL_EXECUTING should query() merge,
        not defer."""
        actor._generation_state = GenerationState.TOOL_EXECUTING
        actor._active_tool = "send_message"
        actor._pooled.client.query = AsyncMock()

        additive_signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"additional_input": "also mention the price"},
        )
        await actor._do_additive(additive_signal)

        # Should NOT be deferred
        assert actor._deferred_intervention is None
        # Should have called query() with wrapped supplementary info
        actor._pooled.client.query.assert_called_once()
        call_arg = actor._pooled.client.query.call_args[0][0]
        assert "[SUPPLEMENTARY_INFO]" in call_arg
        assert "also mention the price" in call_arg

    @pytest.mark.asyncio
    async def test_deferred_correction_dispatched_after_tool_completes(self, actor):
        """After tool completion, deferred CORRECTION should be dispatched."""
        actor._generation_state = GenerationState.GENERATING
        actor._pooled.client.interrupt = AsyncMock()
        actor._pooled.client.query = AsyncMock()
        # In production, a pending request always exists during GENERATING.
        mock_req = _make_pending_req(pubsub=MagicMock(publish=AsyncMock()))
        actor._pending.append(mock_req)

        deferred_signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"corrected_input": "fix this"},
        )
        actor._deferred_intervention = deferred_signal

        # Simulate tool completion triggering deferred handler
        await actor._handle_deferred_intervention()

        # Deferred should be cleared
        assert actor._deferred_intervention is None
        # The correction handler should have executed (interrupt + query)
        actor._pooled.client.interrupt.assert_called_once()
        actor._pooled.client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_deferred_cancel_dispatched_after_tool_completes(self, actor):
        """After tool completion, deferred CANCEL should be dispatched."""
        actor._generation_state = GenerationState.GENERATING
        actor._pooled.client.interrupt = AsyncMock()
        # Need a pending request for _emit_done_for_cancel
        mock_req = _make_pending_req()
        actor._pending.append(mock_req)

        deferred_signal = _make_signal(
            signal_type=InterventionType.CANCEL.value,
        )
        actor._deferred_intervention = deferred_signal

        await actor._handle_deferred_intervention()

        assert actor._deferred_intervention is None
        # Cancel should have interrupted
        actor._pooled.client.interrupt.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_deferred_intervention_is_noop(self, actor):
        """_handle_deferred_intervention with no deferred signal is a no-op."""
        actor._deferred_intervention = None
        actor._pooled.client.interrupt = AsyncMock()

        await actor._handle_deferred_intervention()

        actor._pooled.client.interrupt.assert_not_called()

    @pytest.mark.asyncio
    async def test_deferred_dropped_when_budget_exceeded(self, actor):
        """Deferred intervention should be dropped if budget was exceeded
        during the deferral period."""
        actor._generation_state = GenerationState.GENERATING
        actor._intervention_count = 10  # Exceed default max (5)
        actor._pooled.client.interrupt = AsyncMock()
        actor._pooled.client.query = AsyncMock()

        deferred_signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"corrected_input": "fix this"},
        )
        actor._deferred_intervention = deferred_signal

        await actor._handle_deferred_intervention()

        assert actor._deferred_intervention is None
        # Handler should NOT have been called since budget is exceeded
        actor._pooled.client.interrupt.assert_not_called()
        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_confirm_during_non_interruptible_tool_merges_directly(self, actor):
        """CONFIRM during non-interruptible TOOL_EXECUTING merges via query()
        per design S3.3, not deferred."""
        actor._generation_state = GenerationState.TOOL_EXECUTING
        actor._active_tool = "confirm_action"
        actor._pooled.client.query = AsyncMock()

        confirm_signal = _make_signal(
            signal_type=InterventionType.CONFIRM.value,
            payload={
                "pending_action_id": "action-123",
                "confirmation": "approve",
            },
        )
        await actor._do_confirm(confirm_signal)

        # Should NOT be deferred -- per design S3.3, CONFIRM merges directly
        assert actor._deferred_intervention is None
        # Should have called query() with confirmation prompt
        actor._pooled.client.query.assert_called_once()
        call_arg = actor._pooled.client.query.call_args[0][0]
        assert "[USER_CONFIRMATION]" in call_arg
        assert "action-123" in call_arg


# ---------------------------------------------------------------------------
# Fix #7: DIGRESSION queuing during GENERATING
# ---------------------------------------------------------------------------


class TestDigressionQueuingDuringGenerating:
    """DIGRESSION during GENERATING should queue a new request, not call
    client.query() directly (Fix #7)."""

    @pytest.mark.asyncio
    async def test_digression_queued_during_generating(self, actor):
        actor._generation_state = GenerationState.GENERATING
        mock_req = _make_pending_req(user_input="original question")
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.DIGRESSION.value,
            payload={"new_input": "completely different topic"},
        )
        await actor._do_digression(signal)

        # The digression should be queued as a new request
        assert not actor._queue.empty()
        # client.query() should NOT have been called directly
        actor._pooled.client.query.assert_not_called()


# ---------------------------------------------------------------------------
# Fix #9: ADDITIVE buffering during GENERATING
# ---------------------------------------------------------------------------


class TestAdditiveBufferingDuringGenerating:
    """ADDITIVE during GENERATING should be buffered, not sent via
    client.query() (Fix #9)."""

    @pytest.mark.asyncio
    async def test_additive_buffered_during_generating(self, actor):
        actor._generation_state = GenerationState.GENERATING

        signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"additional_input": "also consider the weather"},
        )
        await actor._do_additive(signal)

        # Signal should be buffered
        assert len(actor._buffered_additives) == 1
        assert actor._buffered_additives[0] is signal
        # client.query() should NOT have been called
        actor._pooled.client.query.assert_not_called()


# ---------------------------------------------------------------------------
# Fix #10: CONFIRM during WAITING_USER
# ---------------------------------------------------------------------------


class TestConfirmDuringWaitingUser:
    """CONFIRM during WAITING_USER should interrupt then query with
    confirmation prompt (Fix #10)."""

    @pytest.mark.asyncio
    async def test_confirm_interrupts_and_queries_during_waiting_user(self, actor):
        actor._generation_state = GenerationState.WAITING_USER
        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.CONFIRM.value,
            payload={
                "pending_action_id": "action-456",
                "confirmation": "approve",
            },
        )
        await actor._do_confirm(signal)

        # Should have interrupted first
        actor._pooled.client.interrupt.assert_called_once()
        # Should have queried with confirmation prompt
        actor._pooled.client.query.assert_called_once()
        call_arg = actor._pooled.client.query.call_args[0][0]
        assert "[USER_CONFIRMATION]" in call_arg
        assert "action-456" in call_arg

    @pytest.mark.asyncio
    async def test_confirm_emits_bridging_during_waiting_user(self, actor):
        """CONFIRM during WAITING_USER should emit a BRIDGING event with
        signal_type='confirm' and continues_from linking old generation_id."""
        actor._generation_state = GenerationState.WAITING_USER
        actor._current_generation_id = "old-gen-123"
        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.CONFIRM.value,
            payload={
                "pending_action_id": "action-789",
                "confirmation": "approve",
            },
        )
        await actor._do_confirm(signal)

        # Find the BRIDGING publish call among all pubsub.publish calls
        bridging_calls = [
            call
            for call in mock_pubsub.publish.call_args_list
            if hasattr(call[0][1], "message_type")
            and call[0][1].message_type.value == "bridging"
        ]
        assert len(bridging_calls) == 1, (
            f"Expected 1 bridging call, got {len(bridging_calls)}"
        )
        bridging_msg = bridging_calls[0][0][1]
        assert bridging_msg.payload["signal_type"] == "confirm"
        assert bridging_msg.payload["continues_from"] == "old-gen-123"
        assert "new_generation_id" in bridging_msg.payload


# ---------------------------------------------------------------------------
# Fix #11: Buffered ADDITIVE flush on ResultMessage
# ---------------------------------------------------------------------------


class TestAdditiveFlushOnIdle:
    """Buffered ADDITIVEs should be flushed as plain user messages
    (sent via query()) when state transitions to IDLE."""

    @pytest.mark.asyncio
    async def test_flush_sends_combined_user_message(self, actor):
        actor._generation_state = GenerationState.GENERATING

        sig1 = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            signal_id="add-1",
            payload={"additional_input": "also consider the weather"},
        )
        sig2 = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            signal_id="add-2",
            payload={"additional_input": "budget under 5000"},
        )
        await actor._do_additive(sig1)
        await actor._do_additive(sig2)

        assert len(actor._buffered_additives) == 2
        actor._pooled.client.query.assert_not_called()

        # Simulate transition to IDLE by calling flush
        actor._generation_state = GenerationState.IDLE
        await actor._flush_buffered_additives()

        assert len(actor._buffered_additives) == 0
        actor._pooled.client.query.assert_called_once()
        call_arg = actor._pooled.client.query.call_args[0][0]
        # Should NOT use [SUPPLEMENTARY_INFO] wrapper (which suppresses replies)
        assert "[SUPPLEMENTARY_INFO]" not in call_arg
        assert "请回复用户" in call_arg
        assert "also consider the weather" in call_arg
        assert "budget under 5000" in call_arg

    @pytest.mark.asyncio
    async def test_flush_noop_when_empty(self, actor):
        assert len(actor._buffered_additives) == 0
        await actor._flush_buffered_additives()
        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_increments_additive_turn_counter(self, actor):
        actor._generation_state = GenerationState.GENERATING

        sig = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"additional_input": "add spicy food"},
        )
        await actor._do_additive(sig)

        initial_count = actor._additive_this_turn
        await actor._flush_buffered_additives()
        assert actor._additive_this_turn == initial_count + 1


# ---------------------------------------------------------------------------
# Fix #12: Sidekick urgency x state gating
# ---------------------------------------------------------------------------


class TestSidekickUrgencyStateGating:
    """Verify _do_sidekick enforces the urgency x state matrix from S3.3/S7.2:
    - IDLE: all urgencies inject
    - GENERATING: low/medium rejected, high buffered
    - TOOL_EXECUTING: low/medium rejected, high injects
    - WAITING_USER: low/medium rejected, high buffered
    """

    @pytest.mark.asyncio
    async def test_idle_low_urgency_injects(self, actor):
        actor._generation_state = GenerationState.IDLE
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "low", "insight_text": "Remember birthday"},
        )
        await actor._do_sidekick(signal)
        actor._pooled.client.query.assert_called_once()
        assert actor._sidekick_count_session == 1

    @pytest.mark.asyncio
    async def test_idle_high_urgency_injects(self, actor):
        actor._generation_state = GenerationState.IDLE
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "high", "insight_text": "Urgent reminder"},
        )
        await actor._do_sidekick(signal)
        actor._pooled.client.query.assert_called_once()
        assert actor._sidekick_count_session == 1

    @pytest.mark.asyncio
    async def test_generating_low_urgency_rejected(self, actor):
        actor._generation_state = GenerationState.GENERATING
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "low", "insight_text": "Low priority"},
        )
        await actor._do_sidekick(signal)
        actor._pooled.client.query.assert_not_called()
        assert len(actor._buffered_sidekicks) == 0

    @pytest.mark.asyncio
    async def test_generating_medium_urgency_rejected(self, actor):
        actor._generation_state = GenerationState.GENERATING
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "medium", "insight_text": "Medium priority"},
        )
        await actor._do_sidekick(signal)
        actor._pooled.client.query.assert_not_called()
        assert len(actor._buffered_sidekicks) == 0

    @pytest.mark.asyncio
    async def test_generating_high_urgency_buffered(self, actor):
        actor._generation_state = GenerationState.GENERATING
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "high", "insight_text": "High priority insight"},
        )
        await actor._do_sidekick(signal)
        actor._pooled.client.query.assert_not_called()
        assert len(actor._buffered_sidekicks) == 1

    @pytest.mark.asyncio
    async def test_tool_executing_low_urgency_rejected(self, actor):
        actor._generation_state = GenerationState.TOOL_EXECUTING
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "low", "insight_text": "Low during tool"},
        )
        await actor._do_sidekick(signal)
        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_tool_executing_high_urgency_injects(self, actor):
        actor._generation_state = GenerationState.TOOL_EXECUTING
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "high", "insight_text": "High during tool"},
        )
        await actor._do_sidekick(signal)
        actor._pooled.client.query.assert_called_once()
        assert actor._sidekick_count_session == 1

    @pytest.mark.asyncio
    async def test_waiting_user_medium_urgency_rejected(self, actor):
        actor._generation_state = GenerationState.WAITING_USER
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "medium", "insight_text": "Medium during wait"},
        )
        await actor._do_sidekick(signal)
        actor._pooled.client.query.assert_not_called()
        assert len(actor._buffered_sidekicks) == 0

    @pytest.mark.asyncio
    async def test_waiting_user_high_urgency_buffered(self, actor):
        actor._generation_state = GenerationState.WAITING_USER
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "high", "insight_text": "High during wait"},
        )
        await actor._do_sidekick(signal)
        actor._pooled.client.query.assert_not_called()
        assert len(actor._buffered_sidekicks) == 1

    @pytest.mark.asyncio
    async def test_sidekick_expired_signal_rejected(self, actor):
        """Sidekick signal with an expired expires_at should be rejected."""
        actor._generation_state = GenerationState.IDLE
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={
                "urgency": "high",
                "insight_text": "Expired insight",
                "expires_at": "2020-01-01T00:00:00Z",
            },
        )
        result = await actor._do_sidekick(signal)
        assert result == "reject_expired"
        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sidekick_non_expired_signal_not_rejected(self, actor):
        """Sidekick signal with a future expires_at should proceed normally."""
        actor._generation_state = GenerationState.IDLE
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={
                "urgency": "low",
                "insight_text": "Valid insight",
                "expires_at": "2099-12-31T23:59:59Z",
            },
        )
        result = await actor._do_sidekick(signal)
        assert result == "inject"
        actor._pooled.client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_sidekick_invalid_expires_at_does_not_reject(self, actor):
        """Sidekick signal with an invalid expires_at should not reject, just warn."""
        actor._generation_state = GenerationState.IDLE
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={
                "urgency": "low",
                "insight_text": "Some insight",
                "expires_at": "not-a-date",
            },
        )
        result = await actor._do_sidekick(signal)
        assert result == "inject"
        actor._pooled.client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_buffered_sidekick_flush_records_injection(self, actor):
        """Flushing buffered sidekicks should increment rate limit counters
        (fix for HIGH issue: flush bypassed rate limiting)."""
        actor._generation_state = GenerationState.GENERATING
        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "high", "insight_text": "Buffered insight"},
        )
        await actor._do_sidekick(signal)
        assert actor._sidekick_count_session == 0  # Not yet counted

        actor._generation_state = GenerationState.IDLE
        await actor._flush_buffered_sidekicks()

        actor._pooled.client.query.assert_called_once()
        assert actor._sidekick_count_session == 1
        assert actor._sidekick_count_turn == 1
        assert actor._last_sidekick_time is not None


# ---------------------------------------------------------------------------
# M7: _build_correction_prompt and _format_completed_tool_results
# ---------------------------------------------------------------------------


class TestBuildCorrectionPrompt:
    """Tests for _build_correction_prompt and _format_completed_tool_results.

    These methods format correction prompts with factual embedding wording
    and include tool input summaries from the current request.
    """

    def test_with_tool_input_summaries(self, actor):
        """Tool names should include input summaries from pending request."""
        mock_req = _make_pending_req(
            all_tool_calls=[{"name": "get_weather", "input": {"city": "Shanghai"}}],
        )
        actor._pending = deque([mock_req])

        stitch = StitchingContext(
            partial_text="",
            partial_thinking="",
            interrupted_at=datetime.now(timezone.utc),
            reason="correction",
            original_input="what is the weather",
            completed_tools=["get_weather"],
        )

        result = actor._build_correction_prompt("change to Beijing", stitch)

        assert "get_weather(" in result
        assert "Shanghai" in result
        assert "change to Beijing" in result

    def test_falls_back_to_plain_names_without_pending(self, actor):
        """Without pending requests, tool names should be joined by Chinese comma."""
        actor._pending = deque()

        stitch = StitchingContext(
            partial_text="",
            partial_thinking="",
            interrupted_at=datetime.now(timezone.utc),
            reason="correction",
            original_input="original",
            completed_tools=["get_weather", "query_tasks"],
        )

        result = actor._build_correction_prompt("fix it", stitch)

        assert "get_weather\u3001query_tasks" in result

    def test_partial_tool_dict_shows_uncompleted_wording(self, actor):
        """Partial tool as dict should show uncompleted wording."""
        stitch = StitchingContext(
            partial_text="",
            partial_thinking="",
            interrupted_at=datetime.now(timezone.utc),
            reason="correction",
            original_input="original",
            partial_tool={"name": "web_search", "input": {"q": "flights"}},
        )

        result = actor._build_correction_prompt("try again", stitch)

        assert "\u4f46\u64cd\u4f5c\u672a\u5b8c\u6210" in result
        assert "web_search" in result
        assert "flights" in result

    def test_partial_tool_string_legacy_fallback(self, actor):
        """Partial tool as string (legacy format) should still appear in prompt."""
        stitch = StitchingContext(
            partial_text="",
            partial_thinking="",
            interrupted_at=datetime.now(timezone.utc),
            reason="correction",
            original_input="original",
            partial_tool="legacy_tool",
        )

        result = actor._build_correction_prompt("fix it", stitch)

        assert "legacy_tool" in result
        assert "\u4f46\u64cd\u4f5c\u672a\u5b8c\u6210" in result

    def test_no_stitch_context(self, actor):
        """With no stitch context, result should be just the user instruction."""
        result = actor._build_correction_prompt("change to Beijing", stitch=None)

        assert result == "\u7528\u6237\u7684\u6700\u65b0\u6307\u793a\uff1achange to Beijing"

    def test_partial_text_truncated(self, actor):
        """Partial text longer than _STITCH_PARTIAL_TEXT_MAX_CHARS should be truncated."""
        long_text = "x" * 300

        stitch = StitchingContext(
            partial_text=long_text,
            partial_thinking="",
            interrupted_at=datetime.now(timezone.utc),
            reason="correction",
            original_input="original",
        )

        result = actor._build_correction_prompt("fix it", stitch)

        # The partial text in the result should be truncated to last 200 chars
        assert "\u4f60\u5df2\u7ecf\u56de\u590d\u4e86\u4ee5\u4e0b\u5185\u5bb9\uff1a" in result
        # The full 300-char string should NOT appear
        assert ("x" * 300) not in result
        # But the last 200 chars should
        assert ("x" * 200) in result

    def test_format_completed_tool_results_with_pending(self, actor):
        """_format_completed_tool_results should produce 'name(input)' format
        when pending request has matching tool calls."""
        mock_req = _make_pending_req(
            all_tool_calls=[
                {"name": "get_weather", "input": {"city": "Beijing"}},
                {"name": "query_tasks", "input": {"status": "active"}},
            ],
        )
        actor._pending = deque([mock_req])

        result = actor._format_completed_tool_results(
            ["get_weather", "query_tasks"],
        )

        assert "get_weather(" in result
        assert "Beijing" in result
        assert "query_tasks(" in result
        assert "active" in result
        # Tools should be joined by Chinese comma
        assert "\u3001" in result

    @pytest.mark.asyncio
    async def test_sidekick_session_rate_limit_rejects_at_max(self, actor):
        """When _sidekick_count_session reaches _MAX_SIDEKICK_PER_SESSION (3),
        further sidekick injections should be rejected even at IDLE with high
        urgency, because high urgency only bypasses the rate-limit check, but
        low/medium urgency at IDLE still goes through _check_sidekick_rate_limit."""
        from src.ai_engine.workers.reactive_session_actor import (
            _MAX_SIDEKICK_PER_SESSION,
        )

        actor._generation_state = GenerationState.IDLE
        # Saturate the session counter
        actor._sidekick_count_session = _MAX_SIDEKICK_PER_SESSION

        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={"urgency": "low", "insight_text": "Should be rejected"},
        )
        await actor._do_sidekick(signal)

        # Should NOT have injected -- rate limit hit
        actor._pooled.client.query.assert_not_called()
        # Counter should remain unchanged
        assert actor._sidekick_count_session == _MAX_SIDEKICK_PER_SESSION


# ---------------------------------------------------------------------------
# Fix #8: Session reset trigger when budget exceeded
# ---------------------------------------------------------------------------


class TestSessionResetTrigger:
    """Dispatching one more intervention when at budget limit should trigger
    _reset_session (Fix #8)."""

    @pytest.mark.asyncio
    async def test_session_reset_triggered_at_budget_limit(self, actor):
        # Set intervention count to the max (budget check is now pre-handler)
        actor._intervention_count = actor._budget.max_interventions_per_session
        actor._reset_session = AsyncMock()

        signal = _make_signal(signal_type=InterventionType.ADDITIVE.value)
        await actor._dispatch_signal(signal)

        actor._reset_session.assert_called_once()


# ---------------------------------------------------------------------------
# M5: Run-loop integration – signals dispatched from pending queue
# ---------------------------------------------------------------------------


class TestSignalDispatchLoop:
    """Test that signals enqueued to _pending_interventions get dispatched."""

    @pytest.mark.asyncio
    async def test_signal_dispatched_from_pending_queue(self, actor):
        """Signal enqueued during GENERATING state is dispatched by the handler loop."""
        actor._generation_state = GenerationState.GENERATING
        actor._pooled.client.query = AsyncMock()
        actor._pooled.client.interrupt = AsyncMock()

        # Create an ADDITIVE signal (simplest to verify – just buffers)
        signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"additional_input": "also check the weather"},
        )

        # Dispatch directly (simulates the main loop picking up from queue)
        await actor._dispatch_signal(signal)

        # ADDITIVE during GENERATING should buffer, not query
        assert len(actor._buffered_additives) == 1
        assert actor._intervention_count == 1

    @pytest.mark.asyncio
    async def test_correction_dispatched_during_generating(self, actor):
        """CORRECTION during GENERATING should interrupt and query."""
        actor._generation_state = GenerationState.GENERATING
        actor._pooled.client.interrupt = AsyncMock()
        actor._pooled.client.query = AsyncMock()
        # Need to mock _emit_partial_content and _emit_bridging
        actor._emit_partial_content = AsyncMock()
        actor._emit_bridging = AsyncMock()
        actor._save_stitching_context_from_obj = AsyncMock()

        # Add a pending request with AsyncMock pubsub (for _emit_state_change_nowait)
        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"corrected_input": "change to Shanghai"},
            priority=1,
        )

        await actor._dispatch_signal(signal)

        # Should have interrupted and queried
        actor._pooled.client.interrupt.assert_called_once()
        actor._pooled.client.query.assert_called_once()
        assert actor._correction_count == 1


# ---------------------------------------------------------------------------
# M6: CANCEL during WAITING_USER
# ---------------------------------------------------------------------------


class TestCancelDuringWaitingUser:
    """Test CANCEL handling during WAITING_USER state."""

    @pytest.mark.asyncio
    async def test_cancel_during_waiting_user_interrupts_and_idles(self, actor):
        """CANCEL during WAITING_USER should interrupt, emit partial, and go IDLE."""
        actor._generation_state = GenerationState.WAITING_USER
        actor._pooled.client.interrupt = AsyncMock()
        actor._emit_partial_content = AsyncMock()
        actor._emit_done_for_cancel = AsyncMock()
        actor._invalidate_ctx_cache = AsyncMock()

        # Need a pending request with AsyncMock pubsub (for _emit_state_change_nowait)
        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        cancel_signal = _make_signal(signal_type=InterventionType.CANCEL.value, priority=0)
        await actor._do_cancel(cancel_signal)

        # Should have interrupted
        actor._pooled.client.interrupt.assert_called_once()
        # Should have emitted done
        actor._emit_done_for_cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_during_waiting_user_proceeds_despite_active_tool(self, actor):
        """W2: CANCEL during WAITING_USER should NOT defer even if _active_tool
        is set. The non-interruptible check only applies to TOOL_EXECUTING."""
        actor._generation_state = GenerationState.WAITING_USER
        actor._active_tool = "send_message"  # Would defer in TOOL_EXECUTING, not WAITING_USER
        actor._pooled.client.interrupt = AsyncMock()
        actor._emit_partial_content = AsyncMock()
        actor._emit_done_for_cancel = AsyncMock()
        actor._invalidate_ctx_cache = AsyncMock()

        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        cancel_signal = _make_signal(signal_type=InterventionType.CANCEL.value, priority=0)
        result = await actor._do_cancel(cancel_signal)

        assert result == "cancelled"
        assert actor._deferred_intervention is None
        actor._pooled.client.interrupt.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_clears_all_signal_buffers(self, actor):
        """W1: After cancel, all three signal buffers (additives, confirms,
        sidekicks) must be cleared to prevent stale data leaking into the
        next generation."""
        actor._generation_state = GenerationState.GENERATING
        actor._pooled.client.interrupt = AsyncMock()
        actor._emit_partial_content = AsyncMock()
        actor._emit_done_for_cancel = AsyncMock()
        actor._invalidate_ctx_cache = AsyncMock()

        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        # Pre-populate all three buffers
        actor._buffered_additives.append(
            _make_signal(signal_type=InterventionType.ADDITIVE.value)
        )
        actor._buffered_confirms.append(
            _make_signal(signal_type=InterventionType.CONFIRM.value)
        )
        actor._buffered_sidekicks.append(
            _make_signal(signal_type=InterventionType.SIDEKICK_INSIGHT.value)
        )
        assert len(actor._buffered_additives) == 1
        assert len(actor._buffered_confirms) == 1
        assert len(actor._buffered_sidekicks) == 1

        cancel_signal = _make_signal(signal_type=InterventionType.CANCEL.value, priority=0)
        result = await actor._do_cancel(cancel_signal)

        assert result == "cancelled"
        assert len(actor._buffered_additives) == 0
        assert len(actor._buffered_confirms) == 0
        assert len(actor._buffered_sidekicks) == 0

    @pytest.mark.asyncio
    async def test_cancel_sets_idle_after_interrupt(self, actor):
        """CANCEL should set state to IDLE immediately after interrupt,
        before emitting partial_content and done events."""
        actor._generation_state = GenerationState.GENERATING
        actor._pooled.client.interrupt = AsyncMock()

        states_during_emit = []

        async def capture_state_on_partial(**kwargs):
            states_during_emit.append(actor._generation_state)

        actor._emit_partial_content = AsyncMock(side_effect=capture_state_on_partial)
        actor._emit_done_for_cancel = AsyncMock()
        actor._invalidate_ctx_cache = AsyncMock()

        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        cancel_signal = _make_signal(signal_type=InterventionType.CANCEL.value, priority=0)
        await actor._do_cancel(cancel_signal)

        # State should have been IDLE when _emit_partial_content was called
        assert states_during_emit[0] == GenerationState.IDLE


# ---------------------------------------------------------------------------
# CORRECTION during TOOL_EXECUTING sets IDLE after interrupt
# ---------------------------------------------------------------------------


class TestCorrectionIdleAfterInterrupt:
    """CORRECTION during GENERATING/TOOL_EXECUTING should set state to
    IDLE immediately after interrupt, before stitching work."""

    @pytest.mark.asyncio
    async def test_correction_sets_idle_after_interrupt_during_generating(self, actor):
        """CORRECTION during GENERATING sets state to IDLE right after interrupt."""
        actor._generation_state = GenerationState.GENERATING
        actor._pooled.client.interrupt = AsyncMock()
        actor._pooled.client.query = AsyncMock()
        actor._save_stitching_context_from_obj = AsyncMock()

        states_during_emit = []

        async def capture_state_on_partial(**kwargs):
            states_during_emit.append(actor._generation_state)

        actor._emit_partial_content = AsyncMock(side_effect=capture_state_on_partial)
        actor._emit_bridging = AsyncMock()

        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"corrected_input": "fix this"},
        )
        await actor._do_correction(signal)

        # State should have been IDLE when _emit_partial_content was called
        assert states_during_emit[0] == GenerationState.IDLE

    @pytest.mark.asyncio
    async def test_correction_sets_idle_after_interrupt_during_tool_executing(self, actor):
        """CORRECTION during interruptible TOOL_EXECUTING sets state to IDLE
        right after interrupt."""
        actor._generation_state = GenerationState.TOOL_EXECUTING
        actor._active_tool = "query_weather"  # interruptible
        actor._pooled.client.interrupt = AsyncMock()
        actor._pooled.client.query = AsyncMock()
        actor._save_stitching_context_from_obj = AsyncMock()

        states_during_emit = []

        async def capture_state_on_partial(**kwargs):
            states_during_emit.append(actor._generation_state)

        actor._emit_partial_content = AsyncMock(side_effect=capture_state_on_partial)
        actor._emit_bridging = AsyncMock()

        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"corrected_input": "fix this"},
        )
        await actor._do_correction(signal)

        # State should have been IDLE when _emit_partial_content was called
        assert states_during_emit[0] == GenerationState.IDLE


# ---------------------------------------------------------------------------
# W3: CORRECTION during WAITING_USER saves stitching context
# ---------------------------------------------------------------------------


class TestCorrectionWaitingUserStitching:
    """W3: CORRECTION during WAITING_USER must save stitching context for
    crash recovery, same as the GENERATING path."""

    @pytest.mark.asyncio
    async def test_correction_waiting_user_saves_stitching_context(self, actor):
        """CORRECTION during WAITING_USER should call
        _save_stitching_context_from_obj with a stitch containing
        reason='correction'."""
        actor._generation_state = GenerationState.WAITING_USER
        actor._pooled.client.interrupt = AsyncMock()
        actor._pooled.client.query = AsyncMock()
        actor._save_stitching_context_from_obj = AsyncMock()
        actor._emit_partial_content = AsyncMock()
        actor._emit_bridging = AsyncMock()

        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"corrected_input": "change to Shanghai"},
        )
        result = await actor._do_correction(signal)

        assert result == "interrupt_and_query"
        actor._pooled.client.interrupt.assert_called_once()
        actor._pooled.client.query.assert_called_once()
        # Stitching context must have been saved (via asyncio.create_task)
        # The task calls _save_stitching_context_from_obj with the stitch object
        # We verify it was scheduled by checking the mock was called
        actor._save_stitching_context_from_obj.assert_called_once()
        saved_stitch = actor._save_stitching_context_from_obj.call_args[0][0]
        assert saved_stitch.reason == "correction"

    @pytest.mark.asyncio
    async def test_correction_waiting_user_emits_bridging_with_continues_from(self, actor):
        """W3: CORRECTION during WAITING_USER should emit a BRIDGING event
        linking old → new generation_id."""
        actor._generation_state = GenerationState.WAITING_USER
        actor._current_generation_id = "old-gen-456"
        actor._pooled.client.interrupt = AsyncMock()
        actor._pooled.client.query = AsyncMock()
        actor._save_stitching_context_from_obj = AsyncMock()
        actor._emit_partial_content = AsyncMock()

        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        bridging_calls = []
        original_emit_bridging = actor._emit_bridging

        async def capture_bridging(*args, **kwargs):
            bridging_calls.append((args, kwargs))

        actor._emit_bridging = AsyncMock(side_effect=capture_bridging)

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"corrected_input": "go to Shanghai instead"},
        )
        await actor._do_correction(signal)

        actor._emit_bridging.assert_called_once()
        call_args = actor._emit_bridging.call_args
        assert call_args[0][0] == "correction"
        assert call_args.kwargs.get("continues_from") == "old-gen-456"

    @pytest.mark.asyncio
    async def test_correction_waiting_user_sets_idle_before_emit(self, actor):
        """W3: CORRECTION during WAITING_USER should set state to IDLE
        before emitting partial content."""
        actor._generation_state = GenerationState.WAITING_USER
        actor._pooled.client.interrupt = AsyncMock()
        actor._pooled.client.query = AsyncMock()
        actor._save_stitching_context_from_obj = AsyncMock()
        actor._emit_bridging = AsyncMock()

        states_during_emit = []

        async def capture_state(**kwargs):
            states_during_emit.append(actor._generation_state)

        actor._emit_partial_content = AsyncMock(side_effect=capture_state)

        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()
        mock_req = _make_pending_req(pubsub=mock_pubsub)
        actor._pending.append(mock_req)

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"corrected_input": "fix this"},
        )
        await actor._do_correction(signal)

        assert states_during_emit[0] == GenerationState.IDLE


# ---------------------------------------------------------------------------
# W4: CONFIRM with is_ambiguous flag
# ---------------------------------------------------------------------------


class TestConfirmAmbiguousFlag:
    """W4: When the signal payload has is_ambiguous=True, the actor should
    produce a prompt that instructs the Agent to verify before executing
    destructive operations."""

    @pytest.mark.asyncio
    async def test_ambiguous_confirm_prompt_contains_verification_instruction(self, actor):
        """Ambiguous CONFIRM should produce a prompt with '措辞不够明确'."""
        actor._generation_state = GenerationState.IDLE

        signal = _make_signal(
            signal_type=InterventionType.CONFIRM.value,
            payload={
                "pending_action_id": "action-ambig-1",
                "confirmation": "approve",
                "is_ambiguous": True,
                "text": "我看看",
            },
        )
        await actor._do_confirm(signal)

        actor._pooled.client.query.assert_called_once()
        prompt = actor._pooled.client.query.call_args[0][0]
        assert "措辞不够明确" in prompt
        assert "action-ambig-1" in prompt
        assert "我看看" in prompt

    @pytest.mark.asyncio
    async def test_non_ambiguous_confirm_uses_standard_prompt(self, actor):
        """Non-ambiguous CONFIRM (is_ambiguous=False or missing) should use
        the standard '用户已确认执行操作' prompt."""
        actor._generation_state = GenerationState.IDLE

        signal = _make_signal(
            signal_type=InterventionType.CONFIRM.value,
            payload={
                "pending_action_id": "action-clear-1",
                "confirmation": "approve",
            },
        )
        await actor._do_confirm(signal)

        actor._pooled.client.query.assert_called_once()
        prompt = actor._pooled.client.query.call_args[0][0]
        assert "用户已确认执行操作" in prompt
        assert "措辞不够明确" not in prompt


# ---------------------------------------------------------------------------
# _defer_intervention priority logic (M1)
# ---------------------------------------------------------------------------


class TestDeferInterventionPriority:
    """Test priority-based deferred intervention logic (M1)."""

    def test_cancel_always_wins(self, actor):
        """CANCEL should overwrite any existing deferred signal."""
        existing = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            priority=1,
        )
        actor._deferred_intervention = existing

        cancel = _make_signal(
            signal_type=InterventionType.CANCEL.value,
            priority=0,
        )
        actor._defer_intervention(cancel)

        assert actor._deferred_intervention is cancel

    def test_cannot_overwrite_cancel(self, actor):
        """Non-CANCEL signal should not overwrite existing CANCEL."""
        cancel = _make_signal(
            signal_type=InterventionType.CANCEL.value,
            priority=0,
        )
        actor._deferred_intervention = cancel

        correction = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            priority=1,
        )
        actor._defer_intervention(correction)

        assert actor._deferred_intervention is cancel

    def test_higher_priority_overwrites_lower(self, actor):
        """Higher priority (lower number) should overwrite lower priority."""
        low_priority = _make_signal(
            signal_type=InterventionType.DIGRESSION.value,
            priority=3,
        )
        actor._deferred_intervention = low_priority

        high_priority = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            priority=1,
        )
        actor._defer_intervention(high_priority)

        assert actor._deferred_intervention is high_priority

    def test_lower_priority_dropped(self, actor):
        """Lower priority signal should be dropped when higher exists."""
        high_priority = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            priority=1,
        )
        actor._deferred_intervention = high_priority

        low_priority = _make_signal(
            signal_type=InterventionType.DIGRESSION.value,
            priority=3,
        )
        actor._defer_intervention(low_priority)

        assert actor._deferred_intervention is high_priority

    def test_equal_priority_last_write_wins(self, actor):
        """Equal priority should use last-write-wins."""
        first = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            priority=2,
        )
        actor._deferred_intervention = first

        second = _make_signal(
            signal_type=InterventionType.CONFIRM.value,
            priority=2,
        )
        actor._defer_intervention(second)

        assert actor._deferred_intervention is second

    def test_defer_into_empty_slot(self, actor):
        """Deferring when no existing signal should simply set it."""
        assert actor._deferred_intervention is None

        signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            priority=1,
        )
        actor._defer_intervention(signal)

        assert actor._deferred_intervention is signal
