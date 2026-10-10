"""
Unit tests for pending action Celery tasks.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.unit
class TestExpireStaleActionsTask:
    """Test cases for expire_stale_actions_task."""

    def teardown_method(self):
        """Reset event loop after run_async() closes it."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    def _build_session_mocks(self):
        """Build mock engine + session factory that work with async context managers."""
        mock_engine = AsyncMock()
        mock_session = AsyncMock()

        # session_factory() returns an async context manager yielding mock_session
        session_cm = AsyncMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock(return_value=session_cm)

        return mock_engine, session_factory, mock_session

    @patch("src.modules.conversation.tasks.create_celery_async_session")
    def test_expire_stale_returns_summary(self, mock_create_session):
        """Test that the task returns a summary dict with expired count."""
        from src.modules.conversation.tasks import expire_stale_actions_task

        mock_engine, session_factory, mock_session = self._build_session_mocks()
        mock_create_session.return_value = (mock_engine, session_factory)

        mock_service = AsyncMock()
        mock_service.expire_stale.return_value = 5

        with patch(
            "src.modules.conversation.pending_action_service.PendingActionService",
            return_value=mock_service,
        ):
            result = expire_stale_actions_task()

        assert result["actions_expired"] == 5
        assert result["errors"] == []

    @patch("src.modules.conversation.tasks.create_celery_async_session")
    def test_expire_stale_handles_error(self, mock_create_session):
        """Test that errors are captured in the result dict, not raised."""
        from src.modules.conversation.tasks import expire_stale_actions_task

        mock_engine, session_factory, mock_session = self._build_session_mocks()
        mock_create_session.return_value = (mock_engine, session_factory)

        with patch(
            "src.modules.conversation.pending_action_service.PendingActionService",
            side_effect=RuntimeError("DB connection lost"),
        ):
            result = expire_stale_actions_task()

        assert result["actions_expired"] == 0
        assert len(result["errors"]) == 1
        assert "DB connection lost" in result["errors"][0]

    @patch("src.modules.conversation.tasks.create_celery_async_session")
    def test_expire_stale_zero_expired(self, mock_create_session):
        """Test task with zero expired actions."""
        from src.modules.conversation.tasks import expire_stale_actions_task

        mock_engine, session_factory, mock_session = self._build_session_mocks()
        mock_create_session.return_value = (mock_engine, session_factory)

        mock_service = AsyncMock()
        mock_service.expire_stale.return_value = 0

        with patch(
            "src.modules.conversation.pending_action_service.PendingActionService",
            return_value=mock_service,
        ):
            result = expire_stale_actions_task()

        assert result["actions_expired"] == 0
        assert result["errors"] == []

    @patch("src.modules.conversation.tasks.create_celery_async_session")
    def test_expire_stale_disposes_engine(self, mock_create_session):
        """Test that the engine is always disposed (even on error)."""
        from src.modules.conversation.tasks import expire_stale_actions_task

        mock_engine, session_factory, mock_session = self._build_session_mocks()
        mock_create_session.return_value = (mock_engine, session_factory)

        mock_service = AsyncMock()
        mock_service.expire_stale.return_value = 3

        with patch(
            "src.modules.conversation.pending_action_service.PendingActionService",
            return_value=mock_service,
        ):
            expire_stale_actions_task()

        mock_engine.dispose.assert_awaited_once()
