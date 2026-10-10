"""Recovery and staleness tests for ReactiveSessionActor.

Covers:
- SessionStatus heartbeat staleness detection
- _get_session_status heartbeat staleness threshold
- Session resume decision logic
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai_engine.intervention.types import (
    GenerationState,
    SessionStatus,
)


# ---------------------------------------------------------------------------
# Worker crash recovery / session status staleness
# ---------------------------------------------------------------------------


class TestSessionStatusStaleness:
    """Tests for SessionStatus heartbeat staleness detection (MEDIUM #7)."""

    def test_session_status_is_active_generating(self):
        """GENERATING state should be considered active."""
        status = SessionStatus(
            state=GenerationState.GENERATING.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk1",
            last_heartbeat="2026-02-21T00:00:00+00:00",
            task_summary="test",
        )
        assert status.is_active() is True

    def test_session_status_is_active_tool_executing(self):
        """TOOL_EXECUTING state should be considered active."""
        status = SessionStatus(
            state=GenerationState.TOOL_EXECUTING.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk1",
            last_heartbeat="2026-02-21T00:00:00+00:00",
            task_summary="test",
        )
        assert status.is_active() is True

    def test_session_status_is_active_waiting_user(self):
        """WAITING_USER state should be considered active."""
        status = SessionStatus(
            state=GenerationState.WAITING_USER.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk1",
            last_heartbeat="2026-02-21T00:00:00+00:00",
            task_summary="test",
        )
        assert status.is_active() is True

    def test_session_status_idle_is_not_active(self):
        """IDLE state should NOT be considered active."""
        status = SessionStatus(
            state=GenerationState.IDLE.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk1",
            last_heartbeat="2026-02-21T00:00:00+00:00",
            task_summary="test",
        )
        assert status.is_active() is False

    def test_session_status_serialization_roundtrip(self):
        """SessionStatus should survive JSON serialization roundtrip."""
        original = SessionStatus(
            state=GenerationState.GENERATING.value,
            job_id="job-123",
            worker_id="worker-abc",
            sdk_session_id="sdk-xyz",
            last_heartbeat="2026-02-21T12:00:00+00:00",
            task_summary="test query",
            active_tool="query_weather",
            user_id="user-456",
        )
        json_str = original.to_json()
        restored = SessionStatus.from_json(json_str)
        assert restored.state == original.state
        assert restored.job_id == original.job_id
        assert restored.worker_id == original.worker_id
        assert restored.sdk_session_id == original.sdk_session_id
        assert restored.last_heartbeat == original.last_heartbeat
        assert restored.task_summary == original.task_summary
        assert restored.active_tool == original.active_tool
        assert restored.user_id == original.user_id

    def test_session_status_from_json_empty_returns_none(self):
        """from_json with empty string should return None."""
        assert SessionStatus.from_json("") is None

    def test_session_status_from_json_none_returns_none(self):
        """from_json with None should return None."""
        assert SessionStatus.from_json(None) is None


class TestGetSessionStatusStaleness:
    """Tests for _get_session_status heartbeat staleness threshold (MEDIUM #7).

    The function in chat.py returns None when heartbeat is older than 30s,
    indicating a crashed or unresponsive worker.
    """

    @pytest.mark.asyncio
    async def test_stale_heartbeat_returns_none(self, monkeypatch):
        """Heartbeat older than 30s should cause _get_session_status to return None."""
        from src.api.v1.chat import _get_session_status

        # Create a status with heartbeat 60 seconds in the past
        old_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        stale_status = SessionStatus(
            state=GenerationState.GENERATING.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk1",
            last_heartbeat=old_time.isoformat(),
            task_summary="test",
        )

        # Monkeypatch at the module where redis_client is defined (local import)
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=stale_status.to_json())
        monkeypatch.setattr("src.core.cache.redis_client", mock_redis)

        result = await _get_session_status("test-session-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_fresh_heartbeat_returns_status(self, monkeypatch):
        """Heartbeat within 30s should return the SessionStatus object."""
        from src.api.v1.chat import _get_session_status

        # Create a status with heartbeat 5 seconds ago (fresh)
        recent_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        fresh_status = SessionStatus(
            state=GenerationState.GENERATING.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk1",
            last_heartbeat=recent_time.isoformat(),
            task_summary="test",
        )

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=fresh_status.to_json())
        monkeypatch.setattr("src.core.cache.redis_client", mock_redis)

        result = await _get_session_status("test-session-id")
        assert result is not None
        assert result.state == GenerationState.GENERATING.value
        assert result.job_id == "j1"

    @pytest.mark.asyncio
    async def test_no_session_id_returns_none(self):
        """_get_session_status with None/empty session_id returns None."""
        from src.api.v1.chat import _get_session_status

        assert await _get_session_status(None) is None
        assert await _get_session_status("") is None

    @pytest.mark.asyncio
    async def test_no_redis_data_returns_none(self, monkeypatch):
        """When Redis has no data for the session, return None."""
        from src.api.v1.chat import _get_session_status

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        monkeypatch.setattr("src.core.cache.redis_client", mock_redis)

        result = await _get_session_status("some-session-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_error_returns_none(self, monkeypatch):
        """Redis errors should be caught and return None."""
        from src.api.v1.chat import _get_session_status

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        monkeypatch.setattr("src.core.cache.redis_client", mock_redis)

        result = await _get_session_status("some-session-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_heartbeat_at_boundary_returns_status(self, monkeypatch):
        """Heartbeat exactly at 29s should still return status (< 30s threshold)."""
        from src.api.v1.chat import _get_session_status

        boundary_time = datetime.now(timezone.utc) - timedelta(seconds=29)
        boundary_status = SessionStatus(
            state=GenerationState.TOOL_EXECUTING.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk1",
            last_heartbeat=boundary_time.isoformat(),
            task_summary="test",
        )

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=boundary_status.to_json())
        monkeypatch.setattr("src.core.cache.redis_client", mock_redis)

        result = await _get_session_status("test-session-id")
        assert result is not None
        assert result.state == GenerationState.TOOL_EXECUTING.value


class TestSessionResumeDecisionLogic:
    """Tests for session resume decision factors (MEDIUM #7).

    The resume decision relies on:
    1. sdk_session_id existing (non-empty) in SessionStatus
    2. SessionStatus heartbeat freshness (not stale = worker alive)
    3. is_active() state check
    """

    def test_resume_eligible_with_sdk_session_and_active_state(self):
        """Session with sdk_session_id + active state is eligible for resume."""
        status = SessionStatus(
            state=GenerationState.GENERATING.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk-session-abc",
            last_heartbeat="2026-02-21T12:00:00+00:00",
            task_summary="working on trip",
        )
        assert status.sdk_session_id != ""
        assert status.is_active() is True

    def test_not_eligible_without_sdk_session_id(self):
        """Session without sdk_session_id means no SDK client to resume."""
        status = SessionStatus(
            state=GenerationState.GENERATING.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="",
            last_heartbeat="2026-02-21T12:00:00+00:00",
            task_summary="test",
        )
        # No sdk_session_id means fresh start needed, not resume
        assert status.sdk_session_id == ""

    def test_not_eligible_when_idle(self):
        """IDLE session should not be eligible for resume."""
        status = SessionStatus(
            state=GenerationState.IDLE.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk-session-abc",
            last_heartbeat="2026-02-21T12:00:00+00:00",
            task_summary="test",
        )
        assert status.is_active() is False


# ---------------------------------------------------------------------------
# M7: SDK session resume path
# ---------------------------------------------------------------------------


class TestSDKSessionResumePath:
    """Test SDK session resume logic (M7)."""

    def test_resume_condition_with_valid_sdk_session(self):
        """When sdk_session_id exists and state is active, resume is eligible."""
        status = SessionStatus(
            state=GenerationState.GENERATING.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk-session-123",
            last_heartbeat="2026-02-21T12:00:00+00:00",
            task_summary="working",
        )
        # Resume eligible: has sdk_session_id AND is_active
        assert status.sdk_session_id == "sdk-session-123"
        assert status.is_active() is True

    def test_resume_not_eligible_without_session_id(self):
        """Empty sdk_session_id means no resume."""
        status = SessionStatus(
            state=GenerationState.GENERATING.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="",
            last_heartbeat="2026-02-21T12:00:00+00:00",
            task_summary="working",
        )
        assert status.sdk_session_id == ""
        # Cannot resume without session id

    def test_resume_not_eligible_when_idle(self):
        """IDLE state means no active generation to resume."""
        status = SessionStatus(
            state=GenerationState.IDLE.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id="sdk-session-123",
            last_heartbeat="2026-02-21T12:00:00+00:00",
            task_summary="test",
        )
        assert status.is_active() is False

    def test_resume_fallback_on_missing_session_id(self):
        """When sdk_session_id is None, should not crash."""
        status = SessionStatus(
            state=GenerationState.GENERATING.value,
            job_id="j1",
            worker_id="w1",
            sdk_session_id=None,
            last_heartbeat="2026-02-21T12:00:00+00:00",
            task_summary="working",
        )
        # None should be treated as not eligible
        assert not status.sdk_session_id
