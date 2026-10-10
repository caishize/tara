"""
Holiday Preparation Templates - Template registry and exports.

Provides template selection based on holiday category.
"""

from typing import Optional

from .base import (
    HolidayPreparationTemplate,
    SubtaskDefinition,
    PreparationPlanDefinition,
)
from .major_holiday_template import MajorHolidayTemplate
from .minor_holiday_template import MinorHolidayTemplate
from .solar_term_template import SolarTermTemplate
from ..models import HolidayCategory, get_holiday_category


class TemplateRegistry:
    """
    Registry for holiday preparation templates.

    Manages template instances and provides template selection based on
    holiday category.
    """

    def __init__(self):
        """Initialize template instances."""
        self._templates = {
            HolidayCategory.MAJOR: MajorHolidayTemplate(),
            HolidayCategory.MINOR: MinorHolidayTemplate(),
            HolidayCategory.SOLAR_TERM: SolarTermTemplate(),
        }

    def get_template(
        self,
        category: HolidayCategory
    ) -> HolidayPreparationTemplate:
        """
        Get template for a holiday category.

        Args:
            category: HolidayCategory enum value

        Returns:
            Appropriate template instance

        Raises:
            ValueError: If category is not supported
        """
        template = self._templates.get(category)
        if not template:
            raise ValueError(f"No template registered for category: {category}")
        return template

    def get_template_for_holiday(
        self,
        holiday_name: str
    ) -> HolidayPreparationTemplate:
        """
        Get template for a specific holiday.

        Args:
            holiday_name: Name of the holiday

        Returns:
            Appropriate template instance
        """
        category = get_holiday_category(holiday_name)
        return self.get_template(category)

    def get_trigger_days_before(self, holiday_name: str) -> int:
        """
        Get the number of days before holiday to trigger preparation.

        Args:
            holiday_name: Name of the holiday

        Returns:
            Number of days before to create preparation tasks
        """
        template = self.get_template_for_holiday(holiday_name)
        return template.default_trigger_days_before


# Global registry instance
_template_registry: Optional[TemplateRegistry] = None


def get_template_registry() -> TemplateRegistry:
    """Get or create the global template registry."""
    global _template_registry
    if _template_registry is None:
        _template_registry = TemplateRegistry()
    return _template_registry


__all__ = [
    "HolidayPreparationTemplate",
    "SubtaskDefinition",
    "PreparationPlanDefinition",
    "MajorHolidayTemplate",
    "MinorHolidayTemplate",
    "SolarTermTemplate",
    "TemplateRegistry",
    "get_template_registry",
]
