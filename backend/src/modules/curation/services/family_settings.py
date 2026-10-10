"""Family-level curation settings helpers."""

import json
import logging
from dataclasses import dataclass
from typing import Dict
from uuid import UUID
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.utils.timezone import DEFAULT_TIMEZONE, DEFAULT_TIMEZONE_NAME
from ...insight.models import UserInsightSettings


DEFAULT_PRIORITY_WEIGHTS: Dict[str, float] = {
    "urgency": 0.30,
    "severity": 0.25,
    "stakeholder": 0.25,
    "irrecoverability": 0.20,
}


@dataclass(frozen=True)
class FamilyCurationSettings:
    """Effective curation settings for a family."""

    curation_days_ahead: int
    timezone_name: str
    timezone: ZoneInfo


async def get_family_curation_settings(
    session: AsyncSession,
    family_id: UUID,
    *,
    fallback_days_ahead: int = 14,
) -> FamilyCurationSettings:
    """Load effective curation settings from user_insight_settings."""
    stmt = (
        select(
            UserInsightSettings.curation_days_ahead,
            UserInsightSettings.timezone,
        )
        .where(UserInsightSettings.family_id == family_id)
        .order_by(UserInsightSettings.updated_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()

    days_ahead = fallback_days_ahead
    tz_name = DEFAULT_TIMEZONE_NAME
    if row is not None:
        if row[0] is not None:
            try:
                days_ahead = max(1, min(int(row[0]), 30))
            except (TypeError, ValueError):
                days_ahead = fallback_days_ahead
        if row[1]:
            tz_name = str(row[1])

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz_name = DEFAULT_TIMEZONE_NAME
        tz = DEFAULT_TIMEZONE

    return FamilyCurationSettings(
        curation_days_ahead=days_ahead,
        timezone_name=tz_name,
        timezone=tz,
    )


async def get_priority_weights(family_id: UUID) -> Dict[str, float]:
    """Read family-specific priority weights from Redis.

    Falls back to DEFAULT_PRIORITY_WEIGHTS if no custom weights exist.
    """
    try:
        from ....core.cache import redis_client
        key = f"curation:weights:{family_id}"
        raw = await redis_client.get(key)
        if raw:
            weights = json.loads(raw)
            merged = {**DEFAULT_PRIORITY_WEIGHTS, **weights}
            return merged
    except Exception:
        logger.warning("Failed to read priority weights from Redis for family %s", family_id, exc_info=True)
    return dict(DEFAULT_PRIORITY_WEIGHTS)


async def update_priority_weights(
    family_id: UUID,
    overrides: Dict[str, float],
) -> None:
    """Update family-specific priority weights in Redis."""
    try:
        from ....core.cache import redis_client
        key = f"curation:weights:{family_id}"
        current = await get_priority_weights(family_id)
        merged = {**current, **overrides}
        # Normalize to sum=1.0
        total = sum(merged.values())
        if total > 0:
            merged = {k: v / total for k, v in merged.items()}
        await redis_client.set(key, json.dumps(merged))
    except Exception:
        logger.warning("Failed to update priority weights in Redis for family %s", family_id, exc_info=True)
