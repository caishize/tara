"""Association text policies used by curation and read-path services.

This module keeps user-facing association copy natural while preserving
the original decision logic from curation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...member.models import Member, MemberRelation
from ...member.models.enums import NON_FAMILY_RELATION_TYPES


@dataclass(frozen=True)
class PersonAssociationContext:
    """Minimal person context for user-facing association phrasing."""

    target_id: str
    name: Optional[str] = None
    relation_type: Optional[str] = None
    is_family: bool = False
    co_resident: bool = False
    user_home_location: Optional[str] = None
    member_location: Optional[str] = None


_NON_FAMILY_RELATION_VALUES = {
    str(item.value if hasattr(item, "value") else item).strip().lower()
    for item in NON_FAMILY_RELATION_TYPES
}


def normalize_location_text(value: Optional[str]) -> str:
    """Normalize location text for lightweight overlap checks."""
    if not value:
        return ""
    return "".join(ch for ch in str(value).strip().lower() if not ch.isspace())


def locations_overlap(left: Optional[str], right: Optional[str]) -> bool:
    """Return True when two location strings likely refer to the same place."""
    left_norm = normalize_location_text(left)
    right_norm = normalize_location_text(right)
    if not left_norm or not right_norm:
        return False
    return left_norm in right_norm or right_norm in left_norm


def looks_internal_language(text: Optional[str]) -> bool:
    """Heuristic detector for machine/internal explanation leakage.

    Uses structural signals rather than keyword regex matching:
    - high ASCII+digit density
    - underscored identifiers
    - parameter-like punctuation patterns
    """
    if not text:
        return False

    compact = "".join(ch for ch in str(text) if not ch.isspace())
    if not compact:
        return False

    total = len(compact)
    ascii_letters = sum(1 for ch in compact if ch.isascii() and ch.isalpha())
    digits = sum(1 for ch in compact if ch.isdigit())
    underscores = compact.count("_")
    brackets = sum(compact.count(token) for token in "()[]{}")
    separators = sum(compact.count(token) for token in ":=;/")

    ascii_ratio = ascii_letters / max(total, 1)
    return (
        underscores >= 1
        or (ascii_ratio > 0.22 and digits >= 2)
        or (brackets >= 2 and ascii_letters >= 2)
        or (separators >= 2 and ascii_letters >= 2)
    )


def fallback_association_title(target_type: Optional[str], *, person_name: Optional[str] = None) -> str:
    """Fallback user-facing title when original copy is missing/technical."""
    normalized = str(target_type or "").strip().lower()
    if normalized == "person":
        if person_name:
            return f"记得联系{person_name}"
        return "找个时间联系一下"
    if normalized == "date":
        return "别忘了提前准备"
    if normalized == "memory":
        return "之前说过的事，别忘了"
    if normalized == "task":
        return "趁这次一起办了吧"
    return "这件事留意一下"


def fallback_association_reason(target_type: Optional[str]) -> str:
    """Fallback user-facing reason when original reason is missing/technical."""
    normalized = str(target_type or "").strip().lower()
    if normalized == "person":
        return "难得有这个机会，抽空见见面、聊聊天吧。"
    if normalized == "date":
        return "日子快到了，趁现在有时间提前准备，到时候不慌。"
    if normalized == "memory":
        return "你之前提过这件事，趁这次机会正好可以办了。"
    if normalized == "task":
        return "正好和这次的安排相关，一起办了省得惦记。"
    return "和最近的安排有关，提前留意心里有数。"


def present_association_copy(
    *,
    title: Optional[str],
    reason: Optional[str],
    target_type: Optional[str],
    source_location: Optional[str] = None,
    person_context: Optional[PersonAssociationContext] = None,
) -> tuple[str, str]:
    """Render association copy for end users.

    - strips internal/technical wording
    - applies co-resident family phrasing for person associations
    """
    normalized_target_type = str(target_type or "").strip().lower()

    safe_title = (title or "").strip()
    if not safe_title or looks_internal_language(safe_title):
        safe_title = fallback_association_title(
            normalized_target_type,
            person_name=person_context.name if person_context else None,
        )

    safe_reason = (reason or "").strip()
    if not safe_reason or looks_internal_language(safe_reason):
        safe_reason = fallback_association_reason(normalized_target_type)

    # Co-resident family safety net: if the LLM produced "探望/拜访" wording
    # for a co-resident family member, rewrite to a "bring a gift home" framing.
    # (Co-residents live together — "visiting" them makes no sense when travelling.)
    if (
        person_context is not None
        and person_context.is_family
        and person_context.co_resident
        and any(kw in safe_title for kw in ("探望", "拜访", "顺路见面", "见见面"))
    ):
        safe_title = "返程后给家里带份当地小礼物"
        safe_reason = "家人一直在家等你，带份小心意回去，温暖感更强。"

    return safe_title, safe_reason


def _safe_uuid(value: object) -> Optional[UUID]:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None


async def build_person_context_map(
    session: AsyncSession,
    *,
    family_id: UUID,
    user_id: Optional[UUID],
    person_ids: Iterable[str],
) -> dict[str, PersonAssociationContext]:
    """Build person metadata used for relationship-aware wording."""
    unique_person_ids = []
    seen: set[UUID] = set()
    for raw in person_ids:
        parsed = _safe_uuid(raw)
        if parsed is None or parsed in seen:
            continue
        seen.add(parsed)
        unique_person_ids.append(parsed)

    if not unique_person_ids:
        return {}

    ids_for_member_query = list(unique_person_ids)
    if user_id is not None and user_id not in seen:
        ids_for_member_query.append(user_id)

    member_stmt = select(Member).where(and_(
        Member.family_id == family_id,
        Member.id.in_(ids_for_member_query),
        Member.is_deleted == False,
    ))
    member_result = await session.execute(member_stmt)
    members = member_result.scalars().all()
    member_by_id = {member.id: member for member in members}

    relation_by_target: dict[UUID, str] = {}
    if user_id is not None:
        relation_stmt = select(MemberRelation).where(and_(
            MemberRelation.family_id == family_id,
            MemberRelation.from_member_id == user_id,
            MemberRelation.to_member_id.in_(unique_person_ids),
        ))
        relation_result = await session.execute(relation_stmt)
        for relation in relation_result.scalars().all():
            relation_value = relation.relation_type
            relation_text = (
                relation_value.value
                if hasattr(relation_value, "value")
                else str(relation_value)
            )
            relation_by_target[relation.to_member_id] = str(relation_text or "").strip().lower()

    user_home_location = None
    if user_id is not None:
        user_member = member_by_id.get(user_id)
        if user_member is not None:
            user_home_location = user_member.primary_location

    result: dict[str, PersonAssociationContext] = {}
    for person_id in unique_person_ids:
        member = member_by_id.get(person_id)
        relation_type = relation_by_target.get(person_id)
        is_family = bool(relation_type) and relation_type not in _NON_FAMILY_RELATION_VALUES

        member_location = member.primary_location if member is not None else None
        co_resident = (
            bool(user_id)
            and person_id != user_id
            and locations_overlap(user_home_location, member_location)
        )

        result[str(person_id)] = PersonAssociationContext(
            target_id=str(person_id),
            name=member.name if member is not None else None,
            relation_type=relation_type,
            is_family=is_family,
            co_resident=co_resident,
            user_home_location=user_home_location,
            member_location=member_location,
        )

    return result

