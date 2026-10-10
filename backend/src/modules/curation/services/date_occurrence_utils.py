"""
Shared utility for calculating next occurrences of important dates.

Used by both curation and briefing modules to
ensure consistent date handling across the codebase.
"""
import calendar
from datetime import date
from typing import Optional, Protocol


# Holiday date types that have separate DB records per year
HOLIDAY_DATE_TYPES = frozenset({
    "holiday_legal",
    "holiday_lunar",
    "holiday_solar_term",
    "holiday",
})


class ImportantDateLike(Protocol):
    """Structural type for any object with important date fields."""

    solar_date: Optional[date]
    is_recurring: bool
    is_lunar: bool
    date_type: str


def safe_date_for_year(year: int, month: int, day: int) -> date:
    """Safely create a date, handling Feb 29 in non-leap years."""
    if month == 2 and day == 29 and not calendar.isleap(year):
        return date(year, 2, 28)
    return date(year, month, day)


def calculate_next_occurrence(
    imp_date: ImportantDateLike,
    start_date: date,
    end_date: date,
) -> Optional[date]:
    """Calculate the next occurrence of an important date within a range."""
    if not imp_date.solar_date:
        return None

    base_date = imp_date.solar_date

    # Lunar calendar events have pre-calculated solar equivalents per year.
    if imp_date.is_lunar:
        if start_date <= base_date <= end_date:
            return base_date
        return None

    # Holiday types store separate records for each year.
    if imp_date.date_type in HOLIDAY_DATE_TYPES:
        if start_date <= base_date <= end_date:
            return base_date
        return None

    # Solar recurring events: calculate this year / next year occurrence.
    if imp_date.is_recurring:
        this_year = safe_date_for_year(
            start_date.year, base_date.month, base_date.day
        )
        if start_date <= this_year <= end_date:
            return this_year

        next_year = safe_date_for_year(
            start_date.year + 1, base_date.month, base_date.day
        )
        if start_date <= next_year <= end_date:
            return next_year

        return None

    # Non-recurring (one-time) events
    if start_date <= base_date <= end_date:
        return base_date
    return None
