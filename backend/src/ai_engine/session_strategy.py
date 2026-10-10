"""
Session execution strategies for the worker runner.

Encapsulates the decision logic for how a task should be executed
(lock serialization, mailbox actor, or streaming actor) into a
single polymorphic interface, replacing scattered ``_should_*``
helper functions.
"""
import abc
import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from ..config.settings import settings
from .queue.task_queue import TaskPayload

logger = logging.getLogger(__name__)


class SessionExecutionStrategy(abc.ABC):
    """Abstract base for task execution strategies."""

    @abc.abstractmethod
    async def execute(
        self,
        task: TaskPayload,
        run_fn: Callable[[], Awaitable[None]],
    ) -> None:
        """Execute a task using this strategy.

        Args:
            task: The task payload to process.
            run_fn: The actual processing coroutine to invoke.
        """

    @property
    @abc.abstractmethod
    def timeout_seconds(self) -> int:
        """Return the appropriate timeout for this strategy."""

    @property
    def name(self) -> str:
        return self.__class__.__name__


class LockStrategy(SessionExecutionStrategy):
    """Serialize via per-session asyncio lock."""

    def __init__(self, lock_manager: Any) -> None:
        self._lock_manager = lock_manager

    async def execute(
        self,
        task: TaskPayload,
        run_fn: Callable[[], Awaitable[None]],
    ) -> None:
        async with self._lock_manager.acquire(task.session_id):
            await run_fn()

    @property
    def timeout_seconds(self) -> int:
        return settings.worker_task_timeout_seconds


class MailboxStrategy(SessionExecutionStrategy):
    """Route through the SessionMailboxManager actor."""

    def __init__(self, mailbox_manager: Any) -> None:
        self._mailbox_manager = mailbox_manager

    async def execute(
        self,
        task: TaskPayload,
        run_fn: Callable[[], Awaitable[None]],
    ) -> None:
        await self._mailbox_manager.submit(task)

    @property
    def timeout_seconds(self) -> int:
        return settings.worker_task_timeout_seconds


class StreamingActorStrategy(SessionExecutionStrategy):
    """Streaming-input path with extended timeout, no local lock."""

    async def execute(
        self,
        task: TaskPayload,
        run_fn: Callable[[], Awaitable[None]],
    ) -> None:
        await run_fn()

    @property
    def timeout_seconds(self) -> int:
        return settings.streaming_input_max_timeout_seconds


class DirectStrategy(SessionExecutionStrategy):
    """No serialization, no session — fire and forget."""

    async def execute(
        self,
        task: TaskPayload,
        run_fn: Callable[[], Awaitable[None]],
    ) -> None:
        await run_fn()

    @property
    def timeout_seconds(self) -> int:
        return settings.worker_task_timeout_seconds


def resolve_strategy(
    task: TaskPayload,
    lock_manager: Any,
    mailbox_manager: Optional[Any] = None,
) -> SessionExecutionStrategy:
    """Determine the execution strategy for a task.

    Decision matrix:
    - Streaming-input enabled + slow/hybrid → StreamingActorStrategy
    - Mailbox enabled + slow/hybrid + has session → MailboxStrategy
    - Has session → LockStrategy
    - No session → DirectStrategy
    """
    is_slow_hybrid = task.route_type in {"slow", "hybrid_background"}

    # Streaming-input mode takes priority for slow/hybrid
    if settings.sdk_streaming_input_enabled and is_slow_hybrid:
        return StreamingActorStrategy()

    # Mailbox for slow/hybrid when streaming is off
    if (
        mailbox_manager is not None
        and settings.session_mailbox_enabled
        and task.session_id
        and is_slow_hybrid
    ):
        return MailboxStrategy(mailbox_manager)

    # Lock-based serialization for any task with a session
    if task.session_id:
        return LockStrategy(lock_manager)

    # No session — run directly
    return DirectStrategy()
