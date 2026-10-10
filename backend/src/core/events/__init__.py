"""
Core Events Module

Provides event-driven architecture for module decoupling.
"""

from .event_bus import (
    DomainEvent,
    EventBus,
    get_event_bus,
    event_handler,
)
from .domain_events import (
    # Date Events
    ImportantDateCreated,
    ImportantDateUpdated,
    ImportantDateDeleted,
    DateApproaching,
    # Gift Task Events
    GiftTaskCreated,
    GiftRecommendationGenerated,
    GiftOptionSelected,
    GiftRecommendationExpired,
    GiftTaskStatusChanged,
    # Gift History Events
    GiftHistoryRecorded,
    GiftFeedbackReceived,
    # Member Events
    MemberProfileUpdated,
    MemberRelationChanged,
    # Preference Events
    PreferenceUpdated,
    # Reminder Events
    DateReminderTriggered,
    # Trip Events
    TripCreated,
    TripUpdated,
    TripCancelled,
    TripDeleted,
    TripCompleted,
    # Memory Events
    MemoryExtracted,
    InsightGenerated,
    # Curation Events
    EventCurated,
    EventRequested,
    # Kanban Events
    PreparationToggled,
    # Relationship Events
    FavorRecorded,
    # Constants
    GIFTABLE_DATE_TYPES,
    NON_GIFTABLE_DATE_TYPES,
    DATE_TYPE_TO_OCCASION,
)
from .outbox import OutboxEvent, save_to_outbox
from .consumer import EventConsumer
from .handlers import (
    HandlerRegistry,
    register_all_handlers,
    register_stream_consumers,
)

__all__ = [
    # Event Bus
    'DomainEvent',
    'EventBus',
    'get_event_bus',
    'event_handler',
    # Date Events
    'ImportantDateCreated',
    'ImportantDateUpdated',
    'ImportantDateDeleted',
    'DateApproaching',
    # Gift Events
    'GiftTaskCreated',
    'GiftRecommendationGenerated',
    'GiftOptionSelected',
    'GiftRecommendationExpired',
    'GiftTaskStatusChanged',
    'GiftHistoryRecorded',
    'GiftFeedbackReceived',
    # Member Events
    'MemberProfileUpdated',
    'MemberRelationChanged',
    # Preference Events
    'PreferenceUpdated',
    # Reminder Events
    'DateReminderTriggered',
    # Trip Events
    'TripCreated',
    'TripUpdated',
    'TripCancelled',
    'TripDeleted',
    'TripCompleted',
    # Memory Events
    'MemoryExtracted',
    'InsightGenerated',
    # Curation Events
    'EventCurated',
    'EventRequested',
    # Kanban Events
    'PreparationToggled',
    # Relationship Events
    'FavorRecorded',
    # Constants
    'GIFTABLE_DATE_TYPES',
    'NON_GIFTABLE_DATE_TYPES',
    'DATE_TYPE_TO_OCCASION',
    # Outbox
    'OutboxEvent',
    'save_to_outbox',
    # Consumer
    'EventConsumer',
    # Handlers
    'HandlerRegistry',
    'register_all_handlers',
    'register_stream_consumers',
]
