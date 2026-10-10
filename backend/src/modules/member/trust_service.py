"""Trust level management (L0-L3) with reflection logging.

Trust levels gate feature access and are upgraded/demoted based on
user confirmation patterns over time.

Levels:
  L0 (Novice)   - New user, minimal features
  L1 (Familiar) - 7+ days, 5+ confirmations
  L2 (Trusted)  - 30+ days, 80%+ confirm rate
  L3 (Rapport)  - 90+ days, <5% rejection rate
"""
import logging
from enum import Enum, IntEnum
from typing import Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.audit.service import AuditService
from ...core.utils.timezone import utc_now
from ...db.session import Base

logger = logging.getLogger(__name__)


class TrustLevel(IntEnum):
    L0_NOVICE = 0
    L1_FAMILIAR = 1
    L2_TRUSTED = 2
    L3_RAPPORT = 3


class ReflectionLog(Base):
    """Records trust-level transitions (upgrades, demotions, rejections)."""

    __tablename__ = "reflection_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    family_id = Column(PGUUID(as_uuid=True), nullable=False)
    event_type = Column(String(50), nullable=False)  # "demotion", "upgrade", "rejection"
    details = Column(JSONB, default=dict)
    trust_before = Column(Integer, nullable=False)
    trust_after = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


def evaluate_trust(
    confirmation_count: int,
    rejection_count: int,
    days_registered: int,
    current_level: int = 0,
) -> int:
    """Evaluate whether a trust level upgrade is warranted.

    Returns the new trust level (may equal current_level if no change).
    Only upgrades one level at a time.
    """
    total = confirmation_count + rejection_count
    if total == 0:
        return current_level
    confirm_rate = confirmation_count / total
    reject_rate = rejection_count / total

    if current_level == 0 and days_registered >= 7 and confirmation_count >= 5:
        return 1
    if current_level == 1 and days_registered >= 30 and confirm_rate >= 0.8:
        return 2
    if current_level == 2 and days_registered >= 90 and reject_rate < 0.05:
        return 3
    return current_level


def should_demote(consecutive_rejections: int, same_type: bool = True) -> bool:
    """Determine if trust should be demoted.

    Requires 3+ consecutive rejections of the same action type.
    """
    return consecutive_rejections >= 3 and same_type


# Feature access gating: maps feature names to minimum required trust level.
FEATURE_TRUST_REQUIREMENTS: Dict[str, TrustLevel] = {
    "auto_booking": TrustLevel.L2_TRUSTED,
    "auto_payment": TrustLevel.L3_RAPPORT,
    "proactive_suggestions": TrustLevel.L1_FAMILIAR,
    "sensitive_data_access": TrustLevel.L2_TRUSTED,
}


def check_feature_access(trust_level: int, feature: str) -> bool:
    """Check if a given trust level grants access to a feature."""
    required = FEATURE_TRUST_REQUIREMENTS.get(feature, TrustLevel.L0_NOVICE)
    return trust_level >= required


# ---------------------------------------------------------------------------
# V8 Progressive Feature Unlock — 4-tier system
# ---------------------------------------------------------------------------


class FeatureTier(str, Enum):
    """Progressive feature unlock tiers (V8 design doc)."""
    BASIC = "basic"          # Registration (default)
    ADVANCED = "advanced"    # 7 days + 2 family members
    PREMIUM = "premium"      # 30 days or manual unlock
    EXPERT = "expert"        # Manual unlock only


# Maps tier to the list of features it unlocks.
TIER_FEATURES: Dict[str, list] = {
    FeatureTier.BASIC.value: [
        "conversation",
        "reminders",
        "weather",
    ],
    FeatureTier.ADVANCED.value: [
        "kanban",
        "briefing",
        "memory",
    ],
    FeatureTier.PREMIUM.value: [
        "trip_planning",
        "gifts",
        "relationships",
    ],
    FeatureTier.EXPERT.value: [
        "graph_view",
        "global_orchestration",
    ],
}


def _is_tier_unlocked(
    tier: FeatureTier,
    days_active: int,
    family_member_count: int,
    manual_overrides: Optional[Dict[str, bool]] = None,
) -> bool:
    """Check whether a tier is unlocked given user stats.

    Unlock conditions:
      BASIC    : always (registration)
      ADVANCED : days_active >= 7 AND family_member_count >= 2
      PREMIUM  : days_active >= 30 OR manual override
      EXPERT   : manual override only
    """
    overrides = manual_overrides or {}

    if tier == FeatureTier.BASIC:
        return True

    if tier == FeatureTier.ADVANCED:
        if overrides.get(FeatureTier.ADVANCED.value, False):
            return True
        return days_active >= 7 and family_member_count >= 2

    if tier == FeatureTier.PREMIUM:
        if overrides.get(FeatureTier.PREMIUM.value, False):
            return True
        return days_active >= 30

    if tier == FeatureTier.EXPERT:
        return overrides.get(FeatureTier.EXPERT.value, False)

    return False


def get_available_features(
    days_active: int,
    family_member_count: int,
    manual_overrides: Optional[Dict[str, bool]] = None,
) -> list:
    """Return a flat list of all features the user currently has access to.

    Args:
        days_active: Number of days since the user registered.
        family_member_count: Number of family members the user has added.
        manual_overrides: Dict mapping tier name to True/False for manual unlock.

    Returns:
        List of feature name strings.
    """
    features: list = []
    for tier in FeatureTier:
        if _is_tier_unlocked(tier, days_active, family_member_count, manual_overrides):
            features.extend(TIER_FEATURES.get(tier.value, []))
    return features


def check_tier_feature_access(
    feature_name: str,
    days_active: int,
    family_member_count: int,
    manual_overrides: Optional[Dict[str, bool]] = None,
) -> bool:
    """Check whether a specific feature is accessible for the user.

    Args:
        feature_name: The feature to check.
        days_active: Number of days since the user registered.
        family_member_count: Number of family members the user has added.
        manual_overrides: Dict mapping tier name to True/False for manual unlock.

    Returns:
        True if the feature is accessible.
    """
    for tier in FeatureTier:
        if feature_name in TIER_FEATURES.get(tier.value, []):
            return _is_tier_unlocked(
                tier, days_active, family_member_count, manual_overrides,
            )
    # Unknown features default to accessible (backward compat)
    return True


def get_feature_tiers(
    days_active: int,
    family_member_count: int,
    manual_overrides: Optional[Dict[str, bool]] = None,
) -> Dict[str, dict]:
    """Return status of all tiers with their features and unlock state.

    Args:
        days_active: Number of days since the user registered.
        family_member_count: Number of family members the user has added.
        manual_overrides: Dict mapping tier name to True/False for manual unlock.

    Returns:
        Dict mapping tier name to {unlocked, features, unlock_conditions}.
    """
    result: Dict[str, dict] = {}
    for tier in FeatureTier:
        unlocked = _is_tier_unlocked(
            tier, days_active, family_member_count, manual_overrides,
        )
        conditions = _get_unlock_conditions(tier)
        result[tier.value] = {
            "unlocked": unlocked,
            "features": list(TIER_FEATURES.get(tier.value, [])),
            "unlock_conditions": conditions,
        }
    return result


def _get_unlock_conditions(tier: FeatureTier) -> dict:
    """Return human-readable unlock conditions for a tier."""
    if tier == FeatureTier.BASIC:
        return {"description": "Available at registration", "auto": True}
    if tier == FeatureTier.ADVANCED:
        return {
            "description": "7 days active + 2 family members",
            "days_required": 7,
            "family_members_required": 2,
            "auto": True,
        }
    if tier == FeatureTier.PREMIUM:
        return {
            "description": "30 days active or manual unlock",
            "days_required": 30,
            "auto": True,
            "manual_unlock_available": True,
        }
    if tier == FeatureTier.EXPERT:
        return {
            "description": "Manual unlock only",
            "auto": False,
            "manual_unlock_available": True,
        }
    return {"description": "Unknown tier"}


class TrustTransitionService:
    """Applies trust-level transitions with audit logging and reflection records.

    Wraps the pure ``evaluate_trust`` / ``should_demote`` functions and
    persists both a ReflectionLog row and an AuditLog entry for every
    transition.
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._audit = AuditService(db)

    async def apply_upgrade(
        self,
        user_id: UUID,
        family_id: UUID,
        current_level: int,
        confirmation_count: int,
        rejection_count: int,
        days_registered: int,
    ) -> Optional[int]:
        """Evaluate and apply a trust upgrade if warranted.

        Returns the new level if an upgrade occurred, otherwise None.
        """
        new_level = evaluate_trust(
            confirmation_count=confirmation_count,
            rejection_count=rejection_count,
            days_registered=days_registered,
            current_level=current_level,
        )
        if new_level == current_level:
            return None

        reflection = ReflectionLog(
            user_id=user_id,
            family_id=family_id,
            event_type="upgrade",
            trust_before=current_level,
            trust_after=new_level,
            details={
                "confirmations": confirmation_count,
                "rejections": rejection_count,
                "days_registered": days_registered,
            },
        )
        self._db.add(reflection)

        await self._audit.log_event(
            user_id=user_id,
            family_id=family_id,
            event_type="trust_upgraded",
            event_data={
                "trust_before": current_level,
                "trust_after": new_level,
                "confirmations": confirmation_count,
                "rejections": rejection_count,
                "days_registered": days_registered,
            },
        )
        return new_level

    async def apply_demotion(
        self,
        user_id: UUID,
        family_id: UUID,
        current_level: int,
        consecutive_rejections: int,
        same_type: bool = True,
    ) -> Optional[int]:
        """Evaluate and apply a trust demotion if warranted.

        Returns the new (lower) level if a demotion occurred, otherwise None.
        """
        if not should_demote(consecutive_rejections, same_type):
            return None
        if current_level <= 0:
            return None

        new_level = current_level - 1

        reflection = ReflectionLog(
            user_id=user_id,
            family_id=family_id,
            event_type="demotion",
            trust_before=current_level,
            trust_after=new_level,
            details={
                "consecutive_rejections": consecutive_rejections,
                "same_type": same_type,
            },
        )
        self._db.add(reflection)

        await self._audit.log_event(
            user_id=user_id,
            family_id=family_id,
            event_type="trust_demoted",
            event_data={
                "trust_before": current_level,
                "trust_after": new_level,
                "consecutive_rejections": consecutive_rejections,
                "same_type": same_type,
            },
        )
        return new_level
