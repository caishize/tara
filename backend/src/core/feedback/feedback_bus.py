"""
FeedbackBus - In-process feedback signal distribution bus.

Distributes user feedback signals (e.g. insight_useful, event_cancelled)
to registered consumers that update learned preferences. Designed to work
alongside the existing DomainEvent / EventBus infrastructure without
introducing Redis Streams or other new transport layers.

Architecture:
    User action  ->  API / WebSocket handler  ->  FeedbackBus.emit()
                                                       |
                                      +----------------+----------------+
                                      |                |                |
                              PriorityConsumer  RecommendConsumer  BufferConsumer ...

Each consumer declares which signals it cares about via ``consumes_signals``.
Errors in one consumer never propagate to others.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from ..utils.timezone import utc_now
from enum import Enum
from typing import Callable, Dict, List, Optional, Protocol, runtime_checkable
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal types
# ---------------------------------------------------------------------------

class FeedbackSignal(str, Enum):
    """15 canonical feedback signals covering all user-facing feedback actions."""

    # Insight feedback
    INSIGHT_USEFUL = "insight_useful"
    INSIGHT_IGNORED = "insight_ignored"          # 24h with no action
    INSIGHT_NEVER_AGAIN = "insight_never_again"
    INSIGHT_NOT_USEFUL = "insight_not_useful"    # mapped NOT_USEFUL/NOT_RELEVANT/INCORRECT/TOO_FREQUENT
    INSIGHT_DEFERRED = "insight_deferred"        # weak positive (+0.02)

    # Suggestion feedback
    SUGGESTION_ACTED = "suggestion_acted"
    SUGGESTION_DISMISSED = "suggestion_dismissed"

    # Event feedback
    EVENT_RESCHEDULED = "event_rescheduled"
    EVENT_CANCELLED = "event_cancelled"

    # Buffer / priority feedback
    BUFFER_ADJUSTED = "buffer_adjusted"
    PRIORITY_OVERRIDE = "priority_override"

    # Annotation feedback
    ANNOTATION_HELPFUL = "annotation_helpful"
    ANNOTATION_DISMISSED = "annotation_dismissed"

    # Contact feedback
    CONTACT_INITIATED = "contact_initiated"
    CONTACT_SKIPPED = "contact_skipped"


# ---------------------------------------------------------------------------
# Event envelope
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeedbackEvent:
    """Immutable envelope for a single feedback signal.

    Attributes:
        signal: The feedback signal type.
        family_id: Scoping family.
        user_id: The user who performed the action.
        data: Signal-specific payload (e.g. insight_type, event_id, delta).
        timestamp: When the feedback was captured (UTC).
        source: Where the feedback originated (e.g. "briefing_card", "chat").
        event_id: Unique identifier for this feedback event.
    """

    signal: FeedbackSignal
    family_id: UUID
    user_id: UUID
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=utc_now)
    source: str = ""
    event_id: UUID = field(default_factory=uuid4)


# ---------------------------------------------------------------------------
# Consumer protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class FeedbackConsumer(Protocol):
    """Protocol that feedback consumers must satisfy.

    Implementations declare which signals they care about and handle
    incoming feedback events asynchronously.
    """

    async def on_feedback(self, event: FeedbackEvent) -> None:
        """Process a single feedback event."""
        ...

    @property
    def consumes_signals(self) -> List[FeedbackSignal]:
        """Return the list of signals this consumer wants to receive."""
        ...


# ---------------------------------------------------------------------------
# Error handler type
# ---------------------------------------------------------------------------

ErrorHandler = Callable[[FeedbackEvent, "FeedbackConsumer", Exception], None]


def _default_error_handler(
    event: FeedbackEvent,
    consumer: FeedbackConsumer,
    exc: Exception,
) -> None:
    consumer_name = type(consumer).__name__
    logger.error(
        "FeedbackBus: consumer %s failed on signal %s: %s",
        consumer_name,
        event.signal.value,
        exc,
        exc_info=True,
    )


# ---------------------------------------------------------------------------
# FeedbackBus
# ---------------------------------------------------------------------------

class FeedbackBus:
    """In-process feedback distribution bus.

    Hooks into the existing domain event infrastructure conceptually but
    does **not** introduce Redis Streams or other new transport layers.
    All dispatch is in-process and async-safe.

    Thread safety: This class is designed for single-process async use
    within a FastAPI application. Registration happens at startup;
    ``emit`` / ``emit_batch`` are called from request handlers.
    """

    _instance: Optional["FeedbackBus"] = None

    def __init__(self) -> None:
        self._consumers: Dict[FeedbackSignal, List[FeedbackConsumer]] = {}
        self._error_handler: ErrorHandler = _default_error_handler
        self._enabled: bool = True

    # -- Singleton -----------------------------------------------------------

    @classmethod
    def get_instance(cls) -> "FeedbackBus":
        """Return the module-level singleton, creating it if needed."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    # -- Configuration -------------------------------------------------------

    def set_error_handler(self, handler: ErrorHandler) -> None:
        """Replace the default error handler with a custom one."""
        self._error_handler = handler

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    # -- Registration --------------------------------------------------------

    def register(self, consumer: FeedbackConsumer) -> None:
        """Register a consumer for its declared signals.

        Duplicate registrations of the same consumer instance for the
        same signal are silently ignored.
        """
        for signal in consumer.consumes_signals:
            consumers_for_signal = self._consumers.setdefault(signal, [])
            if consumer not in consumers_for_signal:
                consumers_for_signal.append(consumer)
                logger.debug(
                    "FeedbackBus: registered %s for %s",
                    type(consumer).__name__,
                    signal.value,
                )

    def unregister(self, consumer: FeedbackConsumer) -> None:
        """Remove a consumer from all signals it was registered for."""
        for signal, consumers in self._consumers.items():
            if consumer in consumers:
                consumers.remove(consumer)
                logger.debug(
                    "FeedbackBus: unregistered %s from %s",
                    type(consumer).__name__,
                    signal.value,
                )

    # -- Emission ------------------------------------------------------------

    async def emit(
        self,
        signal: FeedbackSignal,
        data: dict,
        family_id: UUID,
        user_id: UUID,
        source: str = "",
    ) -> None:
        """Emit a single feedback signal to all registered consumers.

        This method is non-blocking from the caller's perspective: consumer
        errors are logged (via the error handler) but never raised.
        """
        if not self._enabled:
            return

        event = FeedbackEvent(
            signal=signal,
            family_id=family_id,
            user_id=user_id,
            data=data,
            source=source,
        )
        await self._dispatch(event)

    async def emit_event(self, event: FeedbackEvent) -> None:
        """Emit a pre-built FeedbackEvent."""
        if not self._enabled:
            return
        await self._dispatch(event)

    async def emit_batch(self, events: List[FeedbackEvent]) -> None:
        """Emit multiple feedback events sequentially.

        Used for batch processing (e.g. nightly insight-ignored sweep).
        Errors in one event do not prevent processing of subsequent events.
        """
        if not self._enabled:
            return
        for event in events:
            await self._dispatch(event)

    # -- Internal dispatch ---------------------------------------------------

    async def _dispatch(self, event: FeedbackEvent) -> None:
        """Dispatch a single event to all consumers registered for its signal."""
        consumers = self._consumers.get(event.signal, [])
        if not consumers:
            logger.debug(
                "FeedbackBus: no consumers for signal %s", event.signal.value,
            )
            return

        for consumer in consumers:
            try:
                await consumer.on_feedback(event)
            except Exception as exc:
                try:
                    self._error_handler(event, consumer, exc)
                except Exception:
                    # Last resort: error handler itself failed
                    logger.exception(
                        "FeedbackBus: error handler raised for %s on %s",
                        type(consumer).__name__,
                        event.signal.value,
                    )

    # -- Introspection (testing / debugging) ---------------------------------

    def get_consumer_count(self, signal: FeedbackSignal) -> int:
        """Return the number of consumers registered for a signal."""
        return len(self._consumers.get(signal, []))

    def get_all_consumers(self) -> Dict[FeedbackSignal, List[FeedbackConsumer]]:
        """Return a shallow copy of the consumer registry."""
        return {sig: list(cs) for sig, cs in self._consumers.items()}

    def clear(self) -> None:
        """Remove all consumers (for testing)."""
        self._consumers.clear()


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

def get_feedback_bus() -> FeedbackBus:
    """Return the FeedbackBus singleton."""
    return FeedbackBus.get_instance()
