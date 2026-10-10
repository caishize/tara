"""RecommendationEngine -- Unified recommendation generation pipeline.

Replaces the separate suggestion/insight systems with a single engine:
- SmartSuggestionService strategies (11 strategies)
- InsightOrchestrator (System A/B/C)

Architecture:
- Strategy pattern via RecommendationStrategy protocol
- Adapter wrappers around existing services (no breaking changes)
- Failure-isolated strategy execution
- Semantic dedup, feedback learning, shown-count suppression

Pipeline:
1. Build shared RecommendationContext
2. Run strategies with isolated failures
3. Semantic dedup (embedding similarity >= 0.75)
4. Apply feedback weights from FamilyPreference.recommendation_weights
5. Sort by priority * type_weight
6. Period filter + density filter
"""

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now, local_today
from .shown_count_tracker import ShownCountTracker
from .trip_correlation_strategy import TripCorrelationStrategy

logger = get_logger(__name__)

# Shown-count suppression thresholds
_SHOWN_UNACTED_SUPPRESS_COUNT = 3
_SHOWN_UNACTED_SUPPRESS_DAYS = 30
_DISMISSED_COOLDOWN_DAYS = 7
_IGNORED_COOLDOWN_DAYS = 3

# Auto-suppress TTL (must match consumer constant)
_SUPPRESS_TTL_DAYS = 30

# Semantic dedup threshold
_DEDUP_SIMILARITY_THRESHOLD = 0.75


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Recommendation:
    """A unified recommendation produced by any strategy."""

    id: UUID
    title: str
    content: str
    recommendation_type: str
    priority: float  # 0.0 - 1.0
    source_strategy: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    shown_count: int = 0
    last_shown_at: Optional[datetime] = None
    last_dismissed_at: Optional[datetime] = None


@dataclass(frozen=True)
class RecommendationContext:
    """Shared context passed to all strategies for a generation run."""

    target_date: date
    period: Optional[str] = None
    emotional_trend: str = "neutral"
    density_level: str = "normal"
    suppressed_types: List[str] = field(default_factory=list)
    type_weights: Dict[str, float] = field(default_factory=dict)
    orchestrated_day: Any = None  # Optional OrchestratedDay from orchestrator


# ---------------------------------------------------------------------------
# Strategy protocol
# ---------------------------------------------------------------------------


class RecommendationStrategy(Protocol):
    """Protocol for pluggable recommendation strategies."""

    async def generate(
        self,
        user_id: UUID,
        family_id: UUID,
        context: RecommendationContext,
    ) -> List[Recommendation]: ...

    @property
    def strategy_name(self) -> str: ...


# ---------------------------------------------------------------------------
# Adapter: InsightOrchestrator -> RecommendationStrategy
# ---------------------------------------------------------------------------


class InsightOrchestratorAdapter:
    """Wraps the existing InsightOrchestrator as a RecommendationStrategy.

    Calls InsightOrchestrator.generate_all() and converts Insight
    objects into Recommendation dataclass instances.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    @property
    def strategy_name(self) -> str:
        return "insight_orchestrator"

    async def generate(
        self,
        user_id: UUID,
        family_id: UUID,
        context: RecommendationContext,
    ) -> List[Recommendation]:
        try:
            from .insight_orchestrator import InsightOrchestrator

            orchestrator = InsightOrchestrator(self._db)
            insights = await orchestrator.generate_all(
                user_id, family_id, context.target_date,
            )
            return [self._convert(insight) for insight in insights]
        except Exception:
            try:
                await self._db.rollback()
            except Exception:
                logger.debug(
                    "Rollback after InsightOrchestratorAdapter failure also failed",
                    exc_info=True,
                )
            logger.warning(
                "InsightOrchestratorAdapter failed for user=%s", user_id,
                exc_info=True,
            )
            return []

    @staticmethod
    def _convert(insight: Any) -> Recommendation:
        # Unified Insight uses importance/urgency (0-100 int)
        importance = getattr(insight, "importance", None) or getattr(insight, "importance_score", 50) or 50
        urgency = getattr(insight, "urgency", None) or getattr(insight, "urgency_score", 50) or 50
        combined = importance * 0.6 + urgency * 0.4
        priority = min(1.0, combined / 100.0)

        # Unified Insight uses source_context (JSONB), legacy uses extra_data
        source_ctx = getattr(insight, "source_context", None) or {}
        extra = getattr(insight, "extra_data", None) or {}
        source = extra.get("source", source_ctx.get("source", "insight"))

        # Extract entity references from insight_entities (unified) or FK columns (legacy)
        entity_refs = {}
        entities = getattr(insight, "entities", None) or []
        for ent in entities:
            etype = getattr(ent, "entity_type", "")
            eid = getattr(ent, "entity_id", None)
            if etype and eid:
                entity_refs.setdefault(f"related_{etype}_id", str(eid))
        # Legacy FK fallback
        for fk in ("related_event_id", "related_important_date_id", "related_person_id"):
            val = getattr(insight, fk, None)
            if val and fk not in entity_refs:
                entity_refs[fk] = str(val)

        return Recommendation(
            id=getattr(insight, "id", None) or uuid4(),
            title=insight.title,
            content=insight.content,
            recommendation_type=insight.insight_type,
            priority=priority,
            source_strategy=f"insight_{source}",
            metadata={
                "importance_score": importance,
                "urgency_score": urgency,
                "suggested_action": getattr(insight, "suggested_action", None),
                **entity_refs,
                "action_data": extra.get("action_data", {}),
            },
        )


# ---------------------------------------------------------------------------
# Adapter: SmartSuggestionService -> RecommendationStrategy
# ---------------------------------------------------------------------------


class SmartSuggestionAdapter:
    """Wraps the existing SmartSuggestionService as a RecommendationStrategy.

    Calls SmartSuggestionService.generate_suggestions() and converts
    Suggestion pydantic models into Recommendation dataclass instances.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    @property
    def strategy_name(self) -> str:
        return "smart_suggestion"

    async def generate(
        self,
        user_id: UUID,
        family_id: UUID,
        context: RecommendationContext,
    ) -> List[Recommendation]:
        try:
            from .suggestion_service import SmartSuggestionService

            service = SmartSuggestionService(self._db)
            suggestions = await service.generate_suggestions(
                user_id, family_id, limit=20,
            )
            return [self._convert(s) for s in suggestions]
        except Exception:
            logger.warning(
                "SmartSuggestionAdapter failed for user=%s", user_id,
                exc_info=True,
            )
            return []

    @staticmethod
    def _convert(suggestion: Any) -> Recommendation:
        raw_priority = getattr(suggestion, "priority", 50) or 50
        priority = min(1.0, raw_priority / 100.0)

        stype = getattr(suggestion, "type", "general")
        if hasattr(stype, "value"):
            stype = stype.value

        return Recommendation(
            id=UUID(suggestion.id) if hasattr(suggestion, "id") else uuid4(),
            title=suggestion.title,
            content=suggestion.content,
            recommendation_type=stype,
            priority=priority,
            source_strategy="smart_suggestion",
            metadata={
                "icon": getattr(suggestion, "icon", "lightbulb"),
                "action_options": getattr(suggestion, "action_options", []),
                "action_data": getattr(suggestion, "action_data", {}),
                "urgency": getattr(suggestion, "urgency", "normal"),
                "related_event_ids": getattr(suggestion, "related_event_ids", []),
                "related_member_ids": getattr(suggestion, "related_member_ids", []),
            },
        )



# ---------------------------------------------------------------------------
# RecommendationEngine
# ---------------------------------------------------------------------------


class RecommendationEngine:
    """Unified recommendation engine using the strategy pattern.

    Wraps existing InsightOrchestrator and SmartSuggestionService via
    adapter pattern (Phase 1 -- no breaking changes to existing code).
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._strategies: List[Any] = [
            InsightOrchestratorAdapter(db),
            SmartSuggestionAdapter(db),
            TripCorrelationStrategy(db),
        ]

    async def generate(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: Optional[date] = None,
        period: Optional[str] = None,
        limit: int = 10,
        orchestrated_day: Optional[Any] = None,
    ) -> List[Recommendation]:
        """Execute the full recommendation pipeline.

        Args:
            orchestrated_day: Optional OrchestratedDay from SecretaryOrchestrator.
                Provides density_score and slot information for context-aware
                recommendations.

        Steps:
        1. Build shared RecommendationContext
        2. Run all strategies with failure isolation
        3. Semantic dedup
        4. Apply feedback weights
        5. Sort by priority * type_weight
        6. Period filter + shown-count suppression
        """
        if target_date is None:
            target_date = local_today()

        context = await self._build_context(
            user_id, family_id, target_date, period,
            orchestrated_day=orchestrated_day,
        )

        # Step 2: Parallel strategy execution
        raw_recs = await self._execute_strategies(user_id, family_id, context)

        if not raw_recs:
            return []

        # Step 3: Semantic dedup
        deduped = await self._semantic_dedup(raw_recs)

        # Step 4: Apply feedback weights
        weighted = self._apply_feedback_weights(deduped, context)

        # Step 5: Sort by effective priority
        weighted.sort(key=lambda r: r.priority, reverse=True)

        # Step 5.5: Hydrate shown counts from Redis
        tracker = await self._get_shown_count_tracker()
        if tracker is not None:
            weighted = await self._hydrate_shown_counts(
                tracker, family_id, weighted,
            )

        # Step 6: Period filter + shown-count suppression
        filtered = self._apply_suppression(weighted, context)

        result = filtered[:limit]

        # Fire-and-forget: increment shown counts for returned recommendations
        if tracker is not None and result:
            asyncio.ensure_future(
                tracker.increment(family_id, [r.title for r in result]),
            )

        return result

    # ------------------------------------------------------------------
    # Step 1: Build context
    # ------------------------------------------------------------------

    async def _build_context(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: date,
        period: Optional[str],
        orchestrated_day: Optional[Any] = None,
    ) -> RecommendationContext:
        """Build the shared context for all strategies."""
        suppressed_types: List[str] = []
        type_weights: Dict[str, float] = {}
        emotional_trend = "neutral"

        try:
            from ...curation.services.family_preference_repository import (
                FamilyPreferenceRepository,
            )

            repo = FamilyPreferenceRepository(self._db)
            pref = await repo.get_by_family_id(family_id)
            if pref is not None:
                raw_suppressed = pref.suppressed_types
                raw_weights = pref.recommendation_weights or {}

                # Check for expired auto-suppressions (TTL = 30 days)
                now = utc_now()
                expired_types: List[str] = []
                if isinstance(raw_suppressed, list) and isinstance(raw_weights, dict):
                    for stype in raw_suppressed:
                        stats = raw_weights.get(str(stype))
                        if not isinstance(stats, dict):
                            continue
                        # Permanent suppressions (NEVER_AGAIN) never expire
                        if stats.get("permanent"):
                            continue
                        suppressed_at_str = stats.get("suppressed_at")
                        if not suppressed_at_str:
                            continue
                        try:
                            suppressed_at = datetime.fromisoformat(suppressed_at_str)
                            if now - suppressed_at > timedelta(days=_SUPPRESS_TTL_DAYS):
                                expired_types.append(str(stype))
                        except (ValueError, TypeError):
                            continue

                # Remove expired suppressions from DB
                for expired in expired_types:
                    await repo.remove_suppressed_type(family_id, expired)
                    logger.info(
                        "Auto-unsuppressed expired type '%s' for family %s (ttl=%dd)",
                        expired, family_id, _SUPPRESS_TTL_DAYS,
                    )

                if isinstance(raw_suppressed, list):
                    suppressed_types = [
                        str(s) for s in raw_suppressed
                        if str(s) not in expired_types
                    ]
                if isinstance(raw_weights, dict):
                    type_weights = {}
                    for k, v in raw_weights.items():
                        if isinstance(v, dict):
                            type_weights[str(k)] = float(v.get("weight", 1.0))
                        else:
                            type_weights[str(k)] = float(v)
        except Exception:
            try:
                await self._db.rollback()
            except Exception:
                logger.debug(
                    "Rollback after FamilyPreference context failure also failed",
                    exc_info=True,
                )
            logger.debug(
                "Failed to load FamilyPreference for context, using defaults",
                exc_info=True,
            )

        try:
            from .insight_feedback_learner import InsightFeedbackLearner

            learner = InsightFeedbackLearner(self._db)
            insight_suppressed = await learner.get_suppressed_types(user_id)
            for st in insight_suppressed:
                if st not in suppressed_types:
                    suppressed_types.append(st)
        except Exception:
            try:
                await self._db.rollback()
            except Exception:
                logger.debug(
                    "Rollback after insight suppression failure also failed",
                    exc_info=True,
                )
            logger.debug(
                "Failed to load insight suppression, continuing",
                exc_info=True,
            )

        try:
            emotional_trend = await self._detect_emotional_trend(user_id)
        except Exception:
            try:
                await self._db.rollback()
            except Exception:
                logger.debug(
                    "Rollback after emotional trend failure also failed",
                    exc_info=True,
                )
            logger.debug("Emotional trend detection failed", exc_info=True)

        # Derive density_level from OrchestratedDay if available
        density_level = "normal"
        if orchestrated_day is not None:
            score = getattr(orchestrated_day, "density_score", 0.0)
            if score >= 0.7:
                density_level = "high"
            elif score <= 0.3:
                density_level = "low"

        return RecommendationContext(
            target_date=target_date,
            period=period,
            emotional_trend=emotional_trend,
            density_level=density_level,
            suppressed_types=suppressed_types,
            type_weights=type_weights,
            orchestrated_day=orchestrated_day,
        )

    async def _detect_emotional_trend(self, user_id: UUID) -> str:
        """Detect recent emotional trend via the EmotionalTrendService."""
        from ...memory.emotional_trend_service import compute_emotional_trend

        result = await compute_emotional_trend(self._db, user_id)
        trend = result.trend
        # Map EmotionalTrend values to the context values this engine expects
        _TREND_MAP = {
            "declining": "negative",
            "improving": "positive",
            "stable": "neutral",
            "unknown": "neutral",
        }
        return _TREND_MAP.get(trend, "neutral")

    # ------------------------------------------------------------------
    # Shown-count hydration
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_shown_count_tracker() -> Optional[ShownCountTracker]:
        """Return a ShownCountTracker backed by the global Redis client.

        Returns None if Redis is unavailable (graceful degradation).
        """
        try:
            from ....core.cache import redis_client

            if redis_client.client is None:
                return None
            return ShownCountTracker(redis_client)
        except Exception:
            logger.debug("Redis unavailable for shown count tracking", exc_info=True)
            return None

    @staticmethod
    async def _hydrate_shown_counts(
        tracker: ShownCountTracker,
        family_id: UUID,
        recommendations: List[Recommendation],
    ) -> List[Recommendation]:
        """Load shown counts from Redis and populate Recommendation fields."""
        titles = [r.title for r in recommendations]
        counts = await tracker.load_counts(family_id, titles)
        if not counts:
            return recommendations

        hydrated: List[Recommendation] = []
        for rec in recommendations:
            entry = counts.get(rec.title)
            if entry is not None:
                shown_count, last_shown = entry
                hydrated.append(Recommendation(
                    id=rec.id,
                    title=rec.title,
                    content=rec.content,
                    recommendation_type=rec.recommendation_type,
                    priority=rec.priority,
                    source_strategy=rec.source_strategy,
                    metadata=rec.metadata,
                    shown_count=shown_count,
                    last_shown_at=last_shown,
                    last_dismissed_at=rec.last_dismissed_at,
                ))
            else:
                hydrated.append(rec)
        return hydrated

    # ------------------------------------------------------------------
    # Step 2: Strategy execution
    # ------------------------------------------------------------------

    async def _execute_strategies(
        self,
        user_id: UUID,
        family_id: UUID,
        context: RecommendationContext,
    ) -> List[Recommendation]:
        """Run all strategies and merge results.

        Uses sequential awaits because all strategies share the same
        AsyncSession; concurrent DB calls on one session/connection can
        fail with asyncpg interface errors.
        """
        import time as _time

        async def _run(strategy: Any) -> List[Recommendation]:
            try:
                return await strategy.generate(user_id, family_id, context)
            except Exception:
                name = getattr(strategy, "strategy_name", type(strategy).__name__)
                logger.warning(
                    "Strategy %s failed for user=%s", name, user_id,
                    exc_info=True,
                )
                return []

        merged: List[Recommendation] = []
        for strategy in self._strategies:
            name = getattr(strategy, "strategy_name", type(strategy).__name__)
            _t0 = _time.perf_counter()
            result = await _run(strategy)
            logger.info(
                "[REC PERF] Strategy %s: %.3fs (%d recs)",
                name, _time.perf_counter() - _t0, len(result),
            )
            merged.extend(result)
        return merged

    # ------------------------------------------------------------------
    # Step 3: Semantic dedup
    # ------------------------------------------------------------------

    async def _semantic_dedup(
        self,
        recommendations: List[Recommendation],
    ) -> List[Recommendation]:
        """Deduplicate recommendations using embedding similarity.

        Falls back to title-based exact dedup if embedding is unavailable.
        Threshold: 0.75 similarity merges recommendations (keeps higher priority).
        """
        if len(recommendations) <= 1:
            return recommendations

        # Try semantic dedup
        try:
            return await self._semantic_dedup_with_embeddings(recommendations)
        except Exception:
            logger.debug(
                "Semantic dedup failed, falling back to title dedup",
                exc_info=True,
            )

        return self._title_dedup(recommendations)

    async def _semantic_dedup_with_embeddings(
        self,
        recommendations: List[Recommendation],
    ) -> List[Recommendation]:
        """Dedup using embedding similarity from memory module."""
        from ...memory.embedding_service import EmbeddingService

        service = EmbeddingService()
        texts = [f"{r.title}: {r.content[:200]}" for r in recommendations]
        embeddings = await service.get_embeddings_batch(texts)

        # First pass: find all similar pairs, always discard the lower-priority one
        discarded: Set[int] = set()

        for i in range(len(recommendations)):
            if embeddings[i] is None:
                continue
            for j in range(i + 1, len(recommendations)):
                if embeddings[j] is None:
                    continue
                similarity = service.compute_similarity(
                    embeddings[i], embeddings[j],
                )
                if similarity >= _DEDUP_SIMILARITY_THRESHOLD:
                    if recommendations[j].priority > recommendations[i].priority:
                        discarded.add(i)
                    else:
                        discarded.add(j)

        # Second pass: collect non-discarded items preserving order
        return [r for idx, r in enumerate(recommendations) if idx not in discarded]

    @staticmethod
    def _title_dedup(
        recommendations: List[Recommendation],
    ) -> List[Recommendation]:
        """Fallback title-based exact dedup."""
        seen_titles: Set[str] = set()
        deduped: List[Recommendation] = []
        for rec in recommendations:
            key = rec.title.strip().lower()
            if key not in seen_titles:
                seen_titles.add(key)
                deduped.append(rec)
        return deduped

    # ------------------------------------------------------------------
    # Step 4: Feedback weights
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_feedback_weights(
        recommendations: List[Recommendation],
        context: RecommendationContext,
    ) -> List[Recommendation]:
        """Apply type weights from FamilyPreference to adjust priority."""
        if not context.type_weights:
            return recommendations

        adjusted: List[Recommendation] = []
        for rec in recommendations:
            weight = context.type_weights.get(rec.recommendation_type, 1.0)
            new_priority = min(1.0, rec.priority * weight)
            adjusted.append(Recommendation(
                id=rec.id,
                title=rec.title,
                content=rec.content,
                recommendation_type=rec.recommendation_type,
                priority=new_priority,
                source_strategy=rec.source_strategy,
                metadata=rec.metadata,
                shown_count=rec.shown_count,
                last_shown_at=rec.last_shown_at,
                last_dismissed_at=rec.last_dismissed_at,
            ))
        return adjusted

    # ------------------------------------------------------------------
    # Step 6: Suppression + period filter
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_suppression(
        recommendations: List[Recommendation],
        context: RecommendationContext,
    ) -> List[Recommendation]:
        """Filter out suppressed types, cooldowns, and shown-count rules."""
        suppressed_set = frozenset(context.suppressed_types)
        now = utc_now()
        kept: List[Recommendation] = []

        for rec in recommendations:
            # Type suppression
            if rec.recommendation_type in suppressed_set:
                continue

            # Dismissed cooldown: recently dismissed -> suppress 7 days
            if rec.last_dismissed_at is not None:
                dismiss_cooldown_end = rec.last_dismissed_at + timedelta(
                    days=_DISMISSED_COOLDOWN_DAYS,
                )
                if now < dismiss_cooldown_end:
                    continue

            # Ignored cooldown: shown but not acted upon -> suppress 3 days
            if (
                rec.shown_count > 0
                and rec.last_shown_at is not None
                and rec.last_dismissed_at is None  # not explicitly dismissed
            ):
                ignored_cooldown_end = rec.last_shown_at + timedelta(
                    days=_IGNORED_COOLDOWN_DAYS,
                )
                if now < ignored_cooldown_end:
                    continue

            # Shown-count suppression: 3 times unacted -> suppress 30 days
            if rec.shown_count >= _SHOWN_UNACTED_SUPPRESS_COUNT:
                if rec.last_shown_at is not None:
                    suppress_until = rec.last_shown_at + timedelta(
                        days=_SHOWN_UNACTED_SUPPRESS_DAYS,
                    )
                    if now < suppress_until:
                        continue

            # Emotional adjustment: reduce low-urgency items during negative trend
            if context.emotional_trend == "negative":
                urgency = rec.metadata.get("urgency", "normal")
                if urgency == "low" and rec.priority < 0.3:
                    continue

            kept.append(rec)

        return kept
