"""
Property-based tests for association priority classification.

Feature: secretary-intelligence-enhancement
Property 7: Association Priority Classification

For any set of discovered associations, they should be classified into exactly one
of three priority levels (strongly_recommend, convenient, optional) based on user
intent explicitness, time urgency, and opportunity rarity.

Validates: Requirements 2.3
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from hypothesis import given, strategies as st, settings

from src.modules.curation.models import CuratedEvent, EventAssociation, SocialIntent
from src.modules.date_manager.models import ImportantDate
from src.modules.member.models import Member
from src.modules.curation.services.rule_engine import RuleBasedAssociationEngine


# Strategy for generating event types
event_type_strategy = st.sampled_from([
    "business_trip", "travel", "meeting", "appointment", "reminder"
])

# Strategy for generating association types
association_type_strategy = st.sampled_from([
    "memory", "temporal", "location", "person", "task"
])

# Strategy for generating priority levels
priority_strategy = st.sampled_from([
    "strongly_recommend", "convenient", "optional"
])


@given(
    association_type=association_type_strategy,
    event_type=event_type_strategy,
    confidence=st.floats(min_value=0.5, max_value=1.0),
)
@settings(max_examples=10, deadline=None)
def test_property_7_priority_classification_returns_valid_level(
    association_type: str,
    event_type: str,
    confidence: float,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 7: Association Priority Classification
    
    For any association, the priority classification should return exactly one
    of the three valid priority levels.
    """
    # Create test objects
    family_id = uuid4()
    event_id = uuid4()
    
    event = CuratedEvent(
        id=event_id,
        family_id=family_id,
        title="Test Event",
        event_type=event_type,
        normalized_start=datetime.now(timezone.utc),
        location="北京",
    )
    
    association = EventAssociation(
        id=uuid4(),
        family_id=family_id,
        source_event_id=event_id,
        target_id=str(uuid4()),
        target_type="person",
        association_type=association_type,
        title="Test Association",
        reason="Test reason",
        priority="convenient",  # Initial value
        confidence=confidence,
    )
    
    # Create rule engine (no session needed for classification)
    engine = RuleBasedAssociationEngine(session=None)
    
    # Classify priority
    priority = engine.classify_association_priority(association, event)
    
    # Verify priority is one of the three valid levels
    assert priority in ["strongly_recommend", "convenient", "optional"]


@given(
    days_until_date=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=10, deadline=None)
def test_property_7_temporal_associations_urgency_based_priority(
    days_until_date: int,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 7: Association Priority Classification
    
    For temporal associations (important dates), priority should be based on
    time urgency: closer dates get higher priority.
    """
    family_id = uuid4()
    event_id = uuid4()
    
    event_date = date.today()
    important_date = event_date + timedelta(days=days_until_date)
    
    event = CuratedEvent(
        id=event_id,
        family_id=family_id,
        title="Test Event",
        event_type="meeting",
        normalized_start=datetime.combine(event_date, datetime.min.time()).replace(tzinfo=timezone.utc),
        location="北京",
    )
    
    imp_date = ImportantDate(
        id=uuid4(),
        family_id=family_id,
        title="生日",
        solar_date=important_date,
        date_type="birthday",
    )
    
    association = EventAssociation(
        id=uuid4(),
        family_id=family_id,
        source_event_id=event_id,
        target_id=str(imp_date.id),
        target_type="date",
        association_type="temporal",
        title="准备生日",
        reason="Test reason",
        priority="convenient",
        confidence=0.9,
    )
    
    engine = RuleBasedAssociationEngine(session=None)
    priority = engine.classify_association_priority(association, event, imp_date)
    
    # Verify priority based on urgency
    if days_until_date <= 3:
        # Very urgent - should be strongly recommended
        assert priority == "strongly_recommend"
    elif days_until_date <= 7:
        # Moderately urgent - should be convenient
        assert priority == "convenient"
    else:
        # Not urgent - could be optional or convenient
        assert priority in ["convenient", "optional"]


@given(
    event_type=st.sampled_from(["business_trip", "travel"]),
    confidence=st.floats(min_value=0.8, max_value=1.0),
)
@settings(max_examples=10, deadline=None)
def test_property_7_memory_associations_always_strongly_recommended(
    event_type: str,
    confidence: float,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 7: Association Priority Classification
    
    For memory associations (user-expressed intents), priority should always be
    "strongly_recommend" because they represent explicit user wishes.
    """
    family_id = uuid4()
    event_id = uuid4()
    
    event = CuratedEvent(
        id=event_id,
        family_id=family_id,
        title="北京出差",
        event_type=event_type,
        normalized_start=datetime.now(timezone.utc),
        location="北京",
    )
    
    intent = SocialIntent(
        id=uuid4(),
        family_id=family_id,
        intent_type="meet_person",
        target_person_name="张三",
        action_description="吃饭",
        trigger_type="location",
        trigger_location="北京",
        status="active",
    )
    
    association = EventAssociation(
        id=uuid4(),
        family_id=family_id,
        source_event_id=event_id,
        target_id=str(intent.id),
        target_type="memory",
        association_type="memory",
        title="约见张三",
        reason="您之前提到要见张三",
        priority="convenient",  # Will be reclassified
        confidence=confidence,
    )
    
    engine = RuleBasedAssociationEngine(session=None)
    priority = engine.classify_association_priority(association, event, intent)
    
    # Memory associations should always be strongly recommended
    assert priority == "strongly_recommend"


@given(
    event_type=st.sampled_from(["business_trip", "travel"]),
    confidence=st.floats(min_value=0.8, max_value=1.0),
)
@settings(max_examples=10, deadline=None)
def test_property_7_location_associations_during_travel_are_valuable(
    event_type: str,
    confidence: float,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 7: Association Priority Classification
    
    For location associations during travel/business trips with high confidence,
    priority should be "strongly_recommend" because travel is a rare opportunity.
    """
    family_id = uuid4()
    event_id = uuid4()
    
    event = CuratedEvent(
        id=event_id,
        family_id=family_id,
        title="北京出差",
        event_type=event_type,
        normalized_start=datetime.now(timezone.utc),
        location="北京",
    )
    
    member = Member(
        id=uuid4(),
        family_id=family_id,
        created_by=uuid4(),
        name="张三",
    )

    association = EventAssociation(
        id=uuid4(),
        family_id=family_id,
        source_event_id=event_id,
        target_id=str(member.id),
        target_type="person",
        association_type="location",
        title="见张三",
        reason="张三在北京",
        priority="convenient",  # Will be reclassified
        confidence=confidence,
    )

    engine = RuleBasedAssociationEngine(session=None)
    priority = engine.classify_association_priority(association, event, member)

    # High-confidence location associations during travel should be strongly recommended
    assert priority == "strongly_recommend"


@given(
    confidence=st.floats(min_value=0.5, max_value=0.69),
)
@settings(max_examples=10, deadline=None)
def test_property_7_low_confidence_location_associations_are_optional(
    confidence: float,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 7: Association Priority Classification
    
    For location associations with low confidence, priority should be "optional"
    because the match quality is uncertain.
    """
    family_id = uuid4()
    event_id = uuid4()
    
    event = CuratedEvent(
        id=event_id,
        family_id=family_id,
        title="会议",
        event_type="meeting",
        normalized_start=datetime.now(timezone.utc),
        location="北京",
    )
    
    member = Member(
        id=uuid4(),
        family_id=family_id,
        created_by=uuid4(),
        name="李四",
    )
    
    association = EventAssociation(
        id=uuid4(),
        family_id=family_id,
        source_event_id=event_id,
        target_id=str(member.id),
        target_type="person",
        association_type="location",
        title="见李四",
        reason="李四在北京郊区",
        priority="convenient",  # Will be reclassified
        confidence=confidence,
    )
    
    engine = RuleBasedAssociationEngine(session=None)
    priority = engine.classify_association_priority(association, event, member)
    
    # Low confidence should result in optional priority
    assert priority == "optional"


def test_property_7_all_associations_have_exactly_one_priority():
    """
    Feature: secretary-intelligence-enhancement
    Property 7: Association Priority Classification
    
    Every association must have exactly one priority level assigned.
    """
    family_id = uuid4()
    event_id = uuid4()
    
    event = CuratedEvent(
        id=event_id,
        family_id=family_id,
        title="Test Event",
        event_type="meeting",
        normalized_start=datetime.now(timezone.utc),
        location="北京",
    )
    
    # Test all association types
    association_types = ["memory", "temporal", "location", "person", "task"]
    
    engine = RuleBasedAssociationEngine(session=None)
    
    for assoc_type in association_types:
        association = EventAssociation(
            id=uuid4(),
            family_id=family_id,
            source_event_id=event_id,
            target_id=str(uuid4()),
            target_type="person",
            association_type=assoc_type,
            title=f"Test {assoc_type}",
            reason="Test reason",
            priority="convenient",
            confidence=0.8,
        )
        
        priority = engine.classify_association_priority(association, event)
        
        # Must be exactly one of the three levels
        assert priority in ["strongly_recommend", "convenient", "optional"]
        # Must not be None or empty
        assert priority is not None
        assert priority != ""
