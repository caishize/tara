"""
Redis Streams Task Queue for Agent Worker dispatch.

Uses Redis Streams for reliable async task processing with consumer groups.
"""
import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ...core.utils.timezone import utc_now
from typing import Any, Deque, Dict, List, Optional
from uuid import uuid4

import redis.asyncio as redis

from ...config.settings import settings
from .types import TaskStatus


logger = logging.getLogger(__name__)


@dataclass
class TaskPayload:
    """
    Task payload for Agent Worker processing.

    Attributes:
        job_id: Unique task identifier
        user_id: User who initiated the task
        family_id: User's family ID
        user_input: Original user message
        route_type: slow or hybrid_background
        context_snapshot: Minimal context hints for rehydration
        created_at: Task creation timestamp
        metadata: Additional task metadata
    """
    job_id: str
    user_id: str
    family_id: str
    user_input: str
    route_type: str
    session_id: Optional[str] = None
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: utc_now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        result = {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "family_id": self.family_id,
            "user_input": self.user_input,
            "route_type": self.route_type,
            "context_snapshot": json.dumps(self.context_snapshot),
            "created_at": self.created_at,
            "metadata": json.dumps(self.metadata),
        }
        if self.session_id is not None:
            result["session_id"] = self.session_id
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskPayload":
        """Create from Redis stream entry."""
        context_snapshot = data.get("context_snapshot", "{}")
        if isinstance(context_snapshot, str):
            try:
                context_snapshot = json.loads(context_snapshot)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse context_snapshot JSON: %.200s", context_snapshot)
                context_snapshot = {}

        metadata = data.get("metadata", "{}")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse metadata JSON: %.200s", metadata)
                metadata = {}

        return cls(
            job_id=data["job_id"],
            user_id=data["user_id"],
            family_id=data["family_id"],
            user_input=data["user_input"],
            route_type=data.get("route_type", "slow"),
            session_id=data.get("session_id"),
            context_snapshot=context_snapshot,
            created_at=data.get("created_at", utc_now().isoformat()),
            metadata=metadata,
        )


class TaskQueue:
    """
    Redis Streams based task queue for Agent Workers.

    Features:
    - Consumer groups for horizontal scaling
    - Automatic message acknowledgment
    - Dead letter queue for failed tasks
    - Pending message recovery

    Usage:
        # Enqueue (API Gateway)
        queue = TaskQueue()
        await queue.connect()
        job_id = await queue.enqueue(TaskPayload(...))

        # Dequeue (Agent Worker)
        task = await queue.dequeue("agent_workers", "worker_1")
        if task:
            # Process task...
            await queue.ack(task.job_id)
    """

    # Stream and consumer group names
    STREAM_KEY = "agent:tasks"
    CONSUMER_GROUP = "agent_workers"
    DLQ_STREAM_KEY = "agent:tasks:dlq"

    # Timeouts
    READ_TIMEOUT_MS = 1000    # 1 second - block time for reading (low for fast pickup)

    # Stream size limits (approximate; ~ prefix enables efficient trimming)
    STREAM_MAXLEN = 10000
    DLQ_STREAM_MAXLEN = 5000

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._lock = asyncio.Lock()
        self._affinity_ttl = settings.session_affinity_ttl_seconds
        self._worker_heartbeat_ttl = settings.worker_heartbeat_ttl_seconds
        self._claim_timeout_ms = settings.claim_timeout_ms
        self._max_delivery_count = settings.max_delivery_count
        # Claimed stale tasks are buffered and consumed before reading new entries.
        self._claimed_buffer: Deque[TaskPayload] = deque()

    async def connect(self) -> None:
        """Initialize Redis connection."""
        async with self._lock:
            if self._client is None:
                self._client = redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=20,
                )

                # Ensure consumer group exists
                await self._ensure_consumer_group()

            logger.info("Task queue connected")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
        logger.info("Task queue disconnected")

    async def _ensure_consumer_group(self) -> None:
        """Create consumer group if it doesn't exist."""
        try:
            await self._client.xgroup_create(
                self.STREAM_KEY,
                self.CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
            logger.info("Created consumer group: %s", self.CONSUMER_GROUP)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            # Group already exists, that's fine

    async def enqueue(self, task: TaskPayload) -> str:
        """
        Enqueue a task for processing.

        Args:
            task: Task payload to enqueue

        Returns:
            Redis stream message ID
        """
        if self._client is None:
            await self.connect()

        try:
            message_id = await self._client.xadd(
                self.STREAM_KEY,
                task.to_dict(),
                maxlen=self.STREAM_MAXLEN,
                approximate=True,
            )
            logger.info(
                "Enqueued task job_id=%s, message_id=%s, route=%s",
                task.job_id, message_id, task.route_type,
            )
            return message_id
        except Exception as e:
            logger.error("Failed to enqueue task: %s", e)
            raise

    async def dequeue(
        self,
        consumer_group: str,
        consumer_name: str,
        count: int = 1,
    ) -> Optional[TaskPayload]:
        """
        Dequeue a task from the queue.

        Uses XREADGROUP for consumer group semantics:
        - Each message is delivered to exactly one consumer
        - Messages must be acknowledged after processing
        - Unacknowledged messages can be claimed by other consumers

        Args:
            consumer_group: Consumer group name
            consumer_name: Unique consumer identifier
            count: Maximum number of tasks to fetch (default 1)

        Returns:
            TaskPayload if available, None otherwise
        """
        if self._client is None:
            await self.connect()

        try:
            # First drain locally buffered stale claims from the previous poll.
            while self._claimed_buffer:
                buffered_task = self._claimed_buffer.popleft()
                maybe_task = await self._apply_session_affinity(
                    buffered_task,
                    consumer_group,
                    consumer_name,
                    buffered_task.metadata.get("_stream_message_id", ""),
                )
                if maybe_task is not None:
                    logger.debug(
                        "Dequeued claimed buffered task job_id=%s, message_id=%s, consumer=%s",
                        maybe_task.job_id,
                        maybe_task.metadata.get("_stream_message_id", ""),
                        consumer_name,
                    )
                    return maybe_task

            # Then claim pending messages that have been idle too long.
            # XCLAIM only changes ownership in PEL; these entries are not returned
            # by XREADGROUP with ">", so we must consume them explicitly.
            claimed = await self._claim_stale_messages(consumer_group, consumer_name)
            if claimed:
                # Keep remaining claimed tasks for subsequent dequeue() calls.
                if len(claimed) > 1:
                    self._claimed_buffer.extend(claimed[1:])

                first_claimed = claimed[0]
                maybe_task = await self._apply_session_affinity(
                    first_claimed,
                    consumer_group,
                    consumer_name,
                    first_claimed.metadata.get("_stream_message_id", ""),
                )
                if maybe_task is not None:
                    logger.debug(
                        "Dequeued claimed task job_id=%s, message_id=%s, consumer=%s",
                        maybe_task.job_id,
                        maybe_task.metadata.get("_stream_message_id", ""),
                        consumer_name,
                    )
                    return maybe_task

            # Read new messages
            result = await self._client.xreadgroup(
                groupname=consumer_group,
                consumername=consumer_name,
                streams={self.STREAM_KEY: ">"},  # Only new messages
                count=count,
                block=self.READ_TIMEOUT_MS,
            )

            if not result:
                return None

            # Parse first message
            stream_name, messages = result[0]
            if not messages:
                return None

            message_id, fields = messages[0]

            # Store message_id in metadata for acknowledgment
            task = TaskPayload.from_dict(fields)
            task.metadata["_stream_message_id"] = message_id

            task = await self._apply_session_affinity(
                task, consumer_group, consumer_name, message_id
            )
            if task is None:
                return None

            logger.debug(
                "Dequeued task job_id=%s, message_id=%s, consumer=%s",
                task.job_id, message_id, consumer_name,
            )
            return task

        except Exception as e:
            logger.error("Failed to dequeue task: %s", e)
            raise

    async def _apply_session_affinity(
        self,
        task: TaskPayload,
        consumer_group: str,
        consumer_name: str,
        message_id: str,
    ) -> Optional[TaskPayload]:
        """Apply session-affinity routing rules for a dequeued task."""
        if not task.session_id:
            return task

        affinity_worker = await self.get_session_affinity(task.session_id)
        if affinity_worker and affinity_worker != consumer_name:
            redirected = await self._redirect_to_affinity_worker(
                consumer_group, affinity_worker, message_id,
            )
            if redirected:
                logger.debug(
                    "Redirected task %s to affinity worker %s",
                    task.job_id, affinity_worker,
                )
                return None
            logger.warning(
                "Failed to redirect task %s to affinity worker %s; "
                "processing on %s",
                task.job_id, affinity_worker, consumer_name,
            )
            return task

        if not affinity_worker:
            await self.set_session_affinity(task.session_id, consumer_name)
        return task

    async def _claim_stale_messages(
        self,
        consumer_group: str,
        consumer_name: str,
    ) -> List[TaskPayload]:
        """
        Claim messages that have been pending too long.

        This handles worker failures by allowing other workers to
        pick up abandoned tasks.  Messages that exceed
        ``max_delivery_count`` are moved to the DLQ instead of being
        re-claimed, preventing poison-message loops.
        """
        claimed = []
        try:
            # Get pending messages
            pending = await self._client.xpending_range(
                self.STREAM_KEY,
                consumer_group,
                min="-",
                max="+",
                count=10,
            )

            for entry in pending:
                message_id = entry["message_id"]
                idle_time = entry["time_since_delivered"]
                owner = entry.get("consumer")
                times_delivered = entry.get("times_delivered", 1)

                if idle_time > self._claim_timeout_ms:
                    # ── Poison message guard ──────────────────────────
                    # If this message has already been delivered too many
                    # times, move it to the DLQ to stop the loop.
                    if times_delivered >= self._max_delivery_count:
                        logger.warning(
                            "Message %s exceeded max delivery count (%d/%d), "
                            "moving to DLQ",
                            message_id, times_delivered, self._max_delivery_count,
                        )
                        await self._move_pending_to_dlq(
                            consumer_group, consumer_name, message_id,
                            reason=f"exceeded max_delivery_count={self._max_delivery_count} "
                                   f"(delivered {times_delivered} times)",
                        )
                        continue

                    # Only reclaim from workers that are no longer alive.
                    # Reclaiming from alive workers can duplicate in-flight
                    # tasks when execution exceeds claim_timeout_ms.
                    if owner == consumer_name:
                        continue
                    if owner:
                        try:
                            owner_alive = await self._client.exists(
                                f"worker:heartbeat:{owner}"
                            )
                        except Exception:
                            owner_alive = 0
                        if owner_alive:
                            continue

                    # Claim the message
                    result = await self._client.xclaim(
                        self.STREAM_KEY,
                        consumer_group,
                        consumer_name,
                        min_idle_time=self._claim_timeout_ms,
                        message_ids=[message_id],
                    )

                    if result:
                        fields = result[0][1]
                        task = TaskPayload.from_dict(fields)
                        task.metadata["_stream_message_id"] = message_id
                        task.metadata["_claimed_from"] = owner
                        task.metadata["_times_delivered"] = times_delivered + 1
                        claimed.append(task)

                        # Clean dead worker's affinity mappings
                        dead_worker = owner
                        try:
                            if dead_worker:
                                affinities = await self._client.hgetall(self.AFFINITY_KEY)
                                for sid, wid in affinities.items():
                                    if wid == dead_worker:
                                        await self._client.hdel(self.AFFINITY_KEY, sid)
                                await self._client.hdel(self.WORKER_REGISTRY_KEY, dead_worker)
                        except Exception as affinity_err:
                            logger.debug("Failed to clean affinity for %s: %s", dead_worker, affinity_err)

                        logger.warning(
                            "Claimed stale message %s from %s (delivery #%d)",
                            message_id, dead_worker, times_delivered + 1,
                        )

        except Exception as e:
            logger.warning("Error claiming stale messages: %s", e)

        return claimed

    async def _move_pending_to_dlq(
        self,
        consumer_group: str,
        consumer_name: str,
        message_id: str,
        reason: str,
    ) -> None:
        """Claim a pending message and move it directly to the DLQ.

        Used for poison messages that have exceeded ``max_delivery_count``.
        """
        try:
            result = await self._client.xclaim(
                self.STREAM_KEY,
                consumer_group,
                consumer_name,
                min_idle_time=0,
                message_ids=[message_id],
            )
            if result:
                fields = result[0][1]
                task = TaskPayload.from_dict(fields)
                await self.move_to_dlq(task, reason, message_id)
            else:
                # Message may have been already acked/deleted; just log.
                logger.debug(
                    "Could not claim message %s for DLQ move (already gone?)",
                    message_id,
                )
        except Exception as e:
            logger.error(
                "Failed to move pending message %s to DLQ: %s", message_id, e,
            )

    async def _redirect_to_affinity_worker(
        self,
        consumer_group: str,
        target_worker: str,
        message_id: str,
    ) -> bool:
        """Reassign a pending message to the affinity worker."""
        if self._client is None:
            return False
        try:
            await self._client.xclaim(
                self.STREAM_KEY,
                consumer_group,
                target_worker,
                min_idle_time=0,
                message_ids=[message_id],
            )
            return True
        except Exception as e:
            logger.warning(
                "Failed to redirect message %s to %s: %s",
                message_id, target_worker, e,
            )
            return False

    async def ack(self, job_id: str, message_id: Optional[str] = None) -> bool:
        """
        Acknowledge task completion.

        Args:
            job_id: Task job ID (for logging)
            message_id: Redis stream message ID

        Returns:
            True if acknowledged successfully
        """
        if self._client is None:
            return False

        if message_id is None:
            logger.warning("No message_id provided for ack, job_id=%s", job_id)
            return False

        try:
            result = await self._client.xack(
                self.STREAM_KEY,
                self.CONSUMER_GROUP,
                message_id,
            )
            logger.debug("Acknowledged task job_id=%s, message_id=%s", job_id, message_id)
            return result > 0
        except Exception as e:
            logger.error("Failed to ack task: %s", e)
            return False

    async def move_to_dlq(
        self,
        task: TaskPayload,
        error: str,
        message_id: str,
    ) -> None:
        """
        Move failed task to dead letter queue.

        Args:
            task: Failed task
            error: Error message
            message_id: Original stream message ID
        """
        if self._client is None:
            return

        try:
            dlq_payload = {
                **task.to_dict(),
                "error": error,
                "failed_at": utc_now().isoformat(),
                "original_message_id": message_id,
            }

            await self._client.xadd(
                self.DLQ_STREAM_KEY,
                dlq_payload,
                maxlen=self.DLQ_STREAM_MAXLEN,
                approximate=True,
            )
            await self.ack(task.job_id, message_id)

            logger.warning(
                "Moved task to DLQ job_id=%s, error=%.100s", task.job_id, error
            )

            # Best-effort: notify user so the client exits "thinking" state.
            try:
                from ...core.pubsub.redis_pubsub import get_pubsub_manager
                pubsub = get_pubsub_manager()
                await pubsub.publish_error(
                    user_id=task.user_id,
                    error_message="处理请求时出现异常，请重新发送。",
                    error_code="DLQ_MOVED",
                    trace_id=task.job_id,
                    session_id=task.session_id,
                )
            except Exception:
                pass
        except Exception as e:
            logger.error("Failed to move task to DLQ: %s", e)

    async def get_pending_count(self) -> int:
        """Get number of pending (unprocessed) messages."""
        if self._client is None:
            return 0

        try:
            info = await self._client.xpending(self.STREAM_KEY, self.CONSUMER_GROUP)
            return info.get("pending", 0) if info else 0
        except Exception as e:
            logger.warning("Failed to get pending count: %s", e)
            return 0

    async def get_stream_length(self) -> int:
        """Get total number of messages in the stream."""
        if self._client is None:
            return 0

        try:
            return await self._client.xlen(self.STREAM_KEY)
        except Exception as e:
            logger.warning("Failed to get stream length: %s", e)
            return 0

    async def health_check(self) -> bool:
        """Check if queue is healthy."""
        try:
            if self._client is None:
                return False
            await self._client.ping()
            return True
        except Exception as e:
            logger.error("Task queue health check failed: %s", e)
            return False

    # ============ Session Affinity (Phase 6) ============

    AFFINITY_KEY = "session:affinity"
    AFFINITY_TTL = 1800  # 30 minutes (default; overridden by settings)
    WORKER_REGISTRY_KEY = "worker:registry"
    WORKER_HEARTBEAT_TTL = 30  # 30 seconds (default; overridden by settings)

    async def register_worker(self, worker_id: str) -> None:
        """Register a worker in the worker registry with heartbeat TTL."""
        if self._client is None:
            await self.connect()
        try:
            await self._client.hset(
                self.WORKER_REGISTRY_KEY,
                worker_id,
                utc_now().isoformat(),
            )
            # Set per-worker heartbeat key with TTL
            await self._client.set(
                f"worker:heartbeat:{worker_id}",
                "1",
                ex=self._worker_heartbeat_ttl,
            )
            logger.debug("Registered worker %s", worker_id)
        except Exception as e:
            logger.warning("Failed to register worker %s: %s", worker_id, e)

    async def deregister_worker(self, worker_id: str) -> None:
        """Remove worker from registry and delete heartbeat key.

        Called during graceful shutdown so that other workers can
        immediately claim this worker's pending messages without
        waiting for the heartbeat TTL to expire.
        """
        if self._client is None:
            return
        try:
            await self._client.delete(f"worker:heartbeat:{worker_id}")
            await self._client.hdel(self.WORKER_REGISTRY_KEY, worker_id)

            # Clean up affinity mappings that point to this worker
            affinities = await self._client.hgetall(self.AFFINITY_KEY)
            stale_sessions = [
                sid for sid, wid in affinities.items() if wid == worker_id
            ]
            for sid in stale_sessions:
                await self._client.hdel(self.AFFINITY_KEY, sid)
                await self._client.delete(f"session:affinity:{sid}")

            logger.info(
                "Deregistered worker %s (cleaned %d affinity mappings)",
                worker_id, len(stale_sessions),
            )
        except Exception as e:
            logger.warning("Failed to deregister worker %s: %s", worker_id, e)

    async def heartbeat(self, worker_id: str) -> None:
        """Renew worker heartbeat."""
        if self._client is None:
            return
        try:
            await self._client.set(
                f"worker:heartbeat:{worker_id}",
                "1",
                ex=self._worker_heartbeat_ttl,
            )
            await self._client.hset(
                self.WORKER_REGISTRY_KEY,
                worker_id,
                utc_now().isoformat(),
            )
        except Exception as e:
            logger.warning("Failed to send heartbeat for %s: %s", worker_id, e)

    async def get_session_affinity(self, session_id: str) -> Optional[str]:
        """Get the worker assigned to a session, if any."""
        if self._client is None:
            return None
        try:
            # Check TTL-based key first (authoritative)
            worker_id = await self._client.get(f"session:affinity:{session_id}")
            if not worker_id:
                # Fallback to hash lookup, clean up stale entry
                worker_id = await self._client.hget(self.AFFINITY_KEY, session_id)
                if not worker_id:
                    return None
            # Check if worker is still alive
            alive = await self._client.exists(f"worker:heartbeat:{worker_id}")
            if alive:
                return worker_id
            # Worker is dead, clean up affinity
            await self._client.hdel(self.AFFINITY_KEY, session_id)
            await self._client.delete(f"session:affinity:{session_id}")
            return None
        except Exception as e:
            logger.warning("Failed to get session affinity: %s", e)
            return None

    async def set_session_affinity(self, session_id: str, worker_id: str) -> None:
        """Set session affinity to a specific worker with TTL to prevent unbounded growth."""
        if self._client is None:
            return
        try:
            # Use per-session key with TTL instead of unbounded hash
            await self._client.set(
                f"session:affinity:{session_id}",
                worker_id,
                ex=self._affinity_ttl,
            )
            # Also store in hash for enumeration (cleanup_dead_workers)
            await self._client.hset(self.AFFINITY_KEY, session_id, worker_id)
        except Exception as e:
            logger.warning("Failed to set session affinity: %s", e)

    async def clear_session_affinity(self, session_id: str) -> None:
        """Clear session affinity (e.g., on session archive)."""
        if self._client is None:
            return
        try:
            await self._client.hdel(self.AFFINITY_KEY, session_id)
            await self._client.delete(f"session:affinity:{session_id}")
        except Exception as e:
            logger.warning("Failed to clear session affinity: %s", e)

    async def cleanup_dead_workers(self) -> int:
        """Remove dead workers from registry and their affinity mappings.

        Also purges stale hash entries whose per-session TTL key has expired,
        preventing unbounded growth of the ``session:affinity`` hash.
        """
        if self._client is None:
            return 0
        removed = 0
        try:
            workers = await self._client.hgetall(self.WORKER_REGISTRY_KEY)
            dead_workers = []
            for worker_id in workers:
                alive = await self._client.exists(f"worker:heartbeat:{worker_id}")
                if not alive:
                    dead_workers.append(worker_id)

            # Fetch affinity hash once for dead-worker cleanup AND stale-session cleanup
            affinities = await self._client.hgetall(self.AFFINITY_KEY)

            if dead_workers:
                dead_set = set(dead_workers)

                for worker_id in dead_workers:
                    await self._client.hdel(self.WORKER_REGISTRY_KEY, worker_id)
                    removed += 1
                    logger.warning("Cleaned up dead worker %s", worker_id)

                # Clean up affinity mappings for all dead workers in one pass
                stale_sessions = [
                    sid for sid, wid in affinities.items() if wid in dead_set
                ]
                for sid in stale_sessions:
                    await self._client.hdel(self.AFFINITY_KEY, sid)

            # Purge hash entries whose per-session TTL key has already expired.
            # This prevents the hash from growing unbounded when workers stay
            # alive but sessions expire naturally.
            expired_sessions = []
            for sid in affinities:
                ttl_key_exists = await self._client.exists(f"session:affinity:{sid}")
                if not ttl_key_exists:
                    expired_sessions.append(sid)
            if expired_sessions:
                for sid in expired_sessions:
                    await self._client.hdel(self.AFFINITY_KEY, sid)
                logger.info(
                    "Purged %d expired session affinity hash entries",
                    len(expired_sessions),
                )
        except Exception as e:
            logger.warning("Failed to cleanup dead workers: %s", e)
        return removed

    async def cleanup_zombie_consumers(
        self,
        group: str,
        idle_threshold_ms: int = 300000,
    ) -> int:
        """Remove zombie consumers that have been idle too long with no pending messages.

        Args:
            group: Consumer group name.
            idle_threshold_ms: Idle time threshold in milliseconds (default 5 minutes).

        Returns:
            Number of consumers removed.
        """
        if self._client is None:
            return 0
        removed = 0
        try:
            consumers = await self._client.xinfo_consumers(self.STREAM_KEY, group)
            for consumer in consumers:
                name = consumer.get("name", "")
                idle = consumer.get("idle", 0)
                pending = consumer.get("pending", 0)
                if idle > idle_threshold_ms and pending == 0:
                    await self._client.xgroup_delconsumer(
                        self.STREAM_KEY, group, name,
                    )
                    removed += 1
                    logger.info(
                        "Removed zombie consumer %s (idle=%dms, pending=%d)",
                        name, idle, pending,
                    )
        except Exception as e:
            logger.warning("Failed to cleanup zombie consumers: %s", e)
        return removed


# Global instance
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """Get or create the global task queue."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue
