"""State machine tests for ReactiveSessionActor.

Covers:
- State transitions (IDLE -> GENERATING -> TOOL_EXECUTING -> WAITING_USER)
- Non-interruptible tool detection
- Public interface: done, request_stop, submit
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai_engine.intervention.types import (
    GenerationState,
    NON_INTERRUPTIBLE_TOOLS,
)


# ---------------------------------------------------------------------------
# State machine tests
# ---------------------------------------------------------------------------


class TestStateMachine:
    def test_initial_state_is_idle(self, actor):
        assert actor._generation_state == GenerationState.IDLE

    def test_set_state_changes_state(self, actor):
        actor._set_state(GenerationState.GENERATING)
        assert actor._generation_state == GenerationState.GENERATING

    def test_set_state_noop_for_same(self, actor):
        actor._set_state(GenerationState.IDLE)
        # No exception, no change
        assert actor._generation_state == GenerationState.IDLE

    def test_state_transitions(self, actor):
        actor._set_state(GenerationState.GENERATING)
        assert actor._generation_state == GenerationState.GENERATING

        actor._set_state(GenerationState.TOOL_EXECUTING)
        assert actor._generation_state == GenerationState.TOOL_EXECUTING

        actor._set_state(GenerationState.WAITING_USER)
        assert actor._generation_state == GenerationState.WAITING_USER

        actor._set_state(GenerationState.IDLE)
        assert actor._generation_state == GenerationState.IDLE


# ---------------------------------------------------------------------------
# Non-interruptible tool check
# ---------------------------------------------------------------------------


class TestNonInterruptible:
    def test_is_non_interruptible_true(self, actor):
        actor._active_tool = "create_trip"
        assert actor._is_non_interruptible() is True

    def test_is_non_interruptible_false(self, actor):
        actor._active_tool = "query_weather"
        assert actor._is_non_interruptible() is False

    def test_is_non_interruptible_none(self, actor):
        actor._active_tool = None
        assert actor._is_non_interruptible() is False

    def test_all_non_interruptible_tools_recognized(self, actor):
        for tool in NON_INTERRUPTIBLE_TOOLS:
            actor._active_tool = tool
            assert actor._is_non_interruptible() is True


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


class TestPublicInterface:
    def test_done_when_no_task(self, actor):
        actor._task = None
        assert actor.done is True

    def test_done_when_task_finished(self, actor):
        mock_task = MagicMock()
        mock_task.done.return_value = True
        actor._task = mock_task
        assert actor.done is True

    def test_not_done_when_task_running(self, actor):
        mock_task = MagicMock()
        mock_task.done.return_value = False
        actor._task = mock_task
        assert actor.done is False

    def test_request_stop(self, actor):
        actor._task = MagicMock()
        actor._task.done.return_value = False
        actor.request_stop()
        assert actor._stop_requested is True
        actor._task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_raises_when_stopped(self, actor):
        actor._stop_requested = True
        mock_request = MagicMock()
        with pytest.raises(RuntimeError, match="stopping"):
            await actor.submit(mock_request)


# ---------------------------------------------------------------------------
# Idle exit teardown behavior
# ---------------------------------------------------------------------------


class TestIdleExitTeardown:
    """Verify that idle timeout returns CLI to pool instead of destroying it."""

    def test_idle_exit_defaults_to_false(self, actor):
        assert actor._idle_exit is False

    @pytest.mark.asyncio
    async def test_teardown_on_idle_exit_preserves_pool(self, actor):
        """When _idle_exit=True, _teardown_client should NOT disconnect."""
        mock_pool = AsyncMock()
        actor._pool = mock_pool
        actor._idle_exit = True

        await actor._teardown_client(mark_disconnected=not actor._idle_exit)

        mock_pool.disconnect_inline.assert_not_called()
        mock_pool.mark_disconnected.assert_not_called()

    @pytest.mark.asyncio
    async def test_teardown_on_error_exit_disconnects(self, actor):
        """When _idle_exit=False (error/cancel), _teardown_client SHOULD call disconnect_inline."""
        mock_pool = AsyncMock()
        actor._pool = mock_pool
        actor._idle_exit = False

        await actor._teardown_client(mark_disconnected=not actor._idle_exit)

        mock_pool.disconnect_inline.assert_called_once_with(actor.session_id)
