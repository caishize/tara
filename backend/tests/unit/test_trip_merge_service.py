from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.trip.services.trip_service import TripService


def _make_trip(
    destination: str,
    start: date,
    end: date,
    participants=None,
) -> SimpleNamespace:
    return SimpleNamespace(
        trip_id=uuid4(),
        destination=destination,
        start_date=start,
        end_date=end,
        participants=list(participants or []),
        canonical_trip_id=None,
        is_active=True,
        status="planning",
        extra_data={},
        updated_at=None,
    )


@pytest.mark.asyncio
async def test_merge_trips_marks_secondary_as_superseded_and_expands_primary_dates():
    db = AsyncMock()
    service = TripService(db)

    user_a = uuid4()
    user_b = uuid4()
    primary = _make_trip("广州", date(2026, 3, 2), date(2026, 3, 3), [user_a])
    secondary = _make_trip("广州圣心大教堂", date(2026, 3, 1), date(2026, 3, 4), [user_b])
    family_id = uuid4()

    primary_result = MagicMock()
    primary_result.scalar_one_or_none.return_value = primary

    secondary_result = MagicMock()
    secondary_scalars = MagicMock()
    secondary_scalars.all.return_value = [secondary]
    secondary_result.scalars.return_value = secondary_scalars

    db.execute = AsyncMock(side_effect=[primary_result, secondary_result, MagicMock()])
    db.flush = AsyncMock()

    result = await service.merge_trips(
        family_id=family_id,
        primary_trip_id=primary.trip_id,
        merge_trip_ids=[secondary.trip_id],
        reason="semantic_merge",
    )

    assert result["success"] is True
    assert result["merged_count"] == 1
    assert primary.start_date == date(2026, 3, 1)
    assert primary.end_date == date(2026, 3, 4)
    assert set(primary.participants) == {user_a, user_b}

    assert secondary.canonical_trip_id == primary.trip_id
    assert secondary.is_active is False
    assert secondary.extra_data.get("superseded_by_trip_id") == str(primary.trip_id)
    assert secondary.extra_data.get("superseded_reason") == "semantic_merge"
    assert db.flush.called


@pytest.mark.asyncio
async def test_merge_trips_rejects_empty_merge_list():
    db = AsyncMock()
    service = TripService(db)

    result = await service.merge_trips(
        family_id=uuid4(),
        primary_trip_id=uuid4(),
        merge_trip_ids=[],
    )
    assert result["success"] is False
