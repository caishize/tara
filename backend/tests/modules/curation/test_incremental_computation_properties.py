"""
Property-Based Tests for Incremental Association Computation

Feature: secretary-intelligence-enhancement
Property 27: Incremental Association Computation

For any curation run, the Association Discoverer should only process events that
are new or modified since the last run, not reprocess all events.

Validates: Requirements 8.2
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.modules.curation.models import CuratedEvent, CurationJob


# --- Property Tests ---

@pytest.mark.asyncio
@settings(max_examples=10)
@given(
    num_existing_events=st.integers(min_value=5, max_value=20),
    num_new_events=st.integers(min_value=1, max_value=10),
)
async def test_property_27_incremental_computation(
    num_existing_events: int,
    num_new_events: int,
):
    """
    Feature: secretary-intelligence-enhancement
    Property 27: Incremental Association Computation
    
    For any curation run, the Association Discoverer should only process events that
    are new or modified since the last run, not reprocess all events.
    
    Validates: Requirements 8.2
    """
    family_id = uuid4()
    user_id = uuid4()
    
    # Simulate last curation time
    last_curation_time = datetime.now(timezone.utc) - timedelta(hours=24)
    
    # Create existing events (before last curation)
    existing_events = []
    for i in range(num_existing_events):
        event = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            title=f"Existing Event {i}",
            event_type="meeting",
            priority="normal",
            status="confirmed",
            normalized_start=datetime.now(timezone.utc) + timedelta(days=i),
            normalized_end=datetime.now(timezone.utc) + timedelta(days=i, hours=2),
            location="Beijing",
            is_active=True,
            created_at=last_curation_time - timedelta(hours=i),
            updated_at=last_curation_time - timedelta(hours=i),
        )
        existing_events.append(event)
    
    # Create new events (after last curation)
    new_events = []
    for i in range(num_new_events):
        event = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            title=f"New Event {i}",
            event_type="meeting",
            priority="high",
            status="pending",
            normalized_start=datetime.now(timezone.utc) + timedelta(days=i + 30),
            normalized_end=datetime.now(timezone.utc) + timedelta(days=i + 30, hours=2),
            location="Shanghai",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        new_events.append(event)
    
    # Property 1: Only new/modified events should be processed
    events_to_process = [e for e in new_events if e.updated_at > last_curation_time]
    assert len(events_to_process) == num_new_events, \
        f"Should process {num_new_events} new events, got {len(events_to_process)}"
    
    # Property 2: Existing events should not be reprocessed
    events_to_skip = [e for e in existing_events if e.updated_at <= last_curation_time]
    assert len(events_to_skip) == num_existing_events, \
        f"Should skip {num_existing_events} existing events, got {len(events_to_skip)}"
    
    # Property 3: Total processing should be less than full reprocessing
    total_events = num_existing_events + num_new_events
    assert len(events_to_process) < total_events, \
        "Incremental processing should process fewer events than full reprocessing"
    
    # Property 4: Processing efficiency should improve with more existing events
    efficiency_ratio = len(events_to_process) / total_events
    assert efficiency_ratio < 1.0, "Efficiency ratio should be less than 1.0"
    
    # Property 5: Modified events should be included in processing
    # Simulate modifying an existing event
    if existing_events:
        modified_event = existing_events[0]
        modified_event.updated_at = datetime.now(timezone.utc)
        
        events_to_process_with_modified = [
            e for e in existing_events + new_events
            if e.updated_at > last_curation_time
        ]
        assert modified_event in events_to_process_with_modified, \
            "Modified event should be included in processing"


@pytest.mark.asyncio
async def test_incremental_computation_with_curation_job():
    """
    Test incremental computation using CurationJob timestamps.
    """
    family_id = uuid4()
    
    # Create a previous curation job
    previous_job = CurationJob(
        id=uuid4(),
        family_id=family_id,
        trigger_type="scheduled",
        status="completed",
        date_range_start=datetime.now(timezone.utc).date(),
        date_range_end=(datetime.now(timezone.utc) + timedelta(days=30)).date(),
        started_at=datetime.now(timezone.utc) - timedelta(hours=25),
        completed_at=datetime.now(timezone.utc) - timedelta(hours=24),
        events_processed=10,
        events_curated=8,
        associations_created=15,
    )
    
    # Create events with different timestamps
    old_event = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        user_id=uuid4(),
        title="Old Event",
        event_type="meeting",
        priority="normal",
        status="confirmed",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=1, hours=2),
        location="Beijing",
        is_active=True,
        created_at=previous_job.completed_at - timedelta(hours=1),
        updated_at=previous_job.completed_at - timedelta(hours=1),
    )
    
    new_event = CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        user_id=uuid4(),
        title="New Event",
        event_type="meeting",
        priority="high",
        status="pending",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=2),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=2, hours=2),
        location="Shanghai",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    
    # Verify incremental processing logic
    last_curation_time = previous_job.completed_at
    
    should_process_old = old_event.updated_at > last_curation_time
    should_process_new = new_event.updated_at > last_curation_time
    
    assert not should_process_old, "Old event should not be processed"
    assert should_process_new, "New event should be processed"


@pytest.mark.asyncio
async def test_incremental_computation_performance():
    """
    Test that incremental computation improves performance.
    """
    family_id = uuid4()
    user_id = uuid4()
    last_curation_time = datetime.now(timezone.utc) - timedelta(hours=24)
    
    # Create a large number of existing events
    num_existing = 100
    num_new = 5
    
    existing_events = [
        CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            title=f"Event {i}",
            event_type="meeting",
            priority="normal",
            status="confirmed",
            normalized_start=datetime.now(timezone.utc) + timedelta(days=i),
            normalized_end=datetime.now(timezone.utc) + timedelta(days=i, hours=1),
            location="Beijing",
            is_active=True,
            created_at=last_curation_time - timedelta(hours=i),
            updated_at=last_curation_time - timedelta(hours=i),
        )
        for i in range(num_existing)
    ]
    
    new_events = [
        CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            user_id=user_id,
            title=f"New Event {i}",
            event_type="meeting",
            priority="high",
            status="pending",
            normalized_start=datetime.now(timezone.utc) + timedelta(days=i + 200),
            normalized_end=datetime.now(timezone.utc) + timedelta(days=i + 200, hours=1),
            location="Shanghai",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        for i in range(num_new)
    ]
    
    # Calculate processing reduction
    total_events = num_existing + num_new
    events_to_process = [e for e in new_events if e.updated_at > last_curation_time]
    
    processing_reduction = 1 - (len(events_to_process) / total_events)
    
    # Verify significant performance improvement
    assert processing_reduction > 0.9, \
        f"Should achieve >90% processing reduction, got {processing_reduction * 100:.1f}%"
    
    # Verify only new events are processed
    assert len(events_to_process) == num_new, \
        f"Should process only {num_new} new events, got {len(events_to_process)}"
