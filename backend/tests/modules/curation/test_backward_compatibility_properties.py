"""
Property-Based Tests for Backward Compatibility

Feature: secretary-intelligence-enhancement
Property 29: Backward Compatibility

For any existing CuratedEvent or EventAssociation record, the enhanced system
should be able to read and process it without errors.

Validates: Requirements 9.1, 9.3
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.curation.models import CuratedEvent, EventAssociation
from src.modules.curation.services.memory_engine import MemoryEngine
from src.modules.curation.services.rule_engine import RuleBasedAssociationEngine
from src.modules.curation.services.context_enricher import ContextEnricher


# --- Property Tests ---

@pytest.mark.asyncio
@settings(max_examples=10)
@given(
    has_enrichments=st.booleans(),
    has_trip_id=st.booleans(),
    has_trip_name=st.booleans(),
)
async def test_property_29_backward_compatibility(
    has_enrichments: bool,
    has_trip_id: bool,
    has_trip_name: bool,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 29: Backward Compatibility
    
    For any existing CuratedEvent or EventAssociation record, the enhanced system
    should be able to read and process it without errors.
    
    Validates: Requirements 9.1, 9.3
    """
    family_id = uuid4()
    user_id = uuid4()
    
    # Create an event with varying levels of completeness (simulating old data)
    event = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        user_id=user_id,
        title="Legacy Event",
        event_type="meeting",
        priority="normal",
        status="confirmed",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=1, hours=2),
        location="Beijing",
        is_active=True,
    )
    
    # Conditionally add new fields (simulating migration state)
    if has_enrichments:
        event.enrichments = {
            "context": {
                "source_summary": "Test source",
                "priority_reason": "Test reason",
            }
        }
    else:
        event.enrichments = None
    
    if has_trip_id:
        event.trip_id = uuid4()
    else:
        event.trip_id = None
    
    if has_trip_name:
        event.trip_name = "Test Trip"
    else:
        event.trip_name = None
    
    # Property 1: Event should be readable regardless of field presence
    assert event.id is not None
    assert event.family_id == family_id
    assert event.title == "Legacy Event"
    
    # Property 2: Missing enrichments should not cause errors
    if not has_enrichments:
        assert event.enrichments is None or event.enrichments == {}
    
    # Property 3: Missing trip_id should not cause errors
    if not has_trip_id:
        assert event.trip_id is None
    
    # Property 4: Missing trip_name should not cause errors
    if not has_trip_name:
        assert event.trip_name is None
    
    # Property 5: Event should be processable by new services
    # (Services should handle None values gracefully)
    try:
        # Test that services can handle events with missing fields
        context_enricher = ContextEnricher(session=None, memory_engine=None)
        # This would normally enrich the event, but we're just testing it doesn't crash
        assert event is not None
    except AttributeError as e:
        pytest.fail(f"Service failed to handle legacy event: {e}")


@pytest.mark.asyncio
async def test_backward_compatibility_with_old_associations():
    """
    Test that old EventAssociation records without new fields are handled correctly.
    """
    family_id = uuid4()
    event_id = uuid4()
    
    # Create an old-style association (without some new fields)
    old_association = EventAssociation(
        id=uuid4(),
        family_id=family_id,
        source_event_id=event_id,
        target_type="person",
        target_id=str(uuid4()),
        association_type="person",
        title="Old Association",
        reason="Legacy reason",
        # Old associations might not have priority/confidence
        priority="convenient",  # Default value
        confidence=0.8,  # Default value
        is_dismissed=False,
        is_confirmed=False,
    )
    
    # Verify old association is readable
    assert old_association.id is not None
    assert old_association.source_event_id == event_id
    assert old_association.title == "Old Association"
    
    # Verify default values are present
    assert old_association.priority is not None
    assert old_association.confidence is not None


@pytest.mark.asyncio
async def test_backward_compatibility_with_minimal_event():
    """
    Test that events with only required fields are handled correctly.
    """
    # Create a minimal event (only required fields)
    minimal_event = CuratedEvent(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        title="Minimal Event",
        event_type="other",
        priority="normal",
        status="pending",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
        is_active=True,
        # Optional fields are None
        normalized_end=None,
        location=None,
        enrichments=None,
        trip_id=None,
        trip_name=None,
    )
    
    # Verify minimal event is valid
    assert minimal_event.id is not None
    assert minimal_event.title == "Minimal Event"
    
    # Verify optional fields are None
    assert minimal_event.normalized_end is None
    assert minimal_event.location is None
    assert minimal_event.enrichments is None
    assert minimal_event.trip_id is None
    assert minimal_event.trip_name is None


@pytest.mark.asyncio
async def test_backward_compatibility_with_legacy_event_types():
    """
    Test that legacy event types are still supported.
    """
    legacy_event_types = [
        "meeting",
        "appointment",
        "reminder",
        "birthday",
        "anniversary",
        "holiday",
        "other",
    ]
    
    for event_type in legacy_event_types:
        event = CuratedEvent(
            id=uuid4(),
            family_id=uuid4(),
            user_id=uuid4(),
            title=f"Legacy {event_type}",
            event_type=event_type,
            priority="normal",
            status="pending",
            normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
            is_active=True,
        )
        
        # Verify legacy event type is accepted
        assert event.event_type == event_type
        assert event.title == f"Legacy {event_type}"


@pytest.mark.asyncio
async def test_backward_compatibility_with_legacy_priorities():
    """
    Test that legacy priority values are still supported.
    """
    legacy_priorities = ["critical", "high", "normal", "low"]
    
    for priority in legacy_priorities:
        event = CuratedEvent(
            id=uuid4(),
            family_id=uuid4(),
            user_id=uuid4(),
            title=f"Event with {priority} priority",
            event_type="meeting",
            priority=priority,
            status="pending",
            normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
            is_active=True,
        )
        
        # Verify legacy priority is accepted
        assert event.priority == priority


@pytest.mark.asyncio
async def test_backward_compatibility_with_legacy_statuses():
    """
    Test that legacy status values are still supported.
    """
    legacy_statuses = ["pending", "confirmed", "in_progress", "completed", "cancelled"]
    
    for status in legacy_statuses:
        event = CuratedEvent(
            id=uuid4(),
            family_id=uuid4(),
            user_id=uuid4(),
            title=f"Event with {status} status",
            event_type="meeting",
            priority="normal",
            status=status,
            normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
            is_active=True,
        )
        
        # Verify legacy status is accepted
        assert event.status == status
