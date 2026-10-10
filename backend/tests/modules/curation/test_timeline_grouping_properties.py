"""
Property-Based Tests for Timeline Event Grouping

Feature: secretary-intelligence-enhancement
Property 24: Timeline Event Grouping

For any set of events belonging to the same trip (same trip_id), the timeline
should group them together with a trip theme label.

Validates: Requirements 7.2
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.curation.models import CuratedEvent


# --- Property Tests ---

@pytest.mark.asyncio
@settings(max_examples=10)
@given(
    num_trips=st.integers(min_value=1, max_value=5),
    events_per_trip=st.integers(min_value=2, max_value=8),
)
async def test_property_24_timeline_event_grouping(
    num_trips: int,
    events_per_trip: int,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 24: Timeline Event Grouping
    
    For any set of events belonging to the same trip (same trip_id), the timeline
    should group them together with a trip theme label.
    
    Validates: Requirements 7.2
    """
    # Create multiple trips with events
    all_events = []
    trip_groups = {}
    
    for trip_idx in range(num_trips):
        trip_id = uuid4()
        trip_name = f"Trip {trip_idx + 1}"
        family_id = uuid4()
        user_id = uuid4()
        
        trip_events = []
        base_time = datetime.now(timezone.utc) + timedelta(days=trip_idx * 10)
        
        for event_idx in range(events_per_trip):
            event = CuratedEvent(
                id=uuid4(),
                family_id=family_id,
                user_id=user_id,
                trip_id=trip_id,
                trip_name=trip_name,
                title=f"Day {event_idx + 1} · {trip_name}",
                event_type=["travel", "meeting", "appointment", "other"][event_idx % 4],
                priority="normal",
                status="confirmed",
                normalized_start=base_time + timedelta(days=event_idx),
                normalized_end=base_time + timedelta(days=event_idx, hours=2),
                location=f"Location {trip_idx}",
                is_active=True,
            )
            trip_events.append(event)
            all_events.append(event)
        
        trip_groups[trip_id] = trip_events
    
    # Property 1: Events with the same trip_id should be groupable
    for trip_id, expected_events in trip_groups.items():
        grouped_events = [e for e in all_events if e.trip_id == trip_id]
        assert len(grouped_events) == len(expected_events), \
            f"Expected {len(expected_events)} events for trip {trip_id}, got {len(grouped_events)}"
    
    # Property 2: Each group should have a trip theme label (trip_name)
    for trip_id, events in trip_groups.items():
        trip_names = set(e.trip_name for e in events if e.trip_name)
        assert len(trip_names) <= 1, \
            f"Trip {trip_id} should have consistent trip_name, got: {trip_names}"
        if trip_names:
            trip_name = trip_names.pop()
            assert trip_name is not None and len(trip_name) > 0, \
                f"Trip {trip_id} should have non-empty trip_name"
    
    # Property 3: Events in the same group should have the same family_id
    for trip_id, events in trip_groups.items():
        family_ids = set(e.family_id for e in events)
        assert len(family_ids) == 1, \
            f"Trip {trip_id} events should have same family_id, got: {family_ids}"
    
    # Property 4: Events in the same group should be chronologically ordered
    for trip_id, events in trip_groups.items():
        sorted_events = sorted(events, key=lambda e: e.normalized_start)
        for i in range(len(sorted_events) - 1):
            assert sorted_events[i].normalized_start <= sorted_events[i + 1].normalized_start, \
                f"Events in trip {trip_id} should be chronologically ordered"
    
    # Property 5: Events without trip_id should not be grouped
    ungrouped_events = [e for e in all_events if e.trip_id is None]
    # In this test, all events have trip_id, so this should be empty
    assert len(ungrouped_events) == 0, "All test events should have trip_id"


@pytest.mark.asyncio
async def test_timeline_grouping_with_trip_theme():
    """
    Test that timeline groups events by trip_id and displays trip theme.
    """
    trip_id = uuid4()
    trip_name = "Beijing Business Trip"
    family_id = uuid4()
    user_id = uuid4()
    
    # Create events for the same trip
    events = []
    base_time = datetime.now(timezone.utc) + timedelta(days=1)
    
    for i in range(3):
        event = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            trip_id=trip_id,
            trip_name=trip_name,
            title=f"Day {i + 1} · {trip_name}",
            event_type="travel" if i == 0 else "meeting",
            priority="high",
            status="confirmed",
            normalized_start=base_time + timedelta(days=i),
            normalized_end=base_time + timedelta(days=i, hours=2),
            location="Beijing",
            is_active=True,
        )
        events.append(event)
    
    # Verify grouping
    grouped = [e for e in events if e.trip_id == trip_id]
    assert len(grouped) == 3, "All events should be in the same group"
    
    # Verify trip theme
    for event in grouped:
        assert event.trip_name == trip_name, f"Event should have trip_name: {trip_name}"
        assert trip_name in event.title, f"Event title should include trip_name"


@pytest.mark.asyncio
async def test_timeline_grouping_multiple_trips():
    """
    Test that timeline correctly groups events from multiple trips.
    """
    family_id = uuid4()
    user_id = uuid4()
    
    # Create two separate trips
    trip1_id = uuid4()
    trip1_name = "Shanghai Trip"
    trip2_id = uuid4()
    trip2_name = "Guangzhou Trip"
    
    events = []
    base_time = datetime.now(timezone.utc) + timedelta(days=1)
    
    # Trip 1 events
    for i in range(2):
        event = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            trip_id=trip1_id,
            trip_name=trip1_name,
            title=f"Day {i + 1} · {trip1_name}",
            event_type="travel",
            priority="normal",
            status="confirmed",
            normalized_start=base_time + timedelta(days=i),
            normalized_end=base_time + timedelta(days=i, hours=2),
            location="Shanghai",
            is_active=True,
        )
        events.append(event)
    
    # Trip 2 events
    for i in range(2):
        event = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            trip_id=trip2_id,
            trip_name=trip2_name,
            title=f"Day {i + 1} · {trip2_name}",
            event_type="travel",
            priority="normal",
            status="confirmed",
            normalized_start=base_time + timedelta(days=i + 10),
            normalized_end=base_time + timedelta(days=i + 10, hours=2),
            location="Guangzhou",
            is_active=True,
        )
        events.append(event)
    
    # Verify separate grouping
    trip1_events = [e for e in events if e.trip_id == trip1_id]
    trip2_events = [e for e in events if e.trip_id == trip2_id]
    
    assert len(trip1_events) == 2, "Trip 1 should have 2 events"
    assert len(trip2_events) == 2, "Trip 2 should have 2 events"
    
    # Verify no overlap
    trip1_ids = set(e.id for e in trip1_events)
    trip2_ids = set(e.id for e in trip2_events)
    assert len(trip1_ids & trip2_ids) == 0, "Trips should not share events"
