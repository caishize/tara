"""Tests for DayTheme generation via pure rules in SecretaryOrchestrator.

Covers:
- Trip event → theme.title = trip name
- P0/P1 high-priority event → theme based on top event
- High density (>0.8) → "忙碌的一天" theme
- Light/free day → "轻松的一天" theme
- Normal day → day_theme = None
- DayTheme frozen dataclass field completeness
- Evening forward warnings for next-day early events

Source: src.modules.curation.services.orchestrator
"""
import uuid
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.curation.models import CuratedEvent
from src.modules.curation.services.orchestrator import (
    DayTheme,
    GapWarning,
    OrchestratedDay,
    SecretaryOrchestrator,
    TimeSlot,
)
from src.modules.curation.services.priority_engine import (
    EnhancedPriorityScore,
)
from src.modules.curation.services.priority_score import PriorityScore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_dt(hour: int = 9, minute: int = 0, day_offset: int = 0) -> datetime:
    """Build a timezone-aware UTC datetime for today + offset."""
    base = datetime.now(timezone.utc).replace(
        hour=hour, minute=minute, second=0, microsecond=0,
    )
    return base + timedelta(days=day_offset)


def _make_event(
    *,
    title: str = "Test Event",
    event_type: str = "meeting",
    trip_id: uuid.UUID = None,
    trip_name: str = None,
    start_hour: int = 9,
    end_hour: int = 10,
    location: str = None,
) -> CuratedEvent:
    """Build a minimal CuratedEvent."""
    ev = CuratedEvent()
    ev.id = uuid.uuid4()
    ev.user_id = uuid.uuid4()
    ev.family_id = uuid.uuid4()
    ev.title = title
    ev.event_type = event_type
    ev.trip_id = trip_id
    ev.trip_name = trip_name
    ev.location = location
    ev.normalized_start = _utc_dt(hour=start_hour)
    ev.normalized_end = _utc_dt(hour=end_hour)
    ev.original_event_ids = []
    ev.source_types = ["test"]
    ev.confidence = 0.9
    ev.status = "confirmed"
    ev.priority = "normal"
    return ev


def _make_score(
    composite: float,
    *,
    priority_level: str = None,
    secretary_note: str = None,
    preparation_hours: float = 0.0,
) -> EnhancedPriorityScore:
    """Build an EnhancedPriorityScore with a deterministic composite.

    We control the composite by setting urgency = composite on the
    PriorityScore with urgency weight = 1.0 and all others = 0.
    """
    base = PriorityScore(
        urgency=composite,
        severity=0.0,
        stakeholder_weight=0.0,
        irrecoverability=0.0,
        w_urgency_override=1.0,
        w_severity_override=0.0,
        w_stakeholder_override=0.0,
        w_irrecoverability_override=0.0,
    )
    return EnhancedPriorityScore(
        base=base,
        calibration=None,
        preparation_hours=preparation_hours,
        secretary_note=secretary_note,
        fallback=False,
    )


def _make_orchestrator() -> SecretaryOrchestrator:
    """Build an orchestrator with mocked DB and priority engine."""
    db = AsyncMock()
    priority_engine = AsyncMock()
    return SecretaryOrchestrator(db=db, priority_engine=priority_engine)


# ===================================================================
# Test: DayTheme dataclass field completeness
# ===================================================================

class TestDayThemeDataclass:
    """Verify the DayTheme frozen dataclass structure."""

    def test_all_fields_present(self):
        theme = DayTheme(
            title="Test Title",
            primary_event_id=uuid.uuid4(),
            focus="Focus text",
            prep_note="Prep note",
            evening_forward="Tomorrow warning",
        )
        assert theme.title == "Test Title"
        assert theme.primary_event_id is not None
        assert theme.focus == "Focus text"
        assert theme.prep_note == "Prep note"
        assert theme.evening_forward == "Tomorrow warning"

    def test_optional_fields_default_to_none(self):
        theme = DayTheme(
            title="Minimal",
            primary_event_id=None,
            focus="Focus",
        )
        assert theme.prep_note is None
        assert theme.evening_forward is None

    def test_frozen_immutability(self):
        theme = DayTheme(
            title="Frozen",
            primary_event_id=None,
            focus="Focus",
        )
        with pytest.raises(AttributeError):
            theme.title = "Modified"


# ===================================================================
# Test: Trip theme (Rule 1)
# ===================================================================

class TestTripTheme:
    """Trip events should produce a theme with the trip name."""

    def test_trip_event_produces_theme_with_trip_name(self):
        trip_id = uuid.uuid4()
        event = _make_event(
            title="Day 1 - Arrival",
            trip_id=trip_id,
            trip_name="Tokyo Business Trip",
        )
        score = _make_score(0.7)

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[event],
            scores=[score],
            density_score=0.3,
        )

        assert theme is not None
        assert theme.title == "Tokyo Business Trip"
        assert theme.primary_event_id == event.id
        assert "今天的重点" in theme.focus

    def test_trip_event_without_trip_name_uses_title(self):
        """If trip_name is None, fall back to event title."""
        trip_id = uuid.uuid4()
        event = _make_event(
            title="Shanghai Visit Day 2",
            trip_id=trip_id,
            trip_name=None,
        )
        score = _make_score(0.5)

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[event],
            scores=[score],
            density_score=0.3,
        )

        assert theme is not None
        assert theme.title == "Shanghai Visit Day 2"

    def test_trip_takes_priority_over_p0_event(self):
        """When both trip and P0 events exist, trip theme wins."""
        trip_id = uuid.uuid4()
        trip_event = _make_event(
            title="Flight to Tokyo",
            trip_id=trip_id,
            trip_name="Tokyo Trip",
            start_hour=8,
        )
        p0_event = _make_event(
            title="Critical Board Meeting",
            event_type="meeting",
            start_hour=14,
        )
        trip_score = _make_score(0.5)
        p0_score = _make_score(0.95)  # P0 level

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[trip_event, p0_event],
            scores=[trip_score, p0_score],
            density_score=0.6,
        )

        assert theme is not None
        assert theme.title == "Tokyo Trip"

    def test_multiple_trip_events_picks_highest_scored(self):
        """Among multiple trip events, pick the one with highest composite."""
        trip_id = uuid.uuid4()
        ev1 = _make_event(title="Morning Arrival", trip_id=trip_id, trip_name="Trip A")
        ev2 = _make_event(title="Key Client Meet", trip_id=trip_id, trip_name="Trip A")
        s1 = _make_score(0.4)
        s2 = _make_score(0.9)

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[ev1, ev2],
            scores=[s1, s2],
            density_score=0.5,
        )

        assert theme is not None
        assert theme.primary_event_id == ev2.id


# ===================================================================
# Test: P0/P1 theme (Rule 2)
# ===================================================================

class TestHighPriorityTheme:
    """P0/P1 events (no trip) should produce a themed day."""

    def test_p0_event_produces_theme(self):
        event = _make_event(title="Annual Review", event_type="meeting")
        score = _make_score(0.85)  # P0

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[event],
            scores=[score],
            density_score=0.4,
        )

        assert theme is not None
        assert theme.title == "Annual Review"
        assert theme.primary_event_id == event.id
        assert "最重要的事" in theme.focus

    def test_p1_event_produces_theme(self):
        event = _make_event(title="Quarterly Planning", event_type="meeting")
        score = _make_score(0.65)  # P1

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[event],
            scores=[score],
            density_score=0.4,
        )

        assert theme is not None
        assert theme.title == "Quarterly Planning"

    def test_p2_event_no_theme_with_normal_density(self):
        """P2 event with density <= 0.8 → None."""
        event = _make_event(title="Team Lunch", event_type="other")
        score = _make_score(0.4)  # P2

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[event],
            scores=[score],
            density_score=0.5,
        )

        assert theme is None


# ===================================================================
# Test: High density theme (Rule 3)
# ===================================================================

class TestHighDensityTheme:
    """density_score > 0.8 with no trip / P0/P1 → "忙碌的一天"."""

    def test_high_density_produces_theme(self):
        events = [
            _make_event(title=f"Event {i}", start_hour=8 + i)
            for i in range(5)
        ]
        scores = [_make_score(0.4) for _ in events]  # all P2

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=events,
            scores=scores,
            density_score=0.85,
        )

        assert theme is not None
        assert theme.title == "忙碌的一天"
        assert theme.primary_event_id is None
        assert "事情比较多" in theme.focus

    def test_high_density_with_low_priority_items_includes_prep_note(self):
        """Low-priority events in a high-density day get mentioned in prep_note."""
        events = [
            _make_event(title="Core Meeting", start_hour=9),
            _make_event(title="Code Review", start_hour=11),
            _make_event(title="Optional Sync", start_hour=14),
        ]
        scores = [
            _make_score(0.5),  # P2
            _make_score(0.35),  # P2
            _make_score(0.25),  # P3
        ]

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=events,
            scores=scores,
            density_score=0.85,
        )

        assert theme is not None
        assert theme.prep_note is not None
        # P2/P3 titles should be mentioned
        assert "Optional Sync" in theme.prep_note

    def test_density_exactly_0_8_does_not_trigger(self):
        """density_score == 0.8 does not trigger high-density theme."""
        events = [_make_event(title="Single Event")]
        scores = [_make_score(0.4)]

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=events,
            scores=scores,
            density_score=0.8,
        )

        assert theme is None


# ===================================================================
# Test: No theme (Rule 4)
# ===================================================================

class TestNoTheme:
    """Normal day → day_theme = None."""

    def test_single_low_priority_event_no_theme(self):
        event = _make_event(title="Routine Standup")
        score = _make_score(0.2)  # P3

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[event],
            scores=[score],
            density_score=0.3,
        )

        assert theme is None

    def test_empty_events_returns_none(self):
        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[],
            scores=[],
            density_score=0.0,
        )

        assert theme is None


# ===================================================================
# Test: Evening forward (next-day early events)
# ===================================================================

class TestEveningForward:
    """Evening forward warnings for early-morning next-day events."""

    def test_early_morning_next_day_event_triggers_forward(self):
        """Next-day event before 8:00 → evening_forward populated."""
        event = _make_event(title="Regular Day")
        score = _make_score(0.4)  # P2

        next_day_event = _make_event(title="Early Flight", start_hour=6)
        next_day_event.normalized_start = _utc_dt(hour=6, day_offset=1)

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[event],
            scores=[score],
            density_score=0.4,
            next_day_events=[next_day_event],
        )

        # When there is an evening_forward but no other theme trigger,
        # a minimal theme is returned with title "明日提前关注"
        assert theme is not None
        assert theme.evening_forward is not None
        assert "Early Flight" in theme.evening_forward
        assert "06:00" in theme.evening_forward

    def test_no_early_morning_events_no_forward(self):
        """Next-day events all after 8:00 → no evening_forward."""
        event = _make_event(title="Regular Day")
        score = _make_score(0.2)

        next_day_event = _make_event(title="Afternoon Meeting", start_hour=14)
        next_day_event.normalized_start = _utc_dt(hour=14, day_offset=1)

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[event],
            scores=[score],
            density_score=0.3,
            next_day_events=[next_day_event],
        )

        assert theme is None

    def test_trip_theme_includes_evening_forward(self):
        """Trip theme should also include evening_forward if applicable."""
        trip_id = uuid.uuid4()
        event = _make_event(
            title="Trip Day 1",
            trip_id=trip_id,
            trip_name="Business Trip",
        )
        score = _make_score(0.7)

        next_day_event = _make_event(title="05:30 Train", start_hour=5)
        next_day_event.normalized_start = _utc_dt(hour=5, minute=30, day_offset=1)

        orch = _make_orchestrator()
        theme = orch._generate_day_theme(
            events=[event],
            scores=[score],
            density_score=0.4,
            next_day_events=[next_day_event],
        )

        assert theme is not None
        assert theme.title == "Business Trip"
        assert theme.evening_forward is not None
        assert "05:30" in theme.evening_forward


# ===================================================================
# Test: _build_prep_note and _build_focus_text helpers
# ===================================================================

class TestHelpers:
    """Test static helper methods used by _generate_day_theme."""

    def test_build_focus_text_with_start_time(self):
        event = _make_event(title="Client Presentation", start_hour=15)
        score = _make_score(0.8)

        text = SecretaryOrchestrator._build_focus_text(event, score)

        assert "15:00" in text
        assert "Client Presentation" in text
        assert "最重要的事" in text

    def test_build_focus_text_without_start_time(self):
        event = _make_event(title="Flexible Task")
        event.normalized_start = None
        score = _make_score(0.8)

        text = SecretaryOrchestrator._build_focus_text(event, score)

        assert "Flexible Task" in text
        assert "最重要的事" in text

    def test_build_prep_note_with_preparation_hours(self):
        event = _make_event(title="Board Review")
        score = _make_score(0.8, preparation_hours=3.0)

        note = SecretaryOrchestrator._build_prep_note(event, score)

        assert note is not None
        assert "3 小时" in note or "3" in note
        assert "Board Review" in note

    def test_build_prep_note_meeting_without_prep_hours(self):
        event = _make_event(title="Team Sync", event_type="meeting")
        score = _make_score(0.6, preparation_hours=0.0)

        note = SecretaryOrchestrator._build_prep_note(event, score)

        assert note is not None
        assert "Team Sync" in note
        assert "过一遍" in note

    def test_build_prep_note_generic_event_no_prep(self):
        event = _make_event(title="Lunch", event_type="other")
        score = _make_score(0.3, preparation_hours=0.0)

        note = SecretaryOrchestrator._build_prep_note(event, score)

        assert note is None
