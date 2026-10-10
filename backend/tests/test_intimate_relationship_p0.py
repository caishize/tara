"""Tests for intimate-relationship P0 fast-path in HybridPriorityEngine.

Covers:
- Spouse/parent/child + birthday/anniversary/family → unconditional P0
- Non-intimate relations do NOT trigger the fast-path
- Non-important-date event types do NOT trigger the fast-path
- Secretary note personalisation by relation type
- Intimate events are excluded from the LLM calibration needs_cal list

Source: src.modules.curation.services.priority_engine
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.curation.services.priority_engine import (
    EnhancedPriorityScore,
    HybridPriorityEngine,
    _IMPORTANT_DATE_EVENT_TYPES,
    _INTIMATE_RELATION_TYPES,
    _build_intimate_note,
)
from src.modules.curation.services.priority_score import PriorityScore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event_data(
    *,
    event_type: str = "birthday",
    member_ids: List[str] = None,
    title: str = "Test Event",
    priority: str = "normal",
    association_count: int = 0,
) -> dict:
    """Build an event_data dict for the priority engine."""
    return {
        "event_id": str(uuid.uuid4()),
        "title": title,
        "event_type": event_type,
        "normalized_start": datetime.now(timezone.utc).isoformat(),
        "location": "Home",
        "priority": priority,
        "association_count": association_count,
        "has_booking": False,
        "member_ids": member_ids or [],
    }


def _make_engine(
    db: AsyncMock = None,
    calibration_enabled: bool = False,
) -> HybridPriorityEngine:
    """Build a HybridPriorityEngine with a mock DB session."""
    return HybridPriorityEngine(
        db=db or AsyncMock(),
        calibration_enabled=calibration_enabled,
    )


# ===================================================================
# Test: _check_intimate_relationship_boost() direct
# ===================================================================

class TestCheckIntimateRelationshipBoost:
    """Tests for the internal _check_intimate_relationship_boost method."""

    @pytest.mark.asyncio
    async def test_spouse_birthday_returns_p0_note(self):
        """Spouse + birthday → returns a secretary note (P0 trigger)."""
        member_id = str(uuid.uuid4())
        event_data = _make_event_data(
            event_type="birthday",
            member_ids=[member_id],
        )
        family_id = uuid.uuid4()

        engine = _make_engine()
        engine._query_intimate_members = AsyncMock(
            return_value=[("spouse", "Alice")]
        )

        note = await engine._check_intimate_relationship_boost(
            event_data, family_id,
        )

        assert note is not None
        assert "配偶" in note
        assert "Alice" in note
        assert "生日" in note

    @pytest.mark.asyncio
    async def test_parent_anniversary_returns_p0_note(self):
        """Parent + anniversary → returns a secretary note (P0 trigger)."""
        member_id = str(uuid.uuid4())
        event_data = _make_event_data(
            event_type="anniversary",
            member_ids=[member_id],
        )
        family_id = uuid.uuid4()

        engine = _make_engine()
        engine._query_intimate_members = AsyncMock(
            return_value=[("mother", "Mom")]
        )

        note = await engine._check_intimate_relationship_boost(
            event_data, family_id,
        )

        assert note is not None
        assert "父母" in note
        assert "Mom" in note
        assert "纪念日" in note

    @pytest.mark.asyncio
    async def test_child_family_event_returns_p0_note(self):
        """Child + family event → returns a secretary note (P0 trigger)."""
        member_id = str(uuid.uuid4())
        event_data = _make_event_data(
            event_type="family",
            member_ids=[member_id],
        )
        family_id = uuid.uuid4()

        engine = _make_engine()
        engine._query_intimate_members = AsyncMock(
            return_value=[("daughter", "Emily")]
        )

        note = await engine._check_intimate_relationship_boost(
            event_data, family_id,
        )

        assert note is not None
        assert "子女" in note
        assert "Emily" in note
        assert "家庭活动" in note

    @pytest.mark.asyncio
    async def test_non_intimate_relation_returns_none(self):
        """Friend (not in _INTIMATE_RELATION_TYPES) → None (normal path)."""
        member_id = str(uuid.uuid4())
        event_data = _make_event_data(
            event_type="birthday",
            member_ids=[member_id],
        )
        family_id = uuid.uuid4()

        engine = _make_engine()
        engine._query_intimate_members = AsyncMock(return_value=[])

        note = await engine._check_intimate_relationship_boost(
            event_data, family_id,
        )

        assert note is None

    @pytest.mark.asyncio
    async def test_non_important_date_event_returns_none(self):
        """Spouse + meeting (not birthday/anniversary/family) → None."""
        member_id = str(uuid.uuid4())
        event_data = _make_event_data(
            event_type="meeting",
            member_ids=[member_id],
        )
        family_id = uuid.uuid4()

        engine = _make_engine()
        # Should never reach _query_intimate_members for non-important-date types
        engine._query_intimate_members = AsyncMock(return_value=[("spouse", "Bob")])

        note = await engine._check_intimate_relationship_boost(
            event_data, family_id,
        )

        assert note is None
        engine._query_intimate_members.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_member_ids_returns_none(self):
        """Birthday event with no member_ids → None."""
        event_data = _make_event_data(
            event_type="birthday",
            member_ids=[],
        )
        family_id = uuid.uuid4()

        engine = _make_engine()
        engine._query_intimate_members = AsyncMock()

        note = await engine._check_intimate_relationship_boost(
            event_data, family_id,
        )

        assert note is None
        engine._query_intimate_members.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_db_failure_returns_none_gracefully(self):
        """If the DB query fails, return None (proceed with normal scoring)."""
        member_id = str(uuid.uuid4())
        event_data = _make_event_data(
            event_type="birthday",
            member_ids=[member_id],
        )
        family_id = uuid.uuid4()

        engine = _make_engine()
        engine._query_intimate_members = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )

        note = await engine._check_intimate_relationship_boost(
            event_data, family_id,
        )

        assert note is None

    @pytest.mark.asyncio
    async def test_invalid_member_id_format_returns_none(self):
        """Invalid UUID in member_ids is silently skipped."""
        event_data = _make_event_data(
            event_type="birthday",
            member_ids=["not-a-uuid", "also-invalid"],
        )
        family_id = uuid.uuid4()

        engine = _make_engine()
        engine._query_intimate_members = AsyncMock()

        note = await engine._check_intimate_relationship_boost(
            event_data, family_id,
        )

        assert note is None
        engine._query_intimate_members.assert_not_awaited()


# ===================================================================
# Test: score_batch integration - intimate events skip calibration
# ===================================================================

class TestScoreBatchIntimateBypass:
    """Verify that intimate-boost events are excluded from LLM calibration."""

    @pytest.mark.asyncio
    async def test_intimate_event_gets_p0_score(self):
        """Intimate birthday event → P0 composite (>= 0.8) in score_batch."""
        member_id = str(uuid.uuid4())
        event_data = _make_event_data(
            event_type="birthday",
            member_ids=[member_id],
            title="Mom's Birthday",
        )
        family_id = uuid.uuid4()

        engine = _make_engine(calibration_enabled=True)
        engine._query_intimate_members = AsyncMock(
            return_value=[("mother", "Mom")]
        )
        engine._calibrate_batch = AsyncMock(return_value=[])

        results = await engine.score_batch(
            events=[event_data],
            family_id=family_id,
        )

        assert len(results) == 1
        score = results[0]
        assert score.priority_level == "P0"
        assert score.composite >= 0.8
        assert score.secretary_note is not None
        assert "父母" in score.secretary_note

    @pytest.mark.asyncio
    async def test_intimate_events_excluded_from_calibration_batch(self):
        """Intimate events should NOT appear in the calibration call list."""
        member_id = str(uuid.uuid4())
        intimate_event = _make_event_data(
            event_type="birthday",
            member_ids=[member_id],
            title="Wife's Birthday",
        )
        normal_event = _make_event_data(
            event_type="meeting",
            title="Team Standup",
            association_count=5,  # triggers calibration need
        )
        family_id = uuid.uuid4()

        engine = _make_engine(calibration_enabled=True)
        engine._query_intimate_members = AsyncMock(
            return_value=[("spouse", "Wife")]
        )
        # Mock calibration to return a result for the normal event
        engine._calibrate_batch = AsyncMock(return_value=[None])

        results = await engine.score_batch(
            events=[intimate_event, normal_event],
            family_id=family_id,
        )

        assert len(results) == 2
        # First event: intimate P0
        assert results[0].priority_level == "P0"
        assert results[0].secretary_note is not None

        # Calibrate should only be called with the normal event
        if engine._calibrate_batch.called:
            cal_events = engine._calibrate_batch.call_args[0][0]
            cal_event_ids = [e.get("event_id") for e in cal_events]
            assert intimate_event["event_id"] not in cal_event_ids

    @pytest.mark.asyncio
    async def test_mixed_batch_preserves_order(self):
        """score_batch result order matches input order even with intimate mix."""
        mid1 = str(uuid.uuid4())
        mid2 = str(uuid.uuid4())
        ev_intimate = _make_event_data(
            event_type="anniversary",
            member_ids=[mid1],
            title="Anniversary",
        )
        ev_normal = _make_event_data(
            event_type="reminder",
            title="Water plants",
        )
        ev_intimate2 = _make_event_data(
            event_type="family",
            member_ids=[mid2],
            title="Family Dinner",
        )
        family_id = uuid.uuid4()

        engine = _make_engine(calibration_enabled=False)

        # First call → intimate_info for ev_intimate (spouse)
        # ev_normal has event_type="reminder" (not in _IMPORTANT_DATE_EVENT_TYPES)
        # so _query_intimate_members is NOT called for it.
        # Second call → intimate_info for ev_intimate2 (child)
        engine._query_intimate_members = AsyncMock(
            side_effect=[
                [("partner", "Spouse")],
                [("son", "Junior")],
            ]
        )

        results = await engine.score_batch(
            events=[ev_intimate, ev_normal, ev_intimate2],
            family_id=family_id,
        )

        assert len(results) == 3
        assert results[0].priority_level == "P0"  # anniversary + partner
        assert results[1].priority_level != "P0"  # normal reminder
        assert results[2].priority_level == "P0"  # family + son


# ===================================================================
# Test: secretary note personalisation
# ===================================================================

class TestSecretaryNotePersonalisation:
    """Secretary notes should differ by relation type."""

    def test_spouse_note_mentions_companion_time(self):
        note = _build_intimate_note("spouse", "生日", "Alice")

        assert "配偶" in note
        assert "Alice" in note
        assert "陪伴时间" in note

    def test_parent_note_mentions_gift(self):
        note = _build_intimate_note("father", "纪念日", "Dad")

        assert "父母" in note
        assert "Dad" in note
        assert "礼物" in note or "祝福" in note

    def test_mother_note_same_as_parent(self):
        note = _build_intimate_note("mother", "生日", "妈妈")

        assert "父母" in note
        assert "妈妈" in note

    def test_child_note_mentions_full_attendance(self):
        note = _build_intimate_note("daughter", "家庭活动", "Emily")

        assert "子女" in note
        assert "Emily" in note
        assert "全程陪伴" in note

    def test_parent_in_law_treated_as_parent(self):
        note = _build_intimate_note("mother_in_law", "生日", "婆婆")

        assert "父母" in note
        assert "婆婆" in note

    def test_empty_member_name_still_works(self):
        note = _build_intimate_note("spouse", "生日", "")

        assert "配偶" in note
        assert "生日" in note

    def test_generic_intimate_fallback(self):
        """Unknown intimate type → generic fallback note."""
        note = _build_intimate_note("unknown_type", "生日", "Relative")

        assert "亲密关系成员" in note
        assert "Relative" in note


# ===================================================================
# Test: constants sanity
# ===================================================================

class TestIntimateConstants:
    """Verify intimate-relationship constants are correctly defined."""

    def test_intimate_relation_types_include_core_family(self):
        assert "spouse" in _INTIMATE_RELATION_TYPES
        assert "partner" in _INTIMATE_RELATION_TYPES
        assert "father" in _INTIMATE_RELATION_TYPES
        assert "mother" in _INTIMATE_RELATION_TYPES
        assert "son" in _INTIMATE_RELATION_TYPES
        assert "daughter" in _INTIMATE_RELATION_TYPES
        assert "child" in _INTIMATE_RELATION_TYPES
        assert "parent" in _INTIMATE_RELATION_TYPES

    def test_intimate_relation_types_include_in_laws(self):
        assert "father_in_law" in _INTIMATE_RELATION_TYPES
        assert "mother_in_law" in _INTIMATE_RELATION_TYPES
        assert "parent_in_law" in _INTIMATE_RELATION_TYPES

    def test_intimate_relation_types_exclude_non_intimate(self):
        assert "friend" not in _INTIMATE_RELATION_TYPES
        assert "colleague" not in _INTIMATE_RELATION_TYPES
        assert "acquaintance" not in _INTIMATE_RELATION_TYPES

    def test_important_date_event_types(self):
        assert "birthday" in _IMPORTANT_DATE_EVENT_TYPES
        assert "anniversary" in _IMPORTANT_DATE_EVENT_TYPES
        assert "family" in _IMPORTANT_DATE_EVENT_TYPES

    def test_important_date_excludes_regular_events(self):
        assert "meeting" not in _IMPORTANT_DATE_EVENT_TYPES
        assert "travel" not in _IMPORTANT_DATE_EVENT_TYPES
        assert "business_trip" not in _IMPORTANT_DATE_EVENT_TYPES
