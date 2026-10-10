"""Smart gift recommendation service — LLM-powered context-aware recommendations.

Builds an enhanced member context (profile, history, preferences, dedup analysis)
and generates personalized gift suggestions via an LLM provider.
"""
import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .dedup_analyzer import DedupAnalysis, DedupAnalyzer
from .models import GiftCategory, RecommendStatus, TriggerSource
from .recommendation_repositories import (
    HistoryRepository,
    PreferenceRepository,
    RecommendationRepository,
)
from ...core.interfaces.llm_provider import ILLMProvider
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


@dataclass
class EnhancedContext:
    member_id: UUID
    member_name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    occupation: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    habits: Dict[str, Any] = field(default_factory=dict)
    personality_traits: List[str] = field(default_factory=list)
    special_notes: Optional[str] = None
    relation_type: Optional[str] = None
    intimacy_level: int = 5
    history_summary: Dict[str, Any] = field(default_factory=dict)
    preference_scores: Dict[str, float] = field(default_factory=dict)
    dedup_analysis: Optional[DedupAnalysis] = None
    occasion: str = ""
    occasion_date: Optional[date] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    additional_preferences: Optional[str] = None
    exclude_categories: List[str] = field(default_factory=list)
    exclude_gift_names: List[str] = field(default_factory=list)


INTIMACY_BUDGET_MULTIPLIER = {
    1: 0.5, 2: 0.5, 3: 0.5,
    4: 0.8, 5: 1.0, 6: 1.0,
    7: 1.2, 8: 1.5, 9: 1.5,
    10: 2.0,
}
DEFAULT_BUDGET_MIN = 100
DEFAULT_BUDGET_MAX = 500


class SmartRecommendationService:
    """Generate smart gift recommendations using LLM + member context."""

    def __init__(self, session: AsyncSession, llm_provider: ILLMProvider):
        self.session = session
        self.llm = llm_provider
        self.task_repo = None  # Lazy import to avoid circular
        self.recommendation_repo = RecommendationRepository(session)
        self.history_repo = HistoryRepository(session)
        self.preference_repo = PreferenceRepository(session)
        self.dedup_analyzer = DedupAnalyzer(session)

    def _get_task_repo(self):
        if self.task_repo is None:
            from .task_service import GiftTaskRepository
            self.task_repo = GiftTaskRepository(self.session)
        return self.task_repo

    async def generate_for_task(
        self,
        task,
        requester_user_id: UUID,
        additional_preferences: Optional[str] = None,
        exclude_categories: Optional[List[str]] = None,
        exclude_gift_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        start_time = utc_now()
        task_repo = self._get_task_repo()

        try:
            await task_repo.mark_generating(task.id)
            context = await self._build_enhanced_context(
                member_id=task.member_id, family_id=task.family_id,
                occasion=task.occasion, occasion_date=task.occasion_date,
                budget_min=task.budget_min, budget_max=task.budget_max,
                additional_preferences=additional_preferences,
                exclude_categories=exclude_categories,
                exclude_gift_names=exclude_gift_names,
            )
            prompt = self._build_prompt(context)
            llm_response = await self.llm.generate_text(prompt, temperature=0.7)
            recommendations = self._parse_llm_response(llm_response)
            personalization_score = self._calculate_personalization_score(context)
            processing_time_ms = int((utc_now() - start_time).total_seconds() * 1000)

            rec_data = {
                "family_id": task.family_id,
                "recipient_member_id": task.member_id,
                "requester_user_id": requester_user_id,
                "related_date_id": task.important_date_id,
                "occasion": task.occasion,
                "occasion_date": task.occasion_date,
                "trigger_source": TriggerSource.AUTO_DATE.value,
                "budget_min": context.budget_min,
                "budget_max": context.budget_max,
                "user_preferences": json.dumps(context.preferences, ensure_ascii=False) if context.preferences else None,
                "recommendations": recommendations,
                "status": RecommendStatus.PENDING.value,
                "excluded_categories": context.dedup_analysis.excluded_categories if context.dedup_analysis else [],
                "dedup_warnings": self.dedup_analyzer.to_dict(context.dedup_analysis)["warnings"] if context.dedup_analysis else [],
                "llm_prompt": prompt[:1000],
                "llm_model": getattr(self.llm, "model_name", "gpt-4"),
                "generation_time_ms": processing_time_ms,
                "expires_at": utc_now() + timedelta(days=7),
            }
            rec = await self.recommendation_repo.create(rec_data)
            await task_repo.mark_completed(task.id, rec.id, processing_time_ms)

            return {
                "id": str(rec.id), "task_id": str(task.id),
                "member_name": context.member_name, "occasion": task.occasion,
                "recommendations": recommendations,
                "personalization_score": personalization_score,
                "dedup_warnings": rec_data["dedup_warnings"],
                "processing_time_ms": processing_time_ms,
            }
        except Exception as e:
            await task_repo.mark_failed(task.id, str(e))
            logger.error("Failed to generate recommendation for task %s: %s", task.id, e)
            raise

    async def _build_enhanced_context(
        self, member_id: UUID, family_id: UUID, occasion: str,
        occasion_date: Optional[date] = None,
        budget_min: Optional[int] = None, budget_max: Optional[int] = None,
        additional_preferences: Optional[str] = None,
        exclude_categories: Optional[List[str]] = None,
        exclude_gift_names: Optional[List[str]] = None,
    ) -> EnhancedContext:
        from ..member.repositories.member_repository import MemberRepository
        from ..member.repositories.profile_repository import ProfileRepository
        member_repo = MemberRepository(self.session)
        profile_repo = ProfileRepository(self.session)

        member = await member_repo.get_by_id(member_id)
        if not member:
            raise ValueError(f"Member {member_id} not found")

        from ..member.current_work_helper import get_current_work
        current_work = await get_current_work(self.session, member_id)
        occupation = (current_work or {}).get("position")

        context = EnhancedContext(
            member_id=member_id, member_name=member.name,
            gender=member.gender, age=member.age, occupation=occupation,
            occasion=occasion, occasion_date=occasion_date,
        )
        profile = await profile_repo.get_by_member_id(member_id)
        if profile:
            context.preferences = profile.preferences or {}
            context.habits = profile.habits or {}
            context.personality_traits = profile.personality_traits or []
            context.special_notes = profile.special_notes
        context.intimacy_level = 7

        if budget_min is None or budget_max is None:
            multiplier = INTIMACY_BUDGET_MULTIPLIER.get(context.intimacy_level, 1.0)
            context.budget_min = budget_min or int(DEFAULT_BUDGET_MIN * multiplier)
            context.budget_max = budget_max or int(DEFAULT_BUDGET_MAX * multiplier)
        else:
            context.budget_min = budget_min
            context.budget_max = budget_max

        history = await self.history_repo.get_by_recipient(member_id, years_back=3)
        context.history_summary = {
            "total_gifts": len(history),
            "recent_gifts": [
                {"name": h.gift_name, "category": h.gift_category, "date": h.occasion_date.isoformat()}
                for h in history[:5]
            ],
        }
        preferences = await self.preference_repo.get_all_by_member(member_id)
        context.preference_scores = {p.gift_category: p.preference_score for p in preferences}
        context.dedup_analysis = await self.dedup_analyzer.analyze(member_id, family_id, occasion)
        context.additional_preferences = additional_preferences
        context.exclude_categories = exclude_categories or []
        context.exclude_gift_names = exclude_gift_names or []
        return context

    def _build_prompt(self, ctx: EnhancedContext) -> str:
        likes = ctx.preferences.get("喜欢", ctx.preferences.get("likes", []))
        dislikes = ctx.preferences.get("不喜欢", ctx.preferences.get("dislikes", []))
        hobbies = ctx.habits.get("日常爱好", ctx.habits.get("hobbies", []))
        history_desc = ""
        if ctx.dedup_analysis:
            for cat, stats in ctx.dedup_analysis.category_stats.items():
                history_desc += f"- {cat}: {stats['count']}次"
                if stats.get("last_date"):
                    history_desc += f" (最近: {stats['last_date']})"
                history_desc += "\n"
        excluded = ctx.dedup_analysis.excluded_categories if ctx.dedup_analysis else []
        pref_desc = ""
        for cat, score in sorted(ctx.preference_scores.items(), key=lambda x: x[1], reverse=True)[:5]:
            pref_desc += f"- {cat}: {score:.2f}\n"

        return f"""你是一个专业的礼物推荐顾问，请根据以下详细信息为用户推荐3-5个高度个性化的礼物方案。

## 收礼人详细画像
- 姓名：{ctx.member_name}
- 性别：{ctx.gender or '未知'}
- 年龄：{ctx.age or '未知'}岁
- 职业：{ctx.occupation or '未知'}

## 个人偏好
喜欢：{', '.join(likes) if likes else '未知'}
不喜欢：{', '.join(dislikes) if dislikes else '无特殊忌讳'}
日常爱好：{', '.join(hobbies) if hobbies else '未知'}
性格特征：{', '.join(ctx.personality_traits) if ctx.personality_traits else '未知'}
特殊说明：{ctx.special_notes or '无'}

## 送礼场合
- 场合：{ctx.occasion}
- 日期：{ctx.occasion_date.isoformat() if ctx.occasion_date else '未定'}

## 预算范围
{ctx.budget_min} - {ctx.budget_max} 元

## 历史送礼记录
{history_desc if history_desc else '无历史记录'}

## 偏好学习结果
{pref_desc if pref_desc else '暂无偏好数据'}

## 必须排除的类别
{', '.join(excluded) if excluded else '无'}

## 用户额外要求
{ctx.additional_preferences or '无'}

## 必须排除的礼物名称
{', '.join(ctx.exclude_gift_names) if ctx.exclude_gift_names else '无'}

## 输出格式
请以JSON数组格式返回，每个方案包含：
- name: 礼物名称（具体到品牌或型号）
- category: 类别（英文）
- type: 类型（romantic/practical/luxury/experience/emotional）
- price: 预估价格（元，数字）
- reason: 个性化推荐理由（50字以内）

示例格式：
[{{"name": "戴森V12吸尘器", "category": "home", "type": "practical", "price": 2999, "reason": "..."}}]
"""

    def _parse_llm_response(self, response: str) -> List[Dict]:
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        recommendations = []
        if json_match:
            try:
                recommendations = json.loads(json_match.group())
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse LLM response as JSON: %s", e)
        if not recommendations:
            logger.warning("Using fallback recommendation")
            recommendations = [{
                "name": "精选礼品卡", "category": "custom", "type": "practical",
                "price": 300, "reason": "灵活选择，让收礼人自己挑选喜欢的物品",
            }]
        for rec in recommendations:
            self._enhance_recommendation(rec)
        return recommendations

    def _enhance_recommendation(self, recommendation: Dict) -> None:
        gift_name = recommendation.get("name", "")
        search_query = urllib.parse.quote(gift_name)
        recommendation["purchase_link"] = f"https://search.jd.com/Search?keyword={search_query}"

    def _calculate_personalization_score(self, context: EnhancedContext) -> float:
        score = 0.0
        if context.gender:
            score += 0.05
        if context.age:
            score += 0.05
        if context.occupation:
            score += 0.1
        if context.preferences:
            score += 0.1
        if context.habits:
            score += 0.1
        if context.personality_traits:
            score += 0.05
        if context.special_notes:
            score += 0.05
        history_count = context.history_summary.get("total_gifts", 0)
        if history_count > 0:
            score += min(0.15, history_count * 0.03)
        if context.preference_scores:
            score += min(0.15, len(context.preference_scores) * 0.03)
        if context.relation_type:
            score += 0.1
        if context.intimacy_level != 5:
            score += 0.1
        return min(1.0, score)
