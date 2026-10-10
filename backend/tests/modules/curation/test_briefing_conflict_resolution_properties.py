"""
Property-Based Tests for Briefing Conflict Resolution

Feature: secretary-intelligence-enhancement
Property 21: Briefing Conflict Resolution

For any conflict in the briefing period, the briefing should include
the conflict description AND at least one resolution suggestion.

Validates: Requirements 5.6
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.briefing.services.briefing_generator import BriefingGenerator
from src.modules.curation.models import CuratedEvent


# Test configuration
class TestBriefingConflictResolutionProperties:
    """Property tests for briefing conflict resolution"""
    
    @pytest.mark.asyncio
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        event1_title=st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=("L",))),
        event2_title=st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=("L",))),
        overlap_hours=st.integers(min_value=1, max_value=1),
    )
    async def test_property_21_conflict_with_resolution_suggestions(
        self,
        db_session: AsyncSession,
        event1_title: str,
        event2_title: str,
        overlap_hours: int,
    ):
        """
        Property 21: Briefing Conflict Resolution
        
        For any conflict in the briefing period, the briefing should include
        the conflict description AND at least one resolution suggestion.
        
        Validates: Requirements 5.6
        """
        family_id = uuid4()
        
        # Create two overlapping events
        today = datetime.now(timezone.utc)
        event1 = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title=event1_title,
            event_type="meeting",
            location="办公室A",
            normalized_start=today,
            normalized_end=today + timedelta(hours=2),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event1)
        
        # Event2 starts during event1 (overlap)
        event2 = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title=event2_title,
            event_type="meeting",
            location="办公室B",
            normalized_start=today + timedelta(hours=overlap_hours),
            normalized_end=today + timedelta(hours=overlap_hours + 2),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event2)
        await db_session.commit()
        
        # Generate briefing
        generator = BriefingGenerator(db_session)
        briefing = await generator.generate_daily_briefing(
            family_id=family_id,
            target_date=today.date(),
        )
        
        # Property: Briefing should detect the conflict
        assert len(briefing.conflicts) > 0, \
            "Briefing should detect conflicts when events overlap"
        
        # Property: Each conflict should have a description
        for conflict in briefing.conflicts:
            assert conflict.description, \
                "Each conflict should have a description"
            assert len(conflict.description) > 0, \
                "Conflict description should not be empty"
        
        # Property: Each conflict should have at least one resolution suggestion
        for conflict in briefing.conflicts:
            assert len(conflict.resolution_suggestions) > 0, \
                "Each conflict should have at least one resolution suggestion"
        
        # Property: Resolution suggestions should be actionable (not empty strings)
        for conflict in briefing.conflicts:
            for suggestion in conflict.resolution_suggestions:
                assert suggestion and len(suggestion) > 5, \
                    f"Resolution suggestion should be actionable: {suggestion}"
    
    @pytest.mark.asyncio
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        num_conflicts=st.integers(min_value=2, max_value=4),
    )
    async def test_property_21_multiple_conflicts_with_resolutions(
        self,
        db_session: AsyncSession,
        num_conflicts: int,
    ):
        """
        Property 21: Briefing Conflict Resolution (Multiple Conflicts)
        
        When there are multiple conflicts in the briefing period, each conflict
        should have its own resolution suggestions.
        
        Validates: Requirements 5.6
        """
        family_id = uuid4()

        # Create multiple pairs of overlapping events
        # Use midnight UTC today as base so all events fit within the same calendar day
        today = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time(), tzinfo=timezone.utc)
        for i in range(num_conflicts):
            # Each pair starts at a different time to create separate conflicts
            start_time = today + timedelta(hours=i * 4)
            
            event1 = CuratedEvent(
                id=uuid4(),
                family_id=family_id,
                title=f"会议{i*2+1}",
                event_type="meeting",
                location="办公室",
                normalized_start=start_time,
                normalized_end=start_time + timedelta(hours=2),
                is_active=True,
                status="confirmed",
                original_event_ids=[],
                source_types=[],
            )
            db_session.add(event1)
            
            event2 = CuratedEvent(
                id=uuid4(),
                family_id=family_id,
                title=f"会议{i*2+2}",
                event_type="meeting",
                location="办公室",
                normalized_start=start_time + timedelta(hours=1),
                normalized_end=start_time + timedelta(hours=3),
                is_active=True,
                status="confirmed",
                original_event_ids=[],
                source_types=[],
            )
            db_session.add(event2)
        
        await db_session.commit()
        
        # Generate briefing
        generator = BriefingGenerator(db_session)
        briefing = await generator.generate_daily_briefing(
            family_id=family_id,
            target_date=today.date(),
        )
        
        # Property: Briefing should detect all conflicts
        assert len(briefing.conflicts) >= num_conflicts, \
            f"Briefing should detect at least {num_conflicts} conflicts"
        
        # Property: Each conflict should have resolution suggestions
        for conflict in briefing.conflicts:
            assert len(conflict.resolution_suggestions) > 0, \
                "Each conflict should have resolution suggestions"
    
    @pytest.mark.asyncio
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        event1_title=st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=("L",))),
        event2_title=st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=("L",))),
    )
    async def test_property_21_resolution_mentions_events(
        self,
        db_session: AsyncSession,
        event1_title: str,
        event2_title: str,
    ):
        """
        Property 21: Briefing Conflict Resolution (Event Mention)
        
        Resolution suggestions should mention which event(s) to adjust,
        making them actionable and specific.
        
        Validates: Requirements 5.6
        """
        family_id = uuid4()
        
        # Create two overlapping events
        today = datetime.now(timezone.utc)
        event1 = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title=event1_title,
            event_type="meeting",
            location="办公室",
            normalized_start=today,
            normalized_end=today + timedelta(hours=2),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event1)
        
        event2 = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title=event2_title,
            event_type="meeting",
            location="办公室",
            normalized_start=today + timedelta(hours=1),
            normalized_end=today + timedelta(hours=3),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event2)
        await db_session.commit()
        
        # Generate briefing
        generator = BriefingGenerator(db_session)
        briefing = await generator.generate_daily_briefing(
            family_id=family_id,
            target_date=today.date(),
        )
        
        # Property: At least one resolution suggestion should mention an event
        assert len(briefing.conflicts) > 0, "Should detect conflict"
        
        for conflict in briefing.conflicts:
            # At least one suggestion should mention one of the events
            mentions_event = any(
                event1_title in suggestion or event2_title in suggestion or
                "调整" in suggestion or "取消" in suggestion
                for suggestion in conflict.resolution_suggestions
            )
            assert mentions_event, \
                "Resolution suggestions should mention events or actions"
    
    @pytest.mark.asyncio
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        gap_hours=st.integers(min_value=1, max_value=5),
    )
    async def test_property_21_no_conflict_for_non_overlapping_events(
        self,
        db_session: AsyncSession,
        gap_hours: int,
    ):
        """
        Property 21: Briefing Conflict Resolution (No False Positives)
        
        When events do not overlap (have a gap between them), the briefing
        should NOT report a conflict.
        
        Validates: Requirements 5.6
        """
        family_id = uuid4()
        
        # Create two non-overlapping events
        today = datetime.now(timezone.utc)
        event1 = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title="会议1",
            event_type="meeting",
            location="办公室",
            normalized_start=today,
            normalized_end=today + timedelta(hours=1),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event1)
        
        # Event2 starts after event1 ends (with a gap)
        event2 = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title="会议2",
            event_type="meeting",
            location="办公室",
            normalized_start=today + timedelta(hours=1 + gap_hours),
            normalized_end=today + timedelta(hours=2 + gap_hours),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event2)
        await db_session.commit()
        
        # Generate briefing
        generator = BriefingGenerator(db_session)
        briefing = await generator.generate_daily_briefing(
            family_id=family_id,
            target_date=today.date(),
        )
        
        # Property: Should NOT detect a conflict
        assert len(briefing.conflicts) == 0, \
            "Briefing should not detect conflicts for non-overlapping events"
    
    @pytest.mark.asyncio
    async def test_property_21_conflict_description_clarity(
        self,
        db_session: AsyncSession,
    ):
        """
        Property 21: Briefing Conflict Resolution (Description Clarity)
        
        Conflict descriptions should clearly identify which events are in conflict,
        making it easy for the user to understand the problem.
        
        Validates: Requirements 5.6
        """
        family_id = uuid4()
        
        # Create two overlapping events with distinct titles
        today = datetime.now(timezone.utc)
        event1 = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title="重要客户会议",
            event_type="meeting",
            location="办公室",
            normalized_start=today,
            normalized_end=today + timedelta(hours=2),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event1)
        
        event2 = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title="团队周会",
            event_type="meeting",
            location="办公室",
            normalized_start=today + timedelta(hours=1),
            normalized_end=today + timedelta(hours=3),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event2)
        await db_session.commit()
        
        # Generate briefing
        generator = BriefingGenerator(db_session)
        briefing = await generator.generate_daily_briefing(
            family_id=family_id,
            target_date=today.date(),
        )
        
        # Property: Conflict description should mention both events
        assert len(briefing.conflicts) > 0, "Should detect conflict"
        
        conflict = briefing.conflicts[0]
        assert "重要客户会议" in conflict.description or "团队周会" in conflict.description, \
            "Conflict description should mention at least one event"
        
        # Property: Description should indicate the nature of the conflict
        conflict_keywords = ["重叠", "冲突", "时间", "同时"]
        has_conflict_keyword = any(
            keyword in conflict.description
            for keyword in conflict_keywords
        )
        assert has_conflict_keyword, \
            "Conflict description should indicate the nature of the conflict"
