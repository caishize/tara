"""Shared fixtures for unit tests."""

import asyncio

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai_engine.sdk.pooled_context import PooledToolContext
from src.ai_engine.sdk.sdk_stream_handler import SDKStreamHandler
from src.ai_engine.workers.reactive_session_actor import ReactiveSessionActor


@pytest.fixture
async def actor():
    """Create a ReactiveSessionActor with mocked SDK dependencies."""
    on_exit = AsyncMock()
    a = ReactiveSessionActor(
        session_id="test-session-123",
        idle_seconds=60,
        on_exit=on_exit,
    )
    # Provide a mock pooled client for SDK operations
    a._pooled = MagicMock()
    a._pooled.client = MagicMock()
    a._pooled.client.query = AsyncMock()
    a._pooled.client.interrupt = AsyncMock()

    # Set up PooledToolContext so signal-initiated queries can build
    # synthetic _StreamingRequest entries (mirrors post-first-request state).
    mock_task = MagicMock()
    mock_task.user_id = "test-user"
    mock_task.family_id = "test-family"
    mock_task.session_id = "test-session-123"
    mock_task.job_id = "test-job"
    mock_task.route_type = "slow"

    mock_worker = MagicMock()
    mock_worker._make_pubsub_publish_fn = MagicMock(return_value=AsyncMock())

    mock_pubsub = MagicMock()
    mock_pubsub.publish = AsyncMock()

    ctx = PooledToolContext()
    ctx.update(
        bridge=MagicMock(),
        persistence=MagicMock(),
        task=mock_task,
        pubsub=mock_pubsub,
        sdk_stream_handler=MagicMock(),
        worker=mock_worker,
    )
    ctx.keepalive = asyncio.Event()
    a._ctx = ctx

    # Simulate that at least one request has completed, providing the
    # runner/run_config/hook_builder needed by _build_signal_request().
    a._last_runner = MagicMock()
    a._last_run_config = MagicMock()
    a._last_hook_builder = MagicMock()

    yield a
    # Cleanup: cancel background tasks to avoid "Task was destroyed" warnings
    tasks_to_cancel = []
    for task_attr in ("_heartbeat_task", "_signal_listener_task"):
        task = getattr(a, task_attr, None)
        if task is not None and not task.done():
            task.cancel()
            tasks_to_cancel.append(task)
    for task in list(getattr(a, "_audit_tasks", set())):
        if not task.done():
            task.cancel()
            tasks_to_cancel.append(task)
    if tasks_to_cancel:
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
