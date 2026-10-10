"""Unified trip status computation.

Provides a single pure function that derives the effective display status
from the stored DB status and trip date range.  All views (chat, graph,
kanban, briefing) should call this instead of returning raw DB status.
"""
from datetime import date
from typing import Dict, Optional


# Chinese display labels for each status
STATUS_DISPLAY_MAP: Dict[str, str] = {
    "planning": "准备中",
    "confirmed": "已确认",
    "in_progress": "旅途中",
    "completed": "已结束",
    "cancelled": "已取消",
}


def compute_trip_status(
    stored_status: str,
    start_date: Optional[date],
    end_date: Optional[date],
    *,
    today: Optional[date] = None,
) -> str:
    """Derive the effective trip status from stored status + date range.

    Rules (highest priority first):
    1. Terminal states (cancelled, completed) are preserved as-is.
    2. If today falls within [start_date, end_date] -> "in_progress".
    3. If today is past end_date -> "completed".
    4. Otherwise -> stored_status unchanged (e.g. "planning", "confirmed").

    Args:
        stored_status: The raw status value from the database.
        start_date: Trip start date (may be None for incomplete data).
        end_date: Trip end date (may be None for incomplete data).
        today: Override for the current date (useful for testing).

    Returns:
        The effective status string.
    """
    if stored_status in ("cancelled",):
        return stored_status

    if start_date is None or end_date is None:
        return stored_status

    if today is None:
        today = date.today()

    if start_date <= today <= end_date:
        return "in_progress"

    if today > end_date:
        return "completed"

    return stored_status


def get_status_display(status: str) -> str:
    """Return the Chinese display label for a trip status."""
    return STATUS_DISPLAY_MAP.get(status, status)
