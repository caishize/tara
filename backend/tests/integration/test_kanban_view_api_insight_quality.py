"""Integration tests for /api/v1/kanban insight quality and time alignment."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.modules.curation.models import CuratedEvent, PreparationItem, EventAssociation
from src.modules.insight.models import MemoryInsight
from src.modules.trip.models import TripPlan


@pytest.fixture(autouse=True)
def _force_dev_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "strict_auth_enabled", False)
    monkeypatch.setattr(settings, "environment", "development")


def _parse_iso_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kanban_api_returns_actionable_insights_and_aligned_time(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)

    now = datetime.now(timezone.utc)
    trip_id = uuid4()
    trip_start_date = date.today() + timedelta(days=1)
    trip_end_date = trip_start_date + timedelta(days=1)

    trip_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        trip_id=trip_id,
        original_event_ids=["trip-1"],
        source_types=["trip_plan"],
        title="南澳岛周末二人世界之旅",
        normalized_start=now + timedelta(days=1, hours=10),
        normalized_end=now + timedelta(days=2, hours=6),
        location="南澳岛",
        event_type="travel",
        timeline_items=[],
        dedup_reason="integration_test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    date_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["date-1"],
        source_types=["calendar"],
        title="海边晚餐",
        normalized_start=now + timedelta(days=1, hours=14),
        normalized_end=now + timedelta(days=1, hours=16),
        location="南澳岛",
        event_type="appointment",
        timeline_items=[],
        dedup_reason="integration_test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    holiday_event = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=["holiday-1"],
        source_types=["important_date"],
        title="春节",
        normalized_start=now + timedelta(days=2, hours=9),
        normalized_end=now + timedelta(days=2, hours=10),
        location="深圳",
        event_type="holiday",
        timeline_items=[],
        dedup_reason="integration_test",
        confidence=0.9,
        priority="normal",
        status="pending",
    )
    trip_plan = TripPlan(
        trip_id=trip_id,
        family_id=family_id,
        created_by=user_id,
        trip_name="南澳岛周末二人世界之旅",
        destination="南澳岛",
        start_date=trip_start_date,
        end_date=trip_end_date,
        status="planning",
        category="personal",
        participants=[user_id],
    )
    redundant_insight = MemoryInsight(
        user_id=user_id,
        family_id=family_id,
        insight_type="reminder",
        title="您在南澳岛的计划",
        content="之前提到的计划：\n• 创建了南澳岛周末二人世界之旅",
        priority=5,
        urgency="normal",
        related_trip_ids=[trip_id],
        action_data={
            "location": "南澳岛",
            "trip_start_date": trip_start_date.isoformat(),
            "trip_end_date": trip_end_date.isoformat(),
        },
    )

    db_session.add_all([
        trip_event,
        date_event,
        holiday_event,
        trip_plan,
        redundant_insight,
    ])
    await db_session.flush()

    prep_item = PreparationItem(
        event_id=trip_event.id,
        text="确认返程交通",
        source="ai",
        done=False,
        sort_order=0,
    )
    assoc_item = EventAssociation(
        family_id=family_id,
        source_event_id=trip_event.id,
        target_id=str(uuid4()),
        target_type="task",
        association_type="semantic",
        title="海边晚餐后顺路买伴手礼",
        reason="地点与时间都接近，可一起安排。",
        priority="convenient",
        confidence=0.85,
        is_dismissed=False,
        is_confirmed=False,
    )
    db_session.add_all([prep_item, assoc_item])
    await db_session.commit()

    kanban_resp = await async_client.get("/api/v1/kanban")
    assert kanban_resp.status_code == 200
    kanban_data = kanban_resp.json()

    insight_titles = {item["title"] for item in kanban_data["insights"]}
    assert "您在南澳岛的计划" not in insight_titles

    event_id_to_insight = {
        item.get("action_data", {}).get("event_id"): item
        for item in kanban_data["insights"]
        if isinstance(item.get("action_data"), dict)
    }
    assert str(trip_event.id) in event_id_to_insight

    trip_insight = event_id_to_insight[str(trip_event.id)]
    assert "可顺便处理" in trip_insight["content"]

    trip_insight_time = _parse_iso_datetime(trip_insight["created_at"])
    cn_tz = ZoneInfo("Asia/Shanghai")
    assert trip_insight_time.astimezone(cn_tz).date() == trip_start_date

    detail_resp = await async_client.get(f"/api/v1/kanban/events/{trip_event.id}/context")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    detail_start = _parse_iso_datetime(detail_data["event"]["start_time"])
    detail_end = _parse_iso_datetime(detail_data["event"]["end_time"])

    assert detail_start.astimezone(cn_tz).date() == trip_start_date
    assert detail_end.astimezone(cn_tz).date() == trip_end_date
