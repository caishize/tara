"""
Standalone Agent Worker process entry point.

Runs the Agent Worker as an independent process (outside the API server).
This is the production-recommended way to run the Agent Worker,
allowing independent scaling and deployment.

Usage:
    python -m src.ai_engine.worker_main
    # or via the start script:
    ./scripts/start-agent-worker.sh
"""
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Ensure the backend directory is on sys.path when run as a module
_backend_dir = str(Path(__file__).resolve().parents[2])
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from ..config.settings import settings
from ..config.logging import setup_logging, get_logger
from ..core.cache import redis_client
from ..db.session import init_db, close_db
from .worker_runner import run_agent_worker_loop, request_worker_shutdown

# Import celery_app so that shared_task instances (used by curation, memory, etc.)
# bind to our Redis-backed Celery app instead of the default AMQP broker.
from ..celery_app import celery_app as _celery_app  # noqa: F401


setup_logging()
logger = get_logger(__name__)


async def main() -> None:
    """Run the Agent Worker as a standalone async process."""
    logger.info(
        "Starting standalone Agent Worker (max_concurrent=%d, timeout=%ds)",
        settings.worker_max_concurrent_tasks,
        settings.worker_task_timeout_seconds,
    )

    # Initialize shared infrastructure
    await redis_client.connect()
    logger.info("Redis connected")

    # Initialize event bus so domain events emitted during worker processing
    # are dispatched to handlers (same as the API process does in lifespan).
    from ..core.events import get_event_bus, register_all_handlers
    event_bus = get_event_bus()
    register_all_handlers(event_bus)
    logger.info("Event bus initialized")

    shutdown_event = asyncio.Event()
    _signal_count = 0

    def _signal_handler() -> None:
        nonlocal _signal_count
        _signal_count += 1
        if _signal_count >= 2:
            logger.warning(
                "Received %d shutdown signals, force exiting immediately!",
                _signal_count,
            )
            os._exit(1)
        logger.info(
            "Received shutdown signal, waiting for graceful shutdown... "
            "(press Ctrl+C again to force exit)"
        )
        request_worker_shutdown()
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    worker_task = asyncio.create_task(run_agent_worker_loop())
    logger.info("Agent Worker loop started")

    # Wait until a shutdown signal is received
    await shutdown_event.wait()

    # Give the worker loop time to drain in-flight tasks.
    # The loop now checks _shutdown_event and exits within ~1s,
    # but cleanup (mailbox, in-flight tasks, pool) may take longer.
    logger.info("Waiting for Agent Worker to finish...")
    try:
        await asyncio.wait_for(worker_task, timeout=45.0)
    except asyncio.TimeoutError:
        logger.warning("Agent Worker did not finish in time, cancelling")
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    # Cleanup
    try:
        from .tools.web_search import cleanup_web_search_service
        await cleanup_web_search_service()
    except (ImportError, AttributeError):
        pass  # web search cleanup not available

    await redis_client.disconnect()
    await close_db()
    logger.info("Standalone Agent Worker shut down gracefully")


if __name__ == "__main__":
    asyncio.run(main())
