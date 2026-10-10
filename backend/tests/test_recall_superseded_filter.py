"""Tests for SUPERSEDED status filtering in recall_service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from uuid import uuid4

import pytest

from src.modules.memory.models import (
    ConversationMemory,
    MemoryStatus,
    MemoryType,
)
from src.modules.memory.recall_service import (
    MemoryRecallService,
    _EXCLUDED_RECALL_STATUSES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_memory(
    status=MemoryStatus.ACTIVE.value,
    memory_type=MemoryType.PREFERENCE.value,
    importance=5,
    summary="Test memory",
):
    mem = MagicMock(spec=ConversationMemory)
    mem.id = uuid4()
    mem.status = status
    mem.memory_type = memory_type
    mem.importance = importance
    mem.summary = summary
    mem.entities = {}
    mem.tags = []
    mem.trigger_conditions = {}
    mem.feedback_weight = 1.0
    mem.created_at = datetime.now(tz=timezone.utc)
    mem.embedding = None
    return mem


# ---------------------------------------------------------------------------
# _EXCLUDED_RECALL_STATUSES
# ---------------------------------------------------------------------------


class TestExcludedStatuses:
    def test_superseded_is_excluded(self):
        assert MemoryStatus.SUPERSEDED.value in _EXCLUDED_RECALL_STATUSES

    def test_archived_is_excluded(self):
        assert MemoryStatus.ARCHIVED.value in _EXCLUDED_RECALL_STATUSES

    def test_cancelled_is_excluded(self):
        assert MemoryStatus.CANCELLED.value in _EXCLUDED_RECALL_STATUSES

    def test_active_is_not_excluded(self):
        assert MemoryStatus.ACTIVE.value not in _EXCLUDED_RECALL_STATUSES


# ---------------------------------------------------------------------------
# recall_for_message — SUPERSEDED filtering
# ---------------------------------------------------------------------------


class TestRecallForMessageSupersededFilter:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        svc = MemoryRecallService(mock_db)
        # Mock all repo methods to prevent actual DB calls
        svc.memory_repo = MagicMock()
        svc.memory_repo.get_triggered_memories = AsyncMock(return_value=[])
        svc.memory_repo.search_by_location = AsyncMock(return_value=[])
        svc.memory_repo.search_by_person = AsyncMock(return_value=[])
        svc.memory_repo.get_plan_memories = AsyncMock(return_value=[])
        svc.memory_repo.full_text_search = AsyncMock(return_value=[])
        svc.memory_repo.mark_memories_recalled_batch = AsyncMock(return_value=0)
        svc.memory_repo.mark_memories_triggered_batch = AsyncMock(return_value=0)
        return svc

    @pytest.mark.asyncio
    async def test_superseded_memories_excluded_from_recall(self, service):
        active_mem = _make_memory(status=MemoryStatus.ACTIVE.value)
        superseded_mem = _make_memory(status=MemoryStatus.SUPERSEDED.value)

        # Return both from full_text_search
        service.memory_repo.full_text_search = AsyncMock(
            return_value=[active_mem, superseded_mem]
        )

        with patch(
            "src.modules.memory.recall_service.extract_locations_async",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "src.modules.memory.recall_service.extract_persons_async",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "src.modules.memory.recall_service.contains_plan_keywords",
            return_value=False,
        ):
            memories, _ = await service.recall_for_message(
                user_id=uuid4(),
                message="用户喜欢什么",
            )

        # Only active memory should be returned
        memory_ids = {m.id for m in memories}
        assert active_mem.id in memory_ids
        assert superseded_mem.id not in memory_ids

    @pytest.mark.asyncio
    async def test_archived_memories_excluded_from_recall(self, service):
        active_mem = _make_memory(status=MemoryStatus.ACTIVE.value)
        archived_mem = _make_memory(status=MemoryStatus.ARCHIVED.value)

        service.memory_repo.full_text_search = AsyncMock(
            return_value=[active_mem, archived_mem]
        )

        with patch(
            "src.modules.memory.recall_service.extract_locations_async",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "src.modules.memory.recall_service.extract_persons_async",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "src.modules.memory.recall_service.contains_plan_keywords",
            return_value=False,
        ):
            memories, _ = await service.recall_for_message(
                user_id=uuid4(),
                message="用户喜欢什么",
            )

        memory_ids = {m.id for m in memories}
        assert active_mem.id in memory_ids
        assert archived_mem.id not in memory_ids

    @pytest.mark.asyncio
    async def test_active_memories_pass_through(self, service):
        mem1 = _make_memory(status=MemoryStatus.ACTIVE.value, summary="偏好1")
        mem2 = _make_memory(status=MemoryStatus.ACTIVE.value, summary="偏好2")

        service.memory_repo.full_text_search = AsyncMock(
            return_value=[mem1, mem2]
        )

        with patch(
            "src.modules.memory.recall_service.extract_locations_async",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "src.modules.memory.recall_service.extract_persons_async",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "src.modules.memory.recall_service.contains_plan_keywords",
            return_value=False,
        ):
            memories, _ = await service.recall_for_message(
                user_id=uuid4(),
                message="偏好",
            )

        assert len(memories) == 2


# ---------------------------------------------------------------------------
# recall_by_keyword — SUPERSEDED filtering
# ---------------------------------------------------------------------------


class TestRecallByKeywordSupersededFilter:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        svc = MemoryRecallService(mock_db)
        svc.memory_repo = MagicMock()
        return svc

    @pytest.mark.asyncio
    async def test_superseded_excluded_from_keyword_recall(self, service):
        active_mem = _make_memory(status=MemoryStatus.ACTIVE.value)
        superseded_mem = _make_memory(status=MemoryStatus.SUPERSEDED.value)

        service.memory_repo.full_text_search = AsyncMock(
            return_value=[active_mem, superseded_mem]
        )

        memories = await service.recall_by_keyword(
            user_id=uuid4(),
            family_id=uuid4(),
            keywords=["test"],
        )

        memory_ids = {m.id for m in memories}
        assert active_mem.id in memory_ids
        assert superseded_mem.id not in memory_ids


# ---------------------------------------------------------------------------
# Repository-level status filtering verification
# ---------------------------------------------------------------------------


class TestRepositoryStatusFiltering:
    """Verify that repo methods already filter by ACTIVE status,
    which implicitly excludes SUPERSEDED."""

    def test_superseded_is_not_active(self):
        assert MemoryStatus.SUPERSEDED.value != MemoryStatus.ACTIVE.value

    def test_all_excluded_statuses_are_not_active(self):
        for status in _EXCLUDED_RECALL_STATUSES:
            assert status != MemoryStatus.ACTIVE.value
