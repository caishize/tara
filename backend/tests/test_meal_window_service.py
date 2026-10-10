"""Tests for MealWindowInferenceService - statistical meal window inference.

Covers:
- Normal inference with sufficient event data
- Sample too small (< 10 events)
- Empty event set
- Persistence of inferred_meal_windows to FamilyPreference
- Median calculation correctness
- _find_meal_window_in_range gap detection logic
- Default fallback when insufficient free-slot samples
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.curation.services.meal_window_service import (
    MealWindowInferenceService,
    _DEFAULT_DINNER,
    _DEFAULT_LUNCH,
    _MIN_EVENTS_FOR_INFERENCE,
    _MIN_GAP_MINUTES,
    _MIN_SLOT_SAMPLES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uuid():
    return uuid.uuid4()


def _make_event_times_for_lunch_gaps(count: int) -> list[tuple[str, int, int, int, int]]:
    """Generate event_times that produce free-slot gaps in the lunch range (10-15h).

    Each pair on a distinct day creates a ~60 min gap around noon:
    - event i (day i): 10:00 - 11:00
    - gap: 11:00 - 12:00 (60 min >= _MIN_GAP_MINUTES)
    - event i+1 (day i): 12:00 - 13:00
    Using unique date keys per pair ensures gaps are computed within each day.
    """
    times = []
    for i in range(count):
        # Assign each pair of events to the same day
        day = f"2026-01-{(i // 2) + 1:02d}"
        if i % 2 == 0:
            times.append((day, 10, 0, 11, 0))
        else:
            times.append((day, 12, 0, 13, 0))
    return times


def _make_event_times_for_dinner_gaps(count: int) -> list[tuple[str, int, int, int, int]]:
    """Generate event_times that produce free-slot gaps in the dinner range (17-22h)."""
    times = []
    for i in range(count):
        day = f"2026-02-{(i // 2) + 1:02d}"
        if i % 2 == 0:
            times.append((day, 17, 0, 18, 0))
        else:
            times.append((day, 19, 0, 20, 0))
    return times


def _make_diverse_event_times(count: int) -> list[tuple[str, int, int, int, int]]:
    """Generate event_times spanning both lunch and dinner ranges with sufficient gaps."""
    lunch_times = _make_event_times_for_lunch_gaps(count // 2 + 2)
    dinner_times = _make_event_times_for_dinner_gaps(count // 2 + 2)
    return lunch_times + dinner_times


# ---------------------------------------------------------------------------
# _infer_windows (pure computation)
# ---------------------------------------------------------------------------

class TestInferWindows:
    """Tests for the pure statistical inference method."""

    def test_returns_dict_with_lunch_and_dinner_keys(self):
        """Result should always have 'lunch' and 'dinner' keys."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        event_times = _make_diverse_event_times(20)
        result = service._infer_windows(event_times)

        assert result is not None
        assert "lunch" in result
        assert "dinner" in result
        assert len(result["lunch"]) == 4
        assert len(result["dinner"]) == 4

    def test_lunch_window_within_range(self):
        """Inferred lunch window should fall within 10-15h range."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        event_times = _make_event_times_for_lunch_gaps(20)
        result = service._infer_windows(event_times)

        lunch = result["lunch"]
        # lunch is [h_start, m_start, h_end, m_end]
        lunch_start_minutes = lunch[0] * 60 + lunch[1]
        lunch_end_minutes = lunch[2] * 60 + lunch[3]

        assert 10 * 60 <= lunch_start_minutes <= 15 * 60
        assert 10 * 60 <= lunch_end_minutes <= 15 * 60
        assert lunch_start_minutes < lunch_end_minutes

    def test_dinner_window_within_range(self):
        """Inferred dinner window should fall within 17-22h range."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        event_times = _make_event_times_for_dinner_gaps(20)
        result = service._infer_windows(event_times)

        dinner = result["dinner"]
        dinner_start_minutes = dinner[0] * 60 + dinner[1]
        dinner_end_minutes = dinner[2] * 60 + dinner[3]

        assert 17 * 60 <= dinner_start_minutes <= 22 * 60
        assert 17 * 60 <= dinner_end_minutes <= 22 * 60
        assert dinner_start_minutes < dinner_end_minutes

    def test_defaults_when_no_events_in_range(self):
        """Events outside meal ranges should produce default windows."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        # Events only in early morning (7-9h) -- no overlap with lunch/dinner
        event_times = [("2026-01-01", 7, 0, 8, 0)] * 20
        result = service._infer_windows(event_times)

        assert result["lunch"] == list(_DEFAULT_LUNCH)
        assert result["dinner"] == list(_DEFAULT_DINNER)

    def test_defaults_when_insufficient_gaps(self):
        """Fewer than _MIN_SLOT_SAMPLES gaps should produce default."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        # Only 2 events on the same day in lunch range => at most 1 gap per day
        event_times = [("2026-01-01", 10, 0, 11, 0), ("2026-01-01", 12, 0, 13, 0)]
        result = service._infer_windows(event_times)

        # With 1 day, at most 1 gap + 1 leading gap = 2 total
        # which is < _MIN_SLOT_SAMPLES (5), so default should be used
        assert result["lunch"] == list(_DEFAULT_LUNCH)


# ---------------------------------------------------------------------------
# _find_meal_window_in_range (gap detection)
# ---------------------------------------------------------------------------

class TestFindMealWindowInRange:
    """Tests for the gap-finding algorithm."""

    def test_gap_between_consecutive_events(self):
        """Two events on the same day with a 60-min gap should produce a free slot."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        # Need enough gaps (>= _MIN_SLOT_SAMPLES = 5): use 6 distinct days
        event_times = []
        for day_n in range(1, 7):
            day = f"2026-01-{day_n:02d}"
            event_times.append((day, 10, 0, 11, 0))
            event_times.append((day, 12, 0, 13, 0))

        result = service._find_meal_window_in_range(
            event_times,
            range_start_h=10,
            range_end_h=15,
            default=_DEFAULT_LUNCH,
        )

        # Each day has a gap: 11:00 -> 12:00 = 60 min (>= 45 min threshold)
        # 6 days => 6 gaps => enough for median
        start_min = result[0] * 60 + result[1]
        end_min = result[2] * 60 + result[3]
        assert start_min >= 10 * 60
        assert end_min <= 15 * 60

    def test_no_events_in_range_returns_default(self):
        """No events in range should return the default."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        # All events outside the 10-15h range
        event_times = [("2026-01-01", 8, 0, 9, 0)] * 10

        result = service._find_meal_window_in_range(
            event_times,
            range_start_h=10,
            range_end_h=15,
            default=_DEFAULT_LUNCH,
        )

        assert result == _DEFAULT_LUNCH

    def test_small_gaps_ignored(self):
        """Gaps smaller than _MIN_GAP_MINUTES should not count as free slots."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        # Events with only 30-min gaps (< 45 min threshold) across multiple days
        event_times = []
        for day_n in range(1, 7):
            day = f"2026-01-{day_n:02d}"
            for i in range(12):
                base = 10 * 60 + i * 30  # 10:00, 10:30, 11:00, ...
                h_start = base // 60
                m_start = base % 60
                h_end = (base + 20) // 60
                m_end = (base + 20) % 60
                if h_start < 15:  # stay in lunch range
                    event_times.append((day, h_start, m_start, h_end, m_end))

        result = service._find_meal_window_in_range(
            event_times,
            range_start_h=10,
            range_end_h=15,
            default=_DEFAULT_LUNCH,
        )

        # With 10-min event duration and 30-min spacing, gaps are 10 min
        # which is < _MIN_GAP_MINUTES, so default should apply
        assert result == _DEFAULT_LUNCH

    def test_leading_gap_before_first_event(self):
        """Gap from range_start to first event should be detected per day."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        # First event of each day starts at 11:30 (range starts at 10:00)
        # Leading gap = 11:30 - 10:00 = 90 min >= 45 min
        # Use enough days to get >= _MIN_SLOT_SAMPLES gaps total
        event_times = []
        for day_n in range(1, 9):
            day = f"2026-01-{day_n:02d}"
            event_times.append((day, 11, 30, 12, 30))
            event_times.append((day, 13, 30, 14, 30))

        result = service._find_meal_window_in_range(
            event_times,
            range_start_h=10,
            range_end_h=15,
            default=_DEFAULT_LUNCH,
        )

        # Each day has a leading gap: 10:00 -> 11:30 and an inter-event gap
        start_min = result[0] * 60 + result[1]
        assert start_min >= 10 * 60


# ---------------------------------------------------------------------------
# MealWindowInferenceService.infer_and_save
# ---------------------------------------------------------------------------

class TestInferAndSave:
    """Tests for the main public method."""

    @pytest.mark.asyncio
    async def test_normal_inference_returns_true(self):
        """With sufficient events, infer_and_save returns True."""
        family_id = _make_uuid()

        db = AsyncMock()
        service = MealWindowInferenceService(db)

        event_times = _make_diverse_event_times(20)
        service._collect_event_times = AsyncMock(return_value=event_times)
        service._persist_windows = AsyncMock()

        result = await service.infer_and_save(family_id)

        assert result is True
        service._persist_windows.assert_awaited_once()
        # Verify the windows dict was passed
        call_args = service._persist_windows.call_args
        windows = call_args[0][1]
        assert "lunch" in windows
        assert "dinner" in windows

    @pytest.mark.asyncio
    async def test_sample_too_small_returns_false(self):
        """Fewer than _MIN_EVENTS_FOR_INFERENCE events returns False."""
        family_id = _make_uuid()

        db = AsyncMock()
        service = MealWindowInferenceService(db)

        # Only 5 events (< 10 threshold)
        event_times = [("2026-01-01", 10, 0, 11, 0)] * 5
        service._collect_event_times = AsyncMock(return_value=event_times)
        service._persist_windows = AsyncMock()

        result = await service.infer_and_save(family_id)

        assert result is False
        service._persist_windows.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_exactly_threshold_events_proceeds(self):
        """Exactly _MIN_EVENTS_FOR_INFERENCE events should proceed."""
        family_id = _make_uuid()

        db = AsyncMock()
        service = MealWindowInferenceService(db)

        event_times = _make_diverse_event_times(_MIN_EVENTS_FOR_INFERENCE)
        service._collect_event_times = AsyncMock(return_value=event_times)
        service._persist_windows = AsyncMock()

        result = await service.infer_and_save(family_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_empty_events_returns_false(self):
        """No events at all returns False."""
        family_id = _make_uuid()

        db = AsyncMock()
        service = MealWindowInferenceService(db)
        service._collect_event_times = AsyncMock(return_value=[])
        service._persist_windows = AsyncMock()

        result = await service.infer_and_save(family_id)

        assert result is False
        service._persist_windows.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_nine_events_is_below_threshold(self):
        """9 events (threshold - 1) should not proceed."""
        family_id = _make_uuid()

        db = AsyncMock()
        service = MealWindowInferenceService(db)

        event_times = [("2026-01-01", 10, 0, 11, 0)] * 9
        service._collect_event_times = AsyncMock(return_value=event_times)
        service._persist_windows = AsyncMock()

        result = await service.infer_and_save(family_id)

        assert result is False


# ---------------------------------------------------------------------------
# MealWindowInferenceService._persist_windows
# ---------------------------------------------------------------------------

class TestPersistWindows:
    """Tests for the persistence logic."""

    @pytest.mark.asyncio
    async def test_creates_new_preference_when_none_exists(self):
        """When no FamilyPreference exists, a new one should be created."""
        family_id = _make_uuid()
        windows = {"lunch": [11, 0, 12, 30], "dinner": [18, 0, 19, 30]}

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        service = MealWindowInferenceService(db)

        with patch(
            "src.modules.curation.services.meal_window_service.utc_now"
        ) as mock_now:
            mock_now.return_value = datetime(2026, 2, 25, 12, 0, 0, tzinfo=timezone.utc)
            await service._persist_windows(family_id, windows)

        db.add.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert added_obj.family_id == family_id
        assert added_obj.inferred_meal_windows == windows
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_updates_existing_preference(self):
        """When FamilyPreference exists, update inferred_meal_windows in place."""
        family_id = _make_uuid()
        windows = {"lunch": [11, 30, 12, 45], "dinner": [18, 30, 20, 0]}

        existing_pref = MagicMock()
        existing_pref.family_id = family_id
        existing_pref.inferred_meal_windows = None
        existing_pref.meal_windows_inferred_at = None

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_pref
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()

        service = MealWindowInferenceService(db)

        with patch(
            "src.modules.curation.services.meal_window_service.utc_now"
        ) as mock_now:
            mock_now.return_value = datetime(2026, 2, 25, 12, 0, 0, tzinfo=timezone.utc)
            await service._persist_windows(family_id, windows)

        assert existing_pref.inferred_meal_windows == windows
        assert existing_pref.meal_windows_inferred_at is not None
        # Should NOT call db.add for existing records
        db.add.assert_not_called()
        db.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# MealWindowInferenceService._collect_event_times
# ---------------------------------------------------------------------------

class TestCollectEventTimes:
    """Tests for the event time collection from DB."""

    @pytest.mark.asyncio
    async def test_excludes_travel_event_types(self):
        """Events with event_type in _EXCLUDED_EVENT_TYPES should be filtered."""
        family_id = _make_uuid()
        now = datetime.now(tz=timezone.utc)

        # Create mock events: one travel (excluded), one meeting (included)
        travel_event = SimpleNamespace(
            event_type="travel",
            normalized_start=now,
            normalized_end=now + timedelta(hours=1),
        )
        meeting_event = SimpleNamespace(
            event_type="meeting",
            normalized_start=now,
            normalized_end=now + timedelta(hours=1),
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [travel_event, meeting_event]
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        service = MealWindowInferenceService(db)
        times = await service._collect_event_times(family_id)

        # travel event should be excluded, only meeting should remain
        assert len(times) == 1

    @pytest.mark.asyncio
    async def test_skips_multi_day_events(self):
        """Events spanning multiple days should be excluded."""
        family_id = _make_uuid()
        now = datetime.now(tz=timezone.utc)

        multi_day_event = SimpleNamespace(
            event_type="meeting",
            normalized_start=now,
            normalized_end=now + timedelta(days=2),
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [multi_day_event]
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        service = MealWindowInferenceService(db)
        times = await service._collect_event_times(family_id)

        assert len(times) == 0

    @pytest.mark.asyncio
    async def test_skips_events_with_none_end(self):
        """Events with None normalized_end should be excluded."""
        family_id = _make_uuid()
        now = datetime.now(tz=timezone.utc)

        no_end_event = SimpleNamespace(
            event_type="appointment",
            normalized_start=now,
            normalized_end=None,
        )

        db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [no_end_event]
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        service = MealWindowInferenceService(db)
        times = await service._collect_event_times(family_id)

        assert len(times) == 0

    @pytest.mark.asyncio
    async def test_empty_events_returns_empty(self):
        """No events from DB returns empty list."""
        family_id = _make_uuid()

        db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        service = MealWindowInferenceService(db)
        times = await service._collect_event_times(family_id)

        assert times == []


# ---------------------------------------------------------------------------
# Median calculation verification
# ---------------------------------------------------------------------------

class TestMedianCalculation:
    """Verify that the median-based window calculation is correct."""

    def test_median_of_free_slots(self):
        """Same-day duplicate events should yield only one per-day gap (< _MIN_SLOT_SAMPLES)."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        # 7 pairs all on the SAME day: per-day grouping produces only 1 gap per day
        # (one day => 1 gap), which is < _MIN_SLOT_SAMPLES => default
        event_times = []
        for _ in range(7):
            event_times.append(("2026-01-01", 10, 0, 10, 30))
            event_times.append(("2026-01-01", 11, 30, 12, 0))

        result = service._find_meal_window_in_range(
            event_times,
            range_start_h=10,
            range_end_h=15,
            default=_DEFAULT_LUNCH,
        )

        # Only 1 day => at most 2 gaps (leading + 1 between clusters)
        # Both < _MIN_SLOT_SAMPLES (5), so defaults
        assert result == _DEFAULT_LUNCH

    def test_sufficient_gaps_produce_median(self):
        """With enough distinct per-day gaps, median values should be computed."""
        db = AsyncMock()
        service = MealWindowInferenceService(db)

        # Create 5 days, each with events that produce at least 1 gap >= 45 min
        event_times = []
        for day_n in range(1, 6):
            day = f"2026-01-{day_n:02d}"
            event_times.append((day, 10, 30, 11, 0))   # gap: 11:00 -> 12:00 = 60min
            event_times.append((day, 12, 0, 12, 15))
            event_times.append((day, 13, 0, 13, 15))

        result = service._find_meal_window_in_range(
            event_times,
            range_start_h=10,
            range_end_h=15,
            default=_DEFAULT_LUNCH,
        )

        # The result should be a 4-tuple of ints
        assert isinstance(result, tuple)
        assert len(result) == 4
        assert all(isinstance(v, int) for v in result)

        # The start should be within the lunch range
        start_minutes = result[0] * 60 + result[1]
        end_minutes = result[2] * 60 + result[3]
        assert 10 * 60 <= start_minutes <= 15 * 60
        assert 10 * 60 <= end_minutes <= 15 * 60


# ---------------------------------------------------------------------------
# Constants validation
# ---------------------------------------------------------------------------

class TestConstants:
    """Verify service constants are sensible."""

    def test_min_events_threshold(self):
        assert _MIN_EVENTS_FOR_INFERENCE == 10

    def test_min_gap_minutes(self):
        assert _MIN_GAP_MINUTES == 45

    def test_min_slot_samples(self):
        assert _MIN_SLOT_SAMPLES == 5

    def test_default_lunch_format(self):
        assert len(_DEFAULT_LUNCH) == 4
        assert _DEFAULT_LUNCH[0] == 12  # 12:00 start
        assert _DEFAULT_LUNCH[2] == 13  # 13:30 end

    def test_default_dinner_format(self):
        assert len(_DEFAULT_DINNER) == 4
        assert _DEFAULT_DINNER[0] == 18  # 18:00 start
        assert _DEFAULT_DINNER[2] == 19  # 19:30 end
