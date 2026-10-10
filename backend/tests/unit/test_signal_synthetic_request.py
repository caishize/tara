"""Tests for signal-initiated synthetic _StreamingRequest creation.

Verifies that when signal handlers call _query_sdk() with empty _pending,
a synthetic request is created so SDK responses are properly consumed
and streamed to the user via WebSocket.
"""

import asyncio
from collections import deque
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai_engine.intervention.types import (
    GenerationState,
    InterventionType,
)
from src.ai_engine.sdk.pooled_context import PooledToolContext
from src.ai_engine.sdk.sdk_stream_handler import SDKStreamHandler
from src.ai_engine.workers.reactive_session_actor import (
    ReactiveSessionActor,
    _StreamingRequest,
)
from tests.unit.reactive_actor_helpers import _make_signal


# ---------------------------------------------------------------------------
# _build_signal_request
# ---------------------------------------------------------------------------


class TestBuildSignalRequest:
    """Tests for _build_signal_request() method."""

    @pytest.mark.asyncio
    async def test_returns_streaming_request_when_context_available(self, actor):
        """Should return a _StreamingRequest when ctx and last_runner exist."""
        result = actor._build_signal_request(source="test_signal")

        assert result is not None
        assert isinstance(result, _StreamingRequest)
        assert result.worker is actor._ctx.worker
        assert result.runner is actor._last_runner
        assert result.run_config is actor._last_run_config
        assert result.hook_builder is actor._last_hook_builder
        assert result.task is actor._ctx.task
        assert result.pubsub is actor._ctx.pubsub
        assert not result.future.done()

    @pytest.mark.asyncio
    async def test_returns_none_when_ctx_missing(self, actor):
        """Should return None when _ctx is not set."""
        actor._ctx = None

        result = actor._build_signal_request(source="test_signal")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_last_runner_missing(self, actor):
        """Should return None when no prior request has completed."""
        actor._last_runner = None

        result = actor._build_signal_request(source="test_signal")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_worker_missing(self, actor):
        """Should return None when ctx.worker is not set."""
        actor._ctx.worker = None

        result = actor._build_signal_request(source="test_signal")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_task_missing(self, actor):
        """Should return None when ctx.task is not set."""
        actor._ctx.task = None

        result = actor._build_signal_request(source="test_signal")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_pubsub_missing(self, actor):
        """Should return None when ctx.pubsub is not set."""
        actor._ctx.pubsub = None

        result = actor._build_signal_request(source="test_signal")

        assert result is None

    @pytest.mark.asyncio
    async def test_creates_sdk_stream_handler_with_publish_fn(self, actor):
        """Should create SDKStreamHandler using worker's publish fn factory."""
        result = actor._build_signal_request(source="test_signal")

        assert result is not None
        assert isinstance(result.sdk_stream_handler, SDKStreamHandler)
        actor._ctx.worker._make_pubsub_publish_fn.assert_called_once_with(
            actor._ctx.pubsub, actor._ctx.task
        )

    @pytest.mark.asyncio
    async def test_sets_generation_context_with_source(self, actor):
        """Should set generation_context with the signal source."""
        result = actor._build_signal_request(source="signal_additive_idle")

        assert result is not None
        ctx = result.sdk_stream_handler._generation_context
        assert ctx is not None
        assert ctx["signal_source"] == "signal_additive_idle"


# ---------------------------------------------------------------------------
# _query_sdk synthetic request creation
# ---------------------------------------------------------------------------


class TestQuerySdkSyntheticRequest:
    """Tests for synthetic request creation in _query_sdk when _pending is empty."""

    @pytest.mark.asyncio
    async def test_creates_synthetic_when_pending_empty(self, actor):
        """_query_sdk should create a synthetic request when _pending is empty."""
        assert len(actor._pending) == 0

        await actor._query_sdk("test prompt", source="signal_additive_idle")

        # Synthetic request should have been created and is now in _pending
        # (it will be popped when ResultMessage arrives, but for now it's there)
        assert len(actor._pending) == 1
        assert actor._generation_state == GenerationState.GENERATING
        actor._pooled.client.query.assert_called_once_with("test prompt")

    @pytest.mark.asyncio
    async def test_no_synthetic_when_pending_not_empty(self, actor):
        """_query_sdk should NOT create synthetic when _pending has entries."""
        mock_req = MagicMock()
        mock_req.task = MagicMock()
        mock_req.task.job_id = "existing-job"
        mock_req.task.user_id = "test-user"
        mock_req.pubsub = MagicMock(publish=AsyncMock())
        actor._pending.append(mock_req)

        await actor._query_sdk("test prompt", source="signal_additive")

        # Should still have exactly 1 pending (the original, no synthetic added)
        assert len(actor._pending) == 1
        actor._pooled.client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_synthetic_when_change_state_false(self, actor):
        """_query_sdk with change_state=False should NOT create synthetic."""
        assert len(actor._pending) == 0

        await actor._query_sdk(
            "supplementary info",
            source="signal_additive_tool_executing_inject",
            change_state=False,
        )

        # No synthetic request created
        assert len(actor._pending) == 0
        actor._pooled.client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthetic_cleaned_up_on_query_failure(self, actor):
        """If client.query() raises, the synthetic request should be removed."""
        actor._pooled.client.query = AsyncMock(
            side_effect=RuntimeError("SDK error")
        )
        assert len(actor._pending) == 0

        await actor._query_sdk("test prompt", source="signal_test")

        # Synthetic request should be cleaned up
        assert len(actor._pending) == 0
        assert actor._generation_state == GenerationState.IDLE

    @pytest.mark.asyncio
    async def test_returns_early_when_build_signal_request_fails(self, actor):
        """If _build_signal_request returns None, query should not be sent."""
        actor._ctx = None  # Will cause _build_signal_request to return None

        await actor._query_sdk("test prompt", source="signal_test")

        actor._pooled.client.query.assert_not_called()
        assert len(actor._pending) == 0

    @pytest.mark.asyncio
    async def test_returns_early_when_no_pooled_client(self, actor):
        """If _pooled is None, query should not be sent."""
        actor._pooled = None

        await actor._query_sdk("test prompt", source="signal_test")

        assert len(actor._pending) == 0


# ---------------------------------------------------------------------------
# Signal handlers at IDLE with synthetic request
# ---------------------------------------------------------------------------


class TestSignalHandlersAtIdleWithSynthetic:
    """Verify signal handlers at IDLE create synthetic requests via _query_sdk."""

    @pytest.mark.asyncio
    async def test_additive_at_idle_creates_synthetic(self, actor):
        """ADDITIVE at IDLE should create synthetic request and query SDK."""
        actor._generation_state = GenerationState.IDLE

        signal = _make_signal(
            signal_type=InterventionType.ADDITIVE.value,
            payload={"additional_input": "add some context"},
        )
        result = await actor._do_additive(signal)

        assert result == "query"
        assert len(actor._pending) == 1
        actor._pooled.client.query.assert_called_once()
        call_arg = actor._pooled.client.query.call_args[0][0]
        assert "add some context" in call_arg

    @pytest.mark.asyncio
    async def test_confirm_at_idle_creates_synthetic(self, actor):
        """CONFIRM at IDLE should create synthetic request and query SDK."""
        actor._generation_state = GenerationState.IDLE

        signal = _make_signal(
            signal_type=InterventionType.CONFIRM.value,
            payload={
                "pending_action_id": "act-1",
                "confirmation": "approve",
            },
        )
        result = await actor._do_confirm(signal)

        assert result == "query"
        assert len(actor._pending) == 1
        actor._pooled.client.query.assert_called_once()
        call_arg = actor._pooled.client.query.call_args[0][0]
        assert "[USER_CONFIRMATION]" in call_arg

    @pytest.mark.asyncio
    async def test_digression_at_idle_creates_synthetic(self, actor):
        """DIGRESSION at IDLE should create synthetic request and query SDK."""
        actor._generation_state = GenerationState.IDLE

        signal = _make_signal(
            signal_type=InterventionType.DIGRESSION.value,
            payload={"new_input": "tell me a joke"},
        )
        result = await actor._do_digression(signal)

        assert result == "query"
        assert len(actor._pending) == 1
        actor._pooled.client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_sidekick_at_idle_creates_synthetic(self, actor):
        """SIDEKICK at IDLE should create synthetic request and query SDK."""
        actor._generation_state = GenerationState.IDLE

        signal = _make_signal(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            payload={
                "insight_text": "User's birthday is coming up",
                "urgency": "low",
            },
        )
        result = await actor._do_sidekick(signal)

        assert result == "inject"
        assert len(actor._pending) == 1
        actor._pooled.client.query.assert_called_once()
        call_arg = actor._pooled.client.query.call_args[0][0]
        assert "[SYSTEM_INSIGHT]" in call_arg

    @pytest.mark.asyncio
    async def test_flush_all_buffered_creates_synthetic(self, actor):
        """_flush_all_buffered should create synthetic request for combined query."""
        actor._generation_state = GenerationState.IDLE
        actor._buffered_additives = [
            _make_signal(payload={"text": "extra info"}),
        ]

        await actor._flush_all_buffered()

        assert len(actor._pending) == 1
        actor._pooled.client.query.assert_called_once()
        call_arg = actor._pooled.client.query.call_args[0][0]
        assert "请回复用户" in call_arg
        assert "extra info" in call_arg


# ---------------------------------------------------------------------------
# Context preservation in _complete_request
# ---------------------------------------------------------------------------


class TestContextPreservation:
    """Verify _complete_request saves runner/run_config/hook_builder."""

    @pytest.mark.asyncio
    async def test_complete_request_saves_last_context(self, actor):
        """_complete_request should save runner, run_config, hook_builder."""
        from claude_agent_sdk import ResultMessage

        actor._generation_state = GenerationState.GENERATING
        actor._pool = MagicMock()
        actor._pool.mark_used = AsyncMock()

        mock_runner = MagicMock(name="custom_runner")
        mock_run_config = MagicMock(name="custom_config")
        mock_hook_builder = MagicMock(name="custom_hooks")
        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock()

        loop = asyncio.get_event_loop()
        future = loop.create_future()

        mock_req = MagicMock(spec=_StreamingRequest)
        mock_req.runner = mock_runner
        mock_req.run_config = mock_run_config
        mock_req.hook_builder = mock_hook_builder
        mock_req.task = MagicMock()
        mock_req.task.user_id = "test-user"
        mock_req.task.job_id = "test-job"
        mock_req.pubsub = mock_pubsub
        mock_req.all_text = ["hello"]
        mock_req.all_tool_calls = []
        mock_req.stop_reason = None
        mock_req.turns_used = 0
        mock_req.total_cost_usd = None
        mock_req.usage = None
        mock_req.sdk_session_id = None
        mock_req.correction_resubmitted = False
        mock_req.future = future
        mock_req.sdk_stream_handler = MagicMock()
        mock_req.sdk_stream_handler.emit_missing_thinking = AsyncMock()
        mock_req.sdk_stream_handler.set_generation_context = MagicMock()

        actor._pending.append(mock_req)

        result_msg = MagicMock(spec=ResultMessage)
        result_msg.subtype = "end_turn"
        result_msg.num_turns = 1
        result_msg.total_cost_usd = 0.01
        result_msg.usage = {}
        result_msg.session_id = "sdk-session"

        await actor._complete_request(result_msg, mock_req)

        assert actor._last_runner is mock_runner
        assert actor._last_run_config is mock_run_config
        assert actor._last_hook_builder is mock_hook_builder
