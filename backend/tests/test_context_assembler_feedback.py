"""Tests for ContextAssembler Step 3.5 feedback weight enrichment."""

import dataclasses
from uuid import uuid4

import pytest

from src.ai_engine.context_assembler import (
    ContextAssembler,
    ContextItem,
    TokenBudget,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    layer: str = "l4",
    content: str = "test memory",
    feedback_weight: float = 1.0,
    memory_id: str = None,
    entity_ids: tuple = (),
) -> ContextItem:
    metadata = {}
    if memory_id:
        metadata["memory_id"] = memory_id
    return ContextItem(
        layer=layer,
        source="memory",
        content=content,
        tokens=10,
        importance=5.0,
        feedback_weight=feedback_weight,
        recency_days=1.0,
        entity_ids=entity_ids,
        metadata=metadata,
    )


class _MockFeedbackAggregator:
    """Mock aggregator that returns predefined scores."""

    def __init__(self, scores=None):
        self._scores = scores or {}

    async def get_bulk_feedback_scores(self, entity_ids, family_id):
        return {str(eid): self._scores.get(str(eid), 1.0) for eid in entity_ids}


class _FailingAggregator:
    """Aggregator that always raises."""

    async def get_bulk_feedback_scores(self, entity_ids, family_id):
        raise Exception("DB connection failed")


# ---------------------------------------------------------------------------
# Tests: _enrich_feedback_weights
# ---------------------------------------------------------------------------


class TestEnrichFeedbackWeights:
    """Test Step 3.5 feedback enrichment."""

    @pytest.mark.asyncio
    async def test_no_aggregator_returns_unchanged(self):
        assembler = ContextAssembler()
        items = [_make_item()]
        result = await assembler._enrich_feedback_weights(items, uuid4())
        assert result == items

    @pytest.mark.asyncio
    async def test_enriches_l4_items_with_memory_id(self):
        mem_id = uuid4()
        scores = {str(mem_id): 1.8}
        aggregator = _MockFeedbackAggregator(scores)
        assembler = ContextAssembler(feedback_aggregator=aggregator)

        items = [_make_item(memory_id=str(mem_id))]
        result = await assembler._enrich_feedback_weights(items, uuid4())

        assert len(result) == 1
        assert result[0].feedback_weight == 1.8

    @pytest.mark.asyncio
    async def test_enriches_via_entity_ids(self):
        mem_id = uuid4()
        scores = {str(mem_id): 0.5}
        aggregator = _MockFeedbackAggregator(scores)
        assembler = ContextAssembler(feedback_aggregator=aggregator)

        items = [_make_item(entity_ids=(str(mem_id),))]
        result = await assembler._enrich_feedback_weights(items, uuid4())

        assert result[0].feedback_weight == 0.5

    @pytest.mark.asyncio
    async def test_l1_l2_items_unchanged(self):
        mem_id = uuid4()
        scores = {str(mem_id): 0.2}
        aggregator = _MockFeedbackAggregator(scores)
        assembler = ContextAssembler(feedback_aggregator=aggregator)

        items = [
            _make_item(layer="l1", memory_id=str(mem_id)),
            _make_item(layer="l2", memory_id=str(mem_id)),
        ]
        result = await assembler._enrich_feedback_weights(items, uuid4())

        # L1/L2 should retain original weight
        assert result[0].feedback_weight == 1.0
        assert result[1].feedback_weight == 1.0

    @pytest.mark.asyncio
    async def test_items_without_entity_ids_unchanged(self):
        aggregator = _MockFeedbackAggregator({})
        assembler = ContextAssembler(feedback_aggregator=aggregator)

        items = [_make_item(layer="l3")]
        result = await assembler._enrich_feedback_weights(items, uuid4())

        assert result[0].feedback_weight == 1.0

    @pytest.mark.asyncio
    async def test_aggregator_failure_returns_unchanged(self):
        aggregator = _FailingAggregator()
        assembler = ContextAssembler(feedback_aggregator=aggregator)

        mem_id = uuid4()
        items = [_make_item(memory_id=str(mem_id))]
        result = await assembler._enrich_feedback_weights(items, uuid4())

        # Should fallback gracefully
        assert result[0].feedback_weight == 1.0

    @pytest.mark.asyncio
    async def test_multiple_items_mixed_enrichment(self):
        mem1 = uuid4()
        mem2 = uuid4()
        mem3 = uuid4()
        scores = {str(mem1): 1.5, str(mem2): 0.3}
        aggregator = _MockFeedbackAggregator(scores)
        assembler = ContextAssembler(feedback_aggregator=aggregator)

        items = [
            _make_item(layer="l1", memory_id=str(mem1)),  # L1, untouched
            _make_item(layer="l4", memory_id=str(mem1)),  # enriched to 1.5
            _make_item(layer="l4", memory_id=str(mem2)),  # enriched to 0.3
            _make_item(layer="l3", memory_id=str(mem3)),  # no score, stays 1.0
        ]
        result = await assembler._enrich_feedback_weights(items, uuid4())

        assert result[0].feedback_weight == 1.0  # L1
        assert result[1].feedback_weight == 1.5
        assert result[2].feedback_weight == 0.3
        assert result[3].feedback_weight == 1.0  # default

    @pytest.mark.asyncio
    async def test_enrichment_affects_rank_score(self):
        """Verify that enriched feedback_weight changes rank_score."""
        mem_id = uuid4()
        scores = {str(mem_id): 2.0}
        aggregator = _MockFeedbackAggregator(scores)
        assembler = ContextAssembler(feedback_aggregator=aggregator)

        item = _make_item(layer="l4", memory_id=str(mem_id))
        original_rank = item.rank_score

        result = await assembler._enrich_feedback_weights([item], uuid4())
        enriched_rank = result[0].rank_score

        assert enriched_rank > original_rank
        assert enriched_rank == result[0].importance * 2.0 * max(0.1, 1.0 - result[0].recency_days / 90.0)


# ---------------------------------------------------------------------------
# Tests: Full pipeline with feedback aggregator
# ---------------------------------------------------------------------------


class TestAssemblerPipelineWithFeedback:
    """Test that the full assemble() pipeline uses feedback enrichment."""

    @pytest.mark.asyncio
    async def test_pipeline_with_aggregator(self):
        mem_id = uuid4()
        user_id = uuid4()
        family_id = uuid4()

        scores = {str(mem_id): 0.5}
        aggregator = _MockFeedbackAggregator(scores)

        async def mock_l4_fetcher(uid, msg):
            return [_make_item(layer="l4", memory_id=str(mem_id))]

        assembler = ContextAssembler(
            budget=TokenBudget(total=5000, l1_fixed=500, l2_fixed=1500, l5_fixed=500,
                               l3_min=300, l3_max=1000, l4_min=300, l4_max=1500),
            l4_fetcher=mock_l4_fetcher,
            feedback_aggregator=aggregator,
        )

        prompt, metadata = await assembler.assemble(
            user_id=user_id,
            family_id=family_id,
            session_id="test-session",
            user_message="test",
        )

        # The assembler ran without error and produced output
        assert isinstance(prompt, str)
        assert metadata.total_tokens_used > 0

    @pytest.mark.asyncio
    async def test_pipeline_without_aggregator(self):
        """Pipeline works fine with no aggregator (backward compat)."""
        user_id = uuid4()
        family_id = uuid4()

        async def mock_l4_fetcher(uid, msg):
            return [_make_item(layer="l4")]

        assembler = ContextAssembler(
            budget=TokenBudget(total=5000, l1_fixed=500, l2_fixed=1500, l5_fixed=500,
                               l3_min=300, l3_max=1000, l4_min=300, l4_max=1500),
            l4_fetcher=mock_l4_fetcher,
        )

        prompt, metadata = await assembler.assemble(
            user_id=user_id,
            family_id=family_id,
            session_id="test-session",
            user_message="test",
        )

        assert isinstance(prompt, str)
