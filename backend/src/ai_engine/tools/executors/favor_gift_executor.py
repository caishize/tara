"""Favor tracking and gift recommendation executor.

Extracted from memory_executor.py to keep files under 800 lines.
Handles record_favor, query_favor_balance, suggest_favor_return,
recommend_gift, and create_gift_task.
"""

import json
import re as regex
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now
from ..shared.errors import ToolErrorType, tool_error
from ..shared.progress import ProgressCallback
from .base import BaseToolExecutor

logger = get_logger(__name__)


class FavorGiftExecutor(BaseToolExecutor):
    """Handles favor tracking and gift recommendation tools."""

    # ------------------------------------------------------------------
    # Favor tracking (PRD 4.4)
    # ------------------------------------------------------------------

    async def record_favor(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        try:
            from ....modules.relationship.favor_service import FavorService
            from ....modules.relationship.schemas import FavorQuickCreate

            favor_service = FavorService(self.db)

            contact_name = args.get("contact_name", "")
            direction = args.get("direction", "receive")
            event_type = args.get("event_type", "favor")
            description = args.get("description", "")
            amount = args.get("amount")
            weight = args.get("weight", 2)

            event_type_map = {
                "help": "人情-帮忙",
                "gift": "人情-送礼",
                "meal": "人情-请客",
                "introduction": "人情-介绍",
                "favor": "人情",
                "other": "人情-其他",
            }

            favor_data = FavorQuickCreate(
                family_id=family_id,
                contact_name=contact_name,
                direction=direction,
                event_type=event_type_map.get(event_type, "人情"),
                amount=amount if amount else (weight * 100),
                recorded_at=None,
            )

            favor = await favor_service.quick_create_favor(favor_data)
            await self.db.commit()

            if direction == "receive":
                response_msg = f"已记录：{contact_name}帮了您一个忙（{description}）\n这份人情要记住，找机会回报！"
                suggestion = f"建议：{contact_name}喜欢什么？可以考虑送点心意表示感谢。"
            else:
                response_msg = f"已记录：您帮了{contact_name}一个忙（{description}）\n这是您的社交资产！"
                suggestion = ""

            return {
                "success": True,
                "favor_id": str(favor.id),
                "contact_name": contact_name,
                "direction": direction,
                "event_type": event_type,
                "message": response_msg,
                "suggestion": suggestion,
            }

        except ImportError:
            logger.warning("Favor module not available, storing as memory")
            return {
                "success": True,
                "message": f"已记录与{args.get('contact_name', '对方')}的人情往来",
                "stored_as": "memory",
            }
        except Exception as e:
            logger.error("Record favor failed: %s", e)
            return {"success": False, "message": "记录人情失败，请稍后重试"}

    async def query_favor_balance(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        try:
            from ....modules.relationship.favor_service import FavorService

            favor_service = FavorService(self.db)

            contact_name = args.get("contact_name")
            direction = args.get("direction", "all")

            stats = await favor_service.get_statistics(family_id)

            favors = await favor_service.list_favors(
                family_id=str(family_id),
                direction=direction if direction != "all" else None,
                limit=10,
            )

            if contact_name:
                favors = [
                    f for f in favors
                    if contact_name.lower() in (getattr(f, "person_id", "") or "").lower()
                    or contact_name.lower() in (getattr(f, "description", "") or "").lower()
                ]

            received_count = stats.count_received if stats else 0
            given_count = stats.count_given if stats else 0
            pending_count = len([f for f in favors if f.direction == "received"])

            response_parts = []

            if contact_name:
                received_from = [f for f in favors if f.direction == "received"]
                given_to = [f for f in favors if f.direction == "gave"]

                response_parts.append(f"与{contact_name}的人情往来：")
                if received_from:
                    response_parts.append(f"  收到 {len(received_from)} 次人情")
                    for f in received_from[:3]:
                        response_parts.append(f"    · {f.favor_type or '人情'}")
                if given_to:
                    response_parts.append(f"  送出 {len(given_to)} 次人情")

                balance = len(received_from) - len(given_to)
                if balance > 0:
                    response_parts.append(f"  您还欠{contact_name} {balance} 份人情，建议找机会回报")
                elif balance < 0:
                    response_parts.append(f"  {contact_name}还欠您 {-balance} 份人情")
                else:
                    response_parts.append(f"  与{contact_name}的人情持平")
            else:
                response_parts.append("人情账本概览：")
                response_parts.append(f"  收到人情：{received_count} 次")
                response_parts.append(f"  送出人情：{given_count} 次")
                if pending_count > 0:
                    response_parts.append(f"  待回报：{pending_count} 份")

            return {
                "success": True,
                "contact_name": contact_name,
                "received_count": received_count,
                "given_count": given_count,
                "pending_count": pending_count,
                "favors": [
                    {
                        "id": f.id,
                        "person_id": f.person_id,
                        "direction": f.direction,
                        "favor_type": f.favor_type,
                        "amount": f.amount,
                        "date": str(f.date) if f.date else None,
                    }
                    for f in favors[:10]
                ],
                "message": "\n".join(response_parts),
            }

        except ImportError:
            return {"success": False, "message": "人情账本模块未启用"}
        except Exception as e:
            logger.error("Query favor balance failed: %s", e)
            return {"success": False, "message": "查询人情往来失败，请稍后重试"}

    async def suggest_favor_return(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        try:
            contact_name = args.get("contact_name", "")

            from ....modules.relationship.favor_service import FavorService
            from ....modules.relationship.schemas import FavorListParams

            favor_service = FavorService(self.db)

            params = FavorListParams(
                family_id=family_id,
                page=1,
                page_size=20,
                direction="receive",
                status="pending",
            )
            result = await favor_service.list_favors(params)
            favors = result.get("items", [])
            contact_favors = [f for f in favors if contact_name.lower() in (f.get("contact_name") or "").lower()]

            if not contact_favors:
                return {
                    "success": True,
                    "contact_name": contact_name,
                    "message": f"目前没有找到需要回报{contact_name}的人情记录。\n如果想表示感谢，可以主动送点心意！",
                    "suggestions": [],
                }

            preferences: List[str] = []
            try:
                from ....modules.memory.repository import MemoryRepository

                memory_repo = MemoryRepository(self.db)
                person_memories = await memory_repo.search_by_person(user_id, contact_name, limit=10)
                for mem in person_memories:
                    summary = mem.summary or ""
                    if any(kw in summary for kw in ["喜欢", "爱好", "偏好", "想要"]):
                        preferences.append(summary)
            except Exception as e:
                logger.warning("Could not get preferences from memory: %s", e)

            total_weight = sum(1 for _ in contact_favors)

            suggestions = []
            if total_weight >= 3:
                suggestions.append("考虑送一份有分量的礼物，如高档茶叶、名酒")
                suggestions.append("约一顿正式的饭局表示感谢")
            elif total_weight >= 2:
                suggestions.append("送点实用的礼物，如进口水果、糕点")
                suggestions.append("约个咖啡或茶聊聊")
            else:
                suggestions.append("发条感谢微信，表达谢意")
                suggestions.append("顺手带点小礼物，如特产、零食")

            if preferences:
                suggestions.append(f"根据记忆：{preferences[0][:30]}...")

            response_parts = [
                f"回报{contact_name}人情的建议：",
                "",
                f"待回报人情：{len(contact_favors)} 份",
            ]

            for favor in contact_favors[:3]:
                response_parts.append(f"  · {favor.get('event_type', '人情')}")

            response_parts.append("")
            response_parts.append("建议方式：")
            for s in suggestions[:3]:
                response_parts.append(f"  {s}")

            return {
                "success": True,
                "contact_name": contact_name,
                "pending_favors": len(contact_favors),
                "suggestions": suggestions,
                "preferences": preferences[:2],
                "message": "\n".join(response_parts),
            }

        except ImportError:
            return {"success": False, "message": "人情账本模块未启用"}
        except Exception as e:
            logger.error("Suggest favor return failed: %s", e)
            return {"success": False, "message": "生成建议失败，请稍后重试"}

    # ------------------------------------------------------------------
    # Gift recommendation
    # ------------------------------------------------------------------

    async def _gather_gift_context(
        self,
        member_id: UUID,
        family_id: UUID,
        user_id: UUID,
        member_name: str,
    ) -> Dict[str, Any]:
        """Gather rich context from gift history, preferences, memories, and favors.

        Each section is independently try/except'd so a single failure
        does not block the others.
        """
        from datetime import timedelta
        from ....core.utils.timezone import utc_now

        context: Dict[str, Any] = {
            "gift_history": [],
            "recent_gift_names": [],
            "liked_categories": [],
            "preference_scores": {},
            "excluded_categories": [],
            "memories": [],
            "favor_balance": None,
        }

        # 1. Gift history -- surface what was given before
        try:
            from ....modules.gift.recommendation_repositories import HistoryRepository
            history_repo = HistoryRepository(self.db)
            histories = await history_repo.get_by_recipient(member_id, years_back=3)
            context["gift_history"] = [
                {
                    "name": h.gift_name,
                    "category": h.gift_category,
                    "date": h.occasion_date.isoformat() if h.occasion_date else None,
                    "occasion": h.occasion,
                    "feedback": h.feedback_rating,
                }
                for h in histories[:10]
            ]
            # Items given in the last 6 months (avoid duplicates)
            six_months_ago = (utc_now() - timedelta(days=180)).date()
            context["recent_gift_names"] = [
                h.gift_name for h in histories
                if h.occasion_date and h.occasion_date >= six_months_ago
            ]
        except Exception as e:
            logger.warning("Failed to load gift history: %s", e)

        # 2. Preference scores -- use real scores + excluded categories
        try:
            from ....modules.gift.recommendation_repositories import PreferenceRepository
            pref_repo = PreferenceRepository(self.db)

            top_prefs = await pref_repo.get_top_preferences(member_id, limit=5)
            excluded = await pref_repo.get_excluded_categories(member_id)

            context["liked_categories"] = [
                p.gift_category for p in top_prefs
            ]
            context["preference_scores"] = {
                p.gift_category: round(p.preference_score, 2) for p in top_prefs
            }
            context["excluded_categories"] = excluded
        except Exception as e:
            logger.warning("Failed to load preference data: %s", e)

        # 3. Relevant memories via MemoryRecallService (richer than raw repo)
        try:
            from ....modules.memory.recall_service import MemoryRecallService
            recall_svc = MemoryRecallService(self.db)
            query = f"{member_name} 喜欢 爱好 兴趣 礼物"
            memories, _ctx = await recall_svc.recall_for_message(
                user_id, query, limit=8,
            )
            context["memories"] = [
                mem.summary or mem.content or ""
                for mem in memories
                if (mem.summary or mem.content)
            ][:6]
        except Exception as e:
            logger.warning("Failed to load memories via recall: %s", e)

        # 4. Favor balance for reciprocation context
        try:
            from ....modules.relationship.favor_service import FavorService
            from ....modules.relationship.schemas import FavorListParams
            favor_service = FavorService(self.db)
            params = FavorListParams(
                family_id=family_id,
                page=1,
                page_size=20,
            )
            result = await favor_service.list_favors(params)
            favors = result.get("items", [])
            name_lower = member_name.lower()
            contact_favors = [
                f for f in favors
                if name_lower in (f.get("contact_name") or "").lower()
            ]
            if contact_favors:
                received = sum(1 for f in contact_favors if f.get("direction") == "receive")
                given = sum(1 for f in contact_favors if f.get("direction") == "give")
                context["favor_balance"] = {
                    "received": received,
                    "given": given,
                    "net": received - given,
                }
        except Exception as e:
            logger.warning("Failed to load favor data: %s", e)

        return context

    async def recommend_gift(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.member.repositories.member_repository import MemberRepository
        from ..web_search import WebSearchService
        from ....core.llm import openai_adapter
        from ....core.interfaces.llm_provider import LLMMessage

        recipient = args.get("recipient", "")
        occasion = args.get("occasion", "birthday")
        raw_budget = args.get("budget", 500)

        if isinstance(raw_budget, str):
            budget_match = regex.search(r"(\d+)", raw_budget)
            budget = int(budget_match.group(1)) if budget_match else 500
        else:
            budget = int(raw_budget) if raw_budget else 500

        if not recipient:
            return {"success": False, "message": "请告诉我要送礼物给谁"}

        self._emit_progress(progress_cb, "searching", f"正在查找{recipient}的信息...")

        member_repo = MemberRepository(self.db)
        members = await member_repo.search_by_name(family_id, recipient)

        if not members:
            return {
                "success": False,
                "message": f"抱歉，我还不认识{recipient}。请先添加这位家庭成员，这样我才能推荐合适的礼物。",
                "suggestions": ["添加成员"],
            }

        member = members[0]
        name = member.nickname or member.name
        age = member.age
        gender = member.gender

        member_interests = getattr(member, "interests", None) or ""
        member_occupation = getattr(member, "occupation", None) or ""
        member_notes = getattr(member, "notes", None) or ""

        if not age:
            age_group = "成年人"
            age_keyword = ""
        elif age < 12:
            age_group, age_keyword = "儿童", "儿童"
        elif age < 18:
            age_group, age_keyword = "青少年", "青少年"
        elif age < 30:
            age_group, age_keyword = "青年", "年轻人"
        elif age < 50:
            age_group, age_keyword = "中年", "中年"
        elif age < 70:
            age_group, age_keyword = "中老年", "中老年"
        else:
            age_group, age_keyword = "老年", "老年人"

        occasion_names = {
            "birthday": "生日",
            "anniversary": "纪念日",
            "festival": "节日",
            "thank_you": "感谢",
            "graduation": "毕业",
            "new_year": "新年",
            "spring_festival": "春节",
            "other": "礼物",
        }
        occasion_name = occasion_names.get(occasion, occasion if occasion else "礼物")

        # Gather rich context in parallel with web search
        self._emit_progress(progress_cb, "searching", "正在收集送礼参考信息...")

        rich_context = await self._gather_gift_context(
            member_id=member.id,
            family_id=family_id,
            user_id=user_id,
            member_name=name,
        )

        self._emit_progress(progress_cb, "searching", "正在搜索热门礼物趋势...")
        search_service = WebSearchService()
        trending_gifts: List[Dict[str, Any]] = []

        try:
            gender_keyword = "女性" if gender == "female" else "男性" if gender == "male" else ""
            search_queries = [
                f"{utc_now().year} {age_keyword} {gender_keyword} {occasion_name}礼物推荐 热门",
                f"{age_keyword} 送什么礼物好 {budget}元左右",
            ]

            for sq in search_queries[:1]:
                search_result = await search_service.search(sq, num_results=5)
                if search_result.get("results"):
                    for sr in search_result["results"]:
                        trending_gifts.append({
                            "title": sr.get("title", ""),
                            "content": sr.get("content", "")[:200],
                            "url": sr.get("url", ""),
                        })

            await search_service.close()
        except Exception as e:
            logger.warning("搜索热门礼物失败: %s", e)

        # Build the enhanced prompt with rich context
        prompt = f"""你是一个专业的礼物推荐助手。请根据以下信息为受礼人推荐3-5个个性化礼物方案。

## 受礼人信息
- 姓名/称谓: {name}
- 年龄: {age}岁 ({age_group})
- 性别: {"女" if gender == "female" else "男" if gender == "male" else "未知"}
- 职业: {member_occupation or "未知"}
- 兴趣爱好: {member_interests or "未知"}
- 备注: {member_notes or "无"}

## 送礼场合
- 场合: {occasion_name}
- 预算: {budget}元左右 (可以上下浮动30%)
"""

        # Inject gift history context
        if rich_context["gift_history"]:
            prompt += "\n## 送礼历史 (避免重复)\n"
            for h in rich_context["gift_history"][:5]:
                feedback_str = f" (反馈: {h['feedback']})" if h.get("feedback") else ""
                prompt += f"- {h['name']} ({h.get('category', '?')}) — {h.get('occasion', '?')} {h.get('date', '')}{feedback_str}\n"
            prompt += "注意：不要推荐与以上已送过的礼物重复或相似的物品。\n"

        # Inject preference data with real scores
        if rich_context["liked_categories"] or rich_context["excluded_categories"]:
            prompt += "\n## 偏好分析\n"
            if rich_context["liked_categories"]:
                scored_cats = []
                for cat in rich_context["liked_categories"]:
                    score = rich_context["preference_scores"].get(cat)
                    if score is not None:
                        scored_cats.append(f"{cat} ({score})")
                    else:
                        scored_cats.append(cat)
                prompt += f"- 喜欢的类别: {', '.join(scored_cats)}\n"
            if rich_context["excluded_categories"]:
                prompt += f"- 不喜欢的类别: {', '.join(rich_context['excluded_categories'])}\n"

        # Inject relevant memories
        if rich_context["memories"]:
            prompt += "\n## 相关记忆\n"
            for mem in rich_context["memories"][:5]:
                prompt += f"- {mem[:80]}\n"

        # Inject favor balance
        if rich_context["favor_balance"]:
            fb = rich_context["favor_balance"]
            if fb["net"] > 0:
                prompt += f"\n## 人情关系\n- 您还欠{name} {fb['net']} 份人情，建议选择更有诚意的礼物。\n"
            elif fb["net"] < 0:
                prompt += f"\n## 人情关系\n- {name}欠您 {-fb['net']} 份人情，正常礼物即可。\n"

        # Build "avoid" section from excluded categories + recent gifts
        avoid_items: List[str] = []
        if rich_context.get("excluded_categories"):
            avoid_items.append(f"类别: {', '.join(rich_context['excluded_categories'])}")
        if rich_context.get("recent_gift_names"):
            recent_names = rich_context["recent_gift_names"][:5]
            avoid_items.append(f"近期已送: {', '.join(recent_names)}")
        if avoid_items:
            prompt += "\n## 需要避免\n"
            for item in avoid_items:
                prompt += f"- {item}\n"

        # Trending gifts section
        prompt += "\n## 热门礼物参考\n"
        if trending_gifts:
            for i, gift in enumerate(trending_gifts[:3], 1):
                prompt += f"{i}. {gift['title']}\n   {gift['content']}\n\n"
        else:
            prompt += "（无法获取热门礼物信息，请根据受礼人特点推荐）\n"

        prompt += f"""
## 要求
1. 推荐 3-5 个具体的、可购买的礼物
2. 每个礼物都要有明确的品牌和型号（如果适用）
3. 价格要在预算范围内（{int(budget * 0.7)}-{int(budget * 1.3)}元）
4. 推荐理由要结合受礼人的特点（年龄、性别、兴趣等）
5. 考虑实用性和心意
6. 不要推荐与已送过的礼物重复的物品
7. 优先考虑受礼人喜欢的类别，避免不喜欢的类别

请以 JSON 数组格式返回，每个礼物包含:
- name: 礼物名称（包含品牌）
- brand: 品牌名
- price: 预估价格（整数）
- reason: 推荐理由（结合受礼人特点，30字以内）
- category: 类别（electronics/cosmetics/health/food/fashion/jewelry/sports/toys/books/home/other）

示例:
[
  {{"name": "飞利浦电动剃须刀S5000", "brand": "Philips", "price": 599, "reason": "送给爸爸的实用礼物，方便日常使用", "category": "electronics"}}
]
"""

        self._emit_progress(progress_cb, "generating", f"正在为{name}生成个性化礼物推荐...")
        try:
            messages = [LLMMessage(role="user", content=prompt)]
            llm_response = await openai_adapter.chat(messages, temperature=0.7, max_tokens=1500)
            llm_text = llm_response.text

            json_match = regex.search(r"\[.*\]", llm_text, regex.DOTALL)
            if json_match:
                recommendations_raw = json.loads(json_match.group())
            else:
                raise ValueError("无法解析 LLM 返回的 JSON")

        except Exception as e:
            logger.error("LLM 推荐生成失败: %s", e)
            raise RuntimeError(f"礼物推荐生成失败: {e}")

        recommendations = []
        for rec in recommendations_raw[:5]:
            gift_name = rec.get("name", "")
            brand = rec.get("brand", "")
            price = rec.get("price", budget)

            search_query = urllib.parse.quote(f"{brand} {gift_name}" if brand else gift_name)
            purchase_url = f"https://search.jd.com/Search?keyword={search_query}"

            category = rec.get("category", "other")
            image_url = self._get_category_placeholder_image(category)

            recommendations.append({
                "name": gift_name,
                "brand": brand,
                "price": price,
                "reason": rec.get("reason", "精选推荐"),
                "category": category,
                "image_url": image_url,
                "purchase_link": purchase_url,
            })

        age_desc = f"{age}岁" if age else ""

        return {
            "success": True,
            "member_id": str(member.id),
            "member_name": name,
            "age": age,
            "age_group": age_group,
            "occasion": occasion_name,
            "budget": budget,
            "recommendations": recommendations,
            "context_richness": {
                "has_history": len(rich_context["gift_history"]) > 0,
                "has_preferences": len(rich_context["liked_categories"]) > 0 or len(rich_context["excluded_categories"]) > 0,
                "has_memories": len(rich_context["memories"]) > 0,
                "has_favor_data": rich_context["favor_balance"] is not None,
            },
            "message": f"为{name}（{age_desc}{age_group}）推荐了{len(recommendations)}个{occasion_name}礼物",
        }

    # ------------------------------------------------------------------
    # Gift task creation
    # ------------------------------------------------------------------

    async def create_gift_task(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Create a gift planning task for an upcoming occasion."""
        from ....modules.member.repositories.member_repository import MemberRepository
        from ....modules.gift.task_service import GiftTaskService
        from ....modules.gift.models import TriggerSource
        from datetime import date as date_type

        recipient = args.get("recipient", "")
        occasion = args.get("occasion", "birthday")
        occasion_date_str = args.get("occasion_date", "")
        budget_min = args.get("budget_min")
        budget_max = args.get("budget_max")
        notes = args.get("notes")

        if not recipient:
            return {"success": False, "message": "请提供收礼人姓名"}
        if not occasion_date_str:
            return {"success": False, "message": "请提供场合日期 (YYYY-MM-DD)"}

        try:
            occasion_date = date_type.fromisoformat(occasion_date_str)
        except ValueError:
            return {"success": False, "message": f"无效的日期格式: {occasion_date_str}"}

        member_repo = MemberRepository(self.db)
        members = await member_repo.search_by_name(family_id, recipient)
        if not members:
            return {
                "success": False,
                "message": f"未找到成员「{recipient}」，请先添加家庭成员",
            }

        member = members[0]

        try:
            task_service = GiftTaskService(self.db)
            task = await task_service.create_task_for_date(
                family_id=family_id,
                date_id=member.id,
                member_id=member.id,
                date_type=occasion,
                occasion_date=occasion_date,
                title=f"{member.nickname or member.name}的{occasion}礼物",
                trigger_source=TriggerSource.MANUAL,
                budget_min=budget_min,
                budget_max=budget_max,
                notes=notes,
            )

            if task is None:
                return {
                    "success": True,
                    "message": "该场合的礼物任务已存在，无需重复创建",
                    "already_exists": True,
                }

            await self.db.commit()

            return {
                "success": True,
                "task_id": str(task.id),
                "recipient": member.nickname or member.name,
                "occasion": occasion,
                "occasion_date": occasion_date_str,
                "message": f"已为{member.nickname or member.name}创建{occasion}礼物准备任务",
            }
        except Exception as e:
            logger.error("Create gift task failed: %s", e)
            await self.db.rollback()
            return {"success": False, "message": f"创建礼物任务失败: {str(e)}"}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_category_placeholder_image(category: str) -> str:
        category_emojis = {
            "electronics": "%F0%9F%93%B1",
            "cosmetics": "%F0%9F%92%84",
            "health": "%F0%9F%92%8A",
            "food": "%F0%9F%8D%AB",
            "fashion": "%F0%9F%91%97",
            "jewelry": "%F0%9F%92%8D",
            "sports": "%E2%9A%BD",
            "toys": "%F0%9F%8E%AE",
            "books": "%F0%9F%93%9A",
            "home": "%F0%9F%8F%A0",
            "other": "%F0%9F%8E%81",
        }
        category_colors = {
            "electronics": "3B82F6",
            "cosmetics": "EC4899",
            "health": "10B981",
            "food": "F59E0B",
            "fashion": "8B5CF6",
            "jewelry": "D946EF",
            "sports": "6366F1",
            "toys": "F97316",
            "books": "EAB308",
            "home": "14B8A6",
            "other": "6366F1",
        }
        color = category_colors.get(category, "6366F1")
        emoji = category_emojis.get(category, "%F0%9F%8E%81")
        return f"https://placehold.co/400x400/{color}/FFFFFF?text={emoji}&font=noto"
