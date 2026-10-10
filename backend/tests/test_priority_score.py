"""Tests for PriorityScore four-dimension scoring.

Covers:
- PriorityScore dataclass: composite, priority_level, to_dict
- Dimension scoring functions: urgency, severity, stakeholder, irrecoverability
- compute_priority_score integration
- Boundary conditions for P0/P1/P2/P3 levels
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.modules.curation.services.priority_score import (
    PriorityScore,
    compute_priority_score,
    _score_urgency,
    _score_severity,
    _score_stakeholder_weight,
    _score_irrecoverability,
)


# ---------------------------------------------------------------------------
# PriorityScore dataclass
# ---------------------------------------------------------------------------


class TestPriorityScore:

    def test_composite_weighted_sum(self):
        ps = PriorityScore(
            urgency=1.0, severity=1.0,
            stakeholder_weight=1.0, irrecoverability=1.0,
        )
        assert ps.composite == pytest.approx(1.0)

    def test_composite_zero(self):
        ps = PriorityScore(
            urgency=0.0, severity=0.0,
            stakeholder_weight=0.0, irrecoverability=0.0,
        )
        assert ps.composite == pytest.approx(0.0)

    def test_composite_mixed(self):
        ps = PriorityScore(
            urgency=0.5, severity=0.5,
            stakeholder_weight=0.5, irrecoverability=0.5,
        )
        # 0.5 * (0.30 + 0.25 + 0.25 + 0.20) = 0.5
        assert ps.composite == pytest.approx(0.5)

    def test_priority_level_p0(self):
        ps = PriorityScore(urgency=1.0, severity=1.0, stakeholder_weight=1.0, irrecoverability=1.0)
        assert ps.priority_level == "P0"

    def test_priority_level_p1(self):
        ps = PriorityScore(urgency=0.7, severity=0.7, stakeholder_weight=0.6, irrecoverability=0.5)
        assert ps.composite >= 0.6
        assert ps.composite < 0.8
        assert ps.priority_level == "P1"

    def test_priority_level_p2(self):
        ps = PriorityScore(urgency=0.4, severity=0.3, stakeholder_weight=0.3, irrecoverability=0.3)
        assert ps.composite >= 0.3
        assert ps.composite < 0.6
        assert ps.priority_level == "P2"

    def test_priority_level_p3(self):
        ps = PriorityScore(urgency=0.1, severity=0.1, stakeholder_weight=0.1, irrecoverability=0.1)
        assert ps.composite < 0.3
        assert ps.priority_level == "P3"

    def test_boundary_p0(self):
        """Exact 0.8 composite should be P0."""
        ps = PriorityScore(urgency=0.8, severity=0.8, stakeholder_weight=0.8, irrecoverability=0.8)
        assert ps.composite == pytest.approx(0.8)
        assert ps.priority_level == "P0"

    def test_boundary_p1(self):
        """Exact 0.6 composite should be P1."""
        ps = PriorityScore(urgency=0.6, severity=0.6, stakeholder_weight=0.6, irrecoverability=0.6)
        assert ps.composite == pytest.approx(0.6)
        assert ps.priority_level == "P1"

    def test_boundary_p2(self):
        """Exact 0.3 composite should be P2."""
        ps = PriorityScore(urgency=0.3, severity=0.3, stakeholder_weight=0.3, irrecoverability=0.3)
        assert ps.composite == pytest.approx(0.3)
        assert ps.priority_level == "P2"

    def test_to_dict(self):
        ps = PriorityScore(urgency=0.9, severity=0.8, stakeholder_weight=0.7, irrecoverability=0.6)
        d = ps.to_dict()
        assert d["urgency"] == 0.9
        assert d["severity"] == 0.8
        assert d["stakeholder_weight"] == 0.7
        assert d["irrecoverability"] == 0.6
        assert "composite" in d
        assert "priority_level" in d

    def test_frozen(self):
        ps = PriorityScore(urgency=0.5, severity=0.5, stakeholder_weight=0.5, irrecoverability=0.5)
        with pytest.raises(AttributeError):
            ps.urgency = 0.9


# ---------------------------------------------------------------------------
# Individual dimension scoring
# ---------------------------------------------------------------------------


class TestScoreUrgency:

    def test_past_event(self):
        assert _score_urgency(-1.0) == 1.0

    def test_within_2_hours(self):
        assert _score_urgency(1.5) == 0.95

    def test_within_6_hours(self):
        assert _score_urgency(5.0) == 0.85

    def test_within_24_hours(self):
        assert _score_urgency(20.0) == 0.6

    def test_next_week(self):
        assert _score_urgency(100.0) == 0.25

    def test_far_future(self):
        assert _score_urgency(500.0) == 0.1

    def test_none_hours(self):
        assert _score_urgency(None) == 0.3


class TestScoreSeverity:

    def test_business_trip_critical(self):
        score = _score_severity("business_trip", "critical")
        assert score == pytest.approx(1.0)

    def test_meeting_normal(self):
        score = _score_severity("meeting", "normal")
        assert score == 0.7

    def test_unknown_type_low_priority(self):
        score = _score_severity("other", "low")
        assert score == pytest.approx(0.2)

    def test_associations_boost(self):
        base = _score_severity("reminder", "normal")
        with_assoc = _score_severity("reminder", "normal", association_count=3)
        assert with_assoc > base

    def test_clamped_to_0_1(self):
        score = _score_severity("business_trip", "critical", association_count=10)
        assert score <= 1.0
        score_low = _score_severity("other", "low")
        assert score_low >= 0.0


class TestScoreStakeholderWeight:

    def test_none_context(self):
        assert _score_stakeholder_weight(None) == 0.3

    def test_high_participant_count(self):
        score = _score_stakeholder_weight({"participant_count": 5})
        assert score == 0.6

    def test_close_relation(self):
        score = _score_stakeholder_weight({
            "relation_types": ["spouse"],
            "has_close_relation": True,
        })
        assert score >= 0.6

    def test_multiple_factors(self):
        score = _score_stakeholder_weight({
            "participant_count": 3,
            "relation_types": ["child"],
        })
        assert score >= 0.6


class TestScoreIrrecoverability:

    def test_flight_irrecoverable(self):
        assert _score_irrecoverability("flight") == 0.9

    def test_meeting_moderate(self):
        assert _score_irrecoverability("meeting") == 0.5

    def test_with_booking(self):
        assert _score_irrecoverability("travel", has_booking=True) == 0.7

    def test_unknown_type(self):
        assert _score_irrecoverability("other") == 0.2


# ---------------------------------------------------------------------------
# compute_priority_score integration
# ---------------------------------------------------------------------------


class TestComputePriorityScore:

    def test_urgent_business_meeting(self):
        """Urgent business meeting with close family = P0."""
        now = datetime.now(timezone.utc)
        ps = compute_priority_score(
            event_data={
                "normalized_start": now + timedelta(hours=1),
                "event_type": "business_trip",
                "priority": "critical",
                "association_count": 4,
            },
            member_context={
                "participant_count": 3,
                "relation_types": ["spouse"],
                "has_close_relation": True,
            },
            now=now,
        )
        assert ps.priority_level == "P0"
        assert ps.composite >= 0.8

    def test_far_future_low_event(self):
        """Low-priority event far in the future = P3."""
        now = datetime.now(timezone.utc)
        ps = compute_priority_score(
            event_data={
                "normalized_start": now + timedelta(days=30),
                "event_type": "reminder",
                "priority": "low",
            },
            now=now,
        )
        assert ps.priority_level == "P3"
        assert ps.composite < 0.3

    def test_no_start_time(self):
        """Missing start time uses moderate urgency default."""
        ps = compute_priority_score(
            event_data={
                "event_type": "meeting",
                "priority": "normal",
            },
        )
        assert ps.urgency == 0.3
        assert ps.priority_level in ("P1", "P2")

    def test_iso_string_start_time(self):
        """ISO string start time is parsed correctly."""
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=3)
        ps = compute_priority_score(
            event_data={
                "normalized_start": future.isoformat(),
                "event_type": "appointment",
                "priority": "high",
            },
            now=now,
        )
        assert ps.urgency > 0.5

    def test_returns_priority_score(self):
        ps = compute_priority_score({"priority": "normal"})
        assert isinstance(ps, PriorityScore)
        assert 0.0 <= ps.composite <= 1.0
