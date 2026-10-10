"""
Scheduler Support Services

Extended service methods specifically for scheduler jobs.
These provide simplified interfaces for batch operations.

TodayService and HolidayService have been extracted into
today_service.py and holiday_service.py respectively.
"""
import logging

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..date_manager.models import SmartReminder, ReminderStatus, UserActivityPattern
from ..briefing.models import PreparationPlan, PreparationStatus, PreparationTask
from ...core.utils.timezone import utc_now, local_now, local_today

logger = logging.getLogger(__name__)


class AssistantReminderService:
    """Extended reminder service for scheduler jobs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def should_skip_reminder(self, reminder: SmartReminder) -> bool:
        """Check if reminder should be skipped (quiet hours, etc.)."""
        now = local_now()
        hour = now.hour

        # Skip during quiet hours (22:00 - 07:00) for non-urgent reminders
        if reminder.urgency_level != "urgent" and (hour >= 22 or hour < 7):
            return True

        # Check user's preferred quiet hours
        if reminder.user_id:
            pattern = await self._get_user_pattern(reminder.user_id)
            if pattern and pattern.quiet_hours_start and pattern.quiet_hours_end:
                if pattern.quiet_hours_start <= hour or hour < pattern.quiet_hours_end:
                    return reminder.urgency_level not in ["urgent", "high"]

        return False

    async def send_smart_reminder(self, reminder: SmartReminder) -> bool:
        """Send a smart reminder through the appropriate channel."""
        # Get user's activity pattern to determine best channel
        pattern = await self._get_user_pattern(reminder.user_id) if reminder.user_id else None

        # Determine channel priority based on pattern and urgency
        channels = self._get_channel_priority(reminder, pattern)

        # Try to send through each channel
        for channel in channels:
            try:
                success = await self._send_via_channel(reminder, channel)
                if success:
                    return True
            except Exception:
                continue

        return False

    async def _get_user_pattern(self, user_id: UUID) -> Optional[UserActivityPattern]:
        """Get user's activity pattern."""
        result = await self.db.execute(
            select(UserActivityPattern).where(
                UserActivityPattern.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    def _get_channel_priority(
        self,
        reminder: SmartReminder,
        pattern: Optional[UserActivityPattern]
    ) -> List[str]:
        """Get channel priority based on reminder and user pattern."""
        strategy = reminder.strategy or {}
        channels = strategy.get("channels", ["push"])

        # For urgent reminders, add SMS as backup
        if reminder.urgency_level == "urgent" and "sms" not in channels:
            channels = channels + ["sms"]

        # Prioritize based on user's preferred channel
        if pattern and pattern.preferred_channel:
            if pattern.preferred_channel in channels:
                channels.remove(pattern.preferred_channel)
                channels.insert(0, pattern.preferred_channel)

        return channels

    async def _send_via_channel(self, reminder: SmartReminder, channel: str) -> bool:
        """Send reminder via specific channel."""
        from ...core.push.notification_provider import app_notification_provider

        if channel == "push":
            # Send push notification
            await app_notification_provider.send_notification(
                user_id=str(reminder.user_id) if reminder.user_id else None,
                family_id=str(reminder.family_id),
                title=reminder.title,
                body=reminder.content,
                data={
                    "reminder_id": str(reminder.id),
                    "source_type": reminder.source_type,
                    "urgency": reminder.urgency_level,
                }
            )
            return True

        return True  # Simulate success for now

    async def update_activity_patterns(self, family_id: UUID) -> bool:
        """Update activity patterns for all users in a family."""
        from ..member.models import User

        # Get all users in this family
        result = await self.db.execute(
            select(User.id).where(
                and_(
                    User.family_id == family_id,
                    User.is_active == True,
                )
            )
        )
        user_ids = [row[0] for row in result.all() if row[0]]

        for user_id in user_ids:
            try:
                await self._analyze_and_update_pattern(user_id)
            except Exception:
                continue

        return True

    async def _analyze_and_update_pattern(self, user_id: UUID) -> None:
        """Analyze user activity and update pattern."""
        # Get recent reminder acknowledgments
        result = await self.db.execute(
            select(SmartReminder).where(
                and_(
                    SmartReminder.user_id == user_id,
                    SmartReminder.acknowledged_at.isnot(None),
                    SmartReminder.updated_at >= utc_now() - timedelta(days=30)
                )
            )
        )
        reminders = result.scalars().all()

        if not reminders:
            return

        # Analyze active hours
        weekday_hours: Dict[int, int] = {}
        weekend_hours: Dict[int, int] = {}
        response_times: List[int] = []

        for reminder in reminders:
            if not reminder.acknowledged_at:
                continue

            ack_time = reminder.acknowledged_at
            hour = ack_time.hour
            is_weekend = ack_time.weekday() >= 5

            if is_weekend:
                weekend_hours[hour] = weekend_hours.get(hour, 0) + 1
            else:
                weekday_hours[hour] = weekday_hours.get(hour, 0) + 1

            # Calculate response time
            if reminder.sent_at:
                response_seconds = (ack_time - reminder.sent_at).total_seconds()
                response_times.append(int(response_seconds / 60))

        # Extract top active hours
        def get_active_hours(hour_counts: dict, top_n: int = 6) -> List[int]:
            sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
            return sorted([h for h, _ in sorted_hours[:top_n]])

        weekday_active = get_active_hours(weekday_hours)
        weekend_active = get_active_hours(weekend_hours)
        avg_response = int(sum(response_times) / len(response_times)) if response_times else None

        # Update or create pattern
        result = await self.db.execute(
            select(UserActivityPattern).where(
                UserActivityPattern.user_id == user_id
            )
        )
        pattern = result.scalar_one_or_none()

        if pattern:
            pattern.weekday_active_hours = weekday_active
            pattern.weekend_active_hours = weekend_active
            pattern.avg_response_time_minutes = avg_response
            pattern.updated_at = utc_now()
        else:
            pattern = UserActivityPattern(
                user_id=user_id,
                weekday_active_hours=weekday_active,
                weekend_active_hours=weekend_active,
                avg_response_time_minutes=avg_response,
            )
            self.db.add(pattern)


class PreparationService:
    """Extended preparation service for scheduler jobs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_events_needing_preparation(
        self,
        days_ahead: int = 60,
        min_days_to_event: int = 7
    ) -> List[Dict[str, Any]]:
        """Get events that need preparation plans."""
        from ..date_manager.models import ImportantDate
        from ..member.models import Member, User

        today = local_today()
        end_date = today + timedelta(days=days_ahead)
        min_date = today + timedelta(days=min_days_to_event)

        events_needing_prep = []

        # Get important dates
        result = await self.db.execute(
            select(ImportantDate).where(
                and_(
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

            if next_occurrence and min_date <= next_occurrence <= end_date:
                # Check if preparation plan already exists
                existing = await self.db.execute(
                    select(PreparationPlan).where(
                        and_(
                            PreparationPlan.source_type == "important_date",
                            PreparationPlan.source_id == d.id,
                            PreparationPlan.event_date == next_occurrence,
                            PreparationPlan.is_deleted == False
                        )
                    )
                )
                if not existing.scalar_one_or_none():
                    # Get member info if available
                    member_name = None
                    if d.member_id:
                        member_result = await self.db.execute(
                            select(Member).where(
                                Member.id == d.member_id
                            )
                        )
                        member = member_result.scalar_one_or_none()
                        member_name = member.nickname if member else None

                    events_needing_prep.append({
                        "family_id": d.family_id,
                        "event_type": d.date_type,
                        "event_id": d.id,
                        "event_date": next_occurrence,
                        "member_id": d.member_id,
                        "member_name": member_name,
                        "title": d.title,
                    })

        return events_needing_prep

    async def create_preparation_plan(
        self,
        family_id: UUID,
        event_type: str,
        event_id: UUID,
        event_date: date,
        member_id: Optional[UUID] = None,
        member_name: Optional[str] = None,
    ) -> Optional[PreparationPlan]:
        """Create a preparation plan for an event."""
        # Generate plan content based on event type
        plan_content = await self._generate_plan_content(
            event_type, event_date, member_name
        )

        plan = PreparationPlan(
            family_id=family_id,
            source_type="important_date",
            source_id=event_id,
            event_type=event_type,
            event_date=event_date,
            member_id=member_id,
            title=f"{member_name or ''}的{event_type}准备方案",
            plan_content=plan_content,
            status=PreparationStatus.DRAFT,
        )

        self.db.add(plan)
        await self.db.flush()
        return plan

    async def _generate_plan_content(
        self,
        event_type: str,
        event_date: date,
        member_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate preparation plan content."""
        days_until = (event_date - local_today()).days

        if event_type == "birthday":
            return {
                "phases": [
                    {
                        "name": "选礼物",
                        "days_before": min(days_until, 14),
                        "tasks": [
                            "了解对方最近的兴趣爱好",
                            "确定礼物预算",
                            "浏览礼物推荐",
                            "选定礼物方案",
                        ]
                    },
                    {
                        "name": "准备庆祝",
                        "days_before": min(days_until, 7),
                        "tasks": [
                            "预订蛋糕",
                            "准备生日祝福语",
                            "通知其他家人",
                        ]
                    },
                    {
                        "name": "当天执行",
                        "days_before": 0,
                        "tasks": [
                            "发送生日祝福",
                            "赠送礼物",
                            "拍照记录",
                        ]
                    }
                ],
                "gift_suggestions": {
                    "enabled": True,
                    "budget_range": [100, 500],
                }
            }
        elif event_type == "anniversary":
            return {
                "phases": [
                    {
                        "name": "策划",
                        "days_before": min(days_until, 14),
                        "tasks": [
                            "回忆共同经历",
                            "确定庆祝方式",
                            "准备特别礼物",
                        ]
                    },
                    {
                        "name": "预订",
                        "days_before": min(days_until, 7),
                        "tasks": [
                            "预订餐厅/场地",
                            "准备纪念礼物",
                        ]
                    }
                ]
            }
        else:
            return {
                "phases": [
                    {
                        "name": "准备",
                        "days_before": min(days_until, 7),
                        "tasks": [
                            "确定准备事项",
                            "安排时间",
                        ]
                    }
                ]
            }

    async def generate_preparation_tasks(
        self,
        plan: PreparationPlan
    ) -> List[PreparationTask]:
        """Generate tasks from a preparation plan."""
        tasks = []
        plan_content = plan.plan_content or {}
        phases = plan_content.get("phases", [])

        for phase in phases:
            phase_name = phase.get("name", "")
            days_before = phase.get("days_before", 7)
            task_date = plan.event_date - timedelta(days=days_before)

            for task_desc in phase.get("tasks", []):
                task = PreparationTask(
                    plan_id=plan.id,
                    title=task_desc,
                    phase=phase_name,
                    due_date=task_date,
                    status="pending",
                )
                self.db.add(task)
                tasks.append(task)

        await self.db.flush()
        return tasks

    async def calculate_plan_progress(self, plan_id: UUID) -> int:
        """Calculate preparation plan progress percentage."""
        result = await self.db.execute(
            select(func.count(PreparationTask.id)).where(
                PreparationTask.plan_id == plan_id
            )
        )
        total = result.scalar() or 0

        if total == 0:
            return 0

        result = await self.db.execute(
            select(func.count(PreparationTask.id)).where(
                and_(
                    PreparationTask.plan_id == plan_id,
                    PreparationTask.status == "completed"
                )
            )
        )
        completed = result.scalar() or 0

        return int((completed / total) * 100)

    async def escalate_overdue_tasks(self, plan_id: UUID) -> int:
        """Escalate overdue tasks in a plan."""
        today = local_today()
        result = await self.db.execute(
            select(PreparationTask).where(
                and_(
                    PreparationTask.plan_id == plan_id,
                    PreparationTask.status == "pending",
                    PreparationTask.due_date < today
                )
            )
        )
        overdue_tasks = result.scalars().all()

        escalated = 0
        for task in overdue_tasks:
            task.priority = "high"
            escalated += 1

        return escalated
