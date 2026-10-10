"""
Property-Based Tests for Unresolvable Conflict Explanation

Tests Property 16: Unresolvable Conflict Explanation
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.curation.models import CuratedEvent
from src.modules.curation.services.conflict_resolver_service import ConflictResolver


@st.composite
def hard_constraint_pair_strategy(draw):
    """Generate a pair of hard constraint events that conflict"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=draw(st.integers(min_value=1, max_value=30)))
    
    # Both events are hard constraints
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title=draw(st.text(min_size=5, max_size=50)),
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=draw(st.integers(min_value=1, max_value=3))),
        event_type=draw(st.sampled_from(["travel", "meeting", "birthday"])),
        status="confirmed",
        priority=draw(st.sampled_from(["high", "critical"])),
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Overlapping hard constraint
    overlap_start = base_time + timedelta(minutes=draw(st.integers(min_value=30, max_value=90)))
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title=draw(st.text(min_size=5, max_size=50)),
        normalized_start=overlap_start,
        normalized_end=overlap_start + timedelta(hours=draw(st.integers(min_value=1, max_value=3))),
        event_type=draw(st.sampled_from(["travel", "meeting", "anniversary"])),
        status="confirmed",
        priority=draw(st.sampled_from(["high", "critical"])),
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    return event1, event2, family_id


@pytest.mark.asyncio
@given(event_data=hard_constraint_pair_strategy())
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_property_16_unresolvable_conflict_explanation(
    event_data,
    async_session: AsyncSession,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 16: Unresolvable Conflict Explanation
    
    For any conflict that cannot be auto-resolved, the Conflict Resolver
    should provide a clear explanation of why and what user decision is needed.
    """
    event1, event2, family_id = event_data
    
    resolver = ConflictResolver(async_session)
    
    # Check if both are hard constraints
    adj1 = resolver._analyze_adjustability(event1)
    adj2 = resolver._analyze_adjustability(event2)
    
    if adj1 == "hard_constraint" and adj2 == "hard_constraint":
        # Generate explanation for unresolvable conflict
        explanation = resolver.generate_unresolvable_explanation(event1, event2)
        
        # Property: Explanation must not be empty
        assert explanation, "Explanation must not be empty for unresolvable conflicts"
        assert len(explanation) > 20, "Explanation should be meaningful (>20 chars)"
        
        # Property: Explanation should mention both events
        # (at least one of them should be mentioned)
        assert event1.title in explanation or event2.title in explanation, \
            "Explanation should mention at least one of the conflicting events"
        
        # Property: Explanation should indicate why it's unresolvable
        unresolvable_keywords = ["硬约束", "无法", "不能", "需要", "决定", "手动"]
        assert any(keyword in explanation for keyword in unresolvable_keywords), \
            "Explanation should indicate why conflict is unresolvable"
        
        # Property: Explanation should suggest what user needs to do
        action_keywords = ["保留", "调整", "取消", "决定", "确认", "手动"]
        assert any(keyword in explanation for keyword in action_keywords), \
            "Explanation should suggest what action user needs to take"


@pytest.mark.asyncio
async def test_both_hard_constraints_explanation(async_session: AsyncSession):
    """Unit test: Both hard constraints should explain why neither can be adjusted"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Hard constraint 1: Confirmed flight
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
    
    # Hard constraint 2: Important meeting
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Board meeting",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=3),
        event_type="meeting",
        status="confirmed",
        priority="critical",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    resolver = ConflictResolver(async_session)
    explanation = resolver.generate_unresolvable_explanation(event1, event2)
    
    # Should mention both events are hard constraints
    assert "硬约束" in explanation or "无法" in explanation
    assert event1.title in explanation or event2.title in explanation
    # Should ask user to decide
    assert "需要" in explanation or "决定" in explanation


@pytest.mark.asyncio
async def test_one_hard_constraint_explanation(async_session: AsyncSession):
    """Unit test: One hard constraint should suggest adjusting the other"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Hard constraint: Confirmed flight
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Flight to Shanghai",
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
        title="Team lunch",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=2),
        event_type="reminder",
        status="tentative",
        priority="normal",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    resolver = ConflictResolver(async_session)
    
    # This should actually be resolvable, so let's test the explanation method directly
    # when we force it to be unresolvable
    explanation = resolver.generate_unresolvable_explanation(event1, event2)
    
    # Should mention which event is the hard constraint
    assert event1.title in explanation
    # Should suggest adjusting the flexible event
    assert event2.title in explanation or "调整" in explanation or "建议" in explanation


@pytest.mark.asyncio
async def test_birthday_hard_constraint_explanation(async_session: AsyncSession):
    """Unit test: Birthday should be explained as unchangeable date"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Birthday (hard constraint)
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="张三生日",
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=1),
        event_type="birthday",
        status="confirmed",
        priority="high",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    # Another important event
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="重要会议",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=2),
        event_type="meeting",
        status="confirmed",
        priority="critical",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    resolver = ConflictResolver(async_session)
    explanation = resolver.generate_unresolvable_explanation(event1, event2)
    
    # Should mention that birthday is unchangeable
    assert "重要日期" in explanation or "不可更改" in explanation or "硬约束" in explanation


@pytest.mark.asyncio
async def test_explanation_provides_actionable_guidance(async_session: AsyncSession):
    """Unit test: Explanation should provide clear next steps"""
    family_id = uuid4()
    base_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Two confirmed meetings (both hard constraints)
    event1 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Client presentation",
        normalized_start=base_time,
        normalized_end=base_time + timedelta(hours=2),
        event_type="meeting",
        status="confirmed",
        priority="critical",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    event2 = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Investor meeting",
        normalized_start=base_time + timedelta(minutes=30),
        normalized_end=base_time + timedelta(hours=2),
        event_type="meeting",
        status="confirmed",
        priority="critical",
        is_active=True,
        original_event_ids=[],
        source_types=[],
    )
    
    resolver = ConflictResolver(async_session)
    explanation = resolver.generate_unresolvable_explanation(event1, event2)
    
    # Should provide actionable guidance
    actionable_phrases = [
        "需要您决定",
        "保留哪个",
        "手动调整",
        "建议",
        "调整或取消",
    ]
    
    assert any(phrase in explanation for phrase in actionable_phrases), \
        "Explanation should provide actionable guidance on what user should do"
