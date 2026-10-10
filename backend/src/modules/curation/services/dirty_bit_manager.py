"""DirtyBitManager — Redis-based accumulation queue for deferred triggers.

Accumulates LOW/MEDIUM impact changes in a Redis HASH per family,
batch-processing them when a threshold is reached or a timeout expires.
Using HASH (hset/hgetall) instead of LIST ensures natural deduplication
by ``{trigger_type}:{entity_id}`` — repeated writes for the same entity
simply overwrite the previous payload.

HIGH impact triggers bypass the queue entirely (immediate dispatch).
SILENT triggers are handled inline without queueing.

Anti-starvation: A Redis NX+EX timer key ensures that even slow-drip
changes are flushed within DEBOUNCE_WINDOW_SECONDS.

Retry policy (PLAN-009): mark_dirty and flush_dirty retry up to 3 times
with exponential backoff (1s/2s/4s) for transient Redis failures.
Deserialization failures logged at WARNING with dead-letter after 3 fails.

V8 architecture: docs/architecture-v8-secretary-brain.md section 4.4
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .impact_arbitrator import (
    ImpactArbitrator,
    ImpactAssessment,
    ImpactLevel,
    TriggerContext,
)

logger = logging.getLogger(__name__)

# Retry policy constants (PLAN-009)
_MAX_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1.0  # 1s, 2s, 4s exponential backoff
_DEAD_LETTER_KEY_PREFIX = "dirty:dead_letter"
_MAX_DESER_FAILURES = 3


async def _retry_redis_op(coro_factory, description: str = "redis_op"):
    """Retry an async Redis operation with exponential backoff.

    Args:
        coro_factory: A callable that returns a new coroutine each time.
        description: Human-readable label for logging.

    Returns:
        The result of the operation.

    Raises:
        The last exception if all attempts fail.
    """
    last_exc = None
    for attempt in range(_MAX_RETRY_ATTEMPTS):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRY_ATTEMPTS - 1:
                delay = _RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                logger.warning(
                    "Redis %s failed (attempt %d/%d), retrying in %.1fs: %s",
                    description, attempt + 1, _MAX_RETRY_ATTEMPTS, delay, exc,
                )
                await asyncio.sleep(delay)
            else:
                logger.warning(
                    "Redis %s failed after %d attempts: %s",
                    description, _MAX_RETRY_ATTEMPTS, exc,
                )
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DirtyEntry:
    """A single queued dirty-bit entry.

    Attributes:
        trigger_type: Type of trigger (e.g. "trip_updated", "memory_extracted")
        entity_id: ID of the affected entity (trip, memory, event, etc.)
        impact_level: Assessed impact level
        timestamp: Unix timestamp when the entry was created
        payload: Original trigger payload (preserved for batch processing)
    """
    trigger_type: str
    entity_id: str
    impact_level: str
    timestamp: float
    payload: Dict[str, Any]

    def serialize(self) -> str:
        """Serialize to JSON string for Redis storage."""
        return json.dumps({
            "trigger_type": self.trigger_type,
            "entity_id": self.entity_id,
            "impact_level": self.impact_level,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }, ensure_ascii=False)

    @classmethod
    def deserialize(cls, raw: str) -> "DirtyEntry":
        """Deserialize from JSON string."""
        data = json.loads(raw)
        return cls(
            trigger_type=data["trigger_type"],
            entity_id=data["entity_id"],
            impact_level=data["impact_level"],
            timestamp=data["timestamp"],
            payload=data.get("payload", {}),
        )


# ---------------------------------------------------------------------------
# DirtyBitManager
# ---------------------------------------------------------------------------

class DirtyBitManager:
    """Redis-based dirty bit accumulation queue with anti-starvation.

    Flow:
    1. Caller invokes mark_dirty() with trigger context
    2. ImpactArbitrator assesses the impact
    3. Based on level:
       - SILENT → silent callback (no queue)
       - HIGH → immediate dispatch callback
       - LOW/MEDIUM → enqueue in Redis HASH, check threshold/timer

    The manager does NOT import Celery or any task module directly.
    Instead, callers provide callback functions for dispatch actions.
    """

    QUEUE_KEY_PREFIX = "curation:dirty"
    TIMER_KEY_PREFIX = "dirty_timer"

    def __init__(
        self,
        redis_client: Any,
        arbitrator: Optional[ImpactArbitrator] = None,
        batch_threshold: int = 5,
        debounce_window_seconds: int = 300,
    ):
        """Initialize DirtyBitManager.

        Args:
            redis_client: RedisClient instance (must have .client property)
            arbitrator: ImpactArbitrator instance (created if not provided)
            batch_threshold: Number of entries before batch flush
            debounce_window_seconds: Max seconds before forced flush
        """
        self._redis = redis_client
        self._arbitrator = arbitrator or ImpactArbitrator()
        self._batch_threshold = max(1, batch_threshold)
        self._debounce_window_seconds = max(1, debounce_window_seconds)

    @property
    def _queue_key(self) -> str:
        """Base prefix for queue keys."""
        return self.QUEUE_KEY_PREFIX

    def _family_queue_key(self, family_id: str) -> str:
        """Redis key for a family's dirty queue."""
        return f"{self.QUEUE_KEY_PREFIX}:{family_id}"

    def _family_timer_key(self, family_id: str) -> str:
        """Redis key for a family's anti-starvation timer."""
        return f"{self.TIMER_KEY_PREFIX}:{family_id}"

    async def mark_dirty(
        self,
        family_id: str,
        context: TriggerContext,
        entity_id: str,
        on_silent: Optional[Any] = None,
        on_immediate: Optional[Any] = None,
        on_batch_ready: Optional[Any] = None,
    ) -> ImpactAssessment:
        """Assess impact and route trigger to the appropriate handler.

        Args:
            family_id: Family ID
            context: Trigger context for impact assessment
            entity_id: ID of the affected entity
            on_silent: async callback(family_id, context) for SILENT level
            on_immediate: async callback(family_id, context, assessment) for HIGH level
            on_batch_ready: async callback(family_id, entries) when batch threshold reached

        Returns:
            The ImpactAssessment result.
        """
        assessment = self._arbitrator.assess(context)

        if assessment.level == ImpactLevel.SILENT:
            if on_silent is not None:
                try:
                    await on_silent(family_id, context)
                except Exception as e:
                    logger.warning(
                        "Silent handler failed for family=%s: %s", family_id, e,
                    )
            return assessment

        if assessment.level == ImpactLevel.HIGH:
            if on_immediate is not None:
                try:
                    await on_immediate(family_id, context, assessment)
                except Exception as e:
                    logger.warning(
                        "Immediate dispatch failed for family=%s: %s", family_id, e,
                    )
            return assessment

        # LOW or MEDIUM: accumulate in Redis queue
        entry = DirtyEntry(
            trigger_type=context.trigger_type,
            entity_id=entity_id,
            impact_level=assessment.level.value,
            timestamp=time.time(),
            payload=context.payload,
        )

        queue_key = self._family_queue_key(family_id)
        raw_client = self._get_raw_client()
        if raw_client is None:
            logger.warning(
                "Redis not available, dispatching immediately for family=%s",
                family_id,
            )
            if on_immediate is not None:
                try:
                    await on_immediate(family_id, context, assessment)
                except Exception as e:
                    logger.warning("Fallback immediate dispatch failed: %s", e)
            return assessment

        hash_field = f"{context.trigger_type}:{entity_id}"
        try:
            serialized = entry.serialize()
            await _retry_redis_op(
                lambda: raw_client.hset(queue_key, hash_field, serialized),
                description=f"mark_dirty({family_id})",
            )
            queue_len = await raw_client.hlen(queue_key)
        except Exception as exc:
            logger.warning(
                "Redis mark_dirty exhausted retries for family=%s, "
                "falling back to immediate dispatch: %s",
                family_id, exc,
            )
            if on_immediate is not None:
                try:
                    await on_immediate(family_id, context, assessment)
                except Exception as e:
                    logger.warning("Fallback immediate dispatch failed: %s", e)
            return assessment

        logger.debug(
            "Dirty bit queued: family=%s, type=%s, entity=%s, level=%s, depth=%d",
            family_id, context.trigger_type, entity_id,
            assessment.level.value, queue_len,
        )

        if queue_len >= self._batch_threshold:
            entries = await self.flush_dirty(family_id)
            if on_batch_ready is not None and entries:
                try:
                    await on_batch_ready(family_id, entries)
                except Exception as e:
                    logger.warning(
                        "Batch dispatch failed for family=%s: %s", family_id, e,
                    )
        else:
            await self._ensure_timeout_flush(family_id)

        return assessment

    async def flush_dirty(self, family_id: str) -> List[DirtyEntry]:
        """Atomically get all entries and clear the queue.

        Retries on transient Redis failure (PLAN-009, TC-12).
        Deserialization failures logged at WARNING. Entries failing
        deserialization are sent to dead-letter after _MAX_DESER_FAILURES.

        Returns:
            List of DirtyEntry objects that were in the queue.
        """
        raw_client = self._get_raw_client()
        if raw_client is None:
            return []

        queue_key = self._family_queue_key(family_id)
        timer_key = self._family_timer_key(family_id)

        # Atomic get-and-delete via pipeline (with retry)
        try:
            async def _pipeline_op():
                pipe = raw_client.pipeline()
                pipe.hgetall(queue_key)
                pipe.delete(queue_key)
                pipe.delete(timer_key)
                return await pipe.execute()

            results = await _retry_redis_op(
                _pipeline_op, description=f"flush_dirty({family_id})",
            )
        except Exception as exc:
            logger.warning(
                "flush_dirty exhausted retries for family=%s: %s",
                family_id, exc,
            )
            return []

        raw_hash = results[0] or {}
        entries: List[DirtyEntry] = []
        deser_failures: List[str] = []
        for field_key, raw in raw_hash.items():
            try:
                entries.append(DirtyEntry.deserialize(raw))
            except Exception as e:
                logger.warning(
                    "Failed to deserialize dirty entry for family=%s: %s",
                    family_id, e,
                )
                field_name = field_key.decode() if isinstance(field_key, bytes) else str(field_key)
                deser_failures.append(field_name)

        # Dead-letter: write failed entries to a dead-letter key
        if deser_failures:
            try:
                dead_letter_key = f"{_DEAD_LETTER_KEY_PREFIX}:{family_id}"
                for field_name in deser_failures:
                    raw_value = raw_hash.get(
                        field_name.encode() if isinstance(field_name, str) else field_name,
                        b"",
                    )
                    await raw_client.hset(
                        dead_letter_key, field_name,
                        raw_value if isinstance(raw_value, (str, bytes)) else str(raw_value),
                    )
                # Set 7-day TTL on dead-letter key to prevent unbounded growth (V-003)
                await raw_client.expire(dead_letter_key, 86400 * 7)
                logger.warning(
                    "Sent %d deserialization failures to dead-letter for family=%s (7d TTL)",
                    len(deser_failures), family_id,
                )
            except Exception as dl_exc:
                logger.warning(
                    "Failed to write dead-letter entries for family=%s: %s",
                    family_id, dl_exc,
                )

        if entries:
            logger.info(
                "Flushed %d dirty entries for family=%s", len(entries), family_id,
            )

        return entries

    async def get_queue_depth(self, family_id: str) -> int:
        """Get the number of queued dirty entries for a family.

        Useful for observability and monitoring dashboards.
        """
        raw_client = self._get_raw_client()
        if raw_client is None:
            return 0

        queue_key = self._family_queue_key(family_id)
        return await raw_client.hlen(queue_key)

    async def has_timer(self, family_id: str) -> bool:
        """Check if the anti-starvation timer is active for a family."""
        raw_client = self._get_raw_client()
        if raw_client is None:
            return False

        timer_key = self._family_timer_key(family_id)
        return bool(await raw_client.exists(timer_key))

    async def _ensure_timeout_flush(self, family_id: str) -> bool:
        """Set anti-starvation timer if not already active.

        Uses SET NX EX to ensure the timer only starts on the first dirty
        bit and doesn't reset on subsequent ones. When the timer expires,
        a Celery Beat scan or Redis keyspace notification triggers flush.

        Returns:
            True if a new timer was set, False if one already existed.
        """
        raw_client = self._get_raw_client()
        if raw_client is None:
            return False

        timer_key = self._family_timer_key(family_id)
        result = await raw_client.set(
            timer_key,
            "1",
            ex=self._debounce_window_seconds,
            nx=True,
        )
        if result:
            logger.debug(
                "Anti-starvation timer set for family=%s (%ds)",
                family_id, self._debounce_window_seconds,
            )
        return bool(result)

    async def get_stale_families(self) -> List[str]:
        """Return family IDs that have dirty entries but no timer.

        These are candidates for forced flush — the timer expired or was
        never created, yet entries remain in the queue.
        """
        raw_client = self._get_raw_client()
        if raw_client is None:
            return []

        stale: List[str] = []
        prefix = f"{self.QUEUE_KEY_PREFIX}:"
        cursor = 0
        while True:
            cursor, keys = await raw_client.scan(
                cursor=cursor, match=f"{prefix}*", count=100,
            )
            for key in keys:
                # key is b"curation:dirty:<family_id>" or str
                key_str = key.decode() if isinstance(key, bytes) else key
                family_id = key_str[len(prefix):]
                timer_key = self._family_timer_key(family_id)
                has_timer = await raw_client.exists(timer_key)
                if not has_timer:
                    stale.append(family_id)
            if cursor == 0:
                break

        return stale

    def _get_raw_client(self):
        """Get the underlying async Redis connection.

        Returns None if Redis is not connected.
        """
        if hasattr(self._redis, "client"):
            return self._redis.client
        return self._redis
