"""
EventService - CRUD operations for user-created events.

User-created events are stored as CuratedEvent records with
source_types=["user_created"] and confidence=1.0.
"""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import local_date_range_to_utc
from ...modules.conversation.display_builder import build_display_data

from .models import CuratedEvent
from .event_schemas import (
    CreateEventRequest,
    UpdateEventRequest,
    EventResponse,
    EventListResponse,
)

logger = get_logger(__name__)

USER_CREATED_SOURCE = "user_created"


def _escape_like(value: str) -> str:
    r"""Escape SQL LIKE special characters to prevent pattern injection."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _trigger_event_curation(
    family_id: UUID,
    trigger_type: str,
    db: AsyncSession,
) -> None:
    """Trigger curation after event changes (deferred import to avoid circular deps)."""
    try:
        from .tasks import trigger_curation_if_enabled
        await trigger_curation_if_enabled(
            family_id,
            "auto_curate_on_event_change",
            trigger_type,
            db=db,
        )
    except Exception as e:
        logger.warning("Failed to trigger curation (%s) for family %s: %s", trigger_type, family_id, e)


async def _emit_event_signal(
    signal_name: str,
    event,
    family_id: UUID,
    user_id: UUID,
    source: str,
    extra_data: Optional[dict] = None,
) -> None:
    """Emit a FeedbackBus signal for event-related user actions."""
    try:
        from ...core.feedback import get_feedback_bus, FeedbackSignal

        bus = get_feedback_bus()
        signal = FeedbackSignal[signal_name]
        data = {
            "event_id": str(event.id),
            "event_type": getattr(event, "event_type", None),
            "title": getattr(event, "title", None),
        }
        if extra_data:
            data.update(extra_data)
        await bus.emit(
            signal=signal,
            data=data,
            family_id=family_id,
            user_id=user_id,
            source=source,
        )
    except Exception:
        logger.warning("FeedbackBus emit failed for %s", signal_name, exc_info=True)


DEFAULT_LIMIT = 100
DEFAULT_OFFSET = 0


class EventService:
    """
    事件 CRUD 服务

    职责：
    1. 创建用户事件 (写入 CuratedEvent, source_types=["user_created"])
    2. 更新事件 (仅允许 user_created 或 confirmed 状态)
    3. 删除事件 (soft delete: status="cancelled")
    4. 查询单个事件 / 列表事件
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(
        self,
        user_id: UUID,
        family_id: UUID,
        request: CreateEventRequest,
    ) -> CuratedEvent:
        """
        创建用户事件。

        写入 CuratedEvent 表，标记 source_types=["user_created"], confidence=1.0。
        """
        trip_id = None
        if request.trip_id:
            try:
                trip_id = UUID(request.trip_id)
            except ValueError:
                logger.warning("Invalid trip_id format: %s", request.trip_id)

        event = CuratedEvent(
            user_id=user_id,
            family_id=family_id,
            trip_id=trip_id,
            original_event_ids=[],
            source_types=[USER_CREATED_SOURCE],
            title=request.title,
            normalized_start=request.start_time,
            normalized_end=request.end_time,
            location=request.location,
            event_type=request.event_type,
            timeline_items=[],
            confidence=1.0,
            status="confirmed",
            priority=request.priority,
            notes=request.notes,
            tags=request.tags or [],
        )

        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)

        logger.info("Created user event: %s - %s", event.id, event.title)

        await _trigger_event_curation(family_id, "event_created", self.db)

        return event

    async def update_event(
        self,
        event_id: UUID,
        user_id: UUID,
        family_id: UUID,
        request: UpdateEventRequest,
    ) -> Optional[CuratedEvent]:
        """
        更新事件。仅允许 user_created 或 confirmed 状态的事件。

        Returns None if event not found or not editable.
        """
        event = await self._get_editable_event(event_id, family_id)
        if not event:
            return None

        # Ownership check: user_created events can only be edited by their creator
        if USER_CREATED_SOURCE in (event.source_types or []) and event.user_id != user_id:
            logger.warning("User %s attempted to update event %s owned by %s", user_id, event_id, event.user_id)
            return None

        updates = request.model_dump(exclude_unset=True)

        # Explicit allowlist of fields that can be updated via API
        _ALLOWED_FIELDS: dict = {
            "title": "title",
            "start_time": "normalized_start",
            "end_time": "normalized_end",
            "event_type": "event_type",
            "location": "location",
            "priority": "priority",
            "notes": "notes",
            "tags": "tags",
            "status": "status",
        }

        for field, value in updates.items():
            db_field = _ALLOWED_FIELDS.get(field)
            if db_field is not None:
                setattr(event, db_field, value)

        await self.db.commit()
        await self.db.refresh(event)

        logger.info("Updated event: %s - %s", event.id, event.title)

        await _trigger_event_curation(family_id, "event_updated", self.db)

        return event

    async def delete_event(
        self,
        event_id: UUID,
        user_id: UUID,
        family_id: UUID,
    ) -> bool:
        """
        软删除事件 (status="cancelled")。

        Returns False if event not found.
        """
        event = await self._get_event(event_id, family_id)
        if not event:
            return False

        # Ownership check: user_created events can only be deleted by their creator
        if USER_CREATED_SOURCE in (event.source_types or []) and event.user_id != user_id:
            logger.warning("User %s attempted to delete event %s owned by %s", user_id, event_id, event.user_id)
            return False

        event.status = "cancelled"
        event.is_active = False

        # If this event belongs to a travel plan, also cancel sibling events
        # (e.g. "Day 2 · 杭州家庭三日游" when "Day 1" is deleted).
        if "trip_plan" in (event.source_types or []):
            from sqlalchemy import update, and_, or_
            conditions = [
                CuratedEvent.family_id == family_id,
                CuratedEvent.id != event_id,
                CuratedEvent.is_active.is_(True),
            ]
            # Match siblings by trip_id (primary) or original_event_ids (fallback)
            match_clauses = []
            if event.trip_id:
                match_clauses.append(CuratedEvent.trip_id == event.trip_id)
            if event.original_event_ids:
                for eid in event.original_event_ids:
                    match_clauses.append(
                        CuratedEvent.original_event_ids.contains([eid])
                    )
            if match_clauses:
                conditions.append(or_(*match_clauses))
                await self.db.execute(
                    update(CuratedEvent)
                    .where(and_(*conditions))
                    .values(is_active=False, status="cancelled")
                )

        await self.db.commit()

        logger.info("Soft-deleted event: %s - %s", event.id, event.title)

        await _trigger_event_curation(family_id, "event_deleted", self.db)
        await _emit_event_signal(
            "EVENT_CANCELLED",
            event=event,
            family_id=family_id,
            user_id=user_id,
            source="delete_event",
        )

        # Cascade analysis: check impact of cancellation on same-day events
        await self._run_cascade_analysis(
            event, family_id, "cancelled", {},
        )

        return True

    async def cancel_by_title(
        self,
        family_id: UUID,
        title: str,
        event_date: Optional[date] = None,
        reason: str = "用户取消",
    ) -> List[CuratedEvent]:
        """
        按标题模糊匹配取消事件。

        Returns cancelled events list (empty if none found).
        """
        safe_title = _escape_like(title)
        conditions = [
            CuratedEvent.family_id == family_id,
            CuratedEvent.is_active.is_(True),
            CuratedEvent.status.notin_(["cancelled", "completed"]),
            or_(
                CuratedEvent.title.ilike(f"%{safe_title}%", escape="\\"),
                CuratedEvent.title.ilike(f"{safe_title}%", escape="\\"),
            ),
        ]

        if event_date:
            conditions.append(cast(CuratedEvent.normalized_start, Date) == event_date)

        stmt = (
            select(CuratedEvent)
            .where(and_(*conditions))
            .order_by(CuratedEvent.normalized_start)
        )

        result = await self.db.execute(stmt)
        events = list(result.scalars().all())

        for event in events:
            event.status = "cancelled"
            event.is_active = False

        if events:
            await self.db.commit()
            logger.info(
                "Cancelled %d events matching '%s' for family %s",
                len(events), title, family_id,
            )
            await _trigger_event_curation(family_id, "event_cancelled", self.db)
            for ev in events:
                if ev.user_id:
                    await _emit_event_signal(
                        "EVENT_CANCELLED",
                        event=ev,
                        family_id=family_id,
                        user_id=ev.user_id,
                        source="cancel_by_title",
                    )

        return events

    async def get_event(
        self,
        event_id: UUID,
        family_id: UUID,
    ) -> Optional[CuratedEvent]:
        """获取单个事件详情。"""
        return await self._get_event(event_id, family_id)

    async def list_events(
        self,
        family_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = DEFAULT_OFFSET,
    ) -> EventListResponse:
        """
        列出事件列表，支持日期范围、类型、状态过滤和分页。
        """
        conditions = [
            CuratedEvent.family_id == family_id,
            CuratedEvent.is_active.is_(True),
            CuratedEvent.status != "cancelled",
        ]

        if start_date and end_date:
            start_utc, end_utc = local_date_range_to_utc(start_date, end_date)
            conditions.append(CuratedEvent.normalized_start >= start_utc)
            conditions.append(CuratedEvent.normalized_start <= end_utc)
        elif start_date:
            start_utc, _ = local_date_range_to_utc(start_date, start_date)
            conditions.append(CuratedEvent.normalized_start >= start_utc)
        elif end_date:
            _, end_utc = local_date_range_to_utc(end_date, end_date)
            conditions.append(CuratedEvent.normalized_start <= end_utc)

        if event_type:
            conditions.append(CuratedEvent.event_type == event_type)

        if status:
            conditions.append(CuratedEvent.status == status)

        where_clause = and_(*conditions)

        # Count total
        count_stmt = select(func.count()).select_from(CuratedEvent).where(where_clause)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get paginated events
        stmt = (
            select(CuratedEvent)
            .where(where_clause)
            .order_by(CuratedEvent.normalized_start)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        db_events = list(result.scalars().all())

        events = [self.to_response(e) for e in db_events]

        return EventListResponse(
            events=events,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(events)) < total,
        )

    def to_response(self, event: CuratedEvent) -> EventResponse:
        """Convert CuratedEvent model to EventResponse schema."""
        return EventResponse(
            id=str(event.id),
            title=event.title,
            start_time=event.normalized_start,
            end_time=event.normalized_end,
            event_type=event.event_type,
            location=event.location,
            status=event.status,
            priority=event.priority,
            notes=event.notes,
            tags=event.tags or [],
            source_types=event.source_types or [],
            confidence=event.confidence,
            trip_id=str(event.trip_id) if event.trip_id else None,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )

    async def reschedule_event(
        self,
        event_id: UUID,
        family_id: UUID,
        new_start: datetime,
        new_end: Optional[datetime] = None,
        trip_id: Optional[UUID] = None,
        trip_day_label: Optional[str] = None,
    ) -> dict:
        """
        Reschedule a curated event and shift trip siblings by the same offset.

        This is the sole write path for rescheduling, enforcing the unique writer
        principle.  The Tool Gateway delegates here instead of writing to the
        curated_events table directly.

        Returns a result dict compatible with the Tool Gateway response format.
        """
        stmt = select(CuratedEvent).where(
            and_(
                CuratedEvent.id == event_id,
                CuratedEvent.family_id == family_id,
            )
        )
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()

        # Fallback: if the original event was replaced by re-curation, try to
        # find the equivalent event by trip_id + trip_day_label.
        if not event and trip_id and trip_day_label:
            fallback_conditions = [
                CuratedEvent.trip_id == trip_id,
                CuratedEvent.trip_day_label == trip_day_label,
                CuratedEvent.is_active.is_(True),
            ]
            fallback_conditions.append(CuratedEvent.family_id == family_id)
            fallback_stmt = (
                select(CuratedEvent)
                .where(and_(*fallback_conditions))
                .limit(1)
            )
            fallback_result = await self.db.execute(fallback_stmt)
            event = fallback_result.scalar_one_or_none()

        if not event:
            return {
                "success": False,
                "error": f"Event {event_id} not found (may have been replaced by re-curation)",
            }

        old_start = event.normalized_start
        event.normalized_start = new_start
        if new_end:
            event.normalized_end = new_end

        # Shift all same-trip sibling events by the same offset so the whole
        # trip moves consistently.
        offset = new_start - old_start if old_start else None
        if offset and event.trip_id:
            sibling_stmt = select(CuratedEvent).where(
                and_(
                    CuratedEvent.trip_id == event.trip_id,
                    CuratedEvent.id != event.id,
                    CuratedEvent.is_active.is_(True),
                )
            )
            sibling_result = await self.db.execute(sibling_stmt)
            for sibling in sibling_result.scalars():
                if sibling.normalized_start:
                    sibling.normalized_start = sibling.normalized_start + offset
                if sibling.normalized_end:
                    sibling.normalized_end = sibling.normalized_end + offset

        await self.db.commit()

        logger.info("Rescheduled event %s (%s) from %s to %s",
                     event_id, event.title, old_start, new_start)

        if event.user_id:
            await _emit_event_signal(
                "EVENT_RESCHEDULED",
                event=event,
                family_id=family_id,
                user_id=event.user_id,
                source="reschedule_event",
                extra_data={
                    "old_start": old_start.isoformat() if old_start else None,
                    "new_start": new_start.isoformat(),
                },
            )

        # Cascade analysis: check impact on same-day events
        await self._run_cascade_analysis(
            event, family_id, "time_changed",
            {"old_start": old_start.isoformat() if old_start else None,
             "new_start": new_start.isoformat()},
        )

        return {
            "success": True,
            "event_id": str(event_id),
            "title": event.title,
            "old_start": old_start.isoformat() if old_start else None,
            "new_start": new_start.isoformat(),
            "new_end": new_end.isoformat() if new_end else None,
            "status": "rescheduled",
            "message": f"Event '{event.title}' rescheduled successfully.",
        }

    async def _run_cascade_analysis(
        self,
        event: CuratedEvent,
        family_id: UUID,
        change_type: str,
        change_detail: dict,
    ) -> None:
        """Run cascade analysis on same-day events after a change."""
        try:
            from .services.orchestrator import SecretaryOrchestrator
            from .services.priority_engine import HybridPriorityEngine

            if not event.normalized_start:
                return

            event_date = event.normalized_start.date()
            stmt = select(CuratedEvent).where(
                and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.id != event.id,
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.status != "cancelled",
                    cast(CuratedEvent.normalized_start, Date) == event_date,
                )
            )
            result = await self.db.execute(stmt)
            affected_events = list(result.scalars().all())

            if not affected_events:
                return

            priority_engine = HybridPriorityEngine(calibration_enabled=False)
            orchestrator = SecretaryOrchestrator(self.db, priority_engine)
            cascade = await orchestrator.analyze_cascade(
                changed_event=event,
                change_type=change_type,
                change_detail=change_detail,
                affected_events=affected_events,
            )
            if cascade.impacts:
                logger.info(
                    "Cascade analysis for event %s (%s): %s",
                    event.id, change_type, cascade.summary,
                )
                await self._apply_cascade_results(
                    cascade, event, family_id,
                )
        except Exception:
            logger.warning(
                "Cascade analysis failed for event %s", event.id,
                exc_info=True,
            )

    async def _apply_cascade_results(
        self,
        cascade,
        source_event: CuratedEvent,
        family_id: UUID,
    ) -> None:
        """Create PendingActions for user-decision impacts and push a notification."""
        if not cascade.impacts:
            return

        user_id = source_event.user_id
        if not user_id:
            return

        # Create PendingActions for impacts that require user decisions
        try:
            from ..conversation.pending_action import ActionType
            from ..conversation.pending_action_service import PendingActionService

            action_service = PendingActionService(self.db)
            for impact in cascade.impacts:
                if not impact.requires_user_decision:
                    continue
                await action_service.create(
                    user_id=user_id,
                    family_id=family_id,
                    action_type=ActionType.RESCHEDULE_EVENT.value,
                    payload={
                        "event_id": str(impact.event_id),
                        "cascade_source_event_id": str(source_event.id),
                        "impact_type": impact.impact_type,
                    },
                    display_data=build_display_data(
                        "reschedule_event",
                        {
                            "event_title": impact.event_title,
                            "impact_type": impact.impact_type,
                            "detail": impact.detail,
                        },
                        description=f"日程级联影响 - {impact.event_title}",
                    ),
                    ttl_minutes=60,
                )
        except Exception:
            logger.warning(
                "Failed to create PendingActions for cascade on event %s",
                source_event.id,
                exc_info=True,
            )

        # Push cascade summary via WebSocket
        try:
            from ...core.pubsub.redis_pubsub import get_pubsub_manager
            from ...core.pubsub.types import PubSubMessage, MessageType

            manager = get_pubsub_manager()
            await manager.publish(
                user_id=str(user_id),
                message=PubSubMessage(
                    user_id=str(user_id),
                    message_type=MessageType.SIDEKICK_INSIGHT,
                    payload={
                        "type": "cascade_alert",
                        "source_event_id": str(source_event.id),
                        "source_event_title": source_event.title,
                        "summary": cascade.summary,
                        "impact_count": len(cascade.impacts),
                        "requires_user_decision": cascade.requires_user_decision,
                    },
                    trace_id=f"cascade_{source_event.id}",
                ),
            )
        except Exception:
            logger.warning(
                "Failed to push cascade notification for event %s",
                source_event.id,
                exc_info=True,
            )

    async def _get_event(
        self,
        event_id: UUID,
        family_id: UUID,
    ) -> Optional[CuratedEvent]:
        """获取事件，排除已取消和非活跃的。"""
        stmt = select(CuratedEvent).where(
            and_(
                CuratedEvent.id == event_id,
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_editable_event(
        self,
        event_id: UUID,
        family_id: UUID,
    ) -> Optional[CuratedEvent]:
        """
        获取可编辑的事件。

        仅 user_created 事件或 confirmed 状态的事件可编辑。
        """
        event = await self._get_event(event_id, family_id)
        if not event:
            return None

        is_user_created = USER_CREATED_SOURCE in (event.source_types or [])
        is_confirmed = event.status == "confirmed"

        if not (is_user_created or is_confirmed):
            logger.warning(
                "Event %s not editable: source_types=%s, status=%s",
                event_id, event.source_types, event.status,
            )
            return None

        return event
