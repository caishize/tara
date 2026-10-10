"""Kanban view service — semantic grouping of future events.

Extracted from secretary/services/event_context_service.py (get_kanban_view).
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import select, and_, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ....config.logging import get_logger
from ....config.settings import settings
from ....core.utils.timezone import utc_now, local_today, local_date_range_to_utc
from ...curation.models import CuratedEvent, EventAssociation
from ...curation.services.association_text import (
    build_person_context_map,
    present_association_copy,
)
from ...insight.models import Insight
from ...insight.insight_query_service import InsightQueryService
from ..kanban_schemas import (
    KanbanEvent,
    KanbanInsight,
    KanbanResponse,
    InsightFeedItem,
    InsightFeedResponse,
    InsightFeedGroupedResponse,
    InsightGroup,
    InsightRelatedEvent,
    InsightRelatedMember,
    InsightRelatedTrip,
)
from ._event_converter import to_kanban_event, get_user_timezone

logger = get_logger(__name__)


def _low_importance_event_types() -> set[str]:
    return {
        str(event_type).strip().lower()
        for event_type in (settings.curation_low_importance_event_types or [])
        if str(event_type).strip()
    }


_ACTION_OPTION_LABELS: dict[str, str] = {
    "send_message": "发送消息",
    "schedule_meeting": "安排见面",
    "set_reminder": "设置提醒",
    "ignore": "忽略",
    "view_details": "查看详情",
    "suggest_gift": "推荐礼物",
    "schedule_meal": "约一顿饭",
    "mark_done": "已完成",
    "complete_plan": "完成计划",
    "still_planning": "继续计划",
    "cancel_plan": "取消计划",
    "plan_week": "规划本周",
    "view_calendar": "查看日历",
    "view_tasks": "查看任务",
    "plan_next_week": "规划下周",
    "plan_holiday": "安排准备",
    "recommend_gift": "推荐礼物",
    "plan_celebration": "安排庆祝",
}

_INSIGHT_TYPE_LABELS: dict[str, str] = {
    "relationship_maintenance": "关系维护",
    "event_preparation": "事件准备",
    "reminder": "日常提醒",
    "observation": "动态观察",
    "correlation": "关联发现",
    "suggestion": "建议",
    "followup": "跟进",
    "weekly_review": "周回顾",
    "daily_briefing": "日报",
    "proactive": "主动发现",
}

_URGENCY_LABELS: dict[str, str] = {
    "critical": "紧急",
    "high": "高优先",
    "normal": "日常",
    "low": "低优先",
}


_GENERIC_CALENDAR_DATE_TYPES = frozenset({
    "holiday",
    "holiday_legal",
    "holiday_lunar",
    "holiday_solar_term",
    "solar_term",
})


class KanbanService:
    """Provides the semantic kanban view over curated events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _extract_matching_event_types(value: Any, candidates: set[str]) -> set[str]:
        """Recursively extract event-type-like values from structured payloads."""
        matches: set[str] = set()

        def _walk(node: Any) -> None:
            if isinstance(node, str):
                normalized = node.strip().lower()
                if normalized in candidates:
                    matches.add(normalized)
                return
            if isinstance(node, list):
                for item in node:
                    _walk(item)
                return
            if isinstance(node, dict):
                for item in node.values():
                    _walk(item)

        _walk(value)
        return matches

    async def _load_user_low_importance_preferences(
        self,
        *,
        family_id: UUID,
        user_id: UUID,
        low_importance_types: set[str],
    ) -> set[str]:
        """Infer which low-importance calendar types this user actually cares about.

        Uses structured behavior signals:
        - user/family-created ImportantDate records (non-system)
        - confirmed date associations
        - explicit preference memories with matching event-type values
        """
        if not low_importance_types:
            return set()

        from ...date_manager.models import ImportantDate
        from ...memory.models import ConversationMemory, MemoryType, MemoryStatus

        preferred_types: set[str] = set()

        custom_date_stmt = (
            select(ImportantDate.date_type)
            .where(and_(
                ImportantDate.family_id == family_id,
                ImportantDate.date_type.in_(list(low_importance_types)),
            ))
            .limit(200)
        )
        custom_date_result = await self.session.execute(custom_date_stmt)
        preferred_types.update(
            str(date_type).strip().lower()
            for date_type in custom_date_result.scalars().all()
            if date_type
        )

        confirmed_assoc_stmt = (
            select(ImportantDate.date_type)
            .join(
                EventAssociation,
                and_(
                    cast(ImportantDate.id, String)
                    == EventAssociation.target_id,
                    EventAssociation.family_id == family_id,
                    EventAssociation.target_type == "date",
                    EventAssociation.is_confirmed.is_(True),
                ),
            )
            .where(ImportantDate.date_type.in_(list(low_importance_types)))
            .limit(200)
        )
        confirmed_assoc_result = await self.session.execute(confirmed_assoc_stmt)
        preferred_types.update(
            str(date_type).strip().lower()
            for date_type in confirmed_assoc_result.scalars().all()
            if date_type
        )

        pref_memory_stmt = (
            select(ConversationMemory.entities)
            .where(and_(
                ConversationMemory.user_id == user_id,
                ConversationMemory.family_id == family_id,
                ConversationMemory.status == MemoryStatus.ACTIVE.value,
                ConversationMemory.memory_type == MemoryType.PREFERENCE.value,
            ))
            .order_by(ConversationMemory.updated_at.desc())
            .limit(100)
        )
        pref_memory_result = await self.session.execute(pref_memory_stmt)
        for entities in pref_memory_result.scalars().all():
            preferred_types.update(
                self._extract_matching_event_types(entities, low_importance_types)
            )

        return preferred_types

    @staticmethod
    def _should_surface_low_priority_event(
        event: CuratedEvent,
        *,
        preferred_low_types: set[str],
        low_importance_types: set[str],
        has_pending_prep: bool,
        has_open_association: bool,
    ) -> bool:
        """Decide whether a low-priority event should still be shown."""
        normalized_event_type = str(event.event_type or "").strip().lower()
        if normalized_event_type not in low_importance_types:
            return False
        if normalized_event_type in preferred_low_types:
            return True
        if has_pending_prep or has_open_association:
            return True
        return False

    @staticmethod
    def _safe_uuid(value: object) -> Optional[UUID]:
        if value is None:
            return None
        try:
            return UUID(str(value))
        except Exception:
            return None

    async def _load_open_association_date_meta(
        self,
        events: List[CuratedEvent],
    ) -> dict[str, dict[str, object]]:
        """Load date metadata for open date associations used in quality gating."""
        from ...date_manager.models import ImportantDate

        date_target_ids: set[UUID] = set()
        for event in events:
            for assoc in (event.associations or []):
                if assoc.is_dismissed or assoc.is_confirmed:
                    continue
                if assoc.target_type != "date":
                    continue
                parsed = self._safe_uuid(assoc.target_id)
                if parsed is not None:
                    date_target_ids.add(parsed)

        if not date_target_ids:
            return {}

        stmt = select(
            ImportantDate.id,
            ImportantDate.family_id,
            ImportantDate.date_type,
            ImportantDate.importance_level,
            ImportantDate.source,
        ).where(ImportantDate.id.in_(list(date_target_ids)))
        result = await self.session.execute(stmt)

        meta: dict[str, dict[str, object]] = {}
        for row in result:
            meta[str(row.id)] = {
                "family_id": row.family_id,
                "date_type": str(row.date_type or "").strip().lower(),
                "importance_level": int(row.importance_level or 0),
                "source": str(row.source or "").strip().lower(),
            }
        return meta

    @classmethod
    def _is_actionable_date_association(
        cls,
        *,
        date_meta: Optional[dict[str, object]],
        family_id: UUID,
    ) -> bool:
        """Determine whether a date-target association is genuinely actionable."""
        if not date_meta:
            return False

        date_type = str(date_meta.get("date_type") or "").strip().lower()
        if not date_type:
            return False

        if date_type not in _GENERIC_CALENDAR_DATE_TYPES:
            return True

        same_family = str(date_meta.get("family_id")) == str(family_id)
        importance = int(date_meta.get("importance_level") or 0)
        # Generic holidays/solar terms are only actionable when user/family has
        # explicitly elevated them with high importance.
        return same_family and importance >= 8

    def _filter_actionable_associations(
        self,
        *,
        source_event: CuratedEvent,
        associations: List[EventAssociation],
        family_id: UUID,
        date_meta_by_target_id: dict[str, dict[str, object]],
    ) -> List[EventAssociation]:
        """Keep only associations that provide concrete user value."""
        actionable: List[EventAssociation] = []
        source_is_holiday_like = self._is_holiday_like_event_type(source_event.event_type)

        for assoc in associations:
            if assoc.target_type != "date":
                if self._is_low_signal_association(
                    source_event=source_event,
                    association=assoc,
                ):
                    continue
                actionable.append(assoc)
                continue

            target_meta = date_meta_by_target_id.get(str(assoc.target_id))
            if self._is_actionable_date_association(
                date_meta=target_meta,
                family_id=family_id,
            ):
                actionable.append(assoc)
                continue

            # Avoid "common sense" reminder chains like holiday -> nearby holiday.
            if source_is_holiday_like:
                continue

            # For non-holiday source events, only keep strong date links.
            if assoc.priority == "strongly_recommend":
                actionable.append(assoc)

        return actionable

    @classmethod
    def _is_low_signal_association(
        cls,
        *,
        source_event: CuratedEvent,
        association: EventAssociation,
    ) -> bool:
        """Filter structurally weak links that rarely translate to clear actions."""
        target_type = str(association.target_type or "").strip().lower()
        assoc_type = str(association.association_type or "").strip().lower()
        priority = str(association.priority or "").strip().lower()

        if target_type in {"person", "memory", "place"}:
            return False

        source_is_holiday_like = cls._is_holiday_like_event_type(source_event.event_type)
        if assoc_type == "temporal" and target_type in {"task", "date"}:
            if source_is_holiday_like:
                return True
            return priority != "strongly_recommend"

        return False

    async def get_kanban_view(
        self,
        family_id: UUID,
        user_id: UUID,
        limit: int = 100,
    ) -> KanbanResponse:
        """Semantic grouping of future events into kanban buckets."""
        user_tz = await get_user_timezone(self.session, user_id)
        now = utc_now()
        today = local_today(user_tz)

        week_end = today + timedelta(days=7)
        month_end = today + timedelta(days=30)

        today_start_utc, week_end_utc = local_date_range_to_utc(today, week_end, user_tz)
        _, month_end_utc = local_date_range_to_utc(today, month_end, user_tz)

        # Fetch all future active events
        stmt = (
            select(CuratedEvent)
            .options(selectinload(CuratedEvent.preparation_item_rows))
            .options(selectinload(CuratedEvent.associations))
            .where(and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
                or_(
                    CuratedEvent.normalized_start >= today_start_utc,
                    and_(
                        CuratedEvent.event_type.in_(["travel", "business_trip"]),
                        CuratedEvent.trip_id.is_not(None),
                    ),
                ),
            ))
            .order_by(CuratedEvent.normalized_start)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()

        # Load referenced travel plans for canonical dates
        trip_ids = {
            ev.trip_id for ev in events
            if ev.trip_id and ev.event_type in ("travel", "business_trip")
        }
        plans_by_id: dict[UUID, object] = {}
        if trip_ids:
            from ...trip.models.trip_plan import TripPlan

            plan_stmt = select(TripPlan).where(and_(
                TripPlan.trip_id.in_(trip_ids),
                TripPlan.status != "cancelled",
            ))
            plan_result = await self.session.execute(plan_stmt)
            plans_by_id = {
                plan.trip_id: plan
                for plan in plan_result.scalars().all()
            }

        low_importance_types = _low_importance_event_types()
        preferred_low_types = await self._load_user_low_importance_preferences(
            family_id=family_id,
            user_id=user_id,
            low_importance_types=low_importance_types,
        )
        date_meta_by_target_id = await self._load_open_association_date_meta(events)

        this_week: List[KanbanEvent] = []
        needs_preparation: List[KanbanEvent] = []
        monthly: List[KanbanEvent] = []
        later: List[KanbanEvent] = []
        weekly_source_pairs: List[tuple[CuratedEvent, KanbanEvent]] = []

        for ev in events:
            effective_start = ev.normalized_start
            effective_end = ev.normalized_end

            if ev.trip_id and ev.event_type in ("travel", "business_trip"):
                plan = plans_by_id.get(ev.trip_id)
                if plan and plan.start_date and plan.end_date:
                    if plan.end_date < today:
                        continue
                    effective_start, effective_end = local_date_range_to_utc(
                        plan.start_date,
                        plan.end_date,
                        user_tz,
                    )

            if effective_start is None:
                continue

            # Skip events that have already passed
            if effective_start < today_start_utc:
                continue

            prep_rows = ev.preparation_item_rows or []
            has_pending_prep = any(not row.done for row in prep_rows)
            open_associations = [
                assoc
                for assoc in (ev.associations or [])
                if not assoc.is_dismissed and not assoc.is_confirmed
            ]
            actionable_open_associations = self._filter_actionable_associations(
                source_event=ev,
                associations=open_associations,
                family_id=family_id,
                date_meta_by_target_id=date_meta_by_target_id,
            )
            has_open_association = bool(actionable_open_associations)

            # Skip low-priority events (e.g. solar terms) — the secretary
            # assigns priority during curation. We still surface low-priority
            # entries when the user has explicit preference signals or when
            # there is concrete pending work/association attached.
            if ev.priority == "low" and not self._should_surface_low_priority_event(
                ev,
                preferred_low_types=preferred_low_types,
                low_importance_types=low_importance_types,
                has_pending_prep=has_pending_prep,
                has_open_association=has_open_association,
            ):
                continue

            kanban_ev = to_kanban_event(
                ev,
                effective_start=effective_start,
                effective_end=effective_end,
            )

            if has_pending_prep and (effective_end is None or effective_end > now):
                needs_preparation.append(kanban_ev)

            if effective_start < week_end_utc:
                this_week.append(kanban_ev)
                weekly_source_pairs.append((ev, kanban_ev))
            elif effective_start < month_end_utc:
                monthly.append(kanban_ev)
            else:
                later.append(kanban_ev)

        # Query insights from unified insights table via InsightQueryService
        insight_query_svc = InsightQueryService(self.session)
        insight_cards = await insight_query_svc.get_for_kanban(user_id, limit=10)

        db_reminders = self._map_insight_cards(
            insight_cards,
            weekly_events=this_week,
            weekly_source_pairs=weekly_source_pairs,
            family_id=family_id,
            date_meta_by_target_id=date_meta_by_target_id,
        )
        needs_preparation_ids = {ev.id for ev in needs_preparation}
        event_driven = await self._build_event_driven_insights(
            weekly_source_pairs,
            today=today,
            user_tz=user_tz,
            family_id=family_id,
            user_id=user_id,
            date_meta_by_target_id=date_meta_by_target_id,
            needs_preparation_ids=needs_preparation_ids,
        )
        ai_reminders = self._merge_insights(event_driven, db_reminders, limit=10)

        return KanbanResponse(
            this_week=this_week,
            needs_preparation=needs_preparation,
            monthly=monthly,
            later=later,
            insights=ai_reminders,
        )

    def _map_insight_cards(
        self,
        cards: list,
        weekly_events: List[KanbanEvent],
        *,
        weekly_source_pairs: List[tuple[CuratedEvent, KanbanEvent]],
        family_id: UUID,
        date_meta_by_target_id: dict[str, dict[str, object]],
    ) -> List[KanbanInsight]:
        """Map InsightCard DTOs to KanbanInsight API schema."""
        mapped: List[KanbanInsight] = []
        for card in cards:
            raw_options = card.action_options or []
            translated_options = []
            for opt in raw_options:
                if isinstance(opt, dict):
                    translated_options.append(opt)
                else:
                    label = _ACTION_OPTION_LABELS.get(opt, opt)
                    translated_options.append({
                        "label": label,
                        "action_type": "open_detail",
                        "action_payload": {},
                    })

            # Map numeric urgency to string label
            urgency_val = card.urgency
            if isinstance(urgency_val, int):
                if urgency_val >= 90:
                    urgency_str = "critical"
                elif urgency_val >= 70:
                    urgency_str = "high"
                elif urgency_val >= 40:
                    urgency_str = "normal"
                else:
                    urgency_str = "low"
            else:
                urgency_str = str(urgency_val or "normal")
            urgency_label = _URGENCY_LABELS.get(urgency_str, urgency_str)
            type_label = _INSIGHT_TYPE_LABELS.get(
                card.insight_type or "", card.insight_type or ""
            )
            db_context_hint = f"{urgency_label} · {type_label}"

            mapped.append(
                KanbanInsight(
                    id=str(card.id),
                    title=card.title,
                    content=card.content,
                    insight_type=card.insight_type,
                    priority=card.importance or 50,
                    urgency=urgency_str,
                    action_type=None,
                    action_data=None,
                    action_options=translated_options,
                    context_hint=db_context_hint,
                    created_at=card.created_at,
                )
            )
        return mapped

    def _is_stale_low_value_event_context_insight(
        self,
        insight: Insight,
        *,
        source_event_by_id: dict[str, CuratedEvent],
        weekly_event_by_id: dict[str, KanbanEvent],
        family_id: UUID,
        date_meta_by_target_id: dict[str, dict[str, object]],
    ) -> bool:
        """Hide stale event-context reminders when no concrete action anchor remains."""
        action_data = getattr(insight, "action_data", None)
        action_data = action_data if isinstance(action_data, dict) else {}
        event_id = str(action_data.get("event_id") or "").strip()
        if not event_id:
            return False

        source_event = source_event_by_id.get(event_id)
        weekly_event = weekly_event_by_id.get(event_id)
        if source_event is None or weekly_event is None:
            return False

        action_type = str(getattr(insight, "action_type", "") or "").strip().lower()
        payload_type = str(action_data.get("type") or "").strip().lower()
        is_event_context = (
            payload_type in {"", "event_context"}
            and action_type in {"", "open_event_detail"}
        )
        if not is_event_context:
            return False

        has_pending_prep = any(
            (item.item or "").strip() and not item.done
            for item in (weekly_event.preparation_items or [])
        )
        if has_pending_prep:
            return False

        open_associations = [
            assoc
            for assoc in (source_event.associations or [])
            if not assoc.is_dismissed and not assoc.is_confirmed
        ]
        actionable_associations = self._filter_actionable_associations(
            source_event=source_event,
            associations=open_associations,
            family_id=family_id,
            date_meta_by_target_id=date_meta_by_target_id,
        )
        if actionable_associations:
            return False

        return True

    @staticmethod
    def _is_structurally_redundant_trip_reminder(
        insight: Insight,
        weekly_events: List[KanbanEvent],
    ) -> bool:
        """Suppress reminders that only restate a current weekly trip/location context.

        Uses structured fields (trip/location/event links), not title regex.
        """
        action_data = getattr(insight, "action_data", None)
        action_data = action_data if isinstance(action_data, dict) else {}

        weekly_trip_ids = {
            str(ev.trip_id) for ev in weekly_events
            if ev.trip_id is not None
        }
        weekly_locations = {
            (ev.location or "").strip().lower()
            for ev in weekly_events
            if ev.location
        }

        related_trips = {
            str(tid) for tid in (getattr(insight, "related_trip_ids", None) or [])
            if tid
        }
        location = str(action_data.get("location", "")).strip().lower()

        matches_current_context = bool(weekly_trip_ids & related_trips)
        if not matches_current_context and location:
            matches_current_context = location in weekly_locations
        if not matches_current_context:
            return False

        has_direct_targets = bool(
            (getattr(insight, "related_event_ids", None) or [])
            or (getattr(insight, "related_member_ids", None) or [])
            or action_data.get("person")
        )
        context_only_keys = {"location", "trip_start_date", "trip_end_date", "date"}
        has_extra_context = any(
            key not in context_only_keys for key in action_data.keys()
        )

        return not has_direct_targets and not has_extra_context

    @staticmethod
    def _resolve_insight_display_time(insight: Insight) -> Optional[datetime]:
        """Prefer event-related reference time over creation timestamp for display."""
        action_data = getattr(insight, "action_data", None)
        action_data = action_data if isinstance(action_data, dict) else {}
        for key in ("event_start_at", "trip_start_at", "trip_start_date", "date"):
            parsed = KanbanService._parse_action_datetime(action_data.get(key))
            if parsed is not None:
                return parsed
        return insight.created_at

    @staticmethod
    def _parse_action_datetime(value: object) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min, tzinfo=timezone.utc)

        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None

        try:
            if "T" in text:
                normalized = text.replace("Z", "+00:00")
                dt = datetime.fromisoformat(normalized)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt
            parsed_date = date.fromisoformat(text)
            return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
        except ValueError:
            return None

    async def _build_event_driven_insights(
        self,
        weekly_source_pairs: List[tuple[CuratedEvent, KanbanEvent]],
        *,
        today: date,
        user_tz: Optional[object] = None,
        family_id: UUID,
        user_id: UUID,
        date_meta_by_target_id: dict[str, dict[str, object]],
        needs_preparation_ids: Optional[set[str]] = None,
    ) -> List[KanbanInsight]:
        """Generate event-level actionable insights from preparation + associations.

        When an event already appears in the "needs_preparation" section (checkbox
        list), its preparation items are excluded from insight cards to avoid
        duplication.  Association-only insights are still generated.
        """
        generated: List[KanbanInsight] = []
        person_context = await build_person_context_map(
            self.session,
            family_id=family_id,
            user_id=user_id,
            person_ids=[
                str(assoc.target_id)
                for source_event, _ in weekly_source_pairs
                for assoc in (source_event.associations or [])
                if (
                    not assoc.is_dismissed
                    and not assoc.is_confirmed
                    and assoc.target_type == "person"
                )
            ],
        )

        for source_event, weekly_event in weekly_source_pairs:
            event_start = weekly_event.start_time
            if event_start is None:
                continue

            # Convert event_start to local date using user_tz to avoid
            # off-by-one errors when UTC date differs from local date.
            if user_tz is not None and getattr(event_start, "tzinfo", None) is not None:
                event_local_date = event_start.astimezone(user_tz).date()
            else:
                event_local_date = event_start.date()
            days_until = (event_local_date - today).days
            if days_until < 0:
                continue

            pending_items = [
                item.item.strip()
                for item in (weekly_event.preparation_items or [])
                if not item.done and item.item and item.item.strip()
            ]
            open_associations = [
                assoc
                for assoc in (source_event.associations or [])
                if not assoc.is_dismissed and not assoc.is_confirmed
            ]
            actionable_associations = self._filter_actionable_associations(
                source_event=source_event,
                associations=open_associations,
                family_id=family_id,
                date_meta_by_target_id=date_meta_by_target_id,
            )
            explicit_association_titles: List[str] = []
            for assoc in actionable_associations:
                if not assoc.title:
                    continue
                person_ctx = (
                    person_context.get(str(assoc.target_id))
                    if assoc.target_type == "person"
                    else None
                )
                display_title, _ = present_association_copy(
                    title=assoc.title,
                    reason=assoc.reason,
                    target_type=assoc.target_type,
                    source_location=weekly_event.location,
                    person_context=person_ctx,
                )
                if display_title.strip():
                    explicit_association_titles.append(display_title.strip())
            inferred_association_titles: List[str] = []
            # Avoid filler "time-nearby" lines when we already have explicit,
            # user-actionable associations for this event.
            if pending_items and not explicit_association_titles:
                inferred_association_titles = self._derive_nearby_event_association_titles(
                    current_event=weekly_event,
                    weekly_events=[pair[1] for pair in weekly_source_pairs],
                    max_items=2,
                )
            association_titles = list(dict.fromkeys(
                [*explicit_association_titles, *inferred_association_titles]
            ))

            # If this event already appears in the "needs_preparation" section
            # (checkbox list), suppress prep items here to avoid duplication.
            # Only keep association-based content for the insight card.
            event_in_prep_section = (
                needs_preparation_ids
                and weekly_event.id in needs_preparation_ids
            )
            preparation_suggestions = [] if event_in_prep_section else pending_items

            # Quality gate: no concrete prep and no actionable association -> no card.
            if not preparation_suggestions and not explicit_association_titles:
                continue

            title = f"{weekly_event.title}的准备建议"
            if not preparation_suggestions and association_titles:
                title = f"{weekly_event.title}的关联提醒"

            when_text = "今天"
            if days_until == 1:
                when_text = "明天"
            elif days_until > 1:
                when_text = f"{days_until}天后"

            content_parts = [f"{when_text}有「{weekly_event.title}」。"]
            if preparation_suggestions:
                content_parts.append(
                    "建议先完成：" + "、".join(preparation_suggestions[:3]) + "。"
                )
            if association_titles:
                content_parts.append(
                    "可顺便处理：" + "、".join(association_titles[:3]) + "。"
                )

            priority_base = {
                "critical": 10,
                "high": 8,
                "normal": 6,
                "low": 4,
            }.get(weekly_event.priority or "normal", 6)
            priority = min(
                10,
                priority_base
                + (1 if preparation_suggestions else 0)
                + (1 if association_titles else 0)
                + (2 if days_until <= 2 else 0),
            )
            urgency = "high" if days_until <= 2 else "normal"
            insight_type = "event_preparation" if preparation_suggestions else "reminder"

            action_data = {
                "type": "event_context",
                "event_id": weekly_event.id,
                "event_start_at": event_start.isoformat(),
                "days_until": days_until,
                "pending_preparation_count": len(preparation_suggestions),
                "association_count": len(association_titles),
                "explicit_association_count": len(explicit_association_titles),
                "inferred_association_count": len(inferred_association_titles),
                "associations": [
                    {
                        "id": str(assoc.id),
                        "title": display_title,
                        "target_type": assoc.target_type,
                        "target_id": str(assoc.target_id),
                        "reason": assoc.reason,
                    }
                    for assoc, display_title in zip(
                        actionable_associations, explicit_association_titles
                    )
                ],
                "preparation_suggestions": preparation_suggestions[:3],
            }

            is_trip = (
                weekly_event.event_type in ("travel", "business_trip")
                and weekly_event.trip_id
            )
            if is_trip:
                action_data["trip_id"] = str(weekly_event.trip_id)
                event_action_options = [
                    {"label": "查看行程详情", "action_type": "open_trip_detail", "action_payload": {}},
                    {"label": "忽略", "action_type": "dismiss", "action_payload": {}},
                ]
            else:
                event_action_options = [
                    {"label": "打开事件详情", "action_type": "open_event_detail", "action_payload": {}},
                    {"label": "忽略", "action_type": "dismiss", "action_payload": {}},
                ]

            prep_count = len(preparation_suggestions)
            assoc_count = len(association_titles)
            hint_detail = (
                f"{prep_count}项准备" if prep_count
                else f"{assoc_count}项关联" if assoc_count
                else ""
            )
            event_context_hint = f"{when_text} · {hint_detail}" if hint_detail else when_text

            generated.append(
                KanbanInsight(
                    id=f"event-context:{weekly_event.id}",
                    title=title,
                    content="".join(content_parts),
                    insight_type=insight_type,
                    priority=priority,
                    urgency=urgency,
                    action_type="open_trip_detail" if is_trip else "open_event_detail",
                    action_data=action_data,
                    action_options=event_action_options,
                    context_hint=event_context_hint,
                    created_at=event_start,
                )
            )

        return self._consolidate_holiday_like_insights(
            generated,
            weekly_source_pairs=weekly_source_pairs,
        )

    @staticmethod
    def _is_holiday_like_event_type(event_type: Optional[str]) -> bool:
        normalized = str(event_type or "").strip().lower()
        return normalized in {"holiday", "holiday_solar_term", "solar_term"}

    def _consolidate_holiday_like_insights(
        self,
        insights: List[KanbanInsight],
        *,
        weekly_source_pairs: List[tuple[CuratedEvent, KanbanEvent]],
    ) -> List[KanbanInsight]:
        """Merge highly similar holiday-like insights in the same short window."""
        event_by_id = {kanban_event.id: kanban_event for _, kanban_event in weekly_source_pairs}

        holiday_pairs: List[tuple[KanbanInsight, KanbanEvent]] = []
        for insight in insights:
            action_data = insight.action_data if isinstance(insight.action_data, dict) else {}
            event_id = str(action_data.get("event_id") or "").strip()
            if not event_id:
                continue
            event = event_by_id.get(event_id)
            if event is None or event.start_time is None:
                continue
            if not self._is_holiday_like_event_type(event.event_type):
                continue
            holiday_pairs.append((insight, event))

        if len(holiday_pairs) < 2:
            return insights

        holiday_pairs.sort(key=lambda pair: pair[1].start_time or datetime.max.replace(tzinfo=timezone.utc))

        clustered_insight_ids: set[str] = set()
        replacements: dict[str, KanbanInsight] = {}
        cluster: List[tuple[KanbanInsight, KanbanEvent]] = []

        def _flush_cluster() -> None:
            if len(cluster) < 2:
                cluster.clear()
                return

            # Keep the strongest card as canonical and fold nearby holiday context into it.
            canonical_pair = max(
                cluster,
                key=lambda pair: (
                    pair[0].priority or 0,
                    pair[1].start_time or datetime.max.replace(tzinfo=timezone.utc),
                ),
            )
            canonical_insight, canonical_event = canonical_pair
            cluster_titles = [pair[1].title for pair in cluster if pair[1].title]
            deduped_titles = list(dict.fromkeys(cluster_titles))
            extra_titles = [
                title for title in deduped_titles
                if title != canonical_event.title
            ]

            merged_title = canonical_insight.title

            merged_content = canonical_insight.content

            merged_action_data = dict(canonical_insight.action_data or {})
            merged_action_data["related_event_ids"] = [
                pair[1].id for pair in cluster if pair[1].id != canonical_event.id
            ]
            merged_action_data["clustered_event_count"] = len(cluster)
            if extra_titles:
                merged_action_data["related_event_titles"] = extra_titles[:3]

            replacements[canonical_insight.id] = KanbanInsight(
                id=canonical_insight.id,
                title=merged_title,
                content=merged_content,
                insight_type=canonical_insight.insight_type,
                priority=canonical_insight.priority,
                urgency=canonical_insight.urgency,
                action_type=canonical_insight.action_type,
                action_data=merged_action_data,
                # PLAN-005: carry over action_options from canonical source insight (TC-7)
                action_options=canonical_insight.action_options,
                context_hint=canonical_insight.context_hint,
                created_at=canonical_insight.created_at,
            )

            for pair in cluster:
                insight, _ = pair
                if insight.id != canonical_insight.id:
                    clustered_insight_ids.add(insight.id)
            cluster.clear()

        for insight, event in holiday_pairs:
            if not cluster:
                cluster.append((insight, event))
                continue
            prev_event = cluster[-1][1]
            prev_start = prev_event.start_time
            cur_start = event.start_time
            if prev_start is None or cur_start is None:
                _flush_cluster()
                cluster.append((insight, event))
                continue
            if abs((cur_start.date() - prev_start.date()).days) <= 1:
                cluster.append((insight, event))
                continue
            _flush_cluster()
            cluster.append((insight, event))
        _flush_cluster()

        if not clustered_insight_ids and not replacements:
            return insights

        consolidated: List[KanbanInsight] = []
        for insight in insights:
            if insight.id in clustered_insight_ids:
                continue
            replacement = replacements.get(insight.id)
            consolidated.append(replacement or insight)
        return consolidated

    @staticmethod
    def _derive_nearby_event_association_titles(
        *,
        current_event: KanbanEvent,
        weekly_events: List[KanbanEvent],
        max_items: int = 2,
    ) -> List[str]:
        """Derive cross-event links only when nearby events have pending prep tasks."""
        if current_event.start_time is None:
            return []

        derived: List[str] = []

        for other in weekly_events:
            if other.id == current_event.id or other.start_time is None:
                continue

            day_gap = abs((other.start_time.date() - current_event.start_time.date()).days)
            if day_gap > 3:
                continue

            has_pending_prep = any(
                (item.item or "").strip() and not item.done
                for item in (other.preparation_items or [])
            )
            if not has_pending_prep:
                continue

            title = f"顺手把「{other.title}」前的准备事项一起确认"

            if title in derived:
                continue
            derived.append(title)
            if len(derived) >= max_items:
                break

        return derived

    @staticmethod
    def _extract_group_components(
        action_data: dict,
        insight_type: str,
        fallback_id: str,
    ) -> tuple:
        """Extract grouping components from action_data.

        Returns a tuple suitable for both merge-key dedup and
        suggestion group_key generation.
        """
        event_id = action_data.get("event_id")
        if event_id:
            return ("event", str(event_id))

        person = str(action_data.get("person", "")).strip()
        if person:
            return ("person", person.lower(), insight_type)

        location = str(action_data.get("location", "")).strip().lower()
        date_ref = action_data.get("trip_start_date") or action_data.get("date")
        if location and date_ref:
            return ("trip", location, str(date_ref), insight_type)

        return ("id", fallback_id)

    @staticmethod
    def _insight_merge_key(insight: KanbanInsight) -> tuple:
        action_data = insight.action_data if isinstance(insight.action_data, dict) else {}
        return KanbanService._extract_group_components(
            action_data, insight.insight_type, insight.id,
        )

    @staticmethod
    def _suggestion_group_key(
        item: InsightFeedItem,
        member_names: Optional[List[str]] = None,
    ) -> str:
        """Compute a stable group_key string for a Future View suggestion.

        Falls back to person-name matching when action_data has no entity
        info (common for DB-sourced insights that lack action_data).
        Scans title + content against family member names for grouping.
        """
        action_data = item.action_data if isinstance(item.action_data, dict) else {}
        components = KanbanService._extract_group_components(
            action_data, item.insight_type, item.id,
        )
        if components[0] != "id":
            return ":".join(str(c) for c in components)

        # Fallback: scan title+content for family member names
        text = f"{item.title or ''} {item.content or ''}".lower()
        if member_names:
            for name in member_names:
                if name.lower() in text:
                    return f"person_name:{name.lower()}"

        # Final fallback: title-based grouping
        if (item.title or "").strip():
            return f"title:{item.title.strip().lower()}:{item.insight_type}"
        return ":".join(str(c) for c in components)

    @staticmethod
    def _assign_group_labels(suggestions: list[dict]) -> None:
        """Set group_label to the first title seen for each group_key."""
        first_title: dict[str, str] = {}
        for s in suggestions:
            key = s.get("group_key", "")
            if key not in first_title:
                first_title[key] = s.get("title", "")
        for s in suggestions:
            s["group_label"] = first_title.get(s.get("group_key", ""), "")

    def _merge_insights(
        self,
        generated: List[KanbanInsight],
        from_db: List[KanbanInsight],
        *,
        limit: int,
    ) -> List[KanbanInsight]:
        """Merge generated + DB insights, keep strongest per semantic key."""
        merged: dict[tuple, KanbanInsight] = {}

        def _normalized(dt: Optional[datetime]) -> datetime:
            if dt is None:
                return datetime.max.replace(tzinfo=timezone.utc)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        def _better(current: KanbanInsight, candidate: KanbanInsight) -> KanbanInsight:
            if candidate.priority != current.priority:
                return candidate if candidate.priority > current.priority else current
            current_time = _normalized(current.created_at)
            candidate_time = _normalized(candidate.created_at)
            return candidate if candidate_time < current_time else current

        def _is_generated_event_insight(insight: KanbanInsight) -> bool:
            return str(insight.id).startswith("event-context:")

        for insight in [*generated, *from_db]:
            key = self._insight_merge_key(insight)
            existing = merged.get(key)
            if existing is None:
                merged[key] = insight
                continue
            if key and key[0] == "event":
                existing_generated = _is_generated_event_insight(existing)
                incoming_generated = _is_generated_event_insight(insight)
                if existing_generated != incoming_generated:
                    merged[key] = existing if existing_generated else insight
                    continue
            merged[key] = _better(existing, insight)

        def _urgency_score(value: str) -> int:
            if value == "high":
                return 2
            if value == "normal":
                return 1
            return 0

        ordered = sorted(
            merged.values(),
            key=lambda insight: (
                -(insight.priority or 0),
                -_urgency_score(insight.urgency),
                _normalized(insight.created_at),
            ),
        )
        return self._apply_type_diversity_cap(ordered, max_per_type=3, limit=limit)

    # ------------------------------------------------------------------
    # Upcoming events (for briefing integration)
    # ------------------------------------------------------------------

    async def get_upcoming_events(
        self,
        family_id: UUID,
        user_id: UUID,
        days: int = 7,
    ) -> List[KanbanEvent]:
        """Fetch upcoming active events within the next N days with preparation items.

        Intended as the single query layer for briefing and graph modules.
        """
        user_tz = await get_user_timezone(self.session, user_id)
        today = local_today(user_tz)
        end_date = today + timedelta(days=days)

        today_start_utc, end_utc = local_date_range_to_utc(today, end_date, user_tz)

        stmt = (
            select(CuratedEvent)
            .where(and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
                CuratedEvent.normalized_start >= today_start_utc,
                CuratedEvent.normalized_start < end_utc,
            ))
            .order_by(CuratedEvent.normalized_start)
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()

        return [to_kanban_event(ev) for ev in events]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _insight_dedup_key(insight: object) -> tuple:
        """Build a stable dedup key from structured action_data fields.

        For insights with a ``holiday`` in action_data the key is
        ``("holiday", name)`` — same holiday only shows once.

        For insights with ``type=important_date`` the key is
        ``("important_date", identifier, insight_type)``.

        For insights with a ``person`` in action_data the key is
        ``(person, insight_type)`` — same person only shows once
        regardless of title wording or destination.

        For other insights the key is ``(insight_type, insight_id)``
        so every non-person insight is unique (dedup is left to the
        LLM consolidation service).
        """
        action_data = getattr(insight, "action_data", None)
        action_data = action_data if isinstance(action_data, dict) else {}
        insight_type = getattr(insight, "insight_type", "")

        # Holiday dedup: same holiday → one slot
        holiday = action_data.get("holiday", "")
        if holiday:
            return ("holiday", str(holiday).strip())

        # Important date dedup: same date entity → one slot
        date_type = action_data.get("type", "")
        if date_type in ("important_date", "holiday_prep"):
            identifier = (
                action_data.get("person_name")
                or action_data.get("holiday")
                or action_data.get("date", "")
            )
            if identifier:
                return ("important_date", str(identifier).strip(), insight_type)

        person = action_data.get("person", "")
        if person:
            return (person, insight_type)

        return (insight_type, str(getattr(insight, "id", "")))

    @staticmethod
    def _apply_type_diversity_cap(
        insights: list,
        *,
        max_per_type: int = 3,
        limit: int = 10,
    ) -> list:
        """Cap per insight_type to ensure diversity, then slice to limit."""
        type_counts: dict[str, int] = {}
        result: list = []
        for ins in insights:
            itype = getattr(ins, "insight_type", "") or ""
            count = type_counts.get(itype, 0)
            if count >= max_per_type:
                continue
            type_counts[itype] = count + 1
            result.append(ins)
            if len(result) >= limit:
                break
        return result

    # ------------------------------------------------------------------
    # Insight Feed (insight-centric feed endpoint)
    # ------------------------------------------------------------------

    async def get_insight_feed(
        self,
        family_id: UUID,
        user_id: UUID,
        limit: int = 100,
    ) -> InsightFeedResponse:
        """Return an insight-centric feed with resolved entity relationships.

        Reuses event-fetching and insight-loading from get_kanban_view, then
        enriches each insight with resolved related entities.
        """
        user_tz = await get_user_timezone(self.session, user_id)
        now = utc_now()
        today = local_today(user_tz)

        week_end = today + timedelta(days=7)
        month_end = today + timedelta(days=30)

        today_start_utc, week_end_utc = local_date_range_to_utc(today, week_end, user_tz)
        _, month_end_utc = local_date_range_to_utc(today, month_end, user_tz)

        stmt = (
            select(CuratedEvent)
            .options(selectinload(CuratedEvent.preparation_item_rows))
            .options(selectinload(CuratedEvent.associations))
            .where(and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
                or_(
                    CuratedEvent.normalized_start >= today_start_utc,
                    and_(
                        CuratedEvent.event_type.in_(["travel", "business_trip"]),
                        CuratedEvent.trip_id.is_not(None),
                    ),
                ),
            ))
            .order_by(CuratedEvent.normalized_start)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        all_events = result.scalars().all()

        trip_ids = {
            ev.trip_id for ev in all_events
            if ev.trip_id and ev.event_type in ("travel", "business_trip")
        }
        plans_by_id: dict = {}
        if trip_ids:
            from ...trip.models.trip_plan import TripPlan

            plan_stmt = select(TripPlan).where(and_(
                TripPlan.trip_id.in_(trip_ids),
                TripPlan.status != "cancelled",
            ))
            plan_result = await self.session.execute(plan_stmt)
            plans_by_id = {
                plan.trip_id: plan
                for plan in plan_result.scalars().all()
            }

        low_importance_types = _low_importance_event_types()
        preferred_low_types = await self._load_user_low_importance_preferences(
            family_id=family_id,
            user_id=user_id,
            low_importance_types=low_importance_types,
        )
        date_meta_by_target_id = await self._load_open_association_date_meta(all_events)

        this_week: List[KanbanEvent] = []
        needs_preparation: List[KanbanEvent] = []
        monthly_events: List[KanbanEvent] = []
        later_events: List[KanbanEvent] = []
        weekly_source_pairs: List[tuple] = []

        for ev in all_events:
            effective_start = ev.normalized_start
            effective_end = ev.normalized_end

            if ev.trip_id and ev.event_type in ("travel", "business_trip"):
                plan = plans_by_id.get(ev.trip_id)
                if plan and plan.start_date and plan.end_date:
                    if plan.end_date < today:
                        continue
                    effective_start, effective_end = local_date_range_to_utc(
                        plan.start_date,
                        plan.end_date,
                        user_tz,
                    )

            if effective_start is None or effective_start < today_start_utc:
                continue

            prep_rows = ev.preparation_item_rows or []
            has_pending_prep = any(not row.done for row in prep_rows)
            open_associations = [
                assoc
                for assoc in (ev.associations or [])
                if not assoc.is_dismissed and not assoc.is_confirmed
            ]
            actionable_open_associations = self._filter_actionable_associations(
                source_event=ev,
                associations=open_associations,
                family_id=family_id,
                date_meta_by_target_id=date_meta_by_target_id,
            )
            has_open_association = bool(actionable_open_associations)

            if ev.priority == "low" and not self._should_surface_low_priority_event(
                ev,
                preferred_low_types=preferred_low_types,
                low_importance_types=low_importance_types,
                has_pending_prep=has_pending_prep,
                has_open_association=has_open_association,
            ):
                continue

            kanban_ev = to_kanban_event(
                ev,
                effective_start=effective_start,
                effective_end=effective_end,
            )

            if has_pending_prep and (effective_end is None or effective_end > now):
                needs_preparation.append(kanban_ev)

            if effective_start < week_end_utc:
                this_week.append(kanban_ev)
                weekly_source_pairs.append((ev, kanban_ev))
            elif effective_start < month_end_utc:
                monthly_events.append(kanban_ev)
            else:
                later_events.append(kanban_ev)

        # Query insights from unified insights table via InsightQueryService
        insight_query_svc = InsightQueryService(self.session)
        insight_cards = await insight_query_svc.get_for_kanban(user_id, limit=10)

        needs_preparation_ids = {ev.id for ev in needs_preparation}
        event_driven = await self._build_event_driven_insights(
            weekly_source_pairs,
            today=today,
            user_tz=user_tz,
            family_id=family_id,
            user_id=user_id,
            date_meta_by_target_id=date_meta_by_target_id,
            needs_preparation_ids=needs_preparation_ids,
        )
        db_reminders = self._map_insight_cards(
            insight_cards,
            weekly_events=this_week,
            weekly_source_pairs=weekly_source_pairs,
            family_id=family_id,
            date_meta_by_target_id=date_meta_by_target_id,
        )
        merged_insights = self._merge_insights(event_driven, db_reminders, limit=10)

        feed_items = await self._resolve_insight_entities(insight_cards, merged_insights)
        standalone_events = self._classify_standalone_events(this_week, feed_items)

        return InsightFeedResponse(
            insights=feed_items,
            standalone_events=standalone_events,
            later_events=monthly_events + later_events,
            needs_preparation=needs_preparation,
        )

    def group_insight_feed(
        self,
        flat_feed: InsightFeedResponse,
    ) -> InsightFeedGroupedResponse:
        """Transform a flat insight feed into semantically grouped clusters.

        Groups:
          - today_focus: urgent + important + event_preparation insights
          - relationship_care: correlation, followup, relationship_maintenance
          - coming_up: reminder, suggestion for future events
          - patterns: observation, pattern_observation

        Pure function over the already-computed flat feed — no DB queries.
        """
        _FOCUS_TYPES = frozenset({"event_preparation"})
        _FOCUS_URGENCIES = frozenset({"urgent", "important"})
        _RELATIONSHIP_TYPES = frozenset({
            "correlation",
            "followup",
            "relationship_maintenance",
        })
        _PATTERN_TYPES = frozenset({"observation", "pattern_observation"})

        focus_items: List[InsightFeedItem] = []
        relationship_items: List[InsightFeedItem] = []
        coming_up_items: List[InsightFeedItem] = []
        pattern_items: List[InsightFeedItem] = []

        for insight in flat_feed.insights:
            if (
                insight.urgency in _FOCUS_URGENCIES
                or insight.insight_type in _FOCUS_TYPES
            ):
                focus_items.append(insight)
            elif insight.insight_type in _RELATIONSHIP_TYPES:
                relationship_items.append(insight)
            elif insight.insight_type in _PATTERN_TYPES:
                pattern_items.append(insight)
            else:
                coming_up_items.append(insight)

        groups: List[InsightGroup] = []

        if focus_items or flat_feed.standalone_events or flat_feed.needs_preparation:
            groups.append(InsightGroup(
                group_id="today_focus",
                title="现在关注",
                subtitle=f"{len(focus_items) + len(flat_feed.standalone_events)} 项需要关注",
                insights=focus_items,
                preparation_events=list(flat_feed.needs_preparation),
                standalone_events=list(flat_feed.standalone_events),
            ))

        if relationship_items:
            groups.append(InsightGroup(
                group_id="relationship_care",
                title="关系维护",
                subtitle=f"{len(relationship_items)} 条提醒",
                insights=relationship_items,
            ))

        if coming_up_items:
            groups.append(InsightGroup(
                group_id="coming_up",
                title="接下来",
                subtitle=f"{len(coming_up_items)} 项安排",
                insights=coming_up_items,
            ))

        if pattern_items:
            groups.append(InsightGroup(
                group_id="patterns",
                title="发现与观察",
                insights=pattern_items,
            ))

        return InsightFeedGroupedResponse(
            groups=groups,
            later_events=list(flat_feed.later_events),
        )

    async def _resolve_insight_entities(
        self,
        insight_cards: list,
        mapped_insights: List[KanbanInsight],
    ) -> List[InsightFeedItem]:
        """Enrich KanbanInsight list with resolved entity summaries.

        Uses InsightCard.entities (InsightEntityRef list) from the unified
        insight system to resolve related events, members, and trips.
        """
        all_event_ids: Set[str] = set()
        all_member_ids: Set[str] = set()
        all_trip_ids: Set[str] = set()

        card_by_id: Dict[str, object] = {
            str(card.id): card
            for card in insight_cards
            if getattr(card, "id", None) is not None
        }

        for insight in mapped_insights:
            card = card_by_id.get(insight.id)
            if card is not None:
                for entity_ref in (getattr(card, "entities", None) or []):
                    eid = str(entity_ref.entity_id)
                    if entity_ref.entity_type == "event":
                        all_event_ids.add(eid)
                    elif entity_ref.entity_type == "person":
                        all_member_ids.add(eid)
                    elif entity_ref.entity_type == "trip":
                        all_trip_ids.add(eid)

        events_map, members_map, trips_map = await asyncio.gather(
            self._batch_resolve_events(all_event_ids),
            self._batch_resolve_members(all_member_ids),
            self._batch_resolve_trips(all_trip_ids),
        )

        feed_items: List[InsightFeedItem] = []
        for insight in mapped_insights:
            card = card_by_id.get(insight.id)

            related_event_ids: List[str] = []
            related_member_ids: List[str] = []
            related_trip_ids: List[str] = []

            if card is not None:
                for entity_ref in (getattr(card, "entities", None) or []):
                    eid = str(entity_ref.entity_id)
                    if entity_ref.entity_type == "event":
                        related_event_ids.append(eid)
                    elif entity_ref.entity_type == "person":
                        related_member_ids.append(eid)
                    elif entity_ref.entity_type == "trip":
                        related_trip_ids.append(eid)

            resolved_events = [
                events_map[eid] for eid in related_event_ids if eid in events_map
            ]
            resolved_members = [
                members_map[mid] for mid in related_member_ids if mid in members_map
            ]
            resolved_trip: Optional[InsightRelatedTrip] = None
            for tid in related_trip_ids:
                if tid in trips_map:
                    resolved_trip = trips_map[tid]
                    break

            if insight.id.startswith("event-context:"):
                source_ctx = "事件关联分析"
            else:
                source_ctx = _INSIGHT_TYPE_LABELS.get(
                    insight.insight_type or "", "AI洞察"
                )
            if resolved_trip is not None and resolved_trip.name:
                source_ctx = f"{source_ctx} · 行程: {resolved_trip.name}"

            feed_items.append(
                InsightFeedItem(
                    id=insight.id,
                    title=insight.title,
                    content=insight.content,
                    insight_type=insight.insight_type,
                    priority=insight.priority,
                    urgency=insight.urgency,
                    action_type=insight.action_type,
                    action_data=insight.action_data,
                    action_options=insight.action_options,
                    context_hint=insight.context_hint,
                    created_at=insight.created_at,
                    related_events=resolved_events,
                    related_members=resolved_members,
                    related_trip=resolved_trip,
                    source_context=source_ctx,
                )
            )

        return feed_items

    async def _batch_resolve_events(
        self,
        event_ids: Set[str],
    ) -> Dict[str, InsightRelatedEvent]:
        """Query CuratedEvent rows for the given IDs and return a lookup map."""
        if not event_ids:
            return {}

        try:
            uuid_ids = [UUID(eid) for eid in event_ids if eid]
        except Exception:
            valid: List[UUID] = []
            for eid in event_ids:
                try:
                    valid.append(UUID(eid))
                except Exception:
                    pass
            uuid_ids = valid

        if not uuid_ids:
            return {}

        try:
            stmt = select(CuratedEvent).where(CuratedEvent.id.in_(uuid_ids))
            result = await self.session.execute(stmt)
            rows = result.scalars().all()
        except Exception:
            logger.error("_batch_resolve_events query failed", exc_info=True)
            return {}

        return {
            str(row.id): InsightRelatedEvent(
                id=str(row.id),
                title=row.title or "",
                event_type=row.event_type,
                start_time=row.normalized_start,
                location=row.location,
                status=row.status or "active",
            )
            for row in rows
        }

    async def _batch_resolve_members(
        self,
        member_ids: Set[str],
    ) -> Dict[str, InsightRelatedMember]:
        """Query Member rows for the given IDs and return a lookup map."""
        if not member_ids:
            return {}

        try:
            uuid_ids = [UUID(mid) for mid in member_ids if mid]
        except Exception:
            valid = []
            for mid in member_ids:
                try:
                    valid.append(UUID(mid))
                except Exception:
                    pass
            uuid_ids = valid

        if not uuid_ids:
            return {}

        try:
            from ...member.models.member import Member

            stmt = select(Member).where(
                Member.id.in_(uuid_ids),
                Member.is_deleted.is_(False),
            )
            result = await self.session.execute(stmt)
            rows = result.scalars().all()
        except Exception:
            logger.error("_batch_resolve_members query failed", exc_info=True)
            return {}

        return {
            str(row.id): InsightRelatedMember(
                id=str(row.id),
                name=row.name or "",
                relationship=None,
                avatar_url=getattr(row, "avatar_url", None),
            )
            for row in rows
        }

    async def _batch_resolve_trips(
        self,
        trip_ids: Set[str],
    ) -> Dict[str, InsightRelatedTrip]:
        """Query TripPlan rows for the given IDs and return a lookup map."""
        if not trip_ids:
            return {}

        try:
            uuid_ids = [UUID(tid) for tid in trip_ids if tid]
        except Exception:
            valid = []
            for tid in trip_ids:
                try:
                    valid.append(UUID(tid))
                except Exception:
                    pass
            uuid_ids = valid

        if not uuid_ids:
            return {}

        try:
            from ...trip.models.trip_plan import TripPlan

            stmt = select(TripPlan).where(TripPlan.trip_id.in_(uuid_ids))
            result = await self.session.execute(stmt)
            rows = result.scalars().all()
        except Exception:
            logger.error("_batch_resolve_trips query failed", exc_info=True)
            return {}

        return {
            str(row.trip_id): InsightRelatedTrip(
                id=str(row.trip_id),
                name=row.trip_name or row.destination or "",
                start_date=row.start_date,
                end_date=row.end_date,
                status=row.status,
            )
            for row in rows
        }

    def _classify_standalone_events(
        self,
        this_week_events: List[KanbanEvent],
        feed_items: List[InsightFeedItem],
    ) -> List[KanbanEvent]:
        """Return this-week events not referenced by any insight's related_events."""
        referenced_ids: Set[str] = set()
        for item in feed_items:
            for ev in item.related_events:
                referenced_ids.add(ev.id)

        return [ev for ev in this_week_events if ev.id not in referenced_ids]

    # ------------------------------------------------------------------
    # Future View (V4 timeline)
    # ------------------------------------------------------------------

    _AVATAR_PALETTE = [
        "#7B1FA2", "#1976D2", "#E65100", "#D89575",
        "#3D8A5A", "#D32F2F", "#00796B", "#E6A000",
    ]

    _DATE_TYPE_CONTEXT_HINTS: dict[str, str] = {
        "birthday": "记得准备生日礼物和祝福",
        "anniversary": "可以安排一次纪念活动",
        "holiday": "提前做好假期安排",
        "festival": "提前做好节日准备",
        "memorial": "可以安排纪念活动",
        "graduation": "准备祝贺和礼物",
        "wedding": "准备祝福和礼金",
    }

    async def get_future_view(
        self,
        *,
        family_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Return data for the V4 future timeline view.

        Runs 4 section queries in parallel:
        - Active trips with preparation progress
        - AI suggestions (non-trip insights)
        - Upcoming important dates (next 90 days)
        - Family members with relationship info
        """
        # SQLAlchemy async sessions do not support concurrent operations,
        # so run each section sequentially on the same session.
        trips_data = await self._future_view_trips(family_id=family_id, user_id=user_id)

        # Collect existing prep item texts per trip to deduplicate suggestions
        existing_prep_by_trip: dict[str, set[str]] = {}
        for trip in trips_data:
            trip_id = trip.get("id", "")
            texts: set[str] = set()
            for task in trip.get("tasks", []):
                title = (task.get("title") or "").strip()
                if title:
                    texts.add(title)
            if texts:
                existing_prep_by_trip[trip_id] = texts

        # Collect member names for person-based suggestion grouping
        members_data = await self._future_view_members(family_id=family_id)
        member_names = [m.get("name", "") for m in members_data if m.get("name")]

        suggestions_data = await self._future_view_suggestions(
            family_id=family_id,
            user_id=user_id,
            existing_prep_by_trip=existing_prep_by_trip,
            member_names=member_names,
        )

        # First page: only items within 30 days
        upcoming_data, upcoming_has_more = await self._future_view_upcoming(
            family_id=family_id,
            max_days=30,
        )

        return {
            "trips": trips_data,
            "suggestions": suggestions_data,
            "upcoming": upcoming_data,
            "upcoming_has_more": upcoming_has_more,
            "family_members": members_data,
        }

    # -- Section helpers (each wrapped in try/except) --------------------

    async def _future_view_trips(
        self,
        *,
        family_id: UUID,
        user_id: UUID,
    ) -> list:
        """Active trips with preparation task progress."""
        try:
            from ...trip.models.trip_plan import TripPlan
            from ...member.models.member import Member

            today = local_today()

            stmt = (
                select(TripPlan)
                .where(and_(
                    TripPlan.family_id == family_id,
                    TripPlan.is_active.is_(True),
                    TripPlan.status.in_(["planning", "confirmed", "in_progress"]),
                    TripPlan.end_date >= today,
                ))
                .order_by(TripPlan.start_date)
                .limit(5)
            )
            result = await self.session.execute(stmt)
            trips = list(result.scalars().all())

            if not trips:
                return []

            # Collect all participant IDs for batch member lookup
            all_participant_ids: set[UUID] = set()
            for trip in trips:
                for pid in (trip.participants or []):
                    all_participant_ids.add(pid)

            members_by_id: dict[UUID, object] = {}
            if all_participant_ids:
                member_stmt = select(Member).where(
                    Member.id.in_(list(all_participant_ids)),
                    Member.is_deleted.is_(False),
                )
                member_result = await self.session.execute(member_stmt)
                members_by_id = {
                    m.id: m for m in member_result.scalars().all()
                }

            # Load preparation items via CuratedEvent for each trip
            trip_ids = [t.trip_id for t in trips]
            prep_stmt = (
                select(CuratedEvent)
                .options(selectinload(CuratedEvent.preparation_item_rows))
                .where(and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.trip_id.in_(trip_ids),
                    CuratedEvent.is_active.is_(True),
                ))
            )
            prep_result = await self.session.execute(prep_stmt)
            events_by_trip: dict[UUID, list] = {}
            for ev in prep_result.scalars().all():
                events_by_trip.setdefault(ev.trip_id, []).append(ev)

            trips_data: list[dict] = []
            for trip in trips:
                days_until = (trip.start_date - today).days

                # Build task list from preparation items
                tasks: list[dict] = []
                source_labels = {
                    "ai": "AI建议",
                    "travel": "行程规划",
                    "memory": "记忆提取",
                    "manual": "",
                }
                for ev in events_by_trip.get(trip.trip_id, []):
                    for item in (ev.preparation_item_rows or []):
                        item_text = (item.text or "").strip()
                        if not item_text:
                            continue
                        source = getattr(item, "source", "manual") or "manual"
                        subtitle = source_labels.get(source, "")
                        tasks.append({
                            "id": str(item.key if hasattr(item, "key") and item.key else item.id),
                            "title": item_text,
                            "subtitle": subtitle,
                            "done": bool(item.done),
                            "action_label": "查看" if not item.done else "",
                            "action_type": "view",
                            "is_primary_action": False,
                            "member_color": None,
                        })

                # Also include adopted insight items for this trip
                adopted_tasks = await self._get_adopted_insight_tasks(
                    family_id=family_id,
                    trip_id=str(trip.trip_id),
                )
                tasks.extend(adopted_tasks)

                done_count = sum(1 for t in tasks if t["done"])
                total_count = len(tasks)

                # Build participant list with colors
                participants: list[dict] = []
                for idx, pid in enumerate(trip.participants or []):
                    member = members_by_id.get(pid)
                    color = self._AVATAR_PALETTE[
                        idx % len(self._AVATAR_PALETTE)
                    ]
                    participants.append({
                        "id": str(pid),
                        "name": member.name if member else "未知",
                        "avatar_url": getattr(member, "avatar_url", None),
                        "color": color,
                    })

                # Determine emoji and category
                trip_type = getattr(trip, "trip_type", None) or ""
                is_business = trip_type.lower() in ("business", "work", "出差")
                emoji = "✈️" if is_business else "🏖️"

                trips_data.append({
                    "id": str(trip.trip_id),
                    "name": trip.trip_name or trip.destination,
                    "emoji": emoji,
                    "category": "business" if is_business else "personal",
                    "destination": trip.destination,
                    "start_date": trip.start_date.isoformat(),
                    "end_date": trip.end_date.isoformat(),
                    "days_until": days_until,
                    "status": trip.status,
                    "tasks": tasks,
                    "done_count": done_count,
                    "total_count": total_count,
                    "participants": participants,
                })

            # Attach insights to each trip (max 5 trips, so N queries acceptable)
            await self._attach_trip_insights(trips_data, user_id)

            return trips_data

        except Exception:
            logger.error("_future_view_trips failed", exc_info=True)
            return []

    async def _attach_trip_insights(
        self,
        trips_data: list[dict],
        user_id: UUID,
    ) -> None:
        """Query and attach insight cards to each trip dict."""
        svc = InsightQueryService(self.session)
        for trip in trips_data:
            try:
                cards = await svc.get_for_trip(
                    user_id, UUID(trip["id"]), limit=10,
                )
                logger.info(
                    "_attach_trip_insights: trip=%s user=%s found %d insights",
                    trip["id"], user_id, len(cards),
                )
                trip["insights"] = [
                    self._serialize_insight_card(card) for card in cards
                ]
            except Exception:
                logger.error(
                    "_attach_trip_insights failed for trip %s", trip["id"],
                    exc_info=True,
                )
                trip["insights"] = []

    @staticmethod
    def _urgency_int_to_str(val) -> str:
        """Convert urgency int (0-100) to frontend string category."""
        if isinstance(val, int):
            if val >= 90:
                return "critical"
            if val >= 70:
                return "high"
            if val >= 40:
                return "normal"
            return "low"
        return str(val or "normal")

    @staticmethod
    def _serialize_insight_card(card) -> dict:
        """Convert an InsightCard DTO to a JSON-serializable dict."""
        return {
            "id": str(card.id),
            "insight_type": card.insight_type,
            "title": card.title,
            "content": card.content,
            "importance": card.importance,
            "urgency": KanbanService._urgency_int_to_str(card.urgency),
            "suggested_action": card.suggested_action,
            "action_options": card.action_options or [],
            "created_at": card.created_at.isoformat() if card.created_at else None,
        }

    async def _get_adopted_insight_tasks(
        self,
        *,
        family_id: UUID,
        trip_id: str,
    ) -> list[dict]:
        """Load adopted sub-items from Insight records linked to a trip.

        Uses the unified insights table with InsightEntity join to find
        insights associated with the given trip.
        """
        try:
            from ...insight.models import InsightEntity
            # Query insights with adopted entities linked to this trip.
            stmt = (
                select(Insight, InsightEntity)
                .join(InsightEntity, InsightEntity.insight_id == Insight.id)
                .where(and_(
                    Insight.family_id == family_id,
                    Insight.status.in_(["pending", "active", "acted"]),
                    InsightEntity.entity_type == "trip",
                    InsightEntity.entity_id == UUID(trip_id) if trip_id else None,
                    InsightEntity.adopted_at.isnot(None),
                ))
            )
            result = await self.session.execute(stmt)
            rows = list(result.all())

            tasks: list[dict] = []
            for insight, entity in rows:
                tasks.append({
                    "id": f"{insight.id}_adopted",
                    "title": (insight.suggested_action or insight.title).strip(),
                    "subtitle": "AI建议",
                    "done": entity.done_at is not None,
                    "action_label": "",
                    "action_type": "view",
                    "is_primary_action": False,
                    "member_color": None,
                })
            return tasks
        except Exception:
            logger.warning("_get_adopted_insight_tasks failed", exc_info=True)
            return []

    async def _future_view_suggestions(
        self,
        *,
        family_id: UUID,
        user_id: UUID,
        existing_prep_by_trip: dict[str, set[str]] | None = None,
        member_names: Optional[List[str]] = None,
    ) -> list:
        """AI suggestions: insights + pending SUGGEST_* actions, grouped by trip."""
        try:
            feed = await self.get_insight_feed(
                family_id=family_id, user_id=user_id, limit=100,
            )

            # ---- Collect pending SUGGEST_* actions ----
            pending_suggest_items: list[dict] = []
            try:
                from ...conversation.pending_action import PendingAction

                pa_stmt = (
                    select(PendingAction)
                    .where(and_(
                        PendingAction.family_id == family_id,
                        PendingAction.user_id == user_id,
                        PendingAction.status == "pending",
                        PendingAction.expires_at >= utc_now(),
                    ))
                    .order_by(PendingAction.created_at)
                    .limit(20)
                )
                pa_result = await self.session.execute(pa_stmt)
                pending_actions = list(pa_result.scalars().all())

                suggest_types = {
                    "SUGGEST_MEETING", "SUGGEST_GREETING", "SUGGEST_GIFT",
                    "SUGGEST_DEFER",
                }
                for pa in pending_actions:
                    at_str = str(
                        pa.action_type.value
                        if hasattr(pa.action_type, "value")
                        else pa.action_type
                    )
                    if at_str not in suggest_types:
                        continue
                    display = pa.display_data or {}
                    payload = pa.payload or {}
                    pending_suggest_items.append({
                        "pa_id": str(pa.id),
                        "label": display.get("title") or display.get("summary") or at_str,
                        "description": display.get("description", ""),
                        "action_type": at_str.lower(),
                        "source_insight_id": payload.get("source_id"),
                        # Try to find trip context from payload
                        "trip_id": payload.get("trip_id"),
                    })
            except Exception:
                logger.warning("Failed to load suggest PendingActions", exc_info=True)

            # ---- Build insight-based suggestions ----
            suggestions: list[dict] = []
            for item in feed.insights:
                if len(suggestions) >= 10:
                    break

                # Skip insights with empty titles
                if not (item.title or "").strip():
                    continue

                insight_type = item.insight_type or ""
                tag_emoji, tag_label, tag_color = self._resolve_insight_tag(
                    insight_type,
                )

                has_trip = item.related_trip is not None
                related_trip_id = str(item.related_trip) if has_trip else None

                # --- Build sub_items from 3 sources ---
                sub_items: list[dict] = []

                # Source 1: Parse content for actionable items
                content_subs = self._parse_content_sub_items(
                    item.content or "",
                    item.id,
                    related_trip_id,
                )
                sub_items.extend(content_subs)

                # Source 2: Attach matching PendingActions
                remaining_pa: list[dict] = []
                for pa_item in pending_suggest_items:
                    matched = False
                    if pa_item.get("source_insight_id") == item.id:
                        matched = True
                    elif (
                        has_trip
                        and pa_item.get("trip_id")
                        and pa_item["trip_id"] == str(item.related_trip)
                    ):
                        matched = True

                    if matched:
                        sub_items.append({
                            "id": pa_item["pa_id"],
                            "label": pa_item["label"],
                            "description": pa_item["description"],
                            "action_type": pa_item["action_type"],
                            "is_pending_action": True,
                        })
                    else:
                        remaining_pa.append(pa_item)
                pending_suggest_items = remaining_pa

                # Filter out sub-items already adopted on this insight
                insight_action_data = getattr(item, "action_data", None) or {}
                adopted_set = set(insight_action_data.get("adopted_items", []))
                if adopted_set:
                    sub_items = [
                        s for s in sub_items
                        if s["label"].strip() not in adopted_set
                    ]

                # Also filter against existing prep items in the trip
                if related_trip_id and existing_prep_by_trip:
                    trip_preps = existing_prep_by_trip.get(related_trip_id, set())
                    if trip_preps:
                        sub_items = [
                            s for s in sub_items
                            if s["label"].strip() not in trip_preps
                        ]

                # Skip the entire suggestion if all sub-items are already adopted
                if not sub_items and has_trip and (item.content or "").strip():
                    if self._parse_content_sub_items(
                        item.content or "", item.id, related_trip_id,
                    ):
                        continue

                suggestions.append({
                    "id": item.id,
                    "insight_id": item.id,
                    "title": item.title,
                    "description": item.content or "",
                    "tag_emoji": tag_emoji,
                    "tag_label": tag_label,
                    "tag_color": tag_color,
                    "action_label": "采纳" if has_trip else "了解",
                    "action_type": "navigate_trip" if has_trip else "acknowledge",
                    "action_data": {"related_trip_id": related_trip_id} if has_trip else None,
                    "action_options": item.action_options or [],
                    "related_trip_id": related_trip_id,
                    "sub_items": sub_items,
                    "group_key": self._suggestion_group_key(item, member_names),
                    "group_label": "",
                })

            # ---- Remaining PendingActions as standalone suggestion cards ----
            pa_type_tags = {
                "suggest_meeting": ("👥", "会面建议", "#1976D2"),
                "suggest_greeting": ("💌", "祝福建议", "#7B1FA2"),
                "suggest_gift": ("🎁", "礼物建议", "#E65100"),
                "suggest_defer": ("⏸️", "延期建议", "#00796B"),
            }
            for pa_item in pending_suggest_items:
                at = pa_item["action_type"]
                emoji, label, color = pa_type_tags.get(at, ("💡", "建议", "#1976D2"))
                suggestions.append({
                    "id": pa_item["pa_id"],
                    "insight_id": "",
                    "title": pa_item["label"],
                    "description": pa_item["description"],
                    "tag_emoji": emoji,
                    "tag_label": label,
                    "tag_color": color,
                    "action_label": "确认",
                    "action_type": "confirm_pending_action",
                    "action_data": {"pending_action_id": pa_item["pa_id"]},
                    "action_options": [],
                    "related_trip_id": pa_item.get("trip_id"),
                    "sub_items": [],
                    "group_key": f"id:{pa_item['pa_id']}",
                    "group_label": "",
                })

            self._assign_group_labels(suggestions)
            return suggestions

        except Exception:
            logger.error("_future_view_suggestions failed", exc_info=True)
            return []

    @staticmethod
    def _resolve_insight_tag(insight_type: str) -> tuple[str, str, str]:
        """Return (emoji, label, hex_color) for an insight type."""
        if insight_type in ("relationship_maintenance", "correlation", "followup"):
            return "💝", _INSIGHT_TYPE_LABELS.get(insight_type, "关系维护"), "#D32F2F"
        if insight_type == "event_preparation":
            return "📋", _INSIGHT_TYPE_LABELS.get(insight_type, "事件准备"), "#E65100"
        if insight_type in ("observation", "pattern_observation"):
            return "🔍", _INSIGHT_TYPE_LABELS.get(insight_type, "洞察"), "#00796B"
        if insight_type == "reminder":
            return "⏰", _INSIGHT_TYPE_LABELS.get(insight_type, "提醒"), "#7B1FA2"
        return "💡", _INSIGHT_TYPE_LABELS.get(insight_type, "建议"), "#1976D2"

    @staticmethod
    def _parse_content_sub_items(
        content: str, insight_id: str, related_trip_id: str | None,
    ) -> list[dict]:
        """Parse insight content to extract individual actionable items.

        Handles patterns like:
          "可顺便处理：去看看李思远、去看看孙浩。"
          "建议：X、Y、Z"
          "包括：A；B；C"
        """
        import re

        patterns = [
            r'(?:可顺便处理|可以考虑|建议|推荐|需要)[：:]\s*(.+?)(?:。|$)',
            r'(?:包括|如|比如)[：:]\s*(.+?)(?:。|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if not match:
                continue
            items_text = match.group(1).strip()
            items = [
                item.strip()
                for item in re.split(r'[、，,；;]', items_text)
                if item.strip()
            ]
            if len(items) < 2:
                continue

            return [
                {
                    "id": f"{insight_id}_sub_{i}",
                    "label": item,
                    "description": "",
                    "action_type": "add_to_trip" if related_trip_id else "acknowledge",
                    "is_pending_action": False,
                }
                for i, item in enumerate(items)
            ]

        return []

    _DATE_TYPE_EMOJIS: dict[str, str] = {
        "birthday": "🎂",
        "anniversary": "💍",
        "wedding": "💒",
        "holiday": "🎊",
        "meeting": "👥",
        "deadline": "🚩",
        "memorial": "🕯️",
    }

    # Chinese public holidays (approximate lunar dates for 2026)
    _PUBLIC_HOLIDAYS: list[tuple] = [
        # (month, day, title, recurring_annually)
        (1, 1, "元旦", True),
        (2, 14, "情人节", True),
        (2, 17, "春节", False),       # 2026 Chinese New Year
        (3, 8, "妇女节", True),
        (4, 5, "清明节", True),        # usually April 4-6
        (5, 1, "劳动节", True),
        (5, 4, "青年节", True),
        (5, 31, "端午节", False),      # 2026
        (6, 1, "儿童节", True),
        (8, 22, "七夕", False),        # 2026
        (9, 10, "教师节", True),
        (9, 21, "中秋节", False),      # 2026
        (10, 1, "国庆节", True),
        (10, 25, "重阳节", False),     # 2026
        (12, 25, "圣诞节", True),
    ]

    async def _build_all_upcoming(
        self,
        *,
        family_id: UUID,
        exclude_trip_ids: set | None = None,
    ) -> list[dict]:
        """Build full sorted list of upcoming items (dates + holidays).

        Excludes trips that are already shown in the 近期行程 section.
        """
        from ...date_manager.date_models import ImportantDate

        today = local_today()
        upcoming: list[dict] = []

        # --- Important dates from DB ---
        try:
            stmt = select(ImportantDate).where(
                ImportantDate.family_id == family_id,
            )
            result = await self.session.execute(stmt)
            all_dates = result.scalars().all()

            existing_titles: set[str] = set()

            for imp_date in all_dates:
                try:
                    next_occ = imp_date.get_next_occurrence()
                except Exception:
                    next_occ = None

                if next_occ is None or next_occ < today:
                    continue

                days_until = (next_occ - today).days
                date_type_str = str(imp_date.date_type or "").strip().lower()
                context_hint = (
                    imp_date.notes
                    or self._DATE_TYPE_CONTEXT_HINTS.get(date_type_str, "")
                )
                dot_color = "#E65100"
                if date_type_str in ("birthday", "anniversary", "wedding"):
                    dot_color = "#D32F2F"

                date_label = f"{next_occ.month}月{next_occ.day}日"
                emoji = self._DATE_TYPE_EMOJIS.get(date_type_str, "📅")
                title = imp_date.title or ""

                upcoming.append({
                    "id": str(imp_date.id),
                    "title": title,
                    "emoji": emoji,
                    "date_label": date_label,
                    "date_type": date_type_str,
                    "days_until": days_until,
                    "context_hint": context_hint,
                    "dot_color": dot_color,
                })
                existing_titles.add(title.strip().lower())
        except Exception:
            logger.warning("Failed to load ImportantDate for upcoming", exc_info=True)
            existing_titles = set()

        # --- Public holidays (supplement, avoid duplicates) ---
        current_year = today.year
        for month, day, title, _recurring in self._PUBLIC_HOLIDAYS:
            try:
                holiday_date = date(current_year, month, day)
            except ValueError:
                continue
            if holiday_date < today:
                # Try next year for recurring holidays
                try:
                    holiday_date = date(current_year + 1, month, day)
                except ValueError:
                    continue
            if holiday_date < today:
                continue

            # Skip if already in DB dates
            if title.strip().lower() in existing_titles:
                continue

            days_until = (holiday_date - today).days
            upcoming.append({
                "id": f"holiday_{month}_{day}",
                "title": title,
                "emoji": "🎊",
                "date_label": f"{holiday_date.month}月{holiday_date.day}日",
                "date_type": "holiday",
                "days_until": days_until,
                "context_hint": "",
                "dot_color": "#E65100",
            })

        # Sort by days_until
        upcoming.sort(key=lambda x: x["days_until"])
        return upcoming

    async def _future_view_upcoming(
        self,
        *,
        family_id: UUID,
        max_days: int | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[dict], bool]:
        """Upcoming important dates + holidays, paginated.

        Args:
            max_days: Only return items within this many days (e.g. 30).
            offset/limit: Standard pagination (applied after max_days filter).

        Returns (items, has_more).
        """
        try:
            all_items = await self._build_all_upcoming(family_id=family_id)

            if max_days is not None:
                filtered = [i for i in all_items if i["days_until"] <= max_days]
                has_more = len(all_items) > len(filtered)
                return filtered, has_more

            if limit is not None:
                page = all_items[offset:offset + limit]
                has_more = (offset + limit) < len(all_items)
                return page, has_more

            return all_items, False
        except Exception:
            logger.error("_future_view_upcoming failed", exc_info=True)
            return [], False

    async def get_future_view_upcoming_page(
        self,
        *,
        family_id: UUID,
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
        """Paginated upcoming items endpoint (for lazy loading beyond initial 30 days)."""
        items, has_more = await self._future_view_upcoming(
            family_id=family_id,
            offset=offset,
            limit=limit,
        )
        return {
            "items": items,
            "has_more": has_more,
            "total": offset + len(items) + (1 if has_more else 0),
        }

    async def _future_view_members(
        self,
        *,
        family_id: UUID,
    ) -> list:
        """Family members with relationship info and status lines."""
        try:
            from ...member.models.member import Member
            from ...member.models.member import MemberRelation

            stmt = (
                select(Member)
                .where(and_(
                    Member.family_id == family_id,
                    Member.is_deleted.is_(False),
                ))
                .order_by(Member.created_at)
                .limit(5)
            )
            result = await self.session.execute(stmt)
            members = list(result.scalars().all())

            if not members:
                return []

            member_ids = [m.id for m in members]

            # Batch query relationships
            rel_stmt = select(MemberRelation).where(and_(
                MemberRelation.family_id == family_id,
                or_(
                    MemberRelation.from_member_id.in_(member_ids),
                    MemberRelation.to_member_id.in_(member_ids),
                ),
            ))
            rel_result = await self.session.execute(rel_stmt)
            all_relations = list(rel_result.scalars().all())

            # Build relation lookup: member_id -> relation_type string
            relation_by_member: dict[UUID, str] = {}
            for rel in all_relations:
                rel_type = str(
                    rel.relation_type.value
                    if hasattr(rel.relation_type, "value")
                    else rel.relation_type
                )
                if rel.from_member_id in member_ids:
                    relation_by_member.setdefault(
                        rel.from_member_id, rel_type,
                    )
                if rel.to_member_id in member_ids:
                    relation_by_member.setdefault(
                        rel.to_member_id, rel_type,
                    )

            # Build status lines from nearest important dates
            from ...date_manager.date_models import ImportantDate

            today = local_today()

            date_stmt = select(ImportantDate).where(and_(
                ImportantDate.family_id == family_id,
                ImportantDate.member_id.in_(member_ids),
            ))
            date_result = await self.session.execute(date_stmt)
            all_member_dates = list(date_result.scalars().all())

            nearest_date_by_member: dict[UUID, str] = {}
            for imp_date in all_member_dates:
                if imp_date.member_id is None:
                    continue
                try:
                    next_occ = imp_date.get_next_occurrence()
                except Exception:
                    continue
                if next_occ is None or next_occ < today:
                    continue
                days_until = (next_occ - today).days
                status_line = f"{imp_date.title} · {days_until}天后"
                existing = nearest_date_by_member.get(imp_date.member_id)
                if existing is None:
                    nearest_date_by_member[imp_date.member_id] = status_line
                # Keep the nearest one (check days_until)

            members_data: list[dict] = []
            for member in members:
                # Deterministic color from member ID
                color_idx = hash(str(member.id)) % len(self._AVATAR_PALETTE)
                avatar_color = self._AVATAR_PALETTE[color_idx]

                relationship = relation_by_member.get(member.id)
                status_line = nearest_date_by_member.get(member.id)

                # Extract initial from name (first character)
                name_str = member.name or ""
                avatar_initial = name_str[0] if name_str else "?"

                members_data.append({
                    "id": str(member.id),
                    "name": name_str,
                    "nickname": member.nickname,
                    "avatar_url": member.avatar_url,
                    "avatar_color": avatar_color,
                    "avatar_initial": avatar_initial,
                    "relationship": relationship,
                    "status_line": status_line,
                })

            return members_data

        except Exception:
            logger.error("_future_view_members failed", exc_info=True)
            return []
