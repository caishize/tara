"""
Property-based tests for Context Enrichment

Feature: secretary-intelligence-enhancement
Property 11: Event Context Enrichment

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""

import pytest
from datetime import datetime, timedelta, date
from uuid import uuid4
from hypothesis import given, strategies as st, settings
from unittest.mock import AsyncMock, MagicMock, patch

from src.modules.curation.services.context_enricher import ContextEnricher, EventContext
from src.modules.curation.services.memory_engine import MemoryEngine
from src.modules.curation.models import CuratedEvent
from src.modules.member.models import Member


# Strategy for generating valid event types
event_types = st.sampled_from([
    "meeting", "travel", "appointment", "task", "reminder",
    "birthday", "anniversary", "flight", "business_trip"
])

# Strategy for generating valid priorities
priorities = st.sampled_from(["low", "normal", "high", "critical"])

# Strategy for generating valid statuses
statuses = st.sampled_from(["tentative", "confirmed", "cancelled"])

# Strategy for generating locations
locations = st.sampled_from([
    "北京", "上海", "深圳", "杭州", "广州", "成都", "西安", "南京"
])


@pytest.mark.asyncio
@given(
    event_type=event_types,
    priority=priorities,
    status=statuses,
    location=locations,
    has_trip_id=st.booleans(),
)
@settings(max_examples=10, deadline=None)
async def test_property_11_event_context_enrichment(
    event_type: str,
    priority: str,
    status: str,
    location: str,
    has_trip_id: bool,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 11: Event Context Enrichment
    
    For any CuratedEvent, the Context Enricher should attach source information,
    historical events, related people, event chain, and decision support information
    (priority reason, adjustability analysis).
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
    """
    # Setup mocks
    mock_session = AsyncMock()
    mock_memory_engine = MagicMock(spec=MemoryEngine)
    enricher = ContextEnricher(mock_session, mock_memory_engine)
    
    # Mock database queries to return empty results
    mock_session.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))
    
    family_id = uuid4()
    
    # Create test event
    event = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title=f"Test {event_type}",
        event_type=event_type,
        priority=priority,
        status=status,
        location=location,
        normalized_start=datetime.now() + timedelta(days=1),
        normalized_end=datetime.now() + timedelta(days=1, hours=2),
        trip_id=uuid4() if has_trip_id else None,
        original_event_ids=["test_source_123"],
        metadata={"source": "test"},
    )
    
    # Enrich event
    context = await enricher.enrich_event(event, family_id)
    
    # Property 11: Verify all required context fields are present
    
    # 3.1: Source information should be extracted
    assert isinstance(context.source_info, dict), \
        "source_info should be a dictionary"
    assert isinstance(context.source_summary, str), \
        "source_summary should be a string"
    assert len(context.source_summary) > 0, \
        "source_summary should not be empty"
    
    # 3.2: Historical events should be queried (may be empty)
    assert isinstance(context.historical_events, list), \
        "historical_events should be a list"
    
    # 3.3: Related people should be queried (may be empty)
    assert isinstance(context.related_people, list), \
        "related_people should be a list"
    
    # 3.4: Event chain should be discovered (may be empty)
    assert isinstance(context.related_events, list), \
        "related_events should be a list"
    
    # 3.5: Decision support information should be generated
    assert context.priority_reason is not None, \
        "priority_reason should always be present"
    assert isinstance(context.priority_reason, str), \
        "priority_reason should be a string"
    assert len(context.priority_reason) > 0, \
        "priority_reason should not be empty"
    
    assert context.adjustability in ["hard_constraint", "soft_constraint", "flexible"], \
        f"adjustability should be one of the valid values, got: {context.adjustability}"
    
    assert context.adjustability_reason is not None, \
        "adjustability_reason should always be present"
    assert isinstance(context.adjustability_reason, str), \
        "adjustability_reason should be a string"
    assert len(context.adjustability_reason) > 0, \
        "adjustability_reason should not be empty"
    
    # Verify adjustability logic is consistent with event type
    if event_type in ["travel", "flight"] and status == "confirmed":
        assert context.adjustability == "hard_constraint", \
            "Confirmed travel/flight should be hard_constraint"
    
    if event_type in ["birthday", "anniversary"]:
        assert context.adjustability == "hard_constraint", \
            "Birthday/anniversary should be hard_constraint"


@pytest.mark.asyncio
async def test_context_enrichment_basic():
    """
    Basic test that context enrichment works with minimal setup
    """
    # Setup mocks
    mock_session = AsyncMock()
    mock_memory_engine = MagicMock(spec=MemoryEngine)
    enricher = ContextEnricher(mock_session, mock_memory_engine)
    
    # Mock database queries
    mock_session.execute = AsyncMock(return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: [])))
    
    family_id = uuid4()
    
    # Create test event
    event = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        title="Test Meeting",
        event_type="meeting",
        priority="high",
        status="confirmed",
        location="北京",
        normalized_start=datetime.now() + timedelta(days=1),
        normalized_end=datetime.now() + timedelta(days=1, hours=2),
    )
    
    # Enrich event
    context = await enricher.enrich_event(event, family_id)
    
    # Verify basic fields
    assert context.source_summary is not None
    assert context.priority_reason is not None
    assert context.adjustability in ["hard_constraint", "soft_constraint", "flexible"]
    assert context.adjustability_reason is not None
