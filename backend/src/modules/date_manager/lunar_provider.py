"""
LunarCalendarProvider implementation using LunarCalendar library.
"""
from datetime import date
from typing import Optional
from lunarcalendar import Converter, Lunar, Solar

from ...core.interfaces.lunar_calendar_provider import ILunarCalendarProvider, LunarDate


class LunarCalendarProvider(ILunarCalendarProvider):
    """Lunar calendar provider using LunarCalendar library."""

    async def solar_to_lunar(self, solar_date: date) -> LunarDate:
        """
        Convert solar (Gregorian) date to lunar date.

        Args:
            solar_date: Gregorian date

        Returns:
            LunarDate object
        """
        solar = Solar(solar_date.year, solar_date.month, solar_date.day)
        lunar = Converter.Solar2Lunar(solar)

        return LunarDate(
            year=lunar.year,
            month=lunar.month,
            day=lunar.day,
            is_leap=lunar.isleap
        )

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
        lunar = Lunar(year, month, day, isleap=is_leap)
        solar = Converter.Lunar2Solar(lunar)

        return date(solar.year, solar.month, solar.day)

    async def get_leap_month(self, year: int) -> Optional[int]:
        """
        Get leap month for a given lunar year.

        Args:
            year: Lunar year

        Returns:
            Leap month number (1-12) or None if no leap month
        """
        # LunarCalendar library doesn't have a direct API for this
        # We'll check each month to see if there's a leap month
        for month in range(1, 13):
            try:
                lunar = Lunar(year, month, 1, isleap=True)
                # If no exception, this month has a leap month
                return month
            except:
                continue
        return None


# Global instance
lunar_calendar_provider = LunarCalendarProvider()
