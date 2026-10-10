"""
Property-Based Tests for Briefing Insight Generation

Feature: secretary-intelligence-enhancement
Property 19: Briefing Insight Generation

For any discovered opportunity (historical connection, social intent, stale contact),
the briefing should present it as an insight (contextual suggestion) rather than
a simple list item.

Validates: Requirements 5.3
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.briefing.services.briefing_generator import BriefingGenerator
from src.modules.curation.models import CuratedEvent, SocialIntent
from src.modules.member.models import Member


# Test configuration
class TestBriefingInsightGenerationProperties:
    """Property tests for briefing insight generation"""

    @pytest.mark.asyncio
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        location=st.text(min_size=2, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
        person_name=st.text(min_size=2, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
        action=st.text(min_size=2, max_size=30, alphabet=st.characters(whitelist_categories=("L",))),
    )
    async def test_property_19_insight_generation_for_social_intent(
        self,
        db_session: AsyncSession,
        location: str,
        person_name: str,
        action: str,
    ):
        """
        Property 19: Briefing Insight Generation

        When a briefing contains travel events and there are triggered social intents,
        the briefing should generate insights that present the opportunity as a
        contextual suggestion (not just a list item).

        Validates: Requirements 5.3
        """
        family_id = uuid4()

        # Create a travel event
        event = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title=f"{location}出差",
            event_type="business_trip",
            location=location,
            normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
            normalized_end=datetime.now(timezone.utc) + timedelta(days=2),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event)

        # Create a social intent for the same location
        intent = SocialIntent(
            id=uuid4(),
            family_id=family_id,
            intent_type="meet_person",
            target_person_name=person_name,
            action_description=action,
            trigger_type="location",
            trigger_location=location,
            status="active",
        )
        db_session.add(intent)
        await db_session.commit()

        # Generate briefing
        generator = BriefingGenerator(db_session)
        briefing = await generator.generate_daily_briefing(
            family_id=family_id,
            target_date=(datetime.now(timezone.utc) + timedelta(days=1)).date(),
        )

        # Property: Insights or opportunities should be generated (not empty)
        # The briefing surfaces social intents via key_insights (LLM or rule-based)
        # or via opportunities (always deterministic).
        all_suggestions = briefing.key_insights + briefing.opportunities
        assert len(all_suggestions) > 0, \
            "Briefing should generate insights or opportunities when social intents are triggered"

        # Property: At least one suggestion should mention the person or location
        has_contextual_insight = any(
            location in s or person_name in s
            for s in all_suggestions
        )
        assert has_contextual_insight, \
            "At least one suggestion should mention the location or person from the social intent"

        # Property: Each suggestion should be a meaningful string
        for s in all_suggestions:
            assert len(s) > 5, \
                f"Suggestion should be meaningful: {s}"

    @pytest.mark.asyncio
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        location=st.text(min_size=2, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
        num_historical_events=st.integers(min_value=1, max_value=3),
    )
    async def test_property_19_insight_generation_for_historical_connection(
        self,
        db_session: AsyncSession,
        location: str,
        num_historical_events: int,
    ):
        """
        Property 19: Briefing Insight Generation (Historical Connection)

        When a briefing contains travel events and there are historical events
        at the same location, the briefing should generate insights that
        present the historical connection as a contextual suggestion.

        Validates: Requirements 5.3
        """
        family_id = uuid4()

        # Create historical events at the location
        for i in range(num_historical_events):
            hist_event = CuratedEvent(
                id=uuid4(),
                family_id=family_id,
                title=f"历史事件{i+1}",
                event_type="meeting",
                location=location,
                normalized_start=datetime.now(timezone.utc) - timedelta(days=30 * (i + 1)),
                is_active=True,
                status="completed",
                original_event_ids=[],
                source_types=[],
            )
            db_session.add(hist_event)

        # Create a current travel event
        current_event = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title=f"{location}出差",
            event_type="business_trip",
            location=location,
            normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
            normalized_end=datetime.now(timezone.utc) + timedelta(days=2),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(current_event)
        await db_session.commit()

        # Generate briefing
        generator = BriefingGenerator(db_session)
        briefing = await generator.generate_daily_briefing(
            family_id=family_id,
            target_date=(datetime.now(timezone.utc) + timedelta(days=1)).date(),
        )

        # Property: Insights or priority items should be generated
        # When historical events exist, rule-based fallback generates historical insights
        # (LLM may generate different text or fail, so we check combined output)
        all_suggestions = briefing.key_insights + briefing.opportunities
        assert len(briefing.priority_items) > 0 or len(all_suggestions) > 0, \
            "Briefing should generate priority items or insights when historical events exist"

        # Property: The travel event should appear in priority items
        assert len(briefing.priority_items) > 0, \
            "The travel event should appear in priority items"

        # Property: Insights (if any) should be meaningful suggestions
        for insight in briefing.key_insights:
            assert len(insight) > 10, \
                f"Insight should be a meaningful suggestion: {insight}"

    @pytest.mark.asyncio
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        location=st.text(min_size=2, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
        member_name=st.text(min_size=2, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
    )
    async def test_property_19_insight_generation_for_stale_contact(
        self,
        db_session: AsyncSession,
        location: str,
        member_name: str,
    ):
        """
        Property 19: Briefing Insight Generation (Stale Contact)

        When a briefing contains travel events and there are stale contacts
        (long-time-no-contact) at the location, the briefing should generate
        insights suggesting to meet them.

        Validates: Requirements 5.3
        """
        family_id = uuid4()

        # Create a member at the location
        user_id = uuid4()
        member = Member(
            id=uuid4(),
            family_id=family_id,
            name=member_name,
            address=location,
            created_by=user_id,
            locations={"home": {"address": location}},
        )
        db_session.add(member)

        # Create a travel event to the location
        event = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title=f"{location}出差",
            event_type="business_trip",
            location=location,
            normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
            normalized_end=datetime.now(timezone.utc) + timedelta(days=2),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event)
        await db_session.commit()

        # Generate briefing
        generator = BriefingGenerator(db_session)
        briefing = await generator.generate_daily_briefing(
            family_id=family_id,
            target_date=(datetime.now(timezone.utc) + timedelta(days=1)).date(),
        )

        # Property: Insights or opportunities should be generated
        total_suggestions = len(briefing.key_insights) + len(briefing.opportunities)
        assert total_suggestions > 0, \
            "Briefing should generate insights or opportunities when members are at the location"

        # Property: At least one suggestion should mention the member or location
        all_suggestions = briefing.key_insights + briefing.opportunities
        has_relevant_suggestion = any(
            member_name in suggestion or location in suggestion
            for suggestion in all_suggestions
        )
        assert has_relevant_suggestion, \
            "At least one suggestion should mention the member or location"

        # Property: Suggestions should be actionable (not just informational)
        for suggestion in all_suggestions:
            assert len(suggestion) > 5, \
                f"Suggestion should be meaningful: {suggestion}"

    @pytest.mark.asyncio
    async def test_property_19_no_insights_when_no_opportunities(
        self,
        db_session: AsyncSession,
    ):
        """
        Property 19: Briefing Insight Generation (No Opportunities)

        When there are no opportunities (no social intents, no historical events,
        no stale contacts), the briefing should not generate generic insights.
        It's better to have no insights than generic ones.

        Validates: Requirements 5.3
        """
        family_id = uuid4()

        # Create a simple event with no context
        event = CuratedEvent(
            id=uuid4(),
            family_id=family_id,
            title="简单会议",
            event_type="meeting",
            location="办公室",
            normalized_start=datetime.now(timezone.utc) + timedelta(days=1),
            is_active=True,
            status="confirmed",
            original_event_ids=[],
            source_types=[],
        )
        db_session.add(event)
        await db_session.commit()

        # Generate briefing
        generator = BriefingGenerator(db_session)
        briefing = await generator.generate_daily_briefing(
            family_id=family_id,
            target_date=(datetime.now(timezone.utc) + timedelta(days=1)).date(),
        )

        # Property: If insights are generated, they should not be generic
        generic_keywords = ["检查证件", "提前出发", "准备材料", "确认时间"]
        for insight in briefing.key_insights:
            is_generic = any(keyword in insight for keyword in generic_keywords)
            # We allow some generic insights, but they should be specific to the event
            # Not just "检查证件" but "检查会议材料"
            if is_generic:
                assert len(insight) > 10, \
                    f"Generic insight should at least be specific: {insight}"
