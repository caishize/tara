"""Tests for PreferenceLearner -- signal consolidation into FamilyPreference rules."""

import math

import pytest

from src.modules.curation.services.preference_learner import (
    PreferenceLearner,
    _aggregate_signals,
    _compute_confidence,
    _decay_weight,
    _DimensionResult,
    _HALF_LIFE_DAYS,
    _MIN_SIGNAL_COUNT,
    _RATIO_THRESHOLD,
    _DEACTIVATION_THRESHOLD,
    _WeightedSignal,
)


# ---------------------------------------------------------------------------
# _decay_weight
# ---------------------------------------------------------------------------

class TestDecayWeight:

    def test_age_zero_returns_1(self):
        assert _decay_weight(0) == pytest.approx(1.0)

    def test_age_half_life_returns_0_5(self):
        assert _decay_weight(_HALF_LIFE_DAYS) == pytest.approx(0.5, abs=0.001)

    def test_age_60_returns_0_25(self):
        # Two half-lives: 0.5^2 = 0.25
        assert _decay_weight(60) == pytest.approx(0.25, abs=0.01)

    def test_age_90_returns_0_125(self):
        # Three half-lives: 0.5^3 = 0.125
        assert _decay_weight(90) == pytest.approx(0.125, abs=0.01)

    def test_always_positive(self):
        assert _decay_weight(365) > 0

    def test_monotonically_decreasing(self):
        w_10 = _decay_weight(10)
        w_30 = _decay_weight(30)
        w_60 = _decay_weight(60)
        assert w_10 > w_30 > w_60


# ---------------------------------------------------------------------------
# _aggregate_signals
# ---------------------------------------------------------------------------

class TestAggregateSignals:

    def test_all_positive(self):
        signals = [
            _WeightedSignal(is_positive=True, weight=1.0),
            _WeightedSignal(is_positive=True, weight=0.5),
        ]
        pos, neg, count = _aggregate_signals(signals)
        assert pos == pytest.approx(1.5)
        assert neg == pytest.approx(0.0)
        assert count == 2

    def test_all_negative(self):
        signals = [
            _WeightedSignal(is_positive=False, weight=0.8),
            _WeightedSignal(is_positive=False, weight=0.3),
        ]
        pos, neg, count = _aggregate_signals(signals)
        assert pos == pytest.approx(0.0)
        assert neg == pytest.approx(1.1)
        assert count == 2

    def test_mixed_signals(self):
        signals = [
            _WeightedSignal(is_positive=True, weight=1.0),
            _WeightedSignal(is_positive=False, weight=0.5),
            _WeightedSignal(is_positive=True, weight=0.3),
        ]
        pos, neg, count = _aggregate_signals(signals)
        assert pos == pytest.approx(1.3)
        assert neg == pytest.approx(0.5)
        assert count == 3

    def test_empty_signals(self):
        pos, neg, count = _aggregate_signals([])
        assert pos == 0.0
        assert neg == 0.0
        assert count == 0


# ---------------------------------------------------------------------------
# _compute_confidence
# ---------------------------------------------------------------------------

class TestComputeConfidence:

    def test_all_positive(self):
        assert _compute_confidence(5.0, 0.0) == pytest.approx(1.0)

    def test_all_negative(self):
        assert _compute_confidence(0.0, 3.0) == pytest.approx(1.0)

    def test_equal_signals(self):
        assert _compute_confidence(2.0, 2.0) == pytest.approx(0.5)

    def test_mostly_positive(self):
        # 7 / (7+3) = 0.7
        assert _compute_confidence(7.0, 3.0) == pytest.approx(0.7)

    def test_zero_total(self):
        assert _compute_confidence(0.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# _derive_weight_updates
# ---------------------------------------------------------------------------

class TestDeriveWeightUpdates:

    def test_signal_count_below_minimum_skipped(self):
        results = [
            _DimensionResult(
                key="follow_up",
                positive_weight=2.0,
                negative_weight=0.0,
                signal_count=2,  # < 3
                confidence=1.0,
            ),
        ]
        updates = PreferenceLearner._derive_weight_updates(results)
        assert "follow_up" not in updates

    def test_strong_positive_signal(self):
        results = [
            _DimensionResult(
                key="follow_up",
                positive_weight=8.0,
                negative_weight=2.0,
                signal_count=5,
                confidence=0.8,  # 8/(8+2) = 0.8
            ),
        ]
        updates = PreferenceLearner._derive_weight_updates(results)
        assert "follow_up" in updates
        assert updates["follow_up"] > 1.0  # Positive ratio > 0.5

    def test_strong_negative_signal(self):
        results = [
            _DimensionResult(
                key="gift_reminder",
                positive_weight=1.0,
                negative_weight=9.0,
                signal_count=5,
                confidence=0.9,  # 9/(1+9) = 0.9
            ),
        ]
        updates = PreferenceLearner._derive_weight_updates(results)
        assert "gift_reminder" in updates
        assert updates["gift_reminder"] < 1.0  # Negative dominant

    def test_confidence_below_deactivation_threshold(self):
        # 0.55 / (0.55 + 0.45) = 0.55 = confidence
        # Wait -- the confidence is max(pos, neg) / total
        # We need confidence < 0.2
        # confidence = max(0.51, 0.49) / 1.0 = 0.51 -- still too high
        # For confidence < 0.2, we'd need something like max(0.1, 0.1) / (0.1+0.1) = 0.5
        # Actually confidence = max(p,n)/total, so minimum is 0.5 if total > 0
        # The only way to get < 0.2 is via a _DimensionResult with confidence set directly
        results = [
            _DimensionResult(
                key="low_conf",
                positive_weight=0.1,
                negative_weight=0.1,
                signal_count=4,
                confidence=0.15,  # below threshold
            ),
        ]
        updates = PreferenceLearner._derive_weight_updates(results)
        assert updates.get("low_conf") == 0.1  # deactivated

    def test_medium_confidence_skipped(self):
        # Confidence between deactivation (0.2) and threshold (0.7)
        results = [
            _DimensionResult(
                key="ambiguous",
                positive_weight=3.0,
                negative_weight=2.0,
                signal_count=5,
                confidence=0.6,  # 3/(3+2) = 0.6
            ),
        ]
        updates = PreferenceLearner._derive_weight_updates(results)
        assert "ambiguous" not in updates

    def test_weight_range(self):
        # Pure positive: positive_ratio = 1.0, weight = 0.1 + 1.0 * 1.9 = 2.0
        results = [
            _DimensionResult(
                key="max_weight",
                positive_weight=10.0,
                negative_weight=0.0,
                signal_count=5,
                confidence=1.0,
            ),
        ]
        updates = PreferenceLearner._derive_weight_updates(results)
        assert updates["max_weight"] == pytest.approx(2.0)

        # Pure negative: positive_ratio = 0.0, weight = 0.1 + 0.0 * 1.9 = 0.1
        results = [
            _DimensionResult(
                key="min_weight",
                positive_weight=0.0,
                negative_weight=10.0,
                signal_count=5,
                confidence=1.0,
            ),
        ]
        updates = PreferenceLearner._derive_weight_updates(results)
        assert updates["min_weight"] == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# _derive_suppressed_types
# ---------------------------------------------------------------------------

class TestDeriveSuppressedTypes:

    def test_strong_negative_suppresses(self):
        results = [
            _DimensionResult(
                key="annoying_type",
                positive_weight=1.0,
                negative_weight=9.0,
                signal_count=5,
                confidence=0.9,
            ),
        ]
        suppressed = PreferenceLearner._derive_suppressed_types(results)
        assert "annoying_type" in suppressed

    def test_positive_does_not_suppress(self):
        results = [
            _DimensionResult(
                key="useful_type",
                positive_weight=8.0,
                negative_weight=2.0,
                signal_count=5,
                confidence=0.8,
            ),
        ]
        suppressed = PreferenceLearner._derive_suppressed_types(results)
        assert "useful_type" not in suppressed

    def test_below_signal_count_does_not_suppress(self):
        results = [
            _DimensionResult(
                key="rare_type",
                positive_weight=0.0,
                negative_weight=2.0,
                signal_count=2,  # < 3
                confidence=1.0,
            ),
        ]
        suppressed = PreferenceLearner._derive_suppressed_types(results)
        assert "rare_type" not in suppressed

    def test_borderline_ratio_does_not_suppress(self):
        # negative_ratio = 0.69 < 0.70
        results = [
            _DimensionResult(
                key="borderline",
                positive_weight=3.1,
                negative_weight=6.9,
                signal_count=5,
                confidence=0.69,
            ),
        ]
        suppressed = PreferenceLearner._derive_suppressed_types(results)
        assert "borderline" not in suppressed

    def test_exact_threshold_suppresses(self):
        # negative_ratio = 7/10 = 0.7 >= 0.70
        results = [
            _DimensionResult(
                key="exact",
                positive_weight=3.0,
                negative_weight=7.0,
                signal_count=5,
                confidence=0.7,
            ),
        ]
        suppressed = PreferenceLearner._derive_suppressed_types(results)
        assert "exact" in suppressed


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------

class TestFrozenDataclasses:

    def test_weighted_signal_is_frozen(self):
        s = _WeightedSignal(is_positive=True, weight=1.0)
        with pytest.raises(AttributeError):
            s.weight = 0.5

    def test_dimension_result_is_frozen(self):
        r = _DimensionResult(
            key="x",
            positive_weight=1.0,
            negative_weight=0.0,
            signal_count=1,
            confidence=1.0,
        )
        with pytest.raises(AttributeError):
            r.confidence = 0.0


# ---------------------------------------------------------------------------
# PreferenceLearner.consolidate
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class TestConsolidate:

    @pytest.fixture()
    def learner(self):
        db = AsyncMock()
        with patch(
            "src.modules.curation.services.preference_learner.FamilyPreferenceRepository",
        ) as MockRepo:
            mock_repo = AsyncMock()
            # Default: get_or_create_default returns a pref-like object
            pref = MagicMock()
            pref.suppressed_types = []
            pref.last_learned_at = None
            pref.learning_events_count = 0
            pref.updated_at = None
            mock_repo.get_or_create_default = AsyncMock(return_value=pref)
            mock_repo.update_weights = AsyncMock()
            mock_repo.add_suppressed_type = AsyncMock()
            mock_repo.remove_suppressed_type = AsyncMock()
            MockRepo.return_value = mock_repo

            pl = PreferenceLearner(db)
            pl._repo = mock_repo
            pl._pref = pref  # stash for assertions
            return pl

    @pytest.mark.asyncio
    async def test_consolidate_with_signals(self, learner):
        family_id = uuid4()
        rec_signals = [
            _DimensionResult(
                key="follow_up", positive_weight=8.0, negative_weight=2.0,
                signal_count=5, confidence=0.8,
            ),
        ]
        assoc_signals = [
            _DimensionResult(
                key="location_based", positive_weight=7.0, negative_weight=3.0,
                signal_count=4, confidence=0.7,
            ),
        ]

        with patch.object(learner, "_gather_insight_signals", AsyncMock(return_value=rec_signals)), \
             patch.object(learner, "_gather_association_signals", AsyncMock(return_value=assoc_signals)), \
             patch.object(learner, "_sync_suppressed_types", AsyncMock()):
            result = await learner.consolidate(family_id)

        # update_weights called twice: recommendation + association
        assert learner._repo.update_weights.call_count == 2
        # First call: recommendation_weights
        first_call_args = learner._repo.update_weights.call_args_list[0]
        assert first_call_args[0][1] == "recommendation_weights"
        # Second call: association_weights
        second_call_args = learner._repo.update_weights.call_args_list[1]
        assert second_call_args[0][1] == "association_weights"

    @pytest.mark.asyncio
    async def test_consolidate_no_signals(self, learner):
        family_id = uuid4()

        with patch.object(learner, "_gather_insight_signals", AsyncMock(return_value=[])), \
             patch.object(learner, "_gather_association_signals", AsyncMock(return_value=[])), \
             patch.object(learner, "_sync_suppressed_types", AsyncMock()):
            await learner.consolidate(family_id)

        # No weight updates when no signals
        learner._repo.update_weights.assert_not_called()
        # Metadata still updated (flush called)
        learner._db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_consolidate_suppression_from_signals(self, learner):
        family_id = uuid4()
        rec_signals = [
            _DimensionResult(
                key="annoying_type", positive_weight=1.0, negative_weight=9.0,
                signal_count=5, confidence=0.9,
            ),
        ]

        with patch.object(learner, "_gather_insight_signals", AsyncMock(return_value=rec_signals)), \
             patch.object(learner, "_gather_association_signals", AsyncMock(return_value=[])):
            await learner.consolidate(family_id)

        # _sync_suppressed_types is called internally; verify add_suppressed_type
        # was called for the suppressed type
        learner._repo.add_suppressed_type.assert_called_once()
        args = learner._repo.add_suppressed_type.call_args[0]
        assert args[0] == family_id
        assert args[1] == "annoying_type"

    @pytest.mark.asyncio
    async def test_consolidate_time_expiry_recovery(self, learner):
        family_id = uuid4()
        learner._pref.suppressed_types = ["old_type"]

        with patch.object(learner, "_gather_insight_signals", AsyncMock(return_value=[])), \
             patch.object(learner, "_gather_association_signals", AsyncMock(return_value=[])), \
             patch.object(learner, "_get_expired_suppressions", AsyncMock(return_value={"old_type"})):
            await learner.consolidate(family_id)

        # Expired type should be removed
        learner._repo.remove_suppressed_type.assert_called_once()
        args = learner._repo.remove_suppressed_type.call_args[0]
        assert args[1] == "old_type"

    @pytest.mark.asyncio
    async def test_consolidate_db_failure_graceful(self, learner):
        family_id = uuid4()

        with patch.object(
            learner, "_gather_insight_signals",
            AsyncMock(side_effect=RuntimeError("DB timeout")),
        ):
            with pytest.raises(RuntimeError, match="DB timeout"):
                await learner.consolidate(family_id)
