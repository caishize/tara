"""Unified insight query entry point.

All consumers (kanban, member detail, trip detail, briefing, sidekick)
query insights through this service.  Operates on the unified ``insights``
and ``insight_entities`` tables (migration 120).
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .dynamic_priority import DynamicPriorityAdjuster, UserQueryContext
from .models import Insight, InsightEntity

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------


class InsightEntityRef(BaseModel):
    """Lightweight reference to a related domain entity."""

    entity_type: str
    entity_id: UUID
    role: str = "related"

    class Config:
        from_attributes = True


class InsightCard(BaseModel):
    """DTO for insight display across all consumers."""

    id: UUID
    insight_type: str
    title: str
    content: str
    importance: int
    urgency: int
    status: str
    suggested_action: Optional[str] = None
    action_options: Optional[list] = None
    delivered_via_briefing: bool = False
    delivered_via_sidekick: bool = False
    delivered_via_kanban: bool = False
    delivered_via_push: bool = False
    created_at: datetime
    expires_at: Optional[datetime] = None
    entities: List[InsightEntityRef] = Field(default_factory=list)
    context_hint: Optional[str] = None
    best_action_window: Optional[str] = None
    information_tier: Optional[str] = None
    generation_level: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Valid delivery channels
# ---------------------------------------------------------------------------

_DELIVERY_CHANNELS = frozenset({"briefing", "sidekick", "kanban", "push"})


def _delivery_column_name(channel: str) -> str:
    if channel not in _DELIVERY_CHANNELS:
        raise ValueError(
            f"Unknown delivery channel {channel!r}; "
            f"expected one of {sorted(_DELIVERY_CHANNELS)}"
        )
    return f"delivered_via_{channel}"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class InsightQueryService:
    """Unified insight query entry point.

    All consumers query through this service so that delivery tracking,
    snooze handling, and expiry filtering are consistent.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Public query methods
    # ------------------------------------------------------------------

    async def get_for_kanban(
        self, user_id: UUID, *, limit: int = 10
    ) -> List[InsightCard]:
        """Kanban AI suggestion cards.

        Direct query on the ``insights`` table (no JOIN needed).
        Filters: active/pending, not expired, not snoozed.
        Marks ``delivered_via_kanban = true`` for returned rows.
        """
        now = utc_now()

        stmt = (
            select(Insight)
            .where(
                Insight.user_id == user_id,
                Insight.status.in_(["pending", "active"]),
                or_(
                    Insight.expires_at.is_(None),
                    Insight.expires_at > now,
                ),
                or_(
                    Insight.snoozed_until.is_(None),
                    Insight.snoozed_until <= now,
                ),
            )
            .order_by(
                Insight.importance.desc(),
                Insight.urgency.desc(),
                Insight.created_at.desc(),
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        if not rows:
            return []

        cards = [self._to_card(row) for row in rows]

        context = await self._build_query_context(user_id)
        cards = self._apply_dynamic_priority(cards, rows, context)

        # Mark delivery (fire-and-forget idempotent update)
        insight_ids = [row.id for row in rows]
        await self._mark_delivered_bulk(insight_ids, "kanban")

        return cards

    async def get_for_member(
        self,
        user_id: UUID,
        person_id: UUID,
        *,
        limit: int = 20,
        include_dismissed: bool = False,
    ) -> List[InsightCard]:
        """Member detail page — reverse lookup through ``insight_entities``.

        JOIN ``insight_entities`` WHERE entity_type='person' AND
        entity_id=person_id.
        """
        now = utc_now()
        allowed_statuses = ["pending", "active", "acknowledged"]
        if include_dismissed:
            allowed_statuses.extend(["dismissed", "acted"])

        stmt = (
            select(Insight)
            .join(
                InsightEntity,
                InsightEntity.insight_id == Insight.id,
            )
            .where(
                Insight.user_id == user_id,
                Insight.status.in_(allowed_statuses),
                or_(
                    Insight.expires_at.is_(None),
                    Insight.expires_at > now,
                ),
                InsightEntity.entity_type == "person",
                InsightEntity.entity_id == person_id,
            )
            .order_by(Insight.importance.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())
        return [self._to_card(row) for row in rows]

    async def get_for_trip(
        self,
        user_id: UUID,
        trip_id: UUID,
        *,
        limit: int = 10,
    ) -> List[InsightCard]:
        """Trip detail / timeline — reverse lookup through ``insight_entities``.

        Includes adopted insights (``adopted_at IS NOT NULL``).
        """
        now = utc_now()

        stmt = (
            select(Insight)
            .join(
                InsightEntity,
                InsightEntity.insight_id == Insight.id,
            )
            .where(
                Insight.user_id == user_id,
                or_(
                    Insight.status.in_(["pending", "active", "acknowledged"]),
                    InsightEntity.adopted_at.isnot(None),
                ),
                or_(
                    Insight.expires_at.is_(None),
                    Insight.expires_at > now,
                ),
                InsightEntity.entity_type == "trip",
                InsightEntity.entity_id == trip_id,
            )
            .order_by(Insight.importance.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())
        return [self._to_card(row) for row in rows]

    async def get_for_briefing(
        self,
        user_id: UUID,
        family_id: UUID,
        *,
        limit: int = 5,
    ) -> List[InsightCard]:
        """Daily briefing — high-importance pending insights, no JOIN.

        Marks ``delivered_via_briefing = true``.
        """
        now = utc_now()

        stmt = (
            select(Insight)
            .options(selectinload(Insight.entities))
            .where(
                Insight.user_id == user_id,
                Insight.family_id == family_id,
                Insight.status == "pending",
                Insight.importance >= 60,
                or_(
                    Insight.expires_at.is_(None),
                    Insight.expires_at > now,
                ),
            )
            .order_by(
                Insight.importance.desc(),
                Insight.urgency.desc(),
                Insight.created_at.desc(),
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        if not rows:
            return []

        cards = [self._to_card(row) for row in rows]

        context = await self._build_query_context(user_id)
        cards = self._apply_dynamic_priority(cards, rows, context)

        insight_ids = [row.id for row in rows]
        await self._mark_delivered_bulk(insight_ids, "briefing")

        return cards

    async def get_for_wave(
        self,
        user_id: UUID,
        family_id: UUID,
        wave_name: str,
        *,
        limit: int = 3,
    ) -> List[InsightCard]:
        """Wave-aware insight query for four-wave delivery system.

        Filters by the wave's ``focus_types`` (insight_type IN (...)) so each
        wave only surfaces contextually relevant content.  Falls back to
        ``get_for_briefing()`` semantics (importance >= 60, status pending) when
        the wave config is not found.

        Marks ``delivered_via_briefing = true`` for returned rows (waves are
        a sub-channel of the briefing delivery path).
        """
        from .delivery_timing_engine import _WAVE_BY_NAME

        if wave_name not in _WAVE_BY_NAME:
            logger.warning(
                "get_for_wave: unknown wave_name=%r, falling back to briefing", wave_name
            )

        now = utc_now()
        wave_cfg = _WAVE_BY_NAME.get(wave_name)

        # Base filter: pending, not expired, user-scoped
        base_conditions = [
            Insight.user_id == user_id,
            Insight.family_id == family_id,
            Insight.status == "pending",
            Insight.importance >= 60,
            or_(
                Insight.expires_at.is_(None),
                Insight.expires_at > now,
            ),
        ]

        # Wave-specific: restrict to focus_types when config is available
        if wave_cfg is not None:
            base_conditions.append(
                Insight.insight_type.in_(list(wave_cfg.focus_types))
            )
            effective_limit = min(limit, wave_cfg.max_items)
        else:
            effective_limit = limit

        stmt = (
            select(Insight)
            .where(*base_conditions)
            .order_by(
                Insight.importance.desc(),
                Insight.urgency.desc(),
                Insight.created_at.desc(),
            )
            .limit(effective_limit)
        )

        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        if not rows:
            return []

        cards = [self._to_card(row) for row in rows]

        context = await self._build_query_context(user_id)
        cards = self._apply_dynamic_priority(cards, rows, context)

        insight_ids = [row.id for row in rows]
        await self._mark_delivered_bulk(insight_ids, "briefing")

        return cards

    async def get_for_sidekick(
        self, user_id: UUID, *, limit: int = 3
    ) -> List[InsightCard]:
        """Sidekick injection candidates — recent 6h, high importance.

        Only insights not yet delivered via sidekick.
        """
        now = utc_now()
        six_hours_ago = now - timedelta(hours=6)

        stmt = (
            select(Insight)
            .where(
                Insight.user_id == user_id,
                Insight.status.in_(["pending", "active"]),
                Insight.importance >= 70,
                Insight.created_at >= six_hours_ago,
                Insight.delivered_via_sidekick.is_(False),
                or_(
                    Insight.expires_at.is_(None),
                    Insight.expires_at > now,
                ),
            )
            .order_by(
                Insight.importance.desc(),
                Insight.urgency.desc(),
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        if not rows:
            return []

        cards = [self._to_card(row) for row in rows]
        context = await self._build_query_context(user_id)
        return self._apply_dynamic_priority(cards, rows, context)

    # ------------------------------------------------------------------
    # Lifecycle mutations
    # ------------------------------------------------------------------

    async def mark_shown(self, insight_ids: List[UUID]) -> None:
        """Transition pending -> active and set ``shown_at``.

        Idempotent: already-active insights are left unchanged.
        """
        if not insight_ids:
            return

        now = utc_now()

        await self.db.execute(
            update(Insight)
            .where(
                Insight.id.in_(insight_ids),
                Insight.status == "pending",
            )
            .values(status="active", shown_at=now, activated_at=now)
        )
        await self.db.flush()

    async def mark_delivered(self, insight_id: UUID, channel: str) -> None:
        """Mark a single delivery channel (idempotent).

        ``UPDATE SET delivered_via_<channel> = true
          WHERE id = ? AND NOT delivered_via_<channel>``
        """
        await self._mark_delivered_bulk([insight_id], channel)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _build_query_context(
        self, user_id: UUID, *, density_score: Optional[float] = None
    ) -> UserQueryContext:
        """Build a UserQueryContext from available data, using sensible defaults.

        Fetches dismiss counts by insight_type and emotional trend from the DB.
        density_score and recent_entity_ids use defaults — they require data
        sources (OrchestratedDay / activity log) not accessible here.
        """
        now = utc_now()
        seven_days_ago = now - timedelta(days=7)

        # Dismiss counts by insight_type over last 7 days (uses existing table)
        dismiss_count_7d: Dict[str, int] = {}
        try:
            stmt = (
                select(Insight.insight_type, func.count(Insight.id))
                .where(
                    Insight.user_id == user_id,
                    Insight.status == "dismissed",
                    Insight.feedback_source == "user",
                    Insight.created_at >= seven_days_ago,
                )
                .group_by(Insight.insight_type)
            )
            result = await self.db.execute(stmt)
            dismiss_count_7d = {row[0]: row[1] for row in result.all()}
        except Exception:
            logger.warning("Failed to fetch dismiss counts for dynamic priority", exc_info=True)

        # User mood from emotional trend (declining→low, improving→high, else normal)
        user_mood: Optional[str] = "normal"
        try:
            from ..memory.emotional_trend_service import compute_emotional_trend
            trend = await compute_emotional_trend(self.db, user_id)
            if trend.trend == "declining":
                user_mood = "low"
            elif trend.trend == "improving":
                user_mood = "high"
            else:
                user_mood = "normal"
        except Exception:
            logger.warning("Failed to fetch emotional trend for dynamic priority", exc_info=True)

        # Weekend detection from current date (no extra DB query)
        is_weekend = now.weekday() >= 5

        # density_score: ideally sourced from OrchestratedDay.density_score (curation
        # module). OrchestratedDay is computed on-demand and not persisted, so we
        # approximate it here by counting today's active CuratedEvents and normalising
        # to [0, 1] with a cap of 10 events (≥10 → 1.0).  Callers that already hold a
        # fully orchestrated day (e.g. BriefingService) should pass the real value
        # directly via the density_score parameter to avoid the COUNT query.
        if density_score is None:
            density_score = 0.5
            try:
                from ..curation.models import CuratedEvent
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
                count_stmt = (
                    select(func.count())
                    .where(
                        CuratedEvent.user_id == user_id,
                        CuratedEvent.normalized_start >= today_start,
                        CuratedEvent.normalized_start <= today_end,
                        CuratedEvent.status != "cancelled",
                    )
                )
                count_result = await self.db.execute(count_stmt)
                today_event_count = count_result.scalar() or 0
                # Normalise: 0 events → 0.0, ≥10 events → 1.0
                density_score = min(1.0, today_event_count / 10.0)
            except Exception:
                logger.debug(
                    "density_score estimation failed; using default 0.5",
                    exc_info=True,
                )
                density_score = 0.5

        return UserQueryContext(
            recent_entity_ids=frozenset(),  # activity log not accessible here
            dismiss_count_7d=dismiss_count_7d,
            density_score=density_score,
            is_weekend=is_weekend,
            is_holiday=False,  # no holiday calendar accessible here
            user_mood=user_mood,
        )

    def _apply_dynamic_priority(
        self,
        cards: List[InsightCard],
        rows: List,
        context: UserQueryContext,
    ) -> List[InsightCard]:
        """Apply DynamicPriorityAdjuster to each card and re-sort by adjusted scores.

        Returns a new list with adjusted importance/urgency values.
        Preserves all other card fields unchanged (immutable pattern).
        """
        adjuster = DynamicPriorityAdjuster()
        adjusted: List[InsightCard] = []
        for card, row in zip(cards, rows):
            new_importance, new_urgency = adjuster.adjust(row, context)
            adjusted.append(card.model_copy(update={
                "importance": new_importance,
                "urgency": new_urgency,
            }))
        adjusted.sort(key=lambda c: (c.importance, c.urgency), reverse=True)
        return adjusted

    async def _mark_delivered_bulk(
        self, insight_ids: List[UUID], channel: str
    ) -> None:
        """Idempotent bulk delivery marking."""
        if not insight_ids:
            return

        col_name = _delivery_column_name(channel)
        col = getattr(Insight, col_name)

        await self.db.execute(
            update(Insight)
            .where(
                Insight.id.in_(insight_ids),
                col.is_(False),
            )
            .values(**{col_name: True})
        )
        await self.db.flush()

    def _to_card(self, insight) -> InsightCard:
        """Convert an ORM Insight row to an ``InsightCard`` DTO."""
        entities: List[InsightEntityRef] = []
        # If the ORM model has eagerly-loaded entities, include them.
        raw_entities = getattr(insight, "entities", None)
        if raw_entities:
            entities = [
                InsightEntityRef(
                    entity_type=e.entity_type,
                    entity_id=e.entity_id,
                    role=e.role,
                )
                for e in raw_entities
            ]

        return InsightCard(
            id=insight.id,
            insight_type=insight.insight_type,
            title=insight.title,
            content=insight.content,
            importance=insight.importance,
            urgency=insight.urgency,
            status=insight.status,
            suggested_action=insight.suggested_action,
            action_options=insight.action_options,
            delivered_via_briefing=insight.delivered_via_briefing,
            delivered_via_sidekick=insight.delivered_via_sidekick,
            delivered_via_kanban=insight.delivered_via_kanban,
            delivered_via_push=insight.delivered_via_push,
            created_at=insight.created_at,
            expires_at=insight.expires_at,
            entities=entities,
            context_hint=getattr(insight, "context_hint", None),
            best_action_window=getattr(insight, "best_action_window", None),
            information_tier=getattr(insight, "information_tier", None),
            generation_level=getattr(insight, "generation_level", None),
        )
