"""
Unit tests for trip grouping logic.

Tests the 3-phase interval merging algorithm in trip_grouping.py:
- normalize_destination
- split_by_date_gaps
- get_subgroup_destination
- merge_adjacent_subgroups
- group_events_into_trips
"""
import pytest
from datetime import datetime, date, timezone
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from src.modules.curation.services.trip_grouping import (
    SubGroup,
    normalize_destination,
    local_start_date,
    local_end_date,
    split_by_date_gaps,
    get_subgroup_destination,
    merge_adjacent_subgroups,
    group_events_into_trips,
)

from typing import Optional

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _make_event(
    title: str = "测试事件",
    event_type: str = "travel",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    trip_id=None,
    city: Optional[str] = None,
    location: Optional[str] = None,
) -> SimpleNamespace:
    """Create a minimal event-like object for testing."""
    return SimpleNamespace(
        id=uuid4(),
        title=title,
        event_type=event_type,
        normalized_start=start,
        normalized_end=end,
        trip_id=trip_id,
        city=city,
        location=location,
    )


def _dt(month: int, day: int, hour: int = 9) -> datetime:
    """Shortcut: build a UTC datetime in 2026."""
    return datetime(2026, month, day, hour, tzinfo=timezone.utc)


# ============================================================
# normalize_destination
# ============================================================


class TestNormalizeDestination:
    """Tests for normalize_destination (minimal cleanup only)."""

    def test_strip_whitespace(self):
        assert normalize_destination("  北京  ") == "北京"

    def test_lowercase_english(self):
        assert normalize_destination("Beijing") == "beijing"

    def test_empty_string(self):
        assert normalize_destination("") == ""

    def test_none(self):
        assert normalize_destination(None) == ""

    def test_chinese_passthrough(self):
        assert normalize_destination("北京") == "北京"

    def test_mixed_case(self):
        assert normalize_destination("ShangHai") == "shanghai"


# ============================================================
# split_by_date_gaps
# ============================================================


class TestSplitByDateGaps:
    """Tests for split_by_date_gaps."""

    def test_single_event(self):
        ev = _make_event(start=_dt(1, 5), end=_dt(1, 5, 18))
        result = split_by_date_gaps([ev], SHANGHAI_TZ)
        assert len(result) == 1
        assert len(result[0]) == 1

    def test_three_consecutive_days(self):
        """Events on Jan 5, 6, 7 should stay together."""
        events = [
            _make_event(start=_dt(1, 5), end=_dt(1, 5, 18)),
            _make_event(start=_dt(1, 6), end=_dt(1, 6, 18)),
            _make_event(start=_dt(1, 7), end=_dt(1, 7, 18)),
        ]
        result = split_by_date_gaps(events, SHANGHAI_TZ)
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_two_day_gap_splits(self):
        """Jan 5 and Jan 8 (gap=2) should split into two groups."""
        events = [
            _make_event(start=_dt(1, 5), end=_dt(1, 5, 18)),
            _make_event(start=_dt(1, 8), end=_dt(1, 8, 18)),
        ]
        result = split_by_date_gaps(events, SHANGHAI_TZ)
        assert len(result) == 2

    def test_adjacent_gap_one_stays_together(self):
        """Jan 5 (end) and Jan 6 (start): gap=1 should stay together."""
        events = [
            _make_event(start=_dt(1, 5), end=_dt(1, 5, 18)),
            _make_event(start=_dt(1, 6), end=_dt(1, 6, 18)),
        ]
        result = split_by_date_gaps(events, SHANGHAI_TZ)
        assert len(result) == 1

    def test_null_end_falls_back_to_start(self):
        """Event with no end time uses start as end."""
        events = [
            _make_event(start=_dt(1, 5), end=None),
            _make_event(start=_dt(1, 6), end=None),
        ]
        result = split_by_date_gaps(events, SHANGHAI_TZ)
        assert len(result) == 1

    def test_empty_list(self):
        result = split_by_date_gaps([], SHANGHAI_TZ)
        assert result == []

    def test_unsorted_input_gets_sorted(self):
        """Events passed out of order should still be grouped correctly."""
        events = [
            _make_event(start=_dt(1, 7), end=_dt(1, 7, 18)),
            _make_event(start=_dt(1, 5), end=_dt(1, 5, 18)),
            _make_event(start=_dt(1, 6), end=_dt(1, 6, 18)),
        ]
        result = split_by_date_gaps(events, SHANGHAI_TZ)
        assert len(result) == 1
        assert len(result[0]) == 3


# ============================================================
# get_subgroup_destination
# ============================================================


class TestGetSubgroupDestination:
    """Tests for get_subgroup_destination."""

    def test_all_same_city(self):
        events = [
            _make_event(city="北京"),
            _make_event(city="北京"),
        ]
        assert get_subgroup_destination(events) == "北京"

    def test_mixed_cities_returns_none(self):
        events = [
            _make_event(city="北京"),
            _make_event(city="上海"),
        ]
        assert get_subgroup_destination(events) is None

    def test_route_string_returns_none(self):
        """A road trip with different cities returns None."""
        events = [
            _make_event(city="上海"),
            _make_event(city="杭州"),
            _make_event(city="深圳"),
        ]
        assert get_subgroup_destination(events) is None

    def test_all_null_cities_returns_none(self):
        events = [
            _make_event(city=None),
            _make_event(city=None),
        ]
        assert get_subgroup_destination(events) is None

    def test_falls_back_to_location(self):
        """When city is None, falls back to location field."""
        events = [
            _make_event(city=None, location="北京"),
            _make_event(city=None, location="北京"),
        ]
        assert get_subgroup_destination(events) == "北京"

    def test_case_insensitive_match(self):
        events = [
            _make_event(city="Beijing"),
            _make_event(city="beijing"),
        ]
        assert get_subgroup_destination(events) == "beijing"


# ============================================================
# merge_adjacent_subgroups
# ============================================================


class TestMergeAdjacentSubgroups:
    """Tests for merge_adjacent_subgroups."""

    def test_same_dest_adjacent_merges(self):
        """Same destination + adjacent dates → merge."""
        sg1 = SubGroup(
            events=[_make_event(city="北京", start=_dt(1, 3), end=_dt(1, 3, 18))],
            trip_ids={uuid4()},
        )
        sg2 = SubGroup(
            events=[_make_event(city="北京", start=_dt(1, 4), end=_dt(1, 5, 18))],
            trip_ids={uuid4()},
        )
        result = merge_adjacent_subgroups([sg1, sg2], SHANGHAI_TZ)
        assert len(result) == 1
        assert len(result[0].events) == 2
        assert len(result[0].trip_ids) == 2

    def test_same_dest_three_day_gap_separate(self):
        """Same destination + 3-day gap → separate."""
        sg1 = SubGroup(
            events=[_make_event(city="北京", start=_dt(1, 3), end=_dt(1, 3, 18))],
            trip_ids={uuid4()},
        )
        sg2 = SubGroup(
            events=[_make_event(city="北京", start=_dt(1, 7), end=_dt(1, 7, 18))],
            trip_ids={uuid4()},
        )
        result = merge_adjacent_subgroups([sg1, sg2], SHANGHAI_TZ)
        assert len(result) == 2

    def test_different_dest_adjacent_separate(self):
        """Different destination + adjacent → separate."""
        sg1 = SubGroup(
            events=[_make_event(city="北京", start=_dt(1, 3), end=_dt(1, 3, 18))],
            trip_ids={uuid4()},
        )
        sg2 = SubGroup(
            events=[_make_event(city="上海", start=_dt(1, 4), end=_dt(1, 4, 18))],
            trip_ids={uuid4()},
        )
        result = merge_adjacent_subgroups([sg1, sg2], SHANGHAI_TZ)
        assert len(result) == 2

    def test_road_trip_mixed_dest_never_merges(self):
        """Sub-group with mixed destinations (road trip) never merges."""
        sg1 = SubGroup(
            events=[
                _make_event(city="北京", start=_dt(1, 3), end=_dt(1, 3, 18)),
                _make_event(city="上海", start=_dt(1, 4), end=_dt(1, 4, 18)),
            ],
            trip_ids={uuid4()},
        )
        sg2 = SubGroup(
            events=[_make_event(city="上海", start=_dt(1, 5), end=_dt(1, 5, 18))],
            trip_ids={uuid4()},
        )
        result = merge_adjacent_subgroups([sg1, sg2], SHANGHAI_TZ)
        # sg1 has mixed dest (None), so it can't merge with sg2
        assert len(result) == 2

    def test_a_b_a_pattern_three_separate(self):
        """BJ, SH, BJ pattern → 3 separate trips."""
        sg1 = SubGroup(
            events=[_make_event(city="北京", start=_dt(1, 1), end=_dt(1, 3, 18))],
            trip_ids={uuid4()},
        )
        sg2 = SubGroup(
            events=[_make_event(city="上海", start=_dt(1, 4), end=_dt(1, 5, 18))],
            trip_ids={uuid4()},
        )
        sg3 = SubGroup(
            events=[_make_event(city="北京", start=_dt(1, 6), end=_dt(1, 7, 18))],
            trip_ids={uuid4()},
        )
        result = merge_adjacent_subgroups([sg1, sg2, sg3], SHANGHAI_TZ)
        assert len(result) == 3

    def test_empty_list(self):
        result = merge_adjacent_subgroups([], SHANGHAI_TZ)
        assert result == []


# ============================================================
# group_events_into_trips (full pipeline)
# ============================================================


class TestGroupEventsIntoTrips:
    """Tests for the full 3-phase pipeline."""

    def test_over_grouped_events_get_split(self):
        """Same trip_id but weeks apart (>7 days) → split into separate trips."""
        tid = uuid4()
        events = [
            _make_event("Day 1 · 广州游", start=_dt(2, 7), end=_dt(2, 8, 18), trip_id=tid, city="广州"),
            _make_event("Day 2 · 广州游", start=_dt(2, 8), end=_dt(2, 8, 18), trip_id=tid, city="广州"),
            _make_event("Day 1 · 广州游B", start=_dt(3, 21), end=_dt(3, 22, 18), trip_id=tid, city="广州"),
            _make_event("Day 2 · 广州游B", start=_dt(3, 22), end=_dt(3, 22, 18), trip_id=tid, city="广州"),
        ]
        result = group_events_into_trips(events, SHANGHAI_TZ)
        assert len(result) == 2

    def test_same_trip_id_small_gap_stays_together(self):
        """Same trip_id with 3-day gap (≤7) → stays as one trip (lenient intra-trip gap)."""
        tid = uuid4()
        events = [
            _make_event("Day 1 · 北京", start=_dt(1, 5), end=_dt(1, 5, 18), trip_id=tid, city="北京"),
            _make_event("Day 3 · 北京", start=_dt(1, 8), end=_dt(1, 8, 18), trip_id=tid, city="北京"),
        ]
        result = group_events_into_trips(events, SHANGHAI_TZ)
        assert len(result) == 1
        assert len(result[0].events) == 2

    def test_adjacent_different_trip_ids_merge(self):
        """Different trip_ids but same city + adjacent → merge."""
        events = [
            _make_event("BJ Day 1", start=_dt(1, 1), end=_dt(1, 3, 18), trip_id=uuid4(), city="北京"),
            _make_event("BJ Day 2", start=_dt(1, 4), end=_dt(1, 5, 18), trip_id=uuid4(), city="北京"),
        ]
        result = group_events_into_trips(events, SHANGHAI_TZ)
        assert len(result) == 1
        assert len(result[0].events) == 2

    def test_solo_events_each_a_group(self):
        """Events without trip_id → each its own group (unless same dest + adjacent)."""
        events = [
            _make_event("会议A", start=_dt(1, 10), end=_dt(1, 10, 18), city="北京"),
            _make_event("会议B", start=_dt(2, 15), end=_dt(2, 15, 18), city="上海"),
        ]
        result = group_events_into_trips(events, SHANGHAI_TZ)
        assert len(result) == 2

    def test_road_trip_single_group(self):
        """Road trip BJ→HZ→SZ (same trip_id) → single group."""
        tid = uuid4()
        events = [
            _make_event("Day 1 · 北京", start=_dt(1, 1), end=_dt(1, 1, 18), trip_id=tid, city="北京"),
            _make_event("Day 2 · 杭州", start=_dt(1, 2), end=_dt(1, 2, 18), trip_id=tid, city="杭州"),
            _make_event("Day 3 · 深圳", start=_dt(1, 3), end=_dt(1, 3, 18), trip_id=tid, city="深圳"),
        ]
        result = group_events_into_trips(events, SHANGHAI_TZ)
        # Phase 2 doesn't split (consecutive days)
        # Phase 3 can't merge (mixed dest → dest is None)
        assert len(result) == 1
        assert len(result[0].events) == 3

    def test_overlapping_events_same_trip(self):
        """Overlapping events (1-3 BJ + 2 BJ, same trip_id) → single group."""
        tid = uuid4()
        events = [
            _make_event("BJ Trip", start=_dt(1, 1), end=_dt(1, 3, 18), trip_id=tid, city="北京"),
            _make_event("BJ Meeting", start=_dt(1, 2), end=_dt(1, 2, 18), trip_id=tid, city="北京"),
        ]
        result = group_events_into_trips(events, SHANGHAI_TZ)
        assert len(result) == 1

    def test_empty_list(self):
        result = group_events_into_trips([], SHANGHAI_TZ)
        assert result == []

    def test_bj_sh_bj_three_trips(self):
        """BJ (1-3) + SH (4-5) + BJ (6-7) → 3 separate trips."""
        events = [
            _make_event("BJ1", start=_dt(1, 1), end=_dt(1, 3, 18), trip_id=uuid4(), city="北京"),
            _make_event("SH", start=_dt(1, 4), end=_dt(1, 5, 18), trip_id=uuid4(), city="上海"),
            _make_event("BJ2", start=_dt(1, 6), end=_dt(1, 7, 18), trip_id=uuid4(), city="北京"),
        ]
        result = group_events_into_trips(events, SHANGHAI_TZ)
        assert len(result) == 3

    def test_same_trip_id_adjacent_stays_one(self):
        """1-3 BJ + 4-5 BJ (same trip_id) → stays as one trip."""
        tid = uuid4()
        events = [
            _make_event("BJ Day1-3", start=_dt(1, 1), end=_dt(1, 3, 18), trip_id=tid, city="北京"),
            _make_event("BJ Day4-5", start=_dt(1, 4), end=_dt(1, 5, 18), trip_id=tid, city="北京"),
        ]
        result = group_events_into_trips(events, SHANGHAI_TZ)
        assert len(result) == 1
        assert len(result[0].events) == 2

    def test_diff_trip_ids_adjacent_same_dest_merges(self):
        """1-3 BJ + 4-5 BJ (different trip_ids) → merge into one."""
        events = [
            _make_event("BJ Plan A", start=_dt(1, 1), end=_dt(1, 3, 18), trip_id=uuid4(), city="北京"),
            _make_event("BJ Plan B", start=_dt(1, 4), end=_dt(1, 5, 18), trip_id=uuid4(), city="北京"),
        ]
        result = group_events_into_trips(events, SHANGHAI_TZ)
        assert len(result) == 1
        assert len(result[0].trip_ids) == 2
