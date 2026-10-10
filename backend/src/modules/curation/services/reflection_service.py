"""
Post-Session Reflection Service

Immediately after a session is archived, extract the entities discussed
(trips, people, dates) and trigger focused curation for only those entities.
This eliminates the up-to-24-hour delay of waiting for the next daily task.

Design:
- Fire-and-forget: all exceptions are caught and logged as warnings
- Graceful degrade: LLM failure returns empty entities, skipping curation
- Idempotent: TripCompletenessService and TriggerDispatcher handlers are
  idempotent by design (unique constraints on PreparationItem / EventAssociation)
- Cooldown: skips entities already reflected within REFLECTION_COOLDOWN_MINUTES
  (trips via DB check, members/dates via in-process monotonic cache)
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.utils.timezone import utc_now

logger = logging.getLogger(__name__)

# Configurable via environment variable
REFLECTION_COOLDOWN_MINUTES = int(
    os.getenv("POST_SESSION_REFLECTION_COOLDOWN_MINUTES", "30")
)
_COOLDOWN_SECONDS = REFLECTION_COOLDOWN_MINUTES * 60
_ENTITY_EXTRACTION_PROMPT = """\
你是信息提取助手。从以下对话中提取结构化实体。

对话内容：{messages_text}

提取规则：
- trip_hints: 提取对话中提及的行程/出差/旅行信息，每条包含目的地(destination)和大致日期(date_hint)。若无则空列表。最多3条。
- member_names: 提取对话中出现的真实人名（非虚指），最多5个
- important_dates: 提取明确提到的具体日期（格式YYYY-MM-DD），最多3个
- completed_actions: 提取对话中已完成的行动，每条包含动作(action)、对象(entity)和原文片段(context)。
  - 寻找完成信号词：「已经」「已」「完成了」「搞定了」「办好了」「取消了」「不需要了」「不用了」
  - action 填: contacted（联系了某人）/ booked（预订了）/ cancelled（取消了）/ resolved（解决了）
  - entity 填: 人名或地点名称
  - context 填: 包含完成信号的原文片段（不超过20字）
  - 仅在有明确完成信号时提取，不能仅凭提及判断已完成。若无则空列表。最多3条。

输出严格JSON（若无则用空列表）：
{{"trip_hints": [{{"destination": "上海", "date_hint": "下周五"}}], "member_names": [], "important_dates": [], "completed_actions": [{{"action": "contacted", "entity": "李明", "context": "已经给李明打过电话"}}]}}"""

_MAX_MESSAGES_TEXT_CHARS = 4000

# In-process cooldown cache for members/dates (persists within worker lifetime).
# Key: (family_id_str, entity_type, entity_key) → monotonic timestamp of last run.
# This handles rapid-fire session archives; cross-worker dedup is covered by
# the idempotent design of association discovery and date_approaching dispatch.
_reflection_cooldown_cache: dict[tuple, float] = {}


@dataclass(frozen=True)
class SessionEntities:
    """Immutable set of entities extracted from a conversation session."""

    trip_hints: tuple  # [{"destination": "上海", "date_hint": "..."}]
    member_names: tuple  # tuple of str
    important_dates: tuple  # tuple of str
    completed_actions: tuple = ()  # tuple of dicts: {"action": "contacted", "entity": "李明", "context": "已经给李明打过电话"}

    @property
    def is_empty(self) -> bool:
        return not (self.trip_hints or self.member_names or self.important_dates or self.completed_actions)


_EMPTY_ENTITIES = SessionEntities(
    trip_hints=(),
    member_names=(),
    important_dates=(),
    completed_actions=(),
)


class PostSessionReflectionService:
    """Extracts session entities and triggers focused curation immediately."""

    def __init__(self, db: AsyncSession, llm_provider=None):
        self._db = db
        self._llm_provider = llm_provider

    async def reflect(
        self,
        session_id: UUID,
        user_id: UUID,
        family_id: UUID,
    ) -> None:
        """Main entry point: extract entities then trigger focused curation.

        Designed as fire-and-forget — all exceptions are silently logged.
        """
        try:
            entities = await self._extract_entities(session_id)
            if entities.is_empty:
                logger.debug(
                    "post_session_reflection: no entities in session %s, skipping",
                    session_id,
                )
                return
            # Dismiss insights fulfilled by conversation actions (non-blocking)
            try:
                dismissed_count = await self._dismiss_fulfilled_insights(user_id, entities)
                if dismissed_count > 0:
                    logger.info(
                        "Session %s: auto-dismissed %d fulfilled insights",
                        session_id,
                        dismissed_count,
                    )
            except Exception as e:
                logger.warning("Fulfillment check failed (non-blocking): %s", e)
            await self._focused_curation(entities, family_id)
            logger.info(
                "post_session_reflection: completed for session %s "
                "(trip_hints=%d, members=%d, dates=%d)",
                session_id,
                len(entities.trip_hints),
                len(entities.member_names),
                len(entities.important_dates),
            )
        except Exception as exc:
            logger.warning(
                "post_session_reflection: failed for session %s: %s",
                session_id,
                exc,
            )

    async def _extract_entities(self, session_id: UUID) -> SessionEntities:
        """Use Haiku to extract entities from session messages.

        Returns empty entities on any failure (graceful degrade).
        """
        from ...conversation.models import ConversationMessage

        try:
            result = await self._db.execute(
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.created_at)
            )
            messages = result.scalars().all()
            if not messages:
                return _EMPTY_ENTITIES

            messages_text = self._build_messages_text(messages)
            return await self._call_haiku_for_entities(messages_text)
        except Exception as exc:
            logger.warning(
                "post_session_reflection: entity extraction failed "
                "for session %s: %s",
                session_id,
                exc,
            )
            return _EMPTY_ENTITIES

    def _build_messages_text(self, messages: list) -> str:
        """Concatenate role: content pairs, truncated to avoid token overflow."""
        lines = [f"{m.role}: {m.content}" for m in messages if m.content]
        text = "\n".join(lines)
        return text[:_MAX_MESSAGES_TEXT_CHARS]

    async def _call_haiku_for_entities(self, messages_text: str) -> SessionEntities:
        """Call Haiku with the entity extraction prompt; parse JSON response."""
        from ....config.settings import settings
        from ....core.llm.haiku_client import get_haiku_client

        client = get_haiku_client()
        prompt = _ENTITY_EXTRACTION_PROMPT.format(messages_text=messages_text)
        response = await client.messages.create(
            model=settings.fast_worker_model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text_parts = [
            block.text
            for block in response.content
            if hasattr(block, "text")
        ]
        if not text_parts:
            return _EMPTY_ENTITIES

        raw = text_parts[0].strip()
        # Strip optional markdown code fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        data = json.loads(raw)
        raw_hints = data.get("trip_hints", [])
        trip_hints = tuple(
            {"destination": str(h.get("destination", "")), "date_hint": str(h.get("date_hint", ""))}
            for h in raw_hints
            if isinstance(h, dict) and h.get("destination")
        )
        raw_actions = data.get("completed_actions", [])
        completed_actions = tuple(
            {
                "action": str(a.get("action", "")),
                "entity": str(a.get("entity", "")),
                "context": str(a.get("context", "")),
            }
            for a in raw_actions
            if isinstance(a, dict) and a.get("entity")
        )
        return SessionEntities(
            trip_hints=trip_hints,
            member_names=tuple(str(n) for n in data.get("member_names", [])),
            important_dates=tuple(
                str(d) for d in data.get("important_dates", [])
            ),
            completed_actions=completed_actions,
        )

    async def _focused_curation(
        self,
        entities: SessionEntities,
        family_id: UUID,
    ) -> None:
        """Dispatch focused curation for each extracted entity type."""
        if entities.trip_hints:
            await self._check_trip_completeness_from_hints(
                entities.trip_hints, family_id
            )
        for entity_type, values, handler in (
            ("members", entities.member_names, self._trigger_memory_associations),
            ("dates", entities.important_dates, self._trigger_date_approaching),
        ):
            if not values:
                continue
            if self._is_entity_in_cooldown(family_id, entity_type, values):
                logger.debug(
                    "post_session_reflection: %s %s in cooldown, skipping",
                    entity_type, values,
                )
                continue
            await handler(values, family_id)

    @staticmethod
    def _is_entity_in_cooldown(
        family_id: UUID,
        entity_type: str,
        entity_values: tuple,
    ) -> bool:
        """Check in-process cooldown cache for members/dates entities.

        Returns True if the same (family, entity_type, sorted_values) was
        processed within REFLECTION_COOLDOWN_MINUTES. Automatically registers
        the current timestamp when not in cooldown.
        """
        sorted_key = tuple(sorted(str(v) for v in entity_values))
        cache_key = (str(family_id), entity_type, sorted_key)
        now = time.monotonic()
        last_run = _reflection_cooldown_cache.get(cache_key)
        if last_run is not None and (now - last_run) < _COOLDOWN_SECONDS:
            return True
        _reflection_cooldown_cache[cache_key] = now
        return False

    async def _resolve_trip_hints_to_ids(
        self,
        trip_hints: tuple[dict, ...],
        family_id: UUID,
    ) -> list[UUID]:
        """Resolve LLM-extracted trip hints (destination keywords) to real trip IDs.

        Queries active TripPlan records matching any extracted destination keyword.
        """
        from ...trip.models.trip_plan import TripPlan

        destinations = [
            h["destination"] for h in trip_hints if h.get("destination")
        ]
        if not destinations:
            return []

        from .query_utils import escape_like

        dest_filters = [
            TripPlan.destination.ilike(f"%{escape_like(d)}%", escape="\\")
            for d in destinations
        ]
        name_filters = [
            TripPlan.trip_name.ilike(f"%{escape_like(d)}%", escape="\\")
            for d in destinations
        ]

        now = utc_now()
        result = await self._db.execute(
            select(TripPlan.trip_id).where(
                and_(
                    TripPlan.family_id == family_id,
                    TripPlan.status.in_(["planning", "confirmed", "in_progress"]),
                    TripPlan.end_date >= now.date(),
                    or_(*dest_filters, *name_filters),
                )
            )
        )
        trip_ids = [row[0] for row in result.all()]
        logger.debug(
            "post_session_reflection: resolved %d trip hints → %d trip IDs",
            len(destinations),
            len(trip_ids),
        )
        return trip_ids

    async def _check_trip_completeness_from_hints(
        self,
        trip_hints: tuple[dict, ...],
        family_id: UUID,
    ) -> None:
        """Resolve trip hints to IDs, then run completeness checks."""
        from .trip_completeness_service import TripCompletenessService

        trip_ids = await self._resolve_trip_hints_to_ids(trip_hints, family_id)
        if not trip_ids:
            return

        service = TripCompletenessService(self._db, self._llm_provider)
        for trip_id in trip_ids:
            if await self._is_trip_in_cooldown(trip_id, family_id):
                logger.debug(
                    "post_session_reflection: trip %s in cooldown, skipping",
                    trip_id,
                )
                continue

            try:
                result = await service.check_completeness(trip_id, family_id)
                if result:
                    logger.info(
                        "post_session_reflection: trip %s completeness checked "
                        "(gaps=%d)",
                        trip_id,
                        len(result.gaps) if hasattr(result, "gaps") else 0,
                    )
            except Exception as exc:
                logger.warning(
                    "post_session_reflection: completeness check failed "
                    "for trip %s: %s",
                    trip_id,
                    exc,
                )

    async def _trigger_memory_associations(
        self,
        member_names: tuple[str, ...],
        family_id: UUID,
    ) -> None:
        """Validate mentioned members exist, then run association discovery.

        The member lookup serves as an early-exit gate: if none of the
        extracted names resolve to real family members, we skip the
        (more expensive) event query and association discovery entirely.

        Note: CuratedEvent has no direct member_id foreign key, so we
        cannot filter events by member. Association discovery itself
        (inside SecretaryCurationService._discover_associations) handles
        the member-to-event matching via rule engine and LLM.
        """
        from ...member.models import Member
        from ..models import CuratedEvent
        from .query_utils import escape_like
        from .trigger_dispatcher import TriggerDispatcher

        if not member_names:
            return

        name_filters = [
            Member.name.ilike(f"%{escape_like(n)}%", escape="\\")
            for n in member_names
        ]
        result = await self._db.execute(
            select(Member).where(
                and_(
                    Member.family_id == family_id,
                    or_(*name_filters),
                )
            )
        )
        members = result.scalars().all()
        if not members:
            logger.debug(
                "post_session_reflection: no members matched names %s",
                member_names,
            )
            return

        matched_member_ids = [m.id for m in members]
        logger.debug(
            "post_session_reflection: matched %d members (ids=%s) for names %s",
            len(members),
            matched_member_ids,
            member_names,
        )

        now = utc_now()
        window_start = now - timedelta(days=7)
        window_end = now + timedelta(days=30)

        events_result = await self._db.execute(
            select(CuratedEvent).where(
                and_(
                    CuratedEvent.family_id == family_id,
                    CuratedEvent.is_active.is_(True),
                    CuratedEvent.normalized_start >= window_start,
                    CuratedEvent.normalized_start <= window_end,
                )
            )
        )
        active_events = events_result.scalars().all()
        if not active_events:
            logger.debug(
                "post_session_reflection: no active events for association discovery",
            )
            return

        dispatcher = TriggerDispatcher(
            self._db, llm_provider=self._llm_provider
        )
        total = 0
        for event in active_events:
            try:
                count = await dispatcher.discover_associations_for_event(
                    family_id, event
                )
                total += count
            except Exception as exc:
                logger.warning(
                    "post_session_reflection: association discovery failed "
                    "for event %s: %s",
                    event.id,
                    exc,
                )

        logger.info(
            "post_session_reflection: discovered %d associations "
            "for %d members across %d events",
            total,
            len(members),
            len(active_events),
        )

    async def _trigger_date_approaching(
        self,
        important_dates: tuple[str, ...],
        family_id: UUID,
    ) -> None:
        """Dispatch date_approaching triggers for each important date."""
        from datetime import date as date_type

        from .trigger_dispatcher import TriggerDispatcher
        from ....core.utils.timezone import local_today

        dispatcher = TriggerDispatcher(
            self._db, llm_provider=self._llm_provider
        )
        today = local_today()

        for date_str in important_dates:
            try:
                target = date_type.fromisoformat(date_str)
                days_until = (target - today).days
                await dispatcher.dispatch(
                    family_id=family_id,
                    trigger_type="date_approaching",
                    payload={
                        "title": date_str,
                        "days_until": days_until,
                        "source": "post_session_reflection",
                    },
                )
            except Exception as exc:
                logger.warning(
                    "post_session_reflection: date_approaching dispatch failed "
                    "for date %s: %s",
                    date_str,
                    exc,
                )

    async def _is_trip_in_cooldown(
        self,
        trip_id: UUID,
        family_id: UUID,
    ) -> bool:
        """Return True if a completeness check was run for this trip recently."""
        from .trip_completeness_service import TripCompletenessCheck

        cutoff = utc_now() - timedelta(minutes=REFLECTION_COOLDOWN_MINUTES)
        try:
            result = await self._db.execute(
                select(TripCompletenessCheck)
                .where(
                    and_(
                        TripCompletenessCheck.trip_id == trip_id,
                        TripCompletenessCheck.family_id == family_id,
                        TripCompletenessCheck.checked_at >= cutoff,
                    )
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None
        except (ProgrammingError, OperationalError) as exc:
            logger.debug(
                "post_session_reflection: cooldown check failed "
                "(table may not exist): %s",
                exc,
            )
            return False

    async def _dismiss_fulfilled_insights(
        self,
        user_id: UUID,
        entities: SessionEntities,
    ) -> int:
        """Dismiss insights that match completed actions from conversation.

        Looks up unified Insight records linked to the same person/location
        via insight_entities and marks them as acted.
        """
        from sqlalchemy import update as sa_update
        from ...insight.models import Insight, InsightEntity, InsightStatus

        if not entities.completed_actions:
            return 0

        persons = [
            a["entity"]
            for a in entities.completed_actions
            if a.get("action") in ("contacted",) and a.get("entity")
        ]
        locations = [
            a["entity"]
            for a in entities.completed_actions
            if a.get("action") in ("booked", "cancelled", "resolved") and a.get("entity")
        ]
        all_entities = [
            a["entity"]
            for a in entities.completed_actions
            if a.get("entity")
        ]
        search_persons = list(set(persons))
        search_locations = list(set(locations) | (set(all_entities) - set(persons)))

        if not search_persons and not search_locations:
            return 0

        # Find active insights linked to matching entities
        entity_conditions = []
        for person in search_persons:
            entity_conditions.append(
                and_(
                    InsightEntity.entity_type == "person",
                    InsightEntity.entity_id == person,
                )
            )
        for location in search_locations:
            entity_conditions.append(
                and_(
                    InsightEntity.entity_type == "location",
                    InsightEntity.entity_id == location,
                )
            )

        stmt = (
            select(Insight.id)
            .join(InsightEntity, InsightEntity.insight_id == Insight.id)
            .where(
                and_(
                    Insight.user_id == user_id,
                    Insight.status.in_([
                        InsightStatus.PENDING.value,
                        InsightStatus.ACTIVE.value,
                    ]),
                    or_(*entity_conditions),
                )
            )
        )
        result = await self._db.execute(stmt)
        matched_ids = [row[0] for row in result.all()]

        if not matched_ids:
            return 0

        now = utc_now()
        update_result = await self._db.execute(
            sa_update(Insight)
            .where(Insight.id.in_(matched_ids))
            .values(status=InsightStatus.ACTED.value, acted_at=now)
        )
        dismissed_count = update_result.rowcount

        if dismissed_count > 0:
            await self._db.commit()
            entity_labels = [a["entity"] for a in entities.completed_actions if a.get("entity")]
            logger.info(
                "Auto-dismissed %d insights via fulfillment matching: %s",
                dismissed_count,
                entity_labels,
            )

        return dismissed_count
