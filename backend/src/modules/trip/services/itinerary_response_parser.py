"""
Itinerary response parser - parses LLM responses and provides default structures.

Extracted from smart_itinerary_planner.py for file size management.
"""
import json
import re
from typing import Dict, Any, List

from ....config.logging import get_logger

logger = get_logger(__name__)


def parse_smart_response(llm_response: str, duration_days: int) -> Dict[str, Any]:
    """解析 LLM 响应"""
    try:
        # 尝试提取 JSON - 使用 raw_decode 来处理 JSON 后面的额外内容
        # 首先找到第一个 { 的位置
        json_start = llm_response.find('{')
        if json_start == -1:
            raise ValueError("AI响应中未找到JSON数据")

        # 使用 raw_decode 解析 JSON，它会在解析完成后停止，忽略后续内容
        decoder = json.JSONDecoder()
        try:
            result, end_idx = decoder.raw_decode(llm_response, json_start)
            logger.info(
                f"Successfully parsed JSON from position {json_start} to {json_start + end_idx}"
            )
        except json.JSONDecodeError as e:
            # 如果 raw_decode 失败，尝试用正则提取并清理
            logger.warning(f"raw_decode failed: {e}, trying regex extraction")
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                json_str = json_match.group(0)
                # 尝试找到平衡的括号
                json_str = extract_balanced_json(json_str)
                result = json.loads(json_str)
            else:
                raise

        # Validate that we have daily_schedules
        if result.get("daily_schedules") and len(result["daily_schedules"]) > 0:
            return result
        else:
            logger.error("LLM response missing daily_schedules")
            raise ValueError("AI生成的行程格式不完整，缺少每日行程安排")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Response preview: {llm_response[:500]}...")
        raise ValueError(f"AI生成的行程无法解析: {str(e)}")


def extract_balanced_json(text: str) -> str:
    """提取平衡括号的 JSON 字符串"""
    if not text.startswith('{'):
        start = text.find('{')
        if start == -1:
            return text
        text = text[start:]

    depth = 0
    in_string = False
    escape = False

    for i, char in enumerate(text):
        if escape:
            escape = False
            continue
        if char == '\\' and in_string:
            escape = True
            continue
        if char == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[:i+1]

    return text


def get_default_structure(
    duration_days: int,
    destination: str = "目的地",
) -> Dict[str, Any]:
    """获取默认的响应结构，带完整的每日行程"""
    daily_schedules: List[Dict[str, Any]] = []
    for i in range(duration_days):
        daily_schedules.append(_build_default_day(i, destination))

    return {
        "trip_design_rationale": {
            "planning_philosophy": "根据您的需求，我们安排了轻松舒适的行程",
            "route_logic": "景点按地理位置分区安排，减少往返交通",
            "highlights": ["核心景点体验", "当地美食品尝"],
            "backup_plans": [
                {"scenario": "下雨天", "alternative": "可改去室内景点或商场"}
            ],
            "local_tips": ["建议提前购买景点门票", "当地公共交通便捷"]
        },
        "budget_allocation": {
            "transportation": {"amount": 500, "percentage": 20},
            "accommodation": {"amount": 900, "percentage": 35},
            "food": {"amount": 600, "percentage": 25},
            "tickets": {"amount": 400, "percentage": 15},
            "other": {"amount": 100, "percentage": 5},
            "total": 2500
        },
        "daily_schedules": daily_schedules
    }


def _build_default_day(day_index: int, destination: str) -> Dict[str, Any]:
    """构建单日默认行程"""
    day_num = day_index + 1
    source_ref = {
        "id": 1,
        "type": "guide",
        "title": f"{destination}旅游攻略",
        "author": "旅行家小助手",
        "platform": "携程旅行",
        "url": "https://www.ctrip.com",
        "summary": f"{destination}热门景点和美食推荐"
    }

    return {
        "day": day_num,
        "date_label": f"第{day_num}天",
        "theme": "探索之旅" if day_index == 0 else "深度体验",
        "summary": f"第{day_num}天的精彩行程安排",
        "sources": [source_ref],
        "activities": [
            _default_activity(
                "09:00", 120, "attraction", "上午景点游览",
                f"{destination}景区", "游览当地著名景点", 50,
                [{"category": "ticket", "item_name": "景区门票",
                  "unit_price": 50, "quantity": 1, "subtotal": 50,
                  "notes": "成人票价", "booking_link": "https://www.ctrip.com"}],
                "这是当地最具代表性的景点之一",
                "建议上午前往，人少且光线好",
                "建议停留2小时左右",
                "提前在线购票可享优惠",
                ["节假日人多，建议错峰"],
            ),
            _default_activity(
                "12:00", 90, "meal", "午餐",
                "当地特色餐厅", "品尝当地特色美食", 80,
                [{"category": "meal", "item_name": "午餐（人均）",
                  "unit_price": 80, "quantity": 1, "subtotal": 80,
                  "notes": "当地特色菜"}],
                "当地人推荐的美食聚集地",
                "推荐尝试当地招牌菜",
                "11:30到达可避开高峰",
                "人均80元左右",
                [],
            ),
            _default_activity(
                "14:00", 120, "other", "休息/自由活动",
                "酒店或咖啡馆", "午后休息，储备精力", 0,
                [],
                "适当休息保持良好状态",
                "可以休息或逛逛附近",
                "休息1-2小时即可",
                "在酒店休息不额外花费",
                [],
            ),
            _default_activity(
                "16:00", 120, "attraction", "下午景点",
                f"{destination}", "下午继续游览", 40,
                [{"category": "ticket", "item_name": "景区门票",
                  "unit_price": 40, "quantity": 1, "subtotal": 40}],
                "下午时段适合这个景点",
                "傍晚时分景色最美",
                "建议待到日落",
                "下午票价可能有优惠",
                [],
            ),
            _default_activity(
                "18:30", 90, "meal", "晚餐",
                f"{destination}餐厅", "享用当地美食", 100,
                [{"category": "meal", "item_name": "晚餐（人均）",
                  "unit_price": 100, "quantity": 1, "subtotal": 100}],
                "精选当地好评餐厅",
                "尝试当地特色菜品",
                "18:30是用餐黄金时间",
                "人均100元档位选择多",
                ["热门餐厅可能需要排队"],
            ),
        ],
        "day_summary": {
            "total_cost": 270,
            "walking_distance_km": 6,
            "activity_count": 5,
            "energy_level": "适中",
            "cost_by_category": {
                "transportation": 0,
                "accommodation": 0,
                "tickets": 90,
                "meals": 180,
                "other": 0
            }
        }
    }


def _default_activity(
    time: str,
    duration_minutes: int,
    activity_type: str,
    title: str,
    location: str,
    description: str,
    estimated_cost: int,
    cost_breakdown: List[Dict[str, Any]],
    why_chosen: str,
    best_experience: str,
    time_tips: str,
    cost_tips: str,
    warnings: List[str],
) -> Dict[str, Any]:
    """构建单个默认活动"""
    source_refs = [1] if activity_type != "other" else []
    return {
        "time": time,
        "duration_minutes": duration_minutes,
        "activity_type": activity_type,
        "title": title,
        "location": location,
        "description": description,
        "estimated_cost": estimated_cost,
        "cost_breakdown": cost_breakdown,
        "source_refs": source_refs,
        "professional_advice": {
            "why_chosen": why_chosen,
            "best_experience": best_experience,
            "time_tips": time_tips,
            "cost_tips": cost_tips,
            "warnings": warnings,
        },
        "alternatives": []
    }
