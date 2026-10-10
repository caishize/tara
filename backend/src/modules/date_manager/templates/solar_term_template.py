"""
Solar Term Template - Template for 24 solar terms.

Solar terms (二十四节气) warrant 3-day advance notice with simple reminders.
"""

from datetime import date
from typing import List, Dict

from .base import HolidayPreparationTemplate, SubtaskDefinition


# Preparation tasks for notable solar terms
SOLAR_TERM_TASKS: Dict[str, List[Dict]] = {
    "立春": [
        {"title": "春季养生准备", "priority": "low", "days_before": 3},
        {"title": "调整作息迎接春天", "priority": "low", "days_before": 1},
    ],
    "清明": [
        {"title": "清明养生注意事项", "priority": "low", "days_before": 3},
    ],
    "立夏": [
        {"title": "夏季防暑准备", "priority": "normal", "days_before": 3},
        {"title": "检查空调/风扇", "priority": "low", "days_before": 2},
    ],
    "夏至": [
        {"title": "注意防暑降温", "priority": "normal", "days_before": 2},
    ],
    "立秋": [
        {"title": "秋季养生准备", "priority": "low", "days_before": 3},
        {"title": "准备秋季衣物", "priority": "low", "days_before": 2},
    ],
    "秋分": [
        {"title": "秋季进补计划", "priority": "low", "days_before": 3},
    ],
    "立冬": [
        {"title": "冬季保暖准备", "priority": "normal", "days_before": 3},
        {"title": "检查取暖设备", "priority": "normal", "days_before": 2},
    ],
    "冬至": [
        {"title": "准备饺子/汤圆材料", "priority": "normal", "days_before": 2},
        {"title": "冬至养生注意", "priority": "low", "days_before": 1},
    ],
    "小寒": [
        {"title": "注意防寒保暖", "priority": "normal", "days_before": 2},
    ],
    "大寒": [
        {"title": "一年最冷时节保暖", "priority": "normal", "days_before": 2},
        {"title": "准备年货采购", "priority": "normal", "days_before": 1},
    ],
}

# Default task for solar terms without specific configuration
DEFAULT_SOLAR_TERM_TASKS = [
    {"title": "了解节气养生知识", "priority": "low", "days_before": 2},
]


class SolarTermTemplate(HolidayPreparationTemplate):
    """
    Template for 24 solar terms.

    Solar terms are traditional Chinese calendar markers for seasonal changes.
    They warrant 3-day advance notice with simple health and lifestyle reminders.
    """

    @property
    def category_name(self) -> str:
        return "solar_term"

    @property
    def default_trigger_days_before(self) -> int:
        return 3

    def get_parent_task_title(self, holiday_name: str, occurrence_date: date) -> str:
        """Solar terms use different title format."""
        return f"{holiday_name}节气提醒"

    def get_parent_task_description(
        self,
        holiday_name: str,
        occurrence_date: date,
        days_until: int
    ) -> str:
        """Generate description for solar term reminder."""
        date_str = occurrence_date.strftime("%Y年%m月%d日")
        return f"{holiday_name}({date_str})即将到来，注意应时养生"

    def get_priority(self, days_until: int) -> str:
        """Solar terms generally have lower priority."""
        if days_until <= 1:
            return "normal"
        else:
            return "low"

    def get_subtasks(
        self,
        holiday_name: str,
        occurrence_date: date,
        days_until: int
    ) -> List[SubtaskDefinition]:
        """Generate simple subtasks for solar terms."""
        # Get term-specific tasks or use defaults
        tasks_config = SOLAR_TERM_TASKS.get(holiday_name, DEFAULT_SOLAR_TERM_TASKS)

        subtasks = []
        for task in tasks_config:
            if task.get("days_before", 3) <= days_until:
                subtasks.append(SubtaskDefinition(
                    title=task["title"],
                    priority=task.get("priority", "low"),
                    days_before_due=task.get("days_before"),
                ))

        return subtasks
