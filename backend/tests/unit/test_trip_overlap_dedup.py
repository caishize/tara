"""
Unit tests for trip overlap dedup logic.

Tests the pure helper functions in curation_dedup.py:
- _cluster_by_date_proximity
- _pick_best_trip

And the async _dedup_overlapping_trips method (via mock DB session).
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from typing import Optional

from src.modules.curation.services.dedup_service import (
    _cluster_by_date_proximity,
    _pick_best_trip,
)


def _make_trip(
    destination: str = "东京",
    start: Optional[date] = None,
    end: Optional[date] = None,
    status: str = "planning",
    description: str = "",
    trip_name: str = "",
    updated_at: Optional[datetime] = None,
) -> SimpleNamespace:
    """Create a minimal TripPlan-like object for testing."""
    return SimpleNamespace(
        trip_id=uuid4(),
        destination=destination,
        start_date=start or date(2026, 3, 1),
        end_date=end or date(2026, 3, 5),
        status=status,
        description=description,
        trip_name=trip_name,
        updated_at=updated_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        notes=None,
    )


# ============================================================
# _cluster_by_date_proximity
# ============================================================


class TestClusterByDateProximity:
    """Tests for the sweep-line clustering algorithm."""

    def test_single_trip_returns_one_cluster(self):
        t = _make_trip(start=date(2026, 3, 1), end=date(2026, 3, 5))
        clusters = _cluster_by_date_proximity([t], proximity_days=3)
        assert len(clusters) == 1
        assert clusters[0] == [t]

    def test_overlapping_trips_same_cluster(self):
        t1 = _make_trip(start=date(2026, 3, 1), end=date(2026, 3, 5))
        t2 = _make_trip(start=date(2026, 3, 3), end=date(2026, 3, 8))
        clusters = _cluster_by_date_proximity([t1, t2], proximity_days=3)
        assert len(clusters) == 1
        assert len(clusters[0]) == 2

    def test_near_overlapping_trips_within_window(self):
        """Trips 2 days apart should cluster with proximity_days=3."""
        t1 = _make_trip(start=date(2026, 3, 1), end=date(2026, 3, 5))
        t2 = _make_trip(start=date(2026, 3, 7), end=date(2026, 3, 10))
        clusters = _cluster_by_date_proximity([t1, t2], proximity_days=3)
        assert len(clusters) == 1

    def test_distant_trips_separate_clusters(self):
        """Trips >proximity_days apart should be separate clusters."""
        t1 = _make_trip(start=date(2026, 3, 1), end=date(2026, 3, 5))
        t2 = _make_trip(start=date(2026, 3, 15), end=date(2026, 3, 20))
        clusters = _cluster_by_date_proximity([t1, t2], proximity_days=3)
        assert len(clusters) == 2
        assert clusters[0] == [t1]
        assert clusters[1] == [t2]

    def test_exactly_at_boundary(self):
        """Trip starting exactly proximity_days after previous end."""
        t1 = _make_trip(start=date(2026, 3, 1), end=date(2026, 3, 5))
        t2 = _make_trip(start=date(2026, 3, 8), end=date(2026, 3, 12))
        # Gap = 3 days (Mar 5 → Mar 8), proximity_days=3 → should cluster
        clusters = _cluster_by_date_proximity([t1, t2], proximity_days=3)
        assert len(clusters) == 1

    def test_one_day_past_boundary(self):
        """Trip starting proximity_days+1 after previous end."""
        t1 = _make_trip(start=date(2026, 3, 1), end=date(2026, 3, 5))
        t2 = _make_trip(start=date(2026, 3, 9), end=date(2026, 3, 12))
        # Gap = 4 days (Mar 5 → Mar 9), proximity_days=3 → separate
        clusters = _cluster_by_date_proximity([t1, t2], proximity_days=3)
        assert len(clusters) == 2

    def test_three_trips_chained(self):
        """Three trips that chain together into one cluster."""
        t1 = _make_trip(start=date(2026, 3, 1), end=date(2026, 3, 5))
        t2 = _make_trip(start=date(2026, 3, 7), end=date(2026, 3, 10))
        t3 = _make_trip(start=date(2026, 3, 12), end=date(2026, 3, 15))
        clusters = _cluster_by_date_proximity([t1, t2, t3], proximity_days=3)
        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_unsorted_input(self):
        """Input order shouldn't matter — sorting happens internally."""
        t1 = _make_trip(start=date(2026, 3, 15), end=date(2026, 3, 20))
        t2 = _make_trip(start=date(2026, 3, 1), end=date(2026, 3, 5))
        clusters = _cluster_by_date_proximity([t1, t2], proximity_days=3)
        assert len(clusters) == 2
        # First cluster should be the earlier trip
        assert clusters[0][0].start_date == date(2026, 3, 1)

    def test_zero_proximity(self):
        """With proximity_days=0, only strictly overlapping trips cluster."""
        t1 = _make_trip(start=date(2026, 3, 1), end=date(2026, 3, 5))
        t2 = _make_trip(start=date(2026, 3, 6), end=date(2026, 3, 10))
        clusters = _cluster_by_date_proximity([t1, t2], proximity_days=0)
        assert len(clusters) == 2

    def test_empty_input(self):
        clusters = _cluster_by_date_proximity([], proximity_days=3)
        assert clusters == []


# ============================================================
# _pick_best_trip
# ============================================================


class TestPickBestTrip:
    """Tests for the trip selection priority logic."""

    def test_confirmed_beats_planning(self):
        t_planning = _make_trip(status="planning")
        t_confirmed = _make_trip(status="confirmed")
        best = _pick_best_trip([t_planning, t_confirmed])
        assert best is t_confirmed

    def test_in_progress_beats_planning(self):
        t_planning = _make_trip(status="planning")
        t_active = _make_trip(status="in_progress")
        best = _pick_best_trip([t_planning, t_active])
        assert best is t_active

    def test_longer_trip_wins_same_status(self):
        t_short = _make_trip(
            start=date(2026, 3, 1), end=date(2026, 3, 3), status="planning"
        )
        t_long = _make_trip(
            start=date(2026, 3, 1), end=date(2026, 3, 8), status="planning"
        )
        best = _pick_best_trip([t_short, t_long])
        assert best is t_long

    def test_more_description_wins_same_duration(self):
        t_sparse = _make_trip(
            start=date(2026, 3, 1),
            end=date(2026, 3, 5),
            description="short",
        )
        t_rich = _make_trip(
            start=date(2026, 3, 1),
            end=date(2026, 3, 5),
            description="a much more detailed travel plan with itinerary",
        )
        best = _pick_best_trip([t_sparse, t_rich])
        assert best is t_rich

    def test_most_recently_updated_wins_as_tiebreaker(self):
        t_old = _make_trip(
            start=date(2026, 3, 1),
            end=date(2026, 3, 5),
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        t_new = _make_trip(
            start=date(2026, 3, 1),
            end=date(2026, 3, 5),
            updated_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        best = _pick_best_trip([t_old, t_new])
        assert best is t_new


# ============================================================
# _dedup_overlapping_trips (async, requires mock session)
# ============================================================


class TestDedupOverlappingTrips:
    """Integration-style tests for the full dedup method."""

    def _make_mixin(self):
        """Create a minimal mixin instance with a mock DB session."""
        from src.modules.curation.services.dedup_service import CurationDedupMixin

        mixin = CurationDedupMixin()
        mixin.session = AsyncMock()
        mixin.session.execute = AsyncMock()
        mixin.session.flush = AsyncMock()
        return mixin

    @pytest.mark.asyncio
    async def test_no_duplicates_returns_all(self):
        mixin = self._make_mixin()
        t1 = _make_trip(destination="东京", start=date(2026, 3, 1), end=date(2026, 3, 5))
        t2 = _make_trip(destination="大阪", start=date(2026, 3, 1), end=date(2026, 3, 5))
        result = await mixin._dedup_overlapping_trips([t1, t2])
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_overlapping_same_dest_cancels_loser(self):
        mixin = self._make_mixin()
        t_short = _make_trip(
            destination="东京",
            start=date(2026, 3, 1),
            end=date(2026, 3, 3),
            description="short",
        )
        t_long = _make_trip(
            destination="东京",
            start=date(2026, 3, 2),
            end=date(2026, 3, 8),
            description="detailed plan",
        )
        result = await mixin._dedup_overlapping_trips([t_short, t_long])
        assert len(result) == 1
        assert result[0] is t_long
        assert t_short.status == "cancelled"

    @pytest.mark.asyncio
    async def test_near_overlapping_trips_merged(self):
        mixin = self._make_mixin()
        t1 = _make_trip(
            destination="东京",
            start=date(2026, 3, 1),
            end=date(2026, 3, 5),
        )
        t2 = _make_trip(
            destination="东京",
            start=date(2026, 3, 7),
            end=date(2026, 3, 10),
        )
        result = await mixin._dedup_overlapping_trips([t1, t2], proximity_days=3)
        assert len(result) == 1
        # Winner's date range should cover both
        winner = result[0]
        assert winner.start_date == date(2026, 3, 1)
        assert winner.end_date == date(2026, 3, 10)

    @pytest.mark.asyncio
    async def test_confirmed_trip_absorbs_planning(self):
        mixin = self._make_mixin()
        t_planning = _make_trip(
            destination="东京",
            start=date(2026, 3, 1),
            end=date(2026, 3, 8),
            status="planning",
            description="very long detailed description of the trip",
        )
        t_confirmed = _make_trip(
            destination="东京",
            start=date(2026, 3, 2),
            end=date(2026, 3, 5),
            status="confirmed",
            description="",
        )
        result = await mixin._dedup_overlapping_trips([t_planning, t_confirmed])
        assert len(result) == 1
        assert result[0] is t_confirmed  # confirmed always wins
        assert t_planning.status == "cancelled"
        # Confirmed trip's dates extended
        assert t_confirmed.start_date == date(2026, 3, 1)
        assert t_confirmed.end_date == date(2026, 3, 8)

    @pytest.mark.asyncio
    async def test_different_destinations_kept_separate(self):
        mixin = self._make_mixin()
        t1 = _make_trip(destination="东京", start=date(2026, 3, 1), end=date(2026, 3, 5))
        t2 = _make_trip(destination="大阪", start=date(2026, 3, 2), end=date(2026, 3, 6))
        result = await mixin._dedup_overlapping_trips([t1, t2])
        assert len(result) == 2
        # Neither should be cancelled
        assert t1.status == "planning"
        assert t2.status == "planning"

    @pytest.mark.asyncio
    async def test_empty_input(self):
        mixin = self._make_mixin()
        result = await mixin._dedup_overlapping_trips([])
        assert result == []

    @pytest.mark.asyncio
    async def test_case_insensitive_destination(self):
        mixin = self._make_mixin()
        t1 = _make_trip(
            destination="Tokyo",
            start=date(2026, 3, 1),
            end=date(2026, 3, 5),
        )
        t2 = _make_trip(
            destination="tokyo",
            start=date(2026, 3, 3),
            end=date(2026, 3, 8),
        )
        result = await mixin._dedup_overlapping_trips([t1, t2])
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_curated_events_deactivated_on_cancel(self):
        """Cancelled trips should trigger deactivation of their curated_events."""
        mixin = self._make_mixin()
        t1 = _make_trip(
            destination="东京",
            start=date(2026, 3, 1),
            end=date(2026, 3, 3),
        )
        t2 = _make_trip(
            destination="东京",
            start=date(2026, 3, 2),
            end=date(2026, 3, 8),
        )
        await mixin._dedup_overlapping_trips([t1, t2])
        # session.execute should have been called (for the UPDATE on curated_events)
        assert mixin.session.execute.called
        assert mixin.session.flush.called
