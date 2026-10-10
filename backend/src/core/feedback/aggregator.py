"""Unified feedback aggregation across insight, curation, and memory modules.

Collects feedback signals from three sources and produces a single
weighted score (0.1 to 2.0) per entity, used by ContextAssembler Step 4.

Sources:
    1. insights + insight_entities -- unified insight status/feedback
    2. event_associations -- dismiss/confirm on curation associations
    3. conversation_memories -- per-memory feedback_weight column
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Score range bounds
MIN_SCORE = 0.1
MAX_SCORE = 2.0
DEFAULT_SCORE = 1.0

# Weights for each feedback source when aggregating
_SOURCE_WEIGHT_INSIGHT = 0.3
_SOURCE_WEIGHT_CURATION = 0.3
_SOURCE_WEIGHT_MEMORY = 0.4

# Insight feedback type -> score contribution
_INSIGHT_FEEDBACK_SCORES: Dict[str, float] = {
    "useful": 1.5,
    "not_useful": 0.5,
    "too_frequent": 0.7,
    "not_relevant": 0.4,
    "incorrect": 0.2,
}


class FeedbackAggregator:
    """Aggregates feedback from insight, curation, and memory modules.

    Produces a unified feedback weight for any entity (typically a memory)
    that can be used in context ranking.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_entity_feedback_score(
        self,
        entity_id: UUID,
        family_id: UUID,
    ) -> float:
        """Compute a unified feedback score for an entity.

        Queries all 3 feedback sources and returns a weighted average.
        Returns DEFAULT_SCORE (1.0) if no feedback exists.

        Args:
            entity_id: The UUID of the entity (typically a memory ID).
            family_id: The family context for scoping queries.

        Returns:
            A float between 0.1 and 2.0.
        """
        scores: List[float] = []
        weights: List[float] = []

        insight_score = await self._get_insight_feedback_score(entity_id)
        if insight_score is not None:
            scores.append(insight_score)
            weights.append(_SOURCE_WEIGHT_INSIGHT)

        curation_score = await self._get_curation_feedback_score(
            entity_id, family_id,
        )
        if curation_score is not None:
            scores.append(curation_score)
            weights.append(_SOURCE_WEIGHT_CURATION)

        memory_score = await self._get_memory_feedback_score(entity_id)
        if memory_score is not None:
            scores.append(memory_score)
            weights.append(_SOURCE_WEIGHT_MEMORY)

        if not scores:
            return DEFAULT_SCORE

        total_weight = sum(weights)
        if total_weight <= 0:
            return DEFAULT_SCORE

        weighted_avg = sum(s * w for s, w in zip(scores, weights)) / total_weight
        return max(MIN_SCORE, min(MAX_SCORE, weighted_avg))

    async def get_bulk_feedback_scores(
        self,
        entity_ids: List[UUID],
        family_id: UUID,
    ) -> Dict[str, float]:
        """Compute feedback scores for multiple entities at once.

        More efficient than calling get_entity_feedback_score in a loop
        because it batches DB queries per source.

        Returns a dict mapping entity_id (str) -> score (float).
        Missing entities default to 1.0.
        """
        if not entity_ids:
            return {}

        insight_scores = await self._get_bulk_insight_scores(entity_ids)
        curation_scores = await self._get_bulk_curation_scores(
            entity_ids, family_id,
        )
        memory_scores = await self._get_bulk_memory_scores(entity_ids)

        result: Dict[str, float] = {}
        for eid in entity_ids:
            eid_str = str(eid)
            scores: List[float] = []
            weights: List[float] = []

            if eid_str in insight_scores:
                scores.append(insight_scores[eid_str])
                weights.append(_SOURCE_WEIGHT_INSIGHT)
            if eid_str in curation_scores:
                scores.append(curation_scores[eid_str])
                weights.append(_SOURCE_WEIGHT_CURATION)
            if eid_str in memory_scores:
                scores.append(memory_scores[eid_str])
                weights.append(_SOURCE_WEIGHT_MEMORY)

            if not scores:
                result[eid_str] = DEFAULT_SCORE
                continue

            total_weight = sum(weights)
            weighted_avg = sum(s * w for s, w in zip(scores, weights)) / total_weight
            result[eid_str] = max(MIN_SCORE, min(MAX_SCORE, weighted_avg))

        return result

    # ── Insight feedback ──────────────────────────────────────────────

    @staticmethod
    def _status_to_feedback_type(status: Optional[str], feedback: Optional[str]) -> Optional[str]:
        """Derive a feedback-type string from unified Insight status/feedback.

        Prefers the explicit ``feedback`` column when populated; otherwise
        maps ``status`` to an equivalent feedback type for scoring.
        """
        if feedback:
            return feedback
        _STATUS_MAP = {
            "acted": "useful",
            "dismissed": "not_useful",
            "acknowledged": "useful",
        }
        return _STATUS_MAP.get(status or "") if status else None

    async def _get_insight_feedback_score(
        self, entity_id: UUID,
    ) -> Optional[float]:
        """Score from the unified Insight table for a given entity.

        Queries InsightEntity to find insights referencing the entity,
        then derives feedback signals from Insight.status / Insight.feedback.
        """
        try:
            from ...modules.insight.models import Insight, InsightEntity
        except ImportError:
            return None

        all_feedback_types: list = []

        try:
            stmt = (
                select(Insight.status, Insight.feedback)
                .join(InsightEntity, InsightEntity.insight_id == Insight.id)
                .where(InsightEntity.entity_id == entity_id)
            )
            result = await self._db.execute(stmt)
            for status, feedback in result.all():
                ft = self._status_to_feedback_type(status, feedback)
                if ft:
                    all_feedback_types.append(ft)
        except Exception as e:
            logger.debug("Insight feedback query failed: %s", e)

        if not all_feedback_types:
            return None
        return self._compute_insight_score(all_feedback_types)

    async def _get_bulk_insight_scores(
        self, entity_ids: List[UUID],
    ) -> Dict[str, float]:
        """Bulk insight feedback scores keyed by entity_id string.

        Queries the unified Insight + InsightEntity tables.
        """
        try:
            from ...modules.insight.models import Insight, InsightEntity
        except ImportError:
            return {}

        grouped: Dict[str, List[str]] = {}

        try:
            stmt = (
                select(
                    InsightEntity.entity_id,
                    Insight.status,
                    Insight.feedback,
                )
                .join(InsightEntity, InsightEntity.insight_id == Insight.id)
                .where(InsightEntity.entity_id.in_(entity_ids))
            )
            result = await self._db.execute(stmt)
            for eid, status, feedback in result.all():
                ft = self._status_to_feedback_type(status, feedback)
                if ft:
                    grouped.setdefault(str(eid), []).append(ft)
        except Exception as e:
            logger.debug("Bulk insight feedback query failed: %s", e)

        if not grouped:
            return {}

        return {
            eid: self._compute_insight_score(types)
            for eid, types in grouped.items()
        }

    @staticmethod
    def _compute_insight_score(feedback_types: List[str]) -> float:
        """Average the score contributions of all insight feedback types."""
        if not feedback_types:
            return DEFAULT_SCORE
        total = sum(
            _INSIGHT_FEEDBACK_SCORES.get(ft, DEFAULT_SCORE)
            for ft in feedback_types
        )
        return total / len(feedback_types)

    # ── Curation feedback ─────────────────────────────────────────────

    async def _get_curation_feedback_score(
        self,
        entity_id: UUID,
        family_id: UUID,
    ) -> Optional[float]:
        """Score from event_associations for a given target memory."""
        try:
            from ...modules.curation.models import EventAssociation
        except ImportError:
            return None

        try:
            entity_str = str(entity_id)
            stmt = (
                select(
                    func.count(case(
                        (EventAssociation.is_confirmed == True, 1),  # noqa: E712
                    )).label("confirmed"),
                    func.count(case(
                        (EventAssociation.is_dismissed == True, 1),  # noqa: E712
                    )).label("dismissed"),
                    func.count(literal_column("1")).label("total"),
                )
                .where(
                    EventAssociation.target_id == entity_str,
                    EventAssociation.family_id == family_id,
                )
            )
            result = await self._db.execute(stmt)
            row = result.one_or_none()
            if row is None or row.total == 0:
                return None
            return self._compute_curation_score(
                row.confirmed, row.dismissed, row.total,
            )
        except Exception as e:
            logger.debug("Curation feedback query failed: %s", e)
            return None

    async def _get_bulk_curation_scores(
        self,
        entity_ids: List[UUID],
        family_id: UUID,
    ) -> Dict[str, float]:
        """Bulk curation feedback scores."""
        try:
            from ...modules.curation.models import EventAssociation
        except ImportError:
            return {}

        try:
            entity_strs = [str(eid) for eid in entity_ids]
            stmt = (
                select(
                    EventAssociation.target_id,
                    func.count(case(
                        (EventAssociation.is_confirmed == True, 1),  # noqa: E712
                    )).label("confirmed"),
                    func.count(case(
                        (EventAssociation.is_dismissed == True, 1),  # noqa: E712
                    )).label("dismissed"),
                    func.count(literal_column("1")).label("total"),
                )
                .where(
                    EventAssociation.target_id.in_(entity_strs),
                    EventAssociation.family_id == family_id,
                )
                .group_by(EventAssociation.target_id)
            )
            result = await self._db.execute(stmt)
            rows = result.all()
            if not rows:
                return {}

            return {
                row.target_id: self._compute_curation_score(
                    row.confirmed, row.dismissed, row.total,
                )
                for row in rows
            }
        except Exception as e:
            logger.debug("Bulk curation feedback query failed: %s", e)
            return {}

    @staticmethod
    def _compute_curation_score(
        confirmed: int, dismissed: int, total: int,
    ) -> float:
        """Compute curation score from confirm/dismiss counts.

        - All confirmed -> 2.0
        - All dismissed -> 0.1
        - Mixed -> proportional between 0.1 and 2.0
        """
        if total == 0:
            return DEFAULT_SCORE
        confirm_ratio = confirmed / total
        dismiss_ratio = dismissed / total
        # Net sentiment: +1 for confirms, -1 for dismisses
        net = confirm_ratio - dismiss_ratio
        # Map [-1, 1] -> [0.1, 2.0]
        return MIN_SCORE + (net + 1.0) / 2.0 * (MAX_SCORE - MIN_SCORE)

    # ── Memory feedback ───────────────────────────────────────────────

    async def _get_memory_feedback_score(
        self, entity_id: UUID,
    ) -> Optional[float]:
        """Score from conversation_memories.feedback_weight."""
        try:
            from ...modules.memory.models import ConversationMemory
        except ImportError:
            return None

        try:
            stmt = (
                select(ConversationMemory.feedback_weight)
                .where(ConversationMemory.id == entity_id)
            )
            result = await self._db.execute(stmt)
            weight = result.scalar_one_or_none()
            if weight is None:
                return None
            # Clamp to our range
            return max(MIN_SCORE, min(MAX_SCORE, weight))
        except Exception as e:
            logger.debug("Memory feedback query failed: %s", e)
            return None

    async def _get_bulk_memory_scores(
        self, entity_ids: List[UUID],
    ) -> Dict[str, float]:
        """Bulk memory feedback scores."""
        try:
            from ...modules.memory.models import ConversationMemory
        except ImportError:
            return {}

        try:
            stmt = (
                select(
                    ConversationMemory.id,
                    ConversationMemory.feedback_weight,
                )
                .where(ConversationMemory.id.in_(entity_ids))
                .where(ConversationMemory.feedback_weight.isnot(None))
            )
            result = await self._db.execute(stmt)
            rows = result.all()
            if not rows:
                return {}

            return {
                str(row[0]): max(MIN_SCORE, min(MAX_SCORE, row[1]))
                for row in rows
            }
        except Exception as e:
            logger.debug("Bulk memory feedback query failed: %s", e)
            return {}
