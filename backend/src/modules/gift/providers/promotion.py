"""
Promotion Period Configuration (T031)
Configures promotional periods (Double 11, 618, etc.) for increased price check frequency.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class PromotionPeriod:
    """
    Promotional period configuration

    Defines periods when price check frequency should be increased.
    """
    name: str  # Display name (e.g., "双十一")
    start_month: int  # Start month (1-12)
    start_day: int  # Start day (1-31)
    end_month: int  # End month (1-12)
    end_day: int  # End day (1-31)
    check_frequency_multiplier: int = 24  # How many times more frequent (24 = hourly vs daily)
    enabled: bool = True

    def is_active(self, check_date: Optional[date] = None) -> bool:
        """
        Check if the promotion is active on a given date

        Args:
            check_date: Date to check (defaults to today)

        Returns:
            True if the promotion is active
        """
        if not self.enabled:
            return False

        if check_date is None:
            check_date = date.today()

        current_month = check_date.month
        current_day = check_date.day

        # Handle same-year promotions (e.g., Jun 1-18)
        if self.start_month <= self.end_month:
            if self.start_month < current_month < self.end_month:
                return True
            if self.start_month == self.end_month:
                # Same month: must be within [start_day, end_day]
                return (
                    current_month == self.start_month
                    and self.start_day <= current_day <= self.end_day
                )
            if current_month == self.start_month and current_day >= self.start_day:
                return True
            if current_month == self.end_month and current_day <= self.end_day:
                return True
            return False

        # Handle cross-year promotions (e.g., Dec 26 - Jan 5)
        else:
            if current_month > self.start_month or current_month < self.end_month:
                return True
            if current_month == self.start_month and current_day >= self.start_day:
                return True
            if current_month == self.end_month and current_day <= self.end_day:
                return True
            return False


# Pre-configured promotional periods for China e-commerce
DEFAULT_PROMOTION_PERIODS: List[PromotionPeriod] = [
    # Double 11 (双十一): November 1-11
    PromotionPeriod(
        name="双十一",
        start_month=11,
        start_day=1,
        end_month=11,
        end_day=11,
        check_frequency_multiplier=24,  # Check every hour
        enabled=True,
    ),

    # 618: June 1-18
    PromotionPeriod(
        name="618",
        start_month=6,
        start_day=1,
        end_month=6,
        end_day=18,
        check_frequency_multiplier=24,  # Check every hour
        enabled=True,
    ),

    # Chinese New Year / Spring Festival Shopping (年货节): January 15-30
    PromotionPeriod(
        name="年货节",
        start_month=1,
        start_day=15,
        end_month=1,
        end_day=30,
        check_frequency_multiplier=12,  # Check every 2 hours
        enabled=True,
    ),

    # Double 12 (双十二): December 1-12
    PromotionPeriod(
        name="双十二",
        start_month=12,
        start_day=1,
        end_month=12,
        end_day=12,
        check_frequency_multiplier=12,  # Check every 2 hours
        enabled=True,
    ),

    # 38 Women's Day: March 1-8
    PromotionPeriod(
        name="38女神节",
        start_month=3,
        start_day=1,
        end_month=3,
        end_day=8,
        check_frequency_multiplier=6,  # Check every 4 hours
        enabled=True,
    ),

    # 99 Shopping Festival: September 1-9
    PromotionPeriod(
        name="99聚划算",
        start_month=9,
        start_day=1,
        end_month=9,
        end_day=9,
        check_frequency_multiplier=6,  # Check every 4 hours
        enabled=True,
    ),
]


class PromotionManager:
    """
    Manages promotional periods

    Determines current promotion status and check frequency adjustments.
    """

    def __init__(self, periods: Optional[List[PromotionPeriod]] = None):
        """
        Initialize promotion manager

        Args:
            periods: List of promotion periods (uses defaults if None)
        """
        self.periods = periods or DEFAULT_PROMOTION_PERIODS.copy()

    def is_promotion_period(self, check_date: Optional[date] = None) -> bool:
        """
        Check if current date is within any promotional period

        Args:
            check_date: Date to check (defaults to today)

        Returns:
            True if within a promotional period
        """
        return any(period.is_active(check_date) for period in self.periods)

    def get_active_promotions(self, check_date: Optional[date] = None) -> List[PromotionPeriod]:
        """
        Get list of currently active promotions

        Args:
            check_date: Date to check (defaults to today)

        Returns:
            List of active promotion periods
        """
        return [period for period in self.periods if period.is_active(check_date)]

    def get_check_interval_seconds(self, check_date: Optional[date] = None) -> int:
        """
        Get recommended price check interval in seconds

        During normal periods: 86400 (once per day)
        During promotions: Adjusted based on frequency multiplier

        Args:
            check_date: Date to check (defaults to today)

        Returns:
            Interval in seconds between price checks
        """
        active = self.get_active_promotions(check_date)

        if not active:
            # Normal period: once per day
            return 86400

        # Use the highest frequency multiplier among active promotions
        max_multiplier = max(p.check_frequency_multiplier for p in active)

        # Daily interval divided by multiplier
        # e.g., 86400 / 24 = 3600 (hourly)
        return 86400 // max_multiplier

    def get_batch_interval_seconds(self, check_date: Optional[date] = None) -> int:
        """
        Get recommended interval between batch requests

        During normal periods: 30 seconds
        During promotions: Reduced to minimize latency

        Args:
            check_date: Date to check (defaults to today)

        Returns:
            Interval in seconds between batch requests
        """
        if self.is_promotion_period(check_date):
            return 15  # Faster batch processing during promotions
        return 30

    def add_period(self, period: PromotionPeriod) -> None:
        """Add a custom promotional period"""
        self.periods.append(period)
        logger.info(f"Added promotional period: {period.name}")

    def remove_period(self, name: str) -> bool:
        """Remove a promotional period by name"""
        initial_count = len(self.periods)
        self.periods = [p for p in self.periods if p.name != name]
        removed = len(self.periods) < initial_count
        if removed:
            logger.info(f"Removed promotional period: {name}")
        return removed

    def enable_period(self, name: str) -> bool:
        """Enable a promotional period by name"""
        for period in self.periods:
            if period.name == name:
                period.enabled = True
                logger.info(f"Enabled promotional period: {name}")
                return True
        return False

    def disable_period(self, name: str) -> bool:
        """Disable a promotional period by name"""
        for period in self.periods:
            if period.name == name:
                period.enabled = False
                logger.info(f"Disabled promotional period: {name}")
                return True
        return False

    def get_period_info(self) -> List[dict]:
        """Get information about all promotional periods"""
        today = date.today()
        return [
            {
                "name": p.name,
                "start": f"{p.start_month}/{p.start_day}",
                "end": f"{p.end_month}/{p.end_day}",
                "frequency_multiplier": p.check_frequency_multiplier,
                "enabled": p.enabled,
                "is_active": p.is_active(today),
            }
            for p in self.periods
        ]


# Global manager instance
_promotion_manager: Optional[PromotionManager] = None


def get_promotion_manager() -> PromotionManager:
    """Get or create the global promotion manager"""
    global _promotion_manager
    if _promotion_manager is None:
        _promotion_manager = PromotionManager()
    return _promotion_manager


def is_promotion_period(check_date: Optional[date] = None) -> bool:
    """
    Convenience function to check if current date is within a promotional period

    Args:
        check_date: Date to check (defaults to today)

    Returns:
        True if within a promotional period
    """
    return get_promotion_manager().is_promotion_period(check_date)


def get_current_promotion_names() -> List[str]:
    """
    Get names of currently active promotions

    Returns:
        List of promotion names
    """
    return [p.name for p in get_promotion_manager().get_active_promotions()]
