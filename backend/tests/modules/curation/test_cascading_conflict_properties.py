"""
Property-Based Tests for Cascading Conflict Detection

Tests Property 15: Cascading Conflict Detection
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.curation.models import CuratedEvent
from src.modules.curation.services.conflict_resolver_service import ConflictResolver


@st.composite
def event_chain_strategy(draw):
    """Generate a chain of events that could create cascading conflicts"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=draw(st.integers(min_value=1, max_value=30)))
    
    events = []
    current_time = base_time
    
    # Generate 3-5 events in sequence
    num_events = draw(st.integers(min_value=3, max_value=5))
    for i in range(num_events):
        duration = timedelta(hours=draw(st.integers(min_value=1, max_value=3)))
        event = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title=f"Event {i+1}",
            normalized_start=current_time,
            normalized_end=current_time + duration,
            event_type=draw(st.sampled_from(["meeting", "appointment"])),
            status=draw(st.sampled_from(["confirmed", "tentative"])),
            priority=draw(st.sampled_from(["low", "normal", "high"])),
            is_active=True,
            original_event_ids=[],
            source_types=[],
        )
        events.append(event)
        # Next event starts after this one with a small gap
        current_time = current_time + duration + timedelta(minutes=draw(st.integers(min_value=15, max_value=60)))
    
    return events, family_id


@pytest.mark.asyncio
@given(event_data=event_chain_strategy())
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_property_15_cascading_conflict_detection(
    event_data,
    async_session: AsyncSession,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 15: Cascading Conflict Detection
    
    For any proposed time adjustment, the Conflict Resolver should check
    whether the new time would create new conflicts before recommending it.
    """
    events, family_id = event_data
    
    # Add all events to database
    for event in events:
        async_session.add(event)
    await async_session.commit()
    
    resolver = ConflictResolver(async_session)
    
    # Take first event and try to move it to conflict with second event
    event_to_move = events[0]
    target_event = events[1]
    
    # Propose a time that would conflict with target_event
    conflicting_time = target_event.normalized_start + timedelta(minutes=30)
    
    # Check if this creates new conflicts
    has_no_conflicts = await resolver._check_no_new_conflicts(
        event_to_move,
        conflicting_time,
        family_id,
    )
    
    # Property: Should detect that this time creates a conflict
    assert has_no_conflicts == False, \
        "Should detect that moving to overlapping time creates a conflict"
    
    # Now try a time that doesn't conflict with any event
    safe_time = events[-1].normalized_end + timedelta(hours=2)
    
    has_no_conflicts_safe = await resolver._check_no_new_conflicts(
        event_to_move,
        safe_time,
        family_id,
    )
    
    # Property: Should confirm that this time is safe
    assert has_no_conflicts_safe == True, \
        "Should confirm that moving to non-overlapping time is safe"


@pytest.mark.asyncio
async def test_cascading_conflict_prevents_bad_adjustments(async_session: AsyncSession):
    """Unit test: Cascading conflict detection prevents creating new conflicts"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Event 1: 9:00-10:00
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Morning meeting",
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=1),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Event 2: 10:30-11:30 (conflicts with event1 if event1 moves to 10:00)
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Late morning meeting",
        normalized_start=base_time + timedelta(hours=1, minutes=30),
        normalized_end=base_time + timedelta(hours=2, minutes=30),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Event 3: 9:30-10:30 (conflicts with event1)
    event3 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Conflicting meeting",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=1, minutes=30),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Add events to database
    async_session.add(event1)
    async_session.add(event2)
    async_session.add(event3)
    await async_session.commit()
    
    resolver = ConflictResolver(async_session)
    
    # Try to resolve conflict between event1 and event3
    # by moving event1 to 10:00
    proposed_time = base_time + timedelta(hours=1)
    
    # This would create a new conflict with event2
    has_no_conflicts = await resolver._check_no_new_conflicts(
        event1,
        proposed_time,
        family_id,
    )
    
    assert has_no_conflicts == False, \
        "Should detect that moving event1 to 10:00 would conflict with event2"
    
    # Generate resolution options - should not include the bad adjustment
    options = await resolver.resolve_conflict(event1, event3, family_id)
    
    # None of the options should propose moving event1 to 10:00
    for opt in options:
        if opt.target_event_id == event1.id and opt.type == "adjust_time":
            assert opt.new_start_time != proposed_time, \
                "Should not propose adjustment that creates new conflict"


@pytest.mark.asyncio
async def test_safe_time_slot_detection(async_session: AsyncSession):
    """Unit test: Should correctly identify safe time slots"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Event 1: 9:00-10:00
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Morning meeting",
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=1),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Event 2: 14:00-15:00 (no conflict)
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Afternoon meeting",
        normalized_start=base_time + timedelta(hours=5),
        normalized_end=base_time + timedelta(hours=6),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    async_session.add(event1)
    async_session.add(event2)
    await async_session.commit()
    
    resolver = ConflictResolver(async_session)
    
    # Test various time slots
    test_cases = [
        (base_time + timedelta(hours=2), True, "11:00 should be safe"),
        (base_time + timedelta(hours=3), True, "12:00 should be safe"),
        (base_time + timedelta(hours=4), True, "13:00 should be safe"),
        (base_time + timedelta(hours=5, minutes=30), False, "14:30 conflicts with event2"),
        (base_time + timedelta(hours=7), True, "16:00 should be safe"),
    ]
    
    for test_time, expected_safe, description in test_cases:
        is_safe = await resolver._check_no_new_conflicts(
            event1,
            test_time,
            family_id,
        )
        assert is_safe == expected_safe, description


@pytest.mark.asyncio
async def test_excludes_self_from_conflict_check(async_session: AsyncSession):
    """Unit test: Should exclude the event being moved from conflict check"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Event 1: 9:00-10:00
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Meeting",
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=1),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    async_session.add(event1)
    await async_session.commit()
    
    resolver = ConflictResolver(async_session)
    
    # Try to move event1 to a time that overlaps with its current time
    # This should be safe because we exclude the event itself
    new_time = base_time + timedelta(minutes=30)
    
    is_safe = await resolver._check_no_new_conflicts(
        event1,
        new_time,
        family_id,
    )
    
    # Should be safe because event1 is excluded from the check
    assert is_safe == True, \
        "Should exclude the event being moved from conflict detection"
