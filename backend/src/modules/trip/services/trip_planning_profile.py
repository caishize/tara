"""
Travel Planning Profile Mixin - User profile analysis for travel planning.

Extracts and analyzes family member profiles to inform trip constraints,
budget levels, and personalization.
"""

from typing import Dict, Any, List, Optional
from datetime import date

from ....config.logging import get_logger
from .trip_planning_constants import (
    AGE_GROUP_CHARACTERISTICS,
    BudgetLevel,
)

logger = get_logger(__name__)


class TripProfileMixin:
    """Mixin for user profile analysis methods."""

    async def _get_comprehensive_user_profile(
        self,
        family_id,
        user_id,
        participants: Optional[List[Dict[str, Any]]] = None,
        excluded_members: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """获取完整的用户画像

        Args:
            family_id: 家庭ID
            user_id: 用户ID
            participants: 指定的出行人员列表（如果提供，只包含这些人）
            excluded_members: 排除的成员列表（如果提供，排除这些人）
        """
        # 获取丰富的成员上下文
        member_context = await self.member_context_service.get_rich_member_context(
            family_id=family_id,
            user_id=user_id,
            include_preferences=True,
            include_health=True,
            include_relations=True,
        )

        all_members = member_context.get("members", [])

        # 根据 participants 和 excluded_members 过滤成员
        members = self._filter_participants(all_members, participants, excluded_members)
        is_filtered = (participants is not None and len(participants) > 0) or \
                      (excluded_members is not None and len(excluded_members) > 0)

        logger.info(f"Filtered members: {len(members)} out of {len(all_members)} total members (is_filtered={is_filtered})")

        # 分析成员年龄分布
        age_distribution = self._analyze_age_distribution(members)

        # 汇总偏好信息
        preferences_summary = self._aggregate_preferences(members)

        # 分析财务能力（基于职业等信息推断）
        financial_profile = self._infer_financial_profile(members)

        # 汇总健康注意事项
        health_considerations = self._aggregate_health_info(members)

        # 构建画像摘要
        summary = self._build_profile_summary(
            members, age_distribution, preferences_summary,
            financial_profile, health_considerations
        )

        return {
            "members": members,
            "member_count": len(members),
            "age_distribution": age_distribution,
            "preferences": preferences_summary,
            "financial_profile": financial_profile,
            "health_considerations": health_considerations,
            "summary": summary,
            "is_filtered": is_filtered,
        }

    def _filter_participants(
        self,
        all_members: List[Dict[str, Any]],
        participants: Optional[List[Dict[str, Any]]],
        excluded_members: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """根据指定的出行人员和排除名单过滤成员

        优先级：
        1. 如果指定了 participants，只包含匹配的成员（加上从 participants 补充的临时成员信息）
        2. 如果指定了 excluded_members，排除匹配的成员
        3. 如果都没有指定，返回所有成员

        匹配逻辑：
        - 按姓名（name）匹配
        - 按昵称（nickname、display_name）匹配
        - 按关系类型（relation）匹配
        """
        if not participants and not excluded_members:
            return all_members

        # 构建成员索引（用于快速查找）
        def member_matches(member: Dict, search_term: str) -> bool:
            """检查成员是否匹配搜索词"""
            search_lower = search_term.lower()
            # 检查名字 (使用 or "" 处理 None 值)
            if (member.get("name") or "").lower() == search_lower:
                return True
            # 检查昵称
            if (member.get("nickname") or "").lower() == search_lower:
                return True
            # 检查显示名
            if (member.get("display_name") or "").lower() == search_lower:
                return True
            # 检查关系类型
            if (member.get("relation") or "").lower() == search_lower:
                return True

            # 部分匹配 - 搜索词包含在名字中
            name = (member.get("name") or "").lower()
            if name and search_lower in name:
                return True

            # 关系类型部分匹配（如"爸爸"匹配"父亲/爸爸"）
            relation = (member.get("relation") or "").lower()
            relation_aliases = {
                "爸爸": ["父亲", "爸", "dad", "father"],
                "妈妈": ["母亲", "妈", "mom", "mother"],
                "爷爷": ["祖父", "grandpa", "grandfather"],
                "奶奶": ["祖母", "grandma", "grandmother"],
                "外公": ["外祖父", "姥爷"],
                "外婆": ["外祖母", "姥姥"],
                "哥哥": ["兄", "brother"],
                "姐姐": ["姊", "sister"],
                "弟弟": ["弟"],
                "妹妹": ["妹"],
                "儿子": ["son"],
                "女儿": ["daughter"],
                "老公": ["丈夫", "先生", "husband"],
                "老婆": ["妻子", "太太", "wife"],
            }

            for primary, aliases in relation_aliases.items():
                all_terms = [primary] + aliases
                if search_lower in all_terms and relation in all_terms:
                    return True

            return False

        result = []

        if participants:
            # 只包含指定的参与者
            matched_ids = set()
            for p in participants:
                p_name = p.get("name", "")
                p_id = p.get("id", "")

                for member in all_members:
                    member_id = str(member.get("id", ""))
                    if member_id in matched_ids:
                        continue

                    if (p_id and member_id == p_id) or member_matches(member, p_name):
                        result.append(member)
                        matched_ids.add(member_id)
                        break

            # 如果有未匹配的参与者，创建临时成员信息
            for p in participants:
                p_name = p.get("name", "")
                found = any(
                    member_matches(m, p_name) or str(m.get("id", "")) == p.get("id", "")
                    for m in result
                )
                if not found and p_name:
                    result.append({
                        "name": p_name,
                        "display_name": p_name,
                        "is_temporary": True,
                    })

        elif excluded_members:
            # 排除指定的成员
            for member in all_members:
                should_exclude = False
                for ex_name in excluded_members:
                    if member_matches(member, ex_name):
                        should_exclude = True
                        break
                if not should_exclude:
                    result.append(member)
        else:
            result = all_members

        return result

    def _analyze_age_distribution(
        self, members: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """分析成员年龄分布"""
        # Age group boundaries: (max_age, group_name)
        age_groups = [
            (2, "infant"),
            (6, "toddler"),
            (12, "child"),
            (17, "teen"),
            (35, "young_adult"),
            (55, "middle_aged"),
            (70, "senior"),
            (float('inf'), "elderly"),
        ]

        distribution = {group[1]: [] for group in age_groups}

        for member in members:
            age = member.get("age")
            if age is None:
                continue

            # Ensure age is an integer for comparison
            try:
                age_int = int(age)
            except (ValueError, TypeError):
                continue

            name = member.get("display_name") or member.get("name", "未知")
            member_info = {"name": name, "age": age_int}

            for max_age, group_name in age_groups:
                if age_int <= max_age:
                    distribution[group_name].append(member_info)
                    break

        # Ensure all ages are integers for aggregation
        ages = []
        for m in members:
            age_val = m.get("age")
            if age_val is not None:
                try:
                    ages.append(int(age_val))
                except (ValueError, TypeError):
                    pass
        stats = {
            "min_age": min(ages) if ages else None,
            "max_age": max(ages) if ages else None,
            "avg_age": sum(ages) / len(ages) if ages else None,
            "has_infants": bool(distribution["infant"]),
            "has_children": bool(distribution["toddler"] or distribution["child"]),
            "has_teens": bool(distribution["teen"]),
            "has_seniors": bool(distribution["senior"] or distribution["elderly"]),
        }

        return {"distribution": distribution, "stats": stats}

    def _aggregate_preferences(
        self, members: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """汇总所有成员的偏好"""
        all_foods = []
        all_hobbies = []
        all_travel_prefs = []
        avoid_foods = []

        def extend_list(target: list, value) -> None:
            """Helper to extend list with value (handles both list and single item)"""
            if isinstance(value, list):
                target.extend(value)
            elif value:
                target.append(value)

        for member in members:
            prefs = member.get("preferences", {})
            if not prefs:
                continue

            extend_list(all_foods, prefs.get("food"))
            extend_list(all_hobbies, prefs.get("hobbies"))
            extend_list(avoid_foods, prefs.get("dietary_restrictions"))

            travel = prefs.get("travel")
            if isinstance(travel, dict):
                extend_list(all_travel_prefs, travel.get("preferred_destinations"))
                extend_list(avoid_foods, travel.get("avoid"))

        return {
            "food_preferences": list(set(all_foods))[:10],
            "hobbies": list(set(all_hobbies))[:10],
            "travel_preferences": list(set(all_travel_prefs))[:5],
            "dietary_restrictions": list(set(avoid_foods)),
        }

    def _infer_financial_profile(
        self, members: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """根据成员信息推断财务状况"""
        high_income_keywords = [
            "总监", "经理", "ceo", "cto", "医生", "律师", "教授",
            "director", "manager", "doctor", "lawyer", "professor",
            "企业家", "老板", "投资", "金融",
        ]
        luxury_keywords = ["ceo", "老板", "企业家", "投资"]

        budget_config = {
            BudgetLevel.BUDGET: {"daily": 300, "hotel": "经济型/快捷酒店"},
            BudgetLevel.MODERATE: {"daily": 600, "hotel": "3-4星酒店"},
            BudgetLevel.COMFORT: {"daily": 1200, "hotel": "4-5星酒店"},
            BudgetLevel.LUXURY: {"daily": 2500, "hotel": "5星/奢华酒店"},
        }

        estimated_level = BudgetLevel.MODERATE

        for member in members:
            occupation = (member.get("occupation") or "").lower()
            if not occupation:
                continue

            if any(kw in occupation for kw in high_income_keywords):
                estimated_level = BudgetLevel.COMFORT
                if any(kw in occupation for kw in luxury_keywords):
                    estimated_level = BudgetLevel.LUXURY
                    break

        config = budget_config.get(estimated_level, budget_config[BudgetLevel.MODERATE])
        return {
            "estimated_level": estimated_level.value,
            "suggested_daily_budget_per_person": config["daily"],
            "suggested_hotel_star": config["hotel"],
        }

    def _aggregate_health_info(
        self, members: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """汇总健康注意事项"""
        age_health_notes = {
            (0, 3): "婴幼儿需要注意：防晒、补水、避免人群密集处",
            (70, float('inf')): "老人需要注意：携带常用药物、避免剧烈运动、注意天气变化",
        }

        considerations = []

        for member in members:
            name = member.get("display_name") or member.get("name", "未知")
            health = member.get("health_summary")

            if health:
                considerations.append({"member": name, "notes": health})

            age = member.get("age")
            if age:
                try:
                    age_int = int(age)
                    for (min_age, max_age), notes in age_health_notes.items():
                        if min_age <= age_int <= max_age:
                            considerations.append({"member": name, "notes": notes})
                            break
                except (ValueError, TypeError):
                    pass

        return considerations

    def _build_profile_summary(
        self,
        members: List[Dict[str, Any]],
        age_distribution: Dict[str, Any],
        preferences: Dict[str, Any],
        financial: Dict[str, Any],
        health: List[Dict[str, str]],
    ) -> str:
        """构建画像摘要文本"""
        lines = []

        # 成员概况
        stats = age_distribution.get("stats", {})
        member_desc = f"家庭共{len(members)}人"
        if stats.get("has_infants"):
            member_desc += "，有婴幼儿"
        if stats.get("has_children"):
            member_desc += "，有儿童"
        if stats.get("has_seniors"):
            member_desc += "，有老人"
        lines.append(member_desc)

        # 年龄范围
        if stats.get("min_age") and stats.get("max_age"):
            lines.append(f"年龄范围：{stats['min_age']}-{stats['max_age']}岁")

        # 偏好
        if preferences.get("food_preferences"):
            lines.append(f"饮食偏好：{', '.join(preferences['food_preferences'][:5])}")
        if preferences.get("hobbies"):
            lines.append(f"兴趣爱好：{', '.join(preferences['hobbies'][:5])}")
        if preferences.get("dietary_restrictions"):
            lines.append(f"饮食禁忌：{', '.join(preferences['dietary_restrictions'])}")

        # 财务
        lines.append(f"建议预算：{financial.get('suggested_daily_budget_per_person', 600)}元/天/人")
        lines.append(f"建议住宿：{financial.get('suggested_hotel_star', '3-4星酒店')}")

        # 健康
        if health:
            health_notes = [h["notes"] for h in health[:3]]
            lines.append(f"健康注意：{'; '.join(health_notes)}")

        return "\n".join(lines)

    def _analyze_trip_constraints(
        self,
        user_profile: Dict[str, Any],
        start_date: date,
        end_date: date,
        budget: Optional[float],
    ) -> Dict[str, Any]:
        """分析旅行约束条件"""
        age_stats = user_profile.get("age_distribution", {}).get("stats", {})
        age_dist = user_profile.get("age_distribution", {}).get("distribution", {})

        constraints = []
        avoid = []
        prefer = []
        max_activity_hours = 10
        max_walking_km = 10

        # 根据年龄组合约束
        for group_name, group_members in age_dist.items():
            if not group_members:
                continue

            group_config = AGE_GROUP_CHARACTERISTICS.get(group_name, {})

            constraints.extend(group_config.get("constraints", []))
            avoid.extend(group_config.get("avoid", []))
            prefer.extend(group_config.get("prefer", []))

            # 取最严格的限制
            group_hours = group_config.get("max_activity_hours", 10)
            group_km = group_config.get("max_walking_km", 10)
            max_activity_hours = min(max_activity_hours, group_hours)
            max_walking_km = min(max_walking_km, group_km)

        # 去重
        constraints = list(set(constraints))
        avoid = list(set(avoid))
        prefer = list(set(prefer))

        # 预算约束
        duration_days = (end_date - start_date).days + 1
        member_count = user_profile.get("member_count", 1)

        if budget:
            budget_total = budget.get("total", 0) if isinstance(budget, dict) else budget
            daily_budget_per_person = budget_total / duration_days / member_count if budget_total else 600
            if daily_budget_per_person < 300:
                constraints.append("严格控制预算")
                avoid.append("高消费场所")
                prefer.append("免费景点")
        else:
            # 使用推断的预算
            daily_budget_per_person = user_profile.get(
                "financial_profile", {}
            ).get("suggested_daily_budget_per_person", 600)

        # 构建摘要
        summary_parts = []
        if constraints:
            summary_parts.append(f"约束：{', '.join(constraints[:5])}")
        if avoid:
            summary_parts.append(f"避免：{', '.join(avoid[:5])}")
        if prefer:
            summary_parts.append(f"推荐：{', '.join(prefer[:5])}")
        summary_parts.append(f"每日活动时长上限：{max_activity_hours}小时")
        summary_parts.append(f"每日步行上限：{max_walking_km}公里")

        return {
            "constraints": constraints,
            "avoid": avoid,
            "prefer": prefer,
            "max_activity_hours": max_activity_hours,
            "max_walking_km": max_walking_km,
            "daily_budget_per_person": daily_budget_per_person,
            "total_budget": budget,
            "summary": "\n".join(summary_parts),
        }
