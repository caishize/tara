"""
Unit tests for promotional period configuration (T031)
Tests PromotionPeriod, PromotionManager, and promotion detection.
"""
import pytest
from datetime import date

from src.modules.gift.providers.promotion import (
    PromotionPeriod,
    PromotionManager,
    get_promotion_manager,
    is_promotion_period,
    get_current_promotion_names,
    DEFAULT_PROMOTION_PERIODS,
)


class TestPromotionPeriod:
    """Test PromotionPeriod dataclass"""

    def test_promotion_period_creation(self):
        """Test creating a promotion period"""
        period = PromotionPeriod(
            name="双十一",
            start_month=11,
            start_day=1,
            end_month=11,
            end_day=11,
            check_frequency_multiplier=24,
            enabled=True
        )
        assert period.name == "双十一"
        assert period.start_month == 11
        assert period.start_day == 1
        assert period.end_month == 11
        assert period.end_day == 11
        assert period.check_frequency_multiplier == 24
        assert period.enabled is True

    def test_is_active_during_period(self):
        """Test promotion is active during the period"""
        # Double 11: Nov 1-11
        period = PromotionPeriod(
            name="双十一",
            start_month=11,
            start_day=1,
            end_month=11,
            end_day=11
        )

        assert period.is_active(date(2024, 11, 1))  # Start date
        assert period.is_active(date(2024, 11, 5))  # Middle
        assert period.is_active(date(2024, 11, 11))  # End date

    def test_is_not_active_outside_period(self):
        """Test promotion is not active outside the period"""
        period = PromotionPeriod(
            name="双十一",
            start_month=11,
            start_day=1,
            end_month=11,
            end_day=11
        )

        assert not period.is_active(date(2024, 10, 31))  # Day before
        assert not period.is_active(date(2024, 11, 12))  # Day after
        assert not period.is_active(date(2024, 6, 15))  # Different month

    def test_is_active_disabled_period(self):
        """Test disabled period is never active"""
        period = PromotionPeriod(
            name="双十一",
            start_month=11,
            start_day=1,
            end_month=11,
            end_day=11,
            enabled=False
        )

        assert not period.is_active(date(2024, 11, 5))

    def test_cross_year_period(self):
        """Test period that spans year boundary"""
        # New Year promotion: Dec 26 - Jan 5
        period = PromotionPeriod(
            name="跨年促销",
            start_month=12,
            start_day=26,
            end_month=1,
            end_day=5
        )

        assert period.is_active(date(2024, 12, 26))  # Start
        assert period.is_active(date(2024, 12, 31))  # NYE
        assert period.is_active(date(2025, 1, 1))  # New Year
        assert period.is_active(date(2025, 1, 5))  # End

        assert not period.is_active(date(2024, 12, 25))  # Before
        assert not period.is_active(date(2025, 1, 6))  # After

    def test_618_period(self):
        """Test 618 promotion period"""
        period = PromotionPeriod(
            name="618",
            start_month=6,
            start_day=1,
            end_month=6,
            end_day=18
        )

        assert period.is_active(date(2024, 6, 1))
        assert period.is_active(date(2024, 6, 18))
        assert not period.is_active(date(2024, 6, 19))


class TestPromotionManager:
    """Test PromotionManager class"""

    def test_default_promotions_loaded(self):
        """Test default promotions are loaded"""
        manager = PromotionManager()
        assert len(manager.periods) > 0

        # Check known promotions exist
        period_names = [p.name for p in manager.periods]
        assert "双十一" in period_names
        assert "618" in period_names

    def test_is_promotion_period_during_double11(self):
        """Test detection during Double 11"""
        manager = PromotionManager()
        assert manager.is_promotion_period(date(2024, 11, 5))

    def test_is_promotion_period_during_618(self):
        """Test detection during 618"""
        manager = PromotionManager()
        assert manager.is_promotion_period(date(2024, 6, 10))

    def test_is_not_promotion_period(self):
        """Test no promotion in July"""
        manager = PromotionManager()
        assert not manager.is_promotion_period(date(2024, 7, 15))

    def test_get_active_promotions(self):
        """Test getting active promotions"""
        manager = PromotionManager()
        active = manager.get_active_promotions(date(2024, 11, 5))

        assert len(active) >= 1
        assert any(p.name == "双十一" for p in active)

    def test_get_check_interval_normal(self):
        """Test check interval during normal period"""
        manager = PromotionManager()
        interval = manager.get_check_interval_seconds(date(2024, 7, 15))

        assert interval == 86400  # Once per day

    def test_get_check_interval_promotional(self):
        """Test check interval during promotional period"""
        manager = PromotionManager()
        interval = manager.get_check_interval_seconds(date(2024, 11, 5))

        # Double 11 has 24x multiplier, so 86400/24 = 3600 (hourly)
        assert interval == 3600

    def test_get_batch_interval_normal(self):
        """Test batch interval during normal period"""
        manager = PromotionManager()
        interval = manager.get_batch_interval_seconds(date(2024, 7, 15))

        assert interval == 30

    def test_get_batch_interval_promotional(self):
        """Test batch interval during promotional period"""
        manager = PromotionManager()
        interval = manager.get_batch_interval_seconds(date(2024, 11, 5))

        assert interval == 15  # Faster during promotions

    def test_add_custom_period(self):
        """Test adding custom promotional period"""
        manager = PromotionManager()
        initial_count = len(manager.periods)

        custom = PromotionPeriod(
            name="自定义促销",
            start_month=8,
            start_day=1,
            end_month=8,
            end_day=10
        )
        manager.add_period(custom)

        assert len(manager.periods) == initial_count + 1
        assert manager.is_promotion_period(date(2024, 8, 5))

    def test_remove_period(self):
        """Test removing promotional period"""
        manager = PromotionManager()
        initial_count = len(manager.periods)

        removed = manager.remove_period("618")
        assert removed is True
        assert len(manager.periods) == initial_count - 1

    def test_remove_nonexistent_period(self):
        """Test removing nonexistent period"""
        manager = PromotionManager()

        removed = manager.remove_period("不存在的促销")
        assert removed is False

    def test_enable_disable_period(self):
        """Test enabling and disabling period"""
        manager = PromotionManager()

        # Disable Double 11
        manager.disable_period("双十一")
        assert not manager.is_promotion_period(date(2024, 11, 5))

        # Re-enable
        manager.enable_period("双十一")
        assert manager.is_promotion_period(date(2024, 11, 5))

    def test_get_period_info(self):
        """Test getting period information"""
        manager = PromotionManager()
        info = manager.get_period_info()

        assert len(info) > 0
        assert all("name" in p for p in info)
        assert all("enabled" in p for p in info)
        assert all("is_active" in p for p in info)


class TestDefaultPromotionPeriods:
    """Test default promotion periods configuration"""

    def test_default_periods_count(self):
        """Test minimum number of default periods"""
        assert len(DEFAULT_PROMOTION_PERIODS) >= 6

    def test_double11_config(self):
        """Test Double 11 configuration"""
        double11 = next(
            (p for p in DEFAULT_PROMOTION_PERIODS if p.name == "双十一"),
            None
        )
        assert double11 is not None
        assert double11.start_month == 11
        assert double11.start_day == 1
        assert double11.end_month == 11
        assert double11.end_day == 11
        assert double11.check_frequency_multiplier == 24

    def test_618_config(self):
        """Test 618 configuration"""
        _618 = next(
            (p for p in DEFAULT_PROMOTION_PERIODS if p.name == "618"),
            None
        )
        assert _618 is not None
        assert _618.start_month == 6
        assert _618.start_day == 1
        assert _618.end_month == 6
        assert _618.end_day == 18
        assert _618.check_frequency_multiplier == 24

    def test_all_periods_enabled(self):
        """Test all default periods are enabled"""
        for period in DEFAULT_PROMOTION_PERIODS:
            assert period.enabled is True


class TestConvenienceFunctions:
    """Test module-level convenience functions"""

    def test_get_promotion_manager_singleton(self):
        """Test get_promotion_manager returns singleton"""
        manager1 = get_promotion_manager()
        manager2 = get_promotion_manager()
        assert manager1 is manager2

    def test_is_promotion_period_function(self):
        """Test is_promotion_period convenience function"""
        # During Double 11
        assert is_promotion_period(date(2024, 11, 5))
        # Not during promotion
        assert not is_promotion_period(date(2024, 7, 15))

    def test_get_current_promotion_names(self):
        """Test get_current_promotion_names function"""
        # This depends on current date, so we test the type
        names = get_current_promotion_names()
        assert isinstance(names, list)


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_single_day_promotion(self):
        """Test promotion lasting single day"""
        period = PromotionPeriod(
            name="闪购",
            start_month=5,
            start_day=20,
            end_month=5,
            end_day=20
        )

        assert period.is_active(date(2024, 5, 20))
        assert not period.is_active(date(2024, 5, 19))
        assert not period.is_active(date(2024, 5, 21))

    def test_month_spanning_promotion(self):
        """Test promotion spanning multiple months"""
        period = PromotionPeriod(
            name="年中大促",
            start_month=5,
            start_day=25,
            end_month=6,
            end_day=18
        )

        assert period.is_active(date(2024, 5, 25))
        assert period.is_active(date(2024, 5, 31))
        assert period.is_active(date(2024, 6, 1))
        assert period.is_active(date(2024, 6, 18))
        assert not period.is_active(date(2024, 5, 24))
        assert not period.is_active(date(2024, 6, 19))

    def test_highest_multiplier_used(self):
        """Test that highest frequency multiplier is used when multiple active"""
        periods = [
            PromotionPeriod(
                name="促销A",
                start_month=11,
                start_day=1,
                end_month=11,
                end_day=15,
                check_frequency_multiplier=6
            ),
            PromotionPeriod(
                name="促销B",
                start_month=11,
                start_day=5,
                end_month=11,
                end_day=20,
                check_frequency_multiplier=24
            ),
        ]
        manager = PromotionManager(periods)

        # Nov 10 is in both promotions
        interval = manager.get_check_interval_seconds(date(2024, 11, 10))

        # Should use highest multiplier (24), so 86400/24 = 3600
        assert interval == 3600
