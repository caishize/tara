"""FeedbackBus consumer implementations.

Each consumer implements the ``FeedbackConsumer`` protocol from
``core.feedback.feedback_bus`` and writes learned preferences to the
``FamilyPreference`` model via ``FamilyPreferenceRepository``.

Usage at application startup::

    from sqlalchemy.ext.asyncio import AsyncSession
    from core.feedback import get_feedback_bus
    from core.feedback.consumers import (
        PriorityFeedbackConsumer,
        AssociationFeedbackConsumer,
        RecommendationFeedbackConsumer,
        BufferTimeFeedbackConsumer,
    )

    def register_feedback_consumers(db: AsyncSession) -> None:
        bus = get_feedback_bus()
        bus.register(PriorityFeedbackConsumer(db))
        bus.register(AssociationFeedbackConsumer(db))
        bus.register(RecommendationFeedbackConsumer(db))
        bus.register(BufferTimeFeedbackConsumer(db))
"""

from .association_feedback_consumer import AssociationFeedbackConsumer
from .buffer_time_feedback_consumer import BufferTimeFeedbackConsumer
from .priority_feedback_consumer import PriorityFeedbackConsumer
from .recommendation_feedback_consumer import RecommendationFeedbackConsumer

__all__ = [
    "AssociationFeedbackConsumer",
    "BufferTimeFeedbackConsumer",
    "PriorityFeedbackConsumer",
    "RecommendationFeedbackConsumer",
]
