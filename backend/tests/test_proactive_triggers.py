"""Tests for T0 proactive triggers.

Covers:
- ProactiveTrigger dataclass
- ProactiveTriggerer.scan_for_triggers orchestration
- _scan_approaching_dates sub-scanner
- _scan_cold_relationships sub-scanner
- _scan_stale_commitments sub-scanner
- _scan_user_rhythm placeholder
- Error isolation between scanners
- MAX_TRIGGERS_PER_SCAN capping
- Priority sorting
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from src.modules.curation.services.proactive_triggerer import (
    ProactiveTrigger,
    ProactiveTriggerer,
    APPROACHING_DATE_DAYS_DEFAULT,
    MAX_TRIGGERS_PER_SCAN,
)


# ---------------------------------------------------------------------------
# ProactiveTrigger dataclass
# ---------------------------------------------------------------------------


class TestProactiveTrigger:

    def test_creation(self):
        fid = uuid4()
        t = ProactiveTrigger(
            trigger_type="approaching_date",
            family_id=fid,
            data={"title": "Mom birthday"},
            priority="P1",
        )
        assert t.trigger_type == "approaching_date"
        assert t.family_id == fid
        assert t.target_member_id is None
        assert t.data["title"] == "Mom birthday"
        assert t.priority == "P1"

    def test_defaults(self):
        fid = uuid4()
        t = ProactiveTrigger(trigger_type="user_rhythm", family_id=fid)
        assert t.data == {}
        assert t.priority == "P2"
        assert t.target_member_id is None

    def test_frozen(self):
        fid = uuid4()
        t = ProactiveTrigger(trigger_type="cold_relationship", family_id=fid)
        with pytest.raises(FrozenInstanceError):
            t.priority = "P0"


# ---------------------------------------------------------------------------
# ProactiveTriggerer — scanner orchestration
# ---------------------------------------------------------------------------


class TestProactiveTriggerer:

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def family_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_scan_returns_empty_when_no_triggers(self, mock_db, family_id):
        triggerer = ProactiveTriggerer(mock_db)
        with patch.object(triggerer, "_scan_approaching_dates", new_callable=AsyncMock, return_value=[]), \
             patch.object(triggerer, "_scan_cold_relationships", new_callable=AsyncMock, return_value=[]), \
             patch.object(triggerer, "_scan_stale_commitments", new_callable=AsyncMock, return_value=[]), \
             patch.object(triggerer, "_scan_user_rhythm", new_callable=AsyncMock, return_value=[]):
            result = await triggerer.scan_for_triggers(family_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_scan_collects_from_multiple_scanners(self, mock_db, family_id):
        t1 = ProactiveTrigger(trigger_type="approaching_date", family_id=family_id, priority="P2")
        t2 = ProactiveTrigger(trigger_type="cold_relationship", family_id=family_id, priority="P1")

        triggerer = ProactiveTriggerer(mock_db)
        with patch.object(triggerer, "_scan_approaching_dates", new_callable=AsyncMock, return_value=[t1]), \
             patch.object(triggerer, "_scan_cold_relationships", new_callable=AsyncMock, return_value=[t2]), \
             patch.object(triggerer, "_scan_stale_commitments", new_callable=AsyncMock, return_value=[]), \
             patch.object(triggerer, "_scan_user_rhythm", new_callable=AsyncMock, return_value=[]):
            result = await triggerer.scan_for_triggers(family_id)

        assert len(result) == 2
        # P1 should come before P2
        assert result[0].priority == "P1"
        assert result[1].priority == "P2"

    @pytest.mark.asyncio
    async def test_scan_caps_at_max_triggers(self, mock_db, family_id):
        triggers = [
            ProactiveTrigger(trigger_type="approaching_date", family_id=family_id)
            for _ in range(MAX_TRIGGERS_PER_SCAN + 5)
        ]

        triggerer = ProactiveTriggerer(mock_db)
        with patch.object(triggerer, "_scan_approaching_dates", new_callable=AsyncMock, return_value=triggers), \
             patch.object(triggerer, "_scan_cold_relationships", new_callable=AsyncMock, return_value=[]), \
             patch.object(triggerer, "_scan_stale_commitments", new_callable=AsyncMock, return_value=[]), \
             patch.object(triggerer, "_scan_user_rhythm", new_callable=AsyncMock, return_value=[]):
            result = await triggerer.scan_for_triggers(family_id)

        assert len(result) == MAX_TRIGGERS_PER_SCAN

    @pytest.mark.asyncio
    async def test_scanner_error_does_not_block_others(self, mock_db, family_id):
        t1 = ProactiveTrigger(trigger_type="stale_commitment", family_id=family_id)

        triggerer = ProactiveTriggerer(mock_db)
        with patch.object(triggerer, "_scan_approaching_dates", new_callable=AsyncMock, side_effect=Exception("DB down")), \
             patch.object(triggerer, "_scan_cold_relationships", new_callable=AsyncMock, side_effect=Exception("timeout")), \
             patch.object(triggerer, "_scan_stale_commitments", new_callable=AsyncMock, return_value=[t1]), \
             patch.object(triggerer, "_scan_user_rhythm", new_callable=AsyncMock, return_value=[]):
            result = await triggerer.scan_for_triggers(family_id)

        # Only stale_commitment survived
        assert len(result) == 1
        assert result[0].trigger_type == "stale_commitment"

    @pytest.mark.asyncio
    async def test_priority_sorting(self, mock_db, family_id):
        t_p3 = ProactiveTrigger(trigger_type="user_rhythm", family_id=family_id, priority="P3")
        t_p0 = ProactiveTrigger(trigger_type="approaching_date", family_id=family_id, priority="P0")
        t_p2 = ProactiveTrigger(trigger_type="cold_relationship", family_id=family_id, priority="P2")
        t_p1 = ProactiveTrigger(trigger_type="stale_commitment", family_id=family_id, priority="P1")

        triggerer = ProactiveTriggerer(mock_db)
        with patch.object(triggerer, "_scan_approaching_dates", new_callable=AsyncMock, return_value=[t_p3, t_p0]), \
             patch.object(triggerer, "_scan_cold_relationships", new_callable=AsyncMock, return_value=[t_p2]), \
             patch.object(triggerer, "_scan_stale_commitments", new_callable=AsyncMock, return_value=[t_p1]), \
             patch.object(triggerer, "_scan_user_rhythm", new_callable=AsyncMock, return_value=[]):
            result = await triggerer.scan_for_triggers(family_id)

        priorities = [t.priority for t in result]
        assert priorities == ["P0", "P1", "P2", "P3"]


# ---------------------------------------------------------------------------
# _scan_approaching_dates
# ---------------------------------------------------------------------------


class TestScanApproachingDates:

    @pytest.mark.asyncio
    async def test_no_upcoming_dates_returns_empty(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_approaching_dates(uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_date_with_existing_event_skipped(self):
        family_id = uuid4()
        mock_db = AsyncMock()

        # First query: upcoming dates
        mock_date = MagicMock()
        mock_date.solar_date = date.today() + timedelta(days=3)
        mock_date.id = uuid4()
        mock_date.title = "Mom Birthday"
        mock_date.date_type = "birthday"
        mock_date.member_id = uuid4()

        dates_result = MagicMock()
        dates_result.scalars.return_value.all.return_value = [mock_date]

        # Second query: existing events count = 1
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        mock_db.execute = AsyncMock(side_effect=[dates_result, count_result])

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_approaching_dates(family_id)
        assert result == []

    @pytest.mark.asyncio
    async def test_date_without_event_generates_trigger(self):
        family_id = uuid4()
        mock_db = AsyncMock()

        mock_date = MagicMock()
        mock_date.solar_date = date.today() + timedelta(days=5)
        mock_date.id = uuid4()
        mock_date.title = "Wedding Anniversary"
        mock_date.date_type = "anniversary"
        mock_date.member_id = uuid4()

        dates_result = MagicMock()
        dates_result.scalars.return_value.all.return_value = [mock_date]

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        mock_db.execute = AsyncMock(side_effect=[dates_result, count_result])

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_approaching_dates(family_id)

        assert len(result) == 1
        assert result[0].trigger_type == "approaching_date"
        assert result[0].data["title"] == "Wedding Anniversary"
        assert result[0].data["days_until"] == 5
        assert result[0].priority == "P2"

    @pytest.mark.asyncio
    async def test_urgent_date_gets_p1(self):
        family_id = uuid4()
        mock_db = AsyncMock()

        mock_date = MagicMock()
        mock_date.solar_date = date.today() + timedelta(days=2)
        mock_date.id = uuid4()
        mock_date.title = "Doctor Appointment"
        mock_date.date_type = "medical"
        mock_date.member_id = None

        dates_result = MagicMock()
        dates_result.scalars.return_value.all.return_value = [mock_date]

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        mock_db.execute = AsyncMock(side_effect=[dates_result, count_result])

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_approaching_dates(family_id)

        assert len(result) == 1
        assert result[0].priority == "P1"
        assert result[0].data["days_until"] == 2


# ---------------------------------------------------------------------------
# _scan_cold_relationships
# ---------------------------------------------------------------------------


class TestScanColdRelationships:

    @pytest.mark.asyncio
    async def test_no_members_returns_empty(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_cold_relationships(uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_cold_member_generates_trigger(self):
        family_id = uuid4()
        mock_db = AsyncMock()

        mock_member = MagicMock()
        mock_member.id = uuid4()
        mock_member.created_by = uuid4()
        mock_member.name = "Uncle Wang"
        mock_member.is_active = True

        members_result = MagicMock()
        members_result.scalars.return_value.all.return_value = [mock_member]
        mock_db.execute = AsyncMock(return_value=members_result)

        mock_temp = MagicMock()
        mock_temp.status = "cold"
        mock_temp.composite = 0.25

        triggerer = ProactiveTriggerer(mock_db)
        with patch(
            "src.modules.relationship.thermometer.compute_temperature",
            new_callable=AsyncMock,
            return_value=mock_temp,
        ):
            result = await triggerer._scan_cold_relationships(family_id)

        assert len(result) == 1
        assert result[0].trigger_type == "cold_relationship"
        assert result[0].data["member_name"] == "Uncle Wang"
        assert result[0].priority == "P2"

    @pytest.mark.asyncio
    async def test_frozen_member_gets_p1(self):
        family_id = uuid4()
        mock_db = AsyncMock()

        mock_member = MagicMock()
        mock_member.id = uuid4()
        mock_member.created_by = uuid4()
        mock_member.name = "Aunt Li"
        mock_member.is_active = True

        members_result = MagicMock()
        members_result.scalars.return_value.all.return_value = [mock_member]
        mock_db.execute = AsyncMock(return_value=members_result)

        mock_temp = MagicMock()
        mock_temp.status = "frozen"
        mock_temp.composite = 0.1

        triggerer = ProactiveTriggerer(mock_db)
        with patch(
            "src.modules.relationship.thermometer.compute_temperature",
            new_callable=AsyncMock,
            return_value=mock_temp,
        ):
            result = await triggerer._scan_cold_relationships(family_id)

        assert len(result) == 1
        assert result[0].priority == "P1"

    @pytest.mark.asyncio
    async def test_warm_member_skipped(self):
        family_id = uuid4()
        mock_db = AsyncMock()

        mock_member = MagicMock()
        mock_member.id = uuid4()
        mock_member.created_by = uuid4()
        mock_member.name = "Best Friend"
        mock_member.is_active = True

        members_result = MagicMock()
        members_result.scalars.return_value.all.return_value = [mock_member]
        mock_db.execute = AsyncMock(return_value=members_result)

        mock_temp = MagicMock()
        mock_temp.status = "warm"
        mock_temp.composite = 0.8

        triggerer = ProactiveTriggerer(mock_db)
        with patch(
            "src.modules.relationship.thermometer.compute_temperature",
            new_callable=AsyncMock,
            return_value=mock_temp,
        ):
            result = await triggerer._scan_cold_relationships(family_id)

        assert result == []


# ---------------------------------------------------------------------------
# _scan_stale_commitments
# ---------------------------------------------------------------------------


class TestScanStaleCommitments:

    @pytest.mark.asyncio
    async def test_no_stale_commitments(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_stale_commitments(uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_stale_vague_commitment(self):
        family_id = uuid4()
        mock_db = AsyncMock()

        now = datetime.now(timezone.utc)
        mock_commitment = MagicMock()
        mock_commitment.id = uuid4()
        mock_commitment.who = "Me"
        mock_commitment.what = "Visit grandma sometime"
        mock_commitment.to_whom = "Grandma"
        mock_commitment.commitment_type = "vague"
        mock_commitment.next_follow_up_at = now - timedelta(days=3)
        mock_commitment.follow_up_count = 0

        commitments_result = MagicMock()
        commitments_result.scalars.return_value.all.return_value = [mock_commitment]
        mock_db.execute = AsyncMock(return_value=commitments_result)

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_stale_commitments(family_id)

        assert len(result) == 1
        assert result[0].trigger_type == "stale_commitment"
        assert result[0].data["who"] == "Me"
        assert result[0].data["what"] == "Visit grandma sometime"
        assert result[0].priority == "P2"

    @pytest.mark.asyncio
    async def test_heavily_overdue_gets_p1(self):
        family_id = uuid4()
        mock_db = AsyncMock()

        now = datetime.now(timezone.utc)
        mock_commitment = MagicMock()
        mock_commitment.id = uuid4()
        mock_commitment.who = "Boss"
        mock_commitment.what = "Send report"
        mock_commitment.to_whom = "Client"
        mock_commitment.commitment_type = "conditional"
        mock_commitment.next_follow_up_at = now - timedelta(days=10)
        mock_commitment.follow_up_count = 2

        commitments_result = MagicMock()
        commitments_result.scalars.return_value.all.return_value = [mock_commitment]
        mock_db.execute = AsyncMock(return_value=commitments_result)

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_stale_commitments(family_id)

        assert len(result) == 1
        assert result[0].priority == "P1"
        assert result[0].data["days_overdue"] >= 7


# ---------------------------------------------------------------------------
# _scan_user_rhythm
# ---------------------------------------------------------------------------


def _make_histogram_rows(hour_counts):
    """Build mock rows for the histogram query.

    Args:
        hour_counts: list of (hour, count) tuples, already in DESC count order.
    """
    rows = []
    for hour, cnt in hour_counts:
        row = MagicMock()
        row.hour = hour
        row.cnt = cnt
        rows.append(row)
    return rows


class TestScanUserRhythm:

    @pytest.fixture
    def family_id(self):
        return uuid4()

    # -- No messages at all → empty --

    @pytest.mark.asyncio
    async def test_no_messages_returns_empty(self, family_id):
        mock_db = AsyncMock()
        # Histogram query returns no rows
        histogram_result = MagicMock()
        histogram_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=histogram_result)

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_user_rhythm(family_id)
        assert result == []

    # -- Too few total messages → empty --

    @pytest.mark.asyncio
    async def test_too_few_messages_returns_empty(self, family_id):
        mock_db = AsyncMock()
        # Only 3 total messages (below _RHYTHM_MIN_TOTAL_MESSAGES=5)
        rows = _make_histogram_rows([(9, 2), (14, 1)])
        histogram_result = MagicMock()
        histogram_result.all.return_value = rows
        mock_db.execute = AsyncMock(return_value=histogram_result)

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_user_rhythm(family_id)
        assert result == []

    # -- Peak hours below minimum peak threshold → empty --

    @pytest.mark.asyncio
    async def test_no_peak_above_threshold_returns_empty(self, family_id):
        mock_db = AsyncMock()
        # Total = 6 (above 5), but no single hour has >= 3 messages
        rows = _make_histogram_rows([(8, 2), (10, 2), (14, 2)])
        histogram_result = MagicMock()
        histogram_result.all.return_value = rows
        mock_db.execute = AsyncMock(return_value=histogram_result)

        triggerer = ProactiveTriggerer(mock_db)
        result = await triggerer._scan_user_rhythm(family_id)
        assert result == []

    # -- Peak hour not yet reached (current_hour < peak + tolerance) → empty --

    @pytest.mark.asyncio
    async def test_current_hour_before_peak_returns_empty(self, family_id):
        mock_db = AsyncMock()
        # Peak at hour 20 with 5 messages, total 10
        rows = _make_histogram_rows([(20, 5), (8, 5)])
        histogram_result = MagicMock()
        histogram_result.all.return_value = rows
        mock_db.execute = AsyncMock(return_value=histogram_result)

        triggerer = ProactiveTriggerer(mock_db)
        # Freeze time to hour 15 UTC — well before peak at 20
        fake_now = datetime(2026, 2, 18, 15, 30, 0, tzinfo=timezone.utc)
        with patch(
            "src.modules.curation.services.proactive_triggerer.utc_now",
            return_value=fake_now,
        ):
            result = await triggerer._scan_user_rhythm(family_id)
        assert result == []

    # -- User already interacted today → empty --

    @pytest.mark.asyncio
    async def test_user_interacted_today_no_trigger(self, family_id):
        mock_db = AsyncMock()
        # Peak at hour 9, 5 messages; total 8
        rows = _make_histogram_rows([(9, 5), (14, 3)])
        histogram_result = MagicMock()
        histogram_result.all.return_value = rows

        # Today-check returns count=2 (user already interacted)
        today_check_result = MagicMock()
        today_check_result.scalar.return_value = 2

        mock_db.execute = AsyncMock(
            side_effect=[histogram_result, today_check_result, today_check_result]
        )

        triggerer = ProactiveTriggerer(mock_db)
        fake_now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
        with patch(
            "src.modules.curation.services.proactive_triggerer.utc_now",
            return_value=fake_now,
        ):
            result = await triggerer._scan_user_rhythm(family_id)
        assert result == []

    # -- Missed peak hour, no interaction today → trigger generated --

    @pytest.mark.asyncio
    async def test_missed_peak_generates_trigger(self, family_id):
        mock_db = AsyncMock()
        # Peak at hour 9, 6 messages; total 10
        rows = _make_histogram_rows([(9, 6), (21, 4)])
        histogram_result = MagicMock()
        histogram_result.all.return_value = rows

        # Today-check returns count=0 for hour 9 (missed it)
        today_check_result = MagicMock()
        today_check_result.scalar.return_value = 0

        mock_db.execute = AsyncMock(
            side_effect=[histogram_result, today_check_result]
        )

        triggerer = ProactiveTriggerer(mock_db)
        # Current hour = 12, past peak 9 + 1 tolerance
        fake_now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
        with patch(
            "src.modules.curation.services.proactive_triggerer.utc_now",
            return_value=fake_now,
        ):
            result = await triggerer._scan_user_rhythm(family_id)

        assert len(result) == 1
        trigger = result[0]
        assert trigger.trigger_type == "user_rhythm"
        assert trigger.family_id == family_id
        assert trigger.priority == "P3"
        assert trigger.data["peak_hour_utc"] == 9
        assert trigger.data["messages_at_peak"] == 6
        assert trigger.data["current_hour_utc"] == 12
        assert trigger.data["total_messages_in_window"] == 10
        assert trigger.data["lookback_days"] == 14

    # -- Two missed peaks → two triggers --

    @pytest.mark.asyncio
    async def test_two_missed_peaks_generate_two_triggers(self, family_id):
        mock_db = AsyncMock()
        # Peak at hour 8 (7 msgs) and hour 14 (5 msgs), total 12
        rows = _make_histogram_rows([(8, 7), (14, 5)])
        histogram_result = MagicMock()
        histogram_result.all.return_value = rows

        # Both today-checks return 0
        zero_result_1 = MagicMock()
        zero_result_1.scalar.return_value = 0
        zero_result_2 = MagicMock()
        zero_result_2.scalar.return_value = 0

        mock_db.execute = AsyncMock(
            side_effect=[histogram_result, zero_result_1, zero_result_2]
        )

        triggerer = ProactiveTriggerer(mock_db)
        # Current hour = 18, past both peaks + tolerance
        fake_now = datetime(2026, 2, 18, 18, 0, 0, tzinfo=timezone.utc)
        with patch(
            "src.modules.curation.services.proactive_triggerer.utc_now",
            return_value=fake_now,
        ):
            result = await triggerer._scan_user_rhythm(family_id)

        assert len(result) == 2
        peak_hours = {t.data["peak_hour_utc"] for t in result}
        assert peak_hours == {8, 14}

    # -- One peak missed, one not yet reached → only one trigger --

    @pytest.mark.asyncio
    async def test_one_peak_missed_one_not_reached(self, family_id):
        mock_db = AsyncMock()
        # Peak at hour 8 (5 msgs) and hour 20 (4 msgs), total 12
        rows = _make_histogram_rows([(8, 5), (20, 4)])
        histogram_result = MagicMock()
        histogram_result.all.return_value = rows

        # Hour 8 check returns 0 (missed), hour 20 won't be checked (not yet reached)
        zero_result = MagicMock()
        zero_result.scalar.return_value = 0

        mock_db.execute = AsyncMock(
            side_effect=[histogram_result, zero_result]
        )

        triggerer = ProactiveTriggerer(mock_db)
        # Current hour = 12: past 8+1=9, but before 20+1=21
        fake_now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
        with patch(
            "src.modules.curation.services.proactive_triggerer.utc_now",
            return_value=fake_now,
        ):
            result = await triggerer._scan_user_rhythm(family_id)

        assert len(result) == 1
        assert result[0].data["peak_hour_utc"] == 8
