"""Cross-cutting family relationship context for the curation pipeline.

Provides a single batch-loaded, frozen dataclass that carries family
relationship awareness through the entire curation run.  Consumers:
priority_engine, rule_engine, proactive_triggerer, proactive_insight_service,
orchestrator.

Design doc: C1 (FamilyRelationContext), TC-1
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Safety cap: maximum members per family to prevent unbounded queries (risk R1)
_MAX_MEMBERS_PER_FAMILY = 200

# Relation types considered "intimate" (spouse, parent, child and in-laws)
INTIMATE_RELATION_TYPES = frozenset({
    "spouse", "partner",
    "father", "mother", "parent",
    "son", "daughter", "child",
    "father_in_law", "mother_in_law", "parent_in_law",
})

# Intimacy level thresholds
_INTIMATE_LEVEL_THRESHOLD = 8  # >= 8 considered intimate regardless of type
_CLOSE_LEVEL_THRESHOLD = 5    # >= 5 considered close (siblings, close friends)


@dataclass(frozen=True)
class MemberRelationInfo:
    """Relationship info for a single member within a family.

    Attributes:
        member_id: The member's UUID.
        member_name: Display name.
        relation_type: Canonical relation type string (e.g. "spouse", "friend").
        intimacy_level: 1-10 scale.
    """

    member_id: UUID
    member_name: str
    relation_type: str
    intimacy_level: int


@dataclass(frozen=True)
class FamilyRelationContext:
    """Batch-loaded family relationship context.

    Loaded once per curation run via ``load_family_context``, then passed
    as a parameter to all downstream consumers.  Eliminates N+1 queries
    for intimate-relationship checks across modules.

    Attributes:
        family_id: The family this context belongs to.
        members: Mapping from member_id to their relation info.
    """

    family_id: UUID
    members: Dict[UUID, MemberRelationInfo]

    def is_intimate(self, member_id: UUID) -> bool:
        """Check if a member has an intimate relationship in this family.

        A member is intimate when:
        - Their relation_type is in INTIMATE_RELATION_TYPES, OR
        - Their intimacy_level >= _INTIMATE_LEVEL_THRESHOLD
        """
        info = self.members.get(member_id)
        if info is None:
            return False
        if info.relation_type in INTIMATE_RELATION_TYPES:
            return True
        return info.intimacy_level >= _INTIMATE_LEVEL_THRESHOLD

    def is_close(self, member_id: UUID) -> bool:
        """Check if a member is at least a close relation (level >= 5)."""
        info = self.members.get(member_id)
        if info is None:
            return False
        return info.intimacy_level >= _CLOSE_LEVEL_THRESHOLD

    def intimacy_level(self, member_id: UUID) -> int:
        """Return the intimacy level for a member, or 0 if unknown."""
        info = self.members.get(member_id)
        return info.intimacy_level if info is not None else 0

    def relation_type(self, member_id: UUID) -> Optional[str]:
        """Return the relation type string, or None if unknown."""
        info = self.members.get(member_id)
        return info.relation_type if info is not None else None

    def member_name(self, member_id: UUID) -> str:
        """Return the member's name, or empty string if unknown."""
        info = self.members.get(member_id)
        return info.member_name if info is not None else ""

    def has_any_intimate(self, member_ids: list) -> bool:
        """Check if any member in the list is intimate."""
        for mid in member_ids:
            if isinstance(mid, str):
                try:
                    mid = UUID(mid)
                except (ValueError, AttributeError):
                    continue
            if self.is_intimate(mid):
                return True
        return False

    def first_intimate(self, member_ids: list) -> Optional[MemberRelationInfo]:
        """Return the first intimate member info from the list, or None."""
        for mid in member_ids:
            if isinstance(mid, str):
                try:
                    mid = UUID(mid)
                except (ValueError, AttributeError):
                    continue
            info = self.members.get(mid)
            if info is not None and self.is_intimate(mid):
                return info
        return None


async def load_family_context(
    db: AsyncSession,
    family_id: UUID,
) -> FamilyRelationContext:
    """Load family relationship context in a single DB query (TC-1).

    Executes exactly 1 SELECT joining MemberRelation + Member,
    capped at _MAX_MEMBERS_PER_FAMILY rows.

    Args:
        db: Async database session.
        family_id: The family to load context for.

    Returns:
        FamilyRelationContext with all member relations for this family.
    """
    # Late imports to avoid circular dependencies at module load time
    from ...member.models.member import MemberRelation, Member

    stmt = (
        select(
            MemberRelation.to_member_id,
            MemberRelation.relation_type,
            MemberRelation.intimacy_level,
            Member.name,
        )
        .join(Member, Member.id == MemberRelation.to_member_id)
        .where(MemberRelation.family_id == family_id)
        .order_by(MemberRelation.intimacy_level.desc())
        .limit(_MAX_MEMBERS_PER_FAMILY)
    )

    try:
        result = await db.execute(stmt)
        rows = result.all()
    except Exception:
        logger.warning(
            "Failed to load family context for family %s, returning empty",
            family_id,
            exc_info=True,
        )
        return FamilyRelationContext(family_id=family_id, members={})

    members: Dict[UUID, MemberRelationInfo] = {}
    for to_member_id, relation_type, intimacy_level, name in rows:
        rel_str = (
            relation_type.value
            if hasattr(relation_type, "value")
            else str(relation_type)
        )
        # Keep highest-intimacy record per member (first wins due to ORDER BY)
        if to_member_id not in members:
            members[to_member_id] = MemberRelationInfo(
                member_id=to_member_id,
                member_name=name or "",
                relation_type=rel_str,
                intimacy_level=intimacy_level or 5,
            )

    return FamilyRelationContext(family_id=family_id, members=members)
