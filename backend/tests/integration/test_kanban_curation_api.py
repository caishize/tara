"""Integration tests for kanban curation trigger/status APIs."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.modules.curation.models import CurationJob, CuratedEvent, EventAssociation
from src.modules.curation.services.curation_service import SecretaryCurationService
from src.modules.curation.services.event_type_utils import normalize_event_type
from src.modules.date_manager.models import ImportantDate
from src.modules.member.models import User
from src.modules.memory.models import ConversationMemory, MemoryStatus, MemoryType
from src.modules.trip.models import TripPlan


@pytest.fixture(autouse=True)
def _force_dev_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "strict_auth_enabled", False)
    monkeypatch.setattr(settings, "environment", "development")


async def _seed_curation_sources(
    db_session: AsyncSession,
    *,
    family_id: UUID,
    user_id: UUID,
) -> None:
    today = date.today()

    user = User(
        id=user_id,
        family_id=family_id,
        username="integration_user",
        email="integration_user@test.local",
        password_hash="fakehash",
    )
    db_session.add(user)

    trip = TripPlan(
        family_id=family_id,
        created_by=user_id,
        trip_name="上海客户拜访",
        destination="上海",
        start_date=today + timedelta(days=1),
        end_date=today + timedelta(days=2),
        status="planning",
        category="business",
        participants=[user_id],
    )
    db_session.add(trip)

    important_date = ImportantDate(
        family_id=family_id,
        created_by=user_id,
        title="妈妈生日",
        date_type="birthday",
        solar_date=today + timedelta(days=3),
        is_recurring=False,
        source="manual",
    )
    db_session.add(important_date)

    schedule_memory = ConversationMemory(
        user_id=user_id,
        family_id=family_id,
        memory_type=MemoryType.SCHEDULE.value,
        content="明天要去牙科复诊",
        summary="牙科复诊",
        entities={"time_hint": "明天"},
        status=MemoryStatus.ACTIVE.value,
        importance=7,
    )
    db_session.add(schedule_memory)

    await db_session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_request_curation_creates_pending_job_and_dispatches_arguments(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def _fake_trigger(
        family_id: UUID,
        trigger_type: str = "event",
        respect_cooldown: bool = True,
        payload: dict | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        existing_job_id: UUID | None = None,
    ) -> bool:
        captured["family_id"] = family_id
        captured["trigger_type"] = trigger_type
        captured["respect_cooldown"] = respect_cooldown
        captured["payload"] = payload
        captured["start_date"] = start_date
        captured["end_date"] = end_date
        captured["existing_job_id"] = existing_job_id
        return True

    start_date = date.today() + timedelta(days=1)
    end_date = start_date + timedelta(days=7)

    monkeypatch.setattr(
        "src.modules.curation.tasks.trigger_curation_async",
        _fake_trigger,
    )

    response = await async_client.post(
        f"/api/v1/kanban/request-curation?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["message"] == "Curation job started"

    job_id = UUID(payload["job_id"])
    job = await db_session.get(CurationJob, job_id)
    assert job is not None
    assert job.status == "pending"
    assert job.trigger_type == "manual"
    assert job.date_range_start == start_date
    assert job.date_range_end == end_date

    assert captured["trigger_type"] == "manual"
    assert captured["respect_cooldown"] is False
    assert captured["start_date"] == start_date
    assert captured["end_date"] == end_date
    assert captured["existing_job_id"] == job_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_request_curation_worker_reuses_job_and_persists_curated_output(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)

    await _seed_curation_sources(
        db_session,
        family_id=family_id,
        user_id=user_id,
    )

    start_date = date.today()
    end_date = start_date + timedelta(days=7)

    monkeypatch.setattr(
        "src.modules.curation.tasks.trigger_curation_async",
        lambda *_args, **_kwargs: True,
    )

    request_response = await async_client.post(
        f"/api/v1/kanban/request-curation?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
    )
    assert request_response.status_code == 200
    request_body = request_response.json()
    job_id = UUID(request_body["job_id"])

    async def _fake_semantic_dedup_and_normalize(
        self,
        family_id: UUID,
        raw_events,
        user_id: UUID | None = None,
        family_prefs=None,
    ):
        curated_events = []
        for raw in raw_events:
            normalized_type = normalize_event_type(raw.event_type, default="appointment")
            curated_events.append(
                CuratedEvent(
                    family_id=family_id,
                    user_id=user_id,
                    original_event_ids=[raw.id],
                    source_types=[raw.source_type],
                    title=raw.title,
                    normalized_start=raw.start_time,
                    normalized_end=raw.end_time or (raw.start_time + timedelta(hours=1)),
                    location=raw.location,
                    event_type=normalized_type,
                    timeline_items=[],
                    dedup_reason="integration_fake_semantic",
                    confidence=0.95,
                    priority="normal",
                    status="pending",
                )
            )
        return curated_events, []

    async def _fake_detect_and_resolve_conflicts(self, family_id, curated_events, user_id, family_prefs=None):
        return 0

    async def _fake_discover_associations(self, family_id, curated_events, date_range, family_prefs=None):
        return []

    monkeypatch.setattr(
        SecretaryCurationService,
        "_semantic_dedup_and_normalize",
        _fake_semantic_dedup_and_normalize,
    )
    monkeypatch.setattr(
        SecretaryCurationService,
        "_detect_and_resolve_conflicts",
        _fake_detect_and_resolve_conflicts,
    )
    monkeypatch.setattr(
        SecretaryCurationService,
        "_discover_associations",
        _fake_discover_associations,
    )

    service = SecretaryCurationService(db_session)
    result = await service.curate_family_events(
        family_id=family_id,
        date_range=(start_date, end_date),
        trigger_type="manual",
        user_id=user_id,
        existing_job_id=job_id,
    )

    assert result.job_id == job_id
    assert result.events_processed == 3
    assert result.events_curated == 3
    assert result.associations_created == 0

    status_response = await async_client.get(f"/api/v1/kanban/curation-status/{job_id}")
    assert status_response.status_code == 200
    status_body = status_response.json()

    assert status_body["status"] == "completed"
    assert status_body["trigger_type"] == "manual"
    assert status_body["events_processed"] == 3
    assert status_body["events_curated"] == 3
    assert status_body["associations_created"] == 0
    assert status_body["error_message"] is None

    events_result = await db_session.execute(
        select(CuratedEvent).where(CuratedEvent.family_id == family_id)
    )
    curated_events = events_result.scalars().all()

    assert len(curated_events) == 3
    event_types = {event.event_type for event in curated_events}
    assert "business_trip" in event_types
    assert "birthday" in event_types
    assert "appointment" in event_types


@pytest.mark.integration
@pytest.mark.asyncio
async def test_curation_association_source_ids_remain_non_null_when_reusing_existing_event(
    db_session: AsyncSession,
    test_family_id: str,
    test_user_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family_id = UUID(test_family_id)
    user_id = UUID(test_user_id)
    start_date = date.today()
    end_date = start_date + timedelta(days=7)

    await _seed_curation_sources(
        db_session,
        family_id=family_id,
        user_id=user_id,
    )

    important_date_result = await db_session.execute(
        select(ImportantDate).where(
            ImportantDate.family_id == family_id,
            ImportantDate.title == "妈妈生日",
        )
    )
    important_date = important_date_result.scalar_one()

    existing_curated = CuratedEvent(
        family_id=family_id,
        user_id=user_id,
        original_event_ids=[str(important_date.id)],
        source_types=["important_date"],
        title=important_date.title,
        normalized_start=datetime.combine(
            important_date.solar_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        ),
        normalized_end=datetime.combine(
            important_date.solar_date,
            datetime.max.time(),
            tzinfo=timezone.utc,
        ),
        event_type="birthday",
        timeline_items=[],
        dedup_reason="preexisting-for-reuse",
        confidence=0.95,
        priority="high",
        status="pending",
    )
    db_session.add(existing_curated)
    await db_session.commit()

    async def _fake_semantic_dedup_and_normalize(
        self,
        family_id: UUID,
        raw_events,
        user_id: UUID | None = None,
        family_prefs=None,
    ):
        curated_events = []
        for raw in raw_events:
            normalized_type = normalize_event_type(raw.event_type, default="appointment")
            curated_events.append(
                CuratedEvent(
                    family_id=family_id,
                    user_id=user_id,
                    original_event_ids=[raw.id],
                    source_types=[raw.source_type],
                    title=raw.title,
                    normalized_start=raw.start_time,
                    normalized_end=raw.end_time or (raw.start_time + timedelta(hours=1)),
                    location=raw.location,
                    event_type=normalized_type,
                    timeline_items=[],
                    dedup_reason="integration_fake_semantic",
                    confidence=0.95,
                    priority="normal",
                    status="pending",
                )
            )
        return curated_events, []

    async def _fake_detect_and_resolve_conflicts(self, family_id, curated_events, user_id, family_prefs=None):
        return 0

    async def _fake_discover_associations(self, family_id, curated_events, date_range, family_prefs=None):
        assert all(event.id is not None for event in curated_events)
        anchor = curated_events[0]
        return [
            EventAssociation(
                family_id=family_id,
                source_event_id=anchor.id,
                target_id="person:test-parent",
                target_type="person",
                association_type="semantic",
                title="探望父母（揭阳）",
                reason="父母均在揭阳，可一并安排见面。",
                priority="convenient",
                confidence=0.75,
                is_dismissed=False,
                is_confirmed=False,
            )
        ]

    monkeypatch.setattr(
        SecretaryCurationService,
        "_semantic_dedup_and_normalize",
        _fake_semantic_dedup_and_normalize,
    )
    monkeypatch.setattr(
        SecretaryCurationService,
        "_detect_and_resolve_conflicts",
        _fake_detect_and_resolve_conflicts,
    )
    monkeypatch.setattr(
        SecretaryCurationService,
        "_discover_associations",
        _fake_discover_associations,
    )

    service = SecretaryCurationService(db_session)
    result = await service.curate_family_events(
        family_id=family_id,
        date_range=(start_date, end_date),
        trigger_type="manual",
        user_id=user_id,
    )

    assert result.associations_created == 1

    assoc_result = await db_session.execute(
        select(EventAssociation).where(
            EventAssociation.family_id == family_id,
            EventAssociation.title == "探望父母（揭阳）",
        )
    )
    associations = assoc_result.scalars().all()
    assert associations
    assert all(assoc.source_event_id is not None for assoc in associations)
