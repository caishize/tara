"""
Holiday Preparation Service - Core business logic for holiday preparations.

Coordinates template selection and task creation for automatic holiday preparations.
"""

import logging
from datetime import date, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from .templates import get_template_registry, PreparationPlanDefinition
from .models import (
    ImportantDate,
    HolidayCategory,
    get_holiday_category,
    MAJOR_HOLIDAYS,
    MINOR_HOLIDAYS,
    SOLAR_TERMS,
)
from ..views.task_service import FamilyTaskService
from ..views.models import FamilyTask
# Import Member to ensure SQLAlchemy mapper is properly initialized
from ..member.models.member import Member
from ...core.constants import SYSTEM_FAMILY_ID, SYSTEM_USER_ID


logger = logging.getLogger(__name__)


@dataclass
class PreparationResult:
    """Result of creating a preparation plan."""
    success: bool
    holiday_name: str
    occurrence_date: date
    parent_task_id: Optional[UUID] = None
    subtask_count: int = 0
    error: Optional[str] = None


class HolidayPreparationService:
    """
    Service for creating holiday preparation tasks.

    Coordinates template selection, task generation, and integration
    with the FamilyTask system.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the service.

        Args:
            session: Async database session
        """
        self.session = session
        self.task_service = FamilyTaskService(session)
        self.template_registry = get_template_registry()

    async def create_holiday_preparation(
        self,
        family_id: UUID,
        holiday_name: str,
        occurrence_date: date,
        creator_id: UUID,
        trigger_days_before: Optional[int] = None,
    ) -> PreparationResult:
        """
        Create preparation tasks for a holiday.

        Args:
            family_id: Family ID to create tasks for
            holiday_name: Name of the holiday
            occurrence_date: Date of the holiday
            creator_id: User ID creating the tasks
            trigger_days_before: Override for trigger days (uses template default if None)

        Returns:
            PreparationResult with status and task info
        """
        try:
            # Get template for this holiday
            template = self.template_registry.get_template_for_holiday(holiday_name)

            # Use template default if trigger not specified
            if trigger_days_before is None:
                trigger_days_before = template.default_trigger_days_before

            # Check if preparation already exists
            if await self._preparation_exists(
                family_id, holiday_name, occurrence_date, trigger_days_before
            ):
                logger.info(
                    f"Preparation already exists for {holiday_name} "
                    f"({occurrence_date}) with trigger {trigger_days_before}"
                )
                return PreparationResult(
                    success=True,
                    holiday_name=holiday_name,
                    occurrence_date=occurrence_date,
                    error="Preparation already exists"
                )

            # Generate preparation plan
            plan = template.generate_plan(
                holiday_name=holiday_name,
                occurrence_date=occurrence_date,
                trigger_days_before=trigger_days_before,
            )

            # Create parent task
            parent_task = await self._create_parent_task(
                family_id=family_id,
                creator_id=creator_id,
                plan=plan,
                occurrence_date=occurrence_date,
            )

            # Create subtasks
            subtasks = await self._create_subtasks(
                family_id=family_id,
                creator_id=creator_id,
                parent_task_id=parent_task.id,
                plan=plan,
                occurrence_date=occurrence_date,
            )

            logger.info(
                f"Created preparation for {holiday_name}: "
                f"parent={parent_task.id}, subtasks={len(subtasks)}"
            )

            return PreparationResult(
                success=True,
                holiday_name=holiday_name,
                occurrence_date=occurrence_date,
                parent_task_id=parent_task.id,
                subtask_count=len(subtasks),
            )

        except Exception as e:
            logger.error(
                f"Failed to create preparation for {holiday_name}: {e}",
                exc_info=True
            )
            return PreparationResult(
                success=False,
                holiday_name=holiday_name,
                occurrence_date=occurrence_date,
                error=str(e),
            )

    async def _preparation_exists(
        self,
        family_id: UUID,
        holiday_name: str,
        occurrence_date: date,
        trigger_days_before: int,
    ) -> bool:
        """Check if preparation already exists for this holiday and trigger."""
        # Query for existing parent task with matching metadata
        stmt = select(FamilyTask).where(
            and_(
                FamilyTask.family_id == family_id,
                FamilyTask.task_type == "preparation",
                FamilyTask.parent_task_id.is_(None),  # Only parent tasks
                FamilyTask.task_metadata["source"]["type"].astext == "holiday_preparation",
                FamilyTask.task_metadata["source"]["holiday_name"].astext == holiday_name,
                FamilyTask.task_metadata["source"]["occurrence_date"].astext == occurrence_date.isoformat(),
            )
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _create_parent_task(
        self,
        family_id: UUID,
        creator_id: UUID,
        plan: PreparationPlanDefinition,
        occurrence_date: date,
    ) -> FamilyTask:
        """Create the parent preparation task."""
        return await self.task_service.create_task(
            family_id=family_id,
            title=plan.parent_title,
            creator_id=creator_id,
            description=plan.parent_description,
            task_type="preparation",
            due_date=occurrence_date,
            priority=plan.parent_priority,
            metadata=plan.metadata,
        )

    async def _create_subtasks(
        self,
        family_id: UUID,
        creator_id: UUID,
        parent_task_id: UUID,
        plan: PreparationPlanDefinition,
        occurrence_date: date,
    ) -> List[FamilyTask]:
        """Create subtasks for the preparation plan."""
        subtasks = []

        for subtask_def in plan.subtasks:
            # Calculate due date for subtask
            if subtask_def.days_before_due:
                due_date = occurrence_date - timedelta(days=subtask_def.days_before_due)
            else:
                due_date = occurrence_date

            subtask = await self.task_service.create_task(
                family_id=family_id,
                title=subtask_def.title,
                creator_id=creator_id,
                description=subtask_def.description,
                task_type="preparation",
                due_date=due_date,
                priority=subtask_def.priority,
                parent_task_id=parent_task_id,
                metadata={
                    "source": plan.metadata["source"],
                    "auto_generated": True,
                },
            )
            subtasks.append(subtask)

        return subtasks

    async def get_upcoming_holidays_for_preparation(
        self,
        days_ahead: int = 30,
    ) -> List[Tuple[str, date, int]]:
        """
        Get holidays that need preparation tasks created.

        Checks for holidays in different windows based on their category:
        - Major holidays: 30 days ahead
        - Minor holidays: 7 days ahead
        - Solar terms: 3 days ahead

        Args:
            days_ahead: Maximum days ahead to look

        Returns:
            List of (holiday_name, occurrence_date, trigger_days_before) tuples
        """
        today = date.today()
        results = []

        # Query upcoming holidays from ImportantDate
        stmt = select(ImportantDate).where(
            and_(
                ImportantDate.family_id == SYSTEM_FAMILY_ID,
                ImportantDate.solar_date >= today,
                ImportantDate.solar_date <= today + timedelta(days=days_ahead),
            )
        )

        query_result = await self.session.execute(stmt)
        upcoming_dates = query_result.scalars().all()

        for date_record in upcoming_dates:
            holiday_name = date_record.title
            occurrence_date = date_record.solar_date
            days_until = (occurrence_date - today).days

            # Get trigger days for this holiday
            trigger_days = self.template_registry.get_trigger_days_before(holiday_name)

            # Check if we're within the trigger window
            if days_until <= trigger_days:
                results.append((holiday_name, occurrence_date, trigger_days))

        return results

    async def process_all_upcoming_preparations(
        self,
        family_id: UUID = SYSTEM_FAMILY_ID,
        creator_id: UUID = SYSTEM_USER_ID,
    ) -> Dict[str, Any]:
        """
        Process all upcoming holidays and create preparation tasks.

        This is the main entry point for the scheduled job.

        Args:
            family_id: Family to create tasks for
            creator_id: User creating the tasks

        Returns:
            Summary dict with created/skipped/failed counts
        """
        created = 0
        skipped = 0
        failed = 0

        # Get all holidays that need preparation
        holidays = await self.get_upcoming_holidays_for_preparation()

        for holiday_name, occurrence_date, trigger_days in holidays:
            result = await self.create_holiday_preparation(
                family_id=family_id,
                holiday_name=holiday_name,
                occurrence_date=occurrence_date,
                creator_id=creator_id,
                trigger_days_before=trigger_days,
            )

            if result.success:
                if result.parent_task_id:
                    created += 1
                else:
                    skipped += 1  # Already existed
            else:
                failed += 1

        return {
            "created": created,
            "skipped": skipped,
            "failed": failed,
            "total_checked": len(holidays),
        }
