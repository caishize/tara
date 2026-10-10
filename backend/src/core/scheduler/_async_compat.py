"""
Async-to-sync bridge for Celery tasks.

Celery tasks run in sync workers. This module provides a process-scoped
event loop bridge so all async task code in the same worker process runs
on one stable loop.

Why this exists:
- asyncpg connections are event-loop bound
- creating/closing a loop for each task makes it easy to hit
  "Future attached to a different loop" and "Event loop is closed"
  when pools or clients are reused
"""

import asyncio
import logging
import os
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)

_loop_lock = threading.Lock()
_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_loop_pid: int | None = None


def _cancel_pending_tasks(loop: asyncio.AbstractEventLoop, baseline_tasks: set[asyncio.Task]) -> None:
    """Cancel tasks spawned during one run_async invocation."""
    new_pending = [
        t for t in asyncio.all_tasks(loop)
        if t not in baseline_tasks and not t.done()
    ]
    if not new_pending:
        return

    for task in new_pending:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*new_pending, return_exceptions=True))


def _ensure_worker_loop() -> asyncio.AbstractEventLoop:
    """Return a live process-local loop, creating one if needed."""
    global _worker_loop, _worker_loop_pid

    pid = os.getpid()
    with _loop_lock:
        if (
            _worker_loop is None
            or _worker_loop.is_closed()
            or _worker_loop_pid != pid
        ):
            _worker_loop = asyncio.new_event_loop()
            _worker_loop_pid = pid
            logger.debug("Created worker async loop (pid=%s)", pid)
        return _worker_loop


def init_worker_event_loop() -> None:
    """Eagerly initialize the process-local loop (called from Celery hooks)."""
    _ensure_worker_loop()


def shutdown_worker_event_loop() -> None:
    """Shutdown and close the process-local loop (called on worker shutdown)."""
    global _worker_loop, _worker_loop_pid

    with _loop_lock:
        loop = _worker_loop
        if loop is None or loop.is_closed():
            _worker_loop = None
            _worker_loop_pid = None
            return

        try:
            asyncio.set_event_loop(loop)
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()
            asyncio.set_event_loop(None)
            _worker_loop = None
            _worker_loop_pid = None
            logger.debug("Closed worker async loop")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine on the process-local worker event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        coro.close()
        raise RuntimeError("run_async() cannot be called from an active event loop")

    loop = _ensure_worker_loop()
    baseline_tasks = set(asyncio.all_tasks(loop))

    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        # Clean up fire-and-forget leftovers from this invocation.
        _cancel_pending_tasks(loop, baseline_tasks)
        loop.run_until_complete(loop.shutdown_asyncgens())
        asyncio.set_event_loop(None)
