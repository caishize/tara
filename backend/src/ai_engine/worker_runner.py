"""
Worker Runner.

Provides functionality to run Agent Worker as a background task within the API process.
Useful for development and simplified deployments.
"""
import asyncio
import logging
import os
import socket
from typing import Optional, Set
from datetime import datetime, timezone

from ..core.utils.timezone import utc_now
from .queue.task_queue import get_task_queue, TaskPayload
from ..core.concurrency import SessionLockManager
from ..core.pubsub.redis_pubsub import get_pubsub_manager, RedisPubSubManager
from .workers.agent_worker import AgentWorker
from .session_mailbox import SessionMailboxManager
from .session_strategy import (
    MailboxStrategy,
    resolve_strategy,
)
from .sdk.sdk_client_pool import (
    get_sdk_client_pool,
    shutdown_sdk_client_pool,
)
from .workers.session_streaming_executor import (
    shutdown_session_streaming_executor_manager,
)
from ..db.session import async_session_maker
from ..config.settings import settings

logger = logging.getLogger(__name__)

_shutdown_event: Optional[asyncio.Event] = None
_active_tasks: Set[asyncio.Task] = set()
_session_lock_manager = SessionLockManager()


def request_worker_shutdown() -> None:
    """Signal the agent worker loop to shut down gracefully."""
    if _shutdown_event is not None:
        logger.info("Agent worker shutdown requested (event_set=True)")
        _shutdown_event.set()
    else:
        logger.info("Agent worker shutdown requested before loop init (event_missing)")


async def _process_task(
    task: TaskPayload,
    pubsub: RedisPubSubManager,
    task_queue,
    semaphore: asyncio.Semaphore,
    mailbox_manager: Optional[SessionMailboxManager] = None,
) -> None:
    """Process a single task with concurrency limiting and timeout."""
    strategy = resolve_strategy(task, _session_lock_manager, mailbox_manager)

    async def _run_once() -> None:
        async with semaphore:
            async with async_session_maker() as session:
                worker = AgentWorker(db=session)
                try:
                    await asyncio.wait_for(
                        worker.process(task, pubsub),
                        timeout=strategy.timeout_seconds,
                    )
                    await task_queue.ack(
                        task.job_id, task.metadata.get("_stream_message_id")
                    )
                    logger.info("Task completed: %s (strategy=%s)", task.job_id, strategy.name)
                except asyncio.TimeoutError:
                    logger.error(
                        "Task timed out after %ds: %s (strategy=%s)",
                        strategy.timeout_seconds,
                        task.job_id,
                        strategy.name,
                    )
                    try:
                        await pubsub.publish_error(
                            user_id=task.user_id,
                            error_message="处理超时，请重试。",
                            error_code="TASK_TIMEOUT",
                            trace_id=task.job_id,
                            session_id=task.session_id,
                        )
                    except Exception as pub_err:
                        logger.warning(
                            "Failed to publish timeout error for %s: %s",
                            task.job_id,
                            pub_err,
                        )
                    # Only disconnect for non-streaming-input path.
                    # When using streaming input, the ReactiveSessionActor
                    # owns the client lifecycle.  External mark_disconnected
                    # races with the actor and can kill the stream for other
                    # pending requests still being processed by the actor.
                    _is_streaming_input = (
                        bool(task.session_id)
                        and settings.sdk_streaming_input_enabled
                        and task.route_type in {"slow", "hybrid_background"}
                    )
                    if task.session_id and settings.sdk_client_pool_enabled and not _is_streaming_input:
                        try:
                            pool = await get_sdk_client_pool()
                            await pool.mark_disconnected(task.session_id)
                        except Exception as pool_err:
                            logger.warning(
                                "Failed to clear pool marker for session %s: %s",
                                task.session_id,
                                pool_err,
                            )
                    if "_stream_message_id" in task.metadata:
                        await task_queue.move_to_dlq(
                            task,
                            f"timeout after {strategy.timeout_seconds}s",
                            task.metadata["_stream_message_id"],
                        )
                except Exception as e:
                    logger.error(
                        "Error processing task %s: %s", task.job_id, e, exc_info=True
                    )
                    try:
                        await pubsub.publish_error(
                            user_id=task.user_id,
                            error_message="处理请求时出现错误，请稍后重试。",
                            error_code="WORKER_ERROR",
                            trace_id=task.job_id,
                            session_id=task.session_id,
                        )
                    except Exception as pub_err:
                        logger.warning(
                            "Failed to publish fallback error for %s: %s",
                            task.job_id,
                            pub_err,
                        )
                    if "_stream_message_id" in task.metadata:
                        await task_queue.move_to_dlq(
                            task, str(e), task.metadata["_stream_message_id"]
                        )

    # MailboxStrategy handles its own dispatch; others wrap _run_once
    if isinstance(strategy, MailboxStrategy):
        try:
            await strategy.execute(task, _run_once)
        except Exception as mailbox_err:
            logger.warning(
                "Mailbox submit failed for job=%s session=%s, "
                "fallback to lock strategy: %s",
                task.job_id,
                task.session_id,
                mailbox_err,
            )
            async with _session_lock_manager.acquire(task.session_id):
                await _run_once()
    else:
        await strategy.execute(task, _run_once)


async def run_agent_worker_loop():
    """
    Background task to run agent worker loop.

    Continuously dequeues tasks from Redis Stream and processes them
    concurrently using asyncio.create_task with a semaphore to limit
    parallelism.
    """
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    logger.info(
        "Starting in-process Agent Worker loop (max_concurrent=%d, timeout=%ds)...",
        settings.worker_max_concurrent_tasks,
        settings.worker_task_timeout_seconds,
    )

    task_queue = get_task_queue()
    pubsub = get_pubsub_manager()

    # Ensure connections
    await task_queue.connect()
    await pubsub.connect()

    # Initialize SDK client pool for CLI process reuse
    if settings.sdk_client_pool_enabled:
        try:
            pool = await get_sdk_client_pool()
            logger.info(
                "SDK client pool initialized (idle_timeout=%ds, max_clients=%d)",
                settings.sdk_client_pool_idle_timeout_seconds,
                settings.sdk_client_pool_max_clients,
            )
            # Clean up ghost Redis markers left by previously-crashed workers
            cleaned = await pool.cleanup_stale_markers()
            if cleaned:
                logger.info("Startup: removed %d stale pool markers", cleaned)
        except Exception as e:
            logger.warning("Failed to initialize SDK client pool: %s", e)

    consumer_name = f"worker-{socket.gethostname()}-{os.getpid()}"
    heartbeat_task: Optional[asyncio.Task] = None
    semaphore = asyncio.Semaphore(settings.worker_max_concurrent_tasks)
    mailbox_manager: Optional[SessionMailboxManager] = None

    async def _process_task_bound(task: TaskPayload) -> None:
        # Called by SessionMailboxManager — pass None for mailbox_manager
        # to avoid re-submitting back to the mailbox (cycle prevention).
        await _process_task(task, pubsub, task_queue, semaphore, None)

    if settings.session_mailbox_enabled:
        mailbox_manager = SessionMailboxManager(
            process_fn=_process_task_bound,
            idle_seconds=settings.session_mailbox_idle_seconds,
            max_queue_size=settings.session_mailbox_max_queue_size,
        )
        logger.info(
            "Session mailbox enabled (idle_seconds=%d, max_queue_size=%d)",
            settings.session_mailbox_idle_seconds,
            settings.session_mailbox_max_queue_size,
        )

    await task_queue.register_worker(consumer_name)

    # Proactively recover messages from dead workers immediately on startup,
    # rather than waiting for the first dequeue cycle + claim_timeout_ms.
    try:
        recovered = await task_queue.cleanup_dead_workers()
        if recovered:
            logger.info(
                "Startup: cleaned up %d dead workers, their pending "
                "messages are now claimable",
                recovered,
            )
    except Exception as e:
        logger.warning("Startup: dead worker cleanup failed (non-fatal): %s", e)

    async def _heartbeat_loop() -> None:
        zombie_cleanup_counter = 0
        while True:
            await task_queue.heartbeat(consumer_name)
            await asyncio.sleep(settings.worker_heartbeat_interval_seconds)
            zombie_cleanup_counter += 1
            # Run zombie consumer cleanup every ~5 minutes
            # (assuming ~10s heartbeat interval, 30 iterations ~ 300s)
            if zombie_cleanup_counter >= 30:
                zombie_cleanup_counter = 0
                try:
                    removed = await task_queue.cleanup_zombie_consumers(
                        task_queue.CONSUMER_GROUP
                    )
                    if removed:
                        logger.info("Cleaned %d zombie consumers", removed)
                except Exception as e:
                    logger.warning(
                        "Zombie consumer cleanup failed (non-fatal): %s", e
                    )

    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    # Start DLQ depth monitor
    dlq_monitor_task: Optional[asyncio.Task] = None
    try:
        from .queue.dlq_monitor import DLQMonitor
        dlq_redis = task_queue._client  # reuse the task queue's Redis connection
        if dlq_redis is not None:
            dlq_monitor_task = asyncio.create_task(DLQMonitor(dlq_redis).run())
    except Exception as e:
        logger.warning("Failed to start DLQ monitor (non-fatal): %s", e)

    while True:
        # Check for shutdown before blocking on dequeue
        if _shutdown_event is not None and _shutdown_event.is_set():
            logger.info("Agent Worker loop: shutdown event detected, exiting main loop")
            break
        try:
            # Dequeue task (blocks for up to 1s inside dequeue)
            task = await task_queue.dequeue(
                consumer_group="agent_workers",
                consumer_name=consumer_name,
                count=1,
            )

            if task:
                delay_ms = None
                try:
                    created_at = datetime.fromisoformat(task.created_at)
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    delay_ms = int(
                        (utc_now() - created_at).total_seconds()
                        * 1000
                    )
                except Exception:
                    delay_ms = None
                if delay_ms is not None:
                    logger.info(
                        "Worker picked up task: %s (queue_delay_ms=%s)",
                        task.job_id,
                        delay_ms,
                    )
                else:
                    logger.info("Worker picked up task: %s", task.job_id)

                # Strategy-based dispatch (lock, mailbox, streaming, or direct)
                t = asyncio.create_task(
                    _process_task(task, pubsub, task_queue, semaphore, mailbox_manager)
                )
                _active_tasks.add(t)
                t.add_done_callback(_active_tasks.discard)
            else:
                # No tasks found, small sleep to yield control
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            # Distinguish genuine shutdown from spurious CancelledError
            # (e.g. SDK client pool cleanup's cross-task cancel-scope leak).
            if _shutdown_event is not None and _shutdown_event.is_set():
                logger.info("Agent Worker loop cancelled (shutdown requested)")
                break
            else:
                logger.warning(
                    "Agent Worker loop received spurious CancelledError, recovering..."
                )
                continue
        except Exception as e:
            logger.error("Agent Worker loop error: %s", e)
            await asyncio.sleep(5)

    # ── Graceful Shutdown Cleanup ────────────────────────────────────────
    logger.info("Agent Worker entering shutdown cleanup")
    try:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
        if dlq_monitor_task is not None:
            dlq_monitor_task.cancel()
        if mailbox_manager is not None:
            await mailbox_manager.stop(grace_seconds=30.0)
        # Wait for in-flight tasks to finish (with a grace period)
        if _active_tasks:
            logger.info(
                "Waiting for %d in-flight tasks to complete (30s grace)...",
                len(_active_tasks),
            )
            try:
                await asyncio.wait_for(
                    asyncio.gather(*_active_tasks, return_exceptions=True),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Grace period expired, force-cancelling %d tasks",
                    len(_active_tasks),
                )
                for t in _active_tasks:
                    t.cancel()
                await asyncio.gather(*_active_tasks, return_exceptions=True)
        # Shutdown streaming executor
        if settings.sdk_streaming_input_enabled:
            try:
                await shutdown_session_streaming_executor_manager()
                logger.info("Session streaming executor shutdown complete")
            except Exception as e:
                logger.warning(
                    "Error shutting down session streaming executor: %s", e
                )
        # Shutdown SDK client pool
        if settings.sdk_client_pool_enabled:
            try:
                await shutdown_sdk_client_pool()
                logger.info("SDK client pool shutdown complete")
            except Exception as e:
                logger.warning("Error shutting down SDK client pool: %s", e)
        # Deregister worker so other workers can immediately claim
        # our pending messages without waiting for heartbeat TTL.
        try:
            await task_queue.deregister_worker(consumer_name)
        except Exception as e:
            logger.warning(
                "Failed to deregister worker on shutdown: %s", e
            )
    except asyncio.CancelledError:
        logger.warning("Shutdown cleanup interrupted by cancellation, forcing exit")
    except Exception as e:
        logger.error("Error during shutdown cleanup: %s", e)
