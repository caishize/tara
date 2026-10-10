"""Unit tests for InsightDeliveryLedger (PLAN-005).

Tests cover mark_delivered, was_delivered, cross-channel dedup, and TTL-based
expiry semantics.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.modules.briefing.services.insight_delivery_ledger import (
    InsightDeliveryLedger,
    _delivery_key,
    _DELIVERY_TTL_SECONDS,
)


@pytest.fixture
def ledger():
    return InsightDeliveryLedger()


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock()
    return mock


# ---------------------------------------------------------------------------
# _delivery_key
# ---------------------------------------------------------------------------


class TestDeliveryKey:
    def test_key_format(self):
        key = _delivery_key("user-1", "insight-abc")
        assert key == "insight:delivered:user-1:insight-abc"

    def test_different_users_different_keys(self):
        assert _delivery_key("u1", "i1") != _delivery_key("u2", "i1")

    def test_different_insights_different_keys(self):
        assert _delivery_key("u1", "i1") != _delivery_key("u1", "i2")


# ---------------------------------------------------------------------------
# mark_delivered
# ---------------------------------------------------------------------------


class TestMarkDelivered:
    @pytest.mark.asyncio
    async def test_sets_key_with_channel_and_ttl(self, ledger, mock_redis):
        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis
            await ledger.mark_delivered("user-1", "insight-1", "briefing")

            mock_redis.setex.assert_awaited_once_with(
                "insight:delivered:user-1:insight-1",
                _DELIVERY_TTL_SECONDS,
                "briefing",
            )

    @pytest.mark.asyncio
    async def test_marks_sidekick_channel(self, ledger, mock_redis):
        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis
            await ledger.mark_delivered("user-1", "insight-1", "sidekick")

            mock_redis.setex.assert_awaited_once_with(
                "insight:delivered:user-1:insight-1",
                _DELIVERY_TTL_SECONDS,
                "sidekick",
            )

    @pytest.mark.asyncio
    async def test_graceful_when_redis_none(self, ledger):
        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = None
            # Should not raise
            await ledger.mark_delivered("user-1", "insight-1", "briefing")

    @pytest.mark.asyncio
    async def test_graceful_on_redis_error(self, ledger, mock_redis):
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis down"))
        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis
            # Should not raise
            await ledger.mark_delivered("user-1", "insight-1", "briefing")


# ---------------------------------------------------------------------------
# was_delivered
# ---------------------------------------------------------------------------


class TestWasDelivered:
    @pytest.mark.asyncio
    async def test_returns_true_when_key_exists(self, ledger, mock_redis):
        mock_redis.get = AsyncMock(return_value="briefing")
        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis
            result = await ledger.was_delivered("user-1", "insight-1")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_key_absent(self, ledger, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis
            result = await ledger.was_delivered("user-1", "insight-1")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_redis_none(self, ledger):
        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = None
            result = await ledger.was_delivered("user-1", "insight-1")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_redis_error(self, ledger, mock_redis):
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis
            result = await ledger.was_delivered("user-1", "insight-1")
            assert result is False


# ---------------------------------------------------------------------------
# Cross-channel dedup (PLAN-005 acceptance criteria)
# ---------------------------------------------------------------------------


class TestCrossChannelDedup:
    @pytest.mark.asyncio
    async def test_briefing_blocks_sidekick(self, ledger, mock_redis):
        """Insight delivered via briefing -> was_delivered returns True -> sidekick blocked."""
        call_count = 0

        async def get_side_effect(key):
            nonlocal call_count
            call_count += 1
            # After mark_delivered sets the key, subsequent gets return the channel
            if call_count > 1:
                return "briefing"
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis

            # Step 1: Not delivered yet
            assert await ledger.was_delivered("u1", "i1") is False

            # Step 2: Mark as delivered via briefing
            await ledger.mark_delivered("u1", "i1", "briefing")

            # Step 3: Subsequent check returns True (sidekick would be blocked)
            assert await ledger.was_delivered("u1", "i1") is True

    @pytest.mark.asyncio
    async def test_ttl_expiry_allows_next_day(self, ledger, mock_redis):
        """After TTL expires, was_delivered returns False -> next day delivery passes."""
        mock_redis.get = AsyncMock(return_value=None)  # Key expired

        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis

            # Day 2: TTL expired, key gone
            result = await ledger.was_delivered("u1", "i1")
            assert result is False

    @pytest.mark.asyncio
    async def test_different_insight_ids_independent(self, ledger, mock_redis):
        """Delivery of insight-1 does not block insight-2."""

        async def get_side_effect(key):
            if "insight-1" in key:
                return "briefing"
            return None

        mock_redis.get = AsyncMock(side_effect=get_side_effect)

        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis

            assert await ledger.was_delivered("u1", "insight-1") is True
            assert await ledger.was_delivered("u1", "insight-2") is False


# ---------------------------------------------------------------------------
# get_channel
# ---------------------------------------------------------------------------


class TestGetChannel:
    @pytest.mark.asyncio
    async def test_returns_channel_name(self, ledger, mock_redis):
        mock_redis.get = AsyncMock(return_value="sidekick")
        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis
            result = await ledger.get_channel("u1", "i1")
            assert result == "sidekick"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_delivered(self, ledger, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        with patch(
            "src.modules.briefing.services.insight_delivery_ledger.redis_client"
        ) as rc_mod:
            rc_mod.client = mock_redis
            result = await ledger.get_channel("u1", "i1")
            assert result is None
