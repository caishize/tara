"""
Service that builds enriched context for the trip detail page.

Resolves participant UUIDs to names, loads preparation items,
fetches side activities from the event graph, and composes an AI
insight paragraph from all available context.

Weather data is now provided by background insight tasks (user_insights table)
rather than live API calls, eliminating ~5s latency from this endpoint.
"""
import logging
from datetime import timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.trip_plan import TripPlan
from ...member.models.member import Member, MemberRelation
from ...curation.models import CuratedEvent, EventAssociation, PreparationItem
from ...curation.services.association_text import (
    build_person_context_map,
    present_association_copy,
)
from ..schemas.trip_context import (
    ParticipantInfo,
    TripPreparationItem,
    WeatherAlert,
    SideActivityItem,
    RecommendationHighlight,
    TripContextResponse,
)

logger = logging.getLogger(__name__)

_ICON_MAP = {
    "task": "clipboard-list",
    "place": "map-pin",
    "date": "calendar",
    "memory": "brain",
    "person": "user",
}
_PRIORITY_DISPLAY = {
    "strongly_recommend": "high",
    "convenient": "medium",
    "optional": "low",
}
_GENERIC_CALENDAR_DATE_TYPES = frozenset({
    "holiday",
    "holiday_legal",
    "holiday_lunar",
    "holiday_solar_term",
    "solar_term",
})


class TripDetailContextService:
    """Builds enriched context for the trip detail page."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def build_context(
        self,
        trip: TripPlan,
        family_id: UUID,
    ) -> TripContextResponse:
        """Build the full trip context response.

        NOTE:
        A single AsyncSession does not support concurrent execute calls.
        Keep these fetches sequential to avoid IllegalStateChangeError /
        InvalidRequestError under load and in tests.
        """
        participants = await self._resolve_participants(trip, family_id)
        prep_result = await self._fetch_preparation_items(trip.trip_id)
        prep_items, curated_event_id = prep_result
        has_pending_preparation = any(not item.done for item in prep_items)
        side_activities = await self._fetch_side_activities(
            trip.trip_id,
            family_id,
            trip.created_by,
            allow_derived=has_pending_preparation,
        )
        weather = None

        rec_highlights = self._extract_recommendation_highlights(trip)
        insight_text = self._compose_insight_text(
            trip, participants, weather, prep_items, side_activities, rec_highlights,
        )

        return TripContextResponse(
            trip_id=trip.trip_id,
            participants=participants,
            weather=weather,
            preparation_items=prep_items,
            curated_event_id=curated_event_id,
            insight_text=insight_text,
            side_activities=side_activities,
            recommendation_highlights=rec_highlights,
        )

    # -------------------------------------------------------------------------
    # Participants
    # -------------------------------------------------------------------------

    async def _resolve_participants(
        self,
        trip: TripPlan,
        family_id: UUID,
    ) -> List[ParticipantInfo]:
        """Resolve participant UUIDs to names and context labels."""
        participant_ids = list(dict.fromkeys(trip.participants or []))
        if not participant_ids and trip.created_by:
            participant_ids = [trip.created_by]
        if not participant_ids:
            return []

        stmt = select(Member).where(
            and_(
                Member.id.in_(participant_ids),
                Member.family_id == family_id,
                Member.is_deleted == False,
            )
        )
        result = await self._db.execute(stmt)
        members = {m.id: m for m in result.scalars().all()}

        relation_map = await self._get_participant_relations(
            family_id=family_id,
            user_id=trip.created_by,
            participant_ids=participant_ids,
        )
        action_tags_map = await self._get_person_action_tags(
            trip.trip_id, user_id=trip.created_by,
        )

        participants = []
        for pid in participant_ids:
            member = members.get(pid)
            if not member:
                participants.append(ParticipantInfo(
                    id=pid,
                    name=str(pid)[:8],
                    relation="self" if pid == trip.created_by else None,
                ))
                continue

            relation = relation_map.get(member.id)
            if relation is None and member.id == trip.created_by:
                relation = "self"

            age = member.age if member.age is not None else member.calculate_age()
            is_child = self._is_child_participant(
                member=member,
                relation=relation,
                age=age,
            )
            location = member.primary_location
            tags = action_tags_map.get(str(member.id), [])

            parts = []
            if is_child and age is not None:
                parts.append(f"{age}岁")
            if location:
                parts.append(f"住{location}")
            if tags:
                parts.extend(tags)
            context_label = " \u00B7 ".join(parts) if parts else None

            participants.append(ParticipantInfo(
                id=member.id,
                name=member.name,
                nickname=member.nickname,
                relation=relation,
                age=age,
                is_child=is_child,
                context_label=context_label,
                action_tags=tags,
            ))

        return participants

    async def _get_participant_relations(
        self,
        *,
        family_id: UUID,
        user_id: UUID,
        participant_ids: List[UUID],
    ) -> dict[UUID, str]:
        """Resolve relation_type for participants from the trip creator's perspective."""
        if not participant_ids:
            return {}

        stmt = select(MemberRelation).where(
            and_(
                MemberRelation.family_id == family_id,
                MemberRelation.from_member_id == user_id,
                MemberRelation.to_member_id.in_(participant_ids),
            )
        )
        result = await self._db.execute(stmt)

        relation_map: dict[UUID, str] = {}
        for rel in result.scalars().all():
            relation_value = rel.relation_type
            relation_map[rel.to_member_id] = (
                relation_value.value
                if hasattr(relation_value, "value")
                else str(relation_value)
            )
        return relation_map

    @staticmethod
    def _is_child_participant(
        *,
        member: Member,
        relation: Optional[str],
        age: Optional[int],
    ) -> bool:
        """Heuristic child detection for trip participant insights."""
        child_relations = {"child", "son", "daughter", "grandson", "granddaughter", "grandchild"}
        if relation and relation in child_relations:
            return True
        if age is not None and age <= 12:
            return True

        raw_tags = member.tags or []
        if isinstance(raw_tags, list):
            normalized_tags = {str(tag).strip().lower() for tag in raw_tags}
            if {"child", "kid", "kids", "baby", "儿童", "小孩", "宝宝"} & normalized_tags:
                return True
        return False

    async def _get_person_action_tags(
        self,
        trip_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> dict:
        """Get action tags for person-type associations linked to this trip.

        Uses a single JOIN query instead of two separate queries (N+1 fix).
        Filters out the trip creator (user_id) to prevent self-referencing
        tags like "顺路拜访邻居Darwin" appearing on the user's own card.
        """
        stmt = (
            select(EventAssociation)
            .join(CuratedEvent, EventAssociation.source_event_id == CuratedEvent.id)
            .where(
                and_(
                    CuratedEvent.trip_id == trip_id,
                    CuratedEvent.status != "cancelled",
                    EventAssociation.target_type == "person",
                )
            )
        )
        result = await self._db.execute(stmt)
        associations = result.scalars().all()

        user_id_str = str(user_id) if user_id else None
        tags_map: dict = {}
        for assoc in associations:
            target_id = assoc.target_id
            if user_id_str and target_id == user_id_str:
                continue
            if target_id not in tags_map:
                tags_map[target_id] = []
            if assoc.title and assoc.title not in tags_map[target_id]:
                tags_map[target_id].append(assoc.title)

        return tags_map

    # -------------------------------------------------------------------------
    # Preparation Items
    # -------------------------------------------------------------------------

    async def _fetch_preparation_items(
        self,
        trip_id: UUID,
    ) -> tuple:
        """Load preparation items from the best active CuratedEvent for a trip.

        We may have multiple historical curated rows for one trip_id. To align
        with kanban cards, prefer active rows with pending preparation items.
        """
        stmt = (
            select(CuratedEvent)
            .options(selectinload(CuratedEvent.preparation_item_rows))
            .where(and_(
                CuratedEvent.trip_id == trip_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
            ))
            .order_by(CuratedEvent.normalized_start.asc(), CuratedEvent.updated_at.desc())
        )
        result = await self._db.execute(stmt)
        curated_events = result.scalars().all()

        if not curated_events:
            return [], None

        curated_event = next(
            (
                ev for ev in curated_events
                if any(not row.done for row in (ev.preparation_item_rows or []))
            ),
            None,
        )
        if curated_event is None:
            curated_event = next(
                (
                    ev for ev in curated_events
                    if any((row.text or "").strip() for row in (ev.preparation_item_rows or []))
                ),
                curated_events[0],
            )

        items = []
        for row in sorted(
            curated_event.preparation_item_rows,
            key=lambda r: r.sort_order,
        ):
            action_label = None
            if not row.done:
                action_label = "去看看"

            items.append(TripPreparationItem(
                key=str(row.key),
                text=row.text,
                done=row.done,
                source=row.source or "manual",
                action_label=action_label,
            ))

        return items, curated_event.id

    # -------------------------------------------------------------------------
    # Side Activities (顺便做的事情) from event graph
    # -------------------------------------------------------------------------

    async def _fetch_side_activities(
        self,
        trip_id: UUID,
        family_id: UUID,
        user_id: Optional[UUID] = None,
        *,
        allow_derived: bool = False,
    ) -> List[SideActivityItem]:
        """Fetch active associations as 'things to do along the way'.

        Uses a single JOIN query instead of two separate queries (N+1 fix).
        """
        stmt = (
            select(EventAssociation, CuratedEvent)
            .join(CuratedEvent, EventAssociation.source_event_id == CuratedEvent.id)
            .where(
                and_(
                    CuratedEvent.trip_id == trip_id,
                    CuratedEvent.status != "cancelled",
                    EventAssociation.is_dismissed == False,
                )
            )
            .order_by(
                EventAssociation.priority.asc(),
                EventAssociation.created_at.desc(),
            )
        )
        result = await self._db.execute(stmt)
        association_pairs = result.all()
        date_meta_by_target_id = await self._load_date_meta_for_association_pairs(
            association_pairs
        )
        person_context = await build_person_context_map(
            self._db,
            family_id=family_id,
            user_id=user_id,
            person_ids=[
                str(assoc.target_id)
                for assoc, _ in association_pairs
                if assoc.target_type == "person"
            ],
        )

        user_id_str = str(user_id) if user_id else None
        side_activities: List[SideActivityItem] = []
        seen_titles: set[str] = set()
        for assoc, source_event in association_pairs:
            # Exclude the trip creator from person-type suggestions
            if (
                user_id_str
                and assoc.target_type == "person"
                and assoc.target_id == user_id_str
            ):
                continue
            if not self._is_actionable_association(
                association=assoc,
                source_event=source_event,
                family_id=family_id,
                date_meta_by_target_id=date_meta_by_target_id,
            ):
                continue
            person_ctx = (
                person_context.get(str(assoc.target_id))
                if assoc.target_type == "person"
                else None
            )
            display_title, display_reason = present_association_copy(
                title=assoc.title,
                reason=assoc.reason,
                target_type=assoc.target_type,
                source_location=source_event.location or source_event.city,
                person_context=person_ctx,
            )
            # Title-level dedup: skip if we already have an activity with the
            # same display title (e.g. multiple co-resident family members
            # both producing "返程后给家里带份当地小礼物").
            title_key = display_title.strip()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            side_activities.append(
                SideActivityItem(
                    id=str(assoc.id),
                    title=display_title,
                    reason=display_reason,
                    priority=_PRIORITY_DISPLAY.get(assoc.priority, "medium"),
                    target_type=assoc.target_type,
                    icon=_ICON_MAP.get(assoc.target_type, "link"),
                )
            )

        existing_titles = {
            (item.title or "").strip()
            for item in side_activities
            if item.title
        }
        derived_titles: List[str] = []
        if allow_derived and not side_activities:
            derived_titles = await self._derive_nearby_side_activity_titles(
                trip_id=trip_id,
                family_id=family_id,
                existing_titles=existing_titles,
            )
        for idx, title in enumerate(derived_titles):
            side_activities.append(
                SideActivityItem(
                    id=f"derived:{trip_id}:{idx}",
                    title=title,
                    reason="和近期安排时间挨得近，把要准备的事项一起确认会更省心。",
                    priority="medium",
                    target_type="task",
                    icon=_ICON_MAP.get("task", "link"),
                )
            )

        return side_activities

    async def _derive_nearby_side_activity_titles(
        self,
        *,
        trip_id: UUID,
        family_id: UUID,
        existing_titles: set[str],
        max_items: int = 2,
    ) -> List[str]:
        """Derive side activities from nearby event overlap to keep view consistency."""
        trip_stmt = (
            select(CuratedEvent)
            .options(selectinload(CuratedEvent.preparation_item_rows))
            .where(and_(
                CuratedEvent.trip_id == trip_id,
                CuratedEvent.status != "cancelled",
                CuratedEvent.is_active.is_(True),
            ))
            .order_by(CuratedEvent.normalized_start)
        )
        trip_result = await self._db.execute(trip_stmt)
        trip_events = [item for item in trip_result.scalars().all() if item.normalized_start]
        if not trip_events:
            return []

        trip_event_ids = {event.id for event in trip_events}
        start_anchor = min(event.normalized_start for event in trip_events)
        end_anchor = max(event.normalized_start for event in trip_events)
        window_start = start_anchor - timedelta(days=3)
        window_end = end_anchor + timedelta(days=3)

        other_stmt = (
            select(CuratedEvent)
            .options(selectinload(CuratedEvent.preparation_item_rows))
            .where(and_(
                CuratedEvent.family_id == family_id,
                CuratedEvent.status != "cancelled",
                CuratedEvent.is_active.is_(True),
                CuratedEvent.normalized_start >= window_start,
                CuratedEvent.normalized_start <= window_end,
                CuratedEvent.id.notin_(trip_event_ids),
            ))
            .order_by(CuratedEvent.normalized_start)
            .limit(30)
        )
        other_result = await self._db.execute(other_stmt)
        nearby_events = [item for item in other_result.scalars().all() if item.normalized_start]

        derived: List[str] = []
        for trip_event in trip_events:
            for other in nearby_events:
                day_gap = abs((other.normalized_start.date() - trip_event.normalized_start.date()).days)
                if day_gap > 3:
                    continue
                has_pending_prep = any(
                    (item.text or "").strip() and not item.done
                    for item in (other.preparation_item_rows or [])
                )
                if not has_pending_prep:
                    continue
                title = f"顺手把「{other.title}」前的准备事项一起确认"

                if title in existing_titles or title in derived:
                    continue
                derived.append(title)
                if len(derived) >= max_items:
                    return derived

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
        association: EventAssociation,
        source_event: CuratedEvent,
    ) -> bool:
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

    def _is_actionable_association(
        self,
        *,
        association: EventAssociation,
        source_event: CuratedEvent,
        family_id: UUID,
        date_meta_by_target_id: dict[str, dict[str, object]],
    ) -> bool:
        if association.target_type != "date":
            return not self._is_low_signal_association(
                association=association,
                source_event=source_event,
            )

        target_meta = date_meta_by_target_id.get(str(association.target_id))
        if self._is_actionable_date_association(
            date_meta=target_meta,
            family_id=family_id,
        ):
            return True

        if self._is_holiday_like_event_type(source_event.event_type):
            return False
        return str(association.priority or "").strip().lower() == "strongly_recommend"

    async def _load_date_meta_for_association_pairs(
        self,
        association_pairs: List[tuple[EventAssociation, CuratedEvent]],
    ) -> dict[str, dict[str, object]]:
        from ...date_manager.models import ImportantDate

        date_ids: set[UUID] = set()
        for assoc, _ in association_pairs:
            if assoc.target_type != "date":
                continue
            parsed = self._safe_uuid(assoc.target_id)
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
        result = await self._db.execute(stmt)

        meta: dict[str, dict[str, object]] = {}
        for row in result:
            meta[str(row.id)] = {
                "family_id": row.family_id,
                "date_type": str(row.date_type or "").strip().lower(),
                "importance_level": int(row.importance_level or 0),
            }
        return meta

    # -------------------------------------------------------------------------
    # Recommendation Highlights (from trip.recommendation_context)
    # -------------------------------------------------------------------------

    @staticmethod
    def _extract_recommendation_highlights(
        trip: TripPlan,
    ) -> List[RecommendationHighlight]:
        """Extract structured highlights from smart itinerary / AI planning."""
        ctx = trip.recommendation_context
        if not ctx or not isinstance(ctx, dict):
            return []

        highlights = []

        # People to meet
        people = ctx.get("people_to_meet")
        if isinstance(people, list):
            for person in people[:3]:
                if isinstance(person, dict):
                    name = person.get("name", "")
                    detail = person.get("detail") or person.get("reason", "")
                    if name:
                        highlights.append(RecommendationHighlight(
                            icon="user",
                            label=str(name),
                            detail=str(detail),
                            category="people",
                        ))

        # Accommodation
        accommodation = ctx.get("accommodation")
        if isinstance(accommodation, dict):
            name = accommodation.get("name") or accommodation.get("area", "")
            reason = accommodation.get("reason", "")
            if name:
                highlights.append(RecommendationHighlight(
                    icon="hotel",
                    label=str(name),
                    detail=str(reason),
                    category="accommodation",
                ))
        elif isinstance(accommodation, str) and accommodation:
            highlights.append(RecommendationHighlight(
                icon="hotel",
                label=accommodation,
                category="accommodation",
            ))

        # Budget allocation
        budget_alloc = ctx.get("budget_allocation")
        if isinstance(budget_alloc, dict) and budget_alloc:
            parts = []
            for key, value in budget_alloc.items():
                if isinstance(value, (int, float)) and value > 0:
                    parts.append(f"{key} \u00A5{int(value)}")
            if parts:
                highlights.append(RecommendationHighlight(
                    icon="wallet",
                    label="预算分配",
                    detail=" \u00B7 ".join(parts[:4]),
                    category="budget",
                ))

        # Travel tips
        tips = ctx.get("travel_tips")
        if isinstance(tips, list):
            for tip in tips[:2]:
                if isinstance(tip, str) and tip:
                    highlights.append(RecommendationHighlight(
                        icon="lightbulb",
                        label="贴士",
                        detail=tip,
                        category="tip",
                    ))

        # Design rationale
        rationale = ctx.get("design_rationale")
        if isinstance(rationale, str) and rationale:
            highlights.append(RecommendationHighlight(
                icon="sparkles",
                label="行程设计理念",
                detail=rationale,
                category="rationale",
            ))

        return highlights

    # -------------------------------------------------------------------------
    # AI Insight Text
    # -------------------------------------------------------------------------

    @staticmethod
    def _compose_insight_text(
        trip: TripPlan,
        participants: List[ParticipantInfo],
        weather: Optional[WeatherAlert],
        prep_items: List[TripPreparationItem],
        side_activities: List[SideActivityItem],
        rec_highlights: List[RecommendationHighlight],
    ) -> str:
        """Compose a natural-language insight paragraph from all context data.

        This acts as a 'secretary summary' — short, actionable, personalized.
        """
        lines = []

        # Participant insights — richer context
        self_participant = next(
            (p for p in participants if p.relation == "self"), None
        )
        other_participants = [p for p in participants if p.relation != "self"]
        if self_participant and self_participant.context_label:
            lines.append(f"{self_participant.nickname or self_participant.name}{self_participant.context_label}。")

        child_participants = [p for p in participants if p.is_child]
        if child_participants:
            names = "、".join((p.nickname or p.name) for p in child_participants[:2])
            age_text = "、".join(f"{p.age}岁" for p in child_participants[:2] if p.age is not None)
            if age_text:
                lines.append(
                    f"有儿童同行（{names}，{age_text}），建议优先亲子友好景点，并预留午休和补水节奏。"
                )
            else:
                lines.append(
                    f"有儿童同行（{names}），建议优先亲子友好景点，并预留午休和补水节奏。"
                )

        # Accommodation highlight
        for h in rec_highlights:
            if h.category == "accommodation" and h.detail:
                lines.append(f"建议住{h.label}，{h.detail}")
                break

        # Preparation progress — show ratio, not just list
        total_prep = len(prep_items)
        undone = [item for item in prep_items if not item.done]
        done_count = total_prep - len(undone)
        if total_prep > 0 and undone:
            undone_texts = [item.text for item in undone[:3]]
            lines.append(
                f"准备进度 {done_count}/{total_prep}，还需完成：{'、'.join(undone_texts)}。"
            )
        elif total_prep > 0 and not undone:
            lines.append(f"准备事项已全部完成（{total_prep}项），可以安心出发。")

        # Side activities — only show count as a hint; the full list is
        # rendered separately in the "顺便做的事情" section, so repeating
        # concrete titles here would be redundant.
        if side_activities:
            count = len(side_activities)
            if count == 1:
                lines.append(f"还有1件事可以顺便处理，详见下方。")
            else:
                lines.append(f"还有{count}件事可以顺便处理，详见下方。")

        # Design rationale
        for h in rec_highlights:
            if h.category == "rationale" and h.detail:
                lines.append(h.detail)
                break

        # Fallback if nothing found
        if not lines:
            duration = (trip.end_date - trip.start_date).days + 1
            lines.append(
                f"{duration}天行程，目的地{trip.destination}。"
            )

        return "\n".join(lines)
