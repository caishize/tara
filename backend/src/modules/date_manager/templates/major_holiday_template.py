"""
Major Holiday Template - Template for major holidays like Spring Festival.

Major holidays (春节, 国庆节, 中秋节) warrant 30-day advance preparation.
"""

from datetime import date
from typing import List, Dict

from .base import HolidayPreparationTemplate, SubtaskDefinition


# Detailed preparation tasks for major holidays
MAJOR_HOLIDAY_TASKS: Dict[str, List[Dict]] = {
    "春节": [
        {"title": "预订返乡机票/火车票", "priority": "urgent", "days_before": 30},
        {"title": "准备年货采购清单", "priority": "high", "days_before": 20},
        {"title": "规划红包预算", "priority": "normal", "days_before": 14},
        {"title": "预约家政大扫除", "priority": "normal", "days_before": 14},
        {"title": "准备年夜饭菜单", "priority": "normal", "days_before": 7},
        {"title": "购买春联、装饰品", "priority": "normal", "days_before": 7},
        {"title": "准备压岁钱红包", "priority": "high", "days_before": 3},
        {"title": "备好年货零食", "priority": "normal", "days_before": 3},
    ],
    "国庆节": [
        {"title": "规划出行目的地", "priority": "high", "days_before": 30},
        {"title": "预订机票/火车票", "priority": "urgent", "days_before": 25},
        {"title": "预订酒店/民宿", "priority": "high", "days_before": 20},
        {"title": "制定详细行程", "priority": "normal", "days_before": 14},
        {"title": "准备出行物品清单", "priority": "normal", "days_before": 7},
        {"title": "检查证件有效期", "priority": "high", "days_before": 7},
        {"title": "了解目的地天气", "priority": "low", "days_before": 3},
    ],
    "中秋节": [
        {"title": "预订/选购月饼", "priority": "high", "days_before": 20},
        {"title": "准备送礼名单", "priority": "normal", "days_before": 14},
        {"title": "安排家庭团聚", "priority": "high", "days_before": 14},
        {"title": "采购水果、茶叶等节礼", "priority": "normal", "days_before": 7},
        {"title": "准备赏月活动", "priority": "low", "days_before": 3},
    ],
}

# Default tasks for major holidays without specific configuration
DEFAULT_MAJOR_TASKS = [
    {"title": "制定节日计划", "priority": "high", "days_before": 14},
    {"title": "准备节日用品", "priority": "normal", "days_before": 7},
    {"title": "安排家庭活动", "priority": "normal", "days_before": 7},
]


class MajorHolidayTemplate(HolidayPreparationTemplate):
    """
    Template for major holidays requiring extensive preparation.

    Major holidays include 春节, 国庆节, 中秋节.
    These holidays warrant 30-day advance notice and detailed preparation tasks.
    """

    @property
    def category_name(self) -> str:
        return "major"

    @property
    def default_trigger_days_before(self) -> int:
        return 30

    def get_subtasks(
        self,
        holiday_name: str,
        occurrence_date: date,
        days_until: int
    ) -> List[SubtaskDefinition]:
        """Generate detailed subtasks for major holidays."""
        # Get holiday-specific tasks or use defaults
        tasks_config = MAJOR_HOLIDAY_TASKS.get(holiday_name, DEFAULT_MAJOR_TASKS)

        subtasks = []
        for task in tasks_config:
            # Only include tasks that are still relevant given days_until
            if task.get("days_before", 30) <= days_until:
                subtasks.append(SubtaskDefinition(
                    title=task["title"],
                    priority=task.get("priority", "normal"),
                    days_before_due=task.get("days_before"),
                ))

        return subtasks

    def get_priority(self, days_until: int) -> str:
        """Major holidays always have at least 'high' priority."""
        if days_until <= 7:
            return "urgent"
        elif days_until <= 14:
            return "high"
        else:
            return "high"
