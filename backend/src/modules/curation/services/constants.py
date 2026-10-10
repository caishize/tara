"""Shared constants for curation services."""

# Major Chinese cities used for location extraction and spatial conflict detection.
# Union of cities used across storage_service.py and conflict_detection.py.
MAJOR_CITIES = [
    "北京", "上海", "广州", "深圳", "成都", "杭州", "武汉", "西安",
    "南京", "重庆", "天津", "苏州", "长沙", "郑州", "青岛", "大连",
    "厦门", "昆明", "合肥", "福州", "济南", "沈阳", "哈尔滨",
    "珠海", "东莞", "佛山", "无锡", "宁波", "温州",
]
