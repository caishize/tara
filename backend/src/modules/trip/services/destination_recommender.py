"""
Destination recommendation service using LLM for intelligent travel suggestions.
"""
from typing import List, Dict, Optional, Any
from uuid import UUID
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import logging

from ....core.interfaces.llm_provider import ILLMProvider
from ....core.utils.timezone import utc_now, local_now

logger = logging.getLogger(__name__)


class DestinationRecommender:
    """Service for generating intelligent destination recommendations."""

    def __init__(
        self,
        db: AsyncSession,
        llm_provider: ILLMProvider,
        vector_db: Optional[Any] = None
    ):
        self.db = db
        self.llm = llm_provider
        self.vector_db = vector_db

    async def analyze_family_composition(
        self,
        family_id: UUID
    ) -> Dict[str, Any]:
        """
        Analyze family composition for destination recommendation.

        Fetches family member info from Module 1 and analyzes:
        - Age distribution (children, adults, elderly)
        - Special needs (child-friendly, elderly-friendly)
        - Interests and preferences

        Args:
            family_id: Family identifier

        Returns:
            Family composition analysis dict
        """
        from sqlalchemy import select
        from ....modules.member.models.member import Member

        result = await self.db.execute(
            select(Member).where(
                Member.family_id == family_id,
                Member.is_deleted == False,
            )
        )
        members = result.scalars().all()

        if not members:
            raise ValueError(f"家庭 {family_id} 没有找到成员信息，无法生成推荐")

        children = []
        adults = []
        elderly = []
        special_needs = set()
        interests = set()

        for m in members:
            age = m.calculate_age()
            info: Dict[str, Any] = {"name": m.name or "", "age": age}

            if age is not None and age < 14:
                needs = ["child_friendly"]
                if age < 4:
                    needs.append("nap_time")
                info["needs"] = needs
                children.append(info)
                special_needs.update(needs)
            elif age is not None and age >= 60:
                info["needs"] = ["slow_pace", "elderly_friendly"]
                elderly.append(info)
                special_needs.update(["slow_pace", "elderly_friendly"])
            else:
                adults.append(info)

            # Extract interests from member tags
            if m.tags and isinstance(m.tags, list):
                interests.update(m.tags)

        return {
            "total_members": len(members),
            "children": children,
            "adults": adults,
            "elderly": elderly,
            "special_needs": sorted(special_needs),
            "interests": sorted(interests) if interests else ["culture", "nature", "food"],
        }

    async def generate_recommendations(
        self,
        family_composition: Dict[str, Any],
        occasion: Optional[str] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        duration_days: Optional[int] = 3,
        season: Optional[str] = None,
        user_input: Optional[str] = None,
        llm_timeout: float = 15.0
    ) -> List[Dict[str, Any]]:
        """
        Generate destination recommendations using LLM.

        Args:
            family_composition: Family composition analysis
            occasion: Travel occasion (国庆, 春节, etc.)
            budget_min: Minimum budget
            budget_max: Maximum budget
            duration_days: Trip duration
            season: Travel season
            user_input: User's natural language request
            llm_timeout: Timeout for LLM call in seconds (default: 15s)

        Returns:
            List of 3 destination recommendations with details
        """
        start_time = utc_now()

        # Build LLM prompt
        prompt = self._build_recommendation_prompt(
            family_composition,
            occasion,
            budget_min,
            budget_max,
            duration_days,
            season,
            user_input
        )

        # Call LLM with timeout
        recommendations = []
        try:
            llm_response = await asyncio.wait_for(
                self.llm.generate_text(prompt, temperature=0.7),
                timeout=llm_timeout,
            )
            recommendations = self._parse_llm_response(llm_response)
        except asyncio.TimeoutError:
            logger.error(f"LLM call timed out after {llm_timeout}s for destination recommendations")
            raise RuntimeError("目的地推荐生成超时，请稍后重试")
        except Exception as e:
            logger.error(f"LLM call failed for destination recommendations: {e}")
            raise RuntimeError(f"目的地推荐生成失败: {e}")

        # Rank and score recommendations
        scored_recommendations = await self.rank_destinations(
            recommendations,
            family_composition,
            budget_min,
            budget_max
        )

        # Calculate generation time
        generation_time_ms = int((utc_now() - start_time).total_seconds() * 1000)

        # Add metadata
        for rec in scored_recommendations:
            rec["generation_time_ms"] = generation_time_ms
            rec["generated_at"] = utc_now().isoformat()

        return scored_recommendations[:3]  # Return top 3

    def _build_recommendation_prompt(
        self,
        family_composition: Dict[str, Any],
        occasion: Optional[str],
        budget_min: Optional[float],
        budget_max: Optional[float],
        duration_days: int,
        season: Optional[str],
        user_input: Optional[str]
    ) -> str:
        """Build LLM prompt for destination recommendation."""

        # Extract family info
        total_members = family_composition.get("total_members", 0)
        children = family_composition.get("children", [])
        elderly = family_composition.get("elderly", [])
        special_needs = family_composition.get("special_needs", [])
        interests = family_composition.get("interests", [])

        # Determine current season if not provided
        if not season:
            current_month = local_now().month
            if current_month in [3, 4, 5]:
                season = "春季"
            elif current_month in [6, 7, 8]:
                season = "夏季"
            elif current_month in [9, 10, 11]:
                season = "秋季"
            else:
                season = "冬季"

        prompt = f"""你是一个专业的家庭旅行规划师。请根据以下信息推荐3个适合的旅行目的地。

家庭成员组成:
- 总人数: {total_members}人
- 儿童: {len(children)}人 (年龄: {', '.join([str(c['age']) + '岁' for c in children]) if children else '无'})
- 老人: {len(elderly)}人 (年龄: {', '.join([str(e['age']) + '岁' for e in elderly]) if elderly else '无'})

特殊需求: {', '.join(special_needs) if special_needs else '无'}
兴趣爱好: {', '.join(interests) if interests else '无特殊偏好'}

旅行参数:
- 场合: {occasion or '家庭休闲游'}
- 预算范围: {budget_min or 0}元 - {budget_max or 10000}元 (总预算)
- 行程天数: {duration_days}天{duration_days - 1}夜
- 季节: {season}

用户输入: {user_input or '请推荐适合全家出游的目的地'}

请为这个家庭推荐3个不同风格的旅行方案，每个方案需包含:

1. destination: 目的地名称
2. trip_type: 旅行类型 (亲子游/休闲游/乐园游/文化游/自然游)
3. suitable_reason: 适合原因 (为什么适合这个家庭)
4. highlights: 行程亮点 (列出3-5个主要看点/活动)
5. budget_estimate: 预算估算 (分项: 交通/住宿/门票/餐饮/其他)
6. best_season: 最佳旅行时间
7. weather_info: 当前季节天气情况
8. attention_points: 注意事项 (针对儿童/老人的特别提醒)
9. estimated_duration: 建议行程天数
10. child_friendly_score: 儿童友好度 (1-10分)
11. elderly_friendly_score: 老人友好度 (1-10分)

请以JSON格式返回，格式如下:
[
  {{
    "destination": "杭州",
    "trip_type": "休闲游",
    "suitable_reason": "适合全家的原因...",
    "highlights": ["西湖游船", "宋城千古情", "动物园看熊猫"],
    "budget_estimate": {{
      "transportation": 800,
      "accommodation": 2400,
      "tickets": 500,
      "food": 1000,
      "other": 300,
      "total": 5000
    }},
    "best_season": "春秋两季",
    "weather_info": "当前{season}气候宜人...",
    "attention_points": ["儿童注意事项", "老人注意事项"],
    "estimated_duration": {duration_days},
    "child_friendly_score": 9,
    "elderly_friendly_score": 8
  }}
]

要求:
- 3个方案要有不同的预算档次和风格
- 考虑家庭成员的年龄和需求
- 预算要符合用户设定的范围
- 选择适合当前季节的目的地
- 给出具体可行的建议
"""

        return prompt

    def _parse_llm_response(self, llm_response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into structured recommendations."""
        import json
        import re

        try:
            # Try to extract JSON from response
            # Look for JSON array pattern
            json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                recommendations = json.loads(json_str)
                return recommendations
            else:
                # Fallback: try parsing entire response
                recommendations = json.loads(llm_response)
                return recommendations
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse destination recommendation JSON: {e}")
            raise RuntimeError("目的地推荐解析失败，请重试")

    async def rank_destinations(
        self,
        recommendations: List[Dict[str, Any]],
        family_composition: Dict[str, Any],
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Rank and score destination recommendations.

        Scoring criteria:
        - Budget fit (within user's budget range)
        - Family composition fit (child-friendly, elderly-friendly)
        - Season appropriateness
        - Overall recommendation confidence

        Args:
            recommendations: List of destination recommendations
            family_composition: Family composition analysis
            budget_min: Minimum budget
            budget_max: Maximum budget

        Returns:
            Ranked list of recommendations with fit scores
        """
        has_children = len(family_composition.get("children", [])) > 0
        has_elderly = len(family_composition.get("elderly", [])) > 0

        for rec in recommendations:
            fit_score = 0.0

            # Budget fit score (0-30 points)
            total_budget = rec.get("budget_estimate", {}).get("total", 0)
            if budget_min and budget_max:
                if budget_min <= total_budget <= budget_max:
                    fit_score += 30
                elif total_budget < budget_min:
                    # Slightly under budget
                    fit_score += 25
                else:
                    # Over budget - penalize
                    over_budget_ratio = (total_budget - budget_max) / budget_max
                    if over_budget_ratio < 0.2:
                        fit_score += 15
                    else:
                        fit_score += 5
            else:
                fit_score += 20

            # Child-friendly score (0-35 points if has children)
            if has_children:
                child_score = rec.get("child_friendly_score", 5)
                fit_score += (child_score / 10) * 35
            else:
                fit_score += 20

            # Elderly-friendly score (0-35 points if has elderly)
            if has_elderly:
                elderly_score = rec.get("elderly_friendly_score", 5)
                fit_score += (elderly_score / 10) * 35
            else:
                fit_score += 20

            rec["fit_score"] = round(fit_score, 2)
            rec["fit_score_max"] = 100

        # Sort by fit score descending
        recommendations.sort(key=lambda x: x.get("fit_score", 0), reverse=True)

        return recommendations

    async def search_destination_knowledge(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search destination knowledge base using vector database.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of relevant destination information
        """
        if not self.vector_db:
            return []

        try:
            results = await self.vector_db.search(
                collection="travel_destinations",
                query=query,
                top_k=top_k
            )
            return results
        except Exception as e:
            logger.error("Vector search error: %s", e)
            return []
