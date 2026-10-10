"""Budget, session reset, context compression, and crash recovery tests
for ReactiveSessionActor.

Covers intervention budget enforcement, additive per-turn budget,
budget-exceeded session reset, deferred budget recheck, cancel budget
exemption, session reset with teardown, context compression, and
worker crash recovery.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claude_agent_sdk import ResultMessage

from src.ai_engine.intervention.types import (
    GenerationState,
    InterventionType,
    StitchingContext,
)

from tests.unit.reactive_actor_helpers import _make_pending_req, _make_signal


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


class TestInterventionBudget:
    def test_default_budget_values(self, actor):
        assert actor._budget.max_interventions_per_session == 5
        assert actor._budget.max_correction_per_session == 3
        assert actor._budget.max_additive_per_turn == 2
        assert actor._budget.context_compression_threshold == 3

    def test_budget_counters_start_at_zero(self, actor):
        assert actor._intervention_count == 0
        assert actor._correction_count == 0

    def test_additive_per_turn_counter_starts_at_zero(self, actor):
        assert actor._additive_this_turn == 0


# ---------------------------------------------------------------------------
# Additive per-turn budget enforcement
# ---------------------------------------------------------------------------


class TestAdditivePerTurnBudget:
    @pytest.mark.asyncio
    async def test_additive_buffered_when_per_turn_budget_reached(self, actor):
        """ADDITIVE signals should be buffered (not dropped) when per-turn budget
        is exhausted during non-IDLE states."""
        actor._set_state(GenerationState.GENERATING)
        actor._additive_this_turn = actor._budget.max_additive_per_turn

        signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"text": "extra info"},
        )
        await actor._do_additive(signal)

        assert len(actor._buffered_additives) == 1
        actor._pooled.client.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_additive_allowed_when_idle_despite_budget(self, actor):
        """ADDITIVE during IDLE should always be allowed regardless of per-turn counter,
        because IDLE means a new turn."""
        actor._set_state(GenerationState.IDLE)
        actor._additive_this_turn = actor._budget.max_additive_per_turn

        signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"text": "new query"},
        )
        await actor._do_additive(signal)

        actor._pooled.client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_additive_increments_per_turn_counter(self, actor):
        """Additive during GENERATING is buffered, so _additive_this_turn stays 0."""
        actor._set_state(GenerationState.GENERATING)
        assert actor._additive_this_turn == 0

        signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"text": "info"},
        )
        await actor._do_additive(signal)

        # Buffering during GENERATING does NOT increment the counter
        assert actor._additive_this_turn == 0
        assert len(actor._buffered_additives) == 1

    @pytest.mark.asyncio
    async def test_additive_counter_resets_on_idle_transition(self, actor):
        """_additive_this_turn should reset to 0 when the actor transitions
        to IDLE via _handle_message processing a ResultMessage."""
        actor._additive_this_turn = 2
        actor._set_state(GenerationState.GENERATING)

        mock_future = asyncio.get_event_loop().create_future()
        mock_req = _make_pending_req(
            future=mock_future,
            all_text=["some text"],
        )
        actor._pending.append(mock_req)
        actor._pool = MagicMock()
        actor._pool.mark_used = AsyncMock()

        # Simulate ResultMessage
        result_msg = MagicMock(spec=ResultMessage)
        result_msg.subtype = "end_turn"
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.01
        result_msg.usage = {}
        result_msg.session_id = "sdk-session"

        await actor._handle_message(result_msg)

        assert actor._additive_this_turn == 0
        assert actor._generation_state == GenerationState.IDLE

    @pytest.mark.asyncio
    async def test_additive_counter_resets_on_session_reset(self, actor):
        """_reset_session should zero out _additive_this_turn."""
        actor._additive_this_turn = 2
        actor._intervention_count = 10
        actor._correction_count = 5
        actor._interrupt_sdk = AsyncMock()
        actor._teardown_client = AsyncMock()

        await actor._reset_session()

        assert actor._additive_this_turn == 0

    @pytest.mark.asyncio
    async def test_additive_tool_executing_increments_counter(self, actor):
        """ADDITIVE during TOOL_EXECUTING should also increment the counter."""
        actor._set_state(GenerationState.TOOL_EXECUTING)
        actor._active_tool = "query_weather"
        assert actor._additive_this_turn == 0

        signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"text": "also check humidity"},
        )
        await actor._do_additive(signal)

        assert actor._additive_this_turn == 1
        actor._pooled.client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_additive_tool_executing_rejected_at_budget(self, actor):
        """ADDITIVE during TOOL_EXECUTING should be rejected when budget reached."""
        actor._set_state(GenerationState.TOOL_EXECUTING)
        actor._active_tool = "query_weather"
        actor._additive_this_turn = actor._budget.max_additive_per_turn

        signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"text": "too many"},
        )
        await actor._do_additive(signal)

        actor._pooled.client.query.assert_not_called()


# ---------------------------------------------------------------------------
# Additive counter at flush time (P2)
# ---------------------------------------------------------------------------


class TestAdditiveCounterAtFlushTime:
    @pytest.mark.asyncio
    async def test_additive_buffer_does_not_increment_counter(self, actor):
        """Buffering an additive during GENERATING should NOT increment
        _additive_this_turn (counter is deferred to flush time)."""
        actor._set_state(GenerationState.GENERATING)

        signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"text": "some info"},
        )
        await actor._do_additive(signal)

        assert actor._additive_this_turn == 0
        assert len(actor._buffered_additives) == 1

    @pytest.mark.asyncio
    async def test_flush_increments_counter(self, actor):
        """_flush_buffered_additives should increment _additive_this_turn
        by the number of flushed signals (one per signal, not per batch)."""
        actor._buffered_additives = [
            _make_signal(payload={"text": "info A"}),
            _make_signal(payload={"text": "info B"}),
        ]
        assert actor._additive_this_turn == 0

        await actor._flush_buffered_additives()

        assert actor._additive_this_turn == 2
        actor._pooled.client.query.assert_called_once()


# ---------------------------------------------------------------------------
# Boundary: Budget-exceeded session reset
# ---------------------------------------------------------------------------


class TestBudgetExceededSessionReset:
    @pytest.mark.asyncio
    async def test_intervention_budget_exceeded_triggers_reset(self, actor):
        """When intervention_count >= max_interventions_per_session at dispatch
        time, the pre-handler budget check rejects the signal and triggers
        _reset_session (handler is NOT called)."""
        actor._reset_session = AsyncMock()
        actor._do_additive = AsyncMock()
        # Set count AT max so the pre-handler check triggers reset
        actor._intervention_count = actor._budget.max_interventions_per_session

        signal = _make_signal(signal_type=InterventionType.ADDITIVE.value)
        await actor._dispatch_signal(signal)

        # Pre-handler budget check blocks the handler and triggers reset
        actor._do_additive.assert_not_called()
        actor._reset_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_correction_budget_exceeded_triggers_reset(self, actor):
        """When correction_count >= max_correction_per_session at dispatch
        time, the pre-handler budget check rejects the signal and triggers
        _reset_session (handler is NOT called)."""
        actor._reset_session = AsyncMock()
        actor._do_correction = AsyncMock()
        # Set correction count AT max so the pre-handler check triggers reset
        actor._correction_count = actor._budget.max_correction_per_session

        signal = _make_signal(signal_type=InterventionType.CORRECTION.value)
        await actor._dispatch_signal(signal)

        # Pre-handler budget check blocks the handler and triggers reset
        actor._do_correction.assert_not_called()
        actor._reset_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_session_clears_counters(self, actor):
        """_reset_session should zero out all intervention counters and buffers."""
        actor._intervention_count = 10
        actor._correction_count = 5
        actor._additive_this_turn = 2
        actor._sidekick_count_session = 2
        actor._sidekick_count_turn = 1
        actor._interrupt_sdk = AsyncMock()
        actor._teardown_client = AsyncMock()

        await actor._reset_session()

        assert actor._intervention_count == 0
        assert actor._correction_count == 0
        assert actor._additive_this_turn == 0
        assert actor._sidekick_count_session == 0
        assert actor._sidekick_count_turn == 0
        assert actor._last_sidekick_time is None
        assert actor._buffered_confirms == []
        assert actor._buffered_sidekicks == []
        assert actor._buffered_additives == []
        assert actor._generation_state == GenerationState.IDLE


# ---------------------------------------------------------------------------
# Deferred budget recheck (P6)
# ---------------------------------------------------------------------------


class TestDeferredBudgetRecheck:
    @pytest.mark.asyncio
    async def test_deferred_skipped_when_budget_exceeded(self, actor):
        """Deferred intervention should be dropped when budget has been
        exceeded during the deferral period."""
        deferred_signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"text": "deferred correction"},
        )
        actor._deferred_intervention = deferred_signal
        actor._intervention_count = actor._budget.max_interventions_per_session

        actor._do_correction = AsyncMock()

        await actor._handle_deferred_intervention()

        # Handler should NOT be called since budget is exceeded
        actor._do_correction.assert_not_called()
        # Deferred should be cleared
        assert actor._deferred_intervention is None

    @pytest.mark.asyncio
    async def test_deferred_dropped_decrements_intervention_count(self, actor):
        """When a deferred intervention is dropped due to budget exceeded,
        the intervention_count should be decremented (it was pre-incremented
        at initial _dispatch_signal time)."""
        deferred_signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"text": "deferred additive"},
        )
        actor._deferred_intervention = deferred_signal
        actor._intervention_count = actor._budget.max_interventions_per_session

        actor._do_additive = AsyncMock()

        await actor._handle_deferred_intervention()

        actor._do_additive.assert_not_called()
        # Counter should have been decremented
        assert actor._intervention_count == actor._budget.max_interventions_per_session - 1

    @pytest.mark.asyncio
    async def test_deferred_dropped_decrements_correction_count(self, actor):
        """When a deferred CORRECTION is dropped due to budget exceeded,
        both intervention_count and correction_count should be decremented."""
        deferred_signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"text": "deferred correction"},
        )
        actor._deferred_intervention = deferred_signal
        actor._intervention_count = actor._budget.max_interventions_per_session
        actor._correction_count = 2

        actor._do_correction = AsyncMock()

        await actor._handle_deferred_intervention()

        actor._do_correction.assert_not_called()
        assert actor._intervention_count == actor._budget.max_interventions_per_session - 1
        assert actor._correction_count == 1

    @pytest.mark.asyncio
    async def test_deferred_dropped_counters_never_go_negative(self, actor):
        """Counter decrements on deferred drop should be clamped to zero."""
        deferred_signal = _make_signal(
            signal_type=InterventionType.CORRECTION.value,
            payload={"text": "deferred correction"},
        )
        actor._deferred_intervention = deferred_signal
        # Force budget exceeded with counters at zero (edge case)
        actor._intervention_count = 0
        actor._correction_count = actor._budget.max_correction_per_session

        actor._do_correction = AsyncMock()

        await actor._handle_deferred_intervention()

        actor._do_correction.assert_not_called()
        assert actor._intervention_count == 0
        assert actor._correction_count == actor._budget.max_correction_per_session - 1


# ---------------------------------------------------------------------------
# CANCEL exempt from budget (HIGH-1)
# ---------------------------------------------------------------------------


class TestCancelExemptFromBudget:
    @pytest.mark.asyncio
    async def test_cancel_not_blocked_by_exhausted_budget(self, actor):
        """CANCEL should execute even when intervention budget is exhausted."""
        actor._do_cancel = AsyncMock()
        actor._reset_session = AsyncMock()
        # Exhaust the budget
        actor._intervention_count = actor._budget.max_interventions_per_session + 10

        signal = _make_signal(signal_type=InterventionType.CANCEL.value)
        await actor._dispatch_signal(signal)

        # CANCEL should still be called
        actor._do_cancel.assert_called_once_with(signal)
        # Budget should not be incremented
        assert actor._intervention_count == actor._budget.max_interventions_per_session + 10
        # Reset should NOT be triggered by CANCEL
        actor._reset_session.assert_not_called()


# ---------------------------------------------------------------------------
# FIX 2: Session reset with SDK teardown
# ---------------------------------------------------------------------------


class TestSessionResetWithTeardown:
    @pytest.mark.asyncio
    async def test_reset_session_tears_down_client(self, actor):
        """_reset_session should tear down the SDK client."""
        actor._intervention_count = 10
        actor._correction_count = 5
        actor._interrupt_sdk = AsyncMock()
        actor._teardown_client = AsyncMock()

        await actor._reset_session()

        actor._teardown_client.assert_called_once_with(mark_disconnected=True)

    @pytest.mark.asyncio
    async def test_reset_session_builds_summary(self, actor):
        """_reset_session should build summary from stitch history."""
        actor._interrupt_sdk = AsyncMock()
        actor._teardown_client = AsyncMock()
        # Add stitch history
        actor._stitch_history = [
            StitchingContext(
                partial_text="partial response about weather",
                partial_thinking="",
                interrupted_at=__import__("datetime").datetime(2026, 2, 22),
                reason="correction",
                original_input="weather query",
                completed_tools=["query_weather", "format_result"],
            )
        ]
        actor._signal_redis = AsyncMock()
        actor._signal_redis.setex = AsyncMock()

        await actor._reset_session()

        # Summary should have been stored in Redis
        actor._signal_redis.setex.assert_called()
        call_args = actor._signal_redis.setex.call_args[0]
        assert call_args[0].startswith("session:reset:")
        summary = call_args[2]
        assert "Previous context" in summary
        assert "query_weather" in summary


# ---------------------------------------------------------------------------
# FIX 8: Context compression produces summary
# ---------------------------------------------------------------------------


class TestContextCompression:
    @pytest.mark.asyncio
    async def test_compress_stores_summary_in_redis(self, actor):
        """_compress_context_if_needed should build summary from stitch history
        and store in Redis."""
        actor._stitch_history = [
            StitchingContext(
                partial_text="weather response",
                partial_thinking="",
                interrupted_at=__import__("datetime").datetime(2026, 2, 22),
                reason="correction",
                original_input="check weather",
                completed_tools=["query_weather"],
            )
        ]
        actor._signal_redis = AsyncMock()
        actor._signal_redis.setex = AsyncMock()
        actor._signal_redis.scan = AsyncMock(return_value=(0, []))

        await actor._compress_context_if_needed()

        actor._signal_redis.setex.assert_called_once()
        call_args = actor._signal_redis.setex.call_args[0]
        assert call_args[0].startswith("session:compressed:")
        summary = call_args[2]
        assert "Previous context" in summary
        assert "query_weather" in summary

    def test_build_reset_summary_empty_history(self, actor):
        """_build_reset_summary should return empty string when no history."""
        assert actor._build_reset_summary() == ""

    def test_build_reset_summary_with_history(self, actor):
        """_build_reset_summary should combine partial texts and tools."""
        actor._stitch_history = [
            StitchingContext(
                partial_text="response A",
                partial_thinking="",
                interrupted_at=__import__("datetime").datetime(2026, 2, 22),
                reason="correction",
                original_input="input A",
                completed_tools=["tool_a"],
            ),
            StitchingContext(
                partial_text="response B",
                partial_thinking="",
                interrupted_at=__import__("datetime").datetime(2026, 2, 22),
                reason="correction",
                original_input="input B",
                completed_tools=["tool_b", "tool_a"],
            ),
        ]
        summary = actor._build_reset_summary()
        assert "response A" in summary
        assert "response B" in summary
        assert "tool_a" in summary
        assert "tool_b" in summary

    def test_build_reset_summary_includes_pending_request(self, actor):
        """_build_reset_summary should include user input and accumulated text
        from the current pending request."""
        mock_req = _make_pending_req(
            user_input="帮我查北京天气",
            all_text=["北京今天的天气是", "晴，温度25度"],
        )
        actor._pending.append(mock_req)

        summary = actor._build_reset_summary()
        assert "帮我查北京天气" in summary
        assert "晴，温度25度" in summary


# ---------------------------------------------------------------------------
# Worker crash recovery tests (Fix 9)
# ---------------------------------------------------------------------------


class TestWorkerCrashRecovery:
    @pytest.mark.asyncio
    async def test_stale_heartbeat_returns_none(self):
        """_get_session_status should return None for stale heartbeats (>30s)."""
        from datetime import datetime, timedelta, timezone

        from src.ai_engine.intervention.types import SessionStatus

        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat()
        status_json = SessionStatus(
            state="generating",
            job_id="test-job",
            worker_id="w1",
            sdk_session_id="sdk-1",
            last_heartbeat=stale_time,
            task_summary="test task",
            active_tool=None,
            user_id="user-1",
        ).to_json()

        with patch("src.core.cache.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=status_json)

            from src.api.v1.chat import _get_session_status
            result = await _get_session_status("test-session-id")

            assert result is None

    @pytest.mark.asyncio
    async def test_fresh_heartbeat_returns_status(self):
        """_get_session_status should return status for fresh heartbeats (<30s)."""
        from datetime import datetime, timezone

        from src.ai_engine.intervention.types import SessionStatus

        fresh_time = datetime.now(timezone.utc).isoformat()
        status_json = SessionStatus(
            state="generating",
            job_id="test-job",
            worker_id="w1",
            sdk_session_id="sdk-1",
            last_heartbeat=fresh_time,
            task_summary="test task",
            active_tool=None,
            user_id="user-1",
        ).to_json()

        with patch("src.core.cache.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=status_json)

            from src.api.v1.chat import _get_session_status
            result = await _get_session_status("test-session-id")

            assert result is not None
            assert result.state == "generating"
            assert result.job_id == "test-job"

    @pytest.mark.asyncio
    async def test_missing_status_returns_none(self):
        """_get_session_status should return None when no status exists in Redis."""
        with patch("src.core.cache.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)

            from src.api.v1.chat import _get_session_status
            result = await _get_session_status("nonexistent-session")

            assert result is None

    @pytest.mark.asyncio
    async def test_redis_error_returns_none(self):
        """_get_session_status should return None on Redis errors."""
        with patch("src.core.cache.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))

            from src.api.v1.chat import _get_session_status
            result = await _get_session_status("test-session")

            assert result is None
