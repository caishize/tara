"""
Travel Planning Search Mixin - Web search and LLM sub-queries for travel info.

Handles searching for restaurants, hotels, attractions, transport tips,
and enhancing LLM results with real web search data.
"""

from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import date
import json
import re
import asyncio

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now

logger = get_logger(__name__)


class TripSearchMixin:
    """Mixin for web search and LLM sub-query methods."""

    async def _search_restaurant_recommendations(
        self,
        destination: str,
        user_requirements: Optional[str],
    ) -> List[Dict[str, Any]]:
        """使用真实网络搜索获取餐厅推荐

        像做功课的人一样搜索大众点评、小红书等平台的真实评价

        Args:
            destination: 目的地
            user_requirements: 用户需求描述

        Returns:
            餐厅推荐列表，包含真实评价
        """
        if not self.web_search.is_available():
            logger.info("Web search not available, will use LLM-only recommendations")
            return []

        try:
            # 构建搜索查询 - 像真正做攻略的人一样
            search_queries = [
                f"{destination} 美食攻略 必吃餐厅 推荐 小红书",
                f"{destination} 大众点评 高分餐厅 人均",
                f"{destination} 特色美食 本地人推荐",
            ]

            if user_requirements:
                # 从用户需求中提取关键信息
                if "老人" in user_requirements or "长辈" in user_requirements:
                    search_queries.append(f"{destination} 适合老人 餐厅 清淡")
                if "小孩" in user_requirements or "孩子" in user_requirements:
                    search_queries.append(f"{destination} 亲子餐厅 儿童友好")
                if "海鲜" in user_requirements:
                    search_queries.append(f"{destination} 海鲜餐厅 推荐 新鲜")

            all_results = []
            search_tasks = [
                self.web_search.search(
                    query,
                    num_results=3,
                    include_domains=["dianping.com", "xiaohongshu.com", "mafengwo.cn"],
                )
                for query in search_queries[:3]  # 限制并发请求数
            ]

            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Search failed: {result}")
                    continue
                if "error" not in result:
                    all_results.extend(result.get("results", []))

            logger.info(f"Web search found {len(all_results)} results for {destination}")
            return all_results

        except Exception as e:
            logger.warning(f"Restaurant search failed: {e}")
            return []

    async def _enhance_food_with_search(
        self,
        destination: str,
        user_requirements: Optional[str],
        llm_food_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """使用网络搜索结果增强餐厅推荐

        将真实搜索结果与LLM生成的结果结合，确保推荐准确可靠
        """
        # 首先执行网络搜索
        search_results = await self._search_restaurant_recommendations(
            destination, user_requirements
        )

        if not search_results:
            return llm_food_results

        # 将搜索结果整理成上下文，让LLM生成更准确的推荐
        search_context = "\n".join([
            f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
            for r in search_results[:10]
        ])

        enhance_prompt = f"""基于以下真实的网络搜索结果，提取出{destination}最值得推荐的具体餐厅信息。

搜索结果（来自大众点评、小红书等平台）：
{search_context}

请从搜索结果中提取真实存在的餐厅，以 JSON 数组格式输出：
[
  {{
    "name": "从搜索结果中提取的真实餐厅名",
    "category": "菜系类型",
    "location": "地址（如果有）",
    "price_range": "人均价格（如果有）",
    "signature_dish": "招牌菜（如果有）",
    "rating": "评分（如果有）",
    "review_highlight": "网友真实评价摘录",
    "tips": "用餐建议",
    "suitable_for": "适合人群",
    "source": "信息来源（如：小红书/大众点评）"
  }}
]

注意：
1. 只提取搜索结果中明确提到的餐厅名
2. 如果搜索结果中没有明确信息，用"待确认"标注
3. 优先选择评价好、具体地址清晰的餐厅
4. 最多返回5家餐厅"""

        try:
            enhanced_response = await asyncio.wait_for(
                self.llm.generate_text(enhance_prompt, temperature=0.3, max_tokens=1500),
                timeout=30.0
            )

            json_match = re.search(r'\[[\s\S]*\]', enhanced_response)
            if json_match:
                enhanced_food = json.loads(json_match.group(0))
                logger.info(f"Enhanced {len(enhanced_food)} restaurants with web search data")
                return enhanced_food

        except Exception as e:
            logger.warning(f"Failed to enhance food recommendations: {e}")

        return llm_food_results

    async def _search_hotel_recommendations(
        self,
        destination: str,
        user_requirements: Optional[str],
    ) -> List[Dict[str, Any]]:
        """使用真实网络搜索获取酒店推荐

        像做功课的人一样搜索携程、Booking、小红书等平台的真实评价
        """
        if not self.web_search.is_available():
            logger.info("Web search not available, will use LLM-only hotel recommendations")
            return []

        try:
            search_queries = [
                f"{destination} 酒店推荐 携程 评价",
                f"{destination} 住宿攻略 小红书 推荐",
                f"{destination} 酒店性价比 高分 推荐",
            ]

            if user_requirements:
                if "老人" in user_requirements or "长辈" in user_requirements:
                    search_queries.append(f"{destination} 酒店 无障碍设施 老人友好")
                if "小孩" in user_requirements or "孩子" in user_requirements or "亲子" in user_requirements:
                    search_queries.append(f"{destination} 亲子酒店 儿童友好 家庭房")
                if "商务" in user_requirements:
                    search_queries.append(f"{destination} 商务酒店 推荐")
                if "度假" in user_requirements:
                    search_queries.append(f"{destination} 度假酒店 推荐")

            all_results = []
            search_tasks = [
                self.web_search.search(
                    query,
                    num_results=3,
                    include_domains=["ctrip.com", "booking.com", "mafengwo.cn", "xiaohongshu.com"],
                )
                for query in search_queries[:3]
            ]

            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Hotel search failed: {result}")
                    continue
                if "error" not in result:
                    all_results.extend(result.get("results", []))

            logger.info(f"Web search found {len(all_results)} hotel results for {destination}")
            return all_results

        except Exception as e:
            logger.warning(f"Hotel search failed: {e}")
            return []

    async def _enhance_hotels_with_search(
        self,
        destination: str,
        user_requirements: Optional[str],
        llm_hotel_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """使用网络搜索结果增强酒店推荐

        将真实搜索结果与LLM生成的结果结合，确保推荐准确可靠
        """
        search_results = await self._search_hotel_recommendations(
            destination, user_requirements
        )

        if not search_results:
            return llm_hotel_results

        search_context = "\n".join([
            f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
            for r in search_results[:10]
        ])

        requirements_desc = user_requirements if user_requirements else "家庭出游"

        enhance_prompt = f"""基于以下真实的网络搜索结果，提取出{destination}最值得推荐的具体酒店信息。

搜索结果（来自携程、Booking、小红书等平台）：
{search_context}

用户需求：{requirements_desc}

请从搜索结果中提取真实存在的酒店，以 JSON 数组格式输出：
[
  {{
    "name": "从搜索结果中提取的真实酒店名",
    "location": "位置/地段",
    "star": "星级",
    "price_range": "每晚价格区间",
    "room_types": ["可用房型"],
    "suitable_for": "适合人群",
    "highlights": "亮点特色",
    "facilities": ["主要设施"],
    "rating": "评分（如果有）",
    "review_highlight": "网友真实评价摘录",
    "tips": "预订建议",
    "source": "信息来源（如：携程/小红书/Booking）"
  }}
]

注意：
1. 只提取搜索结果中明确提到的酒店名
2. 如果搜索结果中没有明确信息，用"待确认"标注
3. 优先选择评价好、位置便利的酒店
4. 最多返回5家酒店"""

        try:
            enhanced_response = await asyncio.wait_for(
                self.llm.generate_text(enhance_prompt, temperature=0.3, max_tokens=1500),
                timeout=30.0
            )

            json_match = re.search(r'\[[\s\S]*\]', enhanced_response)
            if json_match:
                enhanced_hotels = json.loads(json_match.group(0))
                logger.info(f"Enhanced {len(enhanced_hotels)} hotels with web search data")
                return enhanced_hotels

        except Exception as e:
            logger.warning(f"Failed to enhance hotel recommendations: {e}")

        return llm_hotel_results

    async def _fetch_real_time_info_with_progress(
        self,
        destination: str,
        start_date: date,
        end_date: date,
        user_requirements: Optional[str],
    ) -> AsyncIterator[Dict[str, Any]]:
        """获取实时信息，以 async generator 形式 yield 进度事件和最终结果。

        Yields:
            {"type": "progress", "stage": ..., "message": ...} -- sub-step progress
            {"type": "result", "data": ...} -- final result (last event)
        """
        insights: List[str] = []
        search_results: Dict[str, Any] = {}

        # --- Step 3a: 分析住宿需求 ---
        yield {
            "type": "progress",
            "stage": "hotel_needs",
            "message": "🏨 正在分析住宿需求...",
        }

        nights = (end_date - start_date).days
        needs_hotel = await self._understand_hotel_needs(
            user_requirements=user_requirements,
            nights=nights,
            destination=destination,
        )

        hotel_status = "需要住宿" if needs_hotel else "当天往返，无需住宿"
        yield {
            "type": "progress",
            "stage": "hotel_needs_done",
            "message": f"✅ 住宿需求分析完成 — {hotel_status}",
        }

        # --- Step 3b-3e: 分步查询实时信息 ---
        requirements_desc = user_requirements if user_requirements else "家庭出游"
        llm_succeeded = False

        try:
            # --- 3b: 景点查询 ---
            yield {
                "type": "progress",
                "stage": "attractions_search",
                "message": f"🏛️ 正在查询{destination}热门景点...",
            }
            attractions_data = await self._query_attractions(destination)
            if attractions_data:
                search_results["attractions"] = attractions_data
                llm_succeeded = True
                names = [a.get("name", "") for a in attractions_data[:5] if a.get("name")]
                yield {
                    "type": "progress",
                    "stage": "attractions_done",
                    "message": f"✅ 发现 {len(attractions_data)} 个景点：{', '.join(names)}",
                }
            else:
                yield {
                    "type": "progress",
                    "stage": "attractions_done",
                    "message": "⚠️ 景点查询未返回结果",
                }

            # --- 3c: 美食查询 ---
            yield {
                "type": "progress",
                "stage": "food_search",
                "message": f"🍜 正在查询{destination}特色美食和餐厅...",
            }
            food_data = await self._query_food(destination, requirements_desc)
            if food_data:
                search_results["food"] = food_data
                llm_succeeded = True
                names = [f.get("name", "") for f in food_data[:5] if f.get("name")]
                yield {
                    "type": "progress",
                    "stage": "food_done",
                    "message": f"✅ 发现 {len(food_data)} 家餐厅：{', '.join(names)}",
                }
            else:
                yield {
                    "type": "progress",
                    "stage": "food_done",
                    "message": "⚠️ 餐厅查询未返回结果",
                }

            # --- 3d: 酒店查询（仅在需要住宿时） ---
            if needs_hotel:
                yield {
                    "type": "progress",
                    "stage": "hotel_search",
                    "message": f"🏨 正在查询{destination}住宿推荐...",
                }
                hotel_data = await self._query_hotels(destination, nights, requirements_desc)
                if hotel_data:
                    search_results["hotels"] = hotel_data
                    llm_succeeded = True
                    names = [h.get("name", "") for h in hotel_data[:3] if h.get("name")]
                    yield {
                        "type": "progress",
                        "stage": "hotel_done",
                        "message": f"✅ 发现 {len(hotel_data)} 家酒店：{', '.join(names)}",
                    }

            # --- 3e: 交通 + 避坑 + 省钱 ---
            yield {
                "type": "progress",
                "stage": "tips_search",
                "message": f"📝 正在查询{destination}交通和避坑指南...",
            }
            tips_data = await self._query_transport_and_tips(destination)
            if tips_data:
                for key in ("transport", "pitfalls", "money_saving_tips", "best_season", "weather_now"):
                    if tips_data.get(key):
                        search_results[key] = tips_data[key]
                llm_succeeded = True
                pitfalls = tips_data.get("pitfalls", [])
                tip_preview = pitfalls[0][:30] if pitfalls else "无"
                yield {
                    "type": "progress",
                    "stage": "tips_done",
                    "message": f"✅ 交通和避坑指南已获取 — {tip_preview}",
                }

            if llm_succeeded:
                insights.append(f"已获取{destination}的最新旅游信息")
                logger.info(f"Successfully fetched real-time info for {destination}")

            # --- Web search enhancement (food) ---
            if self.web_search.is_available() and search_results.get("food"):
                yield {
                    "type": "progress",
                    "stage": "food_enhancement",
                    "message": "🍜 正在从大众点评/小红书增强餐厅数据...",
                }
                try:
                    enhanced_food = await self._enhance_food_with_search(
                        destination=destination,
                        user_requirements=user_requirements,
                        llm_food_results=search_results.get("food", []),
                    )
                    if enhanced_food:
                        search_results = {**search_results, "food": enhanced_food}
                        insights.append("已从大众点评/小红书获取真实餐厅评价")
                        names = [f.get("name", "") for f in enhanced_food[:3] if f.get("name")]
                        yield {
                            "type": "progress",
                            "stage": "food_enhancement_done",
                            "message": f"✅ 餐厅数据增强完成：{', '.join(names)}",
                        }
                except Exception as e:
                    logger.warning(f"Food enhancement failed: {e}")

            # --- Web search enhancement (hotels) ---
            if self.web_search.is_available() and search_results.get("hotels") and needs_hotel:
                yield {
                    "type": "progress",
                    "stage": "hotel_enhancement",
                    "message": "🏨 正在从携程增强酒店数据...",
                }
                try:
                    enhanced_hotels = await self._enhance_hotels_with_search(
                        destination=destination,
                        user_requirements=user_requirements,
                        llm_hotel_results=search_results.get("hotels", []),
                    )
                    if enhanced_hotels:
                        search_results = {**search_results, "hotels": enhanced_hotels}
                        insights.append("已从携程/小红书获取真实酒店评价")
                        yield {
                            "type": "progress",
                            "stage": "hotel_enhancement_done",
                            "message": "✅ 酒店数据增强完成",
                        }
                except Exception as e:
                    logger.warning(f"Hotel enhancement failed: {e}")

            # Report failure if all LLM sub-queries failed
            if not llm_succeeded:
                yield {
                    "type": "progress",
                    "stage": "error",
                    "message": f"抱歉，暂时无法获取{destination}的实时旅游信息，请稍后重试",
                }
                logger.error(f"All LLM sub-queries failed for {destination}")
                insights.append("实时信息获取失败")

        except Exception as e:
            logger.warning(f"Failed to fetch real-time info: {e}")
            insights.append("暂无法获取实时信息")

        # --- Emit summary progress ---
        search_detail_parts = []
        attractions = search_results.get("attractions", [])
        foods = search_results.get("food", [])
        pitfalls_list = search_results.get("pitfalls", [])

        if isinstance(attractions, list) and attractions:
            names = [a.get("name", "") for a in attractions[:3] if a.get("name")]
            if names:
                search_detail_parts.append(f"热门景点: {', '.join(names)}")
        if isinstance(foods, list) and foods:
            names = [f.get("name", "") for f in foods[:3] if f.get("name")]
            if names:
                search_detail_parts.append(f"特色美食: {', '.join(names)}")
        if isinstance(pitfalls_list, list) and pitfalls_list:
            tip = pitfalls_list[0]
            search_detail_parts.append(
                f"避坑提醒: {tip[:20]}..." if len(tip) > 20 else f"避坑提醒: {tip}"
            )

        detail_str = "；".join(search_detail_parts) if search_detail_parts else "暂无详细信息"
        yield {
            "type": "progress",
            "stage": "realtime_info_done",
            "message": f"✅ {destination}信息获取完成 - {detail_str}",
        }

        # --- Final result ---
        yield {
            "type": "result",
            "data": {
                "search_results": search_results,
                "insights": insights,
                "fetched_at": utc_now().isoformat(),
                "needs_hotel": needs_hotel,
                "nights": nights,
            },
        }

    # ------------------------------------------------------------------
    # Sub-query helpers -- each does one focused LLM call with small
    # max_tokens so it returns fast. Used by _fetch_real_time_info_with_progress.
    # ------------------------------------------------------------------

    async def _query_attractions(self, destination: str) -> List[Dict[str, Any]]:
        """查询景点信息（focused sub-query）"""
        prompt = f"""请推荐{destination}最值得去的5-8个景点，包含门票和游玩建议。
只返回 JSON 数组，不要其他文字：
[{{"name": "景点名", "ticket_price": "价格", "best_time": "最佳时间", "tips": "建议", "highlights": "亮点"}}]"""
        try:
            response = await asyncio.wait_for(
                self.llm.generate_text(prompt, temperature=0.4, max_tokens=800),
                timeout=60.0,
            )
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            logger.warning(f"Attractions query failed: {e}")
        return []

    async def _query_food(self, destination: str, requirements_desc: str) -> List[Dict[str, Any]]:
        """查询美食信息（focused sub-query）"""
        prompt = f"""请推荐{destination}最具特色的5-8家餐厅/美食，要求具体店名和地址。
用户需求：{requirements_desc}
只返回 JSON 数组，不要其他文字：
[{{"name": "真实店名", "category": "菜系", "location": "地址", "price_range": "人均", "signature_dish": "招牌菜", "tips": "建议", "suitable_for": "适合人群"}}]"""
        try:
            response = await asyncio.wait_for(
                self.llm.generate_text(prompt, temperature=0.4, max_tokens=800),
                timeout=60.0,
            )
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            logger.warning(f"Food query failed: {e}")
        return []

    async def _query_hotels(
        self, destination: str, nights: int, requirements_desc: str
    ) -> List[Dict[str, Any]]:
        """查询酒店信息（focused sub-query）"""
        prompt = f"""请推荐{destination}适合{requirements_desc}的3-5家酒店，住{nights}晚。
要求具体酒店名和位置。
只返回 JSON 数组，不要其他文字：
[{{"name": "酒店名", "location": "位置", "star": "星级", "price_range": "每晚价格", "suitable_for": "适合人群", "highlights": "亮点"}}]"""
        try:
            response = await asyncio.wait_for(
                self.llm.generate_text(prompt, temperature=0.4, max_tokens=600),
                timeout=60.0,
            )
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            logger.warning(f"Hotel query failed: {e}")
        return []

    async def _query_transport_and_tips(self, destination: str) -> Dict[str, Any]:
        """查询交通和避坑指南（focused sub-query）"""
        prompt = f"""请提供{destination}的交通指南、避坑建议和省钱技巧。
只返回 JSON 对象，不要其他文字：
{{"transport": "交通方式建议", "pitfalls": ["避坑1", "避坑2", "避坑3"], "money_saving_tips": ["省钱1", "省钱2"], "best_season": "最佳旅游季节", "weather_now": "当前天气概况"}}"""
        try:
            response = await asyncio.wait_for(
                self.llm.generate_text(prompt, temperature=0.4, max_tokens=600),
                timeout=60.0,
            )
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            logger.warning(f"Transport/tips query failed: {e}")
        return {}
