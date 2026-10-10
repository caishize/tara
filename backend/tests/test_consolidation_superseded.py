"""Tests for superseded_by fix in consolidation_service."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.memory.models import (
    ConversationMemory,
    MemoryStatus,
    MemorySummary,
    MemoryType,
    SummaryType,
)
from src.modules.memory.consolidation_service import MemoryConsolidationService
from src.modules.memory.repository import MemoryRepository


# ---------------------------------------------------------------------------
# MemoryRepository.mark_memories_superseded
# ---------------------------------------------------------------------------


class TestMarkMemoriesSuperseded:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 3
        db.execute.return_value = mock_result
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_mark_superseded_sets_status_and_superseded_by(self, mock_db):
        repo = MemoryRepository(mock_db)
        summary_id = uuid4()
        memory_ids = [uuid4(), uuid4(), uuid4()]

        count = await repo.mark_memories_superseded(memory_ids, summary_id)

        assert count == 3
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_superseded_empty_list(self, mock_db):
        repo = MemoryRepository(mock_db)
        count = await repo.mark_memories_superseded([], uuid4())
        assert count == 0
        mock_db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Consolidation topic summary marks memories as superseded
# ---------------------------------------------------------------------------


class TestConsolidationSuperseded:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.flush = AsyncMock()
        db.refresh = AsyncMock()
        return db

    def _make_memory(self, memory_type="preference", importance=5):
        mem = MagicMock(spec=ConversationMemory)
        mem.id = uuid4()
        mem.summary = "Test memory"
        mem.importance = importance
        mem.memory_type = memory_type
        mem.entities = {}
        mem.created_at = None
        mem.status = MemoryStatus.ACTIVE.value
        return mem

    @pytest.mark.asyncio
    async def test_create_topic_summary_marks_superseded(self, mock_db):
        service = MemoryConsolidationService(mock_db)

        # Mock the LLM
        mock_response = MagicMock()
        mock_response.content = "Test topic summary"
        service.llm = MagicMock()
        service.llm.chat = AsyncMock(return_value=mock_response)

        # Mock the repo's mark_memories_superseded
        service.memory_repo.mark_memories_superseded = AsyncMock(return_value=3)

        # Mock flush to assign an ID to the summary object
        summary_id = uuid4()

        async def fake_flush():
            # Find the MemorySummary that was added to the session
            for call in mock_db.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, MemorySummary) and obj.id is None:
                    obj.id = summary_id

        mock_db.flush = AsyncMock(side_effect=fake_flush)

        memories = [self._make_memory() for _ in range(3)]
        memory_ids = [m.id for m in memories]

        from src.core.utils.timezone import utc_now

        now = utc_now()
        period_start = now - timedelta(days=7)

        await service._create_topic_summary(
            user_id=uuid4(),
            family_id=uuid4(),
            topic="preference",
            memories=memories,
            period_start=period_start,
            period_end=now,
        )

        # Verify mark_memories_superseded was called with correct args
        service.memory_repo.mark_memories_superseded.assert_called_once()
        call_args = service.memory_repo.mark_memories_superseded.call_args
        assert set(call_args.kwargs["memory_ids"]) == set(memory_ids)
        # superseded_by should point to the summary (ID assigned by flush)
        assert call_args.kwargs["superseded_by"] == summary_id

    @pytest.mark.asyncio
    async def test_create_period_summary_marks_remaining_active(self, mock_db):
        service = MemoryConsolidationService(mock_db)

        mock_response = MagicMock()
        mock_response.content = "Weekly summary"
        service.llm = MagicMock()
        service.llm.chat = AsyncMock(return_value=mock_response)

        service.memory_repo.mark_memories_superseded = AsyncMock(return_value=2)

        # Mock flush to assign ID
        period_summary_id = uuid4()

        async def fake_flush():
            for call in mock_db.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, MemorySummary) and obj.id is None:
                    obj.id = period_summary_id

        mock_db.flush = AsyncMock(side_effect=fake_flush)

        # Some memories already superseded by topic, some still active
        mem_active_1 = self._make_memory()
        mem_active_1.status = MemoryStatus.ACTIVE.value

        mem_active_2 = self._make_memory()
        mem_active_2.status = MemoryStatus.ACTIVE.value

        mem_superseded = self._make_memory()
        mem_superseded.status = MemoryStatus.SUPERSEDED.value

        memories = [mem_active_1, mem_active_2, mem_superseded]

        from src.core.utils.timezone import utc_now

        now = utc_now()
        period_start = now - timedelta(days=7)

        await service._create_period_summary(
            user_id=uuid4(),
            family_id=uuid4(),
            memories=memories,
            period_start=period_start,
            period_end=now,
        )

        # Should only mark the 2 still-active memories, not the already-superseded one
        service.memory_repo.mark_memories_superseded.assert_called_once()
        call_args = service.memory_repo.mark_memories_superseded.call_args
        superseded_ids = set(call_args.kwargs["memory_ids"])
        assert mem_active_1.id in superseded_ids
        assert mem_active_2.id in superseded_ids
        assert mem_superseded.id not in superseded_ids

    @pytest.mark.asyncio
    async def test_create_period_summary_skips_if_all_superseded(self, mock_db):
        service = MemoryConsolidationService(mock_db)

        mock_response = MagicMock()
        mock_response.content = "Weekly summary"
        service.llm = MagicMock()
        service.llm.chat = AsyncMock(return_value=mock_response)

        service.memory_repo.mark_memories_superseded = AsyncMock()

        # Mock flush to assign ID
        async def fake_flush():
            for call in mock_db.add.call_args_list:
                obj = call[0][0]
                if isinstance(obj, MemorySummary) and obj.id is None:
                    obj.id = uuid4()

        mock_db.flush = AsyncMock(side_effect=fake_flush)

        mem = self._make_memory()
        mem.status = MemoryStatus.SUPERSEDED.value

        from src.core.utils.timezone import utc_now

        now = utc_now()

        await service._create_period_summary(
            user_id=uuid4(),
            family_id=uuid4(),
            memories=[mem],
            period_start=now - timedelta(days=7),
            period_end=now,
        )

        # No active memories to supersede
        service.memory_repo.mark_memories_superseded.assert_not_called()


# ---------------------------------------------------------------------------
# Model field existence checks
# ---------------------------------------------------------------------------


class TestConversationMemoryFields:
    def test_superseded_by_field_exists(self):
        assert hasattr(ConversationMemory, "superseded_by")

    def test_superseded_status_exists(self):
        assert MemoryStatus.SUPERSEDED.value == "superseded"

    def test_is_consolidated_field_exists(self):
        assert hasattr(ConversationMemory, "is_consolidated")
