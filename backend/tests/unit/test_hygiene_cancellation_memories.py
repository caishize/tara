"""Tests for _extract_cancellation_memories in EventHygieneService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import uuid4

import pytest

from src.modules.curation.services.hygiene_service import EventHygieneService


def _make_cancelled_event(**overrides):
    """Create a mock cancelled CuratedEvent."""
    ev = MagicMock()
    ev.id = overrides.get("id", uuid4())
    ev.user_id = overrides.get("user_id", uuid4())
    ev.family_id = overrides.get("family_id", uuid4())
    ev.title = overrides.get("title", "去三亚旅行")
    ev.event_type = overrides.get("event_type", "travel")
    ev.priority = overrides.get("priority", "high")
    ev.location = overrides.get("location", "三亚")
    ev.normalized_start = overrides.get(
        "normalized_start",
        datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc),
    )
    ev.updated_at = overrides.get(
        "updated_at",
        datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
    )
    ev.status = "cancelled"
    ev.source_types = overrides.get("source_types", ["calendar"])
    return ev


class TestExtractCancellationMemories:

    @pytest.fixture()
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture()
    def service(self, mock_db):
        return EventHygieneService(session=mock_db)

    @pytest.mark.asyncio
    async def test_qualifying_event_creates_memory(self, service, mock_db):
        """High-priority significant event creates a PLAN memory."""
        event = _make_cancelled_event(
            event_type="travel", priority="high",
        )
        count = await service._extract_cancellation_memories([event])

        assert count == 1
        mock_db.add.assert_called_once()
        memory = mock_db.add.call_args[0][0]
        assert "三亚" in memory.content
        assert "取消" in memory.content

    @pytest.mark.asyncio
    async def test_low_priority_event_skipped(self, service, mock_db):
        """Low-priority events don't qualify for memory extraction."""
        event = _make_cancelled_event(priority="low")
        count = await service._extract_cancellation_memories([event])

        assert count == 0
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_significant_event_type_skipped(self, service, mock_db):
        """Event types not in _SIGNIFICANT_EVENT_TYPES are skipped."""
        event = _make_cancelled_event(
            event_type="task", priority="high",
        )
        count = await service._extract_cancellation_memories([event])

        assert count == 0
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_user_id_skipped(self, service, mock_db):
        """Events without user_id are skipped."""
        event = _make_cancelled_event(user_id=None, priority="high")
        count = await service._extract_cancellation_memories([event])

        assert count == 0
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_qualifying_events(self, service, mock_db):
        """Multiple qualifying events create one memory each."""
        events = [
            _make_cancelled_event(
                event_type="medical", priority="normal",
                title="体检", location="协和医院",
            ),
            _make_cancelled_event(
                event_type="birthday", priority="high",
                title="妈妈生日", location=None,
            ),
        ]
        count = await service._extract_cancellation_memories(events)

        assert count == 2
        assert mock_db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_event_without_start_uses_updated_at(self, service, mock_db):
        """Events without normalized_start fall back to updated_at for date."""
        event = _make_cancelled_event(
            normalized_start=None,
            updated_at=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        )
        count = await service._extract_cancellation_memories([event])

        assert count == 1
        memory = mock_db.add.call_args[0][0]
        assert "2026-01-15" in memory.content

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero(self, service, mock_db):
        """Empty events list returns 0."""
        count = await service._extract_cancellation_memories([])
        assert count == 0
        mock_db.add.assert_not_called()
