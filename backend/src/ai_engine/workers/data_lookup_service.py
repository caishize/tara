"""
Data Lookup Service - Provides real data lookups for FastWorker.

Retrieves tasks, reminders, today items, and family members from the database.
Formats data for LLM consumption.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

from ...core.utils.timezone import utc_now
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from ...modules.views.repositories import FamilyTaskRepository
from ...modules.date_manager.repositories import ReminderRepository
from ...modules.views.repositories import TodayRepository
from ...modules.member.repositories.member_repository import MemberRepository
from ...modules.curation.models import CuratedEvent
from ...modules.trip.models.trip_plan import TripPlan

from .data_lookup_classifier import DataLookupType


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataLookupResult:
    """Result of a data lookup operation."""
    success: bool
    data: Dict[str, Any]
    message: str
    item_count: int


class DataLookupService:
    """
    Service for looking up user data from the database.

    Provides formatted data suitable for LLM context and responses.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._task_repo = FamilyTaskRepository(db)
        self._reminder_repo = ReminderRepository(db)
        self._today_repo = TodayRepository(db)
        self._member_repo = MemberRepository(db)

    async def lookup(
        self,
        lookup_type: DataLookupType,
        user_id: str,
        family_id: str,
        sub_type: Optional[str] = None,
        limit: int = 10,
    ) -> DataLookupResult:
        """
        Perform a data lookup based on type.

        Args:
            lookup_type: Type of data to look up
            user_id: User ID (string, will be converted to UUID)
            family_id: Family ID (string, will be converted to UUID)
            sub_type: Optional sub-type for more specific queries
            limit: Maximum number of items to return

        Returns:
            DataLookupResult with the requested data
        """
        try:
            user_uuid = UUID(user_id)
            family_uuid = UUID(family_id)
        except ValueError as e:
            logger.error("Invalid UUID: %s", e)
            return DataLookupResult(
                success=False,
                data={},
                message="Invalid user or family ID",
                item_count=0,
            )

        try:
            if lookup_type == DataLookupType.TASK:
                return await self._lookup_tasks(user_uuid, family_uuid, sub_type, limit)
            elif lookup_type == DataLookupType.REMINDER:
                return await self._lookup_reminders(user_uuid, family_uuid, limit)
            elif lookup_type == DataLookupType.TODAY:
                return await self._lookup_today_items(user_uuid, family_uuid, limit)
            elif lookup_type == DataLookupType.FAMILY_MEMBER:
                return await self._lookup_family_members(family_uuid, limit)
            elif lookup_type == DataLookupType.SCHEDULE:
                return await self._lookup_schedule(user_uuid, family_uuid, limit)
            elif lookup_type == DataLookupType.TRIP:
                return await self._lookup_trips(user_uuid, family_uuid, sub_type, limit)
            else:
                return DataLookupResult(
                    success=False,
                    data={},
                    message="Unknown lookup type",
                    item_count=0,
                )
        except Exception as e:
            logger.error("Data lookup failed: %s", e)
            return DataLookupResult(
                success=False,
                data={},
                message="查询失败，请稍后重试",
                item_count=0,
            )

    async def _lookup_tasks(
        self,
        user_id: UUID,
        family_id: UUID,
        sub_type: Optional[str],
        limit: int,
    ) -> DataLookupResult:
        """Look up tasks from the database."""
        tasks = []

        if sub_type == "overdue":
            tasks = await self._task_repo.get_overdue_tasks(
                family_id=family_id,
                user_id=user_id,
            )
            message = "逾期任务" if tasks else "没有逾期的任务"
        elif sub_type == "today":
            tasks = await self._task_repo.get_today_tasks(
                family_id=family_id,
                user_id=user_id,
            )
            message = "今日任务" if tasks else "今天没有任务"
        else:
            # Get active tasks
            tasks = await self._task_repo.get_active_tasks(
                family_id=family_id,
                user_id=user_id,
                limit=limit,
            )
            message = "待办任务" if tasks else "没有待办任务"

        # Format tasks for LLM
        formatted_tasks = []
        for task in tasks[:limit]:
            formatted = {
                "id": str(task.id),
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
            }
            if task.due_date:
                formatted["due_date"] = task.due_date.isoformat()
            if task.description:
                formatted["description"] = task.description[:100]  # Truncate long descriptions
            formatted_tasks.append(formatted)

        return DataLookupResult(
            success=True,
            data={
                "tasks": formatted_tasks,
                "query_type": sub_type or "active",
            },
            message=message,
            item_count=len(formatted_tasks),
        )

    async def _lookup_reminders(
        self,
        user_id: UUID,
        family_id: UUID,
        limit: int,
    ) -> DataLookupResult:
        """Look up reminders from the database."""
        reminders = await self._reminder_repo.get_user_reminders(
            user_id=user_id,
            status="pending",
        )

        formatted_reminders = []
        for reminder in reminders[:limit]:
            formatted = {
                "id": str(reminder.id),
                "title": reminder.title,
                "content": reminder.content,
                "urgency": reminder.urgency_level,
            }
            if reminder.next_send_at:
                formatted["scheduled_time"] = reminder.next_send_at.isoformat()
            formatted_reminders.append(formatted)

        message = "待处理的提醒" if formatted_reminders else "没有待处理的提醒"

        return DataLookupResult(
            success=True,
            data={"reminders": formatted_reminders},
            message=message,
            item_count=len(formatted_reminders),
        )

    async def _lookup_today_items(
        self,
        user_id: UUID,
        family_id: UUID,
        limit: int,
    ) -> DataLookupResult:
        """Look up today's schedule items."""
        today = utc_now().date()

        # Get today's tasks
        tasks = await self._task_repo.get_today_tasks(
            family_id=family_id,
            user_id=user_id,
        )

        # Get today's pending items from TodayRepository
        try:
            today_items = await self._today_repo.get_user_items(
                user_id=user_id,
                family_id=family_id,
                status="pending",
            )
        except Exception as e:
            logger.warning("Failed to get today items: %s", e)
            today_items = []

        # Format combined data
        formatted = {
            "date": today.isoformat(),
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "priority": t.priority,
                    "due_time": t.due_time.isoformat() if t.due_time else None,
                }
                for t in tasks[:limit]
            ],
            "events": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "item_type": getattr(item, "source_type", "event"),
                    "scheduled_time": item.due_datetime.isoformat() if item.due_datetime else None,
                }
                for item in today_items[:limit]
            ],
        }

        total_items = len(formatted["tasks"]) + len(formatted["events"])
        message = f"今天有 {total_items} 项安排" if total_items > 0 else "今天没有安排"

        return DataLookupResult(
            success=True,
            data=formatted,
            message=message,
            item_count=total_items,
        )

    async def _lookup_family_members(
        self,
        family_id: UUID,
        limit: int,
    ) -> DataLookupResult:
        """Look up family members."""
        members = await self._member_repo.get_family_members(
            family_id=family_id,
            limit=limit,
        )

        formatted_members = []
        for member in members:
            formatted = {
                "id": str(member.id),
                "name": member.name,
                "relation": getattr(member, "relation", None),
            }
            if hasattr(member, "nickname") and member.nickname:
                formatted["nickname"] = member.nickname
            formatted_members.append(formatted)

        message = f"家庭有 {len(formatted_members)} 位成员" if formatted_members else "没有找到家庭成员"

        return DataLookupResult(
            success=True,
            data={"members": formatted_members},
            message=message,
            item_count=len(formatted_members),
        )

    async def _lookup_schedule(
        self,
        user_id: UUID,
        family_id: UUID,
        limit: int,
    ) -> DataLookupResult:
        """Look up upcoming schedule items (CuratedEvents)."""
        from datetime import timedelta
        from ...core.utils.timezone import utc_now

        now = utc_now()
        window_end = now + timedelta(days=30)

        stmt = (
            select(CuratedEvent)
            .where(and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active == True,
                CuratedEvent.status.notin_(["cancelled"]),
                CuratedEvent.normalized_start >= now,
                CuratedEvent.normalized_start <= window_end,
            ))
            .order_by(CuratedEvent.normalized_start)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        events = list(result.scalars().all())

        formatted_events = []
        for event in events:
            formatted_events.append({
                "id": str(event.id),
                "title": event.title,
                "start_time": event.normalized_start.isoformat() if event.normalized_start else None,
                "end_time": event.normalized_end.isoformat() if event.normalized_end else None,
                "location": event.location,
                "event_type": event.event_type,
            })

        message = f"未来30天有 {len(formatted_events)} 项日程" if formatted_events else "未来30天没有日程安排"

        return DataLookupResult(
            success=True,
            data={
                "events": formatted_events,
                "period": "next_30_days",
            },
            message=message,
            item_count=len(formatted_events),
        )

    async def _lookup_trips(
        self,
        user_id: UUID,
        family_id: UUID,
        destination_filter: Optional[str],
        limit: int,
    ) -> DataLookupResult:
        """Look up trip plans from the database, optionally filtered by destination."""
        query = (
            select(TripPlan)
            .where(TripPlan.family_id == family_id)
            .where(TripPlan.status.notin_(["cancelled"]))
            .options(selectinload(TripPlan.itineraries))
            .order_by(TripPlan.start_date.desc())
            .limit(limit)
        )

        if destination_filter:
            from ...claude_agent.tools.shared.sql_utils import escape_like
            escaped = escape_like(destination_filter)
            query = query.where(TripPlan.destination.ilike(f"%{escaped}%", escape="\\"))

        result = await self.db.execute(query)
        trips = list(result.scalars().all())

        from ...modules.trip.services.trip_status import (
            compute_trip_status,
            get_status_display,
        )

        formatted_trips = []
        for trip in trips:
            effective = compute_trip_status(
                trip.status, trip.start_date, trip.end_date,
            )
            formatted = {
                "trip_id": str(trip.trip_id),
                "trip_name": trip.trip_name,
                "destination": trip.destination,
                "start_date": trip.start_date.isoformat() if trip.start_date else None,
                "end_date": trip.end_date.isoformat() if trip.end_date else None,
                "duration_days": trip.duration_days,
                "status": effective,
                "status_label": get_status_display(effective),
                "category": trip.category,
                "trip_type": trip.trip_type,
                "notes": trip.notes,
            }

            if trip.budget:
                formatted["budget"] = float(trip.budget)
            if trip.actual_expense:
                formatted["actual_expense"] = float(trip.actual_expense)

            # Include itinerary summary
            if trip.itineraries:
                itinerary_days = []
                for itin in sorted(trip.itineraries, key=lambda x: x.day_number):
                    day_info = {
                        "day_number": itin.day_number,
                        "activity_count": itin.activity_count,
                    }
                    if itin.schedule:
                        day_info["activities"] = [
                            {
                                "time": act.get("time", ""),
                                "title": act.get("title", ""),
                                "location": act.get("location", ""),
                                "activity_type": act.get("activity_type", ""),
                            }
                            for act in itin.schedule[:8]  # Limit activities per day
                        ]
                    itinerary_days.append(day_info)
                formatted["itinerary"] = itinerary_days

            formatted_trips.append(formatted)

        dest_label = f"「{destination_filter}」" if destination_filter else ""
        if formatted_trips:
            message = f"找到 {len(formatted_trips)} 个{dest_label}旅行计划"
        else:
            message = f"没有找到{dest_label}相关的旅行计划"

        return DataLookupResult(
            success=True,
            data={"trips": formatted_trips},
            message=message,
            item_count=len(formatted_trips),
        )

    def format_for_llm(self, result: DataLookupResult) -> str:
        """
        Format lookup result as a string for LLM context.

        Args:
            result: The lookup result to format

        Returns:
            Formatted string suitable for LLM prompt
        """
        if not result.success:
            return f"查询失败: {result.message}"

        lines = [result.message]

        # Format based on data type
        if "tasks" in result.data:
            tasks = result.data["tasks"]
            if tasks:
                lines.append("\n任务列表:")
                for i, task in enumerate(tasks, 1):
                    priority_marker = "!" * (3 if task.get("priority") == "high" else 1)
                    due_info = f" (截止: {task.get('due_date', '无')})" if task.get("due_date") else ""
                    lines.append(f"  {i}. {priority_marker} {task['title']}{due_info}")

        if "reminders" in result.data:
            reminders = result.data["reminders"]
            if reminders:
                lines.append("\n提醒列表:")
                for i, reminder in enumerate(reminders, 1):
                    time_info = f" ({reminder.get('scheduled_time', '')})" if reminder.get("scheduled_time") else ""
                    lines.append(f"  {i}. {reminder['title']}{time_info}")

        if "events" in result.data:
            events = result.data["events"]
            if events:
                lines.append("\n日程事件:")
                for i, event in enumerate(events, 1):
                    time_str = event.get("start_time") or event.get("scheduled_time") or ""
                    end_str = event.get("end_time", "")
                    time_info = f" ({time_str}"
                    if end_str:
                        time_info += f" ~ {end_str}"
                    time_info += ")" if time_str else ""
                    loc = event.get("location", "")
                    loc_info = f" @ {loc}" if loc else ""
                    lines.append(f"  {i}. {event['title']}{time_info}{loc_info}")

        if "members" in result.data:
            members = result.data["members"]
            if members:
                lines.append("\n家庭成员:")
                for member in members:
                    relation = f" ({member.get('relation')})" if member.get("relation") else ""
                    lines.append(f"  - {member['name']}{relation}")

        if "schedule" in result.data:
            schedule = result.data["schedule"]
            if schedule:
                lines.append("\n未来安排:")
                for item in schedule:
                    date_info = f" ({item.get('due_date', '')})" if item.get("due_date") else ""
                    lines.append(f"  - {item['title']}{date_info}")

        if "trips" in result.data:
            trips = result.data["trips"]
            if trips:
                lines.append("\n旅行计划:")
                from ...modules.trip.services.trip_status import get_status_display

                for trip in trips:
                    name = trip.get("trip_name") or trip.get("destination", "未知")
                    status_label = trip.get("status_label") or get_status_display(trip.get("status", ""))
                    lines.append(
                        f"  📍 {name} ({trip.get('destination', '')})"
                    )
                    lines.append(
                        f"     日期: {trip.get('start_date', '?')} ~ {trip.get('end_date', '?')} "
                        f"({trip.get('duration_days', '?')}天)  状态: {status_label}"
                    )
                    if trip.get("budget"):
                        expense = trip.get("actual_expense", 0)
                        lines.append(f"     预算: ¥{trip['budget']}  已花: ¥{expense}")
                    if trip.get("notes"):
                        lines.append(f"     备注: {trip['notes'][:100]}")

                    # Itinerary details
                    itinerary = trip.get("itinerary", [])
                    if itinerary:
                        lines.append("     行程安排:")
                        for day in itinerary:
                            lines.append(f"       第{day['day_number']}天:")
                            for act in day.get("activities", []):
                                time_str = act.get("time", "")
                                title = act.get("title", "")
                                loc = act.get("location", "")
                                loc_str = f" @ {loc}" if loc else ""
                                lines.append(f"         {time_str} {title}{loc_str}")

        return "\n".join(lines)
