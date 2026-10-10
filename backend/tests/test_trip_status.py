"""Tests for unified trip status computation."""
from datetime import date

import pytest

from src.modules.trip.services.trip_status import (
    compute_trip_status,
    get_status_display,
    STATUS_DISPLAY_MAP,
)


# ---------------------------------------------------------------------------
# compute_trip_status — terminal states
# ---------------------------------------------------------------------------


class TestTerminalStates:
    """Terminal states (cancelled) are never overridden by date logic."""

    def test_cancelled_preserved_even_if_current(self):
        assert (
            compute_trip_status(
                "cancelled",
                date(2026, 2, 1),
                date(2026, 2, 10),
                today=date(2026, 2, 5),
            )
            == "cancelled"
        )

    def test_cancelled_preserved_even_if_past(self):
        assert (
            compute_trip_status(
                "cancelled",
                date(2026, 1, 1),
                date(2026, 1, 5),
                today=date(2026, 2, 1),
            )
            == "cancelled"
        )


# ---------------------------------------------------------------------------
# compute_trip_status — in_progress detection
# ---------------------------------------------------------------------------


class TestInProgress:
    """Trips where today falls within [start_date, end_date]."""

    def test_planning_becomes_in_progress(self):
        assert (
            compute_trip_status(
                "planning",
                date(2026, 2, 1),
                date(2026, 2, 10),
                today=date(2026, 2, 5),
            )
            == "in_progress"
        )

    def test_confirmed_becomes_in_progress(self):
        assert (
            compute_trip_status(
                "confirmed",
                date(2026, 2, 1),
                date(2026, 2, 10),
                today=date(2026, 2, 5),
            )
            == "in_progress"
        )

    def test_on_start_date_is_in_progress(self):
        assert (
            compute_trip_status(
                "planning",
                date(2026, 2, 5),
                date(2026, 2, 10),
                today=date(2026, 2, 5),
            )
            == "in_progress"
        )

    def test_on_end_date_is_in_progress(self):
        assert (
            compute_trip_status(
                "planning",
                date(2026, 2, 1),
                date(2026, 2, 5),
                today=date(2026, 2, 5),
            )
            == "in_progress"
        )

    def test_single_day_trip_on_that_day(self):
        assert (
            compute_trip_status(
                "planning",
                date(2026, 2, 5),
                date(2026, 2, 5),
                today=date(2026, 2, 5),
            )
            == "in_progress"
        )


# ---------------------------------------------------------------------------
# compute_trip_status — auto-complete past trips
# ---------------------------------------------------------------------------


class TestAutoComplete:
    """Trips past their end_date become completed."""

    def test_planning_becomes_completed(self):
        assert (
            compute_trip_status(
                "planning",
                date(2026, 1, 1),
                date(2026, 1, 5),
                today=date(2026, 2, 1),
            )
            == "completed"
        )

    def test_confirmed_becomes_completed(self):
        assert (
            compute_trip_status(
                "confirmed",
                date(2026, 1, 1),
                date(2026, 1, 5),
                today=date(2026, 2, 1),
            )
            == "completed"
        )

    def test_day_after_end_date(self):
        assert (
            compute_trip_status(
                "planning",
                date(2026, 2, 1),
                date(2026, 2, 5),
                today=date(2026, 2, 6),
            )
            == "completed"
        )


# ---------------------------------------------------------------------------
# compute_trip_status — future trips (no override)
# ---------------------------------------------------------------------------


class TestFutureTrips:
    """Future trips retain their stored status."""

    def test_planning_preserved(self):
        assert (
            compute_trip_status(
                "planning",
                date(2026, 3, 1),
                date(2026, 3, 5),
                today=date(2026, 2, 1),
            )
            == "planning"
        )

    def test_confirmed_preserved(self):
        assert (
            compute_trip_status(
                "confirmed",
                date(2026, 3, 1),
                date(2026, 3, 5),
                today=date(2026, 2, 1),
            )
            == "confirmed"
        )


# ---------------------------------------------------------------------------
# compute_trip_status — edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Handle None dates and unexpected values gracefully."""

    def test_none_start_date(self):
        assert compute_trip_status("planning", None, date(2026, 3, 5)) == "planning"

    def test_none_end_date(self):
        assert compute_trip_status("planning", date(2026, 3, 1), None) == "planning"

    def test_both_none(self):
        assert compute_trip_status("confirmed", None, None) == "confirmed"

    def test_unknown_status_preserved(self):
        assert (
            compute_trip_status(
                "pending",
                date(2026, 3, 1),
                date(2026, 3, 5),
                today=date(2026, 2, 1),
            )
            == "pending"
        )

    def test_empty_string_status(self):
        assert (
            compute_trip_status(
                "",
                date(2026, 2, 1),
                date(2026, 2, 10),
                today=date(2026, 2, 5),
            )
            == "in_progress"
        )


# ---------------------------------------------------------------------------
# get_status_display
# ---------------------------------------------------------------------------


class TestStatusDisplay:
    """Chinese display labels for status strings."""

    def test_all_known_statuses(self):
        assert get_status_display("planning") == "准备中"
        assert get_status_display("confirmed") == "已确认"
        assert get_status_display("in_progress") == "旅途中"
        assert get_status_display("completed") == "已结束"
        assert get_status_display("cancelled") == "已取消"

    def test_unknown_status_returns_raw(self):
        assert get_status_display("pending") == "pending"
        assert get_status_display("draft") == "draft"

    def test_display_map_completeness(self):
        expected = {"planning", "confirmed", "in_progress", "completed", "cancelled"}
        assert set(STATUS_DISPLAY_MAP.keys()) == expected
