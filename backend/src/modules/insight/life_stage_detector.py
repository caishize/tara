"""Life Stage Detector — Infers family life stage from member demographics.

Automatically detects the family's current life stage based on member ages
and relationship types, then provides strategy adjustments for the insight
pipeline. Zero LLM cost — pure rule-based inference.

Stages:
    NEWLYWED: No children, marriage < 3 years
    TODDLER_PARENT: Youngest child age < 3
    SCHOOL_AGE_PARENT: Youngest child age 3-12
    EMPTY_NEST: No young children at home
    UNKNOWN: Insufficient data to determine
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum years since marriage to qualify as newlywed
NEWLYWED_MARRIAGE_YEARS_MAX = 3

# Age boundaries for child stages
TODDLER_AGE_MAX = 3
SCHOOL_AGE_MAX = 12

# Relationship types that indicate a child member
_CHILD_RELATION_TYPES: FrozenSet[str] = frozenset({
    "son", "daughter", "child",
})

# Relationship types that indicate a spouse
_SPOUSE_RELATION_TYPES: FrozenSet[str] = frozenset({
    "spouse",
})


# ---------------------------------------------------------------------------
# Enums & Data types
# ---------------------------------------------------------------------------


class LifeStage(str, Enum):
    """Family life stage classification."""
    NEWLYWED = "newlywed"
    TODDLER_PARENT = "toddler_parent"
    SCHOOL_AGE_PARENT = "school_age_parent"
    EMPTY_NEST = "empty_nest"
    UNKNOWN = "unknown"


# Strategy adjustment keys used by the insight pipeline
_STAGE_STRATEGIES: Dict[LifeStage, Dict[str, Any]] = {
    LifeStage.NEWLYWED: {
        "focus_areas": ["in_law_relationships", "holiday_customs", "couple_bonding"],
        "suppress_types": [],
        "boost_types": ["relationship"],
        "description": "新婚阶段：关注姻亲关系礼仪、节日习俗融合",
    },
    LifeStage.TODDLER_PARENT: {
        "focus_areas": ["efficiency", "postpartum_emotion", "childcare"],
        "suppress_types": ["relationship"],
        "boost_types": ["health", "efficiency"],
        "description": "幼儿阶段：精简非必要社交提醒，聚焦效率与产后情绪关怀",
    },
    LifeStage.SCHOOL_AGE_PARENT: {
        "focus_areas": ["teacher_relationships", "parent_social", "child_interests"],
        "suppress_types": [],
        "boost_types": ["relationship", "time"],
        "description": "学龄阶段：关注师生关系、家长社交、孩子兴趣追踪",
    },
    LifeStage.EMPTY_NEST: {
        "focus_areas": ["social_proactive", "health_focus", "hobby_recommendations"],
        "suppress_types": [],
        "boost_types": ["relationship", "health"],
        "description": "空巢阶段：主动社交建议、健康关注、兴趣推荐",
    },
    LifeStage.UNKNOWN: {
        "focus_areas": [],
        "suppress_types": [],
        "boost_types": [],
        "description": "数据不足，无法判断家庭阶段",
    },
}


@dataclass(frozen=True)
class LifeStageContext:
    """Immutable context describing the detected family life stage."""
    stage: LifeStage
    youngest_child_age: Optional[int]
    child_count: int
    strategy_adjustments: Dict[str, Any]


# ---------------------------------------------------------------------------
# Default context for graceful degradation
# ---------------------------------------------------------------------------

_UNKNOWN_CONTEXT = LifeStageContext(
    stage=LifeStage.UNKNOWN,
    youngest_child_age=None,
    child_count=0,
    strategy_adjustments=copy.deepcopy(_STAGE_STRATEGIES[LifeStage.UNKNOWN]),
)


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------


def _calculate_age(dob: Optional[date], reference_date: Optional[date] = None) -> Optional[int]:
    """Calculate age from date of birth, returning None if dob is missing."""
    if dob is None:
        return None
    ref = reference_date or utc_now().date()
    return ref.year - dob.year - (
        (ref.month, ref.day) < (dob.month, dob.day)
    )


def _infer_stage(
    child_ages: List[int],
    has_spouse: bool,
    spouse_marriage_years: Optional[int],
) -> Tuple[LifeStage, Optional[int]]:
    """Infer the life stage from child ages and marriage data.

    Returns (stage, youngest_child_age).
    """
    youngest = min(child_ages) if child_ages else None

    if child_ages:
        if youngest is not None and youngest < TODDLER_AGE_MAX:
            return LifeStage.TODDLER_PARENT, youngest
        if youngest is not None and youngest <= SCHOOL_AGE_MAX:
            return LifeStage.SCHOOL_AGE_PARENT, youngest
        # All children are older than school age
        return LifeStage.EMPTY_NEST, youngest

    # No children detected
    if has_spouse:
        if (
            spouse_marriage_years is not None
            and spouse_marriage_years < NEWLYWED_MARRIAGE_YEARS_MAX
        ):
            return LifeStage.NEWLYWED, None
        # Married but no children, marriage > 3 years
        return LifeStage.EMPTY_NEST, None

    return LifeStage.UNKNOWN, None


async def detect_life_stage(
    db: AsyncSession,
    family_id: UUID,
) -> LifeStageContext:
    """Detect the family's current life stage from member data.

    Queries members and their relations to find children and spouse
    relationships, then applies rule-based classification.

    Returns LifeStageContext with UNKNOWN stage if data is insufficient.
    """
    try:
        from ..member.models.member import Member, MemberRelation
        from ..member.models.enums import RelationType

        # Fetch all active members in the family
        member_stmt = (
            select(Member.id, Member.date_of_birth, Member.age)
            .where(
                and_(
                    Member.family_id == family_id,
                    Member.is_deleted.is_(False),
                )
            )
        )
        member_result = await db.execute(member_stmt)
        members = list(member_result.all())

        if not members:
            return _UNKNOWN_CONTEXT

        member_ids = {row.id for row in members}
        member_dob_map: Dict[UUID, Optional[date]] = {
            row.id: row.date_of_birth for row in members
        }
        member_age_map: Dict[UUID, Optional[int]] = {
            row.id: row.age for row in members
        }

        # Fetch relations within this family
        relation_stmt = (
            select(
                MemberRelation.from_member_id,
                MemberRelation.to_member_id,
                MemberRelation.relation_type,
                MemberRelation.created_at,
            )
            .where(MemberRelation.family_id == family_id)
        )
        relation_result = await db.execute(relation_stmt)
        relations = list(relation_result.all())

        # Identify children and spouse
        child_member_ids: List[UUID] = []
        has_spouse = False
        spouse_created_at = None

        for rel in relations:
            rel_type_val = (
                rel.relation_type.value
                if hasattr(rel.relation_type, "value")
                else str(rel.relation_type)
            )

            if rel_type_val in _CHILD_RELATION_TYPES:
                # The "to" member is the child
                child_member_ids.append(rel.to_member_id)

            if rel_type_val in _SPOUSE_RELATION_TYPES:
                has_spouse = True
                if spouse_created_at is None or (
                    rel.created_at and rel.created_at < spouse_created_at
                ):
                    spouse_created_at = rel.created_at

        # Calculate child ages
        child_ages: List[int] = []
        for child_id in child_member_ids:
            dob = member_dob_map.get(child_id)
            age = _calculate_age(dob)
            if age is None:
                # Fall back to stored age field
                age = member_age_map.get(child_id)
            if age is not None:
                child_ages.append(age)

        # Calculate marriage duration
        spouse_marriage_years: Optional[int] = None
        if has_spouse and spouse_created_at is not None:
            today = utc_now().date()
            spouse_marriage_years = today.year - spouse_created_at.year - (
                (today.month, today.day) < (spouse_created_at.month, spouse_created_at.day)
            )

        stage, youngest = _infer_stage(child_ages, has_spouse, spouse_marriage_years)

        context = LifeStageContext(
            stage=stage,
            youngest_child_age=youngest,
            child_count=len(child_ages),
            strategy_adjustments=copy.deepcopy(_STAGE_STRATEGIES[stage]),
        )

        logger.info(
            "Life stage detected for family %s: stage=%s, children=%d, youngest=%s",
            family_id, stage.value, len(child_ages), youngest,
        )

        return context

    except Exception as exc:
        logger.error(
            "Life stage detection failed for family %s: %s",
            family_id, exc,
        )
        return _UNKNOWN_CONTEXT
