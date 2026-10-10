"""Tests for core/feedback/aggregator.py -- cross-module feedback aggregation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.core.feedback.aggregator import (
    DEFAULT_SCORE,
    MAX_SCORE,
    MIN_SCORE,
    FeedbackAggregator,
    _INSIGHT_FEEDBACK_SCORES,
    _SOURCE_WEIGHT_CURATION,
    _SOURCE_WEIGHT_INSIGHT,
    _SOURCE_WEIGHT_MEMORY,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_db():
    """Create a mock AsyncSession."""
    db = AsyncMock()
    return db


def _make_mock_result(rows):
    """Create a mock result set that returns rows."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows
    mock_result.scalar_one_or_none.return_value = None
    mock_result.all.return_value = rows
    mock_result.one_or_none.return_value = None
    return mock_result


# ---------------------------------------------------------------------------
# Unit tests: _compute_insight_score
# ---------------------------------------------------------------------------


class TestComputeInsightScore:
    """Test static insight score computation."""

    def test_empty_feedback(self):
        score = FeedbackAggregator._compute_insight_score([])
        assert score == DEFAULT_SCORE

    def test_single_useful(self):
        score = FeedbackAggregator._compute_insight_score(["useful"])
        assert score == _INSIGHT_FEEDBACK_SCORES["useful"]

    def test_single_not_useful(self):
        score = FeedbackAggregator._compute_insight_score(["not_useful"])
        assert score == _INSIGHT_FEEDBACK_SCORES["not_useful"]

    def test_mixed_feedback_averages(self):
        types = ["useful", "not_useful"]
        expected = (
            _INSIGHT_FEEDBACK_SCORES["useful"]
            + _INSIGHT_FEEDBACK_SCORES["not_useful"]
        ) / 2
        score = FeedbackAggregator._compute_insight_score(types)
        assert abs(score - expected) < 0.001

    def test_unknown_type_defaults_to_1(self):
        score = FeedbackAggregator._compute_insight_score(["unknown_type"])
        assert score == DEFAULT_SCORE

    def test_all_incorrect_gives_low_score(self):
        score = FeedbackAggregator._compute_insight_score(
            ["incorrect", "incorrect", "incorrect"]
        )
        assert abs(score - _INSIGHT_FEEDBACK_SCORES["incorrect"]) < 0.001


# ---------------------------------------------------------------------------
# Unit tests: _compute_curation_score
# ---------------------------------------------------------------------------


class TestComputeCurationScore:
    """Test static curation score computation."""

    def test_zero_total(self):
        score = FeedbackAggregator._compute_curation_score(0, 0, 0)
        assert score == DEFAULT_SCORE

    def test_all_confirmed(self):
        score = FeedbackAggregator._compute_curation_score(5, 0, 5)
        assert score == MAX_SCORE

    def test_all_dismissed(self):
        score = FeedbackAggregator._compute_curation_score(0, 5, 5)
        assert score == MIN_SCORE

    def test_balanced(self):
        score = FeedbackAggregator._compute_curation_score(2, 2, 4)
        # net = 0, maps to midpoint = 0.1 + (0+1)/2 * 1.9 = 0.1 + 0.95 = 1.05
        expected = MIN_SCORE + (0 + 1.0) / 2.0 * (MAX_SCORE - MIN_SCORE)
        assert abs(score - expected) < 0.001

    def test_more_confirms_than_dismisses(self):
        score = FeedbackAggregator._compute_curation_score(3, 1, 4)
        assert score > DEFAULT_SCORE

    def test_more_dismisses_than_confirms(self):
        score = FeedbackAggregator._compute_curation_score(1, 3, 4)
        assert score < DEFAULT_SCORE

    def test_no_interaction_but_total(self):
        """Items exist but neither confirmed nor dismissed."""
        score = FeedbackAggregator._compute_curation_score(0, 0, 3)
        expected = MIN_SCORE + (0 + 1.0) / 2.0 * (MAX_SCORE - MIN_SCORE)
        assert abs(score - expected) < 0.001


# ---------------------------------------------------------------------------
# Integration-style tests: get_entity_feedback_score
# ---------------------------------------------------------------------------


class TestGetEntityFeedbackScore:
    """Test the main aggregation method with mocked DB queries."""

    @pytest.mark.asyncio
    async def test_no_feedback_returns_default(self):
        db = _make_mock_db()
        # All queries return empty
        mock_result = _make_mock_result([])
        db.execute.return_value = mock_result

        aggregator = FeedbackAggregator(db)
        score = await aggregator.get_entity_feedback_score(
            entity_id=uuid4(), family_id=uuid4(),
        )
        assert score == DEFAULT_SCORE

    @pytest.mark.asyncio
    async def test_score_within_bounds(self):
        db = _make_mock_db()
        mock_result = _make_mock_result([])
        db.execute.return_value = mock_result

        aggregator = FeedbackAggregator(db)
        score = await aggregator.get_entity_feedback_score(
            entity_id=uuid4(), family_id=uuid4(),
        )
        assert MIN_SCORE <= score <= MAX_SCORE

    @pytest.mark.asyncio
    async def test_handles_import_error_gracefully(self):
        """If a module cannot be imported, aggregator returns default."""
        db = _make_mock_db()
        mock_result = _make_mock_result([])
        db.execute.return_value = mock_result

        aggregator = FeedbackAggregator(db)

        with patch.dict("sys.modules", {"src.modules.insight.models": None}):
            score = await aggregator.get_entity_feedback_score(
                entity_id=uuid4(), family_id=uuid4(),
            )
        # Should not crash, returns default
        assert MIN_SCORE <= score <= MAX_SCORE

    @pytest.mark.asyncio
    async def test_handles_db_error_gracefully(self):
        """DB errors don't crash, sources are skipped."""
        db = _make_mock_db()
        db.execute.side_effect = Exception("DB connection failed")

        aggregator = FeedbackAggregator(db)
        score = await aggregator.get_entity_feedback_score(
            entity_id=uuid4(), family_id=uuid4(),
        )
        assert score == DEFAULT_SCORE


# ---------------------------------------------------------------------------
# Bulk feedback scores
# ---------------------------------------------------------------------------


class TestGetBulkFeedbackScores:
    """Test bulk score retrieval."""

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty(self):
        db = _make_mock_db()
        aggregator = FeedbackAggregator(db)
        result = await aggregator.get_bulk_feedback_scores(
            entity_ids=[], family_id=uuid4(),
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_all_defaults_when_no_feedback(self):
        db = _make_mock_db()
        mock_result = _make_mock_result([])
        db.execute.return_value = mock_result

        ids = [uuid4(), uuid4()]
        aggregator = FeedbackAggregator(db)
        result = await aggregator.get_bulk_feedback_scores(
            entity_ids=ids, family_id=uuid4(),
        )
        for eid in ids:
            assert result[str(eid)] == DEFAULT_SCORE

    @pytest.mark.asyncio
    async def test_handles_db_error_gracefully(self):
        db = _make_mock_db()
        db.execute.side_effect = Exception("DB error")

        ids = [uuid4()]
        aggregator = FeedbackAggregator(db)
        result = await aggregator.get_bulk_feedback_scores(
            entity_ids=ids, family_id=uuid4(),
        )
        # All fallback to default
        for eid in ids:
            assert result[str(eid)] == DEFAULT_SCORE


# ---------------------------------------------------------------------------
# Score bounds validation
# ---------------------------------------------------------------------------


class TestScoreBounds:
    """Ensure scores are always clamped within [MIN_SCORE, MAX_SCORE]."""

    def test_min_greater_than_zero(self):
        assert MIN_SCORE > 0

    def test_max_is_two(self):
        assert MAX_SCORE == 2.0

    def test_default_is_one(self):
        assert DEFAULT_SCORE == 1.0

    def test_weights_sum_to_one(self):
        total = _SOURCE_WEIGHT_INSIGHT + _SOURCE_WEIGHT_CURATION + _SOURCE_WEIGHT_MEMORY
        assert abs(total - 1.0) < 0.001
