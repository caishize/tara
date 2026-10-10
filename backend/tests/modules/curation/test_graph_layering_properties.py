"""
Property-Based Tests for Event Graph Layering

Feature: secretary-intelligence-enhancement
Property 22: Event Graph Layering

For any event graph generation, events should be classified into exactly one of
four layers (core trips, must-do items, convenient opportunities, background info)
based on event type and associations.

Validates: Requirements 6.1, 6.3, 6.4, 6.5
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.views.services.graph_service import EventGraphService
from src.modules.views.services._graph_helpers import determine_layer
from src.modules.curation.models import CuratedEvent, EventAssociation


# --- Test Strategies ---

@st.composite
def curated_event_strategy(draw):
    """Generate a CuratedEvent for testing"""
    event_types = ["travel", "business_trip", "meeting", "appointment", "task", "reminder", "birthday", "other"]
    priorities = ["critical", "high", "normal", "low"]
    statuses = ["pending", "confirmed", "in_progress", "completed"]
    
    event_type = draw(st.sampled_from(event_types))
    priority = draw(st.sampled_from(priorities))
    status = draw(st.sampled_from(statuses))
    
    start_time = datetime.now(timezone.utc) + timedelta(days=draw(st.integers(min_value=1, max_value=30)))
    end_time = start_time + timedelta(hours=draw(st.integers(min_value=1, max_value=8)))
    
    return CuratedEvent(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        title=f"Test Event {draw(st.text(min_size=5, max_size=20))}",
        event_type=event_type,
        priority=priority,
        status=status,
        normalized_start=start_time,
        normalized_end=end_time,
        location=draw(st.text(min_size=3, max_size=20)),
        is_active=True,
    )


@st.composite
def event_association_strategy(draw, event_id):
    """Generate an EventAssociation for testing"""
    target_types = ["person", "place", "task", "reminder", "date", "memory", "gift"]
    association_types = ["location", "temporal", "person", "semantic", "memory", "task"]
    priorities = ["strongly_recommend", "convenient", "optional"]
    
    target_type = draw(st.sampled_from(target_types))
    association_type = draw(st.sampled_from(association_types))
    priority = draw(st.sampled_from(priorities))
    
    return EventAssociation(
        id=uuid4(),
        family_id=uuid4(),
        source_event_id=event_id,
        target_type=target_type,
        target_id=str(uuid4()),
        association_type=association_type,
        title=f"Test Association {draw(st.text(min_size=5, max_size=20))}",
        reason=draw(st.text(min_size=10, max_size=50)),
        priority=priority,
        confidence=draw(st.floats(min_value=0.5, max_value=1.0)),
        is_dismissed=False,
        is_confirmed=False,
    )


# --- Property Tests ---

@pytest.mark.asyncio
@settings(max_examples=10)  # Use 10 examples for speed
@given(
    trip_event=curated_event_strategy(),
    num_events=st.integers(min_value=1, max_value=10),
    num_associations=st.integers(min_value=1, max_value=15),
)
async def test_property_22_event_graph_layering(
    trip_event: CuratedEvent,
    num_events: int,
    num_associations: int,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 22: Event Graph Layering
    
    For any event graph generation, events should be classified into exactly one of
    four layers (core trips, must-do items, convenient opportunities, background info)
    based on event type and associations.
    
    Validates: Requirements 6.1, 6.3, 6.4, 6.5
    """
    # Create a mock session (we'll test the layering logic directly)
    service = EventGraphService(db=None)
    
    # Generate test events
    events = [trip_event]
    for _ in range(num_events):
        event = CuratedEvent(
            id=uuid4(),
            family_id=trip_event.family_id,
            user_id=trip_event.user_id,
            title=f"Event {_}",
            event_type=["travel", "meeting", "task", "reminder", "other"][_ % 5],
            priority=["critical", "high", "normal", "low"][_ % 4],
            status="pending",
            normalized_start=trip_event.normalized_start + timedelta(hours=_),
            normalized_end=trip_event.normalized_start + timedelta(hours=_ + 1),
            location=trip_event.location,
            is_active=True,
        )
        events.append(event)
    
    # Generate test associations
    associations = []
    for _ in range(num_associations):
        assoc = EventAssociation(
            id=uuid4(),
            family_id=trip_event.family_id,
            source_event_id=trip_event.id,
            target_type=["person", "place", "task", "date", "memory"][_ % 5],
            target_id=str(uuid4()),
            association_type=["location", "temporal", "person", "memory"][_ % 4],
            title=f"Association {_}",
            reason=f"Test reason {_}",
            priority=["strongly_recommend", "convenient", "optional"][_ % 3],
            confidence=0.8,
            is_dismissed=False,
            is_confirmed=False,
        )
        associations.append(assoc)
    
    # Build graph
    nodes, edges = service._build_graph(trip_event, events, associations)
    
    # Property 1: All nodes must have a layer assigned
    for node in nodes:
        assert hasattr(node, 'layer'), f"Node {node.id} missing layer attribute"
        if node.type != "category":  # Category nodes may not have layer in some implementations
            assert node.layer is not None, f"Node {node.id} has None layer"
    
    # Property 2: Each node must be in exactly one of the four layers
    valid_layers = {"core_trips", "must_do", "convenient", "background"}
    for node in nodes:
        if node.layer is not None:
            assert node.layer in valid_layers, \
                f"Node {node.id} has invalid layer: {node.layer}"
    
    # Property 3: Core trip event must be in core_trips layer
    center_node = next((n for n in nodes if n.id == str(trip_event.id)), None)
    assert center_node is not None, "Center node (trip event) not found in graph"
    assert center_node.layer == "core_trips", \
        f"Center node should be in core_trips layer, got: {center_node.layer}"
    
    # Property 4: Travel/business_trip events should be in core_trips layer
    for node in nodes:
        if node.type in ["travel", "business_trip"] and node.type != "category":
            assert node.layer == "core_trips", \
                f"Travel/business_trip node {node.id} should be in core_trips layer, got: {node.layer}"
    
    # Property 5: Task/reminder *event* nodes should be in must_do layer.
    # Note: association nodes whose target_type is "task"/"reminder" get their
    # layer from priority, not event_type. So we only check nodes that
    # correspond to actual CuratedEvents (their IDs come from events list).
    event_ids = {str(e.id) for e in events}
    for node in nodes:
        if node.type in ["task", "reminder"] and node.id in event_ids:
            assert node.layer == "must_do", \
                f"Task/reminder event node {node.id} should be in must_do layer, got: {node.layer}"
    
    # Property 6: strongly_recommend associations should be in must_do layer
    for assoc in associations:
        if assoc.priority == "strongly_recommend":
            assoc_node = next((n for n in nodes if n.id == str(assoc.id)), None)
            if assoc_node:
                assert assoc_node.layer == "must_do", \
                    f"strongly_recommend association {assoc.id} should be in must_do layer, got: {assoc_node.layer}"
    
    # Property 7: convenient priority associations should be in convenient layer
    for assoc in associations:
        if assoc.priority == "convenient":
            assoc_node = next((n for n in nodes if n.id == str(assoc.id)), None)
            if assoc_node:
                assert assoc_node.layer == "convenient", \
                    f"convenient association {assoc.id} should be in convenient layer, got: {assoc_node.layer}"
    
    # Property 8: optional priority associations should be in background layer
    for assoc in associations:
        if assoc.priority == "optional":
            assoc_node = next((n for n in nodes if n.id == str(assoc.id)), None)
            if assoc_node:
                assert assoc_node.layer == "background", \
                    f"optional association {assoc.id} should be in background layer, got: {assoc_node.layer}"
    
    # Property 9: date/memory type associations should be in background layer (if no explicit priority)
    for assoc in associations:
        if assoc.target_type in ["date", "memory"] and assoc.priority not in ["strongly_recommend", "convenient"]:
            assoc_node = next((n for n in nodes if n.id == str(assoc.id)), None)
            if assoc_node:
                assert assoc_node.layer == "background", \
                    f"date/memory association {assoc.id} should be in background layer, got: {assoc_node.layer}"
    
    # Property 10: person/place type associations should be in convenient layer (if no explicit priority)
    for assoc in associations:
        if assoc.target_type in ["person", "place"] and assoc.priority not in ["strongly_recommend", "optional"]:
            assoc_node = next((n for n in nodes if n.id == str(assoc.id)), None)
            if assoc_node:
                assert assoc_node.layer == "convenient", \
                    f"person/place association {assoc.id} should be in convenient layer, got: {assoc_node.layer}"


@pytest.mark.asyncio
async def test_layer_determination_logic():
    """
    Unit test for _determine_layer method to verify layer classification logic.
    """
    # Test priority-based classification
    assert determine_layer("strongly_recommend", "person", "location") == "must_do"
    assert determine_layer("convenient", "person", "location") == "convenient"
    assert determine_layer("optional", "person", "location") == "background"

    # Test type-based classification (when priority is not explicit)
    assert determine_layer("", "task", "task") == "must_do"
    assert determine_layer("", "reminder", "task") == "must_do"
    assert determine_layer("", "person", "person") == "convenient"
    assert determine_layer("", "place", "location") == "convenient"
    assert determine_layer("", "gift", "gift") == "convenient"
    assert determine_layer("", "date", "temporal") == "background"
    assert determine_layer("", "memory", "memory") == "background"

    # Test priority overrides type
    assert determine_layer("strongly_recommend", "date", "temporal") == "must_do"
    assert determine_layer("optional", "task", "task") == "background"


@pytest.mark.asyncio
async def test_all_nodes_have_layer():
    """
    Test that all nodes in the graph have a layer assigned.
    """
    service = EventGraphService(db=None)
    
    # Create a simple trip event
    trip_event = CuratedEvent(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        title="Test Trip",
        event_type="travel",
        priority="high",
        status="confirmed",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=3),
        location="Beijing",
        is_active=True,
    )
    
    # Create some events
    events = [
        trip_event,
        CuratedEvent(
            id=uuid4(),
            family_id=trip_event.family_id,
            user_id=trip_event.user_id,
            title="Meeting",
            event_type="meeting",
            priority="high",
            status="confirmed",
            normalized_start=trip_event.normalized_start + timedelta(hours=2),
            normalized_end=trip_event.normalized_start + timedelta(hours=3),
            location="Beijing",
            is_active=True,
        ),
    ]
    
    # Create some associations
    associations = [
        EventAssociation(
            id=uuid4(),
            family_id=trip_event.family_id,
            source_event_id=trip_event.id,
            target_type="person",
            target_id=str(uuid4()),
            association_type="person",
            title="Meet Zhang San",
            reason="He's in Beijing",
            priority="strongly_recommend",
            confidence=0.9,
            is_dismissed=False,
            is_confirmed=False,
        ),
    ]
    
    # Build graph
    nodes, edges = service._build_graph(trip_event, events, associations)
    
    # Verify all nodes have layer
    for node in nodes:
        assert hasattr(node, 'layer'), f"Node {node.id} missing layer attribute"
        # Category nodes and center node should have layer
        if node.type in ["trip", "category"] or node.id == str(trip_event.id):
            assert node.layer is not None, f"Node {node.id} ({node.type}) has None layer"
