"""
Member Context Service - Provides rich member context for intelligent planning

Aggregates member information including:
- Basic info (name, age, gender)
- Preferences and habits
- Location and occupation
- Health considerations
- Relationships
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...config.logging import get_logger
from .models.member import Member
from .models.member import MemberProfile
from .models.member import MemberRelation
from .repositories.member_repository import MemberRepository


logger = get_logger(__name__)


# 关系称谓映射
RELATION_DISPLAY_MAP = {
    "spouse": "配偶",
    "parent": "父/母",
    "child": "子女",
    "sibling": "兄弟姐妹",
    "grandparent": "祖父母/外祖父母",
    "grandchild": "孙子女/外孙子女",
    "in_law": "姻亲",
    "other": "其他亲属",
}

# 称谓到关系类型的映射
NICKNAME_TO_RELATION = {
    "老婆": ("spouse", "female"),
    "妻子": ("spouse", "female"),
    "老公": ("spouse", "male"),
    "丈夫": ("spouse", "male"),
    "爸爸": ("parent", "male"),
    "父亲": ("parent", "male"),
    "爸": ("parent", "male"),
    "妈妈": ("parent", "female"),
    "母亲": ("parent", "female"),
    "妈": ("parent", "female"),
    "儿子": ("child", "male"),
    "女儿": ("child", "female"),
    "哥哥": ("sibling", "male"),
    "姐姐": ("sibling", "female"),
    "弟弟": ("sibling", "male"),
    "妹妹": ("sibling", "female"),
    "爷爷": ("grandparent", "male"),
    "奶奶": ("grandparent", "female"),
    "外公": ("grandparent", "male"),
    "外婆": ("grandparent", "female"),
    "孙子": ("grandchild", "male"),
    "孙女": ("grandchild", "female"),
    "外孙": ("grandchild", "male"),
    "外孙女": ("grandchild", "female"),
    "公公": ("in_law", "male"),
    "婆婆": ("in_law", "female"),
    "岳父": ("in_law", "male"),
    "岳母": ("in_law", "female"),
}


class MemberContextService:
    """Provides rich member context for intelligent conversation and planning."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.member_repo = MemberRepository(db)

    async def get_all_members_for_context(
        self,
        family_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Get lightweight member data for context building.

        Returns basic info only (name, nickname, relation, age, gender).
        Detailed preferences/health are available via tools on-demand.
        """
        members = await self.member_repo.get_family_members(family_id)
        if not members:
            return []

        return [
            {
                "id": str(m.id),
                "name": m.name,
                "nickname": m.nickname,
                "relation_type": getattr(m, "relation_type", None),
                "age": m.calculate_age() if m.date_of_birth else m.age,
                "gender": m.gender,
            }
            for m in members
        ]

    async def get_members_context_text(
        self,
        family_id: UUID,
    ) -> str:
        """
        Get a one-line summary of family members for system prompt.

        Format: 家庭成员：老板(男,35岁)、太太·小丽(女,32岁)、儿子·小明(男,5岁)
        Detailed info (preferences, health) is available via tools.
        """
        members = await self.member_repo.get_family_members(family_id)
        if not members:
            return "暂无家庭成员信息"

        parts = []
        for m in members:
            display = m.nickname or m.name
            relation = getattr(m, "relation_type", None)
            if relation:
                display = f"{relation}·{display}"

            detail_parts = []
            if m.gender:
                detail_parts.append("男" if m.gender == "male" else "女")
            age = m.calculate_age() if m.date_of_birth else m.age
            if age:
                detail_parts.append(f"{age}岁")

            if detail_parts:
                display += f"({','.join(detail_parts)})"

            parts.append(display)

        return "家庭成员：" + "、".join(parts)

    async def get_rich_member_context(
        self,
        family_id: UUID,
        user_id: UUID,
        include_preferences: bool = True,
        include_health: bool = True,
        include_relations: bool = True,
    ) -> Dict[str, Any]:
        """
        Get comprehensive member context for LLM.

        Returns:
            {
                "members": [...],
                "member_count": int,
                "summary": str  # Human-readable summary for LLM
            }
        """
        members = await self.member_repo.get_family_members(family_id)

        if not members:
            return {
                "members": [],
                "member_count": 0,
                "summary": "暂无家庭成员信息"
            }

        # Batch-fetch current work to avoid N+1
        from .current_work_helper import get_current_work_batch
        member_ids = [m.id for m in members]
        work_map = await get_current_work_batch(self.db, member_ids)

        member_contexts = []
        for member in members:
            context = await self._build_member_context(
                member,
                include_preferences=include_preferences,
                include_health=include_health,
                current_work=work_map.get(member.id),
            )
            member_contexts.append(context)

        # Build relations if requested
        if include_relations:
            relations = await self._get_family_relations(family_id)
            for ctx in member_contexts:
                member_id = ctx["id"]
                ctx["relations"] = relations.get(member_id, [])

        # Build summary for LLM
        summary = self._build_context_summary(member_contexts)

        return {
            "members": member_contexts,
            "member_count": len(member_contexts),
            "summary": summary
        }

    async def _build_member_context(
        self,
        member: Member,
        include_preferences: bool = True,
        include_health: bool = True,
        current_work: dict = None,
    ) -> Dict[str, Any]:
        """Build context for a single member."""
        context = {
            "id": str(member.id),
            "name": member.name,
            "nickname": member.nickname,
            "display_name": member.nickname or member.name,
        }

        # Age calculation
        if member.date_of_birth:
            age = member.calculate_age()
            context["age"] = age
            context["age_group"] = self._get_age_group(age)
            context["date_of_birth"] = member.date_of_birth.isoformat()
        elif member.age:
            context["age"] = member.age
            context["age_group"] = self._get_age_group(member.age)

        # Gender
        if member.gender:
            context["gender"] = member.gender
            context["gender_display"] = "男" if member.gender == "male" else "女" if member.gender == "female" else "未知"

        # Location info
        if member.address:
            context["location"] = member.address

        # Work info from work_histories (single source of truth)
        if current_work is None:
            from .current_work_helper import get_current_work
            current_work = await get_current_work(self.db, member.id)
        if current_work:
            if current_work["company_name"]:
                context["current_company"] = current_work["company_name"]
                # Backward-compatible keys
                context["workplace"] = current_work["company_name"]
            if current_work["position"]:
                context["current_position"] = current_work["position"]
                # Backward-compatible keys
                context["occupation"] = current_work["position"]

        # Tags
        if member.tags:
            context["tags"] = member.tags

        # Profile data
        if member.profile:
            profile = member.profile
            if include_preferences and profile.preferences:
                context["preferences"] = profile.preferences
            if profile.habits:
                context["habits"] = profile.habits
            if include_health and profile.health_summary:
                context["health_summary"] = profile.health_summary
            if profile.personality_traits:
                context["personality"] = profile.personality_traits
            if profile.special_notes:
                context["special_notes"] = profile.special_notes

        return context

    async def _get_family_relations(
        self,
        family_id: UUID,
    ) -> Dict[str, List[Dict[str, str]]]:
        """Get all relations in the family."""
        stmt = select(MemberRelation).where(
            MemberRelation.family_id == family_id
        )
        result = await self.db.execute(stmt)
        relations = result.scalars().all()

        # Build relation map
        relation_map = {}
        for rel in relations:
            from_id = str(rel.from_member_id)
            to_id = str(rel.to_member_id)
            rel_type = rel.relation_type.value if hasattr(rel.relation_type, 'value') else str(rel.relation_type)
            rel_display = RELATION_DISPLAY_MAP.get(rel_type, rel_type)

            # Add relation for from_member
            if from_id not in relation_map:
                relation_map[from_id] = []
            relation_map[from_id].append({
                "member_id": to_id,
                "relation": rel_display,
                "relation_type": rel_type,
            })

        return relation_map

    def _get_age_group(self, age: Optional[int]) -> str:
        """Categorize age into groups for planning purposes."""
        if age is None:
            return "未知"
        if age < 3:
            return "婴幼儿"
        if age < 7:
            return "学龄前儿童"
        if age < 13:
            return "小学生"
        if age < 18:
            return "青少年"
        if age < 30:
            return "青年"
        if age < 50:
            return "中年"
        if age < 70:
            return "中老年"
        return "老年"

    def _build_context_summary(self, member_contexts: List[Dict[str, Any]]) -> str:
        """Build a human-readable summary for LLM system prompt."""
        if not member_contexts:
            return "暂无家庭成员信息"

        lines = ["【家庭成员信息】"]

        for ctx in member_contexts:
            parts = [f"- {ctx['display_name']}"]

            # Age and gender
            info_parts = []
            if ctx.get("gender_display"):
                info_parts.append(ctx["gender_display"])
            if ctx.get("age"):
                info_parts.append(f"{ctx['age']}岁")
            if ctx.get("age_group") and ctx["age_group"] != "未知":
                info_parts.append(ctx["age_group"])
            if info_parts:
                parts.append(f"({', '.join(info_parts)})")

            # Occupation and location
            extra = []
            if ctx.get("occupation"):
                extra.append(f"职业:{ctx['occupation']}")
            if ctx.get("location"):
                extra.append(f"住址:{ctx['location'][:20]}")  # Truncate long addresses
            if extra:
                parts.append(f"[{'; '.join(extra)}]")

            # Preferences summary
            prefs = ctx.get("preferences", {})
            if prefs:
                pref_items = []
                if prefs.get("food"):
                    foods = prefs["food"][:3] if isinstance(prefs["food"], list) else [prefs["food"]]
                    pref_items.append(f"喜欢的食物:{','.join(str(f) for f in foods)}")
                if prefs.get("hobbies"):
                    hobbies = prefs["hobbies"][:3] if isinstance(prefs["hobbies"], list) else [prefs["hobbies"]]
                    pref_items.append(f"爱好:{','.join(str(h) for h in hobbies)}")
                if prefs.get("travel"):
                    travel = prefs["travel"]
                    if isinstance(travel, dict):
                        if travel.get("preferred_destinations"):
                            pref_items.append(f"喜欢去:{','.join(travel['preferred_destinations'][:2])}")
                if pref_items:
                    parts.append(f"偏好:{'; '.join(pref_items)}")

            # Health considerations
            if ctx.get("health_summary"):
                parts.append(f"健康注意:{ctx['health_summary'][:30]}")

            # Relations
            if ctx.get("relations"):
                rel_strs = [f"{r['relation']}" for r in ctx["relations"][:3]]
                if rel_strs:
                    parts.append(f"关系:{','.join(rel_strs)}")

            lines.append(" ".join(parts))

        return "\n".join(lines)

    async def get_user_default_location(
        self,
        user_id: UUID,
        family_id: UUID,
    ) -> Optional[str]:
        """
        Extract user's default city from existing Member data.

        Checks locations JSONB (using default_location_type) then falls back
        to the member's address field.

        Returns:
            City name string or None if not found.
        """
        try:
            stmt = select(Member).where(
                Member.family_id == family_id,
                Member.created_by == user_id,
                Member.is_deleted == False,
            ).limit(1)
            result = await self.db.execute(stmt)
            member = result.scalar_one_or_none()

            if not member:
                return None

            # Try locations JSONB first
            if member.locations and isinstance(member.locations, dict):
                loc_type = member.default_location_type or "home"
                loc_data = member.locations.get(loc_type) or {}
                address = loc_data.get("address", "")
                city = self._extract_city_from_address(address)
                if city:
                    return city

                # Try any location entry
                for loc_data in member.locations.values():
                    if isinstance(loc_data, dict):
                        address = loc_data.get("address", "")
                        city = self._extract_city_from_address(address)
                        if city:
                            return city

            # Fallback to member.address
            if member.address:
                city = self._extract_city_from_address(member.address)
                if city:
                    return city

            return None
        except Exception as e:
            logger.warning("Failed to get user default location: %s", e)
            return None

    @staticmethod
    def _extract_city_from_address(address: str) -> Optional[str]:
        """Extract city name from a Chinese address string."""
        if not address:
            return None
        import re
        # Match patterns like "上海市", "北京市", "深圳市" etc.
        match = re.search(r'([\u4e00-\u9fff]{2,4})[市]', address)
        if match:
            return match.group(1)
        # Match province-level municipalities without 市 suffix
        for city in ("北京", "上海", "天津", "重庆"):
            if city in address:
                return city
        # Fallback: return first 2-4 Chinese characters as a rough city guess
        chars = re.findall(r'[\u4e00-\u9fff]', address)
        if len(chars) >= 2:
            return ''.join(chars[:2])
        return None

    async def find_member_by_reference(
        self,
        family_id: UUID,
        reference: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a member by various references (name, nickname, relation term).

        Args:
            family_id: Family UUID
            reference: The reference text (e.g., "老婆", "张三", "妈妈")

        Returns:
            Member context dict or None
        """
        # Clean reference
        reference = reference.strip()

        # Remove possessive prefixes
        for prefix in ["我", "我的", "我们的", "我们家"]:
            if reference.startswith(prefix):
                reference = reference[len(prefix):]
                break

        # 1. Try direct name search
        members = await self.member_repo.search_by_name(family_id, reference)
        if members:
            return await self._build_member_context(members[0])

        # 2. Try nickname match
        all_members = await self.member_repo.get_family_members(family_id)
        for member in all_members:
            if member.nickname and reference in member.nickname:
                return await self._build_member_context(member)

        # 3. Try relation term match by checking tags or relations
        if reference in NICKNAME_TO_RELATION:
            rel_type, gender = NICKNAME_TO_RELATION[reference]
            # Find member with matching relation type
            for member in all_members:
                if member.gender == gender:
                    # Check if this member has the expected relation
                    # For now, just return based on gender match
                    return await self._build_member_context(member)

        return None

    async def extract_member_info_from_text(
        self,
        text: str,
    ) -> Dict[str, Any]:
        """
        Extract potential member information from natural text.

        Args:
            text: Natural language text mentioning a person

        Returns:
            Extracted member info that can be used to create a new member
        """
        import re

        info = {}

        # Extract relation term
        for term, (rel_type, gender) in NICKNAME_TO_RELATION.items():
            pattern = rf"(?:我|我的|我们的)?{term}"
            if re.search(pattern, text):
                info["relation_term"] = term
                info["relation_type"] = rel_type
                info["gender"] = gender
                break

        # Extract name
        # Pattern: "叫XXX" or "名字是XXX" or "XXX是我的..."
        name_patterns = [
            r"叫[做]?\s*([^\s，。,!！]+)",
            r"名字是\s*([^\s，。,!！]+)",
            r"是\s*([^\s，。,!！]{2,4})\s*(?:的)?(?:生日|纪念日|日期)",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                potential_name = match.group(1)
                # Filter out relation terms
                if potential_name not in NICKNAME_TO_RELATION:
                    info["name"] = potential_name
                    break

        # Extract age
        age_match = re.search(r"(\d{1,3})\s*岁", text)
        if age_match:
            age = int(age_match.group(1))
            if 0 < age < 150:
                info["age"] = age

        # Extract date of birth patterns
        dob_patterns = [
            r"(\d{4})年(\d{1,2})月(\d{1,2})[日号]?出生",
            r"出生于(\d{4})年(\d{1,2})月(\d{1,2})[日号]?",
        ]
        for pattern in dob_patterns:
            match = re.search(pattern, text)
            if match:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                try:
                    dob = date(year, month, day)
                    info["date_of_birth"] = dob.isoformat()
                except ValueError:
                    pass
                break

        return info

    async def suggest_member_creation(
        self,
        family_id: UUID,
        reference: str,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a suggestion for creating a new member based on reference.

        Returns:
            Suggested member data for creation
        """
        # Extract info from reference
        extracted = await self.extract_member_info_from_text(reference)

        # Merge with additional info
        if additional_info:
            extracted.update(additional_info)

        # Build suggestion
        suggestion = {
            "name": extracted.get("name", extracted.get("relation_term", "新成员")),
            "nickname": extracted.get("relation_term"),
            "gender": extracted.get("gender"),
            "age": extracted.get("age"),
            "date_of_birth": extracted.get("date_of_birth"),
            "relation_type": extracted.get("relation_type"),
            "source": "conversation_extraction",
        }

        return suggestion


__all__ = [
    "MemberContextService",
    "RELATION_DISPLAY_MAP",
    "NICKNAME_TO_RELATION",
]
