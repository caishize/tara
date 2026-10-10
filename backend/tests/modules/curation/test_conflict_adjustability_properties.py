"""
Property-based tests for conflict adjustability analysis

Feature: secretary-intelligence-enhancement
Property 12: Conflict Adjustability Analysis
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timezone
from uuid import uuid4

from src.modules.curation.models import CuratedEvent
from src.modules.curation.services.conflict_resolver_service import ConflictResolver


# Strategies
event_types = st.sampled_from([
    "travel", "flight", "train", "meeting", "appointment",
    "birthday", "anniversary", "task", "reminder", "social"
])

statuses = st.sampled_from(["confirmed", "tentative", "pending", "cancelled"])

priorities = st.sampled_from(["critical", "high", "normal", "low"])


@st.composite
def curated_event_strategy(draw):
    """Generate a CuratedEvent for testing"""
    event_type = draw(event_types)
    status = draw(statuses)
    priority = draw(priorities)
    
    return CuratedEvent(
        id=uuid4(),
        family_id=uuid4(),
        title=draw(st.text(min_size=1, max_size=100)),
        normalized_start=datetime.now(timezone.utc),
        event_type=event_type,
        status=status,
        priority=priority,
    )


class TestConflictAdjustabilityProperties:
    """Property-based tests for conflict adjustability analysis"""
    
    @given(event=curated_event_strategy())
    @settings(max_examples=10, deadline=None)
    def test_property_12_adjustability_classification(self, event):
        """
        **Property 12: Conflict Adjustability Analysis**
        
        **Validates: Requirements 4.1**
        
        For any pair of conflicting events, the Conflict Resolver should
        analyze and classify each event's adjustability (hard_constraint,
        soft_constraint, flexible) based on event type, status, and importance.
        """
        # Create resolver (no session needed for this method)
        resolver = ConflictResolver(session=None)
        
        # Analyze adjustability
        adjustability = resolver._analyze_adjustability(event)
        
        # Property 1: Result must be one of the three valid values
        assert adjustability in ["hard_constraint", "soft_constraint", "flexible"], \
            f"Adjustability must be one of the three valid values, got: {adjustability}"
        
        # Property 2: Confirmed travel/flight/train should be hard constraint
        if event.event_type in ["travel", "flight", "train"] and event.status == "confirmed":
            assert adjustability == "hard_constraint", \
                f"Confirmed {event.event_type} should be hard_constraint, got: {adjustability}"
        
        # Property 3: Birthday/anniversary should always be hard constraint
        if event.event_type in ["birthday", "anniversary"]:
            assert adjustability == "hard_constraint", \
                f"{event.event_type} should be hard_constraint, got: {adjustability}"
        
        # Property 4: Critical priority should not be flexible
        if event.priority == "critical":
            assert adjustability in ["hard_constraint", "soft_constraint"], \
                f"Critical priority should not be flexible, got: {adjustability}"
        
        # Property 5: Confirmed meetings should be hard constraint
        if event.event_type in ["meeting", "appointment"] and event.status == "confirmed":
            assert adjustability == "hard_constraint", \
                f"Confirmed {event.event_type} should be hard_constraint, got: {adjustability}"
    
    @given(
        event_type=event_types,
        status=statuses,
        priority=priorities,
    )
    @settings(max_examples=10, deadline=None)
    def test_property_12_adjustability_consistency(
        self, event_type, status, priority
    ):
        """
        Test that adjustability analysis is consistent for same inputs
        """
        resolver = ConflictResolver(session=None)
        
        # Create two events with same properties
        event1 = CuratedEvent(
            id=uuid4(),
            family_id=uuid4(),
            title="Event 1",
            normalized_start=datetime.now(timezone.utc),
            event_type=event_type,
            status=status,
            priority=priority,
        )
        
        event2 = CuratedEvent(
            id=uuid4(),
            family_id=uuid4(),
            title="Event 2",
            normalized_start=datetime.now(timezone.utc),
            event_type=event_type,
            status=status,
            priority=priority,
        )
        
        # Analyze both
        adj1 = resolver._analyze_adjustability(event1)
        adj2 = resolver._analyze_adjustability(event2)
        
        # Property: Same inputs should produce same adjustability
        assert adj1 == adj2, \
            f"Same event properties should produce same adjustability: {adj1} != {adj2}"
    
    @given(event=curated_event_strategy())
    @settings(max_examples=10, deadline=None)
    def test_property_12_adjustability_ordering(self, event):
        """
        Test that adjustability has a logical ordering:
        hard_constraint > soft_constraint > flexible
        """
        resolver = ConflictResolver(session=None)
        
        adjustability = resolver._analyze_adjustability(event)
        
        # Define ordering
        ordering = {
            "hard_constraint": 3,
            "soft_constraint": 2,
            "flexible": 1,
        }
        
        # Property: Adjustability should have a valid ordering value
        assert adjustability in ordering, \
            f"Adjustability must have a valid ordering: {adjustability}"
        
        # Property: Higher priority events should have higher or equal constraint level
        if event.priority == "critical":
            assert ordering[adjustability] >= 2, \
                f"Critical events should be at least soft_constraint, got: {adjustability}"
        
        # Property: Confirmed events should have higher constraint level than tentative
        if event.status == "confirmed" and event.event_type in [
            "meeting", "appointment", "travel", "flight", "train"
        ]:
            assert ordering[adjustability] >= 2, \
                f"Confirmed {event.event_type} should be at least soft_constraint, got: {adjustability}"
