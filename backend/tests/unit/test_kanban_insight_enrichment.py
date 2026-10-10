from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.curation.models import (
    CuratedEvent,
    EventAssociation,
    PreparationItem,
)
from src.modules.date_manager.models import ImportantDate
from src.modules.insight.models import Insight, MemoryInsight
from src.modules.member.models import Member, MemberRelation, RelationType
from src.modules.trip.models import TripPlan
from src.modules.views.services.kanban_service import KanbanService


@pytest.mark.asyncio
async def test_kanban_view_enriches_event_insights_and_filters_redundant_trip_reminder(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    trip_id = uuid4()

    now = datetime.now(timezone.utc)
    trip_start = now + timedelta(days=1)
    trip_end = now + timedelta(days=2)
    holiday_start = now + timedelta(days=3)

    trip_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        trip_id=trip_id,
        original_event_ids=["trip-source-1"],
        source_types=["trip_plan"],
        title="南澳岛周末二人世界之旅",
        normalized_start=trip_start,
        normalized_end=trip_end,
        location="南澳岛",
        event_type="travel",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    holiday_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["holiday-source-1"],
        source_types=["important_date"],
        title="春节",
        normalized_start=holiday_start,
        normalized_end=holiday_start + timedelta(hours=1),
        location="深圳",
        event_type="holiday",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    db_session.add_all([trip_event, holiday_event])
    trip_plan = TripPlan(
        trip_id=trip_id,
        family_id=family_id,
        created_by=user_id,
        trip_name="南澳岛周末二人世界之旅",
        destination="南澳岛",
        start_date=trip_start.date(),
        end_date=trip_end.date(),
        status="planning",
        category="personal",
        participants=[user_id],
    )
    db_session.add(trip_plan)
    await db_session.flush()

    prep_item = PreparationItem(
        event_id=trip_event.id,
        text="确认返程交通",
        source="ai",
        done=False,
        sort_order=0,
    )
    association = EventAssociation(
        family_id=family_id,
        source_event_id=trip_event.id,
        target_id=str(uuid4()),
        target_type="task",
        association_type="semantic",
        title="了解春节深圳特别活动",
        reason="同一时间段可顺便处理",
        priority="convenient",
        confidence=0.8,
        is_dismissed=False,
        is_confirmed=False,
    )
    redundant_trip_insight = MemoryInsight(
        user_id=user_id,
        family_id=family_id,
        insight_type="reminder",
        title="您在南澳岛的计划",
        content="之前提到的计划：\n• 创建了南澳岛周末二人世界之旅",
        priority=5,
        urgency="normal",
        related_trip_ids=[trip_id],
        action_options=["view_details", "set_reminder", "ignore"],
        action_data={
            "location": "南澳岛",
            "trip_start_date": trip_start.date().isoformat(),
            "trip_end_date": trip_end.date().isoformat(),
        },
    )
    db_session.add_all([prep_item, association, redundant_trip_insight])
    await db_session.commit()

    service = KanbanService(db_session)
    response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )

    insight_titles = {ins.title for ins in response.insights}
    assert "您在南澳岛的计划" not in insight_titles

    event_id_map = {
        (ins.action_data or {}).get("event_id"): ins
        for ins in response.insights
        if isinstance(ins.action_data, dict)
    }
    assert str(trip_event.id) in event_id_map
    # Common-sense holiday cards without concrete prep/associations are suppressed.
    assert str(holiday_event.id) not in event_id_map

    trip_insight = event_id_map[str(trip_event.id)]
    # The trip event is in needs_preparation (has pending prep items),
    # so prep items are suppressed in the insight card to avoid duplication
    # with the checkbox section.  Only association content remains.
    assert "建议先完成" not in trip_insight.content
    assert "可顺便处理" in trip_insight.content


@pytest.mark.asyncio
async def test_kanban_view_uses_event_reference_time_for_insight_display(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    reference_date = date.today() + timedelta(days=5)

    trip_start_dt = datetime.combine(reference_date, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    insight = Insight(
        user_id=user_id,
        family_id=family_id,
        insight_type="reminder",
        title="行程提醒",
        content="请提前准备",
        importance=50,
        urgency=50,
        status="pending",
        source_context={
            "location": "深圳",
            "trip_start_date": reference_date.isoformat(),
        },
        created_at=trip_start_dt,
    )
    db_session.add(insight)
    await db_session.commit()

    service = KanbanService(db_session)
    response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )

    matched = next((ins for ins in response.insights if ins.id == str(insight.id)), None)
    assert matched is not None, "Insight should appear in kanban response"
    assert matched.created_at is not None
    assert matched.created_at.date() == reference_date


@pytest.mark.asyncio
async def test_kanban_hides_stale_event_context_insight_without_action_anchor(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    now = datetime.now(timezone.utc)

    holiday_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["holiday-stale-insight-source"],
        source_types=["important_date"],
        title="除夕",
        normalized_start=now + timedelta(days=1),
        normalized_end=now + timedelta(days=1, hours=1),
        location="深圳",
        event_type="holiday",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    db_session.add(holiday_event)
    await db_session.flush()

    stale_event_context = MemoryInsight(
        user_id=user_id,
        family_id=family_id,
        insight_type="reminder",
        title="除夕与春节的关联提醒",
        content="与春节时间接近，建议统一准备。",
        priority=9,
        urgency="normal",
        action_data={
            "type": "event_context",
            "event_id": str(holiday_event.id),
            "event_start_at": holiday_event.normalized_start.isoformat(),
            "pending_preparation_count": 0,
            "association_count": 1,
        },
        status="pending",
    )
    db_session.add(stale_event_context)
    await db_session.commit()

    service = KanbanService(db_session)
    response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )

    insight_ids = {ins.id for ins in response.insights}
    assert str(stale_event_context.id) not in insight_ids


@pytest.mark.asyncio
async def test_kanban_view_derives_cross_event_insight_when_explicit_links_missing(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    trip_id = uuid4()

    now = datetime.now(timezone.utc)
    trip_start = now + timedelta(days=1)
    holiday_start = now + timedelta(days=2)

    trip_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        trip_id=trip_id,
        original_event_ids=["trip-source-2"],
        source_types=["trip_plan"],
        title="深圳周末出行",
        normalized_start=trip_start,
        normalized_end=trip_start + timedelta(hours=8),
        location="深圳",
        event_type="travel",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    holiday_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["holiday-source-2"],
        source_types=["important_date"],
        title="元宵节",
        normalized_start=holiday_start,
        normalized_end=holiday_start + timedelta(hours=1),
        location="深圳",
        event_type="holiday",
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
        trip_name="深圳周末出行",
        destination="深圳",
        start_date=trip_start.date(),
        end_date=trip_start.date(),
        status="planning",
        category="personal",
        participants=[user_id],
    )
    db_session.add_all([trip_event, holiday_event, trip_plan])
    await db_session.commit()

    service = KanbanService(db_session)
    response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )

    # Nearby timing/location overlap alone is not enough to produce a card.
    event_ids = {
        (ins.action_data or {}).get("event_id")
        for ins in response.insights
        if isinstance(ins.action_data, dict)
    }
    assert str(trip_event.id) not in event_ids
    assert str(holiday_event.id) not in event_ids


@pytest.mark.asyncio
async def test_kanban_view_skips_holiday_temporal_chain_association(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    now = datetime.now(timezone.utc)

    eve_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["eve-source"],
        source_types=["important_date"],
        title="除夕",
        normalized_start=now + timedelta(days=1),
        normalized_end=now + timedelta(days=1, hours=1),
        location="深圳",
        event_type="holiday",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    spring_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["spring-source"],
        source_types=["important_date"],
        title="春节",
        normalized_start=now + timedelta(days=2),
        normalized_end=now + timedelta(days=2, hours=1),
        location="深圳",
        event_type="holiday",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    db_session.add_all([eve_event, spring_event])
    await db_session.flush()

    temporal_chain_assoc = EventAssociation(
        family_id=family_id,
        source_event_id=spring_event.id,
        target_id=str(uuid4()),
        target_type="task",
        association_type="temporal",
        title="与「除夕」时间接近，建议统一准备",
        reason="日期紧邻，可一起安排。",
        priority="convenient",
        confidence=0.9,
        is_dismissed=False,
        is_confirmed=False,
    )
    db_session.add(temporal_chain_assoc)
    await db_session.commit()

    service = KanbanService(db_session)
    response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )

    event_ids = {
        (ins.action_data or {}).get("event_id")
        for ins in response.insights
        if isinstance(ins.action_data, dict)
    }
    assert str(spring_event.id) not in event_ids


@pytest.mark.asyncio
async def test_low_priority_solar_term_respects_user_preference_signals(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    now = datetime.now(timezone.utc)

    solar_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["solar-term-source"],
        source_types=["important_date"],
        title="雨水",
        normalized_start=now + timedelta(days=2),
        normalized_end=now + timedelta(days=2, hours=1),
        location="深圳",
        event_type="solar_term",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="low",
        status="pending",
    )
    db_session.add(solar_event)
    await db_session.flush()

    generic_holiday = ImportantDate(
        family_id=family_id,
        member_id=None,
        created_by=user_id,
        title="春节",
        date_type="holiday",
        solar_date=(now + timedelta(days=3)).date(),
        is_recurring=False,
        importance_level=5,
        source="manual",
    )
    db_session.add(generic_holiday)
    await db_session.flush()

    weak_assoc = EventAssociation(
        family_id=family_id,
        source_event_id=solar_event.id,
        target_id=str(generic_holiday.id),
        target_type="date",
        association_type="temporal",
        title="与春节时间接近",
        reason="节日彼此接近",
        priority="convenient",
        confidence=0.7,
        is_dismissed=False,
        is_confirmed=False,
    )
    db_session.add(weak_assoc)
    await db_session.commit()

    service = KanbanService(db_session)
    no_pref_response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )
    assert str(solar_event.id) not in {event.id for event in no_pref_response.this_week}

    custom_preference_date = ImportantDate(
        family_id=family_id,
        member_id=None,
        created_by=user_id,
        title="我的雨水记录",
        date_type="solar_term",
        solar_date=(now + timedelta(days=5)).date(),
        is_recurring=False,
        importance_level=7,
        source="manual",
    )
    db_session.add(custom_preference_date)
    await db_session.commit()

    with_pref_response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )
    assert str(solar_event.id) in {event.id for event in with_pref_response.this_week}


@pytest.mark.asyncio
async def test_kanban_drops_common_sense_holiday_chain_without_actions(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    now = datetime.now(timezone.utc)

    chuxi = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["holiday-chuxi-noop"],
        source_types=["important_date"],
        title="除夕",
        normalized_start=now + timedelta(days=1),
        normalized_end=now + timedelta(days=1, hours=1),
        location="深圳",
        event_type="holiday",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    spring = ImportantDate(
        family_id=family_id,
        member_id=None,
        created_by=user_id,
        title="春节",
        date_type="holiday",
        solar_date=(now + timedelta(days=2)).date(),
        is_recurring=False,
        importance_level=5,
        source="manual",
    )
    db_session.add_all([chuxi, spring])
    await db_session.flush()

    assoc = EventAssociation(
        family_id=family_id,
        source_event_id=chuxi.id,
        target_id=str(spring.id),
        target_type="date",
        association_type="temporal",
        title="除夕与春节时间接近",
        reason="建议统一准备",
        priority="convenient",
        confidence=0.8,
        is_dismissed=False,
        is_confirmed=False,
    )
    db_session.add(assoc)
    await db_session.commit()

    service = KanbanService(db_session)
    response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )

    event_ids = {
        (ins.action_data or {}).get("event_id")
        for ins in response.insights
        if isinstance(ins.action_data, dict)
    }
    assert str(chuxi.id) not in event_ids


@pytest.mark.asyncio
async def test_kanban_prefers_generated_event_context_over_stale_db_insight(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    now = datetime.now(timezone.utc)

    trip_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["trip-source-stale-check"],
        source_types=["trip_plan"],
        title="揭阳春节之旅（初二至初五）",
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
    db_session.add(trip_event)
    await db_session.flush()

    assoc = EventAssociation(
        family_id=family_id,
        source_event_id=trip_event.id,
        target_id=str(uuid4()),
        target_type="person",
        association_type="person",
        title="在揭阳期间探望父母",
        reason="父母在揭阳",
        priority="strongly_recommend",
        confidence=0.9,
        is_dismissed=False,
        is_confirmed=False,
    )
    stale_db_insight = MemoryInsight(
        user_id=user_id,
        family_id=family_id,
        insight_type="reminder",
        title="揭阳春节之旅（旧）",
        content="旧洞察：只提示节气",
        priority=10,
        urgency="high",
        action_data={
            "event_id": str(trip_event.id),
            "event_start_at": (now + timedelta(days=2)).isoformat(),
        },
        status="pending",
    )
    db_session.add_all([assoc, stale_db_insight])
    await db_session.commit()

    service = KanbanService(db_session)
    response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )

    event_insight = next(
        insight for insight in response.insights
        if (insight.action_data or {}).get("event_id") == str(trip_event.id)
    )
    assert event_insight.id.startswith("event-context:")
    assert "在揭阳期间探望父母" in event_insight.content


@pytest.mark.asyncio
async def test_kanban_consolidates_nearby_holiday_like_insights(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    now = datetime.now(timezone.utc)

    chuxi_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["holiday-chuxi"],
        source_types=["important_date"],
        title="除夕",
        normalized_start=now + timedelta(days=1),
        normalized_end=now + timedelta(days=1, hours=1),
        location="深圳",
        event_type="holiday",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    chunjie_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["holiday-chunjie"],
        source_types=["important_date"],
        title="春节",
        normalized_start=now + timedelta(days=2),
        normalized_end=now + timedelta(days=2, hours=1),
        location="深圳",
        event_type="holiday",
        timeline_items=[],
        dedup_reason="test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    db_session.add_all([chuxi_event, chunjie_event])
    await db_session.flush()

    chuxi_prep = PreparationItem(
        event_id=chuxi_event.id,
        text="确认除夕晚餐安排",
        source="ai",
        done=False,
        sort_order=0,
    )
    chunjie_prep = PreparationItem(
        event_id=chunjie_event.id,
        text="准备春节拜年礼物",
        source="ai",
        done=False,
        sort_order=0,
    )
    db_session.add_all([chuxi_prep, chunjie_prep])
    await db_session.commit()

    service = KanbanService(db_session)
    response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )

    # Both holiday events have prep items and are in needs_preparation,
    # so their prep items are suppressed in insights (cross-section dedup).
    # Since they have no associations, no insight cards are generated at all.
    clustered = [
        insight for insight in response.insights
        if (insight.action_data or {}).get("clustered_event_count", 0) >= 2
    ]
    assert len(clustered) == 0

    # However, the events should appear in the needs_preparation section
    prep_ids = {ev.id for ev in response.needs_preparation}
    assert str(chuxi_event.id) in prep_ids
    assert str(chunjie_event.id) in prep_ids


@pytest.mark.asyncio
async def test_kanban_uses_co_resident_family_wording_for_person_association(
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
    spouse_relation = MemberRelation(
        family_id=family_id,
        from_member_id=user_id,
        to_member_id=spouse_id,
        relation_type=RelationType.SPOUSE,
        intimacy_level=9,
    )

    trip_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["trip-source-co-resident"],
        source_types=["trip_plan"],
        title="揭阳春节之旅（初二至初五）",
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
    db_session.add_all([self_member, spouse_member, spouse_relation, trip_event])
    await db_session.flush()

    assoc = EventAssociation(
        family_id=family_id,
        source_event_id=trip_event.id,
        target_id=str(spouse_id),
        target_type="person",
        association_type="person",
        title="返程时顺路探望深圳的家人和朋友",
        reason=(
            "index 4（Grace）涉及深圳熟人探望，priority更高"
            "（strongly_recommend）"
        ),
        priority="strongly_recommend",
        confidence=0.92,
        is_dismissed=False,
        is_confirmed=False,
    )
    db_session.add(assoc)
    await db_session.commit()

    service = KanbanService(db_session)
    response = await service.get_kanban_view(
        family_id=family_id,
        user_id=user_id,
        limit=20,
    )

    event_insight = next(
        insight for insight in response.insights
        if (insight.action_data or {}).get("event_id") == str(trip_event.id)
    )
    assert "返程后给家里带份当地小礼物" in event_insight.content
    assert "探望深圳的家人和朋友" not in event_insight.content
