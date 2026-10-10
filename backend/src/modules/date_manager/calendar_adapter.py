"""
Calendar Adapter - Fetches Chinese holidays from multiple sources.

Data sources:
1. Local calculation using lunarcalendar library (for lunar holidays and solar terms)
2. Baidu Open Calendar API (for legal holidays and work-rest arrangements)

Supports:
- Legal holidays (法定节假日) with work-rest arrangements
- Lunar holidays (农历节日)
- 24 Solar terms (二十四节气)

Moved from adapters/calendar/baidu_calendar_adapter.py into date_manager module.
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import httpx
import lunarcalendar
from functools import lru_cache

from ...config.logging import get_logger


logger = get_logger(__name__)


class HolidayType(str, Enum):
    """Type of holiday."""
    LEGAL = "legal"  # 法定节假日
    LUNAR = "lunar"  # 农历节日
    SOLAR_TERM = "solar_term"  # 二十四节气


@dataclass
class HolidayData:
    """Standardized holiday data structure."""
    name: str
    holiday_type: HolidayType
    date: date
    is_work_day: bool = False  # True if it's a work day during holiday period (调休)
    is_off_day: bool = True  # True if it's a day off
    description: Optional[str] = None
    lunar_date: Optional[str] = None  # e.g., "正月初一"
    source: str = "local"
    metadata: Dict[str, Any] = field(default_factory=dict)


# 24 Solar Terms with approximate dates (month, day ranges)
# Solar terms are calculated based on the sun's position, these are approximate
SOLAR_TERM_APPROXIMATE_DATES = {
    "立春": (2, 3, 5),
    "雨水": (2, 18, 20),
    "惊蛰": (3, 5, 7),
    "春分": (3, 20, 22),
    "清明": (4, 4, 6),
    "谷雨": (4, 19, 21),
    "立夏": (5, 5, 7),
    "小满": (5, 20, 22),
    "芒种": (6, 5, 7),
    "夏至": (6, 21, 22),
    "小暑": (7, 6, 8),
    "大暑": (7, 22, 24),
    "立秋": (8, 7, 9),
    "处暑": (8, 22, 24),
    "白露": (9, 7, 9),
    "秋分": (9, 22, 24),
    "寒露": (10, 8, 9),
    "霜降": (10, 23, 24),
    "立冬": (11, 7, 8),
    "小雪": (11, 22, 23),
    "大雪": (12, 6, 8),
    "冬至": (12, 21, 23),
    "小寒": (1, 5, 7),
    "大寒": (1, 20, 21),
}

# Lunar holidays with their lunar month and day
# Note: 春节, 端午节, 中秋节 are handled in _get_legal_holidays() to avoid duplicates
LUNAR_HOLIDAYS_CONFIG = {
    "元宵节": (1, 15),  # 正月十五
    "龙抬头": (2, 2),  # 二月初二
    "七夕节": (7, 7),  # 七月初七
    "中元节": (7, 15),  # 七月十五
    "重阳节": (9, 9),  # 九月初九
    "腊八节": (12, 8),  # 腊月初八
    "小年": (12, 23),  # 腊月二十三 (北方)
    "除夕": (12, 30),  # 腊月三十 (or 二十九 in some years)
}

# Legal holidays (法定节假日) - Fixed dates
LEGAL_HOLIDAYS_CONFIG = {
    "元旦": (1, 1),
    "劳动节": (5, 1),
    "国庆节": (10, 1),
}

# Lunar number mapping
LUNAR_MONTH_NAMES = {
    1: "正月", 2: "二月", 3: "三月", 4: "四月", 5: "五月", 6: "六月",
    7: "七月", 8: "八月", 9: "九月", 10: "十月", 11: "十一月", 12: "腊月"
}

LUNAR_DAY_NAMES = {
    1: "初一", 2: "初二", 3: "初三", 4: "初四", 5: "初五",
    6: "初六", 7: "初七", 8: "初八", 9: "初九", 10: "初十",
    11: "十一", 12: "十二", 13: "十三", 14: "十四", 15: "十五",
    16: "十六", 17: "十七", 18: "十八", 19: "十九", 20: "二十",
    21: "廿一", 22: "廿二", 23: "廿三", 24: "廿四", 25: "廿五",
    26: "廿六", 27: "廿七", 28: "廿八", 29: "廿九", 30: "三十"
}


class BaiduCalendarAdapter:
    """
    Calendar adapter for fetching Chinese holidays.

    Uses local calculation for lunar dates and solar terms,
    and optionally Baidu API for work-rest arrangements.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize the adapter.

        Args:
            api_key: Optional Baidu API key for fetching work-rest info
            timeout: HTTP request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def fetch_holidays(
        self,
        year: int,
        holiday_types: Optional[List[HolidayType]] = None,
    ) -> List[HolidayData]:
        """
        Fetch all holidays for a given year.

        Args:
            year: The year to fetch holidays for
            holiday_types: Optional list of holiday types to fetch
                          (defaults to all types)

        Returns:
            List of HolidayData objects
        """
        if holiday_types is None:
            holiday_types = list(HolidayType)

        holidays: List[HolidayData] = []

        if HolidayType.LEGAL in holiday_types:
            legal_holidays = await self._get_legal_holidays(year)
            holidays.extend(legal_holidays)

        if HolidayType.LUNAR in holiday_types:
            lunar_holidays = await self._get_lunar_holidays(year)
            holidays.extend(lunar_holidays)

        if HolidayType.SOLAR_TERM in holiday_types:
            solar_terms = await self._get_solar_terms(year)
            holidays.extend(solar_terms)

        # Sort by date
        holidays.sort(key=lambda h: h.date)

        logger.info(f"Fetched {len(holidays)} holidays for year {year}")
        return holidays

    async def _get_legal_holidays(self, year: int) -> List[HolidayData]:
        """Get legal/public holidays for a year."""
        holidays = []

        for name, (month, day) in LEGAL_HOLIDAYS_CONFIG.items():
            holiday_date = date(year, month, day)
            holidays.append(HolidayData(
                name=name,
                holiday_type=HolidayType.LEGAL,
                date=holiday_date,
                is_off_day=True,
                is_work_day=False,
                description=f"{year}年{name}",
                source="local",
            ))

        # Add lunar-based legal holidays (春节, 清明, 端午, 中秋)
        # These are derived from lunar calendar
        lunar_legal_holidays = {
            "春节": (1, 1),  # Lunar New Year
            "清明节": None,  # Solar term - handled separately
            "端午节": (5, 5),
            "中秋节": (8, 15),
        }

        for name, lunar_date in lunar_legal_holidays.items():
            if lunar_date is None:
                continue  # Skip solar term based holidays

            try:
                lunar_month, lunar_day = lunar_date
                # Convert lunar to solar date using to_date() which returns datetime.date
                lunar = lunarcalendar.Lunar(year, lunar_month, lunar_day)
                holiday_date = lunar.to_date()

                lunar_date_str = f"{LUNAR_MONTH_NAMES.get(lunar_month, str(lunar_month))}{LUNAR_DAY_NAMES.get(lunar_day, str(lunar_day))}"

                holidays.append(HolidayData(
                    name=name,
                    holiday_type=HolidayType.LEGAL,
                    date=holiday_date,
                    is_off_day=True,
                    is_work_day=False,
                    lunar_date=lunar_date_str,
                    description=f"{year}年{name}",
                    source="local",
                ))
            except Exception as e:
                logger.warning(f"Failed to calculate {name} for year {year}: {e}")

        # Add Qingming (清明) - it's a solar term
        qingming_date = self._calculate_solar_term_date(year, "清明")
        if qingming_date:
            holidays.append(HolidayData(
                name="清明节",
                holiday_type=HolidayType.LEGAL,
                date=qingming_date,
                is_off_day=True,
                is_work_day=False,
                description=f"{year}年清明节",
                source="local",
            ))

        return holidays

    async def _get_lunar_holidays(self, year: int) -> List[HolidayData]:
        """Get lunar calendar holidays for a year."""
        holidays = []

        for name, (lunar_month, lunar_day) in LUNAR_HOLIDAYS_CONFIG.items():
            try:
                # Handle 除夕 (New Year's Eve) specially
                if name == "除夕":
                    # It's the last day of lunar year, which could be 29 or 30
                    # To get 除夕 for year X, we need to get 春节 of year X+1
                    # and go back 1 day (除夕 is always 1 day before 春节)
                    lunar_new_year = lunarcalendar.Lunar(year + 1, 1, 1)
                    new_year_date = lunar_new_year.to_date()
                    holiday_date = new_year_date - timedelta(days=1)
                    # Determine actual lunar day (could be 29 or 30)
                    try:
                        lunar_chuxi = lunarcalendar.Converter.Solar2Lunar(
                            lunarcalendar.Solar(holiday_date.year, holiday_date.month, holiday_date.day)
                        )
                        lunar_date_str = f"腊月{LUNAR_DAY_NAMES.get(lunar_chuxi.day, str(lunar_chuxi.day))}"
                    except Exception:
                        lunar_date_str = "腊月三十"
                else:
                    lunar = lunarcalendar.Lunar(year, lunar_month, lunar_day)
                    holiday_date = lunar.to_date()
                    lunar_date_str = f"{LUNAR_MONTH_NAMES.get(lunar_month, str(lunar_month))}{LUNAR_DAY_NAMES.get(lunar_day, str(lunar_day))}"

                holidays.append(HolidayData(
                    name=name,
                    holiday_type=HolidayType.LUNAR,
                    date=holiday_date,
                    is_off_day=True,
                    is_work_day=False,
                    lunar_date=lunar_date_str,
                    description=f"{year}年{name}（{lunar_date_str}）",
                    source="local",
                ))
            except Exception as e:
                logger.warning(f"Failed to calculate {name} for year {year}: {e}")

        return holidays

    async def _get_solar_terms(self, year: int) -> List[HolidayData]:
        """Get 24 solar terms for a year."""
        holidays = []

        for term_name in SOLAR_TERM_APPROXIMATE_DATES.keys():
            term_date = self._calculate_solar_term_date(year, term_name)
            if term_date:
                holidays.append(HolidayData(
                    name=term_name,
                    holiday_type=HolidayType.SOLAR_TERM,
                    date=term_date,
                    is_off_day=False,  # Solar terms are not holidays
                    is_work_day=False,
                    description=f"{year}年{term_name}",
                    source="local",
                ))

        return holidays

    def _calculate_solar_term_date(self, year: int, term_name: str) -> Optional[date]:
        """
        Calculate the date of a solar term.

        Uses approximate calculation based on typical dates.
        For more accuracy, an astronomical library should be used.
        """
        if term_name not in SOLAR_TERM_APPROXIMATE_DATES:
            return None

        month, day_start, day_end = SOLAR_TERM_APPROXIMATE_DATES[term_name]
        # Use middle of the range as approximate date
        approx_day = (day_start + day_end) // 2

        try:
            # Handle terms that span year boundary (小寒, 大寒 are in January)
            return date(year, month, approx_day)
        except ValueError:
            # Handle invalid date (e.g., Feb 30)
            return date(year, month, day_start)

    async def fetch_work_rest_days(self, year: int) -> Dict[date, bool]:
        """
        Fetch work-rest day arrangements from Baidu API.

        Returns a dict mapping dates to whether they are work days.
        True = work day (调休上班), False = day off.

        Note: This requires a valid Baidu API key.
        """
        if not self.api_key:
            logger.debug("No Baidu API key configured, skipping work-rest fetch")
            return {}

        # TODO: Implement Baidu API call for work-rest arrangements
        # The API endpoint and format depend on the specific Baidu service
        # For now, return empty dict
        logger.info(f"Work-rest day fetch not implemented yet for year {year}")
        return {}


# Global adapter instance
baidu_calendar_adapter = BaiduCalendarAdapter()
