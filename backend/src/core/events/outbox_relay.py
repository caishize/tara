"""Transactional Outbox Relay.

Reads committed domain events from the event_outbox table
and publishes them to Redis Streams for cross-process delivery.

Pattern: DB transaction commits event + outbox row atomically,
then relay polls outbox and publishes to Redis Streams.

Registered as a Celery Beat task running every 5 seconds.
"""

import json
import logging
from datetime import datetime, timezone

from celery import shared_task

logger = logging.getLogger(__name__)

# Maximum rows to relay per invocation to bound latency
RELAY_BATCH_SIZE = 100

# Redis Stream key prefix: events are published to "events:{event_type}"
STREAM_KEY_PREFIX = "events"

# Cap stream length to prevent unbounded growth (per event type)
STREAM_MAXLEN = 10_000


@shared_task(name="events.relay_outbox")
def relay_outbox() -> dict:
    """Read unpublished outbox rows and publish to Redis Streams.

    This task is idempotent: if it crashes after publishing but before
    marking rows as published, the next invocation will re-publish them.
    Consumers must be idempotent (at-least-once delivery).

    Returns:
        Summary dict with count of relayed events.
    """
    from ...core.cache import get_redis_client
    from ...db.session import SessionLocal
    from ...core.utils.timezone import utc_now

    redis = get_redis_client()
    if redis is None:
        logger.error("Redis unavailable, skipping outbox relay")
        return {"error": "redis_unavailable"}

    session = SessionLocal()
    try:
        return _relay_batch(session, redis)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _relay_batch(session, redis) -> dict:
    """Fetch unpublished events and publish to Redis Streams."""
    from sqlalchemy import text
    from ...core.utils.timezone import utc_now

    # Fetch unpublished rows ordered by created_at (FIFO)
    rows = session.execute(
        text(
            "SELECT id, event_type, payload, correlation_id, created_at "
            "FROM event_outbox "
            "WHERE published_at IS NULL "
            "ORDER BY created_at "
            "LIMIT :limit"
        ),
        {"limit": RELAY_BATCH_SIZE},
    ).fetchall()

    if not rows:
        return {"relayed": 0}

    published_ids = []
    for row in rows:
        row_id, event_type, payload, correlation_id, created_at = row
        stream_key = f"{STREAM_KEY_PREFIX}:{event_type}"

        # Build the stream message — Redis Streams accept flat string mappings
        message = {
            "event_id": str(row_id),
            "event_type": event_type,
            "payload": json.dumps(payload, ensure_ascii=False, default=str),
            "correlation_id": str(correlation_id) if correlation_id else "",
            "created_at": created_at.isoformat() if created_at else "",
        }

        try:
            redis.xadd(stream_key, message, maxlen=STREAM_MAXLEN)
            published_ids.append(row_id)  # keep as UUID for SQL
        except Exception as e:
            logger.error(
                "Failed to publish event %s to stream %s: %s",
                row_id, stream_key, e,
            )
            # Stop batch on first failure to preserve ordering
            break

    # Mark published rows
    if published_ids:
        now = utc_now()
        session.execute(
            text(
                "UPDATE event_outbox "
                "SET published_at = :now "
                "WHERE id = ANY(:ids)"
            ),
            {"now": now, "ids": published_ids},
        )
        session.commit()
        logger.info("Relayed %d events to Redis Streams", len(published_ids))

    return {"relayed": len(published_ids)}
