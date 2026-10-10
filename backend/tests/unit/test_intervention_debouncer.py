"""Unit tests for InterventionDebouncer.

Tests cover:
- CANCEL signal bypass and pending cancellation
- Last-write-wins semantics (via callback)
- Single signal dispatch via callback
- Timer reset on new signal
- reset() method
- Zero-window immediate dispatch
- Callback error handling
"""

import asyncio
import uuid
from typing import List

import pytest

from src.ai_engine.intervention.debouncer import (
    InterventionDebouncer,
    DEBOUNCE_WINDOW_SECONDS,
)
from src.ai_engine.intervention.types import InterventionSignal, InterventionType

# Short window for fast tests
_TEST_WINDOW = 0.05


def _make_signal(
    signal_type: str = InterventionType.ADDITIVE.value,
    signal_id: str = None,
    session_id: str = "test-session",
) -> InterventionSignal:
    return InterventionSignal(
        signal_id=signal_id or str(uuid.uuid4()),
        type=signal_type,
        session_id=session_id,
        job_id="test-job",
        user_id="test-user",
        timestamp="2026-02-21T00:00:00+00:00",
        payload={},
        priority=2,
    )


class CallbackCollector:
    """Helper that collects dispatched signals from the debouncer callback."""

    def __init__(self) -> None:
        self.dispatched: List[InterventionSignal] = []
        self.event: asyncio.Event = asyncio.Event()

    async def __call__(self, signal: InterventionSignal) -> None:
        self.dispatched.append(signal)
        self.event.set()

    async def wait_for_dispatch(self, timeout: float = 1.0) -> None:
        await asyncio.wait_for(self.event.wait(), timeout=timeout)
        self.event.clear()


# -- CANCEL bypass --


@pytest.mark.asyncio
async def test_cancel_returns_immediately():
    """CANCEL signal should return the same signal without waiting."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    signal = _make_signal(signal_type=InterventionType.CANCEL.value)

    result = await debouncer.submit(signal)

    assert result is signal


@pytest.mark.asyncio
async def test_cancel_cancels_pending_signal():
    """CANCEL should cancel a pending non-CANCEL signal so the callback never fires for it."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    additive = _make_signal(signal_id="pending-additive")
    cancel = _make_signal(signal_type=InterventionType.CANCEL.value, signal_id="cancel-1")

    # Submit additive — returns None (non-blocking)
    result_additive = await debouncer.submit(additive)
    assert result_additive is None

    # CANCEL arrives and cancels the pending signal
    result_cancel = await debouncer.submit(cancel)
    assert result_cancel is cancel

    # Wait longer than the debounce window to confirm callback never fires
    await asyncio.sleep(_TEST_WINDOW * 2)
    assert len(collector.dispatched) == 0


# -- Last-write-wins --


@pytest.mark.asyncio
async def test_last_write_wins():
    """When two non-CANCEL signals arrive within the window, only the second is dispatched via callback."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    s1 = _make_signal(signal_id="first")
    s2 = _make_signal(signal_id="second")

    # Both return None (non-blocking)
    r1 = await debouncer.submit(s1)
    await asyncio.sleep(0.01)
    r2 = await debouncer.submit(s2)

    assert r1 is None
    assert r2 is None

    # Wait for callback
    await collector.wait_for_dispatch()

    assert len(collector.dispatched) == 1
    assert collector.dispatched[0].signal_id == "second"


@pytest.mark.asyncio
async def test_last_write_wins_three_signals():
    """With three rapid signals, only the third is dispatched via callback."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    s1 = _make_signal(signal_id="first")
    s2 = _make_signal(signal_id="second")
    s3 = _make_signal(signal_id="third")

    await debouncer.submit(s1)
    await asyncio.sleep(0.005)
    await debouncer.submit(s2)
    await asyncio.sleep(0.005)
    await debouncer.submit(s3)

    await collector.wait_for_dispatch()

    assert len(collector.dispatched) == 1
    assert collector.dispatched[0].signal_id == "third"


# -- Single signal dispatch --


@pytest.mark.asyncio
async def test_single_signal_dispatched_after_window():
    """A lone signal is dispatched via callback after the debounce window expires."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    signal = _make_signal(signal_id="only-one")

    result = await debouncer.submit(signal)
    assert result is None  # non-blocking

    await collector.wait_for_dispatch()

    assert len(collector.dispatched) == 1
    assert collector.dispatched[0].signal_id == "only-one"


@pytest.mark.asyncio
async def test_single_signal_callback_receives_same_object():
    """The dispatched signal in the callback should be the exact same object submitted."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    signal = _make_signal()

    await debouncer.submit(signal)
    await collector.wait_for_dispatch()

    assert collector.dispatched[0] is signal


# -- Timer reset on new signal --


@pytest.mark.asyncio
async def test_new_signal_replaces_pending():
    """Submitting a new signal before window expires replaces the pending one in the callback."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    old_signal = _make_signal(signal_id="old")
    new_signal = _make_signal(signal_id="new")

    await debouncer.submit(old_signal)
    await asyncio.sleep(0.01)  # old is now pending
    await debouncer.submit(new_signal)

    await collector.wait_for_dispatch()

    assert len(collector.dispatched) == 1
    assert collector.dispatched[0].signal_id == "new"


# -- reset() method --


@pytest.mark.asyncio
async def test_reset_clears_pending_state():
    """reset() should clear pending signal and cancel timer so callback never fires."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    signal = _make_signal(signal_id="will-be-reset")

    await debouncer.submit(signal)
    await asyncio.sleep(0.01)  # Let it register

    debouncer.reset()

    # Wait longer than the debounce window
    await asyncio.sleep(_TEST_WINDOW * 2)
    assert len(collector.dispatched) == 0


@pytest.mark.asyncio
async def test_reset_allows_new_submissions():
    """After reset(), new signals should be dispatched normally via callback."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    s1 = _make_signal(signal_id="before-reset")

    await debouncer.submit(s1)
    await asyncio.sleep(0.01)
    debouncer.reset()

    # Wait to confirm first signal was not dispatched
    await asyncio.sleep(_TEST_WINDOW * 2)
    assert len(collector.dispatched) == 0

    # New signal after reset
    s2 = _make_signal(signal_id="after-reset")
    await debouncer.submit(s2)
    await collector.wait_for_dispatch()

    assert len(collector.dispatched) == 1
    assert collector.dispatched[0].signal_id == "after-reset"


# -- Zero window --


@pytest.mark.asyncio
async def test_zero_window_dispatches_immediately():
    """With window=0, signals should be dispatched via callback without waiting."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=0)
    signal = _make_signal(signal_id="instant")

    result = await debouncer.submit(signal)
    assert result is None  # still non-blocking

    await collector.wait_for_dispatch()

    assert len(collector.dispatched) == 1
    assert collector.dispatched[0].signal_id == "instant"


@pytest.mark.asyncio
async def test_zero_window_sequential_signals():
    """With window=0, sequential signals are each dispatched via callback."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=0)
    s1 = _make_signal(signal_id="seq-1")
    s2 = _make_signal(signal_id="seq-2")

    await debouncer.submit(s1)
    await collector.wait_for_dispatch()

    await debouncer.submit(s2)
    await collector.wait_for_dispatch()

    assert len(collector.dispatched) == 2
    assert collector.dispatched[0].signal_id == "seq-1"
    assert collector.dispatched[1].signal_id == "seq-2"


# -- Edge cases --


@pytest.mark.asyncio
async def test_default_window_constant():
    """DEBOUNCE_WINDOW_SECONDS should be a positive float."""
    assert isinstance(DEBOUNCE_WINDOW_SECONDS, float)
    assert DEBOUNCE_WINDOW_SECONDS > 0


@pytest.mark.asyncio
async def test_negative_window_clamped_to_zero():
    """A negative window should be clamped to 0."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=-1.0)
    assert debouncer._window == 0.0

    signal = _make_signal(signal_id="neg-window")
    await debouncer.submit(signal)
    await collector.wait_for_dispatch()

    assert len(collector.dispatched) == 1
    assert collector.dispatched[0].signal_id == "neg-window"


@pytest.mark.asyncio
async def test_cancel_with_no_pending():
    """CANCEL when nothing is pending should still return the CANCEL signal."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    cancel = _make_signal(signal_type=InterventionType.CANCEL.value, signal_id="lone-cancel")

    result = await debouncer.submit(cancel)

    assert result is cancel


@pytest.mark.asyncio
async def test_different_sessions_same_debouncer():
    """Signals from different sessions still follow last-write-wins on the same debouncer."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=_TEST_WINDOW)
    s1 = _make_signal(signal_id="session-a", session_id="session-a")
    s2 = _make_signal(signal_id="session-b", session_id="session-b")

    await debouncer.submit(s1)
    await asyncio.sleep(0.01)
    await debouncer.submit(s2)

    await collector.wait_for_dispatch()

    assert len(collector.dispatched) == 1
    assert collector.dispatched[0].signal_id == "session-b"


@pytest.mark.asyncio
async def test_submit_without_callback():
    """When no on_dispatch callback is set, signals are still debounced without error."""
    debouncer = InterventionDebouncer(window=_TEST_WINDOW)
    signal = _make_signal(signal_id="no-callback")

    result = await debouncer.submit(signal)
    assert result is None

    # Wait for debounce window — should complete without error
    await asyncio.sleep(_TEST_WINDOW * 2)


@pytest.mark.asyncio
async def test_callback_error_does_not_crash():
    """If the on_dispatch callback raises, the debouncer should log but not crash."""
    async def failing_callback(signal: InterventionSignal) -> None:
        raise RuntimeError("callback failed")

    debouncer = InterventionDebouncer(on_dispatch=failing_callback, window=_TEST_WINDOW)
    signal = _make_signal(signal_id="error-signal")

    await debouncer.submit(signal)

    # Wait for debounce window — callback fails but debouncer should survive
    await asyncio.sleep(_TEST_WINDOW * 2)

    # Debouncer should still accept new signals
    collector = CallbackCollector()
    debouncer._on_dispatch = collector
    s2 = _make_signal(signal_id="after-error")
    await debouncer.submit(s2)
    await collector.wait_for_dispatch()
    assert collector.dispatched[0].signal_id == "after-error"


@pytest.mark.asyncio
async def test_submit_is_non_blocking():
    """submit() for non-CANCEL signals should return immediately, not block for the window."""
    collector = CallbackCollector()
    debouncer = InterventionDebouncer(on_dispatch=collector, window=0.5)
    signal = _make_signal(signal_id="non-blocking")

    # submit should return nearly instantly (well under the 0.5s window)
    result = await asyncio.wait_for(debouncer.submit(signal), timeout=0.05)
    assert result is None

    # Clean up: cancel the pending timer
    debouncer.reset()
