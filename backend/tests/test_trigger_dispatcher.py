"""Tests for the incremental curation TriggerDispatcher.

Verifies that each trigger type routes to the correct handler
and produces the expected database state changes.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.curation.services.trigger_dispatcher import (
    TriggerDispatcher,
    _source_changed,
)
from src.modules.curation.services.impact_arbitrator import (
    ImpactArbitrator,
    ImpactAssessment,
    ImpactLevel,
    ExecutionMode,
)
from src.modules.curation.models import CuratedEvent, EventAssociation
from src.modules.trip.models.trip_plan import TripPlan
from src.modules.member.models import User
from src.modules.memory.models import ConversationMemory, MemoryType, MemoryStatus


def _make_passthrough_arbitrator() -> MagicMock:
    """Create a mock ImpactArbitrator that always returns MEDIUM impact.

    Used in handler-focused tests to bypass impact-based routing so that
    triggers always reach their handlers for testing handler logic.
    """
    arb = MagicMock(spec=ImpactArbitrator)
    arb.assess.return_value = ImpactAssessment(
        level=ImpactLevel.MEDIUM,
        should_push=False,
        should_brief=True,
        execution_mode=ExecutionMode.T2_INCREMENTAL,
        reason="test passthrough",
    )
    return arb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_family_id():
    return uuid.uuid4()


def _make_user_id():
    return uuid.uuid4()


async def _create_user(db: AsyncSession, family_id, user_id=None):
    """Create a test user with family."""
    uid = user_id or uuid.uuid4()
    user = User(
        id=uid,
        family_id=family_id,
        username=f"test_{uid.hex[:8]}",
        email=f"{uid.hex[:8]}@test.com",
        password_hash="fakehash",
    )
    db.add(user)
    await db.flush()
    return user


async def _create_trip(
    db: AsyncSession,
    family_id,
    user_id,
    *,
    destination="Tokyo",
    start_date=None,
    end_date=None,
    status="planning",
    category="personal",
    trip_name=None,
):
    """Create a test TripPlan."""
    today = date.today()
    trip = TripPlan(
        family_id=family_id,
        created_by=user_id,
        destination=destination,
        start_date=start_date or today + timedelta(days=7),
        end_date=end_date or today + timedelta(days=10),
        status=status,
        category=category,
        trip_name=trip_name,
        participants=[user_id],
    )
    db.add(trip)
    await db.flush()
    return trip


async def _create_curated_event(
    db: AsyncSession,
    family_id,
    *,
    trip_id=None,
    title="Test Event",
    event_type="travel",
    start_time=None,
    end_time=None,
    is_active=True,
    status="pending",
):
    """Create a test CuratedEvent."""
    now = datetime.now(tz=timezone.utc)
    ce = CuratedEvent(
        family_id=family_id,
        trip_id=trip_id,
        original_event_ids=[],
        source_types=["trip_plan"],
        title=title,
        event_type=event_type,
        normalized_start=start_time or now + timedelta(days=7),
        normalized_end=end_time or now + timedelta(days=10),
        location="Tokyo",
        is_active=is_active,
        status=status,
        confidence=0.9,
        dedup_reason="test",
    )
    db.add(ce)
    await db.flush()
    return ce


async def _create_association(
    db: AsyncSession,
    family_id,
    source_event_id,
    *,
    is_confirmed=False,
    is_dismissed=False,
):
    """Create a test EventAssociation."""
    assoc = EventAssociation(
        family_id=family_id,
        source_event_id=source_event_id,
        target_id=str(uuid.uuid4()),
        target_type="person",
        association_type="location",
        title="Test Association",
        reason="Test reason",
        priority="convenient",
        confidence=0.8,
        is_confirmed=is_confirmed,
        is_dismissed=is_dismissed,
    )
    db.add(assoc)
    await db.flush()
    return assoc


# ---------------------------------------------------------------------------
# Trip Created
# ---------------------------------------------------------------------------

class TestTripCreated:
    """Tests for _handle_trip_created."""

    @pytest.mark.asyncio
    async def test_creates_curated_event(self, db_session: AsyncSession):
        """trip_created should create a new CuratedEvent for the trip."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(db_session, family_id, user.id)
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)

        # Mock association discovery to avoid LLM calls
        with patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=0,
        ):
            result = await dispatcher.dispatch(
                family_id, "trip_created",
                {"plan_id": str(trip.trip_id)},
            )

        assert result["status"] == "created"

        # Verify CuratedEvent exists
        stmt = select(CuratedEvent).where(
            CuratedEvent.trip_id == trip.trip_id
        )
        ce_result = await db_session.execute(stmt)
        curated = ce_result.scalar_one_or_none()
        assert curated is not None
        assert curated.title == f"{trip.destination}行程"
        assert curated.event_type == "travel"
        assert curated.is_active is True

    @pytest.mark.asyncio
    async def test_idempotent_skip(self, db_session: AsyncSession):
        """trip_created should skip if CuratedEvent already exists."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(db_session, family_id, user.id)
        await _create_curated_event(
            db_session, family_id, trip_id=trip.trip_id
        )
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        result = await dispatcher.dispatch(
            family_id, "trip_created",
            {"plan_id": str(trip.trip_id)},
        )

        assert result["status"] == "skipped"
        assert result["reason"] == "already_exists"

    @pytest.mark.asyncio
    async def test_missing_trip_id(self, db_session: AsyncSession):
        """trip_created with no trip_id should skip."""
        family_id = _make_family_id()
        dispatcher = TriggerDispatcher(db_session)
        result = await dispatcher.dispatch(
            family_id, "trip_created", {},
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "no_trip_id"

    @pytest.mark.asyncio
    async def test_trip_not_found(self, db_session: AsyncSession):
        """trip_created with nonexistent trip should skip."""
        family_id = _make_family_id()
        dispatcher = TriggerDispatcher(db_session)
        result = await dispatcher.dispatch(
            family_id, "trip_created",
            {"plan_id": str(uuid.uuid4())},
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "trip_not_found"

    @pytest.mark.asyncio
    async def test_business_trip_type(self, db_session: AsyncSession):
        """Business trips should get event_type='business_trip'."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(
            db_session, family_id, user.id, category="business"
        )
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        with patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=0,
        ):
            result = await dispatcher.dispatch(
                family_id, "trip_created",
                {"plan_id": str(trip.trip_id)},
            )

        assert result["status"] == "created"
        stmt = select(CuratedEvent).where(CuratedEvent.trip_id == trip.trip_id)
        ce_result = await db_session.execute(stmt)
        curated = ce_result.scalar_one()
        assert curated.event_type == "business_trip"


# ---------------------------------------------------------------------------
# Trip Updated
# ---------------------------------------------------------------------------

class TestTripUpdated:
    """Tests for _handle_trip_updated."""

    @pytest.mark.asyncio
    async def test_updates_changed_fields(self, db_session: AsyncSession):
        """trip_updated should update only changed fields."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(
            db_session, family_id, user.id, destination="Tokyo"
        )
        ce = await _create_curated_event(
            db_session, family_id, trip_id=trip.trip_id, title="Tokyo行程"
        )
        await db_session.commit()

        # Change destination
        trip.destination = "Osaka"
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        with patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=0,
        ):
            result = await dispatcher.dispatch(
                family_id, "trip_updated",
                {"plan_id": str(trip.trip_id)},
            )

        assert result["status"] == "updated"
        assert "location" in result["changes"]

        await db_session.refresh(ce)
        assert ce.location == "Osaka"

    @pytest.mark.asyncio
    async def test_itinerary_updated_aliases_trip_updated(self, db_session: AsyncSession):
        """itinerary_updated should reuse the trip update logic."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(
            db_session, family_id, user.id, destination="Kyoto", trip_name="京都行程"
        )
        ce = await _create_curated_event(
            db_session, family_id, trip_id=trip.trip_id, title="Tokyo行程"
        )
        ce.location = "Tokyo"
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        with patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=0,
        ):
            result = await dispatcher.dispatch(
                family_id, "itinerary_updated",
                {"trip_id": str(trip.trip_id)},
            )

        assert result["status"] == "updated"
        assert "location" in result["changes"]

        await db_session.refresh(ce)
        assert ce.location == "Kyoto"
        assert ce.title == "京都行程"

    @pytest.mark.asyncio
    async def test_no_material_changes(self, db_session: AsyncSession):
        """trip_updated with no changes should return no_changes."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(
            db_session, family_id, user.id, destination="Tokyo"
        )
        from src.core.utils.timezone import get_user_timezone
        user_tz = get_user_timezone()
        ce = await _create_curated_event(
            db_session, family_id,
            trip_id=trip.trip_id,
            title="Tokyo行程",
            start_time=datetime.combine(
                trip.start_date, datetime.min.time(), tzinfo=user_tz
            ),
            end_time=datetime.combine(
                trip.end_date, datetime.max.time(), tzinfo=user_tz
            ),
        )
        ce.location = "Tokyo"
        ce.event_type = "travel"
        ce.priority = "normal"
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        result = await dispatcher.dispatch(
            family_id, "trip_updated",
            {"plan_id": str(trip.trip_id)},
        )

        assert result["status"] == "no_changes"

    @pytest.mark.asyncio
    async def test_creates_if_no_existing(self, db_session: AsyncSession):
        """trip_updated should create CuratedEvent if none exists."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(db_session, family_id, user.id)
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        with patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=0,
        ):
            result = await dispatcher.dispatch(
                family_id, "trip_updated",
                {"plan_id": str(trip.trip_id)},
            )

        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_delegates_to_lifecycle_end_if_cancelled(
        self, db_session: AsyncSession
    ):
        """trip_updated with status=cancelled should deactivate."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(
            db_session, family_id, user.id, status="cancelled"
        )
        ce = await _create_curated_event(
            db_session, family_id, trip_id=trip.trip_id
        )
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        result = await dispatcher.dispatch(
            family_id, "trip_updated",
            {"plan_id": str(trip.trip_id)},
        )

        assert result["status"] == "deactivated"
        await db_session.refresh(ce)
        assert ce.is_active is False
        assert ce.status == "cancelled"


# ---------------------------------------------------------------------------
# Trip Cancelled / Deleted
# ---------------------------------------------------------------------------

class TestTripLifecycleEnd:
    """Tests for _handle_trip_lifecycle_end."""

    @pytest.mark.asyncio
    async def test_deactivates_curated_events(self, db_session: AsyncSession):
        """trip_cancelled should deactivate all CuratedEvents for the trip."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(db_session, family_id, user.id)
        ce = await _create_curated_event(
            db_session, family_id, trip_id=trip.trip_id
        )
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        result = await dispatcher.dispatch(
            family_id, "trip_cancelled",
            {"plan_id": str(trip.trip_id)},
        )

        assert result["status"] == "deactivated"
        assert result["events_deactivated"] == 1

        await db_session.refresh(ce)
        assert ce.is_active is False
        assert ce.status == "cancelled"

    @pytest.mark.asyncio
    async def test_dismisses_unconfirmed_associations(
        self, db_session: AsyncSession
    ):
        """Unconfirmed associations should be dismissed, confirmed preserved."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(db_session, family_id, user.id)
        ce = await _create_curated_event(
            db_session, family_id, trip_id=trip.trip_id
        )
        # One unconfirmed, one confirmed
        unconfirmed = await _create_association(
            db_session, family_id, ce.id, is_confirmed=False
        )
        confirmed = await _create_association(
            db_session, family_id, ce.id, is_confirmed=True
        )
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        # Patch LLM fallback so borderline cases are deterministically dismissed
        with patch.object(
            dispatcher,
            "_classify_ambiguous_via_llm",
            new_callable=AsyncMock,
            return_value={str(unconfirmed.id): "cancel"},
        ):
            result = await dispatcher.dispatch(
                family_id, "trip_cancelled",
                {"plan_id": str(trip.trip_id)},
            )

        assert result["associations_dismissed"] == 1

        await db_session.refresh(unconfirmed)
        assert unconfirmed.is_dismissed is True
        assert "auto: source trip" in unconfirmed.dismiss_reason

        await db_session.refresh(confirmed)
        assert confirmed.is_dismissed is False  # preserved

    @pytest.mark.asyncio
    async def test_no_events_to_deactivate(self, db_session: AsyncSession):
        """trip_deleted with no CuratedEvents should return no_events."""
        family_id = _make_family_id()
        dispatcher = TriggerDispatcher(db_session)
        result = await dispatcher.dispatch(
            family_id, "trip_deleted",
            {"plan_id": str(uuid.uuid4())},
        )
        assert result["status"] == "no_events"

    @pytest.mark.asyncio
    async def test_trip_deleted_same_as_cancelled(
        self, db_session: AsyncSession
    ):
        """trip_deleted and trip_cancelled should have the same behavior."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)
        trip = await _create_trip(db_session, family_id, user.id)
        ce = await _create_curated_event(
            db_session, family_id, trip_id=trip.trip_id
        )
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        result = await dispatcher.dispatch(
            family_id, "trip_deleted",
            {"plan_id": str(trip.trip_id)},
        )

        assert result["status"] == "deactivated"
        await db_session.refresh(ce)
        assert ce.is_active is False


# ---------------------------------------------------------------------------
# Memory Extracted
# ---------------------------------------------------------------------------

class TestMemoryExtracted:
    """Tests for _handle_memory_extracted."""

    @pytest.mark.asyncio
    async def test_skips_without_memory_id(self, db_session: AsyncSession):
        """memory_extracted without memory_id should skip."""
        family_id = _make_family_id()
        dispatcher = TriggerDispatcher(
            db_session, arbitrator=_make_passthrough_arbitrator(),
        )
        result = await dispatcher.dispatch(
            family_id, "memory_extracted", {},
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "no_memory_id"

    @pytest.mark.asyncio
    async def test_skips_nonexistent_memory(self, db_session: AsyncSession):
        """memory_extracted with nonexistent memory should skip."""
        family_id = _make_family_id()
        dispatcher = TriggerDispatcher(
            db_session, arbitrator=_make_passthrough_arbitrator(),
        )
        result = await dispatcher.dispatch(
            family_id, "memory_extracted",
            {"memory_id": str(uuid.uuid4())},
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "memory_not_found"

    @pytest.mark.asyncio
    async def test_schedule_memory_triggers_mini_curate(
        self, db_session: AsyncSession
    ):
        """SCHEDULE memory should trigger mini_curate."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)

        memory = ConversationMemory(
            family_id=family_id,
            user_id=user.id,
            source_session_id=None,
            memory_type=MemoryType.SCHEDULE.value,
            status=MemoryStatus.ACTIVE.value,
            content="Meeting tomorrow at 3pm",
            summary="Meeting tomorrow",
            entities={"time_hint": "明天", "location": "Office"},
        )
        db.add(memory) if False else db_session.add(memory)
        await db_session.flush()
        await db_session.commit()

        dispatcher = TriggerDispatcher(
            db_session, arbitrator=_make_passthrough_arbitrator(),
        )
        with patch(
            "src.modules.curation.services.curation_service."
            "SecretaryCurationService.mini_curate",
            new_callable=AsyncMock,
        ) as mock_mini:
            mock_curated = MagicMock()
            mock_curated.id = uuid.uuid4()
            mock_mini.return_value = (mock_curated, [])

            result = await dispatcher.dispatch(
                family_id, "memory_extracted",
                {"memory_id": str(memory.id), "user_id": str(user.id)},
            )

        assert result["status"] == "curated"
        mock_mini.assert_called_once()

    @pytest.mark.asyncio
    async def test_plan_memory_scans_events(self, db_session: AsyncSession):
        """PLAN memory should scan existing events for associations."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)

        memory = ConversationMemory(
            family_id=family_id,
            user_id=user.id,
            source_session_id=None,
            memory_type=MemoryType.PLAN.value,
            status=MemoryStatus.ACTIVE.value,
            content="Want to visit friend in Tokyo",
            summary="Visit friend in Tokyo",
        )
        db_session.add(memory)
        await db_session.flush()

        # Create an active event in date range
        ce = await _create_curated_event(
            db_session, family_id, title="Tokyo Trip",
            start_time=datetime.now(tz=timezone.utc) + timedelta(days=3),
            end_time=datetime.now(tz=timezone.utc) + timedelta(days=5),
        )
        await db_session.commit()

        dispatcher = TriggerDispatcher(
            db_session, arbitrator=_make_passthrough_arbitrator(),
        )
        with patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=1,
        ):
            result = await dispatcher.dispatch(
                family_id, "memory_extracted",
                {"memory_id": str(memory.id)},
            )

        assert result["status"] == "associations_discovered"
        assert result["events_scanned"] >= 1


# ---------------------------------------------------------------------------
# Date Approaching
# ---------------------------------------------------------------------------

class TestDateApproaching:
    """Tests for _handle_date_approaching."""

    @pytest.mark.asyncio
    async def test_finds_nearby_events(self, db_session: AsyncSession):
        """date_approaching should scan events near the approaching date."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)

        # Create an event that overlaps with the approaching date
        target = datetime.now(tz=timezone.utc) + timedelta(days=5)
        ce = await _create_curated_event(
            db_session, family_id,
            title="Trip to Tokyo",
            start_time=target - timedelta(days=1),
            end_time=target + timedelta(days=2),
        )
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        with patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=2,
        ):
            result = await dispatcher.dispatch(
                family_id, "date_approaching",
                {"title": "Birthday", "days_until": 5},
            )

        assert result["status"] == "associations_discovered"
        assert result["events_scanned"] >= 1

    @pytest.mark.asyncio
    async def test_no_nearby_events(self, db_session: AsyncSession):
        """date_approaching with no nearby events should return no_nearby_events."""
        family_id = _make_family_id()
        dispatcher = TriggerDispatcher(db_session)
        result = await dispatcher.dispatch(
            family_id, "date_approaching",
            {"title": "Birthday", "days_until": 5},
        )
        assert result["status"] == "no_nearby_events"


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

class TestReconciliation:
    """Tests for TriggerDispatcher.reconcile."""

    @pytest.mark.asyncio
    async def test_skips_unchanged_events(self, db_session: AsyncSession):
        """Reconciliation should leave unchanged events untouched."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)

        trip = await _create_trip(
            db_session, family_id, user.id, destination="Tokyo"
        )
        ce = await _create_curated_event(
            db_session, family_id,
            trip_id=trip.trip_id,
            title="Tokyo行程",
        )
        ce.original_event_ids = [str(trip.trip_id)]
        ce.location = "Tokyo"
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        today = date.today()

        with patch(
            "src.modules.curation.services.curation_service."
            "CurationCollectorMixin._collect_raw_events",
            new_callable=AsyncMock,
        ) as mock_collect, patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=0,
        ):
            # Return a raw event matching our existing CuratedEvent
            from src.modules.curation.services.data_models import RawEvent
            mock_collect.return_value = [
                RawEvent(
                    id=str(trip.trip_id),
                    source_type="trip_plan",
                    title="Tokyo行程",
                    start_time=ce.normalized_start,
                    end_time=ce.normalized_end,
                    location="Tokyo",
                )
            ]

            result = await dispatcher.reconcile(
                family_id, (today, today + timedelta(days=14))
            )

        assert result["status"] == "reconciled"
        assert result["new_events"] == 0
        assert result["orphaned_events"] == 0

    @pytest.mark.asyncio
    async def test_deactivates_orphans(self, db_session: AsyncSession):
        """Reconciliation should deactivate CuratedEvents whose source is gone."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)

        # Create a CuratedEvent with no matching raw source
        ce = await _create_curated_event(
            db_session, family_id,
            title="Ghost Event",
            start_time=datetime.now(tz=timezone.utc) + timedelta(days=3),
            end_time=datetime.now(tz=timezone.utc) + timedelta(days=4),
        )
        ce.original_event_ids = [str(uuid.uuid4())]  # reference to deleted source
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        today = date.today()

        with patch(
            "src.modules.curation.services.curation_service."
            "CurationCollectorMixin._collect_raw_events",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=0,
        ):
            result = await dispatcher.reconcile(
                family_id, (today, today + timedelta(days=14))
            )

        assert result["orphaned_events"] == 1

        await db_session.refresh(ce)
        assert ce.is_active is False
        assert ce.status == "cancelled"

    @pytest.mark.asyncio
    async def test_preserves_confirmed_events(self, db_session: AsyncSession):
        """Reconciliation should NOT deactivate confirmed events."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)

        ce = await _create_curated_event(
            db_session, family_id,
            title="Confirmed Event",
            status="confirmed",
            start_time=datetime.now(tz=timezone.utc) + timedelta(days=3),
            end_time=datetime.now(tz=timezone.utc) + timedelta(days=4),
        )
        ce.original_event_ids = [str(uuid.uuid4())]
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        today = date.today()

        with patch(
            "src.modules.curation.services.curation_service."
            "CurationCollectorMixin._collect_raw_events",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=0,
        ):
            result = await dispatcher.reconcile(
                family_id, (today, today + timedelta(days=14))
            )

        assert result["orphaned_events"] == 0

        await db_session.refresh(ce)
        assert ce.is_active is True
        assert ce.status == "confirmed"

    @pytest.mark.asyncio
    async def test_preserves_user_created_events(
        self, db_session: AsyncSession
    ):
        """Reconciliation should NOT deactivate user_created events."""
        family_id = _make_family_id()
        user = await _create_user(db_session, family_id)

        ce = await _create_curated_event(
            db_session, family_id,
            title="User Created Event",
            start_time=datetime.now(tz=timezone.utc) + timedelta(days=3),
            end_time=datetime.now(tz=timezone.utc) + timedelta(days=4),
        )
        ce.source_types = ["user_created"]
        ce.original_event_ids = [str(uuid.uuid4())]
        await db_session.commit()

        dispatcher = TriggerDispatcher(db_session)
        today = date.today()

        with patch(
            "src.modules.curation.services.curation_service."
            "CurationCollectorMixin._collect_raw_events",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            dispatcher, "discover_associations_for_event",
            new_callable=AsyncMock, return_value=0,
        ):
            result = await dispatcher.reconcile(
                family_id, (today, today + timedelta(days=14))
            )

        assert result["orphaned_events"] == 0
        await db_session.refresh(ce)
        assert ce.is_active is True


# ---------------------------------------------------------------------------
# Diff Logic
# ---------------------------------------------------------------------------

class TestDiffEvents:
    """Tests for _diff_events static method."""

    def test_new_raw_detected(self):
        """Raw events not in existing curated should be flagged as new."""
        from src.modules.curation.services.data_models import RawEvent

        raw = RawEvent(
            id="new-raw-1",
            source_type="trip_plan",
            title="New Trip",
            start_time=datetime.now(tz=timezone.utc),
        )
        new_raws, updated, orphaned = TriggerDispatcher._diff_events(
            [raw], []
        )
        assert len(new_raws) == 1
        assert len(updated) == 0
        assert len(orphaned) == 0

    def test_orphaned_detected(self):
        """CuratedEvents with no matching raw should be orphaned."""
        ce = MagicMock()
        ce.id = uuid.uuid4()
        ce.original_event_ids = ["old-source-1"]
        ce.source_types = ["trip_plan"]
        ce.status = "pending"

        new_raws, updated, orphaned = TriggerDispatcher._diff_events(
            [], [ce]
        )
        assert len(new_raws) == 0
        assert len(orphaned) == 1

    def test_confirmed_not_orphaned(self):
        """Confirmed CuratedEvents should not be orphaned."""
        ce = MagicMock()
        ce.id = uuid.uuid4()
        ce.original_event_ids = ["old-source-1"]
        ce.source_types = ["trip_plan"]
        ce.status = "confirmed"

        new_raws, updated, orphaned = TriggerDispatcher._diff_events(
            [], [ce]
        )
        assert len(orphaned) == 0

    def test_source_changed_detected(self):
        """Changes in raw event should produce updated pair."""
        from src.modules.curation.services.data_models import RawEvent

        raw = RawEvent(
            id="src-1",
            source_type="trip_plan",
            title="Updated Title",
            start_time=datetime.now(tz=timezone.utc),
        )
        ce = MagicMock()
        ce.id = uuid.uuid4()
        ce.original_event_ids = ["src-1"]
        ce.source_types = ["trip_plan"]
        ce.status = "pending"
        ce.title = "Old Title"
        ce.normalized_start = raw.start_time
        ce.normalized_end = None
        ce.location = None

        new_raws, updated, orphaned = TriggerDispatcher._diff_events(
            [raw], [ce]
        )
        assert len(new_raws) == 0
        assert len(updated) == 1
        assert len(orphaned) == 0


# ---------------------------------------------------------------------------
# _source_changed helper
# ---------------------------------------------------------------------------

class TestSourceChanged:
    """Tests for the _source_changed helper."""

    def test_title_changed(self):
        raw = MagicMock(title="New", start_time=None, end_time=None, location=None)
        ce = MagicMock(title="Old", normalized_start=None, normalized_end=None, location=None)
        assert _source_changed(raw, ce) is True

    def test_nothing_changed(self):
        now = datetime.now(tz=timezone.utc)
        raw = MagicMock(title="Same", start_time=now, end_time=now, location="Tokyo")
        ce = MagicMock(title="Same", normalized_start=now, normalized_end=now, location="Tokyo")
        assert _source_changed(raw, ce) is False

    def test_location_changed(self):
        raw = MagicMock(title="Same", start_time=None, end_time=None, location="Osaka")
        ce = MagicMock(title="Same", normalized_start=None, normalized_end=None, location="Tokyo")
        assert _source_changed(raw, ce) is True


# ---------------------------------------------------------------------------
# Unknown Trigger
# ---------------------------------------------------------------------------

class TestUnknownTrigger:
    """Tests for unknown trigger types."""

    @pytest.mark.asyncio
    async def test_unknown_trigger_skips(self, db_session: AsyncSession):
        """Unknown trigger types should be skipped."""
        family_id = _make_family_id()
        dispatcher = TriggerDispatcher(db_session)
        result = await dispatcher.dispatch(
            family_id, "unknown_trigger", {},
        )
        assert result["status"] == "skipped"
        assert "unknown_trigger" in result["reason"]


# ---------------------------------------------------------------------------
# Full Curate Fallback (via tasks.py routing)
# ---------------------------------------------------------------------------

class TestTaskRouting:
    """Tests for task-level routing to dispatcher vs full pipeline."""

    @pytest.mark.asyncio
    async def test_manual_uses_full_pipeline(self):
        """manual trigger should NOT go through dispatcher."""
        from src.modules.curation.tasks import (
            _FULL_PIPELINE_TRIGGERS,
            _INCREMENTAL_TRIGGERS,
        )
        assert "manual" in _FULL_PIPELINE_TRIGGERS
        assert "manual" not in _INCREMENTAL_TRIGGERS

    @pytest.mark.asyncio
    async def test_trip_created_is_incremental(self):
        """trip_created should be in incremental triggers."""
        from src.modules.curation.tasks import _INCREMENTAL_TRIGGERS
        assert "trip_created" in _INCREMENTAL_TRIGGERS
        assert "trip_updated" in _INCREMENTAL_TRIGGERS
        assert "trip_cancelled" in _INCREMENTAL_TRIGGERS
        assert "trip_deleted" in _INCREMENTAL_TRIGGERS
        assert "memory_extracted" in _INCREMENTAL_TRIGGERS
        assert "date_approaching" in _INCREMENTAL_TRIGGERS
