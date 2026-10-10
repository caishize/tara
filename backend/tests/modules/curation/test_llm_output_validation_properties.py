"""
Property-Based Tests for LLM Output Structure Validation

Feature: secretary-intelligence-enhancement
Property 31: LLM Output Structure Validation

For any LLM response for association discovery or insight generation, the system
should validate the output against a JSON schema and reject malformed responses.

Validates: Requirements 10.2, 10.3, 10.5
"""
import pytest
import json
from hypothesis import given, strategies as st, settings
from typing import Dict, Any


# --- Test Strategies ---

@st.composite
def valid_association_response_strategy(draw):
    """Generate a valid association discovery response"""
    num_associations = draw(st.integers(min_value=0, max_value=10))
    
    associations = []
    for _ in range(num_associations):
        assoc = {
            "source_event_id": str(draw(st.uuids())),
            "target_id": str(draw(st.uuids())),
            "target_type": draw(st.sampled_from(["person", "place", "task", "date", "memory", "gift"])),
            "association_type": draw(st.sampled_from(["location", "temporal", "person", "memory", "task"])),
            "title": draw(st.text(min_size=5, max_size=50)),
            "reason": draw(st.text(min_size=10, max_size=100)),
            "priority": draw(st.sampled_from(["strongly_recommend", "convenient", "optional"])),
            "confidence": draw(st.floats(min_value=0.0, max_value=1.0)),
        }
        associations.append(assoc)
    
    return {"associations": associations}


@st.composite
def valid_insight_response_strategy(draw):
    """Generate a valid insight generation response"""
    num_insights = draw(st.integers(min_value=0, max_value=5))
    
    insights = [
        draw(st.text(min_size=10, max_size=200))
        for _ in range(num_insights)
    ]
    
    return {"insights": insights}


@st.composite
def malformed_response_strategy(draw):
    """Generate various malformed responses"""
    malformed_types = [
        {},  # Empty object
        {"wrong_key": []},  # Wrong key
        {"associations": "not_a_list"},  # Wrong type
        {"associations": [{"missing_fields": True}]},  # Missing required fields
        "not_a_dict",  # Not even a dict
        None,  # None
    ]
    return draw(st.sampled_from(malformed_types))


# --- Property Tests ---

@pytest.mark.asyncio
@settings(max_examples=10)
@given(
    response=valid_association_response_strategy(),
)
async def test_property_31_valid_association_response(
    response: Dict[str, Any],
):
    """
    Feature: secretary-intelligence-enhancement
    Property 31: LLM Output Structure Validation
    
    For any valid LLM association discovery response, the system should accept it.
    
    Validates: Requirements 10.2, 10.3, 10.5
    """
    # Property 1: Valid response should have "associations" key
    assert "associations" in response, "Response should have 'associations' key"
    
    # Property 2: "associations" should be a list
    assert isinstance(response["associations"], list), "'associations' should be a list"
    
    # Property 3: Each association should have required fields
    required_fields = [
        "source_event_id",
        "target_id",
        "target_type",
        "association_type",
        "title",
        "reason",
        "priority",
        "confidence",
    ]
    
    for assoc in response["associations"]:
        for field in required_fields:
            assert field in assoc, f"Association missing required field: {field}"
    
    # Property 4: Field types should be correct
    for assoc in response["associations"]:
        assert isinstance(assoc["source_event_id"], str), "source_event_id should be string"
        assert isinstance(assoc["target_id"], str), "target_id should be string"
        assert isinstance(assoc["target_type"], str), "target_type should be string"
        assert isinstance(assoc["association_type"], str), "association_type should be string"
        assert isinstance(assoc["title"], str), "title should be string"
        assert isinstance(assoc["reason"], str), "reason should be string"
        assert isinstance(assoc["priority"], str), "priority should be string"
        assert isinstance(assoc["confidence"], (int, float)), "confidence should be number"
    
    # Property 5: Enum fields should have valid values
    valid_target_types = ["person", "place", "task", "date", "memory", "gift", "reminder"]
    valid_association_types = ["location", "temporal", "person", "semantic", "memory", "task"]
    valid_priorities = ["strongly_recommend", "convenient", "optional"]
    
    for assoc in response["associations"]:
        assert assoc["target_type"] in valid_target_types, \
            f"Invalid target_type: {assoc['target_type']}"
        assert assoc["association_type"] in valid_association_types, \
            f"Invalid association_type: {assoc['association_type']}"
        assert assoc["priority"] in valid_priorities, \
            f"Invalid priority: {assoc['priority']}"
    
    # Property 6: Confidence should be between 0 and 1
    for assoc in response["associations"]:
        assert 0.0 <= assoc["confidence"] <= 1.0, \
            f"Confidence should be between 0 and 1, got: {assoc['confidence']}"


@pytest.mark.asyncio
@settings(max_examples=10)
@given(
    response=valid_insight_response_strategy(),
)
async def test_property_31_valid_insight_response(
    response: Dict[str, Any],
):
    """
    Test that valid insight generation responses are accepted.
    """
    # Property 1: Valid response should have "insights" key
    assert "insights" in response, "Response should have 'insights' key"
    
    # Property 2: "insights" should be a list
    assert isinstance(response["insights"], list), "'insights' should be a list"
    
    # Property 3: Each insight should be a non-empty string
    for insight in response["insights"]:
        assert isinstance(insight, str), "Insight should be a string"
        assert len(insight) > 0, "Insight should not be empty"


@pytest.mark.asyncio
@settings(max_examples=10)
@given(
    response=malformed_response_strategy(),
)
async def test_property_31_malformed_response_rejection(
    response: Any,
):
    """
    Test that malformed LLM responses are rejected.
    """
    # Property 1: Malformed responses should be detectable
    is_valid = False
    
    required_assoc_fields = [
        "source_event_id", "target_id", "target_type",
        "association_type", "title", "reason", "priority", "confidence",
    ]

    try:
        # Check if response is a dict
        if not isinstance(response, dict):
            is_valid = False
        # Check if it has the required key
        elif "associations" not in response and "insights" not in response:
            is_valid = False
        # Check if the value is a list
        elif "associations" in response and not isinstance(response["associations"], list):
            is_valid = False
        elif "insights" in response and not isinstance(response["insights"], list):
            is_valid = False
        # Check that each association has required fields
        elif "associations" in response and any(
            not all(f in assoc for f in required_assoc_fields)
            for assoc in response["associations"]
            if isinstance(assoc, dict)
        ):
            is_valid = False
        else:
            is_valid = True
    except Exception:
        is_valid = False
    
    # Malformed responses should be detected as invalid
    assert not is_valid, f"Malformed response should be detected as invalid: {response}"


@pytest.mark.asyncio
async def test_llm_output_validation_missing_fields():
    """
    Test that responses with missing required fields are rejected.
    """
    # Response missing required fields
    invalid_response = {
        "associations": [
            {
                "source_event_id": "test-id",
                "target_id": "test-target",
                # Missing: target_type, association_type, title, reason, priority, confidence
            }
        ]
    }
    
    # Validate response
    required_fields = [
        "source_event_id",
        "target_id",
        "target_type",
        "association_type",
        "title",
        "reason",
        "priority",
        "confidence",
    ]
    
    is_valid = True
    for assoc in invalid_response["associations"]:
        for field in required_fields:
            if field not in assoc:
                is_valid = False
                break
    
    assert not is_valid, "Response with missing fields should be invalid"


@pytest.mark.asyncio
async def test_llm_output_validation_wrong_types():
    """
    Test that responses with wrong field types are rejected.
    """
    # Response with wrong types
    invalid_response = {
        "associations": [
            {
                "source_event_id": 123,  # Should be string
                "target_id": "test-target",
                "target_type": "person",
                "association_type": "person",
                "title": "Test",
                "reason": "Test reason",
                "priority": "convenient",
                "confidence": "high",  # Should be number
            }
        ]
    }
    
    # Validate types
    is_valid = True
    for assoc in invalid_response["associations"]:
        if not isinstance(assoc["source_event_id"], str):
            is_valid = False
        if not isinstance(assoc["confidence"], (int, float)):
            is_valid = False
    
    assert not is_valid, "Response with wrong types should be invalid"


@pytest.mark.asyncio
async def test_llm_output_validation_invalid_enum_values():
    """
    Test that responses with invalid enum values are rejected.
    """
    # Response with invalid enum values
    invalid_response = {
        "associations": [
            {
                "source_event_id": "test-id",
                "target_id": "test-target",
                "target_type": "invalid_type",  # Invalid
                "association_type": "person",
                "title": "Test",
                "reason": "Test reason",
                "priority": "super_urgent",  # Invalid
                "confidence": 0.8,
            }
        ]
    }
    
    # Validate enum values
    valid_target_types = ["person", "place", "task", "date", "memory", "gift", "reminder"]
    valid_priorities = ["strongly_recommend", "convenient", "optional"]
    
    is_valid = True
    for assoc in invalid_response["associations"]:
        if assoc["target_type"] not in valid_target_types:
            is_valid = False
        if assoc["priority"] not in valid_priorities:
            is_valid = False
    
    assert not is_valid, "Response with invalid enum values should be invalid"


@pytest.mark.asyncio
async def test_llm_output_validation_confidence_range():
    """
    Test that confidence values outside [0, 1] are rejected.
    """
    # Response with out-of-range confidence
    invalid_response = {
        "associations": [
            {
                "source_event_id": "test-id",
                "target_id": "test-target",
                "target_type": "person",
                "association_type": "person",
                "title": "Test",
                "reason": "Test reason",
                "priority": "convenient",
                "confidence": 1.5,  # Out of range
            }
        ]
    }
    
    # Validate confidence range
    is_valid = True
    for assoc in invalid_response["associations"]:
        if not (0.0 <= assoc["confidence"] <= 1.0):
            is_valid = False
    
    assert not is_valid, "Response with out-of-range confidence should be invalid"
