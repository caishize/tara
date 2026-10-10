"""
Session mailbox actors for serializing per-session task execution.

Each active chat session gets a lightweight actor on demand. The actor
processes tasks in FIFO order, which allows clients to send follow-up
messages while a previous slow task is still running without creating
concurrent consumers on the same pooled SDK stream.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Dict, Optional

from .queue.task_queue import TaskPayload

logger = logging.getLogger(__name__)

ProcessFn = Callable[[TaskPayload], Awaitable[None]]


class SessionMailboxActor:
    """Single-session FIFO processor with idle auto-shutdown."""

    def __init__(
        self,
        session_id: str,
        process_fn: ProcessFn,
        idle_seconds: int,
        max_queue_size: int,
        on_exit: Callable[[str, "SessionMailboxActor"], Awaitable[None]],
    ) -> None:
        self.session_id = session_id
        self._process_fn = process_fn
        self._idle_seconds = max(1, int(idle_seconds))
        self._on_exit = on_exit

        self._queue: asyncio.Queue[TaskPayload] = asyncio.Queue(
            maxsize=max(0, int(max_queue_size))
        )
        self._task: Optional[asyncio.Task] = None
        self._stop_requested = False
        self._closed = asyncio.Event()

        self.submitted = 0
        self.processed = 0

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def done(self) -> bool:
        return self._task is None or self._task.done()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(
            self._run(),
            name=f"session-mailbox:{self.session_id}",
        )

    async def submit(self, task: TaskPayload) -> int:
        if self._stop_requested:
            raise RuntimeError(f"Session mailbox is stopping: {self.session_id}")
        await self._queue.put(task)
        self.submitted += 1
        return self._queue.qsize()

    def request_stop(self) -> None:
        self._stop_requested = True

    def cancel(self) -> None:
        self.request_stop()
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def wait_closed(self, timeout_seconds: Optional[float] = None) -> bool:
        if timeout_seconds is None:
            await self._closed.wait()
            return True
        try:
            await asyncio.wait_for(self._closed.wait(), timeout=timeout_seconds)
            return True
        except asyncio.TimeoutError:
            return False

    async def _run(self) -> None:
        logger.info("Session mailbox started: session=%s", self.session_id)
        try:
            while True:
                if self._stop_requested and self._queue.empty():
                    break

                try:
                    task = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._idle_seconds,
                    )
                except asyncio.TimeoutError:
                    if self._queue.empty():
                        logger.info(
                            "Session mailbox idle stop: session=%s submitted=%d processed=%d",
                            self.session_id,
                            self.submitted,
                            self.processed,
                        )
                        break
                    continue

                try:
                    await self._process_fn(task)
                except Exception:
                    logger.exception(
                        "Session mailbox task failed: session=%s job_id=%s",
                        self.session_id,
                        task.job_id,
                    )
                finally:
                    self.processed += 1
                    self._queue.task_done()
        except asyncio.CancelledError:
            logger.info("Session mailbox cancelled: session=%s", self.session_id)
            raise
        finally:
            self._closed.set()
            await self._on_exit(self.session_id, self)
            logger.info("Session mailbox closed: session=%s", self.session_id)


class SessionMailboxManager:
    """Lazily create and retire mailbox actors keyed by session_id."""

    def __init__(
        self,
        process_fn: ProcessFn,
        idle_seconds: int,
        max_queue_size: int = 0,
    ) -> None:
        self._process_fn = process_fn
        self._idle_seconds = idle_seconds
        self._max_queue_size = max_queue_size
        self._actors: Dict[str, SessionMailboxActor] = {}
        self._lock = asyncio.Lock()

    async def submit(self, task: TaskPayload) -> None:
        session_id = (task.session_id or "").strip()
        if not session_id:
            raise ValueError("Session mailbox requires task.session_id")

        async with self._lock:
            actor = self._actors.get(session_id)
            if actor is None or actor.done:
                actor = SessionMailboxActor(
                    session_id=session_id,
                    process_fn=self._process_fn,
                    idle_seconds=self._idle_seconds,
                    max_queue_size=self._max_queue_size,
                    on_exit=self._on_actor_exit,
                )
                self._actors[session_id] = actor
                actor.start()

        queue_size = await actor.submit(task)
        if queue_size > 1:
            logger.info(
                "Session mailbox queued task: session=%s job_id=%s queue_size=%d",
                session_id,
                task.job_id,
                queue_size,
            )

    async def stop(self, grace_seconds: float = 30.0) -> None:
        async with self._lock:
            actors = list(self._actors.values())

        if not actors:
            return

        for actor in actors:
            actor.request_stop()

        waiters = [actor.wait_closed() for actor in actors]
        try:
            await asyncio.wait_for(
                asyncio.gather(*waiters, return_exceptions=True),
                timeout=grace_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Session mailbox stop timeout; force-cancelling %d actor(s)",
                len(actors),
            )
            for actor in actors:
                actor.cancel()
            await asyncio.gather(
                *(actor.wait_closed(timeout_seconds=2.0) for actor in actors),
                return_exceptions=True,
            )

    async def _on_actor_exit(
        self,
        session_id: str,
        actor: SessionMailboxActor,
    ) -> None:
        async with self._lock:
            current = self._actors.get(session_id)
            if current is actor:
                self._actors.pop(session_id, None)
