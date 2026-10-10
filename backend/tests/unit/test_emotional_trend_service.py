"""Tests for EmotionalTrendService -- sentiment aggregation from memories."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.memory.emotional_trend_service import (
    EmotionalTrend,
    _determine_tone,
    _determine_trend,
    compute_emotional_trend,
)


# ---------------------------------------------------------------------------
# _determine_trend
# ---------------------------------------------------------------------------

class TestDetermineTrend:

    def test_declining_when_negative_dominant(self):
        # negative >= 3 and negative > positive * 2
        assert _determine_trend(5, 2) == "declining"

    def test_declining_boundary(self):
        # negative=3, positive=1 -> 3 >= 3 and 3 > 1*2 -> True
        assert _determine_trend(3, 1) == "declining"

    def test_not_declining_when_negative_below_3(self):
        assert _determine_trend(2, 0) == "stable"

    def test_not_declining_when_negative_not_double_positive(self):
        # negative=3, positive=2 -> 3 > 2*2=4 -> False
        assert _determine_trend(3, 2) == "stable"

    def test_improving_when_positive_dominant(self):
        # positive >= 3 and positive > negative * 2
        assert _determine_trend(1, 5) == "improving"

    def test_improving_boundary(self):
        # positive=3, negative=1 -> 3 >= 3 and 3 > 1*2 -> True
        assert _determine_trend(1, 3) == "improving"

    def test_not_improving_when_positive_below_3(self):
        assert _determine_trend(0, 2) == "stable"

    def test_stable_when_balanced(self):
        assert _determine_trend(3, 3) == "stable"

    def test_stable_when_both_zero(self):
        assert _determine_trend(0, 0) == "stable"


# ---------------------------------------------------------------------------
# _determine_tone
# ---------------------------------------------------------------------------

class TestDetermineTone:

    def test_declining_gives_empathetic(self):
        assert _determine_tone("declining", 5, 1) == "empathetic"

    def test_improving_gives_encouraging(self):
        assert _determine_tone("improving", 1, 5) == "encouraging"

    def test_stable_gives_neutral(self):
        assert _determine_tone("stable", 2, 2) == "neutral"

    def test_unknown_gives_neutral(self):
        assert _determine_tone("unknown", 0, 0) == "neutral"


# ---------------------------------------------------------------------------
# EmotionalTrend.to_prompt_section
# ---------------------------------------------------------------------------

class TestToPromptSection:

    def test_unknown_returns_empty(self):
        trend = EmotionalTrend(
            trend="unknown",
            negative_count=0,
            positive_count=0,
            neutral_count=0,
            total_count=0,
            suggested_tone="neutral",
        )
        assert trend.to_prompt_section() == ""

    def test_declining_includes_tone(self):
        trend = EmotionalTrend(
            trend="declining",
            negative_count=5,
            positive_count=1,
            neutral_count=2,
            total_count=8,
            suggested_tone="empathetic",
        )
        section = trend.to_prompt_section()
        assert "declining" in section
        assert "5" in section
        assert "温和共情" in section

    def test_improving_includes_encouraging(self):
        trend = EmotionalTrend(
            trend="improving",
            negative_count=1,
            positive_count=5,
            neutral_count=1,
            total_count=7,
            suggested_tone="encouraging",
        )
        section = trend.to_prompt_section()
        assert "积极鼓励" in section

    def test_stable_includes_neutral_tone(self):
        trend = EmotionalTrend(
            trend="stable",
            negative_count=2,
            positive_count=2,
            neutral_count=3,
            total_count=7,
            suggested_tone="neutral",
        )
        section = trend.to_prompt_section()
        assert "平和自然" in section


# ---------------------------------------------------------------------------
# compute_emotional_trend -- with mocked DB
# ---------------------------------------------------------------------------

class TestComputeEmotionalTrend:

    @pytest.mark.asyncio
    async def test_declining_trend(self):
        row = MagicMock()
        row.total = 8
        row.negative_count = 5
        row.positive_count = 1
        row.neutral_count = 2

        mock_result = MagicMock()
        mock_result.one.return_value = row

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        trend = await compute_emotional_trend(session, uuid4())
        assert trend.trend == "declining"
        assert trend.suggested_tone == "empathetic"
        assert trend.negative_count == 5
        assert trend.total_count == 8

    @pytest.mark.asyncio
    async def test_improving_trend(self):
        row = MagicMock()
        row.total = 6
        row.negative_count = 1
        row.positive_count = 4
        row.neutral_count = 1

        mock_result = MagicMock()
        mock_result.one.return_value = row

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        trend = await compute_emotional_trend(session, uuid4())
        assert trend.trend == "improving"
        assert trend.suggested_tone == "encouraging"

    @pytest.mark.asyncio
    async def test_stable_trend(self):
        row = MagicMock()
        row.total = 6
        row.negative_count = 2
        row.positive_count = 2
        row.neutral_count = 2

        mock_result = MagicMock()
        mock_result.one.return_value = row

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        trend = await compute_emotional_trend(session, uuid4())
        assert trend.trend == "stable"
        assert trend.suggested_tone == "neutral"

    @pytest.mark.asyncio
    async def test_no_data_returns_unknown(self):
        row = MagicMock()
        row.total = 0
        row.negative_count = 0
        row.positive_count = 0
        row.neutral_count = 0

        mock_result = MagicMock()
        mock_result.one.return_value = row

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        trend = await compute_emotional_trend(session, uuid4())
        assert trend.trend == "unknown"
        assert trend.suggested_tone == "neutral"
        assert trend.total_count == 0

    @pytest.mark.asyncio
    async def test_db_failure_returns_unknown(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=RuntimeError("DB down"))

        trend = await compute_emotional_trend(session, uuid4())
        assert trend.trend == "unknown"
        assert trend.suggested_tone == "neutral"
        assert trend.total_count == 0

    @pytest.mark.asyncio
    async def test_none_counts_treated_as_zero(self):
        row = MagicMock()
        row.total = None
        row.negative_count = None
        row.positive_count = None
        row.neutral_count = None

        mock_result = MagicMock()
        mock_result.one.return_value = row

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)

        trend = await compute_emotional_trend(session, uuid4())
        assert trend.trend == "unknown"
        assert trend.total_count == 0


# ---------------------------------------------------------------------------
# EmotionalTrend frozen
# ---------------------------------------------------------------------------

class TestEmotionalTrendFrozen:

    def test_is_frozen(self):
        trend = EmotionalTrend(
            trend="stable",
            negative_count=0,
            positive_count=0,
            neutral_count=0,
            total_count=0,
            suggested_tone="neutral",
        )
        with pytest.raises(AttributeError):
            trend.trend = "declining"
