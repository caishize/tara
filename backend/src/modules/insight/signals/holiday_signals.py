"""Collect upcoming holiday signals with associated family members.

Fetches holidays from BaiduCalendarAdapter, cross-references with active
family members filtered by contact tier, and produces one signal per holiday
containing all eligible persons. The LLM then generates merged insights
(one per holiday, not one per person).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from .tier_utils import resolve_tier

logger = get_logger(__name__)

# Contact-tier-based advance notice windows (days before holiday).
# Higher-tier contacts get earlier reminders.
_TIER_HOLIDAY_WINDOWS = {
    "core": 14,
    "important": 7,
    "general": 3,
}
_DEFAULT_HOLIDAY_WINDOW = 7


async def collect_holiday_signals(
    db: AsyncSession,
    family_id: UUID,
    target_date: date,
) -> List[Dict[str, Any]]:
    """Return upcoming holiday signals with associated family members.

    Each signal represents ONE holiday with all eligible persons grouped together,
    so the LLM can generate one merged greeting insight per holiday.
    """
    from ...date_manager.calendar_adapter import BaiduCalendarAdapter
    from ...date_manager.holiday_models import (
        MAJOR_HOLIDAYS,
        MINOR_HOLIDAYS,
        get_holiday_category,
    )
    from ...member.models.person_profile import PersonProfile
    from ...member.models.enums import ProfileStatus

    # Step 1: Fetch holidays for the target year
    adapter = BaiduCalendarAdapter()
    try:
        holidays = await adapter.fetch_holidays(target_date.year)
    except Exception as exc:
        logger.warning("Holiday signal collection failed (fetch): %s", exc)
        return []
    finally:
        await adapter.close()

    # Step 2: Filter upcoming holidays within their category-based window
    upcoming = []
    for h in holidays:
        days_until = (h.date - target_date).days
        if days_until < 0:
            continue
        max_window = 30 if h.name in MAJOR_HOLIDAYS else (
            7 if h.name in MINOR_HOLIDAYS else 3
        )
        if days_until <= max_window:
            upcoming.append((h, days_until))

    if not upcoming:
        return []

    # Step 3: Fetch active family members
    stmt = (
        select(PersonProfile)
        .where(
            and_(
                PersonProfile.family_id == family_id,
                PersonProfile.status == ProfileStatus.ACTIVE.value,
            )
        )
        .limit(30)
    )
    result = await db.execute(stmt)
    members = list(result.scalars().all())

    if not members:
        return []

    # Step 4: For each holiday, group eligible members (filtered by tier window)
    signals: List[Dict[str, Any]] = []

    for holiday, days_until in upcoming:
        eligible_persons: List[Dict[str, Any]] = []
        is_major = holiday.name in MAJOR_HOLIDAYS

        for member in members:
            importance = getattr(member, "importance", 5)
            tier = resolve_tier(importance)
            tier_key = tier.value if hasattr(tier, "value") else str(tier)
            tier_window = _TIER_HOLIDAY_WINDOWS.get(
                tier_key, _DEFAULT_HOLIDAY_WINDOW,
            )

            if days_until > tier_window:
                continue

            eligible_persons.append({
                "person_id": str(member.id),
                "name": getattr(member, "name", ""),
                "relationship": getattr(member, "relationship", ""),
                "importance": importance,
            })

        if not eligible_persons:
            continue

        names = [p["name"] for p in eligible_persons if p["name"]]

        signals.append({
            "signal_type": "holiday",
            "holiday_name": holiday.name,
            "holiday_date": holiday.date.isoformat(),
            "days_until": days_until,
            "is_major": is_major,
            "category": get_holiday_category(holiday.name),
            "associated_persons": eligible_persons,
            "person_names_summary": "、".join(names) if names else "",
            "description": holiday.description,
        })

    return signals
