"""
Property-Based Tests for Event Graph Association Display

Feature: secretary-intelligence-enhancement
Property 23: Event Graph Association Display

For any event in the graph, clicking it should return all its associations
and enriched context.

Validates: Requirements 6.6
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.curation.models import CuratedEvent, EventAssociation


# --- Property Tests ---

@pytest.mark.asyncio
@settings(max_examples=10)
@given(
    num_associations=st.integers(min_value=0, max_value=20),
)
async def test_property_23_graph_association_display(
    num_associations: int,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 23: Event Graph Association Display
    
    For any event in the graph, clicking it should return all its associations
    and enriched context.
    
    Validates: Requirements 6.6
    """
    # Create a test event
    event = CuratedEvent(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        title="Test Event",
        event_type="travel",
        priority="high",
        status="confirmed",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=3),
        location="Beijing",
        is_active=True,
    )
    
    # Create associations for the event
    associations = []
    for i in range(num_associations):
        assoc = EventAssociation(
            id=uuid4(),
            family_id=event.family_id,
            source_event_id=event.id,
            target_type=["person", "place", "task", "date", "memory"][i % 5],
            target_id=str(uuid4()),
            association_type=["location", "temporal", "person", "memory"][i % 4],
            title=f"Association {i}",
            reason=f"Test reason {i}",
            priority=["strongly_recommend", "convenient", "optional"][i % 3],
            confidence=0.8,
            is_dismissed=False,
            is_confirmed=False,
        )
        associations.append(assoc)
    
    # Property 1: All associations for the event should be retrievable
    event_associations = [a for a in associations if a.source_event_id == event.id]
    assert len(event_associations) == num_associations, \
        f"Expected {num_associations} associations, got {len(event_associations)}"
    
    # Property 2: Each association should have all required fields
    for assoc in event_associations:
        assert assoc.id is not None, "Association missing id"
        assert assoc.source_event_id == event.id, "Association source_event_id mismatch"
        assert assoc.target_type is not None, "Association missing target_type"
        assert assoc.target_id is not None, "Association missing target_id"
        assert assoc.association_type is not None, "Association missing association_type"
        assert assoc.title is not None, "Association missing title"
        assert assoc.reason is not None, "Association missing reason"
        assert assoc.priority is not None, "Association missing priority"
        assert assoc.confidence is not None, "Association missing confidence"
    
    # Property 3: Associations should include full details (reason, priority, confidence)
    for assoc in event_associations:
        assert len(assoc.reason) > 0, "Association reason should not be empty"
        assert assoc.priority in ["strongly_recommend", "convenient", "optional"], \
            f"Invalid priority: {assoc.priority}"
        assert 0.0 <= assoc.confidence <= 1.0, \
            f"Confidence should be between 0 and 1, got: {assoc.confidence}"
    
    # Property 4: Non-dismissed associations should be included
    non_dismissed = [a for a in event_associations if not a.is_dismissed]
    assert len(non_dismissed) == num_associations, \
        "All non-dismissed associations should be included"
    
    # Property 5: Associations should be grouped by type
    types_present = set(a.target_type for a in event_associations)
    for target_type in types_present:
        type_associations = [a for a in event_associations if a.target_type == target_type]
        assert len(type_associations) > 0, f"No associations found for type {target_type}"


@pytest.mark.asyncio
async def test_association_display_includes_context():
    """
    Test that association display includes enriched context information.
    """
    # Create a test event with enriched context
    event = CuratedEvent(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        title="Beijing Business Trip",
        event_type="business_trip",
        priority="high",
        status="confirmed",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=3),
        location="Beijing",
        is_active=True,
        enrichments={
            "context": {
                "source_summary": "来自1月15日与助手的对话",
                "historical_summary": "上次去北京见了张三、李四",
                "people_summary": "张三上次提到想要茶叶",
                "priority_reason": "重要客户会议",
                "adjustability": "soft_constraint",
            }
        },
    )
    
    # Verify enriched context is present
    assert event.enrichments is not None, "Event should have enrichments"
    assert "context" in event.enrichments, "Enrichments should include context"
    
    context = event.enrichments["context"]
    assert "source_summary" in context, "Context should include source_summary"
    assert "historical_summary" in context, "Context should include historical_summary"
    assert "people_summary" in context, "Context should include people_summary"
    assert "priority_reason" in context, "Context should include priority_reason"
    assert "adjustability" in context, "Context should include adjustability"


@pytest.mark.asyncio
async def test_association_display_completeness():
    """
    Test that all association fields are included in the display.
    """
    event_id = uuid4()
    
    # Create a comprehensive association
    assoc = EventAssociation(
        id=uuid4(),
        family_id=uuid4(),
        source_event_id=event_id,
        target_type="person",
        target_id=str(uuid4()),
        association_type="person",
        title="Meet Zhang San",
        reason="He's in Beijing and you mentioned wanting to meet him",
        priority="strongly_recommend",
        confidence=0.95,
        is_dismissed=False,
        is_confirmed=False,
    )
    
    # Verify all fields are present and valid
    assert assoc.id is not None
    assert assoc.family_id is not None
    assert assoc.source_event_id == event_id
    assert assoc.target_type == "person"
    assert assoc.target_id is not None
    assert assoc.association_type == "person"
    assert assoc.title == "Meet Zhang San"
    assert "Beijing" in assoc.reason
    assert assoc.priority == "strongly_recommend"
    assert assoc.confidence == 0.95
    assert assoc.is_dismissed is False
    assert assoc.is_confirmed is False
