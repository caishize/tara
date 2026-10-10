"""Tests for RelationshipThermometer four-dimension model."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.modules.relationship.thermometer import (
    RelationshipTemperature,
    compute_temperature,
)


# ---------------------------------------------------------------------------
# RelationshipTemperature dataclass tests
# ---------------------------------------------------------------------------


class TestRelationshipTemperature:
    """Test the frozen dataclass scoring and status."""

    def test_composite_all_zeros(self):
        temp = RelationshipTemperature()
        assert temp.composite == 0.0

    def test_composite_all_ones(self):
        temp = RelationshipTemperature(
            interaction_freq=1.0,
            interaction_quality=1.0,
            commitment_fulfillment=1.0,
            recency=1.0,
        )
        assert abs(temp.composite - 1.0) < 1e-9

    def test_composite_weighted_calculation(self):
        temp = RelationshipTemperature(
            interaction_freq=0.5,
            interaction_quality=0.8,
            commitment_fulfillment=0.6,
            recency=0.4,
        )
        expected = 0.5 * 0.3 + 0.8 * 0.3 + 0.6 * 0.2 + 0.4 * 0.2
        assert abs(temp.composite - expected) < 1e-9

    def test_status_warm(self):
        temp = RelationshipTemperature(
            interaction_freq=0.9,
            interaction_quality=0.9,
            commitment_fulfillment=0.9,
            recency=0.9,
        )
        assert temp.status == "warm"

    def test_status_cool(self):
        temp = RelationshipTemperature(
            interaction_freq=0.5,
            interaction_quality=0.5,
            commitment_fulfillment=0.5,
            recency=0.5,
        )
        assert temp.status == "cool"

    def test_status_cold(self):
        temp = RelationshipTemperature(
            interaction_freq=0.2,
            interaction_quality=0.3,
            commitment_fulfillment=0.2,
            recency=0.1,
        )
        assert temp.status == "cold"

    def test_status_frozen(self):
        temp = RelationshipTemperature(
            interaction_freq=0.1,
            interaction_quality=0.1,
            commitment_fulfillment=0.1,
            recency=0.0,
        )
        assert temp.status == "frozen"

    def test_boundary_warm_at_exactly_0_7(self):
        # composite = 0.7 * 0.3 + 0.7 * 0.3 + 0.7 * 0.2 + 0.7 * 0.2 = 0.7
        temp = RelationshipTemperature(
            interaction_freq=0.7,
            interaction_quality=0.7,
            commitment_fulfillment=0.7,
            recency=0.7,
        )
        assert temp.status == "warm"

    def test_boundary_cool_just_below_0_7(self):
        temp = RelationshipTemperature(
            interaction_freq=0.69,
            interaction_quality=0.69,
            commitment_fulfillment=0.69,
            recency=0.69,
        )
        assert temp.status == "cool"

    def test_boundary_cold_at_exactly_0_2(self):
        temp = RelationshipTemperature(
            interaction_freq=0.2,
            interaction_quality=0.2,
            commitment_fulfillment=0.2,
            recency=0.2,
        )
        assert temp.status == "cold"

    def test_boundary_frozen_just_below_0_2(self):
        temp = RelationshipTemperature(
            interaction_freq=0.19,
            interaction_quality=0.19,
            commitment_fulfillment=0.19,
            recency=0.19,
        )
        assert temp.status == "frozen"

    def test_frozen_dataclass_immutable(self):
        temp = RelationshipTemperature(interaction_freq=0.5)
        with pytest.raises(AttributeError):
            temp.interaction_freq = 0.9

    def test_default_values(self):
        temp = RelationshipTemperature()
        assert temp.interaction_freq == 0.0
        assert temp.interaction_quality == 0.0
        assert temp.commitment_fulfillment == 0.0
        assert temp.recency == 0.0


# ---------------------------------------------------------------------------
# compute_temperature async tests (mocked DB)
# ---------------------------------------------------------------------------


def _make_scalar_mock(value):
    """Create a mock execute result that returns value from .scalar()."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


class TestComputeTemperature:
    """Test compute_temperature with mocked DB session."""

    @pytest.mark.asyncio
    async def test_compute_with_active_memories(self):
        user_id = uuid4()
        target_id = uuid4()
        now = datetime.now(timezone.utc)

        db = AsyncMock()
        # freq query: 15 memories
        # quality query: avg importance 7.0
        # commitment total: 10, fulfilled: 8
        # recency query: 2 days ago
        db.execute = AsyncMock(
            side_effect=[
                _make_scalar_mock(15),      # freq count
                _make_scalar_mock(7.0),     # avg importance
                _make_scalar_mock(10),      # commitment total
                _make_scalar_mock(8),       # commitment fulfilled
                _make_scalar_mock(now - timedelta(days=2)),  # last interaction
            ]
        )

        temp = await compute_temperature(user_id, target_id, db)

        assert abs(temp.interaction_freq - 0.5) < 1e-9  # 15/30
        assert abs(temp.interaction_quality - 0.7) < 1e-9  # 7/10
        assert abs(temp.commitment_fulfillment - 0.8) < 1e-9  # 8/10
        # recency: 1.0 - 2/30 ≈ 0.933
        assert temp.recency > 0.9
        assert temp.status == "warm"

    @pytest.mark.asyncio
    async def test_compute_no_memories(self):
        user_id = uuid4()
        target_id = uuid4()

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _make_scalar_mock(0),     # no memories
                _make_scalar_mock(None),  # no avg importance
                _make_scalar_mock(0),     # no commitments
                _make_scalar_mock(None),  # no last interaction
            ]
        )

        temp = await compute_temperature(user_id, target_id, db)

        assert temp.interaction_freq == 0.0
        assert abs(temp.interaction_quality - 0.5) < 1e-9  # default 5.0 / 10
        assert temp.commitment_fulfillment == 0.5  # neutral default
        assert temp.recency == 0.0
        assert temp.status == "cold"

    @pytest.mark.asyncio
    async def test_compute_freq_capped_at_1(self):
        user_id = uuid4()
        target_id = uuid4()
        now = datetime.now(timezone.utc)

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _make_scalar_mock(100),     # over 30 memories
                _make_scalar_mock(10.0),    # max importance
                _make_scalar_mock(0),       # no commitments
                _make_scalar_mock(now),     # just now
            ]
        )

        temp = await compute_temperature(user_id, target_id, db)

        assert temp.interaction_freq == 1.0
        assert temp.interaction_quality == 1.0
        assert temp.recency == 1.0

    @pytest.mark.asyncio
    async def test_compute_commitment_fallback_on_error(self):
        """When commitment_items table doesn't exist, falls back to 0.5."""
        user_id = uuid4()
        target_id = uuid4()

        db = AsyncMock()
        # First two calls succeed, then commitment query raises
        call_count = 0

        async def side_effect_fn(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_scalar_mock(10)     # freq
            if call_count == 2:
                return _make_scalar_mock(5.0)    # quality
            if call_count == 3:
                raise Exception("table not found")
            # After commitment fallback, recency query
            return _make_scalar_mock(None)

        db.execute = AsyncMock(side_effect=side_effect_fn)

        temp = await compute_temperature(user_id, target_id, db)

        assert temp.commitment_fulfillment == 0.5
