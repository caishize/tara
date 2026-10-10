"""Tests for the FeedbackBus feedback signal distribution infrastructure."""

import asyncio
from typing import List
from uuid import uuid4

import pytest

from src.core.feedback.feedback_bus import (
    FeedbackBus,
    FeedbackConsumer,
    FeedbackEvent,
    FeedbackSignal,
    get_feedback_bus,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

class RecordingConsumer:
    """A simple consumer that records received events."""

    def __init__(self, signals: List[FeedbackSignal]):
        self._signals = signals
        self.received: List[FeedbackEvent] = []

    @property
    def consumes_signals(self) -> List[FeedbackSignal]:
        return self._signals

    async def on_feedback(self, event: FeedbackEvent) -> None:
        self.received.append(event)


class FailingConsumer:
    """A consumer that always raises on on_feedback."""

    def __init__(self, signals: List[FeedbackSignal]):
        self._signals = signals

    @property
    def consumes_signals(self) -> List[FeedbackSignal]:
        return self._signals

    async def on_feedback(self, event: FeedbackEvent) -> None:
        raise RuntimeError("deliberate test failure")


@pytest.fixture()
def bus() -> FeedbackBus:
    """Return a fresh, isolated FeedbackBus instance (not the singleton)."""
    return FeedbackBus()


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure the singleton is clean before and after each test."""
    FeedbackBus.reset_instance()
    yield
    FeedbackBus.reset_instance()


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------

def test_get_instance_returns_same_object():
    bus_a = FeedbackBus.get_instance()
    bus_b = FeedbackBus.get_instance()
    assert bus_a is bus_b


def test_reset_instance_creates_new_object():
    bus_a = FeedbackBus.get_instance()
    FeedbackBus.reset_instance()
    bus_b = FeedbackBus.get_instance()
    assert bus_a is not bus_b


def test_get_feedback_bus_returns_singleton():
    bus = get_feedback_bus()
    assert bus is FeedbackBus.get_instance()


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

def test_register_adds_consumer(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.register(consumer)
    assert bus.get_consumer_count(FeedbackSignal.INSIGHT_USEFUL) == 1


def test_register_idempotent(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.register(consumer)
    bus.register(consumer)
    assert bus.get_consumer_count(FeedbackSignal.INSIGHT_USEFUL) == 1


def test_register_multiple_signals(bus: FeedbackBus):
    signals = [FeedbackSignal.INSIGHT_USEFUL, FeedbackSignal.INSIGHT_IGNORED]
    consumer = RecordingConsumer(signals)
    bus.register(consumer)
    assert bus.get_consumer_count(FeedbackSignal.INSIGHT_USEFUL) == 1
    assert bus.get_consumer_count(FeedbackSignal.INSIGHT_IGNORED) == 1


def test_unregister_removes_consumer(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.register(consumer)
    bus.unregister(consumer)
    assert bus.get_consumer_count(FeedbackSignal.INSIGHT_USEFUL) == 0


def test_unregister_nonexistent_consumer_is_safe(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.unregister(consumer)  # should not raise


def test_clear_removes_all(bus: FeedbackBus):
    bus.register(RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL]))
    bus.register(RecordingConsumer([FeedbackSignal.EVENT_CANCELLED]))
    bus.clear()
    assert bus.get_consumer_count(FeedbackSignal.INSIGHT_USEFUL) == 0
    assert bus.get_consumer_count(FeedbackSignal.EVENT_CANCELLED) == 0


# ---------------------------------------------------------------------------
# Emit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_emit_delivers_to_matching_consumer(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.register(consumer)

    family_id = uuid4()
    user_id = uuid4()
    await bus.emit(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        data={"insight_type": "follow_up"},
        family_id=family_id,
        user_id=user_id,
        source="briefing_card",
    )

    assert len(consumer.received) == 1
    event = consumer.received[0]
    assert event.signal == FeedbackSignal.INSIGHT_USEFUL
    assert event.family_id == family_id
    assert event.user_id == user_id
    assert event.data == {"insight_type": "follow_up"}
    assert event.source == "briefing_card"


@pytest.mark.asyncio
async def test_emit_does_not_deliver_to_non_matching_consumer(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.EVENT_CANCELLED])
    bus.register(consumer)

    await bus.emit(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        data={},
        family_id=uuid4(),
        user_id=uuid4(),
    )

    assert len(consumer.received) == 0


@pytest.mark.asyncio
async def test_emit_delivers_to_multiple_consumers(bus: FeedbackBus):
    consumer_a = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    consumer_b = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.register(consumer_a)
    bus.register(consumer_b)

    await bus.emit(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        data={},
        family_id=uuid4(),
        user_id=uuid4(),
    )

    assert len(consumer_a.received) == 1
    assert len(consumer_b.received) == 1


@pytest.mark.asyncio
async def test_emit_when_disabled_skips_dispatch(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.register(consumer)
    bus.disable()

    await bus.emit(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        data={},
        family_id=uuid4(),
        user_id=uuid4(),
    )

    assert len(consumer.received) == 0


@pytest.mark.asyncio
async def test_emit_re_enable_works(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.register(consumer)
    bus.disable()
    bus.enable()

    await bus.emit(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        data={},
        family_id=uuid4(),
        user_id=uuid4(),
    )

    assert len(consumer.received) == 1


# ---------------------------------------------------------------------------
# emit_event tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_emit_event_dispatches_prebuilt_event(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.BUFFER_ADJUSTED])
    bus.register(consumer)

    event = FeedbackEvent(
        signal=FeedbackSignal.BUFFER_ADJUSTED,
        family_id=uuid4(),
        user_id=uuid4(),
        data={"delta_minutes": 15},
        source="schedule_view",
    )
    await bus.emit_event(event)

    assert len(consumer.received) == 1
    assert consumer.received[0] is event


# ---------------------------------------------------------------------------
# emit_batch tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_emit_batch_delivers_all(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_IGNORED])
    bus.register(consumer)

    events = [
        FeedbackEvent(
            signal=FeedbackSignal.INSIGHT_IGNORED,
            family_id=uuid4(),
            user_id=uuid4(),
            data={"insight_id": str(uuid4())},
        )
        for _ in range(5)
    ]
    await bus.emit_batch(events)

    assert len(consumer.received) == 5


@pytest.mark.asyncio
async def test_emit_batch_when_disabled(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_IGNORED])
    bus.register(consumer)
    bus.disable()

    events = [
        FeedbackEvent(
            signal=FeedbackSignal.INSIGHT_IGNORED,
            family_id=uuid4(),
            user_id=uuid4(),
        )
    ]
    await bus.emit_batch(events)

    assert len(consumer.received) == 0


# ---------------------------------------------------------------------------
# Error isolation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failing_consumer_does_not_block_others(bus: FeedbackBus):
    failing = FailingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    recording = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.register(failing)
    bus.register(recording)

    await bus.emit(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        data={},
        family_id=uuid4(),
        user_id=uuid4(),
    )

    # The recording consumer should still get the event
    assert len(recording.received) == 1


@pytest.mark.asyncio
async def test_custom_error_handler_is_called(bus: FeedbackBus):
    errors_seen: List[tuple] = []

    def custom_handler(event, consumer, exc):
        errors_seen.append((event.signal, type(consumer).__name__, str(exc)))

    bus.set_error_handler(custom_handler)
    failing = FailingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.register(failing)

    await bus.emit(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        data={},
        family_id=uuid4(),
        user_id=uuid4(),
    )

    assert len(errors_seen) == 1
    assert errors_seen[0][0] == FeedbackSignal.INSIGHT_USEFUL
    assert errors_seen[0][1] == "FailingConsumer"
    assert "deliberate test failure" in errors_seen[0][2]


@pytest.mark.asyncio
async def test_failing_error_handler_does_not_crash(bus: FeedbackBus):
    """Even if the error handler itself throws, emit() must not raise."""

    def broken_handler(event, consumer, exc):
        raise RuntimeError("error handler is also broken")

    bus.set_error_handler(broken_handler)
    bus.register(FailingConsumer([FeedbackSignal.INSIGHT_USEFUL]))

    # Should not raise
    await bus.emit(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        data={},
        family_id=uuid4(),
        user_id=uuid4(),
    )


@pytest.mark.asyncio
async def test_emit_batch_one_event_error_continues_rest(bus: FeedbackBus):
    """If processing one event fails, subsequent events still get processed."""
    call_count = 0

    class CountAndFail:
        @property
        def consumes_signals(self):
            return [FeedbackSignal.CONTACT_INITIATED]

        async def on_feedback(self, event: FeedbackEvent) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("fail on second event")

    bus.register(CountAndFail())

    events = [
        FeedbackEvent(
            signal=FeedbackSignal.CONTACT_INITIATED,
            family_id=uuid4(),
            user_id=uuid4(),
        )
        for _ in range(3)
    ]
    await bus.emit_batch(events)

    # All 3 events were dispatched even though the 2nd one failed
    assert call_count == 3


# ---------------------------------------------------------------------------
# FeedbackEvent immutability tests
# ---------------------------------------------------------------------------

def test_feedback_event_is_frozen():
    event = FeedbackEvent(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        family_id=uuid4(),
        user_id=uuid4(),
    )
    with pytest.raises(AttributeError):
        event.signal = FeedbackSignal.EVENT_CANCELLED


def test_feedback_event_has_event_id():
    event = FeedbackEvent(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        family_id=uuid4(),
        user_id=uuid4(),
    )
    assert event.event_id is not None


def test_feedback_event_has_timestamp():
    event = FeedbackEvent(
        signal=FeedbackSignal.INSIGHT_USEFUL,
        family_id=uuid4(),
        user_id=uuid4(),
    )
    assert event.timestamp is not None


# ---------------------------------------------------------------------------
# FeedbackSignal enum tests
# ---------------------------------------------------------------------------

def test_all_15_signals_defined():
    """Verify all 15 FeedbackSignal members are defined (13 original + INSIGHT_NOT_USEFUL + INSIGHT_DEFERRED)."""
    assert len(FeedbackSignal) == 15


def test_signal_values_are_strings():
    for signal in FeedbackSignal:
        assert isinstance(signal.value, str)


# ---------------------------------------------------------------------------
# Protocol conformance tests
# ---------------------------------------------------------------------------

def test_recording_consumer_satisfies_protocol():
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    assert isinstance(consumer, FeedbackConsumer)


def test_failing_consumer_satisfies_protocol():
    consumer = FailingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    assert isinstance(consumer, FeedbackConsumer)


# ---------------------------------------------------------------------------
# Introspection tests
# ---------------------------------------------------------------------------

def test_get_all_consumers(bus: FeedbackBus):
    consumer_a = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    consumer_b = RecordingConsumer([FeedbackSignal.EVENT_CANCELLED])
    bus.register(consumer_a)
    bus.register(consumer_b)

    all_consumers = bus.get_all_consumers()
    assert FeedbackSignal.INSIGHT_USEFUL in all_consumers
    assert FeedbackSignal.EVENT_CANCELLED in all_consumers
    assert consumer_a in all_consumers[FeedbackSignal.INSIGHT_USEFUL]
    assert consumer_b in all_consumers[FeedbackSignal.EVENT_CANCELLED]


def test_get_all_consumers_returns_copy(bus: FeedbackBus):
    consumer = RecordingConsumer([FeedbackSignal.INSIGHT_USEFUL])
    bus.register(consumer)

    copy = bus.get_all_consumers()
    copy[FeedbackSignal.INSIGHT_USEFUL].clear()

    # Original should be unaffected
    assert bus.get_consumer_count(FeedbackSignal.INSIGHT_USEFUL) == 1
