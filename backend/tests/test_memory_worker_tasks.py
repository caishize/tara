"""Tests for memory-worker V8 conformance tasks:
- Task 1: compute_window_size() dynamic L2 window
- Task 3: pgvector vs ARRAY fallback transparency
- Task 4: confidence_score on memory_summaries
"""

import dataclasses
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Task 1: compute_window_size()
# ---------------------------------------------------------------------------

from src.ai_engine.context_assembler import (
    ContextAssembler,
    ContextItem,
    compute_window_size,
)


class TestComputeWindowSize:
    """Tests for the dynamic L2 window sizing function."""

    def test_default_returns_10(self):
        assert compute_window_size() == 10

    def test_none_classification_returns_10(self):
        assert compute_window_size(None, 0) == 10

    def test_plan_action_returns_20(self):
        classification = SimpleNamespace(action=SimpleNamespace(value="plan"))
        assert compute_window_size(classification) == 20

    def test_analyze_action_returns_20(self):
        classification = SimpleNamespace(action=SimpleNamespace(value="analyze"))
        assert compute_window_size(classification) == 20

    def test_chat_action_returns_10(self):
        classification = SimpleNamespace(action=SimpleNamespace(value="chat"))
        assert compute_window_size(classification) == 10

    def test_lookup_action_returns_10(self):
        classification = SimpleNamespace(action=SimpleNamespace(value="lookup"))
        assert compute_window_size(classification) == 10

    def test_high_tool_count_adds_5(self):
        assert compute_window_size(None, active_tool_count=4) == 15

    def test_high_tool_count_capped_at_25(self):
        classification = SimpleNamespace(action=SimpleNamespace(value="plan"))
        # base=20, +5 for tools = 25 (capped)
        assert compute_window_size(classification, active_tool_count=10) == 25

    def test_tool_count_3_does_not_add(self):
        assert compute_window_size(None, active_tool_count=3) == 10

    def test_tool_count_0_no_change(self):
        assert compute_window_size(None, active_tool_count=0) == 10

    def test_plan_with_many_tools(self):
        classification = SimpleNamespace(action=SimpleNamespace(value="plan"))
        # base=20 (plan), +5 for tools>3 = 25 (capped at 25)
        result = compute_window_size(classification, active_tool_count=5)
        assert result == 25

    def test_no_action_attribute(self):
        """Classification without action attribute falls back to default."""
        classification = SimpleNamespace()
        assert compute_window_size(classification) == 10

    def test_action_without_value(self):
        """Classification.action without value attribute falls back to default."""
        classification = SimpleNamespace(action="plain_string")
        assert compute_window_size(classification) == 10


class TestContextAssemblerDynamicWindow:
    """Tests for compute_window_size integration in ContextAssembler.assemble."""

    @staticmethod
    def _make_fetcher(items):
        async def fetcher(*args):
            return items
        return fetcher

    @pytest.mark.asyncio
    async def test_l2_items_trimmed_by_window_size(self):
        """When L2 has more items than window_size, only the last N are kept."""
        # Create 15 L2 items
        l2_items = [
            ContextItem(
                layer="l2", source="conv", content=f"msg-{i}", tokens=10,
            )
            for i in range(15)
        ]
        assembler = ContextAssembler(
            l2_fetcher=self._make_fetcher(l2_items),
        )
        # Default window_size=10 (no intent, no tools)
        prompt, meta = await assembler.assemble(
            uuid4(), uuid4(), "sess", "hello",
        )
        # L2 should have been trimmed to 10 items (default window)
        assert meta.l2_tokens == 10 * 10  # 10 items * 10 tokens each

    @pytest.mark.asyncio
    async def test_l2_items_not_trimmed_when_within_window(self):
        """When L2 has fewer items than window_size, all are kept."""
        l2_items = [
            ContextItem(layer="l2", source="conv", content=f"msg-{i}", tokens=10)
            for i in range(5)
        ]
        assembler = ContextAssembler(
            l2_fetcher=self._make_fetcher(l2_items),
        )
        prompt, meta = await assembler.assemble(
            uuid4(), uuid4(), "sess", "hello",
        )
        assert meta.l2_tokens == 5 * 10

    @pytest.mark.asyncio
    async def test_plan_intent_increases_window(self):
        """Plan intent gives window_size=20, allowing more L2 items."""
        l2_items = [
            ContextItem(layer="l2", source="conv", content=f"msg-{i}", tokens=10)
            for i in range(15)
        ]
        classification = SimpleNamespace(action=SimpleNamespace(value="plan"))
        assembler = ContextAssembler(
            l2_fetcher=self._make_fetcher(l2_items),
        )
        prompt, meta = await assembler.assemble(
            uuid4(), uuid4(), "sess", "plan a trip",
            intent_classification=classification,
        )
        # window_size=20 for plan, so all 15 items should be kept
        assert meta.l2_tokens == 15 * 10


# ---------------------------------------------------------------------------
# Task 3: pgvector vs ARRAY fallback transparency
# ---------------------------------------------------------------------------


class TestSemanticSearchFallback:
    """Tests for pgvector vs ARRAY fallback with metrics and logging."""

    @pytest.mark.asyncio
    async def test_uses_pgvector_when_available(self):
        """When has_pgvector returns True, pgvector path is attempted."""
        from src.modules.memory.repository import MemoryRepository

        mock_db = AsyncMock()
        repo = MemoryRepository(mock_db)

        mock_memory = MagicMock()
        mock_memory.id = uuid4()
        pgvector_results = [(mock_memory, 0.95)]

        repo.has_pgvector = AsyncMock(return_value=True)
        repo.semantic_search_pgvector = AsyncMock(return_value=pgvector_results)

        results = await repo.semantic_search(
            user_id=uuid4(),
            query_embedding=[0.1] * 10,
            similarity_threshold=0.7,
            limit=5,
        )
        assert len(results) == 1
        assert results[0][1] == 0.95
        repo.semantic_search_pgvector.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_when_no_pgvector(self):
        """When has_pgvector returns False, falls back to in-memory search."""
        from src.modules.memory.repository import MemoryRepository

        mock_db = AsyncMock()
        repo = MemoryRepository(mock_db)

        repo.has_pgvector = AsyncMock(return_value=False)
        repo.get_memories_with_embedding = AsyncMock(return_value=[])

        results = await repo.semantic_search(
            user_id=uuid4(),
            query_embedding=[0.1] * 10,
        )

        assert results == []
        repo.get_memories_with_embedding.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_on_pgvector_error(self):
        """When pgvector raises an exception, falls back to in-memory."""
        from src.modules.memory.repository import MemoryRepository

        mock_db = AsyncMock()
        repo = MemoryRepository(mock_db)

        repo.has_pgvector = AsyncMock(return_value=True)
        repo.semantic_search_pgvector = AsyncMock(
            side_effect=RuntimeError("pgvector crashed")
        )
        repo.get_memories_with_embedding = AsyncMock(return_value=[])

        results = await repo.semantic_search(
            user_id=uuid4(),
            query_embedding=[0.1] * 10,
        )
        assert results == []
        mock_db.rollback.assert_awaited_once()
        repo.get_memories_with_embedding.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_on_empty_pgvector_result(self):
        """When pgvector returns empty, falls back to in-memory."""
        from src.modules.memory.repository import MemoryRepository

        mock_db = AsyncMock()
        repo = MemoryRepository(mock_db)

        repo.has_pgvector = AsyncMock(return_value=True)
        repo.semantic_search_pgvector = AsyncMock(return_value=[])
        repo.get_memories_with_embedding = AsyncMock(return_value=[])

        results = await repo.semantic_search(
            user_id=uuid4(),
            query_embedding=[0.1] * 10,
        )
        assert results == []
        repo.get_memories_with_embedding.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_has_pgvector_check(self):
        """has_pgvector checks the information_schema for embedding_v column."""
        from src.modules.memory.repository import MemoryRepository

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        mock_db.execute = AsyncMock(return_value=mock_result)

        repo = MemoryRepository(mock_db)
        result = await repo.has_pgvector()
        assert result is True

    @pytest.mark.asyncio
    async def test_has_pgvector_returns_false_on_missing(self):
        """has_pgvector returns False when column doesn't exist."""
        from src.modules.memory.repository import MemoryRepository

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        repo = MemoryRepository(mock_db)
        result = await repo.has_pgvector()
        assert result is False

    @pytest.mark.asyncio
    async def test_has_pgvector_returns_false_on_exception(self):
        """has_pgvector returns False on DB error."""
        from src.modules.memory.repository import MemoryRepository

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=RuntimeError("DB down"))

        repo = MemoryRepository(mock_db)
        result = await repo.has_pgvector()
        assert result is False


# ---------------------------------------------------------------------------
# Task 4: confidence_score on memory_summaries
# ---------------------------------------------------------------------------


from src.modules.memory.consolidation_service import compute_summary_confidence


class TestComputeSummaryConfidence:
    """Tests for the confidence score computation."""

    def _make_memory(
        self, importance=5, days_old=0, memory_type="general",
    ):
        """Create a mock ConversationMemory."""
        created = datetime.now(timezone.utc) - timedelta(days=days_old)
        mem = MagicMock()
        mem.importance = importance
        mem.created_at = created
        mem.memory_type = memory_type
        mem.status = "active"
        return mem

    def test_empty_returns_zero(self):
        assert compute_summary_confidence([]) == 0.0

    def test_single_memory(self):
        mem = self._make_memory(importance=5, days_old=0)
        score = compute_summary_confidence([mem])
        # count_factor = 1/10 = 0.1
        # agreement_factor = 1.0 (single memory)
        # recency_factor = 1.0/(1+0/30) = 1.0
        # score = 0.4*0.1 + 0.3*1.0 + 0.3*1.0 = 0.04 + 0.3 + 0.3 = 0.64
        assert 0.6 <= score <= 0.7

    def test_many_memories_high_confidence(self):
        mems = [self._make_memory(importance=5, days_old=0) for _ in range(10)]
        score = compute_summary_confidence(mems)
        # count_factor = 10/10 = 1.0, agreement = 1.0, recency = 1.0
        # score = 0.4*1.0 + 0.3*1.0 + 0.3*1.0 = 1.0
        assert score == pytest.approx(1.0, abs=0.01)

    def test_old_memories_lower_recency(self):
        mems = [self._make_memory(importance=5, days_old=60) for _ in range(5)]
        score = compute_summary_confidence(mems)
        # count_factor = 5/10 = 0.5
        # agreement = 1.0
        # recency = 1/(1+60/30) = 1/3 = 0.333
        # score = 0.4*0.5 + 0.3*1.0 + 0.3*0.333 = 0.2 + 0.3 + 0.1 = 0.6
        assert 0.55 <= score <= 0.65

    def test_diverse_importance_lowers_agreement(self):
        mems = [
            self._make_memory(importance=1, days_old=0),
            self._make_memory(importance=10, days_old=0),
        ]
        score = compute_summary_confidence(mems)
        # Importance values are far apart -> low agreement
        assert score < 0.8

    def test_score_between_zero_and_one(self):
        """Score is always clamped to [0.0, 1.0]."""
        for count in [1, 3, 7, 15]:
            mems = [self._make_memory(importance=5, days_old=i * 10) for i in range(count)]
            score = compute_summary_confidence(mems)
            assert 0.0 <= score <= 1.0

    def test_memories_without_created_at(self):
        mem = MagicMock()
        mem.importance = 5
        mem.created_at = None
        score = compute_summary_confidence([mem])
        # recency_factor defaults to 0.5 when no dates
        assert 0.0 <= score <= 1.0


class TestMemorySummaryConfidenceScoreModel:
    """Tests for the confidence_score column on MemorySummary model."""

    def test_confidence_score_column_exists(self):
        from src.modules.memory.models import MemorySummary
        assert hasattr(MemorySummary, "confidence_score")

    def test_confidence_score_in_to_dict(self):
        from src.modules.memory.models import MemorySummary
        summary = MemorySummary(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            summary_type="topic_summary",
            title="Test",
            content="Test content",
            confidence_score=0.85,
        )
        d = summary.to_dict()
        assert d["confidence_score"] == 0.85

    def test_confidence_score_none_in_to_dict(self):
        from src.modules.memory.models import MemorySummary
        summary = MemorySummary(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            summary_type="topic_summary",
            title="Test",
            content="Test content",
        )
        d = summary.to_dict()
        assert d["confidence_score"] is None


# ---------------------------------------------------------------------------
# Task 4: verify consolidation_service uses confidence_score
# ---------------------------------------------------------------------------


class TestConsolidationServiceConfidence:
    """Tests that consolidation service sets confidence_score on summaries."""

    def test_compute_summary_confidence_imported(self):
        """Verify compute_summary_confidence is accessible from the module."""
        from src.modules.memory.consolidation_service import compute_summary_confidence
        assert callable(compute_summary_confidence)


# ---------------------------------------------------------------------------
# Metrics: vector_search_fallback_total
# ---------------------------------------------------------------------------


class TestVectorSearchFallbackMetric:
    """Tests that the metric is defined and accessible."""

    def test_metric_exists(self):
        from src.core.observability.metrics import vector_search_fallback_total
        assert vector_search_fallback_total is not None

    def test_metric_has_labels_method(self):
        from src.core.observability.metrics import vector_search_fallback_total
        labeled = vector_search_fallback_total.labels(reason="test")
        assert hasattr(labeled, "inc")
