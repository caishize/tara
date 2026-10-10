from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.curation.models import CuratedEvent
from src.modules.curation.services.curation_service import SecretaryCurationService
from src.modules.curation.services.storage_service import compute_event_stable_key


def _scalars_result(rows):
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = rows
    result.scalars.return_value = scalars
    return result


def _make_event(
    *,
    family_id,
    user_id,
    source_types,
    original_ids,
    title,
    event_type,
    start,
    end=None,
    trip_id=None,
    is_active=True,
    status="pending",
):
    return CuratedEvent(
        id=uuid4(),
        family_id=family_id,
        user_id=user_id,
        source_types=list(source_types),
        original_event_ids=list(original_ids),
        title=title,
        normalized_start=start,
        normalized_end=end,
        event_type=event_type,
        trip_id=trip_id,
        status=status,
        is_active=is_active,
        priority="normal",
        location="广州",
    )


@pytest.mark.asyncio
async def test_store_curated_events_reuses_inactive_row_by_stable_key():
    family_id = uuid4()
    user_id = uuid4()
    trip_id = uuid4()
    start = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 3, 4, 18, 0, tzinfo=timezone.utc)

    incoming = _make_event(
        family_id=family_id,
        user_id=user_id,
        source_types=["trip_plan"],
        original_ids=[str(trip_id)],
        title="广州美食文化之旅",
        event_type="travel",
        start=start,
        end=end,
        trip_id=trip_id,
    )
    stable_key = compute_event_stable_key(incoming)

    existing = _make_event(
        family_id=family_id,
        user_id=user_id,
        source_types=["trip_plan"],
        original_ids=[str(trip_id)],
        title="广州美食文化之旅",
        event_type="travel",
        start=start,
        end=end,
        trip_id=trip_id,
        is_active=False,
        status="cancelled",
    )
    existing.stable_key = stable_key

    db = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalars_result([existing]),  # stable key lookup
            _scalars_result([]),          # far-future safety lookup
        ]
    )

    service = SecretaryCurationService(db)
    service._load_mutable_events_for_diff = AsyncMock(return_value=[])
    service._link_events_to_trips = AsyncMock()
    service._populate_trip_context = AsyncMock()
    service._expire_pending_reschedule_actions = AsyncMock()
    service._dismiss_open_associations = AsyncMock()

    persisted = await service._store_curated_events(
        family_id=family_id,
        curated_events=[incoming],
        date_range=(start.date(), end.date()),
        failed_sources=[],
    )

    assert len(persisted) == 1
    assert persisted[0].id == existing.id
    assert existing.is_active is True
    assert db.add.call_count == 0


@pytest.mark.asyncio
async def test_store_curated_events_does_not_deactivate_failed_source_type():
    family_id = uuid4()
    user_id = uuid4()
    trip_id = uuid4()
    start = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 3, 4, 18, 0, tzinfo=timezone.utc)

    existing_trip = _make_event(
        family_id=family_id,
        user_id=user_id,
        source_types=["trip_plan"],
        original_ids=[str(trip_id)],
        title="广州美食文化之旅",
        event_type="travel",
        start=start,
        end=end,
        trip_id=trip_id,
        is_active=True,
        status="pending",
    )

    incoming_date = _make_event(
        family_id=family_id,
        user_id=user_id,
        source_types=["important_date"],
        original_ids=[str(uuid4())],
        title="元宵节",
        event_type="holiday",
        start=datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc),
        end=None,
        trip_id=None,
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _scalars_result([]),  # stable key lookup
            _scalars_result([]),  # far-future safety lookup
        ]
    )

    service = SecretaryCurationService(db)
    service._load_mutable_events_for_diff = AsyncMock(return_value=[existing_trip])
    service._link_events_to_trips = AsyncMock()
    service._populate_trip_context = AsyncMock()
    service._expire_pending_reschedule_actions = AsyncMock()
    service._dismiss_open_associations = AsyncMock()

    await service._store_curated_events(
        family_id=family_id,
        curated_events=[incoming_date],
        date_range=(start.date(), end.date()),
        failed_sources=["trip_plan"],
    )

    assert existing_trip.is_active is True
    assert existing_trip.status == "pending"
