"""Event detail service — enriched context for graph node detail.

Extracted from secretary/services/event_context_service.py (get_event_detail).
"""
from datetime import timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ....config.logging import get_logger
from ....core.utils.timezone import local_date_range_to_utc
from ...curation.models import CuratedEvent
from ...curation.services.association_text import (
    build_person_context_map,
    present_association_copy,
)
from ..kanban_schemas import (
    AssociationSummary,
    RelatedMemory,
    EventDetailResponse,
)
from ._event_converter import to_kanban_event, get_user_timezone

logger = get_logger(__name__)

_GENERIC_CALENDAR_DATE_TYPES = frozenset({
    "holiday",
    "holiday_legal",
    "holiday_lunar",
    "holiday_solar_term",
    "solar_term",
})


class EventDetailService:
    """Returns enriched event context: event data + associations + related memories."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_event_detail(
        self,
        event_id: UUID,
        family_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[EventDetailResponse]:
        """Return enriched event context for graph detail view."""
        stmt = (
            select(CuratedEvent)
            .options(selectinload(CuratedEvent.associations))
            .where(and_(
                CuratedEvent.id == event_id,
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
            ))
        )
        result = await self.session.execute(stmt)
        event = result.scalar_one_or_none()
        if not event:
            return None

        effective_start = event.normalized_start
        effective_end = event.normalized_end

        if event.trip_id and event.event_type in ("travel", "business_trip"):
            from ...trip.models.trip_plan import TripPlan

            plan_stmt = select(TripPlan).where(and_(
                TripPlan.trip_id == event.trip_id,
                TripPlan.status != "cancelled",
            ))
            plan_result = await self.session.execute(plan_stmt)
            plan = plan_result.scalar_one_or_none()
            if plan and plan.start_date and plan.end_date:
                tz_user_id = user_id or event.user_id
                user_tz = await get_user_timezone(self.session, tz_user_id) if tz_user_id else None
                effective_start, effective_end = local_date_range_to_utc(
                    plan.start_date,
                    plan.end_date,
                    user_tz,
                )

        kanban_ev = to_kanban_event(
            event,
            effective_start=effective_start,
            effective_end=effective_end,
        )

        active_associations = [
            assoc
            for assoc in (event.associations or [])
            if not assoc.is_dismissed
        ]
        date_meta_by_target_id = await self._load_date_meta_for_associations(
            active_associations,
        )
        actionable_associations = self._filter_actionable_associations(
            source_event=event,
            associations=active_associations,
            family_id=family_id,
            date_meta_by_target_id=date_meta_by_target_id,
        )
        person_context = await build_person_context_map(
            self.session,
            family_id=family_id,
            user_id=user_id or event.user_id,
            person_ids=[
                str(assoc.target_id)
                for assoc in actionable_associations
                if assoc.target_type == "person"
            ],
        )

        associations: List[AssociationSummary] = []
        for assoc in actionable_associations:
            person_ctx = (
                person_context.get(str(assoc.target_id))
                if assoc.target_type == "person"
                else None
            )
            display_title, display_reason = present_association_copy(
                title=assoc.title,
                reason=assoc.reason,
                target_type=assoc.target_type,
                source_location=event.location or event.city,
                person_context=person_ctx,
            )
            associations.append(
                AssociationSummary(
                    id=str(assoc.id),
                    title=display_title,
                    association_type=assoc.association_type,
                    target_type=assoc.target_type,
                    reason=display_reason,
                    priority=assoc.priority,
                    is_confirmed=assoc.is_confirmed,
                    is_dismissed=assoc.is_dismissed,
                )
            )
        existing_assoc_titles = {
            (assoc.title or "").strip()
            for assoc in associations
            if assoc.title
        }

        has_pending_prep = any(
            (item.item or "").strip() and not item.done
            for item in (kanban_ev.preparation_items or [])
        )
        derived_titles: List[str] = []
        if has_pending_prep and not associations:
            derived_titles = await self._derive_nearby_event_titles(
                current_event=kanban_ev,
                family_id=family_id,
                exclude_event_id=event.id,
            )
        for idx, title in enumerate(derived_titles):
            if title in existing_assoc_titles:
                continue
            associations.append(
                AssociationSummary(
                    id=f"derived:{event.id}:{idx}",
                    title=title,
                    association_type="temporal",
                    target_type="task",
                    reason="和近期安排时间挨得近，把要准备的事项一起确认会更省心。",
                    priority="convenient",
                    is_confirmed=False,
                    is_dismissed=False,
                )
            )

        related_memories: List[RelatedMemory] = []
        try:
            from ...memory.models import ConversationMemory

            memory_conditions = [
                ConversationMemory.family_id == family_id,
                ConversationMemory.status == "active",
            ]

            entity_filters = []
            if event.trip_id:
                entity_filters.append(
                    ConversationMemory.entities["trip_id"].astext == str(event.trip_id)
                )
            if event.location:
                entity_filters.append(
                    ConversationMemory.entities["location"].astext == event.location
                )
            if event.city:
                entity_filters.append(
                    ConversationMemory.entities["location"].astext == event.city
                )

            if entity_filters:
                memory_conditions.append(or_(*entity_filters))

                mem_stmt = (
                    select(ConversationMemory)
                    .where(and_(*memory_conditions))
                    .order_by(ConversationMemory.created_at.desc())
                    .limit(10)
                )
                mem_result = await self.session.execute(mem_stmt)
                memories = mem_result.scalars().all()

                # Deduplicate by ID and by content similarity.
                # Memories from the same conversation can have near-identical
                # summaries (e.g. "更新了XX之旅" variants) — keep only one.
                seen_ids: set = set()
                seen_prefixes: set = set()
                for m in memories:
                    mid = str(m.id)
                    if mid in seen_ids:
                        continue
                    seen_ids.add(mid)

                    # Content-based dedup: use first 20 chars of summary
                    summary = m.summary or ""
                    prefix = summary[:20]
                    if prefix and prefix in seen_prefixes:
                        continue
                    if prefix:
                        seen_prefixes.add(prefix)

                    related_memories.append(
                        RelatedMemory(
                            id=mid,
                            memory_type=m.memory_type,
                            summary=summary,
                            content=m.content,
                            created_at=m.created_at,
                        )
                    )
        except Exception:
            logger.exception("Failed to fetch related memories for event %s", event_id)

        return EventDetailResponse(
            event=kanban_ev,
            associations=associations,
            related_memories=related_memories,
        )

    async def _derive_nearby_event_titles(
        self,
        *,
        current_event,
        family_id: UUID,
        exclude_event_id: UUID,
        max_items: int = 2,
    ) -> List[str]:
        """Derive lightweight nearby-event links for detail consistency."""
        current_start = current_event.start_time
        if current_start is None:
            return []

        window_start = current_start - timedelta(days=3)
        window_end = current_start + timedelta(days=3)

        stmt = (
            select(CuratedEvent)
            .options(selectinload(CuratedEvent.preparation_item_rows))
            .where(and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
                CuratedEvent.id != exclude_event_id,
                CuratedEvent.normalized_start >= window_start,
                CuratedEvent.normalized_start <= window_end,
            ))
            .order_by(CuratedEvent.normalized_start)
            .limit(20)
        )
        result = await self.session.execute(stmt)
        nearby_events = result.scalars().all()
        nearby_kanban = [to_kanban_event(item) for item in nearby_events]
        return self._derive_association_titles(
            current_event=current_event,
            nearby_events=nearby_kanban,
            max_items=max_items,
        )

    @staticmethod
    def _derive_association_titles(
        *,
        current_event,
        nearby_events,
        max_items: int = 2,
    ) -> List[str]:
        if current_event.start_time is None:
            return []

        derived: List[str] = []

        for other in nearby_events:
            if other.start_time is None:
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
    def _safe_uuid(value: object) -> Optional[UUID]:
        if value is None:
            return None
        try:
            return UUID(str(value))
        except Exception:
            return None

    @staticmethod
    def _is_holiday_like_event_type(event_type: Optional[str]) -> bool:
        normalized = str(event_type or "").strip().lower()
        return normalized in {"holiday", "holiday_solar_term", "solar_term"}

    @classmethod
    def _is_actionable_date_association(
        cls,
        *,
        date_meta: Optional[dict[str, object]],
        family_id: UUID,
    ) -> bool:
        if not date_meta:
            return False

        date_type = str(date_meta.get("date_type") or "").strip().lower()
        if not date_type:
            return False
        if date_type not in _GENERIC_CALENDAR_DATE_TYPES:
            return True

        same_family = str(date_meta.get("family_id")) == str(family_id)
        importance = int(date_meta.get("importance_level") or 0)
        return same_family and importance >= 8

    @classmethod
    def _is_low_signal_association(
        cls,
        *,
        source_event: CuratedEvent,
        association: object,
    ) -> bool:
        target_type = str(getattr(association, "target_type", "") or "").strip().lower()
        assoc_type = str(getattr(association, "association_type", "") or "").strip().lower()
        priority = str(getattr(association, "priority", "") or "").strip().lower()

        if target_type in {"person", "memory", "place"}:
            return False

        source_is_holiday_like = cls._is_holiday_like_event_type(source_event.event_type)
        if assoc_type == "temporal" and target_type in {"task", "date"}:
            if source_is_holiday_like:
                return True
            return priority != "strongly_recommend"
        return False

    def _filter_actionable_associations(
        self,
        *,
        source_event: CuratedEvent,
        associations: List[object],
        family_id: UUID,
        date_meta_by_target_id: dict[str, dict[str, object]],
    ) -> List[object]:
        actionable: List[object] = []
        source_is_holiday_like = self._is_holiday_like_event_type(source_event.event_type)

        for assoc in associations:
            if getattr(assoc, "target_type", None) != "date":
                if self._is_low_signal_association(
                    source_event=source_event,
                    association=assoc,
                ):
                    continue
                actionable.append(assoc)
                continue

            target_meta = date_meta_by_target_id.get(str(getattr(assoc, "target_id", "")))
            if self._is_actionable_date_association(
                date_meta=target_meta,
                family_id=family_id,
            ):
                actionable.append(assoc)
                continue

            if source_is_holiday_like:
                continue

            if str(getattr(assoc, "priority", "") or "").strip().lower() == "strongly_recommend":
                actionable.append(assoc)

        return actionable

    async def _load_date_meta_for_associations(
        self,
        associations: List[object],
    ) -> dict[str, dict[str, object]]:
        from ...date_manager.models import ImportantDate

        date_ids: set[UUID] = set()
        for assoc in associations:
            if getattr(assoc, "target_type", None) != "date":
                continue
            parsed = self._safe_uuid(getattr(assoc, "target_id", None))
            if parsed is not None:
                date_ids.add(parsed)

        if not date_ids:
            return {}

        stmt = select(
            ImportantDate.id,
            ImportantDate.family_id,
            ImportantDate.date_type,
            ImportantDate.importance_level,
        ).where(ImportantDate.id.in_(list(date_ids)))
        result = await self.session.execute(stmt)

        meta: dict[str, dict[str, object]] = {}
        for row in result:
            meta[str(row.id)] = {
                "family_id": row.family_id,
                "date_type": str(row.date_type or "").strip().lower(),
                "importance_level": int(row.importance_level or 0),
            }
        return meta
