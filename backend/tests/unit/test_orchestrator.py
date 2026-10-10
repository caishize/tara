"""Tests for SecretaryOrchestrator -- structured day planning."""

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.curation.services.orchestrator import (
    CascadeAnalysis,
    CascadeImpact,
    GapWarning,
    OrchestratedDay,
    PreparationItem,
    PreparationStep,
    PreparationTimeline,
    SecretaryOrchestrator,
    TimeSlot,
    _compute_density,
    _compute_gap,
    _DEFAULT_BUFFERS,
    _resolve_buffers,
    _time_diff_minutes,
)
from src.modules.curation.services.priority_score import PriorityScore
from src.modules.curation.services.priority_engine import EnhancedPriorityScore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_curated_event(
    event_id=None,
    title="Test Event",
    event_type="meeting",
    start_dt=None,
    end_dt=None,
    location=None,
    priority="normal",
    trip_id=None,
    associations=None,
):
    ev = SimpleNamespace(
        id=event_id or uuid4(),
        title=title,
        event_type=event_type,
        normalized_start=start_dt,
        normalized_end=end_dt,
        location=location,
        priority=priority,
        trip_id=trip_id,
        associations=associations or [],
    )
    return ev


def _make_enhanced_score(composite_val=0.5):
    base = PriorityScore(
        urgency=composite_val,
        severity=composite_val,
        stakeholder_weight=composite_val,
        irrecoverability=composite_val,
    )
    return EnhancedPriorityScore(base=base)


# ---------------------------------------------------------------------------
# _compute_density
# ---------------------------------------------------------------------------

class TestComputeDensity:

    def test_zero_events(self):
        assert _compute_density([], date(2026, 2, 23)) == 0.0

    def test_eight_events_with_full_coverage(self):
        events = []
        base_dt = datetime(2026, 2, 23, 8, 0, tzinfo=timezone.utc)
        for i in range(8):
            ev = _mock_curated_event(
                start_dt=base_dt + timedelta(hours=i * 1.5),
                end_dt=base_dt + timedelta(hours=i * 1.5 + 1.5),
            )
            events.append((ev, _make_enhanced_score()))
        density = _compute_density(events, date(2026, 2, 23))
        # count_factor = 8/8 = 1.0, coverage = 12h/12h = 1.0
        assert density == pytest.approx(1.0, abs=0.01)

    def test_few_events_low_density(self):
        ev = _mock_curated_event(
            start_dt=datetime(2026, 2, 23, 9, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
        )
        density = _compute_density([(ev, _make_enhanced_score())], date(2026, 2, 23))
        # count_factor = 1/8 = 0.125, coverage = 1h/12h ~ 0.083
        assert density < 0.2

    def test_events_without_end_assume_1h(self):
        ev = _mock_curated_event(start_dt=None, end_dt=None)
        density = _compute_density([(ev, _make_enhanced_score())], date(2026, 2, 23))
        # count = 1/8 = 0.125, coverage = 1h/12h ~ 0.083
        assert density > 0.0


# ---------------------------------------------------------------------------
# _compute_gap
# ---------------------------------------------------------------------------

class TestComputeGap:

    def test_back_to_back_events(self):
        ev1 = _mock_curated_event(title="A", location="Office")
        ev2 = _mock_curated_event(title="B", location="Office")
        result = _compute_gap(
            ev1, ev2,
            prev_end=time(10, 0),
            next_start=time(10, 0),
            buffers=_DEFAULT_BUFFERS,
        )
        assert result.warning is not None
        assert result.warning.gap_type == "back_to_back"
        assert result.buffer_slot is None

    def test_overlapping_events(self):
        ev1 = _mock_curated_event(title="A")
        ev2 = _mock_curated_event(title="B")
        result = _compute_gap(
            ev1, ev2,
            prev_end=time(10, 30),
            next_start=time(10, 0),
            buffers=_DEFAULT_BUFFERS,
        )
        assert result.warning is not None
        assert result.warning.gap_type == "back_to_back"

    def test_no_buffer_warning(self):
        ev1 = _mock_curated_event(title="A", location="Office")
        ev2 = _mock_curated_event(title="B", location="Office")
        result = _compute_gap(
            ev1, ev2,
            prev_end=time(10, 0),
            next_start=time(10, 10),  # 10 min gap, default requires 15
            buffers=_DEFAULT_BUFFERS,
        )
        assert result.warning is not None
        assert result.warning.gap_type == "no_buffer"
        assert result.buffer_slot is not None

    def test_impossible_commute_with_location_change(self):
        ev1 = _mock_curated_event(title="A", location="Downtown")
        ev2 = _mock_curated_event(title="B", location="Airport")
        result = _compute_gap(
            ev1, ev2,
            prev_end=time(10, 0),
            next_start=time(10, 20),  # 20 min, location change needs 45
            buffers=_DEFAULT_BUFFERS,
        )
        assert result.warning is not None
        assert result.warning.gap_type == "impossible_commute"

    def test_sufficient_gap_no_warning(self):
        ev1 = _mock_curated_event(title="A", location="Office")
        ev2 = _mock_curated_event(title="B", location="Office")
        result = _compute_gap(
            ev1, ev2,
            prev_end=time(10, 0),
            next_start=time(11, 0),  # 60 min gap
            buffers=_DEFAULT_BUFFERS,
        )
        assert result.warning is None
        assert result.buffer_slot is not None

    def test_meal_window_suggestion(self):
        ev1 = _mock_curated_event(title="A", location="Office")
        ev2 = _mock_curated_event(title="B", location="Office")
        result = _compute_gap(
            ev1, ev2,
            prev_end=time(11, 45),
            next_start=time(13, 30),  # Crosses lunch window
            buffers=_DEFAULT_BUFFERS,
        )
        assert result.buffer_slot is not None
        assert result.buffer_slot.note is not None
        assert "用餐" in result.buffer_slot.note


# ---------------------------------------------------------------------------
# _resolve_buffers
# ---------------------------------------------------------------------------

class TestResolveBuffers:

    def test_default_buffers(self):
        buffers = _resolve_buffers(None)
        assert buffers["default"] == 15
        assert buffers["location_change"] == 45
        assert buffers["high_intensity"] == 20

    def test_family_prefs_override(self):
        prefs = SimpleNamespace(buffer_minutes={"default": 10, "meeting": 5})
        buffers = _resolve_buffers(prefs)
        assert buffers["default"] == 10
        assert buffers["meeting"] == 5
        # Unchanged defaults
        assert buffers["location_change"] == 45

    def test_family_prefs_without_buffer_minutes(self):
        prefs = SimpleNamespace(buffer_minutes=None)
        buffers = _resolve_buffers(prefs)
        assert buffers == dict(_DEFAULT_BUFFERS)


# ---------------------------------------------------------------------------
# _time_diff_minutes
# ---------------------------------------------------------------------------

class TestTimeDiffMinutes:

    def test_positive_diff(self):
        assert _time_diff_minutes(time(10, 0), time(10, 30)) == pytest.approx(30.0)

    def test_zero_diff(self):
        assert _time_diff_minutes(time(10, 0), time(10, 0)) == pytest.approx(0.0)

    def test_negative_diff(self):
        assert _time_diff_minutes(time(10, 30), time(10, 0)) == pytest.approx(-30.0)


# ---------------------------------------------------------------------------
# analyze_cascade
# ---------------------------------------------------------------------------

class TestAnalyzeCascade:

    @pytest.fixture()
    def orchestrator(self):
        db = AsyncMock()
        engine = AsyncMock()
        with patch(
            "src.modules.curation.services.orchestrator.ContextEnricher",
        ), patch(
            "src.modules.curation.services.orchestrator.MemoryEngine",
        ):
            return SecretaryOrchestrator(db, engine)

    @pytest.mark.asyncio
    async def test_delayed_identifies_conflict(self, orchestrator):
        changed = _mock_curated_event(
            title="Meeting",
            end_dt=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
        )
        # E1: normal-priority events get auto_defer (no user decision)
        affected = _mock_curated_event(
            title="Lunch",
            start_dt=datetime(2026, 2, 23, 10, 30, tzinfo=timezone.utc),
        )
        result = await orchestrator.analyze_cascade(
            changed, "delayed", {"delay_minutes": 60}, [affected],
        )
        assert len(result.impacts) == 1
        assert result.impacts[0].impact_type == "auto_defer"
        assert result.requires_user_decision is False

    @pytest.mark.asyncio
    async def test_delayed_high_priority_requires_decision(self, orchestrator):
        """E1: High-priority events still require user decision on delay."""
        changed = _mock_curated_event(
            title="Meeting",
            end_dt=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
        )
        affected = _mock_curated_event(
            title="Important Lunch",
            priority="high",
            start_dt=datetime(2026, 2, 23, 10, 30, tzinfo=timezone.utc),
        )
        result = await orchestrator.analyze_cascade(
            changed, "delayed", {"delay_minutes": 60}, [affected],
        )
        assert len(result.impacts) == 1
        assert result.impacts[0].impact_type == "delayed"
        assert result.requires_user_decision is True

    @pytest.mark.asyncio
    async def test_delayed_no_impact_when_gap_sufficient(self, orchestrator):
        # End at 10:00, delay 10 min -> new_end = 10:10
        # Affected starts at 10:30 -> 10:30 < 10:10 is False -> no impact
        changed = _mock_curated_event(
            title="Call",
            end_dt=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
        )
        affected = _mock_curated_event(
            title="Next",
            start_dt=datetime(2026, 2, 23, 10, 30, tzinfo=timezone.utc),
        )
        result = await orchestrator.analyze_cascade(
            changed, "delayed", {"delay_minutes": 10}, [affected],
        )
        assert len(result.impacts) == 0

    @pytest.mark.asyncio
    async def test_delayed_zero_minutes(self, orchestrator):
        changed = _mock_curated_event(
            title="Event",
            end_dt=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
        )
        result = await orchestrator.analyze_cascade(
            changed, "delayed", {"delay_minutes": 0}, [],
        )
        assert len(result.impacts) == 0
        assert "不明确" in result.summary

    @pytest.mark.asyncio
    async def test_cancelled_same_trip(self, orchestrator):
        """E1: Normal-priority events get auto_cancel, no user decision."""
        trip_id = uuid4()
        changed = _mock_curated_event(title="Flight", trip_id=trip_id)
        affected = _mock_curated_event(title="Hotel Check-in", trip_id=trip_id)
        result = await orchestrator.analyze_cascade(
            changed, "cancelled", {}, [affected],
        )
        assert len(result.impacts) == 1
        assert result.impacts[0].impact_type == "auto_cancel"
        assert result.impacts[0].requires_user_decision is False

    @pytest.mark.asyncio
    async def test_cancelled_same_trip_high_priority(self, orchestrator):
        """E1: Critical-priority events need user decision on cancel."""
        trip_id = uuid4()
        changed = _mock_curated_event(title="Flight", trip_id=trip_id)
        affected = _mock_curated_event(
            title="VIP Meeting", trip_id=trip_id, priority="critical",
        )
        result = await orchestrator.analyze_cascade(
            changed, "cancelled", {}, [affected],
        )
        assert len(result.impacts) == 1
        assert result.impacts[0].impact_type == "needs_reschedule"
        assert result.impacts[0].requires_user_decision is True

    @pytest.mark.asyncio
    async def test_cancelled_different_trip_no_impact(self, orchestrator):
        changed = _mock_curated_event(title="Flight", trip_id=uuid4())
        affected = _mock_curated_event(title="Other", trip_id=uuid4())
        result = await orchestrator.analyze_cascade(
            changed, "cancelled", {}, [affected],
        )
        assert len(result.impacts) == 0

    @pytest.mark.asyncio
    async def test_time_changed_impacts_all(self, orchestrator):
        changed = _mock_curated_event(title="Main")
        affected1 = _mock_curated_event(title="After1")
        affected2 = _mock_curated_event(title="After2")
        result = await orchestrator.analyze_cascade(
            changed, "time_changed", {}, [affected1, affected2],
        )
        assert len(result.impacts) == 2
        assert all(i.requires_user_decision for i in result.impacts)

    @pytest.mark.asyncio
    async def test_location_changed_impacts_all(self, orchestrator):
        changed = _mock_curated_event(title="Moved")
        affected = _mock_curated_event(title="Next")
        result = await orchestrator.analyze_cascade(
            changed, "location_changed", {}, [affected],
        )
        assert len(result.impacts) == 1
        assert result.impacts[0].impact_type == "needs_reschedule"


# ---------------------------------------------------------------------------
# build_preparation_timeline
# ---------------------------------------------------------------------------

class TestBuildPreparationTimeline:

    @pytest.fixture()
    def orchestrator(self):
        db = AsyncMock()
        engine = AsyncMock()
        with patch(
            "src.modules.curation.services.orchestrator.ContextEnricher",
        ), patch(
            "src.modules.curation.services.orchestrator.MemoryEngine",
        ):
            return SecretaryOrchestrator(db, engine)

    @pytest.mark.asyncio
    async def test_basic_timeline(self, orchestrator):
        anchor = _mock_curated_event(
            title="Presentation",
            start_dt=datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc),
        )
        items = [
            PreparationItem(title="Review slides", duration_minutes=30),
            PreparationItem(title="Print handouts", duration_minutes=10),
        ]
        timeline = await orchestrator.build_preparation_timeline(anchor, items)

        assert len(timeline.steps) == 2
        # Steps should be ordered earliest first
        assert timeline.steps[0].suggested_start < timeline.steps[1].suggested_start
        # Last step deadline should be 10 min before anchor
        assert all(s.deadline < anchor.normalized_start for s in timeline.steps)

    @pytest.mark.asyncio
    async def test_buffer_between_steps(self, orchestrator):
        anchor = _mock_curated_event(
            title="Event",
            start_dt=datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc),
        )
        items = [PreparationItem(title="Task A", duration_minutes=20)]
        timeline = await orchestrator.build_preparation_timeline(anchor, items)

        step = timeline.steps[0]
        # deadline should be 10 min before anchor (buffer)
        expected_deadline = anchor.normalized_start - timedelta(minutes=10)
        assert step.deadline == expected_deadline
        # suggested_start should be 20 min before deadline
        expected_start = expected_deadline - timedelta(minutes=20)
        assert step.suggested_start == expected_start

    @pytest.mark.asyncio
    async def test_no_start_time_returns_empty(self, orchestrator):
        anchor = _mock_curated_event(title="Vague", start_dt=None)
        items = [PreparationItem(title="Task", duration_minutes=30)]
        timeline = await orchestrator.build_preparation_timeline(anchor, items)
        assert len(timeline.steps) == 0


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------

class TestFrozenDataclasses:

    def test_time_slot_frozen(self):
        slot = TimeSlot(start=time(10, 0), end=time(11, 0))
        with pytest.raises(AttributeError):
            slot.start = time(9, 0)

    def test_gap_warning_frozen(self):
        gw = GapWarning(gap_type="back_to_back")
        with pytest.raises(AttributeError):
            gw.gap_type = "other"

    def test_orchestrated_day_frozen(self):
        day = OrchestratedDay(target_date=date(2026, 2, 23))
        with pytest.raises(AttributeError):
            day.density_score = 0.5

    def test_cascade_analysis_requires_user_decision(self):
        impact = CascadeImpact(
            event_id=uuid4(),
            event_title="Test",
            impact_type="delayed",
            detail="overlap",
            requires_user_decision=True,
        )
        analysis = CascadeAnalysis(
            changed_event_id=uuid4(),
            change_type="delayed",
            impacts=(impact,),
        )
        assert analysis.requires_user_decision is True

    def test_cascade_analysis_no_impacts_no_decision(self):
        analysis = CascadeAnalysis(
            changed_event_id=uuid4(),
            change_type="cancelled",
        )
        assert analysis.requires_user_decision is False


# ---------------------------------------------------------------------------
# orchestrate_day
# ---------------------------------------------------------------------------

class TestOrchestrateDay:

    @pytest.fixture()
    def orchestrator(self):
        db = AsyncMock()
        engine = AsyncMock()
        with patch(
            "src.modules.curation.services.orchestrator.ContextEnricher",
        ), patch(
            "src.modules.curation.services.orchestrator.MemoryEngine",
        ):
            return SecretaryOrchestrator(db, engine)

    @pytest.mark.asyncio
    async def test_empty_events(self, orchestrator):
        result = await orchestrator.orchestrate_day(
            family_id=uuid4(),
            user_id=uuid4(),
            target_date=date(2026, 2, 23),
            events=[],
        )
        assert result.slots == ()
        assert result.gaps == ()
        assert result.annotations == ()
        assert result.density_score == 0.0
        assert result.suggested_reorder is None

    @pytest.mark.asyncio
    async def test_single_event_basic_slots(self, orchestrator):
        ev = _mock_curated_event(
            title="Standup",
            start_dt=datetime(2026, 2, 23, 9, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
        )
        score = _make_enhanced_score(0.5)
        orchestrator._priority_engine.score_batch = AsyncMock(return_value=[score])
        orchestrator._enricher.enrich_event = AsyncMock(
            return_value=SimpleNamespace(
                historical_summary=None, people_summary=None, event_chain_summary=None,
            ),
        )

        result = await orchestrator.orchestrate_day(
            family_id=uuid4(),
            user_id=uuid4(),
            target_date=date(2026, 2, 23),
            events=[ev],
        )

        event_slots = [s for s in result.slots if s.slot_type == "event"]
        assert len(event_slots) == 1
        assert event_slots[0].event_id == ev.id
        assert result.density_score > 0.0

    @pytest.mark.asyncio
    async def test_two_events_with_buffer(self, orchestrator):
        ev1 = _mock_curated_event(
            title="Meeting A",
            start_dt=datetime(2026, 2, 23, 9, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
            location="Office",
        )
        ev2 = _mock_curated_event(
            title="Meeting B",
            start_dt=datetime(2026, 2, 23, 10, 20, tzinfo=timezone.utc),
            end_dt=datetime(2026, 2, 23, 11, 0, tzinfo=timezone.utc),
            location="Office",
        )
        scores = [_make_enhanced_score(0.5), _make_enhanced_score(0.4)]
        orchestrator._priority_engine.score_batch = AsyncMock(return_value=scores)
        orchestrator._enricher.enrich_event = AsyncMock(
            return_value=SimpleNamespace(
                historical_summary=None, people_summary=None, event_chain_summary=None,
            ),
        )

        result = await orchestrator.orchestrate_day(
            family_id=uuid4(),
            user_id=uuid4(),
            target_date=date(2026, 2, 23),
            events=[ev1, ev2],
        )

        buffer_slots = [s for s in result.slots if s.slot_type == "buffer"]
        assert len(buffer_slots) >= 1

    @pytest.mark.asyncio
    async def test_location_change_commute_buffer(self, orchestrator):
        ev1 = _mock_curated_event(
            title="Downtown Meeting",
            start_dt=datetime(2026, 2, 23, 9, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
            location="Downtown",
        )
        ev2 = _mock_curated_event(
            title="Airport Check-in",
            start_dt=datetime(2026, 2, 23, 10, 20, tzinfo=timezone.utc),
            end_dt=datetime(2026, 2, 23, 11, 0, tzinfo=timezone.utc),
            location="Airport",
        )
        scores = [_make_enhanced_score(0.5), _make_enhanced_score(0.4)]
        orchestrator._priority_engine.score_batch = AsyncMock(return_value=scores)
        orchestrator._enricher.enrich_event = AsyncMock(
            return_value=SimpleNamespace(
                historical_summary=None, people_summary=None, event_chain_summary=None,
            ),
        )

        result = await orchestrator.orchestrate_day(
            family_id=uuid4(),
            user_id=uuid4(),
            target_date=date(2026, 2, 23),
            events=[ev1, ev2],
        )

        commute_warnings = [g for g in result.gaps if g.gap_type == "impossible_commute"]
        assert len(commute_warnings) == 1

    @pytest.mark.asyncio
    async def test_high_density_triggers_reorder(self, orchestrator):
        base_dt = datetime(2026, 2, 23, 7, 0, tzinfo=timezone.utc)
        events = []
        scores = []
        # 8 events of 1.5h each covering 7:00-19:00 (12h) => density ~ 1.0
        for i in range(8):
            events.append(_mock_curated_event(
                title=f"Event {i}",
                start_dt=base_dt + timedelta(hours=i * 1.5),
                end_dt=base_dt + timedelta(hours=i * 1.5 + 1.5),
                location="Office",
            ))
            scores.append(_make_enhanced_score(0.9 - i * 0.05))

        orchestrator._priority_engine.score_batch = AsyncMock(return_value=scores)
        orchestrator._enricher.enrich_event = AsyncMock(
            return_value=SimpleNamespace(
                historical_summary=None, people_summary=None, event_chain_summary=None,
            ),
        )

        result = await orchestrator.orchestrate_day(
            family_id=uuid4(),
            user_id=uuid4(),
            target_date=date(2026, 2, 23),
            events=events,
        )

        assert result.density_score > 0.8
        assert result.suggested_reorder is not None
        overloaded_gaps = [g for g in result.gaps if g.gap_type == "overloaded"]
        assert len(overloaded_gaps) >= 1

    @pytest.mark.asyncio
    async def test_family_prefs_buffer_override(self, orchestrator):
        # Use event_type="appointment" (not high-intensity) so the "default"
        # buffer applies instead of "high_intensity".
        ev1 = _mock_curated_event(
            title="Task A",
            event_type="appointment",
            start_dt=datetime(2026, 2, 23, 9, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
            location="Office",
        )
        ev2 = _mock_curated_event(
            title="Task B",
            event_type="appointment",
            start_dt=datetime(2026, 2, 23, 10, 12, tzinfo=timezone.utc),
            end_dt=datetime(2026, 2, 23, 11, 0, tzinfo=timezone.utc),
            location="Office",
        )
        scores = [_make_enhanced_score(0.5), _make_enhanced_score(0.4)]
        orchestrator._priority_engine.score_batch = AsyncMock(return_value=scores)
        orchestrator._enricher.enrich_event = AsyncMock(
            return_value=SimpleNamespace(
                historical_summary=None, people_summary=None, event_chain_summary=None,
            ),
        )

        # With default 15-min buffer, 12-min gap triggers "no_buffer" warning.
        # Override to 10 min: 12-min gap is sufficient, no warning expected.
        prefs = SimpleNamespace(buffer_minutes={"default": 10})
        result = await orchestrator.orchestrate_day(
            family_id=uuid4(),
            user_id=uuid4(),
            target_date=date(2026, 2, 23),
            events=[ev1, ev2],
            family_prefs=prefs,
        )

        no_buffer_gaps = [g for g in result.gaps if g.gap_type == "no_buffer"]
        assert len(no_buffer_gaps) == 0

    @pytest.mark.asyncio
    async def test_annotation_generation(self, orchestrator):
        ev = _mock_curated_event(
            title="Anniversary",
            start_dt=datetime(2026, 2, 23, 14, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 2, 23, 15, 0, tzinfo=timezone.utc),
        )
        score = _make_enhanced_score(0.6)
        orchestrator._priority_engine.score_batch = AsyncMock(return_value=[score])
        orchestrator._enricher.enrich_event = AsyncMock(
            return_value=SimpleNamespace(
                historical_summary="Last year was a great celebration",
                people_summary=None,
                event_chain_summary=None,
            ),
        )

        result = await orchestrator.orchestrate_day(
            family_id=uuid4(),
            user_id=uuid4(),
            target_date=date(2026, 2, 23),
            events=[ev],
        )

        enricher_annots = [
            a for a in result.annotations if a.source == "context_enricher"
        ]
        assert len(enricher_annots) >= 1
        assert "Last year" in enricher_annots[0].text

    @pytest.mark.asyncio
    async def test_enricher_failure_graceful(self, orchestrator):
        ev = _mock_curated_event(
            title="Important Call",
            start_dt=datetime(2026, 2, 23, 10, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 2, 23, 11, 0, tzinfo=timezone.utc),
        )
        base = PriorityScore(urgency=0.7, severity=0.7, stakeholder_weight=0.7, irrecoverability=0.7)
        score = EnhancedPriorityScore(base=base, secretary_note="High priority call")
        orchestrator._priority_engine.score_batch = AsyncMock(return_value=[score])
        orchestrator._enricher.enrich_event = AsyncMock(
            side_effect=RuntimeError("DB connection lost"),
        )

        result = await orchestrator.orchestrate_day(
            family_id=uuid4(),
            user_id=uuid4(),
            target_date=date(2026, 2, 23),
            events=[ev],
        )

        # Should still succeed despite enricher failure
        assert len(result.slots) >= 1
        # Priority engine annotations should still be present
        pe_annots = [a for a in result.annotations if a.source == "priority_engine"]
        assert len(pe_annots) >= 1
