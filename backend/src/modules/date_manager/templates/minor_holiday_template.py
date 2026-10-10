"""
Minor Holiday Template - Template for minor holidays.

Minor holidays (元旦, 清明节, 端午节, etc.) warrant 7-day advance preparation.
"""

from datetime import date
from typing import List, Dict

from .base import HolidayPreparationTemplate, SubtaskDefinition


# Preparation tasks for minor holidays
MINOR_HOLIDAY_TASKS: Dict[str, List[Dict]] = {
    "元旦": [
        {"title": "规划跨年活动", "priority": "normal", "days_before": 7},
        {"title": "预订跨年聚餐", "priority": "normal", "days_before": 5},
        {"title": "准备新年礼物", "priority": "low", "days_before": 3},
    ],
    "清明节": [
        {"title": "安排扫墓时间", "priority": "high", "days_before": 7},
        {"title": "准备祭扫用品", "priority": "normal", "days_before": 5},
        {"title": "查看天气预报", "priority": "low", "days_before": 2},
        {"title": "注意防火安全", "priority": "high", "days_before": 1},
    ],
    "劳动节": [
        {"title": "规划五一出行", "priority": "normal", "days_before": 7},
        {"title": "预订出行票务", "priority": "high", "days_before": 7},
        {"title": "准备出行物品", "priority": "normal", "days_before": 3},
    ],
    "端午节": [
        {"title": "准备粽子材料", "priority": "normal", "days_before": 5},
        {"title": "安排端午活动", "priority": "normal", "days_before": 5},
        {"title": "购买艾草、香包", "priority": "low", "days_before": 3},
    ],
    "元宵节": [
        {"title": "准备汤圆/元宵", "priority": "normal", "days_before": 3},
        {"title": "查询赏灯活动", "priority": "low", "days_before": 3},
        {"title": "安排家庭聚会", "priority": "normal", "days_before": 2},
    ],
    "重阳节": [
        {"title": "安排看望长辈", "priority": "high", "days_before": 5},
        {"title": "准备重阳糕点", "priority": "normal", "days_before": 3},
        {"title": "规划登高活动", "priority": "low", "days_before": 3},
    ],
    "除夕": [
        {"title": "确认年夜饭安排", "priority": "high", "days_before": 3},
        {"title": "准备守岁零食", "priority": "normal", "days_before": 2},
        {"title": "准备压岁钱", "priority": "high", "days_before": 1},
    ],
}

# Default tasks for minor holidays without specific configuration
DEFAULT_MINOR_TASKS = [
    {"title": "了解节日习俗", "priority": "low", "days_before": 5},
    {"title": "安排节日活动", "priority": "normal", "days_before": 3},
]


class MinorHolidayTemplate(HolidayPreparationTemplate):
    """
    Template for minor holidays requiring moderate preparation.

    Minor holidays include 元旦, 清明节, 劳动节, 端午节, etc.
    These holidays warrant 7-day advance notice.
    """

    @property
    def category_name(self) -> str:
        return "minor"

    @property
    def default_trigger_days_before(self) -> int:
        return 7

    def get_subtasks(
        self,
        holiday_name: str,
        occurrence_date: date,
        days_until: int
    ) -> List[SubtaskDefinition]:
        """Generate subtasks for minor holidays."""
        # Get holiday-specific tasks or use defaults
        tasks_config = MINOR_HOLIDAY_TASKS.get(holiday_name, DEFAULT_MINOR_TASKS)

        subtasks = []
        for task in tasks_config:
            # Only include tasks that are still relevant
            if task.get("days_before", 7) <= days_until:
                subtasks.append(SubtaskDefinition(
                    title=task["title"],
                    priority=task.get("priority", "normal"),
                    days_before_due=task.get("days_before"),
                ))

        return subtasks
