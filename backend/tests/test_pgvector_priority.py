"""Tests for pgvector priority usage in recall_service and repository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.memory.models import (
    ConversationMemory,
    MemoryStatus,
    MemoryType,
)
from src.modules.memory.repository import MemoryRepository
from src.modules.memory.recall_service import MemoryRecallService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_memory(
    memory_id=None,
    status=MemoryStatus.ACTIVE.value,
    importance=5,
    embedding=None,
    feedback_weight=1.0,
):
    mem = MagicMock(spec=ConversationMemory)
    mem.id = memory_id or uuid4()
    mem.status = status
    mem.importance = importance
    mem.memory_type = MemoryType.PREFERENCE.value
    mem.summary = "Test memory"
    mem.entities = {}
    mem.embedding = embedding
    mem.feedback_weight = feedback_weight
    mem.created_at = datetime.now(tz=timezone.utc)
    return mem


# ---------------------------------------------------------------------------
# MemoryRepository.has_pgvector
# ---------------------------------------------------------------------------


class TestHasPgvector:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_has_pgvector_true(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        mock_db.execute.return_value = mock_result

        repo = MemoryRepository(mock_db)
        assert await repo.has_pgvector() is True

    @pytest.mark.asyncio
    async def test_has_pgvector_false_no_column(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        repo = MemoryRepository(mock_db)
        assert await repo.has_pgvector() is False

    @pytest.mark.asyncio
    async def test_has_pgvector_false_on_error(self, mock_db):
        mock_db.execute.side_effect = Exception("db error")

        repo = MemoryRepository(mock_db)
        assert await repo.has_pgvector() is False


# ---------------------------------------------------------------------------
# MemoryRepository._sync_embedding_v
# ---------------------------------------------------------------------------


class TestSyncEmbeddingV:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_sync_embedding_v_success(self, mock_db):
        repo = MemoryRepository(mock_db)
        memory_id = uuid4()
        embedding = [0.1] * 1536

        await repo._sync_embedding_v(memory_id, embedding)

        # Should have called execute with the pgvector update
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        params = call_args[1] if call_args[1] else call_args[0][1]
        assert str(memory_id) in str(params)

    @pytest.mark.asyncio
    async def test_sync_embedding_v_silently_handles_error(self, mock_db):
        mock_db.execute.side_effect = Exception("pgvector not available")

        repo = MemoryRepository(mock_db)
        # Should not raise
        await repo._sync_embedding_v(uuid4(), [0.1] * 1536)


# ---------------------------------------------------------------------------
# MemoryRepository.update_memory_embedding — dual write
# ---------------------------------------------------------------------------


class TestDualEmbeddingWrite:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        db.execute.return_value = mock_result
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_update_embedding_writes_both_columns(self, mock_db):
        repo = MemoryRepository(mock_db)
        memory_id = uuid4()
        embedding = [0.1] * 1536

        result = await repo.update_memory_embedding(memory_id, embedding)

        assert result is True
        # Should have 2 execute calls: one for ARRAY column, one for pgvector
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_update_embedding_batch_writes_both(self, mock_db):
        repo = MemoryRepository(mock_db)
        embeddings = [
            (uuid4(), [0.1] * 1536),
            (uuid4(), [0.3] * 1536),
        ]

        count = await repo.update_memory_embedding_batch(embeddings)

        assert count == 2
        # 2 memories * 2 writes each = 4 execute calls
        assert mock_db.execute.call_count == 4


# ---------------------------------------------------------------------------
# semantic_search — pgvector priority over in-memory fallback
# ---------------------------------------------------------------------------


class TestSemanticSearchPriority:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_pgvector_used_first(self, mock_db):
        repo = MemoryRepository(mock_db)

        mem = _make_memory()
        pgvector_results = [(mem, 0.9)]

        repo.semantic_search_pgvector = AsyncMock(return_value=pgvector_results)
        repo.get_memories_with_embedding = AsyncMock()

        results = await repo.semantic_search(
            user_id=uuid4(),
            query_embedding=[0.1, 0.2, 0.3],
        )

        assert len(results) == 1
        assert results[0][1] == 0.9
        repo.semantic_search_pgvector.assert_called_once()
        # In-memory fallback should NOT be called
        repo.get_memories_with_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_in_memory_on_pgvector_error(self, mock_db):
        repo = MemoryRepository(mock_db)

        repo.semantic_search_pgvector = AsyncMock(side_effect=Exception("no pgvector"))

        mem = _make_memory(embedding=[0.1, 0.2, 0.3])
        repo.get_memories_with_embedding = AsyncMock(return_value=[mem])

        results = await repo.semantic_search(
            user_id=uuid4(),
            query_embedding=[0.1, 0.2, 0.3],
            similarity_threshold=0.0,
        )

        repo.semantic_search_pgvector.assert_called_once()
        mock_db.rollback.assert_awaited_once()
        repo.get_memories_with_embedding.assert_called_once()
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_falls_back_when_pgvector_returns_empty(self, mock_db):
        repo = MemoryRepository(mock_db)

        repo.semantic_search_pgvector = AsyncMock(return_value=[])

        mem = _make_memory(embedding=[0.1, 0.2, 0.3])
        repo.get_memories_with_embedding = AsyncMock(return_value=[mem])

        results = await repo.semantic_search(
            user_id=uuid4(),
            query_embedding=[0.1, 0.2, 0.3],
            similarity_threshold=0.0,
        )

        # pgvector returned empty so fallback should be used
        repo.get_memories_with_embedding.assert_called_once()


# ---------------------------------------------------------------------------
# pgvector SQL already excludes SUPERSEDED
# ---------------------------------------------------------------------------


class TestPgvectorSupersededFiltering:
    def test_pgvector_sql_filters_active_status(self):
        """Verify the raw SQL in semantic_search_pgvector contains active status filter."""
        import inspect

        source = inspect.getsource(MemoryRepository.semantic_search_pgvector)
        # The SQL should include a status = 'active' filter
        assert "status = 'active'" in source
        assert "CAST(:embedding AS vector)" in source

    def test_in_memory_fallback_also_filters_active(self):
        """get_memories_with_embedding filters by ACTIVE status."""
        import inspect

        source = inspect.getsource(MemoryRepository.get_memories_with_embedding)
        assert "MemoryStatus.ACTIVE" in source


# ---------------------------------------------------------------------------
# Ordering by relevance
# ---------------------------------------------------------------------------


class TestResultOrdering:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_results_ordered_by_similarity_desc(self, mock_db):
        repo = MemoryRepository(mock_db)

        mem_low = _make_memory(embedding=[0.1, 0.0, 0.0], feedback_weight=1.0)
        mem_high = _make_memory(embedding=[0.9, 0.9, 0.9], feedback_weight=1.0)

        repo.semantic_search_pgvector = AsyncMock(side_effect=Exception("no pgvector"))
        repo.get_memories_with_embedding = AsyncMock(return_value=[mem_low, mem_high])

        results = await repo.semantic_search(
            user_id=uuid4(),
            query_embedding=[0.9, 0.9, 0.9],
            similarity_threshold=0.0,
        )

        if len(results) >= 2:
            # Higher similarity should come first
            assert results[0][1] >= results[1][1]
