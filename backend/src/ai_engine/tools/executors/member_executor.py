"""Member domain tool executor — 5 tools for member management.

Handles family members, friends, colleagues, business contacts, etc.
"""

from dataclasses import dataclass, field as dc_field
from datetime import date as date_type
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from ....config.logging import get_logger
from ..shared.errors import ToolErrorType, tool_error
from ..shared.progress import ProgressCallback
from .base import BaseToolExecutor

logger = get_logger(__name__)


@dataclass
class MergeProfessionalResult:
    """Result of unified professional info merge."""

    work_history_updated: bool = False
    relation_updated: bool = False
    member_relations_updated: List[str] = dc_field(default_factory=list)


class MemberToolExecutor(BaseToolExecutor):
    """Handles add/update/query/details/delete for members."""

    async def add_member(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.member.repositories.member_repository import MemberRepository

        member_repo = MemberRepository(self.db)

        name = args.get("name", "")
        nickname = args.get("nickname")

        existing = await member_repo.search_by_name(family_id, name)
        if not existing and nickname:
            existing = await member_repo.search_by_name(family_id, nickname)

        if existing:
            return {
                "action": "already_exists",
                "member_id": str(existing[0].id),
                "member_name": existing[0].nickname or existing[0].name,
                "message": f"成员「{existing[0].nickname or existing[0].name}」已存在",
            }

        member_data: Dict[str, Any] = {
            "name": name,
            "nickname": nickname,
            "family_id": family_id,
            "created_by": user_id,
        }

        if args.get("gender"):
            member_data["gender"] = args["gender"]
        if args.get("date_of_birth"):
            member_data["date_of_birth"] = args["date_of_birth"]
        elif args.get("age"):
            member_data["age"] = args["age"]
        if args.get("address"):
            member_data["address"] = args["address"]

        # Build tags from notes and extra info
        tags: List[str] = []
        if args.get("notes"):
            tags.append(f"note:{args['notes']}")
        if args.get("current_company"):
            tags.append(f"company:{args['current_company']}")
        if args.get("current_position"):
            tags.append(f"position:{args['current_position']}")
        if args.get("relation_type"):
            tags.append(f"relation:{args['relation_type']}")
        if tags:
            member_data["tags"] = tags

        member = await member_repo.create(member_data)

        # Create work_history if work info provided
        company = args.get("current_company")
        position = args.get("current_position") or args.get("occupation")
        if company or position:
            await self._sync_work_history(
                family_id, member, company, position,
            )

        if member.date_of_birth:
            await self._create_member_birthday(member, user_id)

        if args.get("relation_type"):
            try:
                await self._update_member_relation(
                    family_id, user_id, member, args["relation_type"],
                    company_name=args.get("current_company"),
                )
            except Exception as e:
                logger.warning(f"Failed to create relation: {e}")

        await self.db.commit()
        logger.info(f"Created member: {member.id}")

        return {
            "success": True,
            "action": "created",
            "member_id": str(member.id),
            "member_name": nickname or name,
            "message": f"已添加成员「{nickname or name}」",
        }

    async def update_member_info(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.member.repositories.member_repository import MemberRepository
        from ....modules.member.repositories.profile_repository import ProfileRepository

        member_repo = MemberRepository(self.db)
        profile_repo = ProfileRepository(self.db)

        member_name = args.get("member_name", "")
        updates = args.get("updates", {})

        if not updates:
            return {"success": False, "message": "没有提供要更新的信息"}

        members = await member_repo.search_by_name(family_id, member_name)
        if not members:
            return {"success": False, "message": f"未找到成员「{member_name}」"}

        member = members[0]

        # -- Build member table updates --
        member_updates: Dict[str, Any] = {}

        # Direct scalar fields on the members table
        _SIMPLE_MEMBER_FIELDS = [
            "name", "nickname", "gender",
            "phone", "email",
        ]
        for field in _SIMPLE_MEMBER_FIELDS:
            if updates.get(field):
                member_updates[field] = updates[field]

        # Age → also compute approximate date_of_birth
        if updates.get("age"):
            age = updates["age"]
            current_year = date_type.today().year
            birth_year = current_year - age
            member_updates["age"] = age
            member_updates["date_of_birth"] = date_type(birth_year, 1, 1)

        # Explicit date_of_birth overrides age-derived one
        if updates.get("date_of_birth"):
            try:
                dob = date_type.fromisoformat(updates["date_of_birth"])
                member_updates["date_of_birth"] = dob
                today = date_type.today()
                computed_age = today.year - dob.year - (
                    (today.month, today.day) < (dob.month, dob.day)
                )
                member_updates["age"] = computed_age
            except (ValueError, TypeError):
                pass

        # Tags from notes
        if updates.get("notes"):
            current_tags: List[str] = list(member.tags or [])
            note_tag = f"note:{updates['notes']}"
            if note_tag not in current_tags:
                member_updates["tags"] = [*current_tags, note_tag]

        # Location handling
        location_type_cn = ""
        address_value = ""

        if updates.get("location"):
            loc = updates["location"]
            loc_type = loc.get("type", "home")
            loc_address = loc.get("address", "")
            if loc_address:
                current_locations = dict(member.locations or {})
                current_locations[loc_type] = {"address": loc_address}
                member_updates["locations"] = current_locations
                location_type_cn = {"home": "家庭", "work": "工作", "school": "学校", "other": ""}.get(loc_type, "")
                address_value = loc_address
        elif updates.get("address"):
            address = updates["address"]
            current_locations = dict(member.locations or {})
            current_locations["home"] = {"address": address}
            member_updates["locations"] = current_locations
            location_type_cn = "家庭"
            address_value = address

        if member_updates:
            await member_repo.update(member.id, member_updates)

        # -- Layer 3: Work + Relations unified merge --
        batch_wh_entries = updates.get("work_history", [])
        merge_result = await self._merge_professional_info_via_llm(
            family_id, user_id, member, updates,
        )
        work_history_updated = merge_result.work_history_updated
        relation_updated = merge_result.relation_updated
        member_relations_updated = merge_result.member_relations_updated

        # -- Profile-level updates --
        profile_updates: Dict[str, Any] = {}
        if updates.get("preferences"):
            current_prefs = {}
            if member.profile and member.profile.preferences:
                current_prefs = dict(member.profile.preferences)
            new_prefs = updates["preferences"]
            for key, value in new_prefs.items():
                if isinstance(value, list) and isinstance(current_prefs.get(key), list):
                    combined = list(set(current_prefs[key] + value))
                    current_prefs[key] = combined
                else:
                    current_prefs[key] = value
            profile_updates["preferences"] = current_prefs

        if updates.get("health_notes"):
            profile_updates["health_summary"] = updates["health_notes"]

        if profile_updates:
            if member.profile:
                await profile_repo.update(member.id, profile_updates)
            else:
                profile_data = {"member_id": member.id, **profile_updates}
                await profile_repo.create(profile_data)

        await self.db.commit()

        # -- Build response --
        updated_items: List[str] = []
        display_details: List[str] = []

        _DISPLAY_LABELS = {
            "name": "姓名", "nickname": "昵称", "age": "年龄",
            "gender": "性别", "date_of_birth": "出生日期",
            "phone": "手机", "email": "邮箱",
        }
        for field in _SIMPLE_MEMBER_FIELDS + ["age", "date_of_birth"]:
            if field in member_updates:
                label = _DISPLAY_LABELS.get(field, field)
                display_details.append(f"{label}: {member_updates[field]}")
                updated_items.append(field)

        # Work info display
        if work_history_updated:
            if batch_wh_entries:
                companies = [e.get("company_name", "") for e in batch_wh_entries if e.get("company_name")]
                display_details.append(f"工作履历: {'→'.join(companies)}")
                updated_items.append("work_history")
            else:
                company = updates.get("current_company")
                position = updates.get("current_position") or updates.get("occupation")
                if company:
                    display_details.append(f"公司: {company}")
                    updated_items.append("current_company")
                if position:
                    display_details.append(f"职位: {position}")
                    updated_items.append("current_position")

        if "locations" in member_updates:
            updated_items.append("locations")
            if location_type_cn and address_value:
                display_details.append(f"{location_type_cn}地址: {address_value}")

        if relation_updated:
            updated_items.append("relation_type")
            display_details.append(f"关系: {updates['relation_type']}")

        if member_relations_updated:
            updated_items.append("member_relations")
            display_details.append(f"成员间关系: {', '.join(member_relations_updated)}")

        if "tags" in member_updates:
            updated_items.append("notes")

        updated_items.extend(list(profile_updates.keys()))

        display_name = member_updates.get("nickname") or member.nickname or member.name
        if display_details:
            detail_str = ", ".join(display_details)
            message = f"已更新「{display_name}」的信息: {detail_str}"
        else:
            message = f"已更新「{display_name}」的信息: {', '.join(updated_items)}"

        return {
            "success": True,
            "member_id": str(member.id),
            "member_name": display_name,
            "updated_fields": updated_items,
            "address_updated": address_value if address_value else None,
            "location_type": location_type_cn if location_type_cn else None,
            "message": message,
        }

    async def _sync_work_history(
        self,
        family_id: UUID,
        member: Any,
        company_name: Optional[str] = None,
        position: Optional[str] = None,
    ) -> bool:
        """Thin wrapper: delegate to unified merge for a single company/position."""
        if not company_name and not position:
            return False
        updates: Dict[str, Any] = {}
        if company_name:
            updates["current_company"] = company_name
        if position:
            updates["current_position"] = position
        merge = await self._merge_professional_info_via_llm(
            family_id, None, member, updates,
        )
        return merge.work_history_updated

    async def _batch_sync_work_history(
        self,
        family_id: UUID,
        member: Any,
        entries: List[Dict[str, Any]],
    ) -> bool:
        """Thin wrapper: delegate to unified merge for a batch of entries."""
        if not entries:
            return False
        merge = await self._merge_professional_info_via_llm(
            family_id, None, member, {"work_history": entries},
        )
        return merge.work_history_updated

    # ------------------------------------------------------------------
    # Unified professional info merge (Layer 3)
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_for_prompt(value: str, max_len: int = 200) -> str:
        """Strip control chars and truncate to prevent prompt injection."""
        sanitized = (
            value.replace("\n", " ")
            .replace("\r", " ")
            .replace("{", "(")
            .replace("}", ")")
        )
        return sanitized[:max_len]

    async def _find_self_member(
        self, family_id: UUID, user_id: UUID,
    ) -> Optional[Any]:
        """Find the member representing the current user.

        Search order:
        1. Member with name '我' created by this user
        2. Any member named '我' in this family
        3. Member whose id == user_id (user record IS a member)
        4. First member created by this user (by creation order)
        """
        from ....modules.member.repositories.member_repository import MemberRepository
        from ....modules.member.models.member import Member as MemberModel
        from sqlalchemy import select as sa_select, and_ as sa_and

        # 1. Exact: name == "我" and created_by == user_id
        stmt = sa_select(MemberModel).where(
            sa_and(
                MemberModel.family_id == family_id,
                MemberModel.is_deleted == False,
                MemberModel.created_by == user_id,
                MemberModel.name == "我",
            )
        )
        result = await self.db.execute(stmt)
        self_member = result.scalar_one_or_none()
        if self_member:
            return self_member

        # 2. Fallback: any member named "我" in the family
        repo = MemberRepository(self.db)
        matches = await repo.search_by_name(family_id, "我")
        if matches:
            return matches[0]

        # 3. Fallback: member whose id == user_id (common in setups where
        #    user and member share the same UUID)
        stmt = sa_select(MemberModel).where(
            sa_and(
                MemberModel.id == user_id,
                MemberModel.family_id == family_id,
                MemberModel.is_deleted == False,
            )
        )
        result = await self.db.execute(stmt)
        self_member = result.scalar_one_or_none()
        if self_member:
            return self_member

        # 4. Last resort: first member created by this user
        stmt = (
            sa_select(MemberModel)
            .where(
                sa_and(
                    MemberModel.family_id == family_id,
                    MemberModel.is_deleted == False,
                    MemberModel.created_by == user_id,
                )
            )
            .order_by(MemberModel.created_at.asc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _merge_professional_info_via_llm(
        self,
        family_id: UUID,
        user_id: Optional[UUID],
        member: Any,
        updates: Dict[str, Any],
    ) -> MergeProfessionalResult:
        """Unified merge for work_history + professional_relations + member_relations.

        Consolidates what was previously 3+ separate write paths into a single
        flow with at most one LLM call for company name disambiguation.
        """
        result = MergeProfessionalResult()

        # --- Collect incoming updates ---
        batch_wh = updates.get("work_history", [])
        company = updates.get("current_company")
        position = updates.get("current_position") or updates.get("occupation")
        relation_type_str = updates.get("relation_type")
        member_relations_entries = updates.get("member_relations", [])

        has_work = bool(batch_wh) or bool(company) or bool(position)
        has_relation = bool(relation_type_str) and user_id is not None
        has_member_rels = bool(member_relations_entries)

        if not has_work and not has_relation and not has_member_rels:
            return result

        # --- Member relations (member↔other members, no LLM needed) ---
        if has_member_rels:
            result.member_relations_updated = await self._sync_member_relations(
                family_id, member, member_relations_entries,
            )

        # --- Relation type (user↔member) ---
        # Create the family/social relation (MemberRelation).
        # Skip the basic ProfessionalRelation when batch work_history is
        # provided — LLM inference will handle per-company PRs correctly.
        self_member = None
        self_member_whs: List[Any] = []
        if has_relation:
            try:
                # Derive effective company for basic PR:
                # prefer current_company, else first is_current from batch
                effective_company = company
                if not effective_company and batch_wh:
                    for e in batch_wh:
                        if e.get("is_current"):
                            effective_company = e.get("company_name")
                            break
                    if not effective_company:
                        effective_company = batch_wh[-1].get("company_name")

                result.relation_updated = await self._update_member_relation(
                    family_id, user_id, member, relation_type_str,
                    company_name=effective_company,
                    skip_professional=bool(batch_wh),
                )

                # Fetch self_member's work histories for LLM PR inference
                if has_work:
                    self_member = await self._find_self_member(family_id, user_id)
                    if self_member:
                        sm_whs, _ = await self._fetch_existing_professional_info(
                            family_id, self_member,
                        )
                        self_member_whs = sm_whs
            except Exception as e:
                logger.warning(f"Failed to update relation: {e}")

        if not has_work:
            return result

        # --- Normalize incoming work entries ---
        if batch_wh:
            incoming_entries = list(batch_wh)
            # Determine which entry (if any) is the current job.
            # If any entry explicitly says is_current=True, use it.
            # If ALL entries explicitly say is_current=False, no current job (-1).
            # Otherwise fall back to last entry for backwards compat.
            has_explicit_current = any(
                e.get("is_current") is True for e in incoming_entries
            )
            if has_explicit_current:
                current_idx = next(
                    i for i, e in enumerate(incoming_entries)
                    if e.get("is_current") is True
                )
            elif all(
                e.get("is_current") is False for e in incoming_entries
            ):
                current_idx = -1  # All entries are past jobs
            else:
                current_idx = len(incoming_entries) - 1
        else:
            incoming_entries = [
                {"company_name": company, "position": position, "is_current": True},
            ]
            current_idx = 0

        # --- Fetch existing data (one shot) ---
        existing_wh, existing_pr = await self._fetch_existing_professional_info(
            family_id, member,
        )

        # --- Build name→WorkHistory lookup ---
        existing_by_name: Dict[str, Any] = {}
        for wh in existing_wh:
            if wh.company_name and wh.company_name not in existing_by_name:
                existing_by_name[wh.company_name] = wh
        existing_by_id: Dict[str, Any] = {str(wh.id): wh for wh in existing_wh}

        # --- Decide: need LLM? ---
        # Also need LLM when inferring per-company professional relations
        # from overlapping work histories between self_member and member.
        need_pr_inference = bool(self_member_whs) and bool(relation_type_str)
        incoming_names = [
            e.get("company_name") for e in incoming_entries
            if e.get("company_name")
        ]

        if not existing_wh and not need_pr_inference:
            skip_llm = True
        elif (
            len(existing_wh) <= 1
            and not need_pr_inference
            and bool(incoming_names)
            and all(name in existing_by_name for name in incoming_names)
        ):
            skip_llm = True
        else:
            skip_llm = False

        # --- Build match map: incoming_index → matched WorkHistory ---
        match_map: Dict[int, Any] = {}
        dedup_map: Dict[str, str] = {}
        inferred_relations: List[Dict[str, Any]] = []

        if skip_llm:
            for i, entry in enumerate(incoming_entries):
                name = entry.get("company_name")
                if name and name in existing_by_name:
                    match_map[i] = existing_by_name[name]
        else:
            match_map, dedup_map, inferred_relations = (
                await self._resolve_matches_via_llm(
                    existing_wh, existing_pr, incoming_entries, existing_by_id,
                    self_member_whs=self_member_whs,
                    relation_type_str=relation_type_str,
                )
            )

        # --- Apply work history changes ---
        result.work_history_updated = await self._apply_work_history_merge(
            family_id, member, incoming_entries, existing_wh,
            existing_by_name, match_map, dedup_map, existing_by_id,
            current_idx,
        )

        # --- Apply inferred per-company professional relations ---
        if inferred_relations and self_member:
            await self._apply_inferred_professional_relations(
                family_id, self_member, member,
                inferred_relations, relation_type_str,
            )
        elif not inferred_relations and self_member and relation_type_str and batch_wh:
            # Fallback: LLM returned no inferred relations, create a single
            # basic PR with correct is_current based on company overlap.
            from ....modules.member.models.enums import ProfessionalRelationType
            _PROF_TYPE_MAP = {
                "boss": ProfessionalRelationType.BOSS,
                "subordinate": ProfessionalRelationType.SUBORDINATE,
                "peer": ProfessionalRelationType.PEER,
                "colleague": ProfessionalRelationType.PEER,
                "mentor": ProfessionalRelationType.MENTOR,
                "mentee": ProfessionalRelationType.MENTEE,
                "client": ProfessionalRelationType.CLIENT,
            }
            prof_type = _PROF_TYPE_MAP.get(relation_type_str)
            if prof_type:
                member_current_company = None
                for e in incoming_entries:
                    if e.get("is_current"):
                        member_current_company = e.get("company_name")
                self_current_company = next(
                    (wh.company_name for wh in self_member_whs if wh.is_current),
                    None,
                )
                is_current = bool(
                    member_current_company
                    and self_current_company
                    and member_current_company == self_current_company
                )
                await self._sync_professional_relation(
                    family_id, self_member, member, prof_type,
                    company_name=member_current_company,
                    is_current=is_current,
                )

        # --- Archive stale professional relations ---
        # When LLM was used, archiving is handled by pr_archive_ids in the
        # LLM response. Only use hardcoded SQL archiving for skip_llm path
        # where company names are exact matches (so SQL != is safe).
        if skip_llm:
            current_company = None
            for i, entry in enumerate(incoming_entries):
                if i == current_idx and entry.get("company_name"):
                    current_company = entry["company_name"]
                    break
            if current_company:
                await self._archive_stale_professional_relations(
                    member, current_company,
                )

        return result

    async def _fetch_existing_professional_info(
        self,
        family_id: UUID,
        member: Any,
    ) -> Tuple[List[Any], List[Any]]:
        """One-shot fetch of work histories and professional relations."""
        from ....modules.member.models.professional import (
            ProfessionalRelation,
            WorkHistory,
        )
        from sqlalchemy import select, and_, or_

        wh_stmt = select(WorkHistory).where(WorkHistory.member_id == member.id)
        wh_result = await self.db.execute(wh_stmt)
        existing_wh = list(wh_result.scalars().all())

        pr_stmt = select(ProfessionalRelation).where(
            and_(
                ProfessionalRelation.family_id == family_id,
                or_(
                    ProfessionalRelation.from_member_id == member.id,
                    ProfessionalRelation.to_member_id == member.id,
                ),
            )
        )
        pr_result = await self.db.execute(pr_stmt)
        existing_pr = list(pr_result.scalars().all())

        return existing_wh, existing_pr

    def _format_wh_for_prompt(self, wh_list: List[Any]) -> List[str]:
        """Format work history records for LLM prompt."""
        if not wh_list:
            return ["(无)"]
        lines: List[str] = []
        for wh in wh_list:
            period = ""
            if wh.start_date:
                end = wh.end_date.strftime("%Y-%m") if wh.end_date else "至今"
                period = f" | {wh.start_date.strftime('%Y-%m')}~{end}"
            current = "当前" if wh.is_current else "非当前"
            lines.append(
                f"[id:{wh.id}] "
                f"{self._sanitize_for_prompt(wh.company_name or '?')} | "
                f"{self._sanitize_for_prompt(wh.position or '?')}"
                f"{period} | {current}"
            )
        return lines

    def _build_merge_prompt(
        self,
        existing_wh: List[Any],
        existing_pr: List[Any],
        incoming_entries: List[Dict[str, Any]],
        self_member_whs: Optional[List[Any]] = None,
        relation_type_str: Optional[str] = None,
    ) -> str:
        """Build LLM prompt for professional info merge decision.

        The LLM decides:
        1. Which incoming entries match which existing work histories
        2. Which existing records are duplicates of each other (dedup)
        3. Which professional relations should be archived
        4. (When self_member_whs provided) Per-company professional relations
           inferred from overlapping work histories
        """
        has_pr_inference = bool(self_member_whs) and bool(relation_type_str)

        parts: List[str] = [
            "你是成员信息合并助手。请分析以下数据并输出合并方案。\n\n"
            "== 成员已有工作履历 ==",
        ]
        parts.extend(self._format_wh_for_prompt(existing_wh))

        parts.append("\n== 已有职业关系 ==")
        if existing_pr:
            for pr in existing_pr:
                current = "当前" if pr.is_current else "非当前"
                rt = (
                    pr.relation_type.value
                    if hasattr(pr.relation_type, "value")
                    else str(pr.relation_type)
                )
                parts.append(
                    f"[id:{pr.id}] 类型: {rt} | "
                    f"公司: {self._sanitize_for_prompt(pr.company_name or '?')} | "
                    f"{current}"
                )
        else:
            parts.append("(无)")

        parts.append("\n== 本次更新的工作履历 ==")
        for i, e in enumerate(incoming_entries):
            fields: List[str] = []
            if e.get("company_name"):
                fields.append(self._sanitize_for_prompt(e["company_name"]))
            if e.get("position"):
                fields.append(self._sanitize_for_prompt(e["position"]))
            if e.get("start_date"):
                end = e.get("end_date", "至今")
                fields.append(f"{e['start_date']}~{end}")
            fields.append("当前" if e.get("is_current") else "非当前")
            parts.append(f"[{i}] {' | '.join(fields)}")

        if has_pr_inference:
            parts.append(f"\n== 用户('我')的工作履历 ==")
            parts.extend(self._format_wh_for_prompt(self_member_whs))
            _RELATION_CN = {
                "boss": "上级/领导",
                "subordinate": "下属",
                "peer": "同事/平级",
                "colleague": "同事",
                "mentor": "导师",
                "mentee": "学员",
                "client": "客户",
            }
            rel_cn = _RELATION_CN.get(relation_type_str, relation_type_str)
            parts.append(
                f"\n== 用户与成员的关系 ==\n"
                f"该成员是用户的「{rel_cn}」(relation_type: {relation_type_str})"
            )

        # --- Task instructions ---
        task_lines = [
            "\n== 任务 ==",
            "1. 判断本次更新的每条工作履历与哪条已有记录是同一家公司",
            '   (例如"哔哩哔哩"="哔哩哔哩(B站)"、"顺丰科技"≈"顺丰")',
            "2. 检查已有记录之间是否有重复(同一公司的不同名称变体)",
            "3. 判断哪些职业关系因公司变动需要归档(is_current→false)",
        ]
        if has_pr_inference:
            task_lines.append(
                "4. 根据用户和成员的工作履历时间重叠，推断在哪些公司存在职业关系\n"
                "   - 双方在同一公司且时间有重叠 → 产生一条职业关系\n"
                "   - 公司名不完全一致时用语义判断(如'顺丰科技'和'顺丰'是同一公司)\n"
                "   - start_date取双方开始日期中较晚的，end_date取双方结束日期中较早的\n"
                "   - 双方目前都在该公司 → is_current=true"
            )

        # --- Output JSON spec ---
        task_lines.append(
            "\n输出JSON(不要输出其他内容):\n{"
        )
        task_lines.append(
            '  "work_history": {\n'
            '    "updates": [{"incoming_index": 0, "existing_id": "匹配的已有记录id"}],\n'
            '    "creates": [{"incoming_index": 1}]\n'
            "  },"
        )
        task_lines.append(
            '  "existing_dedup": [\n'
            '    {"keep_id": "保留的记录id", "remove_id": "重复的记录id"}\n'
            "  ],"
        )
        task_lines.append(
            '  "pr_archive_ids": ["需要归档的职业关系id"]'
        )
        if has_pr_inference:
            task_lines.append(
                ',\n  "inferred_relations": [\n'
                "    {\n"
                '      "company_name": "公司名",\n'
                f'      "relation_type": "{relation_type_str}",\n'
                '      "start_date": "YYYY-MM-DD",\n'
                '      "end_date": "YYYY-MM-DD或null",\n'
                '      "is_current": false\n'
                "    }\n"
                "  ]"
            )
        task_lines.append("\n}")

        task_lines.append(
            "\n规则:\n"
            "- updates: 新条目匹配到已有记录(同一公司)\n"
            "- creates: 无匹配的全新条目\n"
            "- existing_dedup: 已有记录中指向同一公司的重复项，保留信息更完整的那条\n"
            "- pr_archive_ids: 公司已变动导致不再current的职业关系\n"
            "- 如果没有重复或归档，对应数组为空"
        )
        if has_pr_inference:
            task_lines.append(
                "- inferred_relations: 双方在同一公司工作时间有重叠时产生，"
                "每个重叠公司一条记录"
            )

        parts.extend(task_lines)
        return "\n".join(parts)

    async def _resolve_matches_via_llm(
        self,
        existing_wh: List[Any],
        existing_pr: List[Any],
        incoming_entries: List[Dict[str, Any]],
        existing_by_id: Dict[str, Any],
        self_member_whs: Optional[List[Any]] = None,
        relation_type_str: Optional[str] = None,
    ) -> Tuple[Dict[int, Any], Dict[str, str], List[Dict[str, Any]]]:
        """Use Haiku to match incoming entries + dedup + infer relations.

        Returns:
            match_map: incoming_index → matched WorkHistory object
            dedup_map: existing_id_to_remove → keeper_id
            inferred_relations: per-company professional relations from
                overlapping work histories between self_member and member
        """
        import json
        import re

        prompt = self._build_merge_prompt(
            existing_wh, existing_pr, incoming_entries,
            self_member_whs=self_member_whs,
            relation_type_str=relation_type_str,
        )
        pr_by_id: Dict[str, Any] = {str(pr.id): pr for pr in existing_pr}

        try:
            from ....core.llm.haiku_client import get_haiku_client
            from ....config.settings import settings

            client = get_haiku_client()
            response = await client.messages.create(
                model=settings.fast_worker_model,
                max_tokens=1200,
                system="You are a data matching assistant. Output only valid JSON.",
                messages=[{"role": "user", "content": prompt}],
            )

            text_parts = [
                block.text for block in response.content
                if hasattr(block, "text")
            ]
            if not text_parts:
                return {}, {}, []

            content = text_parts[0].strip()
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                content = json_match.group()

            parsed = json.loads(content)

            # --- Parse work_history matches ---
            match_map: Dict[int, Any] = {}
            wh_section = parsed.get("work_history", {})
            entry_count = len(incoming_entries)

            for update in wh_section.get("updates", []):
                existing_id = str(update.get("existing_id", ""))
                incoming_idx = update.get("incoming_index")
                if (
                    existing_id in existing_by_id
                    and incoming_idx is not None
                    and isinstance(incoming_idx, int)
                    and 0 <= incoming_idx < entry_count
                ):
                    match_map[incoming_idx] = existing_by_id[existing_id]

            # --- Parse existing dedup ---
            dedup_map: Dict[str, str] = {}
            for dedup in parsed.get("existing_dedup", []):
                keep_id = str(dedup.get("keep_id", ""))
                remove_id = str(dedup.get("remove_id", ""))
                if keep_id in existing_by_id and remove_id in existing_by_id:
                    dedup_map[remove_id] = keep_id

            # --- Apply professional relation archiving ---
            for pr_id in parsed.get("pr_archive_ids", []):
                pr_id_str = str(pr_id)
                if pr_id_str in pr_by_id:
                    pr_by_id[pr_id_str].is_current = False

            if parsed.get("pr_archive_ids"):
                await self.db.flush()

            # --- Parse inferred relations ---
            inferred_relations: List[Dict[str, Any]] = parsed.get(
                "inferred_relations", [],
            )

            return match_map, dedup_map, inferred_relations

        except Exception as e:
            logger.warning(
                f"LLM professional info merge failed, "
                f"falling back to exact match: {e}"
            )
            name_to_wh: Dict[str, Any] = {}
            for wh in existing_wh:
                if wh.company_name and wh.company_name not in name_to_wh:
                    name_to_wh[wh.company_name] = wh
            fallback: Dict[int, Any] = {}
            for i, entry in enumerate(incoming_entries):
                name = entry.get("company_name")
                if name and name in name_to_wh:
                    fallback[i] = name_to_wh[name]
            return fallback, {}, []

    async def _apply_work_history_merge(
        self,
        family_id: UUID,
        member: Any,
        incoming_entries: List[Dict[str, Any]],
        existing_wh: List[Any],
        existing_by_name: Dict[str, Any],
        match_map: Dict[int, Any],
        dedup_map: Dict[str, str],
        existing_by_id: Dict[str, Any],
        current_idx: int,
    ) -> bool:
        """Apply work history merge: dedup existing, update matched, create new."""
        from ....modules.member.models.professional import WorkHistory

        try:
            # --- Apply LLM-decided dedup of existing records ---
            for remove_id, keep_id in dedup_map.items():
                dup = existing_by_id.get(remove_id)
                keeper = existing_by_id.get(keep_id)
                if not dup or not keeper:
                    continue
                # Merge richer fields from dup into keeper
                if not keeper.position and dup.position:
                    keeper.position = dup.position
                if not keeper.start_date and dup.start_date:
                    keeper.start_date = dup.start_date
                if not keeper.end_date and dup.end_date:
                    keeper.end_date = dup.end_date
                if not keeper.is_current and dup.is_current:
                    keeper.is_current = True
                # Soft-delete the duplicate
                dup.is_current = False
                dup.company_name = f"[merged] {dup.company_name}"
                logger.info(
                    f"Deduped work history: removed {remove_id}, "
                    f"kept {keep_id} for member {member.id}"
                )

            # Filter out deduped records from working set
            active_wh = [
                wh for wh in existing_wh if str(wh.id) not in dedup_map
            ]

            # Special case: position-only update (no company name in any entry)
            has_any_company = any(
                e.get("company_name") for e in incoming_entries
            )
            if not has_any_company:
                position = next(
                    (
                        e.get("position")
                        for e in incoming_entries
                        if e.get("position")
                    ),
                    None,
                )
                if position:
                    current = [wh for wh in active_wh if wh.is_current]
                    if current:
                        current[0].position = position
                        await self.db.flush()
                        return True
                return bool(dedup_map)

            # Reset is_current on existing records when we have a definitive
            # current entry OR when all incoming entries are past jobs.
            new_current_entry = (
                incoming_entries[current_idx]
                if 0 <= current_idx < len(incoming_entries)
                else None
            )
            if current_idx == -1:
                # All entries are past jobs — clear is_current on all existing
                for wh in active_wh:
                    wh.is_current = False
            elif new_current_entry and new_current_entry.get("company_name"):
                for wh in active_wh:
                    wh.is_current = False

            for i, entry in enumerate(incoming_entries):
                company_name = entry.get("company_name")
                if not company_name:
                    continue

                is_current = (i == current_idx)
                position = entry.get("position")
                start_date = None
                end_date = None

                if entry.get("start_date"):
                    try:
                        start_date = date_type.fromisoformat(entry["start_date"])
                    except (ValueError, TypeError):
                        pass
                if entry.get("end_date"):
                    try:
                        end_date = date_type.fromisoformat(entry["end_date"])
                    except (ValueError, TypeError):
                        pass

                matched_wh = match_map.get(i)

                if matched_wh:
                    matched_wh.is_current = is_current
                    if company_name != matched_wh.company_name:
                        matched_wh.company_name = company_name
                    if position:
                        matched_wh.position = position
                    if start_date:
                        matched_wh.start_date = start_date
                    if end_date:
                        matched_wh.end_date = end_date
                else:
                    new_wh = WorkHistory(
                        family_id=family_id,
                        member_id=member.id,
                        company_name=company_name,
                        position=position,
                        start_date=start_date,
                        end_date=end_date,
                        is_current=is_current,
                    )
                    self.db.add(new_wh)
                    existing_by_name[company_name] = new_wh

            await self.db.flush()
            return True

        except Exception as e:
            logger.warning(
                f"Failed to apply work history merge for {member.id}: {e}"
            )
            return False

    async def _apply_inferred_professional_relations(
        self,
        family_id: UUID,
        self_member: Any,
        target_member: Any,
        inferred_relations: List[Dict[str, Any]],
        relation_type_str: Optional[str] = None,
    ) -> None:
        """Create per-company professional relations from LLM-inferred overlaps.

        Each entry in inferred_relations represents a company where both
        self_member and target_member worked during overlapping time periods.
        """
        from ....modules.member.models.enums import ProfessionalRelationType
        from ....modules.member.models.professional import ProfessionalRelation
        from sqlalchemy import select, and_, or_

        _PROF_TYPE_MAP = {
            "boss": ProfessionalRelationType.BOSS,
            "subordinate": ProfessionalRelationType.SUBORDINATE,
            "peer": ProfessionalRelationType.PEER,
            "colleague": ProfessionalRelationType.PEER,
            "mentor": ProfessionalRelationType.MENTOR,
            "mentee": ProfessionalRelationType.MENTEE,
            "client": ProfessionalRelationType.CLIENT,
        }

        for rel in inferred_relations:
            company = rel.get("company_name")
            if not company:
                continue

            rt_str = rel.get("relation_type", relation_type_str or "peer")
            prof_type = _PROF_TYPE_MAP.get(rt_str, ProfessionalRelationType.PEER)
            is_current = rel.get("is_current", False)

            start_date = None
            end_date = None
            if rel.get("start_date"):
                try:
                    start_date = date_type.fromisoformat(rel["start_date"])
                except (ValueError, TypeError):
                    pass
            if rel.get("end_date"):
                try:
                    end_date = date_type.fromisoformat(rel["end_date"])
                except (ValueError, TypeError):
                    pass

            try:
                # Check for existing PR at this company between the two members
                stmt = select(ProfessionalRelation).where(
                    and_(
                        ProfessionalRelation.family_id == family_id,
                        ProfessionalRelation.company_name == company,
                        or_(
                            and_(
                                ProfessionalRelation.from_member_id == self_member.id,
                                ProfessionalRelation.to_member_id == target_member.id,
                            ),
                            and_(
                                ProfessionalRelation.from_member_id == target_member.id,
                                ProfessionalRelation.to_member_id == self_member.id,
                            ),
                        ),
                    )
                )
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.relation_type = prof_type
                    existing.is_current = is_current
                    if start_date:
                        existing.start_date = start_date
                    if end_date:
                        existing.end_date = end_date
                else:
                    new_pr = ProfessionalRelation(
                        family_id=family_id,
                        from_member_id=self_member.id,
                        to_member_id=target_member.id,
                        relation_type=prof_type,
                        company_name=company,
                        is_current=is_current,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    self.db.add(new_pr)

            except Exception as e:
                logger.warning(
                    f"Failed to apply inferred PR at {company}: {e}"
                )

        if inferred_relations:
            await self.db.flush()

    async def _update_member_relation(
        self,
        family_id: UUID,
        user_id: UUID,
        member: Any,
        relation_type_str: str,
        company_name: Optional[str] = None,
        skip_professional: bool = False,
    ) -> bool:
        """Create or update the relation between user ('我') and the member.

        For professional relation types (boss, subordinate, peer, etc.),
        also creates a basic ProfessionalRelation entry.
        """
        from ....modules.member.repositories.member_repository import MemberRepository
        from ....modules.member.repositories.relation_repository import RelationRepository
        from ....modules.member.models.enums import RelationType, ProfessionalRelationType

        # Mapping from tool relation_type → ProfessionalRelationType
        _PROF_TYPE_MAP = {
            "boss": ProfessionalRelationType.BOSS,
            "subordinate": ProfessionalRelationType.SUBORDINATE,
            "peer": ProfessionalRelationType.PEER,
            "colleague": ProfessionalRelationType.PEER,
            "mentor": ProfessionalRelationType.MENTOR,
            "mentee": ProfessionalRelationType.MENTEE,
            "client": ProfessionalRelationType.CLIENT,
        }

        try:
            member_repo = MemberRepository(self.db)

            self_member = await self._find_self_member(family_id, user_id)

            if not self_member:
                # No "self" member found — store relation_type as tag
                # but return False to signal that the professional relation
                # was NOT created (so the AI won't report success)
                current_tags: List[str] = list(member.tags or [])
                tag = f"relation:{relation_type_str}"
                existing_tags = [t for t in current_tags if not t.startswith("relation:")]
                existing_tags.append(tag)
                await member_repo.update(member.id, {"tags": existing_tags})
                logger.warning(
                    f"No self member ('我') found for user {user_id} in family {family_id}. "
                    f"Relation stored as tag only."
                )
                return False

            # --- Family/social relation (member_relations table) ---
            # Map professional types to "colleague" for the family relation table
            family_rel_str = relation_type_str
            if relation_type_str in _PROF_TYPE_MAP:
                family_rel_str = "colleague"

            try:
                rel_type = RelationType(family_rel_str)
            except ValueError:
                logger.warning(f"Unknown relation_type: {family_rel_str}")
                return False

            relation_repo = RelationRepository(self.db)
            existing_relations = await relation_repo.list_by_member(member.id)
            relation_exists = False
            for rel in existing_relations:
                from_id = str(rel.from_member_id)
                to_id = str(rel.to_member_id)
                self_id = str(self_member.id)
                member_id = str(member.id)
                if (from_id == self_id and to_id == member_id) or \
                   (from_id == member_id and to_id == self_id):
                    await relation_repo.update(rel.id, {"relation_type": rel_type})
                    relation_exists = True
                    break

            if not relation_exists:
                await relation_repo.create({
                    "family_id": family_id,
                    "from_member_id": self_member.id,
                    "to_member_id": member.id,
                    "relation_type": rel_type,
                })

            # --- Professional relation (professional_relations table) ---
            # Skip when LLM inference will handle per-company PRs (has_work=True)
            prof_type = _PROF_TYPE_MAP.get(relation_type_str)
            if prof_type and not skip_professional:
                await self._sync_professional_relation(
                    family_id, self_member, member, prof_type, company_name,
                )

            return True

        except Exception as e:
            logger.warning(f"Failed to update relation for member {member.id}: {e}")
            return False

    async def _sync_professional_relation(
        self,
        family_id: UUID,
        self_member: Any,
        target_member: Any,
        prof_type: Any,
        company_name: Optional[str] = None,
        is_current: bool = True,
    ) -> None:
        """Create or update a professional_relations entry."""
        from ....modules.member.models.professional import ProfessionalRelation
        from sqlalchemy import select, and_, or_

        try:
            # Check for existing professional relation
            stmt = select(ProfessionalRelation).where(
                and_(
                    ProfessionalRelation.family_id == family_id,
                    or_(
                        and_(
                            ProfessionalRelation.from_member_id == self_member.id,
                            ProfessionalRelation.to_member_id == target_member.id,
                        ),
                        and_(
                            ProfessionalRelation.from_member_id == target_member.id,
                            ProfessionalRelation.to_member_id == self_member.id,
                        ),
                    ),
                )
            )
            result = await self.db.execute(stmt)
            existing = result.scalars().first()

            if existing:
                existing.relation_type = prof_type
                if company_name:
                    existing.company_name = company_name
                existing.is_current = is_current
                await self.db.flush()
            else:
                new_pr = ProfessionalRelation(
                    family_id=family_id,
                    from_member_id=self_member.id,
                    to_member_id=target_member.id,
                    relation_type=prof_type,
                    company_name=company_name,
                    is_current=is_current,
                )
                self.db.add(new_pr)
                await self.db.flush()

        except Exception as e:
            logger.warning(
                f"Failed to sync professional relation "
                f"{self_member.id} -> {target_member.id}: {e}"
            )

    async def _sync_member_relations(
        self,
        family_id: UUID,
        member: Any,
        entries: List[Dict[str, Any]],
    ) -> List[str]:
        """Create/update professional relations between this member and other members.

        Returns a list of human-readable descriptions for display.
        """
        from ....modules.member.repositories.member_repository import MemberRepository
        from ....modules.member.models.enums import ProfessionalRelationType
        from ....modules.member.models.professional import ProfessionalRelation
        from sqlalchemy import select, and_, or_

        _PROF_TYPE_MAP = {
            "boss": ProfessionalRelationType.BOSS,
            "subordinate": ProfessionalRelationType.SUBORDINATE,
            "peer": ProfessionalRelationType.PEER,
            "colleague": ProfessionalRelationType.PEER,
            "mentor": ProfessionalRelationType.MENTOR,
            "mentee": ProfessionalRelationType.MENTEE,
            "client": ProfessionalRelationType.CLIENT,
        }
        _DISPLAY_MAP = {
            "boss": "上级", "subordinate": "下属", "peer": "同事",
            "colleague": "同事",
            "mentor": "导师", "mentee": "学员", "client": "客户",
        }

        results: List[str] = []
        member_repo = MemberRepository(self.db)

        for entry in entries:
            target_name = entry.get("target_member")
            relation_type_str = entry.get("relation_type")
            if not target_name or not relation_type_str:
                continue

            prof_type = _PROF_TYPE_MAP.get(relation_type_str)
            if not prof_type:
                logger.warning(f"Unknown member relation type: {relation_type_str}")
                continue

            try:
                targets = await member_repo.search_by_name(family_id, target_name)
                if not targets:
                    logger.warning(f"Member not found for relation: {target_name}")
                    continue

                target = targets[0]
                company_name = entry.get("company_name")
                is_current = entry.get("is_current", True)

                # Check for existing relation between the two members
                stmt = select(ProfessionalRelation).where(
                    and_(
                        ProfessionalRelation.family_id == family_id,
                        or_(
                            and_(
                                ProfessionalRelation.from_member_id == member.id,
                                ProfessionalRelation.to_member_id == target.id,
                            ),
                            and_(
                                ProfessionalRelation.from_member_id == target.id,
                                ProfessionalRelation.to_member_id == member.id,
                            ),
                        ),
                    )
                )
                result = await self.db.execute(stmt)
                existing = result.scalars().first()

                if existing:
                    existing.relation_type = prof_type
                    existing.is_current = is_current
                    # Normalize direction: from_member is the one being updated
                    existing.from_member_id = member.id
                    existing.to_member_id = target.id
                    if company_name:
                        existing.company_name = company_name
                else:
                    new_pr = ProfessionalRelation(
                        family_id=family_id,
                        from_member_id=member.id,
                        to_member_id=target.id,
                        relation_type=prof_type,
                        company_name=company_name,
                        is_current=is_current,
                    )
                    self.db.add(new_pr)

                await self.db.flush()

                member_name = member.nickname or member.name
                target_display = target.nickname or target.name
                rel_display = _DISPLAY_MAP.get(relation_type_str, relation_type_str)
                results.append(f"{member_name}是{target_display}的{rel_display}")

            except Exception as e:
                logger.warning(
                    f"Failed to sync member relation "
                    f"{member.id} -> {target_name}: {e}"
                )

        return results

    async def _archive_stale_professional_relations(
        self,
        member: Any,
        new_company_name: Optional[str],
    ) -> None:
        """Mark professional relations at old companies as is_current=False.

        When a member changes company, their professional relations tied to
        the old company should be archived automatically.
        """
        if not new_company_name:
            return

        from ....modules.member.models.professional import ProfessionalRelation
        from sqlalchemy import select, and_, or_

        try:
            stmt = select(ProfessionalRelation).where(
                and_(
                    or_(
                        ProfessionalRelation.from_member_id == member.id,
                        ProfessionalRelation.to_member_id == member.id,
                    ),
                    ProfessionalRelation.is_current.is_(True),
                    ProfessionalRelation.company_name.isnot(None),
                    ProfessionalRelation.company_name != new_company_name,
                )
            )
            result = await self.db.execute(stmt)
            stale_relations = result.scalars().all()

            for rel in stale_relations:
                rel.is_current = False

            if stale_relations:
                await self.db.flush()
                logger.info(
                    f"Archived {len(stale_relations)} stale professional relations "
                    f"for member {member.id} (new company: {new_company_name})"
                )

        except Exception as e:
            logger.warning(
                f"Failed to archive stale professional relations "
                f"for member {member.id}: {e}"
            )

    async def query_members(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.member.repositories.member_repository import MemberRepository
        from ....modules.member.repositories.relation_repository import RelationRepository

        repo = MemberRepository(self.db)

        category = args.get("category", "all")
        if category == "all":
            members = await repo.get_family_members(family_id)
        else:
            members = await repo.get_family_only_members(family_id, user_id)

        # Enrich with relation_type from member_relations table
        relation_repo = RelationRepository(self.db)
        relations = await relation_repo.list_by_family(family_id)
        member_relation_map: Dict[str, str] = {}
        for rel in relations:
            to_id = str(rel.to_member_id)
            if to_id not in member_relation_map:
                rt = rel.relation_type
                member_relation_map[to_id] = rt.value if hasattr(rt, "value") else str(rt)

        # Batch-fetch current work from work_histories
        from ....modules.member.current_work_helper import get_current_work_batch
        member_ids = [m.id for m in members]
        work_map = await get_current_work_batch(self.db, member_ids) if member_ids else {}

        return {
            "success": True,
            "category": category,
            "members": [
                {
                    "id": str(m.id),
                    "name": m.name,
                    "nickname": m.nickname,
                    "display_name": m.nickname or m.name,
                    "relation_type": member_relation_map.get(str(m.id)),
                    "age": m.age,
                    "gender": m.gender,
                    "date_of_birth": m.date_of_birth.isoformat() if m.date_of_birth else None,
                    "health_notes": m.profile.health_summary if m.profile else None,
                    "blood_type": getattr(m, "blood_type", None),
                    "preferences": m.profile.preferences if m.profile else None,
                    "interests": getattr(m, "interests", None),
                    "occupation": (work_map.get(m.id) or {}).get("position"),
                    "current_company": (work_map.get(m.id) or {}).get("company_name"),
                    "current_position": (work_map.get(m.id) or {}).get("position"),
                    "workplace": (work_map.get(m.id) or {}).get("company_name"),
                    "notes": m.profile.special_notes if m.profile else None,
                }
                for m in members
            ],
            "count": len(members),
        }

    async def get_member_details(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.member.context_service import MemberContextService

        member_name = args.get("member_name", "")
        if not member_name:
            return {"success": False, "message": "请提供成员姓名或称谓"}

        service = MemberContextService(self.db)
        member = await service.find_member_by_reference(family_id, member_name)

        if not member:
            return {
                "success": False,
                "message": f"未找到成员「{member_name}」",
                "suggestion": "可以使用 add_member 工具添加该成员",
            }

        details: Dict[str, Any] = {
            "success": True,
            "name": member.get("display_name"),
            "found": True,
        }

        if member.get("age"):
            details["age"] = member["age"]
            details["age_group"] = member.get("age_group", "")
        if member.get("gender_display"):
            details["gender"] = member["gender_display"]
        if member.get("occupation"):
            details["occupation"] = member["occupation"]
        if member.get("current_company"):
            details["current_company"] = member["current_company"]
        if member.get("current_position"):
            details["current_position"] = member["current_position"]
        if member.get("workplace"):
            details["workplace"] = member["workplace"]
        if member.get("location"):
            details["location"] = member["location"]

        if member.get("preferences"):
            prefs = member["preferences"]
            pref_summary = []
            if prefs.get("food"):
                foods = prefs["food"][:5] if isinstance(prefs["food"], list) else [prefs["food"]]
                pref_summary.append(f"喜欢的食物: {', '.join(str(f) for f in foods)}")
            if prefs.get("hobbies"):
                hobbies = prefs["hobbies"][:5] if isinstance(prefs["hobbies"], list) else [prefs["hobbies"]]
                pref_summary.append(f"爱好: {', '.join(str(h) for h in hobbies)}")
            if prefs.get("travel"):
                travel = prefs["travel"]
                if isinstance(travel, dict) and travel.get("preferred_destinations"):
                    pref_summary.append(f"喜欢去: {', '.join(travel['preferred_destinations'][:3])}")
            if pref_summary:
                details["preferences"] = pref_summary

        if member.get("health_summary"):
            details["health_notes"] = member["health_summary"]
        if member.get("special_notes"):
            details["special_notes"] = member["special_notes"]

        return details

    async def delete_member(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.member.repositories.member_repository import MemberRepository
        from ....modules.member.context_service import MemberContextService

        member_name = args.get("member_name", "")
        confirm = args.get("confirm", False)

        if not member_name:
            return tool_error(ToolErrorType.VALIDATION, "请提供要删除的成员姓名或称谓")

        if not confirm:
            return tool_error(
                ToolErrorType.VALIDATION,
                "删除操作需要确认，请设置 confirm=true",
                hint="请先与用户确认是否要删除该成员",
            )

        service = MemberContextService(self.db)
        member_info = await service.find_member_by_reference(family_id, member_name)

        if not member_info:
            return tool_error(
                ToolErrorType.NOT_FOUND,
                f"未找到成员「{member_name}」",
                hint="可以使用 query_members 查看当前成员列表",
            )

        member_repo = MemberRepository(self.db)
        member_id = member_info.get("member_id") or member_info.get("id")
        success = await member_repo.soft_delete(member_id)
        await self.db.commit()

        if not success:
            return tool_error(ToolErrorType.INTERNAL, f"删除成员「{member_name}」失败")

        return {
            "success": True,
            "deleted": True,
            "member_name": member_info.get("display_name", member_name),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _create_member_birthday(self, member: Any, user_id: UUID) -> None:
        from ....modules.date_manager.models import ImportantDate

        try:
            name = member.nickname or member.name or "成员"
            title = f"{name}的生日"

            birthday = ImportantDate(
                family_id=member.family_id,
                member_id=member.id,
                created_by=user_id,
                title=title,
                date_type="birthday",
                solar_date=member.date_of_birth,
                is_lunar=False,
                is_recurring=True,
                recurrence_rule={"freq": "yearly"},
                reminder_offsets=[-7, -1, 0],
                reminder_time="09:00",
                reminder_channels=["app"],
                importance_level=8,
                source="member_sync",
            )

            self.db.add(birthday)
            await self.db.flush()
            logger.info(f"Created birthday for member {member.id}: {title}")
        except Exception as e:
            logger.error(f"Failed to create birthday for member {member.id}: {e}")
