"""Collect relationship temperature signals.

Extracted from InsightSignalCollector._collect_relationship_signals.
Uses the shared ContactTier enum and resolve_tier helper.

Enhanced with multi-dimensional RelationshipHealth model (G9):
- quality_score: interaction depth
- reciprocity_ratio: who initiates contact
- baseline_gap_days: normal contact interval
- trend: warming / stable / cooling
"""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger

logger = get_logger(__name__)

from ...relationship.models import ContactTier
from .tier_utils import resolve_tier

# ContactTier-based thresholds: trigger if no contact for N+ days.
# Contacts that fall below GENERAL importance still get a longer window.
_TIER_CONTACT_WINDOWS: Dict[ContactTier, int] = {
    ContactTier.CORE: 7,        # 至亲
    ContactTier.IMPORTANT: 14,  # 挚友
    ContactTier.GENERAL: 90,    # 一般 (also covers acquaintances)
}

_ACQUAINTANCE_CONTACT_WINDOW = 180  # importance < 3 (acquaintance level)


async def collect_relationship_signals(
    db: AsyncSession,
    family_id: UUID,
    user_id: UUID | None = None,
) -> List[Dict[str, Any]]:
    """Return contacts whose last interaction exceeds their tier window.

    When user_id is provided, enriches each signal with multi-dimensional
    RelationshipHealth data (quality, reciprocity, baseline, trend).
    Suppresses reminders for one-sided relationships (reciprocity < 0.2).
    Boosts urgency for cooling important relationships.
    """
    from ...member.models import PersonProfile
    from ...member.models.enums import ProfileStatus
    from ..relationship_health import (
        RelationshipTrend,
        assess_relationship_health,
        RECIPROCITY_SUPPRESSION_THRESHOLD,
    )

    stmt = (
        select(PersonProfile)
        .where(
            and_(
                PersonProfile.family_id == family_id,
                PersonProfile.status == ProfileStatus.ACTIVE.value,
            )
        )
        .limit(20)
    )
    result = await db.execute(stmt)
    members = list(result.scalars().all())

    signals: List[Dict[str, Any]] = []
    for member in members:
        days_since = (
            member.days_since_last_contact()
            if hasattr(member, "days_since_last_contact")
            else None
        )
        if days_since is None:
            continue

        importance = getattr(member, "importance", 5)
        tier = resolve_tier(importance)

        # Acquaintance-level contacts (importance < 3) get a longer window
        if importance < 3:
            threshold = _ACQUAINTANCE_CONTACT_WINDOW
        else:
            threshold = _TIER_CONTACT_WINDOWS[tier]

        if days_since < threshold:
            continue

        signal: Dict[str, Any] = {
            "person_id": str(member.id),
            "person_name": member.name,
            "relationship": getattr(member, "relationship", None),
            "days_since_contact": days_since,
            "importance": importance,
            "contact_tier": tier.value,
        }

        # Enrich with multi-dimensional health if user_id available
        if user_id is not None:
            try:
                health = await assess_relationship_health(
                    db, user_id, member.id,
                )
                signal["health"] = {
                    "quality_score": health.quality_score,
                    "reciprocity_ratio": health.reciprocity_ratio,
                    "baseline_gap_days": health.baseline_gap_days,
                    "trend": health.trend.value,
                    "overall_score": health.overall_score,
                    "data_sufficient": health.data_sufficient,
                }

                # Suppress one-sided relationships (always user initiating)
                if (
                    health.data_sufficient
                    and health.reciprocity_ratio < RECIPROCITY_SUPPRESSION_THRESHOLD
                ):
                    signal["suppressed"] = True
                    signal["suppression_reason"] = "one_sided_relationship"
                    continue  # Skip this signal entirely

                # Boost urgency for cooling important relationships
                if (
                    health.trend == RelationshipTrend.COOLING
                    and tier in (ContactTier.CORE, ContactTier.IMPORTANT)
                ):
                    signal["urgency_boost"] = True
            except Exception as exc:
                logger.debug(
                    "RelationshipHealth enrichment failed for member %s: %s",
                    member.id, exc,
                )

        signals.append(signal)

    return signals
