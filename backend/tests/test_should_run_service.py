"""Tests for curation should-run decision logic."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.curation.models import CurationJob
from src.modules.curation.services.should_run_service import CurationShouldRunService
from src.modules.trip.models.trip_itinerary import TripItinerary
from src.modules.trip.models.trip_plan import TripPlan


def _make_family_id() -> uuid.UUID:
    return uuid.uuid4()


def _future_date(days: int) -> date:
    return date.today() + timedelta(days=days)


async def _create_trip_with_itinerary(
    db: AsyncSession,
    family_id: uuid.UUID,
    itinerary_updated_at: datetime,
    trip_updated_at: Optional[datetime] = None,
) -> TripPlan:
    created_by = uuid.uuid4()
    trip = TripPlan(
        family_id=family_id,
        created_by=created_by,
        destination="Hangzhou",
        start_date=_future_date(7),
        end_date=_future_date(9),
        status="planning",
        category="personal",
        participants=[created_by],
    )
    db.add(trip)
    await db.flush()
    if trip_updated_at is not None:
        trip.updated_at = trip_updated_at

    itinerary = TripItinerary(
        trip_id=trip.trip_id,
        day_number=1,
        schedule=[{"time": "09:00", "title": "West Lake"}],
        updated_at=itinerary_updated_at,
    )
    db.add(itinerary)
    await db.flush()
    return trip


async def _create_completed_job(
    db: AsyncSession,
    family_id: uuid.UUID,
    completed_at: datetime,
) -> None:
    job = CurationJob(
        family_id=family_id,
        trigger_type="scheduled",
        status="completed",
        started_at=completed_at - timedelta(minutes=1),
        completed_at=completed_at,
    )
    db.add(job)
    await db.flush()


@pytest.mark.asyncio
async def test_itinerary_updated_runs_when_itinerary_is_newer(db_session: AsyncSession):
    family_id = _make_family_id()
    now = datetime.now(timezone.utc)
    trip = await _create_trip_with_itinerary(db_session, family_id, now)
    await _create_completed_job(db_session, family_id, now - timedelta(minutes=5))
    await db_session.commit()

    service = CurationShouldRunService(db_session)
    decision = await service.evaluate(
        family_id=family_id,
        date_range=(date.today(), _future_date(14)),
        trigger_type="itinerary_updated",
        payload={"trip_id": str(trip.trip_id)},
    )

    assert decision.should_run is True
    assert decision.reason == "incremental_itinerary_changed"


@pytest.mark.asyncio
async def test_itinerary_updated_skips_when_signal_is_stale(db_session: AsyncSession):
    family_id = _make_family_id()
    now = datetime.now(timezone.utc)
    trip = await _create_trip_with_itinerary(
        db_session, family_id, now - timedelta(minutes=10)
    )
    await _create_completed_job(db_session, family_id, now - timedelta(minutes=1))
    await db_session.commit()

    service = CurationShouldRunService(db_session)
    decision = await service.evaluate(
        family_id=family_id,
        date_range=(date.today(), _future_date(14)),
        trigger_type="itinerary_updated",
        payload={"trip_id": str(trip.trip_id)},
    )

    assert decision.should_run is False
    assert decision.reason == "stale_incremental_itinerary_signal"


@pytest.mark.asyncio
async def test_scheduled_skips_when_no_signal_and_no_active_events(
    db_session: AsyncSession,
):
    family_id = _make_family_id()
    now = datetime.now(timezone.utc)
    await _create_completed_job(db_session, family_id, now - timedelta(minutes=30))
    await db_session.commit()

    service = CurationShouldRunService(db_session)
    decision = await service.evaluate(
        family_id=family_id,
        date_range=(date.today(), _future_date(14)),
        trigger_type="scheduled",
        payload=None,
    )

    assert decision.should_run is False
    assert decision.reason == "skip_no_active_events"


@pytest.mark.asyncio
async def test_scheduled_runs_when_only_itinerary_watermark_changes(
    db_session: AsyncSession,
):
    family_id = _make_family_id()
    now = datetime.now(timezone.utc)
    await _create_trip_with_itinerary(
        db_session,
        family_id,
        itinerary_updated_at=now - timedelta(minutes=1),
        trip_updated_at=now - timedelta(hours=2),
    )
    await _create_completed_job(db_session, family_id, now - timedelta(minutes=10))
    await db_session.commit()

    service = CurationShouldRunService(db_session)
    decision = await service.evaluate(
        family_id=family_id,
        date_range=(date.today(), _future_date(14)),
        trigger_type="scheduled",
        payload=None,
    )

    assert decision.should_run is True
    assert decision.reason == "source_watermark_changed"
    assert "itinerary" in decision.metadata.get("changed_sources", [])
