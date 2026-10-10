"""Domain Event Consumer.

Reads domain events from Redis Streams and dispatches them
to registered handlers. Supports consumer groups for
at-least-once delivery.

Each module registers its own consumer group so events are
independently consumed by different parts of the system.

Usage:
    consumer = EventConsumer()
    consumer.register("ImportantDateCreated", "gift-module", handle_date_created)
    consumer.register("ImportantDateCreated", "reminder-module", handle_reminder)
    await consumer.start()  # blocking loop
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Dict, List, Optional, Tuple

import redis.asyncio as aioredis

from ...config.settings import settings

logger = logging.getLogger(__name__)

# Stream key prefix (must match outbox_relay.STREAM_KEY_PREFIX)
STREAM_KEY_PREFIX = "events"

# How long to block on XREADGROUP before checking for shutdown
BLOCK_MS = 2_000

# Batch size per read
READ_COUNT = 50

# Handler type: receives (event_type, payload_dict)
EventStreamHandler = Callable[[str, dict], Awaitable[None]]


@dataclass
class _Registration:
    """Internal: a single handler registration."""
    event_type: str
    group: str
    consumer_name: str
    handler: EventStreamHandler


class EventConsumer:
    """Consumes domain events from Redis Streams using consumer groups.

    Supports multiple handler registrations per event type. Each
    (event_type, group) pair gets an independent read position, so
    different modules can process the same event independently.
    """

    def __init__(self, consumer_name: Optional[str] = None):
        """
        Args:
            consumer_name: Unique name for this consumer instance.
                           Defaults to a combination of hostname + PID.
        """
        if consumer_name is None:
            import os
            import socket
            consumer_name = f"{socket.gethostname()}-{os.getpid()}"
        self._consumer_name = consumer_name
        self._registrations: List[_Registration] = []
        self._running = False
        self._redis: Optional[aioredis.Redis] = None

    def register(
        self,
        event_type: str,
        group: str,
        handler: EventStreamHandler,
    ) -> None:
        """Register a handler for an event type + consumer group.

        Args:
            event_type: The domain event class name (e.g. "ImportantDateCreated").
            group: Consumer group name (e.g. "gift-module").
            handler: Async callable receiving (event_type, payload_dict).
        """
        self._registrations.append(
            _Registration(
                event_type=event_type,
                group=group,
                consumer_name=self._consumer_name,
                handler=handler,
            )
        )
        logger.debug(
            "Registered handler for %s in group %s", event_type, group
        )

    async def start(self) -> None:
        """Start consuming events. Blocks until stop() is called."""
        self._redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self._running = True

        # Ensure consumer groups exist (MKSTREAM creates the stream if absent)
        await self._ensure_groups()

        try:
            await self._consume_loop()
        finally:
            self._running = False
            if self._redis:
                await self._redis.close()
                self._redis = None

    async def stop(self) -> None:
        """Signal the consumer to stop after the current iteration."""
        self._running = False

    async def _ensure_groups(self) -> None:
        """Create consumer groups for each registration if they don't exist."""
        seen = set()
        for reg in self._registrations:
            key = (reg.event_type, reg.group)
            if key in seen:
                continue
            seen.add(key)

            stream_key = f"{STREAM_KEY_PREFIX}:{reg.event_type}"
            try:
                await self._redis.xgroup_create(
                    stream_key, reg.group, id="0", mkstream=True
                )
                logger.info(
                    "Created consumer group %s for stream %s",
                    reg.group, stream_key,
                )
            except aioredis.ResponseError as e:
                # "BUSYGROUP Consumer Group name already exists"
                if "BUSYGROUP" in str(e):
                    pass
                else:
                    raise

    async def _consume_loop(self) -> None:
        """Main read loop — reads from all registered streams."""
        # Build a mapping: (stream_key, group) -> list of handlers
        group_handlers: Dict[Tuple[str, str], List[EventStreamHandler]] = {}
        for reg in self._registrations:
            stream_key = f"{STREAM_KEY_PREFIX}:{reg.event_type}"
            key = (stream_key, reg.group)
            group_handlers.setdefault(key, []).append(reg.handler)

        while self._running:
            for (stream_key, group), handlers in group_handlers.items():
                try:
                    messages = await self._redis.xreadgroup(
                        groupname=group,
                        consumername=self._consumer_name,
                        streams={stream_key: ">"},
                        count=READ_COUNT,
                        block=BLOCK_MS,
                    )
                except Exception as e:
                    logger.error("Error reading stream %s: %s", stream_key, e)
                    await asyncio.sleep(1)
                    continue

                if not messages:
                    continue

                for _stream, entries in messages:
                    for message_id, data in entries:
                        await self._dispatch(
                            stream_key, group, message_id, data, handlers
                        )

    async def _dispatch(
        self,
        stream_key: str,
        group: str,
        message_id: str,
        data: dict,
        handlers: List[EventStreamHandler],
    ) -> None:
        """Dispatch a single message to all handlers, then ACK."""
        event_type = data.get("event_type", "")
        raw_payload = data.get("payload", "{}")
        try:
            payload = json.loads(raw_payload)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Invalid payload in message %s on %s, ACKing to skip",
                message_id, stream_key,
            )
            await self._redis.xack(stream_key, group, message_id)
            return

        all_ok = True
        for handler in handlers:
            try:
                await handler(event_type, payload)
            except Exception as e:
                logger.error(
                    "Handler error for %s (msg %s): %s",
                    event_type, message_id, e,
                    exc_info=True,
                )
                all_ok = False

        if all_ok:
            await self._redis.xack(stream_key, group, message_id)
        else:
            # Leave unACKed so it enters the PEL (pending entries list)
            # and can be retried via XCLAIM or XAUTOCLAIM later.
            logger.warning(
                "Message %s on %s left unACKed due to handler errors",
                message_id, stream_key,
            )
