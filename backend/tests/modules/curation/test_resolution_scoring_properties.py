"""
Property-Based Tests for Resolution Option Scoring

Tests Property 14: Resolution Option Scoring
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from hypothesis import given, strategies as st, settings, HealthCheck

from src.modules.curation.models import CuratedEvent
from src.modules.curation.services.conflict_resolver_service import ConflictResolver, ResolutionOption


@st.composite
def resolution_option_strategy(draw):
    """Generate a resolution option with random parameters"""
    option_type = draw(st.sampled_from(["adjust_time", "cancel"]))
    target_event_id = uuid4()
    
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    time_offset_hours = draw(st.integers(min_value=-48, max_value=48))
    new_start_time = base_time + timedelta(hours=time_offset_hours) if option_type == "adjust_time" else None
    
    return ResolutionOption(
        type=option_type,
        target_event_id=target_event_id,
        new_start_time=new_start_time,
        reason=draw(st.text(min_size=10, max_size=100)),
        impact_analysis=draw(st.text(min_size=10, max_size=100)),
    )


@st.composite
def event_with_priority_strategy(draw):
    """Generate an event with specific priority"""
    return CuratedEvent(
        id=uuid4(),
        family_id=uuid4(),
        title=draw(st.text(min_size=5, max_size=50)),
        normalized_start=datetime.now(timezone.utc) + timedelta(days=7),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=7, hours=2),
        event_type=draw(st.sampled_from(["meeting", "appointment", "travel", "reminder"])),
        status=draw(st.sampled_from(["confirmed", "tentative", "pending"])),
        priority=draw(st.sampled_from(["low", "normal", "high", "critical"])),
        is_active=True,
    )


@pytest.mark.asyncio
@given(
    option=resolution_option_strategy(),
    event1=event_with_priority_strategy(),
    event2=event_with_priority_strategy(),
)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_property_14_resolution_option_scoring(
    option,
    event1,
    event2,
    async_session,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 14: Resolution Option Scoring
    
    For any resolution option, the score should consider event importance,
    urgency, and opportunity cost, with lower-impact options scoring higher.
    """
    resolver = ConflictResolver(async_session)
    
    # Set target event ID to one of the events
    option.target_event_id = event1.id
    
    # Calculate score
    score = await resolver._calculate_resolution_score(option, event1, event2)
    
    # Property: Score must be between 0 and 1
    assert 0.0 <= score <= 1.0, f"Score {score} must be between 0 and 1"
    
    # Property: Lower priority events should score higher (easier to adjust)
    priority_order = ["low", "normal", "high", "critical"]
    if event1.priority in priority_order:
        event1_priority_index = priority_order.index(event1.priority)
        
        # Create a comparison event with lower priority
        if event1_priority_index > 0:
            lower_priority_event = CuratedEvent(
                id=uuid4(),
                family_id=event1.family_id,
                title=event1.title,
                normalized_start=event1.normalized_start,
                normalized_end=event1.normalized_end,
                event_type=event1.event_type,
                status=event1.status,
                priority=priority_order[event1_priority_index - 1],
                is_active=True,
                original_event_ids=[],
                source_types=[],
            )
            
            lower_priority_option = ResolutionOption(
                type=option.type,
                target_event_id=lower_priority_event.id,
                new_start_time=option.new_start_time,
                reason=option.reason,
                impact_analysis=option.impact_analysis,
            )
            
            lower_priority_score = await resolver._calculate_resolution_score(
                lower_priority_option, lower_priority_event, event2
            )
            
            # Lower priority should have higher or equal score
            assert lower_priority_score >= score, \
                f"Lower priority event should score higher: {lower_priority_score} >= {score}"


@pytest.mark.asyncio
async def test_cancellation_scores_lower_than_adjustment(async_session):
    """Unit test: Cancellation options should score lower than time adjustments"""
    resolver = ConflictResolver(async_session)
    
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=uuid4(),
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
    
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=event1.family_id,
        title="Another meeting",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=2),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Adjustment option
    adjust_option = ResolutionOption(
        type="adjust_time",
        target_event_id=event1.id,
        new_start_time=base_time + timedelta(hours=3),
        reason="Adjust time",
        impact_analysis="Minimal impact",
    )
    
    # Cancellation option
    cancel_option = ResolutionOption(
        type="cancel",
        target_event_id=event1.id,
        reason="Cancel event",
        impact_analysis="Event cancelled",
    )
    
    adjust_score = await resolver._calculate_resolution_score(adjust_option, event1, event2)
    cancel_score = await resolver._calculate_resolution_score(cancel_option, event1, event2)
    
    # Adjustment should score higher than cancellation
    assert adjust_score > cancel_score, \
        f"Adjustment should score higher than cancellation: {adjust_score} > {cancel_score}"


@pytest.mark.asyncio
async def test_smaller_time_changes_score_higher(async_session):
    """Unit test: Smaller time changes should score higher"""
    resolver = ConflictResolver(async_session)
    
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=uuid4(),
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
    
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=event1.family_id,
        title="Another meeting",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=2),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Small time change (1 hour)
    small_change = ResolutionOption(
        type="adjust_time",
        target_event_id=event1.id,
        new_start_time=base_time + timedelta(hours=1),
        reason="Small adjustment",
        impact_analysis="Minimal impact",
    )
    
    # Large time change (2 days)
    large_change = ResolutionOption(
        type="adjust_time",
        target_event_id=event1.id,
        new_start_time=base_time + timedelta(days=2),
        reason="Large adjustment",
        impact_analysis="Significant impact",
    )
    
    small_score = await resolver._calculate_resolution_score(small_change, event1, event2)
    large_score = await resolver._calculate_resolution_score(large_change, event1, event2)
    
    # Smaller change should score higher
    assert small_score > large_score, \
        f"Smaller time change should score higher: {small_score} > {large_score}"


@pytest.mark.asyncio
async def test_flexible_events_score_higher(async_session):
    """Unit test: Flexible events should score higher than hard constraints"""
    resolver = ConflictResolver(async_session)
    
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Flexible event
    flexible_event = CuratedEvent(
        id=uuid4(),
        family_id=uuid4(),
        title="Team lunch",
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=1),
        event_type="reminder",
        status="tentative",
        priority="low",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Hard constraint event
    hard_event = CuratedEvent(
        id=uuid4(),
        family_id=flexible_event.family_id,
        title="Flight",
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=2),
        event_type="travel",
        status="confirmed",
        priority="critical",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    other_event = CuratedEvent(
        id=uuid4(),
        family_id=flexible_event.family_id,
        title="Meeting",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=2),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    flexible_option = ResolutionOption(
        type="adjust_time",
        target_event_id=flexible_event.id,
        new_start_time=base_time + timedelta(hours=3),
        reason="Adjust flexible event",
        impact_analysis="Minimal impact",
    )
    
    hard_option = ResolutionOption(
        type="adjust_time",
        target_event_id=hard_event.id,
        new_start_time=base_time + timedelta(hours=3),
        reason="Adjust hard constraint",
        impact_analysis="Significant impact",
    )
    
    flexible_score = await resolver._calculate_resolution_score(flexible_option, flexible_event, other_event)
    hard_score = await resolver._calculate_resolution_score(hard_option, hard_event, other_event)
    
    # Flexible event should score higher
    assert flexible_score > hard_score, \
        f"Flexible event should score higher: {flexible_score} > {hard_score}"
