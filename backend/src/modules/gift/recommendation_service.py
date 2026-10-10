"""Gift recommendation service — user-facing recommendation API.

This is the main entry point for the recommendation subsystem.
Sub-modules are re-exported here so existing imports continue to work:
    recommendation_repositories.py  — RecommendationRepository, HistoryRepository, PreferenceRepository
    dedup_analyzer.py               — DedupWarning, DedupAnalysis, DedupAnalyzer
    preference_learning.py          — PreferenceLearningService, PreferenceSummary
    smart_recommendation.py         — SmartRecommendationService, EnhancedContext
"""
import json
import logging
import re
from datetime import date, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    GiftCategory,
    OccasionType,
    RecommendStatus,
    TriggerSource,
)
from .recommendation_repositories import (  # noqa: F401
    HistoryRepository,
    PreferenceRepository,
    RecommendationRepository,
)
from .dedup_analyzer import DedupAnalyzer, DedupAnalysis, DedupWarning  # noqa: F401
from .preference_learning import (  # noqa: F401
    ANNUAL_DECAY_RATE,
    CONFIDENCE_INCREMENT,
    FEEDBACK_SCORE_DELTA,
    MAX_PREFERENCE_SCORE,
    MIN_PREFERENCE_SCORE,
    PreferenceLearningService,
    PreferenceSummary,
)
from .smart_recommendation import (  # noqa: F401
    DEFAULT_BUDGET_MAX,
    DEFAULT_BUDGET_MIN,
    EnhancedContext,
    INTIMACY_BUDGET_MULTIPLIER,
    SmartRecommendationService,
)
from ...core.interfaces.llm_provider import ILLMProvider
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class RecommendationService:
    """User-facing gift recommendation service."""

    def __init__(self, db: AsyncSession, llm_provider: ILLMProvider, encryption_service=None):
        self.db = db
        self.recommendation_repo = RecommendationRepository(db)
        self.history_repo = HistoryRepository(db)
        self.preference_repo = PreferenceRepository(db)
        self.llm = llm_provider
        self.encryption = encryption_service

    async def generate_recommendation(
        self,
        family_id: UUID,
        requester_user_id: UUID,
        recipient_member_id: UUID,
        occasion: str,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        user_preferences: Optional[str] = None,
        related_date_id: Optional[UUID] = None,
        trigger_source: str = TriggerSource.USER_REQUEST.value,
        member_profile: Optional[Dict] = None,
    ) -> Dict:
        start_time = utc_now()
        history = await self.history_repo.get_by_recipient(recipient_member_id, years_back=3)
        category_counts = await self.history_repo.get_category_counts(recipient_member_id, years_back=3)
        preferences = await self.preference_repo.get_all_by_member(recipient_member_id)
        excluded_categories = await self.preference_repo.get_excluded_categories(recipient_member_id)

        prompt = self._build_recommendation_prompt(
            member_profile or {}, occasion, budget_min, budget_max,
            user_preferences, history, category_counts, preferences, excluded_categories,
        )
        llm_response = await self.llm.generate_text(prompt, temperature=0.7)
        recommendations = self._parse_llm_response(llm_response)
        generation_time_ms = int((utc_now() - start_time).total_seconds() * 1000)

        rec_data = {
            "family_id": family_id, "recipient_member_id": recipient_member_id,
            "requester_user_id": requester_user_id, "related_date_id": related_date_id,
            "occasion": occasion,
            "occasion_date": date.today() + timedelta(days=30) if occasion == OccasionType.BIRTHDAY.value else None,
            "trigger_source": trigger_source, "budget_min": budget_min, "budget_max": budget_max,
            "user_preferences": user_preferences, "recommendations": recommendations,
            "status": RecommendStatus.PENDING.value,
            "excluded_categories": excluded_categories,
            "dedup_warnings": self._generate_dedup_warnings(category_counts),
            "llm_prompt": prompt[:500],
            "llm_model": self.llm.model_name if hasattr(self.llm, "model_name") else "gpt-4",
            "generation_time_ms": generation_time_ms,
            "expires_at": utc_now() + timedelta(days=7),
        }
        rec = await self.recommendation_repo.create(rec_data)
        return await self._to_dict(rec)

    def _build_recommendation_prompt(
        self, member_profile, occasion, budget_min, budget_max,
        user_preferences, history, category_counts, preferences, excluded_categories,
    ) -> str:
        prompt = f"""你是一个专业的礼物推荐助手。请根据以下信息为受礼人推荐3-5个个性化礼物方案。

受礼人画像:
- 年龄: {member_profile.get('age', '未知')}
- 性别: {member_profile.get('gender', '未知')}
- 职业: {member_profile.get('occupation', '未知')}
- 兴趣爱好: {member_profile.get('interests', '未知')}

场合: {occasion}
预算范围: {budget_min or 0}元 - {budget_max or 10000}元
用户偏好: {user_preferences or '无特殊偏好'}

历史送礼记录(近3年):
"""
        for cat, count in category_counts.items():
            prompt += f"- {cat}: {count}次\n"
        if excluded_categories:
            prompt += f"\n排除的类别: {', '.join(excluded_categories)}\n"
        if preferences:
            prompt += "\n偏好评分:\n"
            for pref in preferences[:5]:
                prompt += f"- {pref.gift_category}: {pref.preference_score:.2f}\n"
        prompt += """
请以JSON格式返回3-5个推荐方案,每个方案包含:
- name, category, type, price, reason, purchase_link, image_url
"""
        return prompt

    def _parse_llm_response(self, response: str) -> List[Dict]:
        json_match = re.search(r"\[.*\]", response, re.DOTALL)
        if json_match:
            try:
                recommendations = json.loads(json_match.group())
                if recommendations:
                    return recommendations
            except json.JSONDecodeError:
                pass
        raise RuntimeError("LLM 未能返回有效的礼物推荐，请稍后重试")

    def _generate_dedup_warnings(self, category_counts: Dict) -> Dict:
        warnings = {}
        for category, count in category_counts.items():
            if count >= 3:
                warnings[category] = f"已连续{count}次送{category}类礼物,建议尝试其他类别"
        return warnings

    async def get_recommendation(self, recommendation_id: UUID) -> Optional[Dict]:
        rec = await self.recommendation_repo.get_by_id(recommendation_id)
        if not rec:
            return None
        return await self._to_dict(rec)

    async def list_recommendations(
        self, family_id: UUID, status: Optional[str] = None,
        member_id: Optional[UUID] = None, limit: int = 20, offset: int = 0,
    ) -> List[Dict]:
        recs = await self.recommendation_repo.get_by_family(family_id, status, member_id, limit, offset)
        return [await self._to_dict(rec) for rec in recs]

    async def mark_viewed(self, recommendation_id: UUID) -> Optional[Dict]:
        rec = await self.recommendation_repo.update_status(recommendation_id, RecommendStatus.VIEWED.value)
        return await self._to_dict(rec) if rec else None

    async def select_option(self, recommendation_id: UUID, option_index: int) -> Optional[Dict]:
        rec = await self.recommendation_repo.update_status(
            recommendation_id, RecommendStatus.SELECTED.value, selected_option_index=option_index,
        )
        return await self._to_dict(rec) if rec else None

    async def _to_dict(self, rec) -> Dict:
        from ..member.repositories.member_repository import MemberRepository
        member_repo = MemberRepository(self.db)
        member = await member_repo.get_by_id(rec.recipient_member_id)
        member_name = member.name if member else "Unknown"
        preferences = await self.preference_repo.get_all_by_member(rec.recipient_member_id)
        preference_map = {p.gift_category: p.preference_score for p in preferences}

        recs_out = []
        for i, r in enumerate(rec.recommendations or []):
            recs_out.append({
                "id": f"{rec.id}_{i}", "member_id": str(rec.recipient_member_id),
                "occasion": rec.occasion, "gift_name": r.get("name", ""),
                "category": r.get("category", ""), "description": r.get("type", ""),
                "reason": r.get("reason", ""),
                "price_range_min": rec.budget_min, "price_range_max": rec.budget_max,
                "estimated_price": r.get("price"),
                "purchase_url": r.get("purchase_link"), "image_url": r.get("image_url"),
                "confidence_score": 0.7, "tags": [],
                "created_at": rec.created_at.isoformat(),
            })
        return {
            "id": str(rec.id), "member_id": str(rec.recipient_member_id),
            "member_name": member_name, "occasion": rec.occasion,
            "recommendations": recs_out,
            "generated_at": rec.created_at.isoformat(),
            "_family_id": str(rec.family_id),
            "_occasion_date": rec.occasion_date.isoformat() if rec.occasion_date else None,
            "_budget_min": float(rec.budget_min) if rec.budget_min else None,
            "_budget_max": float(rec.budget_max) if rec.budget_max else None,
            "_user_preferences": rec.user_preferences,
            "_status": rec.status,
            "_selected_option_index": rec.selected_option_index,
            "_dedup_warnings": rec.dedup_warnings,
            "_generation_time_ms": rec.generation_time_ms,
            "_viewed_at": rec.viewed_at.isoformat() if rec.viewed_at else None,
            "_selected_at": rec.selected_at.isoformat() if rec.selected_at else None,
            "_expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
        }
