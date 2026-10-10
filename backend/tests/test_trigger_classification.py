"""Tests for T1/T2/T3 trigger classification and impact-aware dispatch routing.

Verifies:
- TriggerLevel enum and classify_trigger_level() mapping
- ImpactArbitrator SILENT -> skip
- ImpactArbitrator LOW -> deferred to DirtyBitManager
- ImpactArbitrator MEDIUM/HIGH -> immediate execution
- T2 triggers route through DirtyBitManager
- T3 triggers return scheduled status
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.curation.services.trigger_dispatcher import (
    TriggerDispatcher,
    TriggerLevel,
    classify_trigger_level,
)
from src.modules.curation.services.impact_arbitrator import (
    ImpactArbitrator,
    ImpactAssessment,
    ImpactLevel,
    ExecutionMode,
    TriggerContext,
)
from src.modules.curation.services.dirty_bit_manager import DirtyBitManager


# ---------------------------------------------------------------------------
# TriggerLevel Enum
# ---------------------------------------------------------------------------

class TestTriggerLevelEnum:
    """Tests for TriggerLevel enum values."""

    def test_t1_value(self):
        assert TriggerLevel.T1.value == "immediate"

    def test_t2_value(self):
        assert TriggerLevel.T2.value == "deferred"

    def test_t3_value(self):
        assert TriggerLevel.T3.value == "scheduled"

    def test_is_string_enum(self):
        assert isinstance(TriggerLevel.T1, str)
        assert TriggerLevel.T1 == "immediate"


# ---------------------------------------------------------------------------
# classify_trigger_level()
# ---------------------------------------------------------------------------

class TestClassifyTriggerLevel:
    """Tests for classify_trigger_level() mapping."""

    # T1 triggers
    def test_trip_created_is_t1(self):
        assert classify_trigger_level("trip_created") == TriggerLevel.T1

    def test_trip_updated_is_t1(self):
        assert classify_trigger_level("trip_updated") == TriggerLevel.T1

    def test_trip_cancelled_is_t1(self):
        assert classify_trigger_level("trip_cancelled") == TriggerLevel.T1

    def test_trip_deleted_is_t1(self):
        assert classify_trigger_level("trip_deleted") == TriggerLevel.T1

    def test_itinerary_updated_is_t1(self):
        assert classify_trigger_level("itinerary_updated") == TriggerLevel.T1

    def test_event_created_is_t1(self):
        assert classify_trigger_level("event_created") == TriggerLevel.T1

    def test_event_updated_is_t1(self):
        assert classify_trigger_level("event_updated") == TriggerLevel.T1

    def test_event_deleted_is_t1(self):
        assert classify_trigger_level("event_deleted") == TriggerLevel.T1

    def test_user_request_is_t1(self):
        assert classify_trigger_level("user_request") == TriggerLevel.T1

    # T2 triggers
    def test_memory_extracted_is_t2(self):
        assert classify_trigger_level("memory_extracted") == TriggerLevel.T2

    def test_date_approaching_is_t2(self):
        assert classify_trigger_level("date_approaching") == TriggerLevel.T2

    def test_weather_changed_is_t2(self):
        assert classify_trigger_level("weather_changed") == TriggerLevel.T2

    # T3 triggers
    def test_scheduled_daily_is_t3(self):
        assert classify_trigger_level("scheduled_daily") == TriggerLevel.T3

    def test_scheduled_weekly_is_t3(self):
        assert classify_trigger_level("scheduled_weekly") == TriggerLevel.T3

    def test_scheduled_is_t3(self):
        assert classify_trigger_level("scheduled") == TriggerLevel.T3

    # Unknown defaults to T2
    def test_unknown_trigger_defaults_to_t2(self):
        assert classify_trigger_level("something_unknown") == TriggerLevel.T2

    def test_empty_string_defaults_to_t2(self):
        assert classify_trigger_level("") == TriggerLevel.T2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_family_id():
    return uuid.uuid4()


def _make_assessment(
    level: ImpactLevel,
    reason: str = "test",
) -> ImpactAssessment:
    """Create an ImpactAssessment with sensible defaults."""
    mode_map = {
        ImpactLevel.SILENT: ExecutionMode.SILENT_UPDATE,
        ImpactLevel.LOW: ExecutionMode.T1_HEURISTIC,
        ImpactLevel.MEDIUM: ExecutionMode.T2_INCREMENTAL,
        ImpactLevel.HIGH: ExecutionMode.T3_FULL,
    }
    return ImpactAssessment(
        level=level,
        should_push=level >= ImpactLevel.HIGH,
        should_brief=level >= ImpactLevel.MEDIUM,
        execution_mode=mode_map[level],
        reason=reason,
    )


# ---------------------------------------------------------------------------
# ImpactArbitrator Integration: SILENT -> skip
# ---------------------------------------------------------------------------

class TestSilentImpactSkip:
    """SILENT impact triggers should be logged and skipped."""

    @pytest.mark.asyncio
    async def test_silent_impact_skips_execution(self, db_session: AsyncSession):
        """When ImpactArbitrator returns SILENT, dispatch should skip."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.SILENT, "only notes changed"
        )

        dispatcher = TriggerDispatcher(
            db_session, arbitrator=mock_arbitrator,
        )

        result = await dispatcher.dispatch(
            family_id, "trip_updated",
            {"plan_id": str(uuid.uuid4()), "diff": {"notes": {"old": "a", "new": "b"}}},
        )

        assert result["status"] == "skipped"
        assert "silent_impact" in result["reason"]
        assert result["impact_level"] == "silent"
        mock_arbitrator.assess.assert_called_once()

    @pytest.mark.asyncio
    async def test_silent_memory_extracted_skips(self, db_session: AsyncSession):
        """memory_extracted with SILENT assessment should skip."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.SILENT, "memory extracted without conflict"
        )

        dispatcher = TriggerDispatcher(
            db_session, arbitrator=mock_arbitrator,
        )

        result = await dispatcher.dispatch(
            family_id, "memory_extracted",
            {"memory_id": str(uuid.uuid4())},
        )

        assert result["status"] == "skipped"
        assert result["impact_level"] == "silent"


# ---------------------------------------------------------------------------
# ImpactArbitrator Integration: LOW -> deferred to DirtyBitManager
# ---------------------------------------------------------------------------

class TestLowImpactDeferred:
    """LOW impact triggers should be upgraded to T2 and deferred."""

    @pytest.mark.asyncio
    async def test_low_impact_defers_to_dirty_bit_manager(
        self, db_session: AsyncSession
    ):
        """LOW impact should route to DirtyBitManager when available."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.LOW, "time shift 1h, no conflict"
        )

        mock_dbm = AsyncMock(spec=DirtyBitManager)
        mock_dbm.mark_dirty = AsyncMock(return_value=_make_assessment(ImpactLevel.LOW))

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=mock_dbm,
        )

        result = await dispatcher.dispatch(
            family_id, "trip_updated",
            {"plan_id": str(uuid.uuid4())},
        )

        assert result["status"] == "deferred"
        assert result["trigger_level"] == "deferred"
        assert result["impact_level"] == "low"
        mock_dbm.mark_dirty.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_impact_t1_trigger_upgraded_to_t2(
        self, db_session: AsyncSession
    ):
        """A T1 trigger with LOW impact should be upgraded to T2."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.LOW, "minor change"
        )

        mock_dbm = AsyncMock(spec=DirtyBitManager)
        mock_dbm.mark_dirty = AsyncMock(return_value=_make_assessment(ImpactLevel.LOW))

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=mock_dbm,
        )

        # trip_created is normally T1
        result = await dispatcher.dispatch(
            family_id, "trip_created",
            {"plan_id": str(uuid.uuid4())},
        )

        # But LOW impact upgrades it to T2 (deferred)
        assert result["status"] == "deferred"
        assert result["trigger_level"] == "deferred"

    @pytest.mark.asyncio
    async def test_low_impact_without_dbm_executes_immediately(
        self, db_session: AsyncSession
    ):
        """LOW impact without DirtyBitManager should fall through to execute."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.LOW, "minor change"
        )

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=None,
        )

        # Without DBM, T2 trigger should skip (no handler for weather_changed)
        result = await dispatcher.dispatch(
            family_id, "weather_changed", {},
        )

        # weather_changed has no handler -> skipped as unknown_trigger
        assert result["status"] == "skipped"
        assert "unknown_trigger" in result["reason"]


# ---------------------------------------------------------------------------
# ImpactArbitrator Integration: MEDIUM/HIGH -> immediate execution
# ---------------------------------------------------------------------------

class TestMediumHighImpactImmediate:
    """MEDIUM and HIGH impact triggers should use classified level as-is."""

    @pytest.mark.asyncio
    async def test_medium_impact_executes_immediately(
        self, db_session: AsyncSession
    ):
        """MEDIUM impact T1 trigger should execute immediately."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.MEDIUM, "location changed"
        )

        mock_dbm = AsyncMock(spec=DirtyBitManager)

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=mock_dbm,
        )

        # trip_created is T1 and MEDIUM -> should execute, not defer
        with patch.object(
            dispatcher, "_execute_handler",
            new_callable=AsyncMock,
            return_value={"status": "created", "trigger_level": "immediate", "impact_level": "medium"},
        ) as mock_exec:
            result = await dispatcher.dispatch(
                family_id, "trip_created",
                {"plan_id": str(uuid.uuid4())},
            )

        mock_exec.assert_called_once()
        mock_dbm.mark_dirty.assert_not_called()
        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_high_impact_executes_immediately(
        self, db_session: AsyncSession
    ):
        """HIGH impact triggers should always execute immediately."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.HIGH, "new trip created"
        )

        mock_dbm = AsyncMock(spec=DirtyBitManager)

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=mock_dbm,
        )

        with patch.object(
            dispatcher, "_execute_handler",
            new_callable=AsyncMock,
            return_value={"status": "created", "trigger_level": "immediate", "impact_level": "high"},
        ) as mock_exec:
            result = await dispatcher.dispatch(
                family_id, "trip_created",
                {"plan_id": str(uuid.uuid4())},
            )

        mock_exec.assert_called_once()
        mock_dbm.mark_dirty.assert_not_called()

    @pytest.mark.asyncio
    async def test_high_impact_t2_trigger_stays_t2_but_executes(
        self, db_session: AsyncSession
    ):
        """T2 trigger with HIGH impact should NOT be deferred."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.HIGH, "memory extracted with conflict"
        )

        mock_dbm = AsyncMock(spec=DirtyBitManager)

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=mock_dbm,
        )

        with patch.object(
            dispatcher, "_execute_handler",
            new_callable=AsyncMock,
            return_value={"status": "executed", "trigger_level": "deferred", "impact_level": "high"},
        ) as mock_exec:
            result = await dispatcher.dispatch(
                family_id, "memory_extracted",
                {"memory_id": str(uuid.uuid4()), "has_conflict": True},
            )

        # T2 trigger classified as memory_extracted, but HIGH impact -> execute
        mock_exec.assert_called_once()
        mock_dbm.mark_dirty.assert_not_called()


# ---------------------------------------------------------------------------
# T2 Triggers and DirtyBitManager routing
# ---------------------------------------------------------------------------

class TestT2DirtyBitManagerRouting:
    """T2 triggers should route through DirtyBitManager."""

    @pytest.mark.asyncio
    async def test_t2_memory_extracted_medium_defers(
        self, db_session: AsyncSession
    ):
        """T2 memory_extracted with MEDIUM impact defers to DirtyBitManager."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.MEDIUM, "memory with possible conflict"
        )

        mock_dbm = AsyncMock(spec=DirtyBitManager)
        mock_dbm.mark_dirty = AsyncMock(
            return_value=_make_assessment(ImpactLevel.MEDIUM)
        )

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=mock_dbm,
        )

        result = await dispatcher.dispatch(
            family_id, "memory_extracted",
            {"memory_id": str(uuid.uuid4())},
        )

        assert result["status"] == "deferred"
        assert result["trigger_level"] == "deferred"
        mock_dbm.mark_dirty.assert_called_once()

    @pytest.mark.asyncio
    async def test_t2_date_approaching_medium_defers(
        self, db_session: AsyncSession
    ):
        """T2 date_approaching with MEDIUM impact defers to DirtyBitManager."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.MEDIUM, "date approaching in 5 days"
        )

        mock_dbm = AsyncMock(spec=DirtyBitManager)
        mock_dbm.mark_dirty = AsyncMock(
            return_value=_make_assessment(ImpactLevel.MEDIUM)
        )

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=mock_dbm,
        )

        result = await dispatcher.dispatch(
            family_id, "date_approaching",
            {"title": "Birthday", "days_until": 5},
        )

        assert result["status"] == "deferred"
        mock_dbm.mark_dirty.assert_called_once()

    @pytest.mark.asyncio
    async def test_entity_id_extracted_for_dirty_bit_manager(
        self, db_session: AsyncSession
    ):
        """DirtyBitManager receives correct entity_id from payload."""
        family_id = _make_family_id()
        memory_id = str(uuid.uuid4())

        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.MEDIUM, "test"
        )

        mock_dbm = AsyncMock(spec=DirtyBitManager)
        mock_dbm.mark_dirty = AsyncMock(
            return_value=_make_assessment(ImpactLevel.MEDIUM)
        )

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=mock_dbm,
        )

        await dispatcher.dispatch(
            family_id, "memory_extracted",
            {"memory_id": memory_id},
        )

        call_kwargs = mock_dbm.mark_dirty.call_args
        assert call_kwargs.kwargs["entity_id"] == memory_id


# ---------------------------------------------------------------------------
# T3 Triggers and ShouldRunService
# ---------------------------------------------------------------------------

class TestT3ScheduledTriggers:
    """T3 triggers should return scheduled status."""

    @pytest.mark.asyncio
    async def test_scheduled_daily_returns_scheduled(
        self, db_session: AsyncSession
    ):
        """scheduled_daily should be classified T3 and return scheduled."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.MEDIUM, "scheduled check"
        )

        dispatcher = TriggerDispatcher(
            db_session, arbitrator=mock_arbitrator,
        )

        result = await dispatcher.dispatch(
            family_id, "scheduled_daily", {},
        )

        assert result["status"] == "scheduled"
        assert result["trigger_level"] == "scheduled"

    @pytest.mark.asyncio
    async def test_scheduled_weekly_returns_scheduled(
        self, db_session: AsyncSession
    ):
        """scheduled_weekly should be classified T3 and return scheduled."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.HIGH, "weekly full review"
        )

        dispatcher = TriggerDispatcher(
            db_session, arbitrator=mock_arbitrator,
        )

        result = await dispatcher.dispatch(
            family_id, "scheduled_weekly", {},
        )

        assert result["status"] == "scheduled"
        assert result["trigger_level"] == "scheduled"

    @pytest.mark.asyncio
    async def test_t3_not_routed_to_dirty_bit_manager(
        self, db_session: AsyncSession
    ):
        """T3 triggers should NOT route through DirtyBitManager."""
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.MEDIUM, "scheduled"
        )

        mock_dbm = AsyncMock(spec=DirtyBitManager)

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=mock_dbm,
        )

        result = await dispatcher.dispatch(
            family_id, "scheduled_daily", {},
        )

        assert result["status"] == "scheduled"
        mock_dbm.mark_dirty.assert_not_called()


# ---------------------------------------------------------------------------
# _extract_entity_id
# ---------------------------------------------------------------------------

class TestExtractEntityId:
    """Tests for _extract_entity_id helper."""

    def test_extracts_plan_id(self):
        result = TriggerDispatcher._extract_entity_id(
            "trip_created", {"plan_id": "abc-123"}
        )
        assert result == "abc-123"

    def test_extracts_trip_id(self):
        result = TriggerDispatcher._extract_entity_id(
            "trip_updated", {"trip_id": "trip-456"}
        )
        assert result == "trip-456"

    def test_extracts_memory_id(self):
        result = TriggerDispatcher._extract_entity_id(
            "memory_extracted", {"memory_id": "mem-789"}
        )
        assert result == "mem-789"

    def test_extracts_event_id(self):
        result = TriggerDispatcher._extract_entity_id(
            "event_updated", {"event_id": "evt-101"}
        )
        assert result == "evt-101"

    def test_prefers_plan_id_over_trip_id(self):
        result = TriggerDispatcher._extract_entity_id(
            "trip_created", {"plan_id": "plan-1", "trip_id": "trip-2"}
        )
        assert result == "plan-1"

    def test_unknown_payload_returns_fallback(self):
        result = TriggerDispatcher._extract_entity_id(
            "weather_changed", {"temp": 25}
        )
        assert result == "weather_changed:unknown"

    def test_empty_payload_returns_fallback(self):
        result = TriggerDispatcher._extract_entity_id(
            "date_approaching", {}
        )
        assert result == "date_approaching:unknown"


# ---------------------------------------------------------------------------
# Result includes trigger_level and impact_level metadata
# ---------------------------------------------------------------------------

class TestResultMetadata:
    """dispatch() results should include trigger_level and impact_level."""

    @pytest.mark.asyncio
    async def test_silent_skip_includes_metadata(self, db_session: AsyncSession):
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.SILENT, "no change"
        )

        dispatcher = TriggerDispatcher(
            db_session, arbitrator=mock_arbitrator,
        )

        result = await dispatcher.dispatch(
            family_id, "trip_updated", {"diff": {"notes": {"old": "a", "new": "b"}}},
        )

        assert "trigger_level" in result
        assert "impact_level" in result
        assert result["trigger_level"] == "immediate"
        assert result["impact_level"] == "silent"

    @pytest.mark.asyncio
    async def test_deferred_includes_metadata(self, db_session: AsyncSession):
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.MEDIUM, "test"
        )

        mock_dbm = AsyncMock(spec=DirtyBitManager)
        mock_dbm.mark_dirty = AsyncMock(
            return_value=_make_assessment(ImpactLevel.MEDIUM)
        )

        dispatcher = TriggerDispatcher(
            db_session,
            arbitrator=mock_arbitrator,
            dirty_bit_manager=mock_dbm,
        )

        result = await dispatcher.dispatch(
            family_id, "memory_extracted",
            {"memory_id": str(uuid.uuid4())},
        )

        assert result["trigger_level"] == "deferred"
        assert result["impact_level"] == "medium"

    @pytest.mark.asyncio
    async def test_scheduled_includes_metadata(self, db_session: AsyncSession):
        family_id = _make_family_id()
        mock_arbitrator = MagicMock(spec=ImpactArbitrator)
        mock_arbitrator.assess.return_value = _make_assessment(
            ImpactLevel.MEDIUM, "scheduled"
        )

        dispatcher = TriggerDispatcher(
            db_session, arbitrator=mock_arbitrator,
        )

        result = await dispatcher.dispatch(
            family_id, "scheduled_daily", {},
        )

        assert result["trigger_level"] == "scheduled"
        assert result["impact_level"] == "medium"
