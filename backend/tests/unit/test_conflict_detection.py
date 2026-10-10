"""
Unit tests for schedule conflict detection logic.

Tests the pure functions in conflict_detection.py:
- determine_conflict_priority
- generate_conflict_suggestion
- build_conflict_alert
- _aggregate_by_trip
- _normalize_destination
"""
import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from src.modules.curation.services.conflict_detection import (
    build_conflict_alert,
    classify_conflict_importance,
    determine_conflict_priority,
    generate_conflict_suggestion,
    _aggregate_by_trip,
    _is_event_important,
    _normalize_destination,
    CONFLICT_EVENT_TYPES,
)
from src.modules.curation.schemas import ConflictPriority
from typing import Optional, List


def _make_event(
    title: str = "测试事件",
    event_type: str = "business_trip",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    trip_id=None,
    location: Optional[str] = None,
    confidence: Optional[float] = None,
    source_types: Optional[list] = None,
    timeline_items: Optional[list] = None,
) -> SimpleNamespace:
    """Create a minimal event-like object for testing."""
    return SimpleNamespace(
        id=uuid4(),
        title=title,
        event_type=event_type,
        normalized_start=start,
        normalized_end=end,
        trip_id=trip_id,
        location=location,
        confidence=confidence,
        source_types=source_types,
        timeline_items=timeline_items,
    )


def _dt(month: int, day: int, hour: int = 0) -> datetime:
    """Shortcut: build a UTC datetime in 2026."""
    return datetime(2026, month, day, hour, tzinfo=timezone.utc)


# ============================================================
# determine_conflict_priority
# ============================================================

class TestDetermineConflictPriority:
    """Tests for determine_conflict_priority."""

    def test_zero_duration_event_returns_high(self):
        """Zero-duration event (start == end) overlapped by anything → high."""
        # Zero-duration event at Jan 30, overlapping with a 3-day event
        result = determine_conflict_priority(
            a_start=_dt(1, 30), a_end=_dt(1, 30),  # zero duration
            b_start=_dt(1, 29), b_end=_dt(2, 1),
        )
        assert result == ConflictPriority.HIGH

    def test_both_zero_duration_returns_high(self):
        """Two zero-duration events at the same time → high."""
        t = _dt(1, 30, 10)
        result = determine_conflict_priority(
            a_start=t, a_end=t,
            b_start=t, b_end=t,
        )
        assert result == ConflictPriority.HIGH

    def test_full_containment_returns_high(self):
        """One event fully inside the other → high (overlap ratio = 1.0)."""
        result = determine_conflict_priority(
            a_start=_dt(1, 28), a_end=_dt(2, 3),   # 6 days
            b_start=_dt(1, 30), b_end=_dt(2, 1),   # 2 days inside
        )
        assert result == ConflictPriority.HIGH

    def test_overlap_above_50_percent_returns_high(self):
        """Overlap > 50% of shorter event → high."""
        # A: Jan 28-31 (3 days), B: Jan 30 - Feb 2 (3 days)
        # Overlap: Jan 30-31 = 1 day, ratio = 1/3 ≈ 33% → medium? No, let's
        # make it bigger.
        # A: Jan 28-31, B: Jan 29 - Feb 1 → overlap = Jan 29-31 = 2 days
        # shorter = 3 days, ratio = 2/3 ≈ 67% → high
        result = determine_conflict_priority(
            a_start=_dt(1, 28), a_end=_dt(1, 31),
            b_start=_dt(1, 29), b_end=_dt(2, 1),
        )
        assert result == ConflictPriority.HIGH

    def test_small_overlap_returns_medium(self):
        """Overlap ≤ 2 days and < 50% of shorter event → medium."""
        # A: Jan 28 - Feb 5 (8 days), B: Feb 4 - Feb 12 (8 days)
        # Overlap: Feb 4-5 = 1 day, ratio = 1/8 = 12.5% → not high
        # overlap_duration.days = 1 ≤ 2 → medium
        result = determine_conflict_priority(
            a_start=_dt(1, 28), a_end=_dt(2, 5),
            b_start=_dt(2, 4), b_end=_dt(2, 12),
        )
        assert result == ConflictPriority.MEDIUM

    def test_large_overlap_below_50_percent_returns_high(self):
        """Overlap > 2 days but < 50% → high (fallthrough)."""
        # A: Jan 1 - Jan 30 (29 days), B: Jan 20 - Feb 28 (39 days)
        # Overlap: Jan 20 - Jan 30 = 10 days, shorter = 29 days
        # ratio = 10/29 ≈ 34% → not ≥ 50%, overlap.days = 10 > 2
        # Falls through to final return → high
        result = determine_conflict_priority(
            a_start=_dt(1, 1), a_end=_dt(1, 30),
            b_start=_dt(1, 20), b_end=_dt(2, 28),
        )
        assert result == ConflictPriority.HIGH

    def test_exactly_50_percent_overlap_returns_high(self):
        """Overlap at exactly 50% boundary → high."""
        # A: Jan 1 - Jan 4 (3 days), B: Jan 2.5 - Jan 7
        # Use hours for precision: A: 0:00 - 72:00, B: 36:00 - 108:00
        a_start = _dt(1, 1)
        a_end = _dt(1, 4)
        b_start = _dt(1, 1) + timedelta(hours=36)
        b_end = _dt(1, 7)
        result = determine_conflict_priority(a_start, a_end, b_start, b_end)
        assert result == ConflictPriority.HIGH


# ============================================================
# generate_conflict_suggestion
# ============================================================

class TestGenerateConflictSuggestion:
    """Tests for generate_conflict_suggestion."""

    def test_full_containment_a_contains_b(self):
        """Event B fully inside event A → suggest rescheduling B."""
        a = _make_event("北京出差", "business_trip", _dt(1, 28), _dt(2, 3))
        b = _make_event("澳门游", "travel", _dt(1, 30), _dt(2, 1))
        result = generate_conflict_suggestion(
            a, _dt(1, 28), _dt(2, 3),
            b, _dt(1, 30), _dt(2, 1),
        )
        assert "澳门游" in result
        assert "完全在" in result
        assert "北京出差" in result

    def test_full_containment_b_contains_a(self):
        """Event A fully inside event B → suggest rescheduling A."""
        a = _make_event("短会议", "meeting", _dt(1, 30), _dt(1, 30))
        b = _make_event("长出差", "business_trip", _dt(1, 28), _dt(2, 3))
        result = generate_conflict_suggestion(
            a, _dt(1, 30), _dt(1, 30),
            b, _dt(1, 28), _dt(2, 3),
        )
        assert "短会议" in result
        assert "完全在" in result

    def test_business_trip_vs_travel_suggests_reschedule_travel(self):
        """Business trip (A) + travel (B) → suggest rescheduling travel."""
        a = _make_event("北京出差", "business_trip", _dt(1, 30), _dt(2, 1))
        b = _make_event("澳门周末游", "travel", _dt(1, 31), _dt(2, 2))
        result = generate_conflict_suggestion(
            a, _dt(1, 30), _dt(2, 1),
            b, _dt(1, 31), _dt(2, 2),
        )
        assert "澳门周末游" in result
        assert "调整" in result

    def test_travel_vs_business_trip_suggests_reschedule_travel(self):
        """Travel (A) + business trip (B) → suggest rescheduling travel (A)."""
        a = _make_event("澳门周末游", "travel", _dt(1, 31), _dt(2, 2))
        b = _make_event("北京出差", "business_trip", _dt(1, 30), _dt(2, 1))
        result = generate_conflict_suggestion(
            a, _dt(1, 31), _dt(2, 2),
            b, _dt(1, 30), _dt(2, 1),
        )
        assert "澳门周末游" in result
        assert "调整" in result

    def test_same_type_suggests_choose(self):
        """Two events of same type with partial overlap → suggest user choose."""
        a = _make_event("澳门周末游", "travel", _dt(1, 31), _dt(2, 2))
        b = _make_event("广州周末游", "travel", _dt(2, 1), _dt(2, 3))
        result = generate_conflict_suggestion(
            a, _dt(1, 31), _dt(2, 2),
            b, _dt(2, 1), _dt(2, 3),
        )
        assert "澳门周末游" in result
        assert "广州周末游" in result
        assert "选择保留" in result

    def test_partial_overlap_one_day_suggests_adjust(self):
        """Partial overlap ≤ 1 day → suggest adjusting times."""
        a = _make_event("北京出差", "business_trip", _dt(1, 28), _dt(1, 30))
        b = _make_event("会议", "meeting", _dt(1, 30), _dt(1, 31))
        # Overlap: Jan 30 only = (30-30).days + 1 = 1
        result = generate_conflict_suggestion(
            a, _dt(1, 28), _dt(1, 30),
            b, _dt(1, 30), _dt(1, 31),
        )
        # Not containment, not same type, not biz_trip vs travel (meeting ≠ travel)
        # overlap_days = 1 ≤ 1 → "重叠时间较短"
        assert "重叠时间较短" in result

    def test_general_case_fallthrough(self):
        """General partial overlap > 1 day, different types → general suggestion."""
        a = _make_event("出差", "business_trip", _dt(1, 28), _dt(2, 1))
        b = _make_event("预约", "appointment", _dt(1, 30), _dt(2, 2))
        # Overlap: Jan 30 - Feb 1 = 2 days → overlap_days = 3
        result = generate_conflict_suggestion(
            a, _dt(1, 28), _dt(2, 1),
            b, _dt(1, 30), _dt(2, 2),
        )
        assert "调整" in result
        assert "预约" in result


# ============================================================
# build_conflict_alert
# ============================================================

class TestBuildConflictAlert:
    """Tests for build_conflict_alert."""

    def test_alert_has_both_event_ids(self):
        """Alert should contain both event IDs."""
        a = _make_event("北京出差", "business_trip", _dt(1, 30), _dt(2, 1))
        b = _make_event("澳门游", "travel", _dt(1, 31), _dt(2, 2))
        alert = build_conflict_alert(
            a, _dt(1, 30), _dt(2, 1),
            b, _dt(1, 31), _dt(2, 2),
        )
        assert str(a.id) in alert.conflicting_event_ids
        assert str(b.id) in alert.conflicting_event_ids
        assert len(alert.conflicting_event_ids) == 2

    def test_alert_id_format(self):
        """Alert ID should be 'conflict-{id_a}-{id_b}'."""
        a = _make_event("A", "travel")
        b = _make_event("B", "travel")
        alert = build_conflict_alert(
            a, _dt(1, 30), _dt(2, 1),
            b, _dt(1, 31), _dt(2, 2),
        )
        assert alert.id == f"conflict-{a.id}-{b.id}"

    def test_alert_title_is_conflict(self):
        """Alert title should be '日程冲突'."""
        a = _make_event("A", "travel")
        b = _make_event("B", "travel")
        alert = build_conflict_alert(
            a, _dt(1, 30), _dt(2, 1),
            b, _dt(1, 31), _dt(2, 2),
        )
        assert alert.title == "日程冲突"

    def test_alert_description_contains_both_titles(self):
        """Description should mention both event titles."""
        a = _make_event("北京出差", "business_trip")
        b = _make_event("澳门游", "travel")
        alert = build_conflict_alert(
            a, _dt(1, 30), _dt(2, 1),
            b, _dt(1, 31), _dt(2, 2),
        )
        assert "北京出差" in alert.description
        assert "澳门游" in alert.description
        assert "时间冲突" in alert.description

    def test_alert_priority_is_enum(self):
        """Priority should be a ConflictPriority enum value."""
        a = _make_event("A", "travel")
        b = _make_event("B", "travel")
        alert = build_conflict_alert(
            a, _dt(1, 30), _dt(2, 1),
            b, _dt(1, 31), _dt(2, 2),
        )
        assert isinstance(alert.priority, ConflictPriority)


# ============================================================
# CONFLICT_EVENT_TYPES
# ============================================================

class TestConflictEventTypes:
    """Verify the set of conflictable event types."""

    def test_includes_expected_types(self):
        assert "business_trip" in CONFLICT_EVENT_TYPES
        assert "travel" in CONFLICT_EVENT_TYPES
        assert "meeting" in CONFLICT_EVENT_TYPES
        assert "appointment" in CONFLICT_EVENT_TYPES

    def test_excludes_date_based_types(self):
        assert "holiday" not in CONFLICT_EVENT_TYPES
        assert "birthday" not in CONFLICT_EVENT_TYPES
        assert "anniversary" not in CONFLICT_EVENT_TYPES
        assert "reminder" not in CONFLICT_EVENT_TYPES

    def test_none_event_type_not_in_set(self):
        assert None not in CONFLICT_EVENT_TYPES


# ============================================================
# _normalize_destination
# ============================================================

class TestNormalizeDestination:
    """Tests for _normalize_destination (now delegates to trip_grouping).

    After the refactor, _normalize_destination only does strip + lowercase.
    Semantic normalization (English→Chinese) is the LLM's job via the `city` field.
    """

    def test_empty_string(self):
        assert _normalize_destination("") == ""

    def test_chinese_city(self):
        assert _normalize_destination("北京") == "北京"

    def test_english_lowercased(self):
        """English city names are lowercased (no longer mapped to Chinese)."""
        assert _normalize_destination("Beijing") == "beijing"

    def test_case_insensitive(self):
        assert _normalize_destination("SHANGHAI") == "shanghai"

    def test_strips_whitespace(self):
        assert _normalize_destination("  guangzhou  ") == "guangzhou"

    def test_unknown_city_lowercased(self):
        assert _normalize_destination("Zurich") == "zurich"


# ============================================================
# _aggregate_by_trip
# ============================================================

class TestAggregateByTrip:
    """Tests for _aggregate_by_trip."""

    def test_standalone_events_pass_through(self):
        """Events without trip_id and not Day-prefixed pass through unchanged."""
        ev = _make_event("客户会议", "meeting", _dt(2, 3, 9), _dt(2, 3, 11))
        result = _aggregate_by_trip([ev])
        assert len(result) == 1
        assert result[0].title == "客户会议"

    def test_single_day_event_with_trip_passes_through(self):
        """A single Day event in a trip group is returned as-is."""
        tid = uuid4()
        ev = _make_event(
            "Day 1 · 北京出差", "business_trip",
            _dt(2, 3, 9), _dt(2, 3, 18),
            trip_id=tid, location="北京",
        )
        result = _aggregate_by_trip([ev])
        assert len(result) == 1
        assert result[0].title == "Day 1 · 北京出差"

    def test_multiple_day_events_aggregated_by_trip_id(self):
        """Multiple Day events with same trip_id are aggregated into one."""
        tid = uuid4()
        day1 = _make_event(
            "Day 1 · 北京出差", "business_trip",
            _dt(2, 3, 9), _dt(2, 3, 18),
            trip_id=tid, location="北京",
        )
        day2 = _make_event(
            "Day 2 · 北京出差", "business_trip",
            _dt(2, 4, 9), _dt(2, 4, 18),
            trip_id=tid, location="北京",
        )
        result = _aggregate_by_trip([day1, day2])
        assert len(result) == 1
        assert result[0].title == "北京出差"
        assert result[0].normalized_start == _dt(2, 3, 9)
        assert result[0].normalized_end == _dt(2, 4, 18)

    def test_day_events_aggregated_by_location(self):
        """Day events without trip_id but same location are aggregated."""
        ev1 = _make_event(
            "Day 1 · 广州周末游", "travel",
            _dt(2, 1, 9), _dt(2, 1, 18),
            location="广州",
        )
        ev2 = _make_event(
            "Day 2 · 广州周末游", "travel",
            _dt(2, 2, 9), _dt(2, 2, 18),
            location="广州",
        )
        result = _aggregate_by_trip([ev1, ev2])
        assert len(result) == 1
        assert result[0].normalized_start == _dt(2, 1, 9)
        assert result[0].normalized_end == _dt(2, 2, 18)

    def test_different_trips_not_merged(self):
        """Events from different trips remain separate."""
        tid_a = uuid4()
        tid_b = uuid4()
        ev_a = _make_event(
            "Day 1 · 北京出差", "business_trip",
            _dt(2, 3, 9), _dt(2, 3, 18),
            trip_id=tid_a, location="北京",
        )
        ev_b = _make_event(
            "Day 1 · 广州周末游", "travel",
            _dt(2, 1, 9), _dt(2, 1, 18),
            trip_id=tid_b, location="广州",
        )
        result = _aggregate_by_trip([ev_a, ev_b])
        assert len(result) == 2

    def test_mixed_standalone_and_trip(self):
        """Standalone events are preserved alongside aggregated trip events."""
        tid = uuid4()
        day1 = _make_event(
            "Day 1 · 北京出差", "business_trip",
            _dt(2, 3, 9), _dt(2, 3, 18),
            trip_id=tid, location="北京",
        )
        day2 = _make_event(
            "Day 2 · 北京出差", "business_trip",
            _dt(2, 4, 9), _dt(2, 4, 18),
            trip_id=tid, location="北京",
        )
        standalone = _make_event(
            "客户午餐", "appointment",
            _dt(2, 5, 12), _dt(2, 5, 14),
        )
        result = _aggregate_by_trip([day1, day2, standalone])
        assert len(result) == 2
        titles = {r.title for r in result}
        assert "北京出差" in titles
        assert "客户午餐" in titles


# ============================================================
# _is_event_important
# ============================================================

class TestIsEventImportant:
    """Tests for _is_event_important."""

    def test_high_confidence_with_user_source(self):
        """High confidence + user-explicit source → important."""
        ev = _make_event(
            confidence=0.9,
            source_types=["user_created"],
        )
        assert _is_event_important(ev) is True

    def test_high_confidence_without_user_source(self):
        """High confidence but no user source → falls through to type check."""
        ev = _make_event(
            event_type="travel",
            confidence=0.9,
            source_types=["auto_detected"],
        )
        # travel is NOT in _HIGH_IMPORTANCE_EVENT_TYPES
        assert _is_event_important(ev) is False

    def test_business_trip_always_important(self):
        """business_trip type → important regardless of confidence."""
        ev = _make_event(
            event_type="business_trip",
            confidence=0.3,
            source_types=["auto_detected"],
        )
        assert _is_event_important(ev) is True

    def test_meeting_always_important(self):
        ev = _make_event(event_type="meeting", confidence=0.5)
        assert _is_event_important(ev) is True

    def test_confirmed_timeline_item(self):
        """Event with a confirmed timeline item → important."""
        ev = _make_event(
            event_type="travel",
            confidence=0.5,
            timeline_items=[{"title": "Flight", "confirmed": True}],
        )
        assert _is_event_important(ev) is True

    def test_low_confidence_travel_not_important(self):
        """Low confidence travel with no user source → not important."""
        ev = _make_event(
            event_type="travel",
            confidence=0.4,
            source_types=["auto_detected"],
        )
        assert _is_event_important(ev) is False

    def test_none_fields_handled(self):
        """None confidence, source_types, timeline_items → not important."""
        ev = _make_event(event_type="travel")
        assert _is_event_important(ev) is False


# ============================================================
# classify_conflict_importance
# ============================================================

class TestClassifyConflictImportance:
    """Tests for classify_conflict_importance."""

    def test_both_important_returns_user_confirm(self):
        """Two important events → user_confirm."""
        a = _make_event("出差A", "business_trip", confidence=0.9)
        b = _make_event("出差B", "business_trip", confidence=0.9)
        assert classify_conflict_importance(a, b) == "user_confirm"

    def test_one_low_importance_returns_auto_resolve(self):
        """One important + one low-importance → auto_resolve."""
        a = _make_event("出差", "business_trip", confidence=0.9)
        b = _make_event("旅游", "travel", confidence=0.4, source_types=["auto_detected"])
        assert classify_conflict_importance(a, b) == "auto_resolve"

    def test_both_low_importance_returns_auto_resolve(self):
        """Two low-importance events → auto_resolve."""
        a = _make_event("旅游A", "travel", confidence=0.4, source_types=["auto_detected"])
        b = _make_event("旅游B", "travel", confidence=0.3, source_types=["auto_detected"])
        assert classify_conflict_importance(a, b) == "auto_resolve"
