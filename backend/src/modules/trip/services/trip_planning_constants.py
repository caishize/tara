"""
Travel Planning Constants - Enums and configuration for travel planning.
"""

from enum import Enum
from typing import Dict, Any, List


class BudgetLevel(str, Enum):
    """预算档次"""
    BUDGET = "budget"           # 经济型: <500/天/人
    MODERATE = "moderate"       # 中等: 500-1000/天/人
    COMFORT = "comfort"         # 舒适: 1000-2000/天/人
    LUXURY = "luxury"           # 豪华: >2000/天/人


class TripStyle(str, Enum):
    """旅行风格"""
    RELAXED = "relaxed"         # 轻松休闲
    INTENSIVE = "intensive"     # 深度打卡
    ADVENTURE = "adventure"     # 户外探险
    CULTURAL = "cultural"       # 文化历史
    FOOD = "food"               # 美食之旅
    PHOTOGRAPHY = "photography" # 摄影之旅
    FAMILY = "family"           # 亲子游
    ROMANTIC = "romantic"       # 浪漫之旅


# 年龄段特征配置
AGE_GROUP_CHARACTERISTICS: Dict[str, Dict[str, Any]] = {
    "infant": {  # 0-2岁
        "constraints": ["需要频繁休息", "需要午睡", "避免人多嘈杂", "需要婴儿设施"],
        "avoid": ["长途步行", "高海拔", "刺激项目", "人流密集区"],
        "prefer": ["亲子酒店", "有儿童设施的景区", "自然环境"],
        "max_activity_hours": 4,
        "max_walking_km": 2,
    },
    "toddler": {  # 3-6岁
        "constraints": ["需要午休", "注意力有限", "需要儿童餐"],
        "avoid": ["长时间排队", "成人化景点", "太过刺激的项目"],
        "prefer": ["动物园", "游乐园", "海滩", "亲子项目"],
        "max_activity_hours": 6,
        "max_walking_km": 4,
    },
    "child": {  # 7-12岁
        "constraints": ["需要趣味性", "可适当增加教育内容"],
        "avoid": ["纯成人景点", "太过深奥的博物馆"],
        "prefer": ["科技馆", "主题乐园", "自然探索", "互动体验"],
        "max_activity_hours": 8,
        "max_walking_km": 8,
    },
    "teen": {  # 13-17岁
        "constraints": ["需要一定自主空间", "喜欢拍照打卡"],
        "avoid": ["太过幼稚的项目"],
        "prefer": ["网红景点", "特色体验", "美食探店"],
        "max_activity_hours": 10,
        "max_walking_km": 12,
    },
    "young_adult": {  # 18-35岁
        "constraints": [],
        "avoid": [],
        "prefer": ["各类体验", "探索发现"],
        "max_activity_hours": 12,
        "max_walking_km": 15,
    },
    "middle_aged": {  # 36-55岁
        "constraints": ["注意体力分配"],
        "avoid": ["太过劳累的行程"],
        "prefer": ["舒适体验", "文化历史", "美食"],
        "max_activity_hours": 10,
        "max_walking_km": 12,
    },
    "senior": {  # 56-70岁
        "constraints": ["需要充足休息", "避免过度劳累", "注意饮食"],
        "avoid": ["剧烈运动", "高海拔", "长时间步行"],
        "prefer": ["自然风光", "温泉养生", "慢节奏游览"],
        "max_activity_hours": 7,
        "max_walking_km": 6,
    },
    "elderly": {  # 70岁以上
        "constraints": ["需要频繁休息", "注意天气变化", "随身携带药品"],
        "avoid": ["爬山", "暴晒", "拥挤场所", "长途跋涉"],
        "prefer": ["平地景区", "有电梯/缆车", "公园散步", "温泉"],
        "max_activity_hours": 5,
        "max_walking_km": 3,
    },
}


# TripStyle display maps used across the codebase
TRAVEL_STYLE_DESC_MAP = {
    TripStyle.RELAXED: "轻松休闲，不赶场，多休息",
    TripStyle.INTENSIVE: "深度打卡，景点全覆盖",
    TripStyle.ADVENTURE: "户外探险，刺激体验",
    TripStyle.CULTURAL: "文化历史，博物馆和古迹",
    TripStyle.FOOD: "美食之旅，当地特色",
    TripStyle.PHOTOGRAPHY: "摄影之旅，网红打卡",
    TripStyle.FAMILY: "亲子互动，寓教于乐",
    TripStyle.ROMANTIC: "浪漫之旅，情侣约会",
}

TRAVEL_STYLE_SHORT_MAP = {
    TripStyle.RELAXED: "轻松休闲",
    TripStyle.INTENSIVE: "深度打卡",
    TripStyle.ADVENTURE: "户外探险",
    TripStyle.CULTURAL: "文化历史",
    TripStyle.FOOD: "美食之旅",
    TripStyle.PHOTOGRAPHY: "摄影打卡",
    TripStyle.FAMILY: "亲子出游",
    TripStyle.ROMANTIC: "浪漫之旅",
}

TRAVEL_STYLE_PROMPT_MAP = {
    TripStyle.RELAXED: "轻松休闲，不赶场，多休息",
    TripStyle.INTENSIVE: "深度打卡，充分利用时间",
    TripStyle.ADVENTURE: "户外探险，自然体验",
    TripStyle.CULTURAL: "文化历史，深度了解",
    TripStyle.FOOD: "美食之旅，品尝当地特色",
    TripStyle.PHOTOGRAPHY: "摄影之旅，打卡美景",
    TripStyle.FAMILY: "亲子游，寓教于乐",
    TripStyle.ROMANTIC: "浪漫之旅，二人世界",
}
