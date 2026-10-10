"""Cross-module feedback infrastructure.

Two complementary subsystems:

1. **FeedbackAggregator** (query-time) -- computes a unified entity weight
   from insight/curation/memory feedback tables, consumed by ContextAssembler
   Step 4 ranking.

2. **FeedbackBus** (event-time) -- distributes user feedback *signals* to
   registered consumers that update learned preferences (FamilyPreference),
   closing the feedback loop from UI actions through to priority scoring,
   association weighting, and recommendation tuning.

Integration with core/events:
    The FeedbackBus is a *parallel* bus to the DomainEvent EventBus.
    Domain events represent *things that happened* in the system (e.g.
    EventCurated, InsightGenerated).  Feedback signals represent *user
    reactions* to those things (e.g. INSIGHT_USEFUL, EVENT_CANCELLED).
    API handlers that capture user reactions should call
    ``get_feedback_bus().emit(...)``; domain-event handlers may also
    bridge into the FeedbackBus when appropriate.
"""

import logging

from .aggregator import FeedbackAggregator
from .feedback_bus import (
    FeedbackBus,
    FeedbackConsumer,
    FeedbackEvent,
    FeedbackSignal,
    get_feedback_bus,
)

logger = logging.getLogger(__name__)


def setup_feedback_consumers(db_session_factory) -> FeedbackBus:
    """Register all feedback consumers with the bus.

    Call during application startup (e.g. in the FastAPI lifespan handler).
    The *db_session_factory* must be an ``async_sessionmaker`` -- each
    consumer opens a scoped session per feedback event.

    Returns the configured FeedbackBus singleton.
    """
    from .consumers import (
        AssociationFeedbackConsumer,
        BufferTimeFeedbackConsumer,
        PriorityFeedbackConsumer,
        RecommendationFeedbackConsumer,
    )

    bus = get_feedback_bus()
    bus.register(PriorityFeedbackConsumer(db_session_factory))
    bus.register(AssociationFeedbackConsumer(db_session_factory))
    bus.register(RecommendationFeedbackConsumer(db_session_factory))
    bus.register(BufferTimeFeedbackConsumer(db_session_factory))

    logger.info(
        "FeedbackBus: registered 4 consumers (%d signal bindings total)",
        sum(bus.get_consumer_count(s) for s in FeedbackSignal),
    )
    return bus


__all__ = [
    # Query-time aggregation
    "FeedbackAggregator",
    # Event-time distribution
    "FeedbackBus",
    "FeedbackConsumer",
    "FeedbackEvent",
    "FeedbackSignal",
    "get_feedback_bus",
    # Startup wiring
    "setup_feedback_consumers",
]
