"""
Smart Itinerary Planner - AI-powered travel itinerary generation with professional traveler insights.

This service provides:
1. Style-based itinerary generation (relaxed, intensive, budget, luxury, adventure, cultural)
2. Professional traveler advice for each activity
3. Family-aware scheduling (children nap time, elderly pace)
4. Trip design rationale and alternatives
5. Real-time itinerary adjustments
6. Weather-aware activity recommendations
"""
from typing import List, Dict, Optional, Any
from uuid import UUID
from datetime import date
import json
import asyncio
import time as time_module

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ..models.trip_plan import TripPlan
from ..models.trip_itinerary import TripItinerary
from ....core.interfaces.llm_provider import ILLMProvider
from ....config.logging import get_logger
from .weather_service import WeatherService, WeatherForecast
from ....core.utils.timezone import utc_now, local_now
from .itinerary_styles import (
    ItineraryStyle,
    STYLE_CONFIGS,
    analyze_family_constraints,
    merge_style_configs,
    map_styles_to_keywords,
)
from .itinerary_prompt_builder import (
    build_weather_context,
    build_search_context,
    build_smart_prompt,
)
from .itinerary_response_parser import (
    parse_smart_response,
    extract_balanced_json,
    get_default_structure,
)

logger = get_logger(__name__)


class SmartItineraryPlanner:
    """智能行程规划器 - 提供专业旅行家级别的行程规划"""

    def __init__(self, db: AsyncSession, llm_provider: ILLMProvider):
        self.db = db
        self.llm = llm_provider
        self.weather_service = WeatherService()
        from ....ai_engine.tools.web_search import get_web_search_service
        self.web_search = get_web_search_service()

    # Backward-compatible instance method wrappers for extracted functions
    def _analyze_family_constraints(
        self,
        family_composition: Dict[str, Any],
        preferences: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return analyze_family_constraints(family_composition, preferences)

    def _merge_style_configs(self, styles: List[ItineraryStyle]) -> Dict[str, Any]:
        return merge_style_configs(styles)

    def _build_smart_prompt(
        self,
        destination: str,
        duration_days: int,
        style_config: Dict[str, Any],
        family_constraints: Dict[str, Any],
        budget: Optional[float],
        preferences: Optional[Dict[str, Any]],
        weather_forecast: Optional[WeatherForecast] = None,
        start_date: Optional[date] = None,
        destination_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        weather_str = build_weather_context(
            self.weather_service, weather_forecast, start_date, duration_days
        )
        search_context = build_search_context(destination_info)
        return build_smart_prompt(
            destination=destination,
            duration_days=duration_days,
            style_config=style_config,
            family_constraints=family_constraints,
            budget=budget,
            preferences=preferences,
            weather_str=weather_str,
            search_context=search_context,
        )

    def _parse_smart_response(
        self, llm_response: str, duration_days: int
    ) -> Dict[str, Any]:
        return parse_smart_response(llm_response, duration_days)

    def _extract_balanced_json(self, text: str) -> str:
        return extract_balanced_json(text)

    def _get_default_structure(
        self, duration_days: int, destination: str = "目的地"
    ) -> Dict[str, Any]:
        return get_default_structure(duration_days, destination)

    async def generate_smart_itinerary(
        self,
        trip_id: UUID,
        destination: str,
        start_date: date,
        end_date: date,
        styles: List[ItineraryStyle],
        family_composition: Dict[str, Any],
        budget: Optional[float] = None,
        preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成智能行程规划

        Args:
            trip_id: 旅行计划ID
            destination: 目的地
            start_date: 开始日期
            end_date: 结束日期
            styles: 行程风格列表（最多3个）
            family_composition: 家庭成员组成
            budget: 总预算
            preferences: 其他偏好

        Returns:
            完整的行程规划，包含设计依据和专业建议
        """
        duration_days = (end_date - start_date).days + 1

        # 分析家庭约束（传入偏好设置）
        family_constraints = analyze_family_constraints(family_composition, preferences)

        # 合并风格配置
        style_config = merge_style_configs(styles)

        # 获取天气预报（如果启用）
        weather_forecast = None
        # Handle both dict and Pydantic model for preferences
        if preferences is None:
            weather_aware = True
        elif hasattr(preferences, 'weather_aware'):
            weather_aware = preferences.weather_aware
        else:
            weather_aware = preferences.get("weather_aware", True)
        if weather_aware:
            try:
                weather_forecast = await self.weather_service.get_forecast(
                    destination, start_date, end_date
                )
                logger.info(f"Retrieved weather forecast for {destination}")
            except Exception as e:
                logger.warning(f"Failed to get weather forecast: {e}")

        # 搜索目的地信息（真实网络搜索）
        logger.info(f"Searching destination info for {destination}")
        destination_info = await self._search_destination_info(
            destination, styles, family_constraints
        )

        # 构建天气和搜索上下文
        weather_str = build_weather_context(
            self.weather_service, weather_forecast, start_date, duration_days
        )
        search_context = build_search_context(destination_info)

        # 构建 LLM Prompt
        prompt = build_smart_prompt(
            destination=destination,
            duration_days=duration_days,
            style_config=style_config,
            family_constraints=family_constraints,
            budget=budget,
            preferences=preferences,
            weather_str=weather_str,
            search_context=search_context,
        )

        logger.info(
            f"Generating smart itinerary for {destination}, {duration_days} days, "
            f"styles: {[s.value for s in styles]}",
            extra={
                "trip_id": str(trip_id),
                "destination": destination,
                "duration_days": duration_days,
                "styles": [s.value for s in styles],
                "has_children": family_constraints.get("has_children", False),
                "has_elderly": family_constraints.get("has_elderly", False),
                "weather_aware": weather_aware,
                "has_weather_forecast": weather_forecast is not None,
            }
        )

        generation_start = time_module.time()
        llm_timeout = 600.0  # 10 minute timeout (Doubao model is slow)

        try:
            # 调用 LLM 生成行程，带超时保护 (wait_for for Python 3.9 compat)
            llm_response = await asyncio.wait_for(
                self.llm.generate_text(prompt, temperature=0.7, max_tokens=4000),
                timeout=llm_timeout,
            )

            llm_duration = time_module.time() - generation_start
            logger.info(
                f"LLM generation completed in {llm_duration:.2f}s",
                extra={
                    "trip_id": str(trip_id),
                    "llm_duration_seconds": llm_duration,
                    "response_length": len(llm_response),
                }
            )

            # 解析响应
            result = parse_smart_response(llm_response, duration_days)

            # 保存到数据库
            await self._save_itineraries(trip_id, start_date, result["daily_schedules"])

            # 添加元数据
            result["trip_id"] = str(trip_id)
            result["destination"] = destination
            result["duration_days"] = duration_days
            result["styles"] = [s.value for s in styles]
            result["generated_at"] = utc_now().isoformat()

            total_duration = time_module.time() - generation_start
            total_activities = sum(
                len(day.get("activities", []))
                for day in result.get("daily_schedules", [])
            )
            total_cost = result.get("budget_allocation", {}).get("total", 0)

            logger.info(
                f"Smart itinerary generated successfully for {destination}",
                extra={
                    "trip_id": str(trip_id),
                    "total_duration_seconds": total_duration,
                    "total_activities": total_activities,
                    "total_budget": total_cost,
                    "days_generated": len(result.get("daily_schedules", [])),
                    "success": True,
                }
            )

            return result

        except asyncio.TimeoutError:
            logger.error(
                f"LLM call timed out after {llm_timeout}s",
                extra={
                    "trip_id": str(trip_id),
                    "destination": destination,
                    "timeout_seconds": llm_timeout,
                    "success": False,
                }
            )
            raise RuntimeError(f"智能行程生成超时（{llm_timeout}秒），请稍后重试")

        except Exception as e:
            total_duration = time_module.time() - generation_start
            logger.error(
                f"Failed to generate smart itinerary: {e}",
                extra={
                    "trip_id": str(trip_id),
                    "destination": destination,
                    "error_type": type(e).__name__,
                    "duration_before_failure": total_duration,
                    "success": False,
                }
            )
            raise RuntimeError(f"智能行程生成失败: {str(e)}")

    async def _search_destination_info(
        self,
        destination: str,
        styles: List[ItineraryStyle],
        family_constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        搜索目的地相关信息

        Args:
            destination: 目的地
            styles: 行程风格
            family_constraints: 家庭约束

        Returns:
            {"attractions": [...], "restaurants": [...], "tips": [...], "sources": [...]}
        """
        if not self.web_search.is_available():
            logger.warning("Web search not available, skipping destination search")
            return {"attractions": [], "restaurants": [], "tips": [], "sources": []}

        style_keywords = map_styles_to_keywords(styles)

        search_start = time_module.time()

        try:
            attractions_task = self.web_search.search_attractions(
                destination,
                styles=style_keywords,
                family_has_children=family_constraints.get("has_children", False),
                family_has_elderly=family_constraints.get("has_elderly", False),
            )

            occasion = "家庭聚餐" if family_constraints.get("has_children") else None
            restaurants_task = self.web_search.search_restaurants(
                destination, occasion=occasion,
            )

            current_year = local_now().year
            tips_task = self.web_search.search(
                f"{destination} 旅游避坑 注意事项 {current_year}",
                num_results=5,
                include_domains=["mafengwo.cn", "xiaohongshu.com", "qyer.com"],
            )

            # 使用10秒超时保护 (wait_for for Python 3.9 compat)
            attractions, restaurants, tips_result = await asyncio.wait_for(
                asyncio.gather(
                    attractions_task, restaurants_task, tips_task,
                    return_exceptions=True,
                ),
                timeout=10.0,
            )

            search_duration = time_module.time() - search_start

            # 处理异常
            if isinstance(attractions, Exception):
                logger.warning(f"Attractions search failed: {attractions}")
                attractions = []
            if isinstance(restaurants, Exception):
                logger.warning(f"Restaurants search failed: {restaurants}")
                restaurants = []
            if isinstance(tips_result, Exception):
                logger.warning(f"Tips search failed: {tips_result}")
                tips_result = {"results": []}

            # 收集所有来源
            sources = _collect_sources(
                self.web_search, attractions, restaurants
            )

            logger.info(
                f"Destination search completed in {search_duration:.2f}s",
                extra={
                    "destination": destination,
                    "attractions_found": len(attractions) if isinstance(attractions, list) else 0,
                    "restaurants_found": len(restaurants) if isinstance(restaurants, list) else 0,
                    "sources_count": len(sources),
                }
            )

            return {
                "attractions": attractions[:10] if isinstance(attractions, list) else [],
                "restaurants": restaurants[:5] if isinstance(restaurants, list) else [],
                "tips": tips_result.get("results", [])[:5] if isinstance(tips_result, dict) else [],
                "sources": sources,
            }

        except asyncio.TimeoutError:
            logger.warning("Destination search timed out after 10s")
            return {"attractions": [], "restaurants": [], "tips": [], "sources": []}
        except Exception as e:
            logger.error(f"Destination search failed: {e}")
            return {"attractions": [], "restaurants": [], "tips": [], "sources": []}

    async def _save_itineraries(
        self,
        trip_id: UUID,
        start_date: date,
        daily_schedules: List[Dict[str, Any]]
    ) -> None:
        """保存行程到数据库"""
        logger.info(f"Saving {len(daily_schedules)} day itineraries for trip {trip_id}")

        # 先删除现有行程
        await self.db.execute(
            delete(TripItinerary).where(TripItinerary.trip_id == trip_id)
        )

        # 保存新行程
        saved_count = 0
        for schedule in daily_schedules:
            day_num = schedule.get("day", 1)
            activities = schedule.get("activities", [])
            logger.info(f"  Day {day_num}: {len(activities)} activities")

            theme = schedule.get("theme", "")
            summary = schedule.get("summary", "")
            packing_notes = {
                "theme": theme,
                "summary": summary,
                "day_summary": schedule.get("day_summary", {})
            } if theme or summary else None

            itinerary = TripItinerary(
                trip_id=trip_id,
                day_number=day_num,
                schedule=activities,
                packing_notes=packing_notes
            )
            self.db.add(itinerary)
            saved_count += 1

        await self.db.commit()
        logger.info(f"Successfully saved {saved_count} day itineraries for trip {trip_id}")

    async def adjust_itinerary(
        self,
        trip_id: UUID,
        adjustment_request: str,
        current_day: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        根据用户自然语言请求调整行程

        Args:
            trip_id: 旅行计划ID
            adjustment_request: 用户的调整请求，如"今天想轻松一点"
            current_day: 当前是第几天（如果在旅途中）

        Returns:
            调整后的行程建议
        """
        # 获取当前行程
        result = await self.db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .order_by(TripItinerary.day_number)
        )
        itineraries = result.scalars().all()

        if not itineraries:
            return {"error": "未找到行程数据"}

        # 构建调整 Prompt
        current_schedule = json.dumps(
            [{"day": it.day_number, "activities": it.schedule} for it in itineraries],
            ensure_ascii=False,
            indent=2
        )

        prompt = f"""你是一位灵活的旅行顾问。用户在旅途中提出了调整请求，请帮助调整行程。

当前行程:
{current_schedule}

用户请求: {adjustment_request}
当前是第{current_day or '?'}天

请根据用户请求，提供调整建议。输出JSON格式：
{{
  "understanding": "你对用户请求的理解",
  "suggestions": [
    {{
      "option": "方案名称",
      "description": "方案描述",
      "changes": ["变更1", "变更2"],
      "impact": "对后续行程的影响"
    }}
  ],
  "recommended": "推荐的方案名称",
  "reason": "推荐理由"
}}

请直接输出JSON。"""

        try:
            llm_response = await self.llm.generate_text(
                prompt, temperature=0.6, max_tokens=2000
            )

            # 解析响应 - 使用 raw_decode 来处理 JSON 后面的额外内容
            json_start = llm_response.find('{')
            if json_start != -1:
                import json as json_mod
                decoder = json_mod.JSONDecoder()
                try:
                    parsed, _ = decoder.raw_decode(llm_response, json_start)
                    return parsed
                except json.JSONDecodeError:
                    json_str = extract_balanced_json(llm_response[json_start:])
                    return json.loads(json_str)
            return json.loads(llm_response)

        except Exception as e:
            logger.error(f"Failed to adjust itinerary: {e}")
            raise RuntimeError(f"行程调整失败: {e}")


def _collect_sources(
    web_search: Any,
    attractions: Any,
    restaurants: Any,
) -> List[Dict[str, Any]]:
    """收集所有来源信息"""
    sources: List[Dict[str, Any]] = []
    source_id = 1

    if isinstance(attractions, list):
        for item in attractions[:10]:
            sources.append({
                "id": source_id,
                "type": "travel_guide",
                "title": item.get("title", ""),
                "platform": item.get("platform", ""),
                "url": item.get("url", ""),
                "summary": item.get("content", "")[:200] if item.get("content") else "",
            })
            source_id += 1

    if isinstance(restaurants, list):
        for item in restaurants[:5]:
            sources.append({
                "id": source_id,
                "type": "food_review",
                "title": item.get("title", ""),
                "platform": web_search._extract_platform(item.get("source", "")),
                "url": item.get("source", ""),
                "summary": item.get("snippet", "")[:200] if item.get("snippet") else "",
            })
            source_id += 1

    return sources
