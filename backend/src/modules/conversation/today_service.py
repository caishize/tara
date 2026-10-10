"""Today Service for scheduler jobs.

Syncs module items to TodayItem and generates AI suggestions.
Extracted from scheduler_support.py for file-size compliance.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..briefing.models import PreparationPlan, PreparationStatus, PreparationTask
from ..views.models import TodayItem, TodayItemStatus, AISuggestion, FamilyTask
from ...core.utils.timezone import utc_now, local_today

logger = logging.getLogger(__name__)


class TodayService:
    """Extended today service for scheduler jobs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_items_for_family(self, family_id: UUID) -> Dict[str, int]:
        """Sync all module items for a family."""
        synced = {
            "important_date": 0,
            "family_task": 0,
            "shopping_item": 0,
            "health_checkup": 0,
            "preparation_task": 0,
        }

        # Sync important dates
        synced["important_date"] = await self._sync_important_dates(family_id)

        # Sync family tasks
        synced["family_task"] = await self._sync_family_tasks(family_id)

        # Sync shopping items
        synced["shopping_item"] = await self._sync_shopping_items(family_id)

        # Sync preparation tasks
        synced["preparation_task"] = await self._sync_preparation_tasks(family_id)

        return synced

    async def _sync_important_dates(self, family_id: UUID) -> int:
        """Sync important dates to today items."""
        from ..date_manager.models import ImportantDate

        today = local_today()
        end_date = today + timedelta(days=3)
        synced = 0

        try:
            result = await self.db.execute(
                select(ImportantDate).where(
                    and_(
                        ImportantDate.family_id == family_id,
                        ImportantDate.is_active == True,
                        ImportantDate.is_deleted == False
                    )
                )
            )
            dates = result.scalars().all()

            for d in dates:
                try:
                    next_occurrence = d.get_next_occurrence()
                except Exception:
                    continue

                if next_occurrence and today <= next_occurrence <= end_date:
                    # Check if already synced
                    existing = await self.db.execute(
                        select(TodayItem).where(
                            and_(
                                TodayItem.source_type == "important_date",
                                TodayItem.source_id == d.id,
                                TodayItem.status == TodayItemStatus.ACTIVE
                            )
                        )
                    )
                    if not existing.scalar_one_or_none():
                        days_until = (next_occurrence - today).days
                        urgency = "urgent" if days_until == 0 else "important" if days_until <= 1 else "normal"

                        item = TodayItem(
                            family_id=family_id,
                            source_type="important_date",
                            source_id=d.id,
                            title=d.title,
                            urgency=urgency,
                            description=f"{'今天' if days_until == 0 else f'{days_until}天后'}",
                            due_datetime=datetime.combine(next_occurrence, datetime.min.time()),
                            actions=[
                                {"type": "view", "label": "查看"},
                                {"type": "prepare", "label": "准备"},
                            ],
                        )
                        self.db.add(item)
                        synced += 1
        except Exception:
            logger.exception("_sync_important_dates failed for family %s", family_id)

        return synced

    async def _sync_family_tasks(self, family_id: UUID) -> int:
        """Sync family tasks to today items."""
        today = local_today()
        synced = 0

        try:
            result = await self.db.execute(
                select(FamilyTask).where(
                    and_(
                        FamilyTask.family_id == family_id,
                        FamilyTask.status.in_(["pending", "in_progress"]),
                        FamilyTask.is_deleted == False,
                        or_(
                            FamilyTask.due_date <= today,
                            FamilyTask.due_date == today + timedelta(days=1)
                        )
                    )
                )
            )
            tasks = result.scalars().all()
            if not tasks:
                return 0

            # Batch-fetch existing TodayItems to avoid N+1 queries
            task_ids = [t.id for t in tasks]
            existing_result = await self.db.execute(
                select(TodayItem.source_id).where(
                    and_(
                        TodayItem.source_type == "family_task",
                        TodayItem.source_id.in_(task_ids),
                        TodayItem.status == TodayItemStatus.ACTIVE,
                    )
                )
            )
            existing_task_ids = {row[0] for row in existing_result.all()}

            for task in tasks:
                if task.id not in existing_task_ids:
                    is_overdue = task.due_date and task.due_date < today
                    urgency = "urgent" if is_overdue else \
                             "important" if task.priority == "high" else "normal"

                    item = TodayItem(
                        family_id=family_id,
                        user_id=task.assignee_id,
                        source_type="family_task",
                        source_id=task.id,
                        title=task.title,
                        urgency=urgency,
                        description=task.description,
                        due_datetime=datetime.combine(task.due_date, task.due_time or datetime.min.time()) if task.due_date else None,
                    )
                    self.db.add(item)
                    synced += 1
        except Exception:
            logger.exception("_sync_family_tasks failed for family %s", family_id)

        return synced

    async def _sync_shopping_items(self, family_id: UUID) -> int:
        """Shopping module removed -- no-op."""
        return 0

    async def _sync_preparation_tasks(self, family_id: UUID) -> int:
        """Sync preparation tasks to today items."""
        today = local_today()
        synced = 0

        try:
            # Get active preparation plans
            result = await self.db.execute(
                select(PreparationPlan).where(
                    and_(
                        PreparationPlan.family_id == family_id,
                        PreparationPlan.status.in_([
                            PreparationStatus.ACTIVE,
                            PreparationStatus.IN_PROGRESS
                        ]),
                        PreparationPlan.is_deleted == False
                    )
                )
            )
            plans = result.scalars().all()

            for plan in plans:
                # Get pending tasks
                task_result = await self.db.execute(
                    select(PreparationTask).where(
                        and_(
                            PreparationTask.plan_id == plan.id,
                            PreparationTask.status == "pending",
                            PreparationTask.due_date <= today + timedelta(days=3)
                        )
                    )
                )
                tasks = task_result.scalars().all()

                for task in tasks:
                    existing = await self.db.execute(
                        select(TodayItem).where(
                            and_(
                                TodayItem.source_type == "preparation_task",
                                TodayItem.source_id == task.id,
                                TodayItem.status == TodayItemStatus.ACTIVE
                            )
                        )
                    )
                    if not existing.scalar_one_or_none():
                        days_until = (task.due_date - today).days if task.due_date else 0
                        urgency = "urgent" if days_until <= 0 else \
                                 "important" if days_until <= 1 else "normal"

                        item = TodayItem(
                            family_id=family_id,
                            source_type="preparation_task",
                            source_id=task.id,
                            title=task.title,
                            urgency=urgency,
                            description=f"准备方案: {plan.title}",
                            due_datetime=datetime.combine(task.due_date, datetime.min.time()) if task.due_date else None,
                        )
                        self.db.add(item)
                        synced += 1
        except Exception:
            logger.exception("_sync_preparation_tasks failed for family %s", family_id)

        return synced

    async def generate_suggestions(self, family_id: UUID) -> List[AISuggestion]:
        """Generate AI suggestions for a family."""
        suggestions = []
        today = local_today()

        try:
            # Suggestion 1: Upcoming birthdays needing preparation
            from ..date_manager.models import ImportantDate

            result = await self.db.execute(
                select(ImportantDate).where(
                    and_(
                        ImportantDate.family_id == family_id,
                        ImportantDate.date_type == "birthday",
                        ImportantDate.is_active == True,
                        ImportantDate.is_deleted == False
                    )
                )
            )
            dates = result.scalars().all()

            for d in dates:
                try:
                    next_occurrence = d.get_next_occurrence()
                except Exception:
                    continue

                if next_occurrence:
                    days_until = (next_occurrence - today).days
                    if 7 <= days_until <= 14:
                        # Check if preparation plan exists
                        existing_plan = await self.db.execute(
                            select(PreparationPlan).where(
                                and_(
                                    PreparationPlan.source_id == d.id,
                                    PreparationPlan.is_deleted == False
                                )
                            )
                        )
                        if not existing_plan.scalar_one_or_none():
                            suggestion = AISuggestion(
                                family_id=family_id,
                                suggestion_type="preparation",
                                content=f"{d.title}还有{days_until}天，是否需要帮您准备礼物方案？",
                                priority=2,
                                actions=[
                                    {"type": "prepare", "label": "开始准备"},
                                    {"type": "remind_later", "label": "稍后提醒"},
                                ],
                                context={
                                    "date_id": str(d.id),
                                    "date_type": d.date_type,
                                    "days_until": days_until,
                                },
                                valid_until=utc_now() + timedelta(days=3),
                            )
                            self.db.add(suggestion)
                            suggestions.append(suggestion)

            # Suggestion 2: Overdue tasks reminder
            overdue_result = await self.db.execute(
                select(func.count(FamilyTask.id)).where(
                    and_(
                        FamilyTask.family_id == family_id,
                        FamilyTask.status == "pending",
                        FamilyTask.due_date < today,
                        FamilyTask.is_deleted == False
                    )
                )
            )
            overdue_count = overdue_result.scalar() or 0

            if overdue_count > 0:
                suggestion = AISuggestion(
                    family_id=family_id,
                    suggestion_type="task_reminder",
                    content=f"您有{overdue_count}个任务已逾期，是否需要查看处理？",
                    priority=3,
                    actions=[
                        {"type": "view_tasks", "label": "查看任务"},
                        {"type": "dismiss", "label": "稍后处理"},
                    ],
                    valid_until=utc_now() + timedelta(hours=12),
                )
                self.db.add(suggestion)
                suggestions.append(suggestion)

            await self.db.flush()

        except Exception as e:
            pass

        return suggestions
