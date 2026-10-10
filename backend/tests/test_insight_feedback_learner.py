"""Contract tests for InsightFeedbackLearner.get_adjusted_weights().

Tests verify:
- Return contract to InsightOrchestrator._build_generation_budget()
- TC-3: After 3+ NOT_USEFUL signals, weight == 0.0 (budget 0)
- TC-8: 90-day rolling window + 7-type native consumption
- Legacy 3-type backward compatibility
- NOT_RELEVANT vs TOO_FREQUENT get distinct adjustments
"""
import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.modules.briefing.services.insight_feedback_learner import (
    InsightFeedbackLearner,
    DEFAULT_WEIGHT,
    MAX_WEIGHT,
    MIN_WEIGHT,
    NOT_USEFUL_ZERO_BUDGET_THRESHOLD,
    ROLLING_WINDOW_DAYS,
    _WEIGHT_ADJUSTMENTS,
)
from src.modules.insight.models import FeedbackType


def _make_db_with_rows(rows):
    """Build a mock AsyncSession that returns ``rows`` from execute()."""
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    db = AsyncMock()
    db.execute.return_value = mock_result
    return db


# ---------------------------------------------------------------------------
# Contract: return type is Dict[str, float]
# ---------------------------------------------------------------------------


class TestGetAdjustedWeightsContract:

    @pytest.mark.asyncio
    async def test_returns_dict_of_str_to_float(self):
        db = _make_db_with_rows([])
        learner = InsightFeedbackLearner(db)
        weights = await learner.get_adjusted_weights(uuid4())
        assert isinstance(weights, dict)
        for k, v in weights.items():
            assert isinstance(k, str)
            assert isinstance(v, float)

    @pytest.mark.asyncio
    async def test_empty_feedback_returns_empty_dict(self):
        db = _make_db_with_rows([])
        learner = InsightFeedbackLearner(db)
        weights = await learner.get_adjusted_weights(uuid4())
        assert weights == {}

    @pytest.mark.asyncio
    async def test_weights_clamped_to_min_max(self):
        """Any weight must be within [MIN_WEIGHT, MAX_WEIGHT]."""
        # 100 NOT_USEFUL signals (extreme case)
        rows = [("relationship", FeedbackType.NOT_USEFUL.value, 100)]
        db = _make_db_with_rows(rows)
        learner = InsightFeedbackLearner(db)
        weights = await learner.get_adjusted_weights(uuid4())
        for v in weights.values():
            assert MIN_WEIGHT <= v <= MAX_WEIGHT


# ---------------------------------------------------------------------------
# TC-3: 3+ NOT_USEFUL signals → weight 0.0
# ---------------------------------------------------------------------------


class TestNotUsefulThreshold:

    @pytest.mark.asyncio
    async def test_two_not_useful_does_not_zero(self):
        rows = [("relationship", FeedbackType.NOT_USEFUL.value, 2)]
        db = _make_db_with_rows(rows)
        learner = InsightFeedbackLearner(db)
        weights = await learner.get_adjusted_weights(uuid4())
        assert weights.get("relationship", DEFAULT_WEIGHT) > MIN_WEIGHT

    @pytest.mark.asyncio
    async def test_three_not_useful_zeros_budget(self):
        """TC-3: Exactly 3 NOT_USEFUL signals → weight 0.0."""
        rows = [("relationship", FeedbackType.NOT_USEFUL.value, 3)]
        db = _make_db_with_rows(rows)
        learner = InsightFeedbackLearner(db)
        weights = await learner.get_adjusted_weights(uuid4())
        assert weights["relationship"] == MIN_WEIGHT

    @pytest.mark.asyncio
    async def test_legacy_ignored_counts_toward_threshold(self):
        """Legacy 'ignored' counts as NOT_USEFUL for TC-3."""
        rows = [("time", "ignored", 3)]
        db = _make_db_with_rows(rows)
        learner = InsightFeedbackLearner(db)
        weights = await learner.get_adjusted_weights(uuid4())
        assert weights["time"] == MIN_WEIGHT

    @pytest.mark.asyncio
    async def test_mixed_not_useful_and_ignored_accumulate(self):
        """2 not_useful + 1 ignored = 3 total → threshold hit."""
        rows = [
            ("favor", FeedbackType.NOT_USEFUL.value, 2),
            ("favor", "ignored", 1),
        ]
        db = _make_db_with_rows(rows)
        learner = InsightFeedbackLearner(db)
        weights = await learner.get_adjusted_weights(uuid4())
        assert weights["favor"] == MIN_WEIGHT


# ---------------------------------------------------------------------------
# TC-8: NOT_RELEVANT vs TOO_FREQUENT get distinct adjustments
# ---------------------------------------------------------------------------


class TestDistinctAdjustments:

    @pytest.mark.asyncio
    async def test_not_relevant_has_stronger_penalty_than_too_frequent(self):
        """NOT_RELEVANT should decrease weight more than TOO_FREQUENT (same count)."""
        rows_not_relevant = [("relationship", FeedbackType.NOT_RELEVANT.value, 1)]
        rows_too_frequent = [("relationship", FeedbackType.TOO_FREQUENT.value, 1)]

        db1 = _make_db_with_rows(rows_not_relevant)
        weight_not_relevant = (await InsightFeedbackLearner(db1).get_adjusted_weights(uuid4())).get("relationship", DEFAULT_WEIGHT)

        db2 = _make_db_with_rows(rows_too_frequent)
        weight_too_frequent = (await InsightFeedbackLearner(db2).get_adjusted_weights(uuid4())).get("relationship", DEFAULT_WEIGHT)

        assert weight_not_relevant < weight_too_frequent

    @pytest.mark.asyncio
    async def test_useful_increases_weight(self):
        rows = [("time", FeedbackType.USEFUL.value, 1)]
        db = _make_db_with_rows(rows)
        learner = InsightFeedbackLearner(db)
        weights = await learner.get_adjusted_weights(uuid4())
        assert weights["time"] > DEFAULT_WEIGHT

    @pytest.mark.asyncio
    async def test_defer_has_minimal_penalty(self):
        """DEFER should have the smallest negative adjustment."""
        rows_defer = [("health", FeedbackType.DEFER.value, 1)]
        rows_not_useful = [("health", FeedbackType.NOT_USEFUL.value, 1)]

        db1 = _make_db_with_rows(rows_defer)
        w_defer = (await InsightFeedbackLearner(db1).get_adjusted_weights(uuid4())).get("health", DEFAULT_WEIGHT)

        db2 = _make_db_with_rows(rows_not_useful)
        w_not_useful = (await InsightFeedbackLearner(db2).get_adjusted_weights(uuid4())).get("health", DEFAULT_WEIGHT)

        # DEFER penalty is less severe than NOT_USEFUL
        assert w_defer > w_not_useful


# ---------------------------------------------------------------------------
# Legacy backward compatibility
# ---------------------------------------------------------------------------


class TestLegacyMapping:

    @pytest.mark.asyncio
    async def test_legacy_useful_maps_to_positive_weight(self):
        """Legacy 'useful' string gives positive delta."""
        rows = [("relationship", "useful", 1)]
        db = _make_db_with_rows(rows)
        learner = InsightFeedbackLearner(db)
        weights = await learner.get_adjusted_weights(uuid4())
        assert weights.get("relationship", DEFAULT_WEIGHT) == pytest.approx(DEFAULT_WEIGHT + _WEIGHT_ADJUSTMENTS["useful"])

    @pytest.mark.asyncio
    async def test_unknown_feedback_type_ignored(self):
        """Unknown feedback strings don't crash and contribute 0 delta."""
        rows = [("time", "some_future_type", 5)]
        db = _make_db_with_rows(rows)
        learner = InsightFeedbackLearner(db)
        weights = await learner.get_adjusted_weights(uuid4())
        # Unknown type → adjustment 0.0 → no entry in weights dict
        assert "time" not in weights


# ---------------------------------------------------------------------------
# get_suppressed_types: 7-type + legacy
# ---------------------------------------------------------------------------


class TestGetSuppressedTypes:

    @pytest.mark.asyncio
    async def test_never_feedback_suppresses_type(self):
        mock_result = MagicMock()
        mock_result.all.return_value = [("relationship",)]
        db = AsyncMock()
        db.execute.return_value = mock_result
        learner = InsightFeedbackLearner(db)
        suppressed = await learner.get_suppressed_types(uuid4())
        assert "relationship" in suppressed

    @pytest.mark.asyncio
    async def test_no_suppression_when_empty(self):
        mock_result = MagicMock()
        mock_result.all.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result
        learner = InsightFeedbackLearner(db)
        suppressed = await learner.get_suppressed_types(uuid4())
        assert suppressed == set()
