from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.curation.services.curation_service import SecretaryCurationService


def _make_plan(
    trip_id,
    destination: str = "广州",
    status: str = "planning",
):
    return SimpleNamespace(
        trip_id=trip_id,
        family_id=uuid4(),
        destination=destination,
        status=status,
        canonical_trip_id=None,
        is_active=True,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 3),
        description="",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        participants=[],
    )


@pytest.mark.asyncio
async def test_back_propagate_trip_merges_updates_trip_aliases():
    db = AsyncMock()
    service = SecretaryCurationService(db)

    t1 = uuid4()
    t2 = uuid4()
    family_id = uuid4()
    plan_primary = _make_plan(t1, destination="广州", status="confirmed")
    plan_secondary = _make_plan(t2, destination="广州圣心大教堂", status="planning")

    execute_result = MagicMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = [plan_primary, plan_secondary]
    execute_result.scalars.return_value = scalars_result
    db.execute = AsyncMock(return_value=execute_result)

    merged_event = SimpleNamespace(
        source_types=["trip_plan"],
        original_event_ids=[str(t1), str(t2)],
        trip_id=None,
    )
    alias_event = SimpleNamespace(
        source_types=["trip_plan"],
        original_event_ids=[str(t2)],
        trip_id=None,
    )

    with patch(
        "src.modules.trip.services.trip_service.TripService.merge_trips",
        new=AsyncMock(return_value={"success": True, "merged_count": 1}),
    ) as merge_mock:
        result = await service._back_propagate_trip_merges(
            family_id=family_id,
            curated_events=[merged_event, alias_event],
        )

    assert result[0].trip_id == t1
    assert result[1].trip_id == t1
    assert merge_mock.await_count == 1
