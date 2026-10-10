"""
Itinerary style definitions, configurations, and family constraint analysis.

Extracted from smart_itinerary_planner.py for file size management.
"""
from typing import List, Dict, Optional, Any
from enum import Enum


class ItineraryStyle(str, Enum):
    """行程风格枚举"""
    INTENSIVE = "intensive"      # 紧凑型：景点密集，充分利用时间
    RELAXED = "relaxed"          # 轻松型：慢节奏，充足休息
    BUDGET = "budget"            # 经济型：控制花费，高性价比
    LUXURY = "luxury"            # 豪华型：高端体验，五星服务
    ADVENTURE = "adventure"      # 探险型：户外活动，自然风光
    CULTURAL = "cultural"        # 文化型：博物馆、历史遗迹


# 风格配置
STYLE_CONFIGS: Dict[ItineraryStyle, Dict[str, Any]] = {
    ItineraryStyle.INTENSIVE: {
        "name": "紧凑型",
        "daily_attractions": "4-6个",
        "pace": "快节奏",
        "wake_time": "07:30",
        "end_time": "21:00",
        "description": "充分利用每一天，适合时间有限但想看尽量多景点的游客",
        "constraints": ["早起晚归", "午餐时间压缩", "景点间快速转移"]
    },
    ItineraryStyle.RELAXED: {
        "name": "轻松型",
        "daily_attractions": "2-3个",
        "pace": "慢节奏",
        "wake_time": "09:00",
        "end_time": "19:00",
        "description": "悠闲度假风格，适合家庭、老人或纯粹想放松的游客",
        "constraints": ["充足休息时间", "午休2小时", "不赶场"]
    },
    ItineraryStyle.BUDGET: {
        "name": "经济型",
        "daily_attractions": "3-4个",
        "pace": "适中",
        "wake_time": "08:00",
        "end_time": "20:00",
        "description": "高性价比旅行，优先免费/低价景点，精打细算",
        "constraints": ["免费景点优先", "公共交通", "平价美食", "经济型住宿"]
    },
    ItineraryStyle.LUXURY: {
        "name": "豪华型",
        "daily_attractions": "2-4个",
        "pace": "从容",
        "wake_time": "09:00",
        "end_time": "22:00",
        "description": "尊享体验，五星酒店、精致餐饮、专属服务",
        "constraints": ["五星级酒店", "米其林/黑珍珠餐厅", "专车接送", "VIP通道"]
    },
    ItineraryStyle.ADVENTURE: {
        "name": "探险型",
        "daily_attractions": "2-3个",
        "pace": "灵活",
        "wake_time": "06:30",
        "end_time": "20:00",
        "description": "户外探索，自然风光，特色体验",
        "constraints": ["户外活动为主", "徒步/骑行", "自然景观", "当地特色体验"]
    },
    ItineraryStyle.CULTURAL: {
        "name": "文化型",
        "daily_attractions": "2-3个",
        "pace": "深度",
        "wake_time": "09:00",
        "end_time": "19:00",
        "description": "深度文化体验，博物馆、历史遗迹、当地民俗",
        "constraints": ["博物馆/历史遗迹为主", "预留充足参观时间", "聘请导游讲解", "文化体验活动"]
    }
}


def analyze_family_constraints(
    family_composition: Dict[str, Any],
    preferences: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    分析家庭成员约束

    Args:
        family_composition: 家庭成员组成
        preferences: 偏好设置 (dict or Pydantic model)

    Returns:
        约束条件字典
    """
    # 从偏好中获取午休设置，支持Pydantic模型和dict两种格式
    if preferences is None:
        prefs: Dict[str, Any] = {}
    elif hasattr(preferences, 'model_dump'):
        # Pydantic v2 model
        prefs = preferences.model_dump()
    elif hasattr(preferences, 'dict'):
        # Pydantic v1 model
        prefs = preferences.dict()
    else:
        prefs = preferences

    enable_nap_time = prefs.get("enable_nap_time", True)
    nap_time_start = prefs.get("nap_time_start", "14:00")
    nap_time_end = prefs.get("nap_time_end", "16:00")

    constraints: Dict[str, Any] = {
        "has_children": False,
        "has_toddlers": False,  # 0-3岁
        "has_young_children": False,  # 4-6岁
        "has_elderly": False,
        "needs_nap_time": False,
        "nap_time_enabled": enable_nap_time,
        "nap_time_start": nap_time_start,
        "nap_time_end": nap_time_end,
        "max_walking_km": 15,  # 默认每日最大步行距离
        "activity_hours": 10,  # 默认每日活动时长
        "special_needs": [],
        "dietary_restrictions": []
    }

    children = family_composition.get("children", [])
    elderly = family_composition.get("elderly", [])
    special_needs = family_composition.get("special_needs", [])

    if children:
        constraints["has_children"] = True
        for child in children:
            age = child.get("age", 10)
            if age <= 3:
                constraints["has_toddlers"] = True
                constraints["needs_nap_time"] = True
                constraints["max_walking_km"] = 5
                constraints["activity_hours"] = 6
            elif age <= 6:
                constraints["has_young_children"] = True
                constraints["needs_nap_time"] = True
                constraints["max_walking_km"] = 8
                constraints["activity_hours"] = 7

    if elderly:
        constraints["has_elderly"] = True
        for elder in elderly:
            age = elder.get("age", 65)
            if age >= 70:
                constraints["max_walking_km"] = min(constraints["max_walking_km"], 6)
                constraints["activity_hours"] = min(constraints["activity_hours"], 6)
            else:
                constraints["max_walking_km"] = min(constraints["max_walking_km"], 8)
                constraints["activity_hours"] = min(constraints["activity_hours"], 7)

    constraints["special_needs"] = special_needs

    return constraints


def merge_style_configs(styles: List[ItineraryStyle]) -> Dict[str, Any]:
    """合并多个风格的配置"""
    if not styles:
        styles = [ItineraryStyle.RELAXED]

    merged: Dict[str, Any] = {
        "primary_style": styles[0].value,
        "style_names": [STYLE_CONFIGS[s]["name"] for s in styles],
        "description": " + ".join([STYLE_CONFIGS[s]["name"] for s in styles]),
        "constraints": []
    }

    # 合并所有风格的约束
    for style in styles:
        config = STYLE_CONFIGS[style]
        merged["constraints"].extend(config["constraints"])

    # 去重
    merged["constraints"] = list(set(merged["constraints"]))

    # 使用最宽松的时间配置
    wake_times = [STYLE_CONFIGS[s]["wake_time"] for s in styles]
    end_times = [STYLE_CONFIGS[s]["end_time"] for s in styles]
    merged["wake_time"] = max(wake_times)  # 最晚起床
    merged["end_time"] = min(end_times)    # 最早结束

    return merged


def map_styles_to_keywords(styles: List[ItineraryStyle]) -> List[str]:
    """转换风格为搜索关键词"""
    keyword_map = {
        ItineraryStyle.CULTURAL: "文化历史",
        ItineraryStyle.ADVENTURE: "户外探险",
        ItineraryStyle.LUXURY: "高端奢华",
        ItineraryStyle.BUDGET: "省钱攻略",
        ItineraryStyle.RELAXED: "休闲度假",
        ItineraryStyle.INTENSIVE: "热门景点",
    }
    return [keyword_map[s] for s in styles if s in keyword_map]
