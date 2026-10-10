from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.curation.models import CuratedEvent, EventAssociation, PreparationItem
from src.modules.member.models import Member, MemberRelation, RelationType
from src.modules.trip.models import TripPlan
from src.modules.trip.services.trip_detail_context_service import TripDetailContextService


@pytest.mark.asyncio
async def test_trip_detail_context_includes_person_side_activities(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    trip_id = uuid4()

    trip = TripPlan(
        trip_id=trip_id,
        family_id=family_id,
        created_by=user_id,
        trip_name="揭阳春节之旅",
        destination="揭阳",
        start_date=date.today() + timedelta(days=2),
        end_date=date.today() + timedelta(days=5),
        status="planning",
        category="personal",
        participants=[user_id],
    )
    event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        trip_id=trip_id,
        original_event_ids=["trip-source"],
        source_types=["trip_plan"],
        title="揭阳春节之旅（初二至初五）",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=2),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=5),
        location="揭阳",
        event_type="travel",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        status="pending",
        priority="normal",
    )

    db_session.add_all([trip, event])
    await db_session.flush()

    assoc_person = EventAssociation(
        family_id=family_id,
        source_event_id=event.id,
        target_id=str(uuid4()),
        target_type="person",
        association_type="person",
        title="在揭阳期间探望父母",
        reason="父母在揭阳，行程重合",
        priority="strongly_recommend",
        confidence=0.9,
        is_dismissed=False,
        is_confirmed=False,
    )
    assoc_task = EventAssociation(
        family_id=family_id,
        source_event_id=event.id,
        target_id=str(uuid4()),
        target_type="task",
        association_type="semantic",
        title="了解春节特别活动",
        reason="与节日安排相关",
        priority="convenient",
        confidence=0.8,
        is_dismissed=False,
        is_confirmed=False,
    )

    db_session.add_all([assoc_person, assoc_task])
    await db_session.commit()

    service = TripDetailContextService(db_session)
    context = await service.build_context(trip, family_id)

    titles = {item.title for item in context.side_activities}
    assert "在揭阳期间探望父母" in titles
    assert "了解春节特别活动" in titles
    person_item = next(item for item in context.side_activities if item.title == "在揭阳期间探望父母")
    assert person_item.target_type == "person"


@pytest.mark.asyncio
async def test_trip_detail_context_humanizes_internal_reason_for_co_resident_family(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    trip_id = uuid4()

    self_member = Member(
        id=user_id,
        family_id=family_id,
        created_by=user_id,
        name="Darwin",
        locations={"home": {"city": "深圳", "address": "深圳福田区山语清晖花园"}},
        default_location_type="home",
    )
    spouse_id = uuid4()
    spouse_member = Member(
        id=spouse_id,
        family_id=family_id,
        created_by=user_id,
        name="Grace",
        locations={"home": {"city": "深圳", "address": "深圳福田区山语清晖花园"}},
        default_location_type="home",
    )
    spouse_relation = MemberRelation(
        family_id=family_id,
        from_member_id=user_id,
        to_member_id=spouse_id,
        relation_type=RelationType.SPOUSE,
        intimacy_level=9,
    )

    trip = TripPlan(
        trip_id=trip_id,
        family_id=family_id,
        created_by=user_id,
        trip_name="揭阳春节之旅",
        destination="揭阳",
        start_date=date.today() + timedelta(days=2),
        end_date=date.today() + timedelta(days=5),
        status="planning",
        category="personal",
        participants=[user_id],
    )
    event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        trip_id=trip_id,
        original_event_ids=["trip-source"],
        source_types=["trip_plan"],
        title="揭阳春节之旅（初二至初五）",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=2),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=5),
        location="揭阳",
        event_type="travel",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        status="pending",
        priority="normal",
    )

    db_session.add_all([self_member, spouse_member, spouse_relation, trip, event])
    await db_session.flush()

    assoc_person = EventAssociation(
        family_id=family_id,
        source_event_id=event.id,
        target_id=str(spouse_id),
        target_type="person",
        association_type="person",
        title="返程时顺路探望深圳的家人和朋友",
        reason=(
            "index 4（Grace）涉及深圳熟人探望，priority更高"
            "（strongly_recommend）"
        ),
        priority="strongly_recommend",
        confidence=0.9,
        is_dismissed=False,
        is_confirmed=False,
    )

    db_session.add(assoc_person)
    await db_session.commit()

    service = TripDetailContextService(db_session)
    context = await service.build_context(trip, family_id)

    titles = {item.title for item in context.side_activities}
    assert "返程后给家里带份当地小礼物" in titles
    rewritten_item = next(item for item in context.side_activities if item.title == "返程后给家里带份当地小礼物")
    assert "index" not in (rewritten_item.reason or "").lower()
    assert "priority" not in (rewritten_item.reason or "").lower()


@pytest.mark.asyncio
async def test_trip_detail_context_falls_back_to_creator_when_participants_empty(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    trip_id = uuid4()

    self_member = Member(
        id=user_id,
        family_id=family_id,
        created_by=user_id,
        name="Darwin",
    )
    trip = TripPlan(
        trip_id=trip_id,
        family_id=family_id,
        created_by=user_id,
        trip_name="揭阳春节之旅",
        destination="揭阳",
        start_date=date.today() + timedelta(days=2),
        end_date=date.today() + timedelta(days=5),
        status="planning",
        category="personal",
        participants=[],
    )

    db_session.add_all([self_member, trip])
    await db_session.commit()

    service = TripDetailContextService(db_session)
    context = await service.build_context(trip, family_id)

    assert len(context.participants) == 1
    assert context.participants[0].id == user_id
    assert context.participants[0].name == "Darwin"


@pytest.mark.asyncio
async def test_trip_detail_context_insight_mentions_children(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    child_id = uuid4()
    trip_id = uuid4()

    self_member = Member(
        id=user_id,
        family_id=family_id,
        created_by=user_id,
        name="Darwin",
    )
    child_member = Member(
        id=child_id,
        family_id=family_id,
        created_by=user_id,
        name="小宇",
        age=5,
    )
    child_relation = MemberRelation(
        family_id=family_id,
        from_member_id=user_id,
        to_member_id=child_id,
        relation_type=RelationType.SON,
        intimacy_level=9,
    )
    trip = TripPlan(
        trip_id=trip_id,
        family_id=family_id,
        created_by=user_id,
        trip_name="揭阳春节之旅",
        destination="揭阳",
        start_date=date.today() + timedelta(days=2),
        end_date=date.today() + timedelta(days=5),
        status="planning",
        category="personal",
        participants=[user_id, child_id],
    )

    db_session.add_all([self_member, child_member, child_relation, trip])
    await db_session.commit()

    service = TripDetailContextService(db_session)
    context = await service.build_context(trip, family_id)

    assert context.insight_text is not None
    assert "有儿童同行" in context.insight_text
    assert "小宇" in context.insight_text


@pytest.mark.asyncio
async def test_trip_detail_context_prefers_active_event_with_pending_preparation_items(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    trip_id = uuid4()

    trip = TripPlan(
        trip_id=trip_id,
        family_id=family_id,
        created_by=user_id,
        trip_name="广州美食文化之旅",
        destination="广州",
        start_date=date.today() + timedelta(days=3),
        end_date=date.today() + timedelta(days=6),
        status="planning",
        category="personal",
        participants=[user_id],
    )

    active_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        trip_id=trip_id,
        original_event_ids=["trip-source-active"],
        source_types=["trip_plan"],
        title="广州美食文化之旅",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=3),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=6),
        location="广州",
        event_type="travel",
        timeline_items=[],
        dedup_reason="active",
        confidence=0.9,
        status="pending",
        priority="normal",
        is_active=True,
    )

    # Simulate a newer but inactive historical row for the same trip_id.
    stale_inactive_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        trip_id=trip_id,
        original_event_ids=["trip-source-stale"],
        source_types=["trip_plan"],
        title="广州美食文化之旅（旧）",
        normalized_start=datetime.now(timezone.utc) + timedelta(days=5),
        normalized_end=datetime.now(timezone.utc) + timedelta(days=6),
        location="广州",
        event_type="travel",
        timeline_items=[],
        dedup_reason="stale",
        confidence=0.7,
        status="pending",
        priority="normal",
        is_active=False,
    )

    db_session.add_all([trip, active_event, stale_inactive_event])
    await db_session.flush()

    prep = PreparationItem(
        event_id=active_event.id,
        key=uuid4(),
        text="预订返程交通",
        source="ai",
        done=False,
        sort_order=0,
    )
    db_session.add(prep)
    await db_session.commit()

    service = TripDetailContextService(db_session)
    context = await service.build_context(trip, family_id)

    assert context.curated_event_id == active_event.id
    assert len(context.preparation_items) == 1
    assert context.preparation_items[0].text == "预订返程交通"
    assert context.preparation_items[0].done is False
