"""Tests for aggregate_dismissed_entities() cross-module feedback aggregation.

Covers:
- Aggregation from insight_feedbacks (dismiss-like types)
- Aggregation from low feedback_weight memories
- Entity extraction from JSONB entities column
- Graceful failure on DB errors
- Empty results when no dismissed data
- Deduplication across sources
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from src.ai_engine.context_fetchers import (
    aggregate_dismissed_entities,
    _FEEDBACK_WEIGHT_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(*vals):
    """Create a mock DB row tuple."""
    return vals


class _FakeResult:
    """Mimics SQLAlchemy async result with fetchall() and all()."""

    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def all(self):
        return self._rows


class _FakeSession:
    """Minimal async session mock that returns scripted results per query."""

    def __init__(self, results_sequence):
        self._results = list(results_sequence)
        self._call_idx = 0

    async def execute(self, stmt):
        if self._call_idx < len(self._results):
            result = self._results[self._call_idx]
            self._call_idx += 1
            return result
        return _FakeResult([])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAggregateDismissedEntities:

    @pytest.mark.asyncio
    async def test_empty_when_no_feedback_or_low_weight(self):
        """Returns empty set when no dismiss feedbacks and no low-weight memories."""
        empty_result = _FakeResult([])
        session = _FakeSession([empty_result, empty_result])

        with patch("src.ai_engine.context_fetchers.get_db_session", return_value=session):
            result = await aggregate_dismissed_entities(
                user_id=uuid4(), family_id=uuid4(),
            )
        assert result == set()

    @pytest.mark.asyncio
    async def test_extracts_entities_from_dismissed_feedback_memories(self):
        """Entities from memories linked to dismiss feedbacks are collected."""
        user_id = uuid4()
        family_id = uuid4()
        mem_id_1 = uuid4()
        mem_id_2 = uuid4()

        # Query 1: insight_feedbacks → returns source_memory_ids
        fb_result = _FakeResult([
            _make_row(mem_id_1),
            _make_row(mem_id_2),
        ])
        # Query 2: conversation_memories entities for dismissed memory ids
        mem_result = _FakeResult([
            _make_row({"person": "entity-abc", "location": "entity-xyz"}),
            _make_row({"tags": ["tag-1", "tag-2"]}),
        ])
        # Query 3: memory_insights related_member_ids for dismissed memories
        insight_result = _FakeResult([
            _make_row([uuid4()]),
        ])
        # Query 4: low feedback_weight memories
        low_weight_result = _FakeResult([])

        session = _FakeSession([fb_result, mem_result, insight_result, low_weight_result])

        with patch("src.ai_engine.context_fetchers.get_db_session", return_value=session):
            result = await aggregate_dismissed_entities(
                user_id=user_id, family_id=family_id,
            )

        assert "entity-abc" in result
        assert "entity-xyz" in result
        assert "tag-1" in result
        assert "tag-2" in result

    @pytest.mark.asyncio
    async def test_extracts_entities_from_low_weight_memories(self):
        """Entities from memories with low feedback_weight are collected."""
        user_id = uuid4()
        family_id = uuid4()

        # Query 1: no dismiss feedbacks
        fb_result = _FakeResult([])
        # Query 2: dismissed insight entity IDs (runs unconditionally)
        dismissed_insight_result = _FakeResult([])
        # Query 3: low feedback_weight memories
        low_weight_result = _FakeResult([
            _make_row({"member_id": "mem-123", "event": "evt-456"}),
            _make_row({"items": ["item-a", "item-b"]}),
        ])

        session = _FakeSession([fb_result, dismissed_insight_result, low_weight_result])

        with patch("src.ai_engine.context_fetchers.get_db_session", return_value=session):
            result = await aggregate_dismissed_entities(
                user_id=user_id, family_id=family_id,
            )

        assert "mem-123" in result
        assert "evt-456" in result
        assert "item-a" in result
        assert "item-b" in result

    @pytest.mark.asyncio
    async def test_deduplicates_across_sources(self):
        """Same entity ID from both sources appears only once."""
        user_id = uuid4()
        family_id = uuid4()
        mem_id = uuid4()

        # Query 1: feedbacks
        fb_result = _FakeResult([_make_row(mem_id)])
        # Query 2: entities from dismissed memories
        mem_result = _FakeResult([_make_row({"shared": "shared-entity"})])
        # Query 3: no insight member ids
        insight_result = _FakeResult([])
        # Query 4: low-weight also has the same entity
        low_weight_result = _FakeResult([_make_row({"shared": "shared-entity"})])

        session = _FakeSession([fb_result, mem_result, insight_result, low_weight_result])

        with patch("src.ai_engine.context_fetchers.get_db_session", return_value=session):
            result = await aggregate_dismissed_entities(
                user_id=user_id, family_id=family_id,
            )

        assert "shared-entity" in result
        # Ensure it's a set (no duplicates by definition)
        assert isinstance(result, set)

    @pytest.mark.asyncio
    async def test_graceful_failure_returns_empty_set(self):
        """DB errors are caught; empty set returned."""
        async def _failing_session():
            raise RuntimeError("DB unavailable")

        # Simulate get_db_session raising
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB unavailable"))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.ai_engine.context_fetchers.get_db_session", return_value=mock_ctx):
            result = await aggregate_dismissed_entities(
                user_id=uuid4(), family_id=uuid4(),
            )

        assert result == set()

    @pytest.mark.asyncio
    async def test_handles_none_entities_gracefully(self):
        """Memories with None entities column are skipped."""
        user_id = uuid4()
        family_id = uuid4()

        # No feedbacks
        fb_result = _FakeResult([])
        # Dismissed insight entity IDs (runs unconditionally)
        dismissed_insight_result = _FakeResult([])
        # Low-weight memories with None entities
        low_weight_result = _FakeResult([
            _make_row(None),
            _make_row({}),
        ])

        session = _FakeSession([fb_result, dismissed_insight_result, low_weight_result])

        with patch("src.ai_engine.context_fetchers.get_db_session", return_value=session):
            result = await aggregate_dismissed_entities(
                user_id=user_id, family_id=family_id,
            )

        assert result == set()

    @pytest.mark.asyncio
    async def test_handles_integer_entity_values(self):
        """Integer entity values are converted to strings."""
        user_id = uuid4()
        family_id = uuid4()

        fb_result = _FakeResult([])
        # Dismissed insight entity IDs (runs unconditionally)
        dismissed_insight_result = _FakeResult([])
        low_weight_result = _FakeResult([
            _make_row({"count": 42, "code": "abc"}),
        ])

        session = _FakeSession([fb_result, dismissed_insight_result, low_weight_result])

        with patch("src.ai_engine.context_fetchers.get_db_session", return_value=session):
            result = await aggregate_dismissed_entities(
                user_id=user_id, family_id=family_id,
            )

        assert "42" in result
        assert "abc" in result

    def test_feedback_weight_threshold_is_reasonable(self):
        """Threshold constant is 0.3 as specified."""
        assert _FEEDBACK_WEIGHT_THRESHOLD == 0.3


# ---------------------------------------------------------------------------
# Integration: assemble() forwards dismissed_entity_ids
# ---------------------------------------------------------------------------


class TestAssemblerDismissedEntitiesParam:
    """Verify ContextAssembler.assemble() passes dismissed_entity_ids to _apply_filters."""

    @pytest.mark.asyncio
    async def test_assemble_passes_dismissed_ids_to_filters(self):
        """assemble(dismissed_entity_ids=...) forwards to _apply_filters."""
        from src.ai_engine.context_assembler import ContextAssembler

        # Minimal fetchers that return empty
        async def empty_l1(uid, fid):
            return []

        async def empty_l2(uid, sid):
            return []

        async def empty_l3(uid, fid, rids):
            return []

        async def empty_l4(uid, msg):
            return []

        assembler = ContextAssembler(
            l1_fetcher=empty_l1,
            l2_fetcher=empty_l2,
            l3_fetcher=empty_l3,
            l4_fetcher=empty_l4,
        )

        dismissed = {"entity-1", "entity-2"}
        captured_args = {}

        original_apply_filters = assembler._apply_filters

        @staticmethod
        def mock_apply_filters(items, viewer_user_id, viewer_family_id, resolved_ids, dismissed_entity_ids=None, privacy_settings=None):
            captured_args["dismissed_entity_ids"] = dismissed_entity_ids
            return items, 0

        async def _no_cache(*a, **kw):
            return None

        async def _noop_cache_set(*a, **kw):
            pass

        mock_histogram = MagicMock()
        mock_histogram.observe = MagicMock()

        with patch.object(assembler, "_cache_get", side_effect=_no_cache), \
             patch.object(assembler, "_cache_set", side_effect=_noop_cache_set), \
             patch.object(type(assembler), "_apply_filters", mock_apply_filters), \
             patch("src.core.observability.metrics.context_cache_ops", MagicMock()), \
             patch("src.core.observability.metrics.context_assembly_seconds", mock_histogram):
                await assembler.assemble(
                    user_id=uuid4(),
                    family_id=uuid4(),
                    session_id="test-session",
                    user_message="hello",
                    dismissed_entity_ids=dismissed,
                )

        assert captured_args.get("dismissed_entity_ids") == dismissed

    @pytest.mark.asyncio
    async def test_assemble_without_dismissed_ids_passes_none(self):
        """assemble() without dismissed_entity_ids passes None to _apply_filters."""
        from src.ai_engine.context_assembler import ContextAssembler

        async def empty_l1(uid, fid):
            return []

        async def empty_l2(uid, sid):
            return []

        async def empty_l3(uid, fid, rids):
            return []

        async def empty_l4(uid, msg):
            return []

        assembler = ContextAssembler(
            l1_fetcher=empty_l1,
            l2_fetcher=empty_l2,
            l3_fetcher=empty_l3,
            l4_fetcher=empty_l4,
        )

        captured_args = {}

        @staticmethod
        def mock_apply_filters(items, viewer_user_id, viewer_family_id, resolved_ids, dismissed_entity_ids=None, privacy_settings=None):
            captured_args["dismissed_entity_ids"] = dismissed_entity_ids
            return items, 0

        async def _no_cache(*a, **kw):
            return None

        async def _noop_cache_set(*a, **kw):
            pass

        mock_histogram = MagicMock()
        mock_histogram.observe = MagicMock()

        with patch.object(assembler, "_cache_get", side_effect=_no_cache), \
             patch.object(assembler, "_cache_set", side_effect=_noop_cache_set), \
             patch.object(type(assembler), "_apply_filters", mock_apply_filters), \
             patch("src.core.observability.metrics.context_cache_ops", MagicMock()), \
             patch("src.core.observability.metrics.context_assembly_seconds", mock_histogram):
                await assembler.assemble(
                    user_id=uuid4(),
                    family_id=uuid4(),
                    session_id="test-session",
                    user_message="hello",
                )

        assert captured_args.get("dismissed_entity_ids") is None
