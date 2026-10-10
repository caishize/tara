"""Tests for push budget and interruption controller.

Covers:
- PushBudget: can_push, record_push, get_remaining, P0 bypass
- InterruptionController: delivery mode decisions, night hours, priority mapping
- DeliveryDecision: frozen dataclass
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.core.push.push_budget import (
    can_push,
    record_push,
    get_remaining,
    _budget_key,
    DEFAULT_DAILY_LIMIT,
)
from src.core.push.interruption_controller import (
    DeliveryDecision,
    InterruptionController,
)


# ---------------------------------------------------------------------------
# PushBudget key generation
# ---------------------------------------------------------------------------


class TestBudgetKey:

    def test_key_format(self):
        uid = uuid4()
        today = date(2026, 2, 18)
        key = _budget_key(uid, today)
        assert key == f"push_count:{uid}:2026-02-18"


# ---------------------------------------------------------------------------
# PushBudget: can_push
# ---------------------------------------------------------------------------


class TestCanPush:

    @pytest.mark.asyncio
    async def test_p0_always_allowed(self):
        """P0 bypasses budget entirely, no Redis call needed."""
        uid = uuid4()
        result = await can_push(uid, priority_level="P0", daily_limit=0)
        assert result is True

    @pytest.mark.asyncio
    async def test_under_limit_allowed(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value="3")
            result = await can_push(uid, priority_level="P2", daily_limit=5)
            assert result is True

    @pytest.mark.asyncio
    async def test_at_limit_denied(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value="5")
            result = await can_push(uid, priority_level="P2", daily_limit=5)
            assert result is False

    @pytest.mark.asyncio
    async def test_over_limit_denied(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value="10")
            result = await can_push(uid, priority_level="P1", daily_limit=5)
            assert result is False

    @pytest.mark.asyncio
    async def test_no_existing_count_allowed(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            result = await can_push(uid, priority_level="P3", daily_limit=5)
            assert result is True

    @pytest.mark.asyncio
    async def test_redis_error_fails_open(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(side_effect=ConnectionError("down"))
            result = await can_push(uid, priority_level="P2", daily_limit=5)
            assert result is True

    @pytest.mark.asyncio
    async def test_custom_daily_limit(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value="2")
            assert await can_push(uid, priority_level="P2", daily_limit=3) is True
            assert await can_push(uid, priority_level="P2", daily_limit=2) is False


# ---------------------------------------------------------------------------
# PushBudget: record_push
# ---------------------------------------------------------------------------


class TestRecordPush:

    @pytest.mark.asyncio
    async def test_increments_count(self):
        uid = uuid4()
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock()
        mock_pipe.expire = MagicMock()
        mock_pipe.execute = AsyncMock(return_value=[4, True])

        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_client.pipeline = MagicMock(return_value=mock_pipe)
            mock_redis.client = mock_client

            count = await record_push(uid)
            assert count == 4
            mock_pipe.incr.assert_called_once()
            mock_pipe.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_none_client(self):
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.client = None
            uid = uuid4()
            count = await record_push(uid)
            assert count == -1

    @pytest.mark.asyncio
    async def test_redis_error_returns_negative(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_client.pipeline = MagicMock(
                side_effect=ConnectionError("down")
            )
            mock_redis.client = mock_client
            count = await record_push(uid)
            assert count == -1


# ---------------------------------------------------------------------------
# PushBudget: get_remaining
# ---------------------------------------------------------------------------


class TestGetRemaining:

    @pytest.mark.asyncio
    async def test_full_budget(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            remaining = await get_remaining(uid, daily_limit=5)
            assert remaining == 5

    @pytest.mark.asyncio
    async def test_partial_budget(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value="3")
            remaining = await get_remaining(uid, daily_limit=5)
            assert remaining == 2

    @pytest.mark.asyncio
    async def test_exhausted_budget(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(return_value="7")
            remaining = await get_remaining(uid, daily_limit=5)
            assert remaining == 0

    @pytest.mark.asyncio
    async def test_error_returns_full_limit(self):
        uid = uuid4()
        with patch("src.core.push.push_budget.redis_client") as mock_redis:
            mock_redis.get = AsyncMock(side_effect=ConnectionError("down"))
            remaining = await get_remaining(uid, daily_limit=5)
            assert remaining == 5


# ---------------------------------------------------------------------------
# DeliveryDecision
# ---------------------------------------------------------------------------


class TestDeliveryDecision:

    def test_frozen(self):
        dd = DeliveryDecision(mode="immediate", reason="P0 urgent")
        with pytest.raises(AttributeError):
            dd.mode = "badge_only"

    def test_default_reason(self):
        dd = DeliveryDecision(mode="immediate")
        assert dd.reason == ""


# ---------------------------------------------------------------------------
# InterruptionController
# ---------------------------------------------------------------------------


class TestInterruptionController:

    def setup_method(self):
        self.ctrl = InterruptionController(night_start=23, night_end=7)

    # -- Night detection --

    def test_is_night_midnight(self):
        assert self.ctrl.is_night(0) is True

    def test_is_night_3am(self):
        assert self.ctrl.is_night(3) is True

    def test_is_night_6am(self):
        assert self.ctrl.is_night(6) is True

    def test_is_night_7am_not_night(self):
        assert self.ctrl.is_night(7) is False

    def test_is_night_noon(self):
        assert self.ctrl.is_night(12) is False

    def test_is_night_22_not_night(self):
        assert self.ctrl.is_night(22) is False

    def test_is_night_23_is_night(self):
        assert self.ctrl.is_night(23) is True

    # -- P0 always immediate --

    def test_p0_daytime(self):
        dd = self.ctrl.get_delivery_mode("P0", 10)
        assert dd.mode == "immediate"

    def test_p0_night(self):
        dd = self.ctrl.get_delivery_mode("P0", 2)
        assert dd.mode == "immediate"

    # -- P1 --

    def test_p1_daytime(self):
        dd = self.ctrl.get_delivery_mode("P1", 10)
        assert dd.mode == "immediate"

    def test_p1_night(self):
        dd = self.ctrl.get_delivery_mode("P1", 2)
        assert dd.mode == "badge_only"

    # -- P2 --

    def test_p2_daytime(self):
        dd = self.ctrl.get_delivery_mode("P2", 14)
        assert dd.mode == "badge_only"

    def test_p2_night(self):
        dd = self.ctrl.get_delivery_mode("P2", 1)
        assert dd.mode == "queue_for_later"

    # -- P3 --

    def test_p3_daytime(self):
        dd = self.ctrl.get_delivery_mode("P3", 10)
        assert dd.mode == "queue_for_later"

    def test_p3_night(self):
        dd = self.ctrl.get_delivery_mode("P3", 3)
        assert dd.mode == "queue_for_later"

    # -- Custom night window --

    def test_custom_night_window(self):
        ctrl = InterruptionController(night_start=22, night_end=6)
        assert ctrl.is_night(22) is True
        assert ctrl.is_night(5) is True
        assert ctrl.is_night(6) is False
        assert ctrl.is_night(21) is False

    # -- Contiguous night window (no midnight wrap) --

    def test_contiguous_night_window(self):
        ctrl = InterruptionController(night_start=0, night_end=6)
        assert ctrl.is_night(0) is True
        assert ctrl.is_night(3) is True
        assert ctrl.is_night(5) is True
        assert ctrl.is_night(6) is False
        assert ctrl.is_night(23) is False

    # -- Validation --

    def test_invalid_night_start(self):
        with pytest.raises(ValueError):
            InterruptionController(night_start=25, night_end=7)

    def test_invalid_night_end(self):
        with pytest.raises(ValueError):
            InterruptionController(night_start=23, night_end=25)

    # -- Reason strings --

    def test_reasons_are_populated(self):
        dd = self.ctrl.get_delivery_mode("P0", 10)
        assert dd.reason != ""

        dd = self.ctrl.get_delivery_mode("P1", 10)
        assert dd.reason != ""

        dd = self.ctrl.get_delivery_mode("P3", 2)
        assert "night" in dd.reason.lower()
