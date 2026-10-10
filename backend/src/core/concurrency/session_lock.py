"""
Shared session-level asyncio lock manager.

Provides per-session serialization so that concurrent tasks targeting the
same chat session are processed one at a time within a single process.
Used by both ``ws_publishers`` (fast/hybrid path) and ``worker_runner``
(slow path) to prevent interleaved message handling.
"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Optional

logger = logging.getLogger(__name__)


class SessionLockManager:
    """Reference-counted per-session asyncio locks.

    Each unique ``session_id`` gets its own ``asyncio.Lock``. A reference
    counter tracks how many callers are currently waiting for or holding
    the lock. When the last caller releases the lock and no one else is
    waiting, the lock is cleaned up to prevent unbounded memory growth.
    """

    def __init__(self) -> None:
        self._locks: Dict[str, asyncio.Lock] = {}
        self._refs: Dict[str, int] = {}
        self._guard: asyncio.Lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, session_id: Optional[str]) -> AsyncIterator[None]:
        """Acquire the session lock, yielding control to the caller.

        If *session_id* is ``None``, this is a no-op (yields immediately).
        """
        if not session_id:
            yield
            return

        started = time.monotonic()
        async with self._guard:
            lock = self._locks.get(session_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[session_id] = lock
                self._refs[session_id] = 0
            self._refs[session_id] = self._refs.get(session_id, 0) + 1

        await lock.acquire()
        wait_ms = (time.monotonic() - started) * 1000
        if wait_ms > 50:
            logger.info(
                "Session lock wait: session=%s wait_ms=%.0f",
                session_id,
                wait_ms,
            )
        try:
            yield
        finally:
            lock.release()
            async with self._guard:
                remaining = self._refs.get(session_id, 1) - 1
                if remaining <= 0 and not lock.locked():
                    self._refs.pop(session_id, None)
                    self._locks.pop(session_id, None)
                else:
                    self._refs[session_id] = remaining
