"""Stream Consumer Registrations.

Defines the mapping from Redis Streams to consumer groups and their
handler functions.  Called during application startup to wire up
the ``EventConsumer`` for cross-process event delivery.

Design reference (architecture-redesign.md / agent-teams-design.md):

| Stream            | Consumer Group      | Consumers           |
|-------------------|---------------------|----------------------|
| events:curation   | curation-workers    | curation module      |
| events:briefing   | briefing-workers    | briefing module      |
| events:memory     | memory-workers      | memory module        |
| events:graph      | graph-workers       | graph module         |
| events:member     | member-workers      | member module        |
| events:ws-bridge  | ws-bridge-workers   | WebSocket PubSub     |
"""

import logging
from typing import Optional

from ..consumer import EventConsumer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handler stubs — each receives (event_type: str, payload: dict)
# Implementations will be filled in as modules mature.
# ---------------------------------------------------------------------------

async def _handle_curation_event(event_type: str, payload: dict) -> None:
    """curation-workers: trip lifecycle, memory, date, and event-requested triggers.

    Passes the full event payload through to TriggerDispatcher so that
    incremental handlers can access trip_id, memory_id, etc.
    """
    logger.info("curation-workers received %s (id=%s)", event_type, payload.get("event_id"))
    family_id_str = payload.get("family_id")
    if not family_id_str:
        return
    try:
        from uuid import UUID
        from ....modules.curation.tasks import trigger_curation_async

        trigger_type_map = {
            "TripCreated": "trip_created",
            "TripUpdated": "trip_updated",
            "TripCancelled": "trip_cancelled",
            "TripDeleted": "trip_deleted",
            "MemoryExtracted": "memory_extracted",
            "DateApproaching": "date_approaching",
            "EventRequested": "event_requested",
        }
        trigger_type = trigger_type_map.get(event_type, "event")

        # For incremental triggers, pass payload so handlers can access
        # event-specific data (trip_id, memory_id, etc.)
        trigger_curation_async(
            UUID(family_id_str),
            trigger_type=trigger_type,
            payload=payload,
        )
    except Exception as e:
        logger.error("Failed to trigger curation for %s: %s", event_type, e)


async def _handle_briefing_event(event_type: str, payload: dict) -> None:
    """briefing-workers: EventCurated, PreparationToggled, FavorRecorded, DateApproaching,
    GiftTaskStatusChanged, InsightGenerated, MemoryExtracted."""
    logger.info("briefing-workers received %s (id=%s)", event_type, payload.get("event_id"))

    family_id_str = payload.get("family_id")
    if not family_id_str:
        logger.warning("briefing event %s missing family_id, skipping", event_type)
        return

    try:
        from uuid import UUID
        from ....modules.briefing.services.accumulator import BriefingAccumulator

        accumulator = BriefingAccumulator()
        family_id = UUID(family_id_str)

        if event_type == "EventCurated":
            event_id_str = payload.get("event_id", "")
            await accumulator.on_event_curated(
                family_id=family_id,
                event_id=UUID(event_id_str) if event_id_str else UUID(int=0),
                event_type=payload.get("curated_event_type", "unknown"),
                priority=payload.get("priority", "normal"),
                title=payload.get("title", ""),
            )
        elif event_type in ("DateApproaching", "InsightGenerated", "MemoryExtracted"):
            await accumulator.on_proactive_trigger(
                family_id=family_id,
                trigger_type=event_type,
                trigger_data=payload,
                priority=payload.get("priority", "normal"),
            )
        else:
            # PreparationToggled, FavorRecorded, GiftTaskStatusChanged
            await accumulator.on_proactive_trigger(
                family_id=family_id,
                trigger_type=event_type,
                trigger_data=payload,
                priority=payload.get("priority", "normal"),
            )
    except Exception as e:
        logger.error("Failed to handle briefing event %s: %s", event_type, e)


async def _handle_memory_event(event_type: str, payload: dict) -> None:
    """memory-workers: TripCreated, TripCompleted, FavorRecorded.

    Receives memory-relevant domain events for future processing
    (e.g., extracting memories from completed trips).
    """
    logger.info("memory-workers received %s (id=%s)", event_type, payload.get("event_id"))


async def _handle_graph_event(event_type: str, payload: dict) -> None:
    """graph-workers: EventCurated.

    Receives curated events for knowledge graph updates.
    """
    logger.info("graph-workers received %s (id=%s)", event_type, payload.get("event_id"))


async def _handle_member_event(event_type: str, payload: dict) -> None:
    """member-workers: MemoryExtracted.

    Receives memory extraction events to update member profiles.
    """
    logger.info("member-workers received %s (id=%s)", event_type, payload.get("event_id"))


async def _handle_ws_bridge_event(event_type: str, payload: dict) -> None:
    """ws-bridge-workers: MemoryExtracted → publish to user's WS channel.

    PLAN-011: Bridges internal domain events to frontend via WebSocket PubSub.
    No LLM call — simple event relay so users see system intelligence in action.
    """
    user_id_str = payload.get("user_id")
    if not user_id_str:
        logger.debug("ws-bridge %s missing user_id, skipping", event_type)
        return

    logger.info(
        "ws-bridge publishing %s to user %s",
        event_type, user_id_str,
    )

    try:
        import uuid as _uuid
        from ...pubsub import get_pubsub_manager
        from ...pubsub.types import MessageType, PubSubMessage

        pubsub = get_pubsub_manager()
        message = PubSubMessage(
            user_id=user_id_str,
            message_type=MessageType.MEMORY_EXTRACTED,
            payload={
                "summary": payload.get("memory_type", "memory"),
                "entities": payload.get("entities", {}),
                "mentioned_persons": payload.get("mentioned_persons", []),
            },
            trace_id=payload.get("event_id", str(_uuid.uuid4())),
        )
        await pubsub.publish(user_id_str, message)
    except Exception as e:
        logger.warning("ws-bridge %s publish failed: %s", event_type, e)


# ---------------------------------------------------------------------------
# Public registration helper
# ---------------------------------------------------------------------------

def register_stream_consumers(consumer: Optional[EventConsumer] = None) -> EventConsumer:
    """Create and configure an ``EventConsumer`` with all required registrations.

    Args:
        consumer: An existing consumer instance to register on.
                  If ``None``, a new one is created.

    Returns:
        The fully-configured consumer (not yet started).
    """
    if consumer is None:
        consumer = EventConsumer()

    # --- events:curation → curation-workers ---
    for event_type in (
        "TripCreated",
        "TripUpdated",
        "TripCancelled",
        "TripDeleted",
        "MemoryExtracted",
        "DateApproaching",
        "EventRequested",
    ):
        consumer.register(event_type, "curation-workers", _handle_curation_event)

    # --- events:briefing → briefing-workers ---
    for event_type in (
        "EventCurated",
        "PreparationToggled",
        "FavorRecorded",
        "DateApproaching",
        "GiftTaskStatusChanged",
        "InsightGenerated",
        "MemoryExtracted",
    ):
        consumer.register(event_type, "briefing-workers", _handle_briefing_event)

    # --- events:memory → memory-workers ---
    for event_type in (
        "TripCreated",
        "TripCompleted",
        "FavorRecorded",
    ):
        consumer.register(event_type, "memory-workers", _handle_memory_event)

    # --- events:graph → graph-workers ---
    consumer.register("EventCurated", "graph-workers", _handle_graph_event)

    # --- events:member → member-workers ---
    consumer.register("MemoryExtracted", "member-workers", _handle_member_event)

    # --- events:ws-bridge → ws-bridge-workers (PLAN-011) ---
    consumer.register("MemoryExtracted", "ws-bridge-workers", _handle_ws_bridge_event)

    logger.info(
        "Registered %d stream consumer handlers across 6 consumer groups",
        len(consumer._registrations),
    )
    return consumer
