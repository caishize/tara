"""Tests for holiday signal collector.

Verifies that collect_holiday_signals produces ONE signal per holiday
with all eligible persons grouped together, replacing the old per-person
rule_engine approach.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_holiday(name: str, holiday_date: date, description: str = "") -> MagicMock:
    h = MagicMock()
    h.name = name
    h.date = holiday_date
    h.description = description
    return h


def _make_member(
    name: str,
    member_id: str | None = None,
    relationship: str = "",
    importance: int = 5,
) -> MagicMock:
    m = MagicMock()
    m.id = uuid.UUID(member_id) if member_id else uuid.uuid4()
    m.name = name
    m.relationship = relationship
    m.importance = importance
    return m


def _mock_db_with_members(members: list) -> AsyncMock:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = members
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


# ===========================================================================
# Tests
# ===========================================================================


class TestCollectHolidaySignals:
    """Verify holiday signals produce one signal per holiday with grouped persons."""

    @pytest.mark.asyncio
    async def test_single_holiday_groups_all_eligible_members(self):
        """3 members eligible → 1 holiday signal with 3 persons."""
        from src.modules.insight.signals.holiday_signals import collect_holiday_signals

        target_date = date(2026, 3, 19)
        holidays = [_make_holiday("龙抬头", target_date + timedelta(days=2))]

        members = [
            _make_member("周明", relationship="朋友", importance=7),
            _make_member("强哥", relationship="朋友", importance=6),
            _make_member("用户太太", relationship="配偶", importance=9),
        ]

        db = _mock_db_with_members(members)

        with patch(
            "src.modules.date_manager.calendar_adapter.BaiduCalendarAdapter"
        ) as mock_adapter_cls:
            adapter_inst = AsyncMock()
            adapter_inst.fetch_holidays = AsyncMock(return_value=holidays)
            adapter_inst.close = AsyncMock()
            mock_adapter_cls.return_value = adapter_inst

            with patch(
                "src.modules.date_manager.holiday_models.get_holiday_category",
                return_value="minor",
            ):
                signals = await collect_holiday_signals(
                    db=db,
                    family_id=uuid.uuid4(),
                    target_date=target_date,
                )

        assert len(signals) == 1
        sig = signals[0]
        assert sig["signal_type"] == "holiday"
        assert sig["holiday_name"] == "龙抬头"
        assert sig["days_until"] == 2
        assert len(sig["associated_persons"]) == 3

        names = [p["name"] for p in sig["associated_persons"]]
        assert "周明" in names
        assert "强哥" in names
        assert "用户太太" in names

    @pytest.mark.asyncio
    async def test_two_holidays_produce_two_signals(self):
        """Two holidays → two signals, each with their own grouped persons."""
        from src.modules.insight.signals.holiday_signals import collect_holiday_signals

        target_date = date(2026, 3, 19)
        holidays = [
            _make_holiday("龙抬头", target_date + timedelta(days=2)),
            _make_holiday("春分", target_date + timedelta(days=1)),
        ]

        members = [
            _make_member("周明", importance=7),
            _make_member("用户太太", importance=9),
        ]

        db = _mock_db_with_members(members)

        with patch(
            "src.modules.date_manager.calendar_adapter.BaiduCalendarAdapter"
        ) as mock_adapter_cls:
            adapter_inst = AsyncMock()
            adapter_inst.fetch_holidays = AsyncMock(return_value=holidays)
            adapter_inst.close = AsyncMock()
            mock_adapter_cls.return_value = adapter_inst

            with patch(
                "src.modules.date_manager.holiday_models.get_holiday_category",
                return_value="minor",
            ):
                signals = await collect_holiday_signals(
                    db=db,
                    family_id=uuid.uuid4(),
                    target_date=target_date,
                )

        assert len(signals) == 2
        holiday_names = {s["holiday_name"] for s in signals}
        assert holiday_names == {"龙抬头", "春分"}

    @pytest.mark.asyncio
    async def test_no_upcoming_holidays_returns_empty(self):
        """No holidays within window → empty list."""
        from src.modules.insight.signals.holiday_signals import collect_holiday_signals

        target_date = date(2026, 6, 1)
        holidays = [_make_holiday("龙抬头", date(2026, 3, 21))]  # past

        db = _mock_db_with_members([_make_member("周明", importance=7)])

        with patch(
            "src.modules.date_manager.calendar_adapter.BaiduCalendarAdapter"
        ) as mock_adapter_cls:
            adapter_inst = AsyncMock()
            adapter_inst.fetch_holidays = AsyncMock(return_value=holidays)
            adapter_inst.close = AsyncMock()
            mock_adapter_cls.return_value = adapter_inst

            signals = await collect_holiday_signals(
                db=db,
                family_id=uuid.uuid4(),
                target_date=target_date,
            )

        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_no_eligible_members_for_holiday_skips_it(self):
        """All members outside tier window → no signal for that holiday."""
        from src.modules.insight.signals.holiday_signals import collect_holiday_signals

        target_date = date(2026, 3, 1)  # 20 days before holiday
        holidays = [_make_holiday("龙抬头", date(2026, 3, 21))]

        # Low importance = general tier = 3 day window, but 20 days away
        members = [_make_member("远房亲戚", importance=1)]

        db = _mock_db_with_members(members)

        with patch(
            "src.modules.date_manager.calendar_adapter.BaiduCalendarAdapter"
        ) as mock_adapter_cls:
            adapter_inst = AsyncMock()
            adapter_inst.fetch_holidays = AsyncMock(return_value=holidays)
            adapter_inst.close = AsyncMock()
            mock_adapter_cls.return_value = adapter_inst

            with patch(
                "src.modules.date_manager.holiday_models.get_holiday_category",
                return_value="minor",
            ):
                signals = await collect_holiday_signals(
                    db=db,
                    family_id=uuid.uuid4(),
                    target_date=target_date,
                )

        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_person_names_summary_included(self):
        """Signal includes a comma-separated person_names_summary."""
        from src.modules.insight.signals.holiday_signals import collect_holiday_signals

        target_date = date(2026, 3, 19)
        holidays = [_make_holiday("龙抬头", target_date + timedelta(days=2))]

        members = [
            _make_member("周明", importance=7),
            _make_member("强哥", importance=6),
        ]

        db = _mock_db_with_members(members)

        with patch(
            "src.modules.date_manager.calendar_adapter.BaiduCalendarAdapter"
        ) as mock_adapter_cls:
            adapter_inst = AsyncMock()
            adapter_inst.fetch_holidays = AsyncMock(return_value=holidays)
            adapter_inst.close = AsyncMock()
            mock_adapter_cls.return_value = adapter_inst

            with patch(
                "src.modules.date_manager.holiday_models.get_holiday_category",
                return_value="minor",
            ):
                signals = await collect_holiday_signals(
                    db=db,
                    family_id=uuid.uuid4(),
                    target_date=target_date,
                )

        assert len(signals) == 1
        summary = signals[0]["person_names_summary"]
        assert "周明" in summary
        assert "强哥" in summary

    @pytest.mark.asyncio
    async def test_adapter_failure_returns_empty(self):
        """BaiduCalendarAdapter failure → empty list, no crash."""
        from src.modules.insight.signals.holiday_signals import collect_holiday_signals

        db = _mock_db_with_members([])

        with patch(
            "src.modules.date_manager.calendar_adapter.BaiduCalendarAdapter"
        ) as mock_adapter_cls:
            adapter_inst = AsyncMock()
            adapter_inst.fetch_holidays = AsyncMock(side_effect=Exception("API down"))
            adapter_inst.close = AsyncMock()
            mock_adapter_cls.return_value = adapter_inst

            signals = await collect_holiday_signals(
                db=db,
                family_id=uuid.uuid4(),
                target_date=date(2026, 3, 19),
            )

        assert signals == []
