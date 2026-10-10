from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.utils.timezone import DEFAULT_TIMEZONE, to_local_date
from src.modules.curation.models import CuratedEvent, EventAssociation, PreparationItem
from src.modules.member.models import Member, MemberRelation, RelationType
from src.modules.trip.models import TripPlan
from src.modules.views.services.event_detail_service import EventDetailService


@pytest.mark.asyncio
async def test_event_detail_uses_trip_plan_date_range_for_trip_event(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    trip_id = uuid4()

    # Deliberately keep curated event timestamp offset from trip_plan date.
    now = datetime.now(timezone.utc)
    curated_start = now + timedelta(days=1, hours=10)
    curated_end = curated_start + timedelta(hours=6)

    event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        trip_id=trip_id,
        original_event_ids=["trip-source"],
        source_types=["trip_plan"],
        title="厦门出行",
        normalized_start=curated_start,
        normalized_end=curated_end,
        location="厦门",
        event_type="travel",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    trip_plan = TripPlan(
        trip_id=trip_id,
        family_id=family_id,
        created_by=user_id,
        trip_name="厦门出行",
        destination="厦门",
        start_date=(now + timedelta(days=2)).date(),
        end_date=(now + timedelta(days=3)).date(),
        status="planning",
        category="personal",
        participants=[user_id],
    )
    db_session.add_all([event, trip_plan])
    await db_session.commit()

    service = EventDetailService(db_session)
    detail = await service.get_event_detail(
        event_id=event.id,
        family_id=family_id,
        user_id=user_id,
    )

    assert detail is not None
    assert detail.event.start_time is not None
    assert detail.event.end_time is not None
    assert to_local_date(detail.event.start_time, DEFAULT_TIMEZONE) == trip_plan.start_date
    assert to_local_date(detail.event.end_time, DEFAULT_TIMEZONE) == trip_plan.end_date


@pytest.mark.asyncio
async def test_event_detail_includes_nearby_derived_association_titles(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    now = datetime.now(timezone.utc)

    main_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["main-event"],
        source_types=["trip_plan"],
        title="揭阳春节之旅",
        normalized_start=now + timedelta(days=2),
        normalized_end=now + timedelta(days=4),
        location="揭阳",
        event_type="travel",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.95,
        priority="high",
        status="pending",
    )
    nearby_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["nearby-event"],
        source_types=["important_date"],
        title="春节",
        normalized_start=now + timedelta(days=3),
        normalized_end=now + timedelta(days=3, hours=1),
        location="揭阳",
        event_type="holiday",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    db_session.add_all([main_event, nearby_event])
    await db_session.flush()

    main_prep = PreparationItem(
        event_id=main_event.id,
        text="确认往返交通",
        source="ai",
        done=False,
        sort_order=0,
    )
    nearby_prep = PreparationItem(
        event_id=nearby_event.id,
        text="准备拜年红包",
        source="ai",
        done=False,
        sort_order=0,
    )
    db_session.add_all([main_prep, nearby_prep])
    await db_session.commit()

    service = EventDetailService(db_session)
    detail = await service.get_event_detail(
        event_id=main_event.id,
        family_id=family_id,
        user_id=user_id,
    )

    assert detail is not None
    assoc_titles = {assoc.title for assoc in detail.associations}
    assert "顺手把「春节」前的准备事项一起确认" in assoc_titles


@pytest.mark.asyncio
async def test_event_detail_humanizes_co_resident_family_association_copy(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    now = datetime.now(timezone.utc)

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
    relation = MemberRelation(
        family_id=family_id,
        from_member_id=user_id,
        to_member_id=spouse_id,
        relation_type=RelationType.SPOUSE,
        intimacy_level=9,
    )

    event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["event-source"],
        source_types=["trip_plan"],
        title="揭阳春节之旅",
        normalized_start=now + timedelta(days=2),
        normalized_end=now + timedelta(days=4),
        location="揭阳",
        event_type="travel",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.95,
        priority="high",
        status="pending",
    )
    db_session.add_all([self_member, spouse_member, relation, event])
    await db_session.flush()

    assoc = EventAssociation(
        family_id=family_id,
        source_event_id=event.id,
        target_id=str(spouse_id),
        target_type="person",
        association_type="person",
        title="返程时顺路探望深圳的家人和朋友",
        reason="index 1 和 2 合并，保留 priority 最高项",
        priority="strongly_recommend",
        confidence=0.9,
        is_dismissed=False,
        is_confirmed=False,
    )
    db_session.add(assoc)
    await db_session.commit()

    service = EventDetailService(db_session)
    detail = await service.get_event_detail(
        event_id=event.id,
        family_id=family_id,
        user_id=user_id,
    )

    assert detail is not None
    rewritten = next(item for item in detail.associations if item.target_type == "person")
    assert rewritten.title == "返程后给家里带份当地小礼物"
    assert "index" not in rewritten.reason.lower()
    assert "priority" not in rewritten.reason.lower()
