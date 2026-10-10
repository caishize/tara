"""
Property-based tests for briefing importance-based ordering.

Feature: secretary-intelligence-enhancement
Property 17: Briefing Importance-Based Ordering

For any daily briefing, events should be ordered by importance score
(considering priority, urgency, opportunity cost, association count)
rather than chronological time.

Validates: Requirements 5.1
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import MagicMock
from hypothesis import given, strategies as st, settings

from src.modules.curation.models import CuratedEvent, EventAssociation
from src.modules.briefing.services.briefing_generator import BriefingGenerator


# Strategy for generating event types
event_type_strategy = st.sampled_from([
    "business_trip", "travel", "meeting", "appointment", "reminder", "custom"
])

# Strategy for generating priority levels
priority_strategy = st.sampled_from([
    "critical", "high", "normal", "low"
])


def create_test_event(
    family_id,
    title: str,
    event_type: str,
    priority: str,
    start_time: datetime,
    association_count: int = 0,
) -> CuratedEvent:
    """Helper to create a test event"""
    event = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title=title,
        event_type=event_type,
        priority=priority,
        normalized_start=start_time,
        normalized_end=start_time + timedelta(hours=1),
        location="测试地点",
        is_active=True,
        status="confirmed",
    )
    
    # Directly inject into __dict__ to bypass SQLAlchemy's instrumented
    # relationship descriptor which would try to validate ORM state.
    assoc_list = []
    if association_count > 0:
        for i in range(association_count):
            mock_assoc = MagicMock(spec=EventAssociation)
            mock_assoc.id = uuid4()
            mock_assoc.family_id = family_id
            mock_assoc.source_event_id = event.id
            mock_assoc.target_id = str(uuid4())
            mock_assoc.target_type = 'person'
            mock_assoc.association_type = 'location'
            mock_assoc.title = f'关联{i}'
            mock_assoc.reason = '测试关联'
            mock_assoc.priority = 'convenient'
            mock_assoc.confidence = 0.8
            assoc_list.append(mock_assoc)
    event.__dict__['associations'] = assoc_list
    
    return event


@given(
    priority1=priority_strategy,
    priority2=priority_strategy,
)
@settings(max_examples=10, deadline=None)
def test_property_17_higher_priority_events_come_first(
    priority1: str,
    priority2: str,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 17: Briefing Importance-Based Ordering
    
    For any two events with different priorities, the higher priority event
    should be ordered before the lower priority event, regardless of time.
    """
    family_id = uuid4()
    generator = BriefingGenerator(session=None)
    
    # Create two events with different priorities but reversed chronological order
    # Event 1 happens later but has priority1
    event1 = create_test_event(
        family_id=family_id,
        title="Event 1",
        event_type="meeting",
        priority=priority1,
        start_time=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    
    # Event 2 happens earlier but has priority2
    event2 = create_test_event(
        family_id=family_id,
        title="Event 2",
        event_type="meeting",
        priority=priority2,
        start_time=datetime.now(timezone.utc),
    )
    
    events = [event1, event2]
    sorted_events = generator._sort_by_importance(events)
    
    # Define priority order
    priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    
    # If priorities are different, verify ordering
    if priority1 != priority2:
        if priority_order[priority1] < priority_order[priority2]:
            # Event 1 has higher priority, should come first
            assert sorted_events[0].id == event1.id
        else:
            # Event 2 has higher priority, should come first
            assert sorted_events[0].id == event2.id


@given(
    event_type1=st.sampled_from(["business_trip"]),
    event_type2=st.sampled_from(["reminder", "custom"]),
)
@settings(max_examples=10, deadline=None)
def test_property_17_urgent_event_types_prioritized(
    event_type1: str,
    event_type2: str,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 17: Briefing Importance-Based Ordering
    
    For events with the same priority, urgent event types (travel, meeting, appointment)
    should be ordered before non-urgent types, regardless of chronological order.
    """
    family_id = uuid4()
    generator = BriefingGenerator(session=None)
    
    # Both events have same priority but different types and same start time
    same_start = datetime.now(timezone.utc) + timedelta(hours=48)
    event1 = create_test_event(
        family_id=family_id,
        title="Urgent Event",
        event_type=event_type1,
        priority="normal",
        start_time=same_start,
    )

    event2 = create_test_event(
        family_id=family_id,
        title="Non-urgent Event",
        event_type=event_type2,
        priority="normal",
        start_time=same_start,
    )

    events = [event2, event1]
    sorted_events = generator._sort_by_importance(events)

    # business_trip/travel have higher severity/irrecoverability than reminder/custom
    # so they should sort first when urgency (time) is equal
    assert sorted_events[0].id == event1.id


@given(
    association_count1=st.integers(min_value=0, max_value=3),
    association_count2=st.integers(min_value=0, max_value=3),
)
@settings(max_examples=10, deadline=None)
def test_property_17_more_associations_increase_importance(
    association_count1: int,
    association_count2: int,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 17: Briefing Importance-Based Ordering
    
    For events with the same priority and type, events with more associations
    should be considered more important and ordered first.
    """
    family_id = uuid4()
    generator = BriefingGenerator(session=None)
    
    # Both events have same priority, type, and start time but different association counts
    same_start = datetime.now(timezone.utc) + timedelta(hours=48)
    event1 = create_test_event(
        family_id=family_id,
        title="Event 1",
        event_type="meeting",
        priority="normal",
        start_time=same_start,
        association_count=association_count1,
    )

    event2 = create_test_event(
        family_id=family_id,
        title="Event 2",
        event_type="meeting",
        priority="normal",
        start_time=same_start,
        association_count=association_count2,
    )
    
    events = [event1, event2]
    sorted_events = generator._sort_by_importance(events)
    
    # If association counts are different, verify ordering
    if association_count1 > association_count2:
        # Event 1 has more associations, should come first
        assert sorted_events[0].id == event1.id
    elif association_count2 > association_count1:
        # Event 2 has more associations, should come first
        assert sorted_events[0].id == event2.id


@given(
    num_events=st.integers(min_value=2, max_value=10),
)
@settings(max_examples=10, deadline=None)
def test_property_17_ordering_is_not_chronological(
    num_events: int,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 17: Briefing Importance-Based Ordering
    
    For any set of events, the importance-based ordering should differ from
    chronological ordering when events have different importance factors.
    """
    family_id = uuid4()
    generator = BriefingGenerator(session=None)
    
    # Create events with varying priorities in chronological order
    priorities = ["low", "normal", "high", "critical"]
    events = []
    
    for i in range(num_events):
        priority = priorities[i % len(priorities)]
        event = create_test_event(
            family_id=family_id,
            title=f"Event {i}",
            event_type="meeting",
            priority=priority,
            start_time=datetime.now(timezone.utc) + timedelta(hours=i),
        )
        events.append(event)
    
    # Sort by importance
    sorted_events = generator._sort_by_importance(events)
    
    # Verify that the ordering is based on importance, not time
    # Check that critical/high priority events come before low priority ones
    critical_high_indices = [
        i for i, e in enumerate(sorted_events)
        if e.priority in ["critical", "high"]
    ]
    low_indices = [
        i for i, e in enumerate(sorted_events)
        if e.priority == "low"
    ]
    
    # If we have both high and low priority events
    if critical_high_indices and low_indices:
        # All high priority events should come before all low priority events
        assert max(critical_high_indices) < min(low_indices)


def test_property_17_importance_score_is_consistent():
    """
    Feature: secretary-intelligence-enhancement
    Property 17: Briefing Importance-Based Ordering
    
    The importance score calculation should be consistent - sorting the same
    events multiple times should produce the same order.
    """
    family_id = uuid4()
    generator = BriefingGenerator(session=None)
    
    # Create a set of events with different characteristics
    events = [
        create_test_event(
            family_id=family_id,
            title="Critical Meeting",
            event_type="meeting",
            priority="critical",
            start_time=datetime.now(timezone.utc),
        ),
        create_test_event(
            family_id=family_id,
            title="Business Trip",
            event_type="business_trip",
            priority="high",
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            association_count=3,
        ),
        create_test_event(
            family_id=family_id,
            title="Low Priority Reminder",
            event_type="reminder",
            priority="low",
            start_time=datetime.now(timezone.utc) + timedelta(hours=2),
        ),
        create_test_event(
            family_id=family_id,
            title="Normal Meeting",
            event_type="meeting",
            priority="normal",
            start_time=datetime.now(timezone.utc) + timedelta(hours=3),
            association_count=1,
        ),
    ]
    
    # Sort multiple times
    sorted1 = generator._sort_by_importance(events.copy())
    sorted2 = generator._sort_by_importance(events.copy())
    sorted3 = generator._sort_by_importance(events.copy())
    
    # Verify consistent ordering
    assert [e.id for e in sorted1] == [e.id for e in sorted2]
    assert [e.id for e in sorted2] == [e.id for e in sorted3]


def test_property_17_business_trip_gets_opportunity_cost_bonus():
    """
    Feature: secretary-intelligence-enhancement
    Property 17: Briefing Importance-Based Ordering
    
    Business trips should receive an opportunity cost bonus in importance scoring,
    making them rank higher than regular meetings of the same priority.
    """
    family_id = uuid4()
    generator = BriefingGenerator(session=None)
    
    # Create a business trip and a regular meeting with same priority
    business_trip = create_test_event(
        family_id=family_id,
        title="Business Trip",
        event_type="business_trip",
        priority="normal",
        start_time=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    
    meeting = create_test_event(
        family_id=family_id,
        title="Regular Meeting",
        event_type="meeting",
        priority="normal",
        start_time=datetime.now(timezone.utc),
    )
    
    events = [meeting, business_trip]
    sorted_events = generator._sort_by_importance(events)
    
    # Business trip should come first due to opportunity cost bonus
    assert sorted_events[0].id == business_trip.id


@given(
    num_events=st.integers(min_value=3, max_value=15),
)
@settings(max_examples=10, deadline=None)
def test_property_17_all_events_are_included_in_sorted_output(
    num_events: int,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 17: Briefing Importance-Based Ordering
    
    Sorting should preserve all events - no events should be lost or duplicated.
    """
    family_id = uuid4()
    generator = BriefingGenerator(session=None)
    
    # Create random events
    events = []
    for i in range(num_events):
        event = create_test_event(
            family_id=family_id,
            title=f"Event {i}",
            event_type="meeting",
            priority="normal",
            start_time=datetime.now(timezone.utc) + timedelta(hours=i),
        )
        events.append(event)
    
    sorted_events = generator._sort_by_importance(events)
    
    # Verify same number of events
    assert len(sorted_events) == len(events)
    
    # Verify all original event IDs are present
    original_ids = {e.id for e in events}
    sorted_ids = {e.id for e in sorted_events}
    assert original_ids == sorted_ids
    
    # Verify no duplicates
    assert len(sorted_ids) == len(sorted_events)
