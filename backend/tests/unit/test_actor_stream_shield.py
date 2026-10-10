"""Tests for _next_message() asyncio.shield() protection.

Validates that cancelling the outer _next_message() task (as happens in
_run_active_phase when asyncio.wait_for times out) does NOT finalize the
underlying receive_messages() async generator.  This was the root cause of
the "stream ended unexpectedly (cli_alive=True)" bug.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from src.ai_engine.workers.reactive_session_actor import ReactiveSessionActor


async def _make_actor() -> ReactiveSessionActor:
    """Minimal actor with a real async generator as _receive_iter."""
    a = ReactiveSessionActor(
        session_id="shield-test",
        idle_seconds=60,
        on_exit=MagicMock(),
    )
    a._pooled = MagicMock()
    return a


async def _fake_receive():
    """Simulate receive_messages() — yields messages on demand."""
    msg_num = 0
    while True:
        msg_num += 1
        yield {"type": "message", "num": msg_num}


class TestNextMessageShield:
    """Verify _next_message() survives cancellation without killing the generator."""

    @pytest.mark.asyncio
    async def test_cancel_does_not_finalize_generator(self):
        """Core regression test: cancel _next_message() then call it again."""
        actor = await _make_actor()
        gen = _fake_receive()
        actor._receive_iter = gen.__aiter__()

        # First call: succeeds normally
        msg1 = await actor._next_message()
        assert msg1["num"] == 1
        assert actor._pending_anext_task is None  # consumed

        # Second call: start _next_message() then cancel it before it completes
        # We'll make the generator block until we explicitly send a value
        blocked = asyncio.Event()
        result_ready = asyncio.Event()
        captured_msg = {}

        async def slow_receive():
            """Generator that blocks on the second yield."""
            yield {"type": "message", "num": "fast"}
            await blocked.wait()
            yield {"type": "message", "num": "slow"}

        slow_gen = slow_receive()
        actor._receive_iter = slow_gen.__aiter__()
        actor._pending_anext_task = None

        # Consume the fast message
        msg_fast = await actor._next_message()
        assert msg_fast["num"] == "fast"

        # Now _next_message will block on the slow yield
        task = asyncio.create_task(actor._next_message())
        await asyncio.sleep(0.01)  # let task enter shield

        # Cancel the outer task (simulates wait_for timeout)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # The inner _pending_anext_task should still be alive (shielded)
        assert actor._pending_anext_task is not None
        assert not actor._pending_anext_task.done()

        # Unblock the generator
        blocked.set()
        await asyncio.sleep(0.01)

        # Now call _next_message again — should reuse the inner task and succeed
        msg_slow = await actor._next_message()
        assert msg_slow["num"] == "slow"
        assert actor._pending_anext_task is None  # consumed

    @pytest.mark.asyncio
    async def test_multiple_cancellations_survive(self):
        """Multiple consecutive cancellations don't corrupt state."""
        actor = await _make_actor()

        blocked = asyncio.Event()

        async def blocking_receive():
            await blocked.wait()
            yield {"type": "message", "num": 1}

        actor._receive_iter = blocking_receive().__aiter__()

        # Cancel 3 times in a row
        for _ in range(3):
            task = asyncio.create_task(actor._next_message())
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        # Same inner task should still be alive
        assert actor._pending_anext_task is not None
        assert not actor._pending_anext_task.done()

        # Unblock and verify it works
        blocked.set()
        await asyncio.sleep(0.01)
        msg = await actor._next_message()
        assert msg["num"] == 1

    @pytest.mark.asyncio
    async def test_completed_task_reused_between_calls(self):
        """If the inner task completes between cancellation and next call,
        its result is picked up (not lost) by the next _next_message()."""
        actor = await _make_actor()

        gate = asyncio.Event()
        released = asyncio.Event()

        async def gated_receive():
            await gate.wait()
            yield {"type": "message", "num": 1}
            yield {"type": "message", "num": 2}

        actor._receive_iter = gated_receive().__aiter__()

        # Start _next_message — it will block on the gate
        task = asyncio.create_task(actor._next_message())
        await asyncio.sleep(0.01)

        # Cancel the outer task while it's blocked
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Inner task is still alive, waiting on the gate
        assert actor._pending_anext_task is not None
        assert not actor._pending_anext_task.done()

        # Open the gate — inner task will complete with a result
        gate.set()
        await asyncio.sleep(0.01)
        assert actor._pending_anext_task.done()

        # _next_message should pick up the completed result via shield()
        msg = await actor._next_message()
        assert msg["num"] == 1
        assert actor._pending_anext_task is None

    @pytest.mark.asyncio
    async def test_stop_async_iteration_still_raises(self):
        """StopAsyncIteration from a genuinely closed generator still raises."""
        actor = await _make_actor()
        actor._pool = MagicMock()
        actor._pool.peek = MagicMock(return_value=None)
        actor._pending = []

        async def empty_receive():
            return
            yield  # makes it an async generator

        actor._receive_iter = empty_receive().__aiter__()

        with pytest.raises(RuntimeError, match="stream ended unexpectedly"):
            await actor._next_message()

    @pytest.mark.asyncio
    async def test_teardown_cancels_pending_anext_task(self):
        """_teardown_client cleans up _pending_anext_task."""
        actor = await _make_actor()

        blocked = asyncio.Event()

        async def blocking_receive():
            await blocked.wait()
            yield {"type": "message", "num": 1}

        actor._receive_iter = blocking_receive().__aiter__()

        # Start a _next_message to create _pending_anext_task
        task = asyncio.create_task(actor._next_message())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert actor._pending_anext_task is not None

        # Call teardown through the actor (mixin method)
        await actor._teardown_client(mark_disconnected=False)

        assert actor._pending_anext_task is None
        assert actor._receive_iter is None
