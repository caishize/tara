"""Event domain tool executor — 6 tools for CuratedEvent CRUD + search + cascade."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from ....config.logging import get_logger
from ..shared.errors import ToolErrorType, tool_error
from ..shared.progress import ProgressCallback
from ..shared.sql_utils import escape_like as _escape_like
from .base import BaseToolExecutor

logger = get_logger(__name__)


class EventToolExecutor(BaseToolExecutor):
    """Handles create/update/cancel/delete/search for CuratedEvent."""

    async def create_event(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.curation.event_service import EventService
        from ....modules.curation.event_schemas import CreateEventRequest

        title = args.get("title")
        start_time_str = args.get("start_time")
        if not title or not start_time_str:
            return tool_error(
                ToolErrorType.VALIDATION,
                "缺少必要参数: title 和 start_time",
                hint="请提供事件标题和开始时间",
            )

        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except ValueError:
            return tool_error(
                ToolErrorType.VALIDATION,
                f"无效的时间格式: {start_time_str}",
                hint="请使用 ISO 8601 格式: YYYY-MM-DDTHH:MM:SS",
            )

        end_time = None
        end_time_str = args.get("end_time")
        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        request = CreateEventRequest(
            title=title,
            start_time=start_time,
            end_time=end_time,
            event_type=args.get("event_type", "other"),
            location=args.get("location"),
            priority=args.get("priority", "normal"),
            notes=args.get("notes"),
            tags=args.get("tags", []),
        )

        service = EventService(self.db)
        event = await service.create_event(
            user_id=user_id,
            family_id=family_id,
            request=request,
        )

        return {
            "success": True,
            "event_id": str(event.id),
            "title": event.title,
            "start_time": event.normalized_start.isoformat(),
            "end_time": event.normalized_end.isoformat() if event.normalized_end else None,
            "event_type": event.event_type,
            "location": event.location,
            "message": f"已创建日程: {event.title}",
        }

    async def update_event(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.curation.event_service import EventService
        from ....modules.curation.event_schemas import UpdateEventRequest

        event_id_str = args.get("event_id")
        if not event_id_str:
            return tool_error(ToolErrorType.VALIDATION, "缺少必要参数: event_id", hint="请提供要修改的事件ID")

        try:
            event_id = UUID(event_id_str)
        except ValueError:
            return tool_error(ToolErrorType.VALIDATION, f"无效的事件ID: {event_id_str}")

        updates_raw = args.get("updates", {})
        update_data: Dict[str, Any] = {}
        for key, value in updates_raw.items():
            if key in ("start_time", "end_time") and isinstance(value, str):
                try:
                    update_data[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    return tool_error(ToolErrorType.VALIDATION, f"无效的时间格式: {value}")
            else:
                update_data[key] = value

        request = UpdateEventRequest(**update_data)
        service = EventService(self.db)
        event = await service.update_event(
            event_id=event_id,
            user_id=user_id,
            family_id=family_id,
            request=request,
        )

        if not event:
            return tool_error(
                ToolErrorType.NOT_FOUND,
                "事件未找到或不可编辑",
                hint="仅用户创建的或已确认的事件可修改",
            )

        return {
            "success": True,
            "event_id": str(event.id),
            "title": event.title,
            "message": f"已更新日程: {event.title}",
        }

    async def cancel_schedule(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.curation.event_service import EventService

        event_title = args.get("event_title", "")
        event_date_str = args.get("event_date")
        reason = args.get("reason", "用户取消")

        if not event_title:
            return tool_error(ToolErrorType.VALIDATION, "请提供要取消的日程名称")

        event_date = None
        if event_date_str:
            try:
                event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.warning("Invalid date format: %s", event_date_str)

        try:
            service = EventService(self.db)
            cancelled_events = await service.cancel_by_title(
                family_id=family_id,
                title=event_title,
                event_date=event_date,
                reason=reason,
            )

            if not cancelled_events:
                return tool_error(ToolErrorType.NOT_FOUND, f"未找到匹配「{event_title}」的日程")

            cancelled_titles = [e.title for e in cancelled_events]

            if len(cancelled_titles) == 1:
                message = f"已取消日程「{cancelled_titles[0]}」"
            else:
                titles_str = "、".join(cancelled_titles[:3])
                if len(cancelled_titles) > 3:
                    titles_str += f" 等{len(cancelled_titles)}个日程"
                message = f"已取消: {titles_str}"

            return {
                "success": True,
                "cancelled_count": len(cancelled_titles),
                "cancelled_titles": cancelled_titles,
                "message": message,
                "secretary_hint": "日程已取消，建议您查看其他相关安排是否需要调整",
                "should_recurate": True,
            }

        except Exception as e:
            logger.error("Cancel schedule failed: %s", e)
            return tool_error(ToolErrorType.INTERNAL, f"取消日程失败: {str(e)}")

    async def delete_event(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.curation.event_service import EventService

        event_id_str = args.get("event_id")
        if not event_id_str:
            return tool_error(ToolErrorType.VALIDATION, "缺少必要参数: event_id")

        try:
            event_id = UUID(event_id_str)
        except ValueError:
            return tool_error(ToolErrorType.VALIDATION, f"无效的事件ID: {event_id_str}")

        service = EventService(self.db)
        deleted = await service.delete_event(
            event_id=event_id,
            user_id=user_id,
            family_id=family_id,
        )

        if not deleted:
            return tool_error(ToolErrorType.NOT_FOUND, "事件未找到")

        return {
            "success": True,
            "event_id": event_id_str,
            "message": "已删除日程",
        }

    async def search_events(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Search curated events by keyword, date range, or type."""
        from sqlalchemy import select, and_, or_
        from ....modules.curation.models import CuratedEvent

        query = args.get("query", "")
        event_type = args.get("event_type")
        start_date_str = args.get("start_date")
        end_date_str = args.get("end_date")
        limit = min(args.get("limit", 10), 50)

        try:
            conditions: List[Any] = [
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active == True,
            ]

            if query:
                safe_query = _escape_like(query)
                conditions.append(
                    or_(
                        CuratedEvent.title.ilike(f"%{safe_query}%", escape="\\"),
                        CuratedEvent.location.ilike(f"%{safe_query}%", escape="\\"),
                        CuratedEvent.notes.ilike(f"%{safe_query}%", escape="\\"),
                    )
                )

            if event_type:
                conditions.append(CuratedEvent.event_type == event_type)

            if start_date_str:
                try:
                    start_dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                    conditions.append(CuratedEvent.normalized_start >= start_dt)
                except ValueError:
                    pass

            if end_date_str:
                try:
                    end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    conditions.append(CuratedEvent.normalized_start <= end_dt)
                except ValueError:
                    pass

            stmt = (
                select(CuratedEvent)
                .where(and_(*conditions))
                .order_by(CuratedEvent.normalized_start)
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            events = list(result.scalars().all())

            return {
                "success": True,
                "events": [
                    {
                        "id": str(e.id),
                        "title": e.title,
                        "event_type": e.event_type,
                        "start_time": e.normalized_start.isoformat() if e.normalized_start else None,
                        "end_time": e.normalized_end.isoformat() if e.normalized_end else None,
                        "location": e.location,
                        "status": e.status,
                        "priority": e.priority,
                    }
                    for e in events
                ],
                "count": len(events),
                "message": f"找到 {len(events)} 个匹配的日程",
            }

        except Exception as e:
            logger.error("Search events failed: %s", e)
            return {"success": False, "message": "搜索日程失败，请稍后重试"}

    async def analyze_event_cascade(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Analyze cascade impact of an event change (delay, cancel, etc.)."""
        from sqlalchemy import select, and_

        from ....modules.curation.models import CuratedEvent
        from ....modules.curation.services.orchestrator import SecretaryOrchestrator
        from ....modules.curation.services.priority_engine import HybridPriorityEngine

        event_id_str = args.get("event_id")
        if not event_id_str:
            return tool_error(ToolErrorType.VALIDATION, "缺少必要参数: event_id")

        try:
            event_id = UUID(event_id_str)
        except ValueError:
            return tool_error(ToolErrorType.VALIDATION, f"无效的事件ID: {event_id_str}")

        change_type = args.get("change_type", "delayed")
        change_detail = args.get("change_detail", {})

        # Load the changed event
        stmt = select(CuratedEvent).where(
            and_(
                CuratedEvent.id == event_id,
                CuratedEvent.family_id == family_id,
            ),
        )
        result = await self.db.execute(stmt)
        changed_event = result.scalar_one_or_none()

        if changed_event is None:
            return tool_error(ToolErrorType.NOT_FOUND, "事件未找到")

        # Find affected same-day events
        affected_events: Sequence[CuratedEvent] = []
        if changed_event.normalized_start:
            target_date = changed_event.normalized_start.date()
            from datetime import time as dt_time

            day_start = datetime.combine(target_date, dt_time.min)
            day_end = datetime.combine(target_date, dt_time.max)

            affected_stmt = (
                select(CuratedEvent)
                .where(
                    and_(
                        CuratedEvent.family_id == family_id,
                        CuratedEvent.id != event_id,
                        CuratedEvent.normalized_start >= day_start,
                        CuratedEvent.normalized_start <= day_end,
                        CuratedEvent.status != "cancelled",
                    ),
                )
                .order_by(CuratedEvent.normalized_start)
            )
            affected_result = await self.db.execute(affected_stmt)
            affected_events = list(affected_result.scalars().all())

        # Run cascade analysis
        priority_engine = HybridPriorityEngine(self.db)
        orchestrator = SecretaryOrchestrator(self.db, priority_engine)
        cascade = await orchestrator.analyze_cascade(
            changed_event=changed_event,
            change_type=change_type,
            change_detail=change_detail,
            affected_events=affected_events,
        )

        return {
            "success": True,
            "changed_event_id": str(cascade.changed_event_id),
            "change_type": cascade.change_type,
            "summary": cascade.summary,
            "requires_user_decision": cascade.requires_user_decision,
            "impacts": [
                {
                    "event_id": str(impact.event_id),
                    "event_title": impact.event_title,
                    "impact_type": impact.impact_type,
                    "detail": impact.detail,
                    "requires_user_decision": impact.requires_user_decision,
                }
                for impact in cascade.impacts
            ],
            "impact_count": len(cascade.impacts),
            "message": cascade.summary,
        }
