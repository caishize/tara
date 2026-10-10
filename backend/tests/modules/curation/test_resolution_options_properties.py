"""
Property-Based Tests for Conflict Resolution Options

Tests Property 13: Multiple Resolution Options Generation
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.curation.models import CuratedEvent
from src.modules.curation.services.conflict_resolver_service import ConflictResolver


# Test data strategies
@st.composite
def event_pair_strategy(draw):
    """Generate a pair of conflicting events"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=draw(st.integers(min_value=1, max_value=30)))
    
    # Event 1
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title=draw(st.text(min_size=5, max_size=50)),
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=draw(st.integers(min_value=1, max_value=4))),
        event_type=draw(st.sampled_from(["meeting", "appointment", "travel", "reminder"])),
        status=draw(st.sampled_from(["confirmed", "tentative", "pending"])),
        priority=draw(st.sampled_from(["low", "normal", "high", "critical"])),
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Event 2 - overlapping with event 1
    overlap_start = base_time + timedelta(minutes=draw(st.integers(min_value=30, max_value=120)))
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title=draw(st.text(min_size=5, max_size=50)),
        normalized_start=overlap_start,
        normalized_end=overlap_start + timedelta(hours=draw(st.integers(min_value=1, max_value=4))),
        event_type=draw(st.sampled_from(["meeting", "appointment", "travel", "reminder"])),
        status=draw(st.sampled_from(["confirmed", "tentative", "pending"])),
        priority=draw(st.sampled_from(["low", "normal", "high", "critical"])),
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    return event1, event2, family_id


@pytest.mark.asyncio
@given(event_data=event_pair_strategy())
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_property_13_multiple_resolution_options(
    event_data,
    async_session: AsyncSession,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 13: Multiple Resolution Options Generation
    
    For any detected conflict, the Conflict Resolver should generate
    at least 2 resolution options (if feasible), each with adjustment
    reason and impact analysis.
    """
    event1, event2, family_id = event_data
    
    # Create resolver
    resolver = ConflictResolver(async_session)
    
    # Generate resolution options
    options = await resolver.resolve_conflict(event1, event2, family_id)
    
    # Property: Should generate at least 2 options if both events are adjustable
    adj1 = resolver._analyze_adjustability(event1)
    adj2 = resolver._analyze_adjustability(event2)
    
    if adj1 != "hard_constraint" or adj2 != "hard_constraint":
        # At least one event is adjustable, should have options
        assert len(options) >= 1, "Should generate at least 1 resolution option when events are adjustable"
        
        # If both are flexible/soft, should have multiple options
        if adj1 in ["flexible", "soft_constraint"] and adj2 in ["flexible", "soft_constraint"]:
            assert len(options) >= 2, "Should generate at least 2 options when both events are adjustable"
    
    # Property: Each option must have reason and impact analysis
    for option in options:
        assert option.reason, f"Option {option.type} must have a reason"
        assert option.impact_analysis, f"Option {option.type} must have impact analysis"
        assert option.target_event_id in [event1.id, event2.id], "Option must target one of the conflicting events"
        
        # Property: adjust_time options must have new_start_time
        if option.type == "adjust_time":
            assert option.new_start_time is not None, "adjust_time option must have new_start_time"


@pytest.mark.asyncio
async def test_resolution_options_specific_examples(async_session: AsyncSession):
    """Unit test: Specific examples of resolution option generation"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Example 1: Two flexible events - should generate multiple options
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Team lunch",
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=1),
        event_type="reminder",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Client call",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=2),
        event_type="meeting",
        status="tentative",
        priority="high",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    resolver = ConflictResolver(async_session)
    options = await resolver.resolve_conflict(event1, event2, family_id)
    
    # Should have multiple options
    assert len(options) >= 2
    
    # Should have both adjustment and cancellation options
    option_types = {opt.type for opt in options}
    assert "adjust_time" in option_types
    
    # Options should be scored
    for opt in options:
        assert 0.0 <= opt.score <= 1.0
    
    # Options should be sorted by score (descending)
    scores = [opt.score for opt in options]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_hard_constraint_no_adjustment_options(async_session: AsyncSession):
    """Unit test: Hard constraints should not generate adjustment options"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Hard constraint event (confirmed flight)
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Flight to Beijing",
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=2),
        event_type="travel",
        status="confirmed",
        priority="critical",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Flexible event
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Team meeting",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=1, minutes=30),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    resolver = ConflictResolver(async_session)
    options = await resolver.resolve_conflict(event1, event2, family_id)
    
    # Should only have options to adjust event2, not event1
    for opt in options:
        if opt.type == "adjust_time":
            assert opt.target_event_id == event2.id, "Should only adjust flexible event, not hard constraint"


@pytest.mark.asyncio
async def test_resolution_impact_analysis(async_session: AsyncSession):
    """Unit test: Impact analysis should describe time changes"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
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
    
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Afternoon meeting",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=2),
        event_type="meeting",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    resolver = ConflictResolver(async_session)
    options = await resolver.resolve_conflict(event1, event2, family_id)
    
    # Each option should have meaningful impact analysis
    for opt in options:
        assert len(opt.impact_analysis) > 0
        # Impact analysis should mention time changes or other impacts
        assert any(keyword in opt.impact_analysis for keyword in ["推迟", "提前", "天", "小时", "影响", "无明显影响"])
