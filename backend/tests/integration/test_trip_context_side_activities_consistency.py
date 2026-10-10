"""Integration tests for trip detail side-activity consistency with kanban insights."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.modules.curation.models import CuratedEvent, EventAssociation
from src.modules.trip.models import TripPlan


@pytest.fixture(autouse=True)
def _force_dev_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "strict_auth_enabled", False)
    monkeypatch.setattr(settings, "environment", "development")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trip_detail_context_keeps_person_side_activities(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    trip_id = uuid4()
    now = datetime.now(timezone.utc)
    trip_start = date.today() + timedelta(days=2)
    trip_end = trip_start + timedelta(days=3)

    trip_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        trip_id=trip_id,
        original_event_ids=["trip-source"],
        source_types=["trip_plan"],
        title="揭阳春节之旅（初二至初五）",
        normalized_start=now + timedelta(days=2, hours=8),
        normalized_end=now + timedelta(days=5, hours=10),
        location="揭阳",
        event_type="travel",
        timeline_items=[],
        dedup_reason="integration_test",
        confidence=0.95,
        status="pending",
        priority="high",
    )
    trip_plan = TripPlan(
        trip_id=trip_id,
        family_id=family_id,
        created_by=user_id,
        trip_name="揭阳春节之旅（初二至初五）",
        destination="揭阳",
        start_date=trip_start,
        end_date=trip_end,
        status="planning",
        category="personal",
        participants=[user_id],
    )

    db_session.add_all([trip_event, trip_plan])
    await db_session.flush()

    assoc_person = EventAssociation(
        family_id=family_id,
        source_event_id=trip_event.id,
        target_id=str(uuid4()),
        target_type="person",
        association_type="person",
        title="在揭阳期间探望父母",
        reason="父母在揭阳，时间重合",
        priority="strongly_recommend",
        confidence=0.92,
        is_dismissed=False,
        is_confirmed=False,
    )
    assoc_task = EventAssociation(
        family_id=family_id,
        source_event_id=trip_event.id,
        target_id=str(uuid4()),
        target_type="task",
        association_type="semantic",
        title="确认返程时间",
        reason="返程节点影响家人探望安排",
        priority="convenient",
        confidence=0.85,
        is_dismissed=False,
        is_confirmed=False,
    )

    db_session.add_all([assoc_person, assoc_task])
    await db_session.commit()

    kanban_resp = await async_client.get("/api/v1/kanban")
    assert kanban_resp.status_code == 200
    kanban_data = kanban_resp.json()

    event_id = str(trip_event.id)
    event_insight = next(
        (
            item
            for item in kanban_data.get("insights", [])
            if item.get("action_data", {}).get("event_id") == event_id
        ),
        None,
    )
    assert event_insight is not None
    assert "在揭阳期间探望父母" in event_insight["content"]

    context_resp = await async_client.get(f"/api/v1/trips/plans/{trip_id}/context")
    assert context_resp.status_code == 200
    context_data = context_resp.json()
    context_side = context_data.get("side_activities", [])
    context_titles = {item["title"] for item in context_side}
    assert "在揭阳期间探望父母" in context_titles
    assert any(item.get("target_type") == "person" for item in context_side)

    detail_resp = await async_client.get(f"/api/v1/trips/plans/{trip_id}/detail")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    detail_context = detail_data.get("context") or {}
    detail_side = detail_context.get("side_activities", [])
    detail_titles = {item["title"] for item in detail_side}
    assert "在揭阳期间探望父母" in detail_titles
    assert any(item.get("target_type") == "person" for item in detail_side)
