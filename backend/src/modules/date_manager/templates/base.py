"""
Holiday Preparation Template Base - Abstract template for holiday preparations.

Provides the interface for generating preparation tasks for different holiday types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Dict, Any


@dataclass
class SubtaskDefinition:
    """Definition for a subtask to be created."""
    title: str
    description: Optional[str] = None
    priority: str = "normal"
    days_before_due: Optional[int] = None  # Days before holiday for this task's due date


@dataclass
class PreparationPlanDefinition:
    """Complete preparation plan definition."""
    parent_title: str
    parent_description: str
    parent_priority: str
    subtasks: List[SubtaskDefinition]
    metadata: Dict[str, Any]


class HolidayPreparationTemplate(ABC):
    """
    Abstract base class for holiday preparation templates.

    Each template defines how to generate preparation tasks for a specific
    category of holidays (major, minor, solar term).
    """

    @property
    @abstractmethod
    def category_name(self) -> str:
        """Return the category name for this template."""
        pass

    @property
    @abstractmethod
    def default_trigger_days_before(self) -> int:
        """Default number of days before holiday to create preparation tasks."""
        pass

    @abstractmethod
    def get_subtasks(
        self,
        holiday_name: str,
        occurrence_date: date,
        days_until: int
    ) -> List[SubtaskDefinition]:
        """
        Generate list of subtasks for the preparation plan.

        Args:
            holiday_name: Name of the holiday
            occurrence_date: Date of the holiday
            days_until: Days until the holiday

        Returns:
            List of SubtaskDefinition objects
        """
        pass

    def get_parent_task_title(self, holiday_name: str, occurrence_date: date) -> str:
        """Generate parent task title."""
        return f"{holiday_name}准备"

    def get_parent_task_description(
        self,
        holiday_name: str,
        occurrence_date: date,
        days_until: int
    ) -> str:
        """Generate parent task description."""
        date_str = occurrence_date.strftime("%Y年%m月%d日")
        return f"为{holiday_name}({date_str})做准备，还有{days_until}天"

    def get_priority(self, days_until: int) -> str:
        """
        Determine task priority based on urgency.

        Args:
            days_until: Days until the holiday

        Returns:
            Priority string: "urgent", "high", "normal", or "low"
        """
        if days_until <= 3:
            return "urgent"
        elif days_until <= 7:
            return "high"
        elif days_until <= 14:
            return "normal"
        else:
            return "normal"

    def get_metadata(
        self,
        holiday_name: str,
        occurrence_date: date,
        trigger_days_before: int
    ) -> Dict[str, Any]:
        """
        Generate task metadata for tracking and deduplication.

        Args:
            holiday_name: Name of the holiday
            occurrence_date: Date of the holiday
            trigger_days_before: Days before holiday when this was created

        Returns:
            Metadata dictionary
        """
        return {
            "source": {
                "type": "holiday_preparation",
                "holiday_name": holiday_name,
                "occurrence_date": occurrence_date.isoformat(),
                "trigger_days_before": trigger_days_before,
                "template_category": self.category_name,
            },
            "auto_generated": True,
        }

    def generate_plan(
        self,
        holiday_name: str,
        occurrence_date: date,
        trigger_days_before: int
    ) -> PreparationPlanDefinition:
        """
        Generate complete preparation plan definition.

        Args:
            holiday_name: Name of the holiday
            occurrence_date: Date of the holiday
            trigger_days_before: Days before holiday when this is being created

        Returns:
            PreparationPlanDefinition with all task information
        """
        days_until = (occurrence_date - date.today()).days

        return PreparationPlanDefinition(
            parent_title=self.get_parent_task_title(holiday_name, occurrence_date),
            parent_description=self.get_parent_task_description(
                holiday_name, occurrence_date, days_until
            ),
            parent_priority=self.get_priority(days_until),
            subtasks=self.get_subtasks(holiday_name, occurrence_date, days_until),
            metadata=self.get_metadata(holiday_name, occurrence_date, trigger_days_before),
        )
