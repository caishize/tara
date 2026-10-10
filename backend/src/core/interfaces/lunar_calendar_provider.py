"""
ILunarCalendarProvider interface.
"""
from abc import ABC, abstractmethod
from datetime import date
from typing import Tuple, Optional


class LunarCalendarError(Exception):
    """Exception raised by lunar calendar provider."""
    pass


class LunarDate:
    """Lunar date representation."""
    def __init__(self, year: int, month: int, day: int, is_leap: bool = False):
        self.year = year
        self.month = month
        self.day = day
        self.is_leap = is_leap

    def __repr__(self):
        leap = "闰" if self.is_leap else ""
        return f"{self.year}年{leap}{self.month}月{self.day}日"


class ILunarCalendarProvider(ABC):
    """Interface for lunar calendar conversion."""

    @abstractmethod
    async def solar_to_lunar(self, solar_date: date) -> LunarDate:
        """
        Convert solar (Gregorian) date to lunar date.

        Args:
            solar_date: Gregorian date

        Returns:
            LunarDate object
        """
        pass

    @abstractmethod
    async def lunar_to_solar(
        self,
        year: int,
        month: int,
        day: int,
        is_leap: bool = False
    ) -> date:
        """
        Convert lunar date to solar (Gregorian) date.

        Args:
            year: Lunar year
            month: Lunar month (1-12)
            day: Lunar day (1-30)
            is_leap: Whether it's a leap month

        Returns:
            Gregorian date
        """
        pass

    @abstractmethod
    async def get_leap_month(self, year: int) -> Optional[int]:
        """
        Get leap month for a given lunar year.

        Args:
            year: Lunar year

        Returns:
            Leap month number (1-12) or None if no leap month
        """
        pass
