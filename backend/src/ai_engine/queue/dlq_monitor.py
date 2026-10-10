"""
Dead Letter Queue (DLQ) depth monitor.

Periodically checks the depth of the ``agent:tasks:dlq`` Redis Stream
and logs a critical warning when the depth exceeds a threshold. Exposes
a Prometheus gauge when the metrics library is available.

Messages older than ``EXPIRE_DAYS`` are automatically trimmed on each
check cycle.
"""
import asyncio
import logging
import time
from typing import List, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 60  # seconds
ALERT_THRESHOLD = 10
DLQ_STREAM_KEY = "agent:tasks:dlq"
EXPIRE_DAYS = 7
TRIM_BATCH_SIZE = 100  # max IDs to delete per cycle


class DLQMonitor:
    """Monitors the depth of the agent task DLQ.

    Start as a background task during worker startup::

        asyncio.create_task(DLQMonitor(redis_client).run())
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client
        self._gauge: Optional[object] = None
        try:
            from ...core.observability.metrics import Gauge
            self._gauge = Gauge(
                "secretary_dlq_depth",
                "Number of messages in the agent task DLQ",
            )
        except Exception:
            pass

    async def _trim_expired(self) -> int:
        """Remove messages older than EXPIRE_DAYS. Returns count deleted."""
        cutoff_ms = int((time.time() - EXPIRE_DAYS * 86400) * 1000)
        # XRANGE with max-id retrieves only messages before the cutoff
        entries: List = await self._redis.xrange(
            DLQ_STREAM_KEY, min="-", max=str(cutoff_ms), count=TRIM_BATCH_SIZE,
        )
        if not entries:
            return 0
        ids = [entry_id for entry_id, _ in entries]
        deleted = await self._redis.xdel(DLQ_STREAM_KEY, *ids)
        return deleted

    async def run(self) -> None:
        """Infinite loop: check DLQ depth every CHECK_INTERVAL seconds."""
        logger.info(
            "DLQ monitor started (interval=%ds, threshold=%d, expire=%dd)",
            CHECK_INTERVAL, ALERT_THRESHOLD, EXPIRE_DAYS,
        )
        while True:
            try:
                await asyncio.sleep(CHECK_INTERVAL)

                # Trim expired messages first
                trimmed = await self._trim_expired()
                if trimmed > 0:
                    logger.info("DLQ trimmed %d expired message(s)", trimmed)

                depth = await self._redis.xlen(DLQ_STREAM_KEY)

                if self._gauge is not None:
                    self._gauge.set(depth)

                if depth >= ALERT_THRESHOLD:
                    logger.critical(
                        "DLQ depth exceeds threshold: depth=%d threshold=%d",
                        depth,
                        ALERT_THRESHOLD,
                    )
                elif depth > 0:
                    logger.warning("DLQ depth: %d", depth)
            except asyncio.CancelledError:
                logger.info("DLQ monitor stopped")
                return
            except Exception as e:
                logger.error("DLQ monitor error: %s", e)
