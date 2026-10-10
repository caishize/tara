"""Entity Resolver — maps names, nicknames, and relation titles to member UUIDs.

Step 0 of the ContextAssembler pipeline. Scans user messages for known
family member references and resolves them to member IDs so downstream
layers (L3, L4) can personalize context retrieval.

Supports:
- Exact name / nickname matching
- Chinese relation title matching (爸爸, 妈妈, 老公, etc.)
- Basic pronoun resolution (他/她 → most recently referenced person)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chinese relation alias table
# ---------------------------------------------------------------------------

# Maps Chinese relation titles to RelationType enum values.
# Multiple aliases can point to the same relation type.
RELATION_ALIASES: Dict[str, str] = {
    # Spouse
    "老公": "spouse",
    "老婆": "spouse",
    "丈夫": "spouse",
    "妻子": "spouse",
    "先生": "spouse",
    "太太": "spouse",
    "媳妇": "spouse",
    "爱人": "spouse",
    # Parents
    "爸爸": "father",
    "爸": "father",
    "父亲": "father",
    "老爸": "father",
    "妈妈": "mother",
    "妈": "mother",
    "母亲": "mother",
    "老妈": "mother",
    # Children
    "儿子": "son",
    "女儿": "daughter",
    "孩子": "child",
    "小孩": "child",
    "宝宝": "child",
    "宝贝": "child",
    # Siblings
    "哥哥": "brother",
    "哥": "brother",
    "弟弟": "brother",
    "弟": "brother",
    "姐姐": "sister",
    "姐": "sister",
    "妹妹": "sister",
    "妹": "sister",
    # Grandparents (paternal)
    "爷爷": "grandfather_paternal",
    "奶奶": "grandmother_paternal",
    # Grandparents (maternal)
    "外公": "grandfather_maternal",
    "姥爷": "grandfather_maternal",
    "外婆": "grandmother_maternal",
    "姥姥": "grandmother_maternal",
    # In-laws
    "公公": "father_in_law",
    "婆婆": "mother_in_law",
    "岳父": "father_in_law",
    "岳母": "mother_in_law",
    # Uncle / Aunt
    "叔叔": "uncle_paternal",
    "伯伯": "uncle_paternal",
    "姑姑": "aunt_paternal",
    "舅舅": "uncle_maternal",
    "阿姨": "aunt_maternal",
    "姨妈": "aunt_maternal",
}

# Pronouns that can resolve to a previously referenced person
MALE_PRONOUNS: FrozenSet[str] = frozenset({"他", "他的"})
FEMALE_PRONOUNS: FrozenSet[str] = frozenset({"她", "她的"})


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MemberAlias:
    """A lookup entry linking an alias string to a member UUID."""
    member_id: UUID
    alias: str
    alias_type: str  # "name", "nickname", "relation", "profile_alias"
    gender: Optional[str] = None  # for pronoun resolution


# ---------------------------------------------------------------------------
# EntityResolver
# ---------------------------------------------------------------------------

class EntityResolver:
    """Resolves entity references in user messages to member UUIDs.

    Usage in production:
        resolver = EntityResolver(db)
        resolved_ids = await resolver.resolve(message, user_id, family_id)

    For ContextAssembler injection:
        assembler = ContextAssembler(entity_resolver=resolver.resolve)
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def resolve(
        self,
        user_message: str,
        user_id: UUID,
        family_id: UUID,
    ) -> Set[UUID]:
        """Scan user_message and return member UUIDs referenced in it.

        Steps:
        1. Build alias table from family members + person profiles
        2. Scan message for name / nickname / relation title matches
        3. Attempt pronoun resolution for unresolved 他/她
        """
        if not user_message or not user_message.strip():
            return set()

        alias_table = await self._build_alias_table(family_id)
        if not alias_table:
            return set()

        matched_ids, matched_genders = self._scan_message(
            user_message, alias_table,
        )

        # Pronoun resolution: if exactly one person was matched and
        # pronouns are present, they likely refer to that person.
        # If no person was matched but a pronoun exists, we cannot resolve.
        pronoun_ids = self._resolve_pronouns(
            user_message, alias_table, matched_ids, matched_genders,
        )
        matched_ids.update(pronoun_ids)

        return matched_ids

    async def _build_alias_table(
        self,
        family_id: UUID,
    ) -> List[MemberAlias]:
        """Build the alias lookup table from Members and PersonProfiles."""
        aliases: List[MemberAlias] = []

        # Fetch members
        try:
            from ..modules.member.models.member import Member, MemberRelation

            result = await self._db.execute(
                select(Member).where(
                    Member.family_id == family_id,
                    Member.is_deleted.is_(False),
                )
            )
            members = list(result.scalars().all())

            for m in members:
                gender = str(m.gender) if m.gender else None
                aliases.append(MemberAlias(
                    member_id=m.id,
                    alias=m.name,
                    alias_type="name",
                    gender=gender,
                ))
                if m.nickname:
                    aliases.append(MemberAlias(
                        member_id=m.id,
                        alias=m.nickname,
                        alias_type="nickname",
                        gender=gender,
                    ))

            # Fetch relations to build relation-title aliases
            relation_result = await self._db.execute(
                select(MemberRelation).where(
                    MemberRelation.family_id == family_id,
                )
            )
            relations = list(relation_result.scalars().all())

            # Build reverse map: relation_type -> member_id
            relation_type_to_members: Dict[str, List[UUID]] = {}
            for rel in relations:
                rt = rel.relation_type
                rt_value = rt.value if hasattr(rt, "value") else str(rt)
                relation_type_to_members.setdefault(rt_value, []).append(
                    rel.to_member_id
                )

            # Map Chinese aliases to member IDs via relation type
            for alias_text, rel_type in RELATION_ALIASES.items():
                member_ids = relation_type_to_members.get(rel_type, [])
                for mid in member_ids:
                    aliases.append(MemberAlias(
                        member_id=mid,
                        alias=alias_text,
                        alias_type="relation",
                    ))

        except Exception:
            logger.warning("Failed to load member aliases", exc_info=True)

        # Fetch person profiles for additional aliases
        try:
            from ..modules.member.models.person_profile import PersonProfile
            from ..modules.member.models.enums import ProfileStatus

            pp_result = await self._db.execute(
                select(PersonProfile).where(
                    PersonProfile.family_id == family_id,
                    PersonProfile.status == ProfileStatus.ACTIVE.value,
                    PersonProfile.member_id.isnot(None),
                )
            )
            profiles = list(pp_result.scalars().all())

            for pp in profiles:
                aliases.append(MemberAlias(
                    member_id=pp.member_id,
                    alias=pp.name,
                    alias_type="profile_alias",
                ))
                for alias_str in (pp.aliases or []):
                    if alias_str:
                        aliases.append(MemberAlias(
                            member_id=pp.member_id,
                            alias=alias_str,
                            alias_type="profile_alias",
                        ))

        except Exception:
            logger.warning("Failed to load person profile aliases", exc_info=True)

        return aliases

    @staticmethod
    def _scan_message(
        user_message: str,
        alias_table: List[MemberAlias],
    ) -> Tuple[Set[UUID], Dict[UUID, Optional[str]]]:
        """Scan user_message for alias matches.

        Returns (matched_member_ids, member_genders_map).
        Longer aliases are matched first to avoid partial matches.
        """
        matched_ids: Set[UUID] = set()
        matched_genders: Dict[UUID, Optional[str]] = {}
        msg_lower = user_message.lower()

        # Sort by alias length descending for greedy matching
        sorted_aliases = sorted(alias_table, key=lambda a: len(a.alias), reverse=True)

        for entry in sorted_aliases:
            if entry.alias.lower() in msg_lower:
                matched_ids.add(entry.member_id)
                if entry.gender:
                    matched_genders[entry.member_id] = entry.gender

        return matched_ids, matched_genders

    @staticmethod
    def _resolve_pronouns(
        user_message: str,
        alias_table: List[MemberAlias],
        already_matched: Set[UUID],
        matched_genders: Dict[UUID, Optional[str]],
    ) -> Set[UUID]:
        """Basic pronoun resolution for 他/她.

        Strategy:
        - If a gendered pronoun is found, look for a unique member of that
          gender in the alias table who is NOT already matched.
        - If exactly one candidate exists, resolve to that person.
        - If zero or multiple candidates exist, skip (ambiguous).
        """
        has_male = any(p in user_message for p in MALE_PRONOUNS)
        has_female = any(p in user_message for p in FEMALE_PRONOUNS)

        if not has_male and not has_female:
            return set()

        resolved: Set[UUID] = set()

        if has_male:
            males = {
                a.member_id for a in alias_table
                if a.gender and a.gender.lower() == "male"
            } - already_matched
            if len(males) == 1:
                resolved.update(males)

        if has_female:
            females = {
                a.member_id for a in alias_table
                if a.gender and a.gender.lower() == "female"
            } - already_matched
            if len(females) == 1:
                resolved.update(females)

        return resolved


# ---------------------------------------------------------------------------
# Standalone factory function for ContextAssembler injection
# ---------------------------------------------------------------------------

async def resolve_entities(
    user_message: str,
    user_id: UUID,
    family_id: UUID,
) -> Set[UUID]:
    """Resolve entity references using a fresh DB session.

    This is the callable injected into ContextAssembler as ``entity_resolver``.
    It creates a short-lived EntityResolver per call so the assembler stays
    stateless with respect to DB sessions.
    """
    try:
        from ..db.session import get_db_session

        async with get_db_session() as db:
            resolver = EntityResolver(db)
            return await resolver.resolve(user_message, user_id, family_id)
    except Exception:
        logger.warning("resolve_entities factory failed, returning empty set", exc_info=True)
        return set()
