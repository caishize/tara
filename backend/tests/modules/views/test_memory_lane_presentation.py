"""Tests for memory lane life-secretary narrative helpers.

Covers: _build_trip_story_title, _build_month_story_title,
        _build_on_this_day_narrative, _compute_emotional_tag
"""
from datetime import datetime, timezone
from typing import Optional, List
from unittest.mock import MagicMock

from src.modules.views.services.memory_lane_service import MemoryLaneService


def _make_event(
    *,
    title: str = "Test Event",
    event_type: str = "other",
    location: Optional[str] = None,
    trip_name: Optional[str] = None,
    normalized_start: Optional[datetime] = None,
    trip_id=None,
    tags=None,
):
    ev = MagicMock()
    ev.title = title
    ev.event_type = event_type
    ev.location = location
    ev.trip_name = trip_name
    ev.normalized_start = normalized_start or datetime(
        2026, 3, 1, 9, 0, tzinfo=timezone.utc,
    )
    ev.trip_id = trip_id
    ev.tags = tags or []
    return ev


def _make_on_this_day_event(
    *,
    title: str = "旧事件",
    event_type: str = "other",
    participants: Optional[List] = None,
    memory_fragments: Optional[List] = None,
):
    ev = MagicMock()
    ev.title = title
    ev.event_type = event_type
    ev.participants = participants
    ev.memory_fragments = memory_fragments
    return ev


# ── _build_trip_story_title ───────────────────────────────────────


class TestBuildTripStoryTitle:
    def test_short_trip_with_trip_name(self):
        events = [
            _make_event(
                trip_name="丽江之旅", location="丽江古城",
                normalized_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            _make_event(
                trip_name="丽江之旅",
                normalized_start=datetime(2026, 3, 2, tzinfo=timezone.utc),
            ),
        ]
        result = MemoryLaneService._build_trip_story_title(events)
        assert "丽江之旅" in result
        assert "那次去" in result

    def test_long_trip_includes_duration(self):
        events = [
            _make_event(
                trip_name="三亚", location="三亚",
                normalized_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            _make_event(
                normalized_start=datetime(2026, 3, 5, tzinfo=timezone.utc),
            ),
        ]
        result = MemoryLaneService._build_trip_story_title(events)
        assert "三亚" in result
        assert "5天之旅" in result

    def test_no_destination_fallback(self):
        events = [
            _make_event(title="出发"),
        ]
        result = MemoryLaneService._build_trip_story_title(events)
        assert result == "出发"

    def test_trip_name_preferred_over_location(self):
        events = [
            _make_event(
                trip_name="云南自驾游", location="昆明机场",
                normalized_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
        ]
        result = MemoryLaneService._build_trip_story_title(events)
        assert "云南自驾游" in result


# ── _build_month_story_title ──────────────────────────────────────


class TestBuildMonthStoryTitle:
    def test_single_event_uses_title(self):
        events = [_make_event(title="和老朋友聚餐")]
        result = MemoryLaneService._build_month_story_title(events, "2026-03")
        assert result == "和老朋友聚餐"

    def test_special_key_uses_title(self):
        events = [
            _make_event(title="妈妈生日"),
            _make_event(title="买蛋糕"),
        ]
        result = MemoryLaneService._build_month_story_title(events, "special-birthday")
        assert result == "妈妈生日"

    def test_social_theme(self):
        events = [
            _make_event(event_type="social"),
            _make_event(event_type="social"),
        ]
        result = MemoryLaneService._build_month_story_title(events, "2025-06")
        assert "聚会时光" in result

    def test_travel_theme(self):
        events = [
            _make_event(event_type="travel"),
            _make_event(event_type="travel"),
        ]
        result = MemoryLaneService._build_month_story_title(events, "2025-08")
        assert "旅行时光" in result

    def test_generic_fallback(self):
        events = [
            _make_event(event_type="other"),
            _make_event(event_type="other"),
        ]
        result = MemoryLaneService._build_month_story_title(events, "2025-12")
        assert "回忆" in result

    def test_invalid_key_returns_key(self):
        events = [_make_event(), _make_event()]
        result = MemoryLaneService._build_month_story_title(events, "invalid")
        assert result == "invalid"


# ── _build_on_this_day_narrative ──────────────────────────────────


class TestBuildOnThisDayNarrative:
    def test_one_year_ago_uses_去年(self):
        events = [_make_on_this_day_event(title="聚餐")]
        result = MemoryLaneService._build_on_this_day_narrative(1, events)
        assert "去年的今天" in result

    def test_multi_year_ago(self):
        events = [_make_on_this_day_event(title="聚餐")]
        result = MemoryLaneService._build_on_this_day_narrative(3, events)
        assert "3年前的今天" in result

    def test_with_participants_social(self):
        events = [_make_on_this_day_event(
            title="聚会", event_type="social",
            participants=["小明", "小红"],
        )]
        result = MemoryLaneService._build_on_this_day_narrative(2, events)
        assert "小明" in result
        assert "小红" in result
        assert "聚了聚" in result

    def test_with_participants_travel(self):
        events = [_make_on_this_day_event(
            title="出发", event_type="travel",
            participants=["爸爸"],
        )]
        result = MemoryLaneService._build_on_this_day_narrative(2, events)
        assert "爸爸" in result
        assert "旅行" in result

    def test_with_memory_fragment(self):
        events = [_make_on_this_day_event(
            title="三亚之旅",
            memory_fragments=["海边的日落真美"],
        )]
        result = MemoryLaneService._build_on_this_day_narrative(2, events)
        assert "三亚之旅" in result
        assert "海边的日落真美" in result

    def test_empty_events(self):
        result = MemoryLaneService._build_on_this_day_narrative(1, [])
        assert "去年的今天" in result


# ── _compute_emotional_tag ────────────────────────────────────────


class TestComputeEmotionalTag:
    def test_travel_events(self):
        events = [_make_event(event_type="travel")]
        result = MemoryLaneService._compute_emotional_tag(events)
        assert result == "温馨旅途"

    def test_business_trip_only(self):
        events = [_make_event(event_type="business_trip")]
        result = MemoryLaneService._compute_emotional_tag(events)
        assert result == "出差记录"

    def test_mixed_travel_and_business(self):
        events = [
            _make_event(event_type="travel"),
            _make_event(event_type="business_trip"),
        ]
        result = MemoryLaneService._compute_emotional_tag(events)
        assert result == "温馨旅途"

    def test_birthday_events(self):
        events = [_make_event(event_type="birthday")]
        result = MemoryLaneService._compute_emotional_tag(events)
        assert result == "特别的日子"

    def test_social_events(self):
        events = [_make_event(event_type="social")]
        result = MemoryLaneService._compute_emotional_tag(events)
        assert result == "朋友聚会"

    def test_empty_returns_none(self):
        result = MemoryLaneService._compute_emotional_tag([])
        assert result is None

    def test_generic_returns_none(self):
        events = [_make_event(event_type="other")]
        result = MemoryLaneService._compute_emotional_tag(events)
        assert result is None
