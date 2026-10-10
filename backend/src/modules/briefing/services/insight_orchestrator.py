"""InsightOrchestrator -- Unified coordinator for insight generation.

Delegates all generation to InsightPipeline (unified pipeline) which replaces
the legacy three-system architecture (System A/B/C).

InsightPipeline handles: signal collection, LLM generation, dedup, preference
filtering, person budget, persistence to unified `insights` table, and sidekick
evaluation -- all in a single pipeline call.
"""
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ....core.utils.timezone import local_today
from ..schemas import InsightItem, InsightEntityRefItem

logger = get_logger(__name__)


class InsightOrchestrator:
    """Unified coordinator for insight generation.

    Delegates all generation to InsightPipeline which handles signal
    collection, LLM generation, dedup, preferences, person budget,
    persistence, and sidekick evaluation in a single pipeline call.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_all(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: Optional[date] = None,
    ) -> list:
        """Generate insights via the unified InsightPipeline.

        Returns list of Insight objects (from unified `insights` table).
        The pipeline internally handles:
        - Signal collection (events, relationships, commitments, memories, EAs)
        - Single Haiku LLM call for batch generation
        - Contextual reactivation of dismissed obligations
        - Dedup (obligation-identity based)
        - Preference filtering (type suppression + pierce logic)
        - Person budget (max 2 per person)
        - Persistence (INSERT ON CONFLICT DO NOTHING)
        - Sidekick evaluation
        """
        if target_date is None:
            target_date = local_today()

        from ...insight.insight_pipeline import InsightPipeline

        pipeline = InsightPipeline(self.db)
        try:
            insight_ids = await pipeline.run_scheduled(
                user_id=user_id,
                family_id=family_id,
                target_date=target_date,
            )
        except Exception:
            logger.error(
                "InsightPipeline.run_scheduled failed for user=%s",
                user_id, exc_info=True,
            )
            return []

        if not insight_ids:
            logger.info(
                "InsightOrchestrator: pipeline produced 0 insights for user=%s",
                user_id,
            )
            return []

        # Load the persisted Insight objects for callers that need them
        from ...insight.models import Insight
        from sqlalchemy import select

        result = await self.db.execute(
            select(Insight).where(Insight.id.in_(insight_ids))
        )
        insights = list(result.scalars().all())

        logger.info(
            "InsightOrchestrator: pipeline produced %d insights for user=%s",
            len(insights), user_id,
        )
        return insights

    async def get_for_briefing(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> List[InsightItem]:
        """Get insights for daily briefing from unified insights table."""
        from ...insight.insight_query_service import InsightQueryService

        if family_id is None:
            return []

        query_service = InsightQueryService(self.db)
        cards = await query_service.get_for_briefing(user_id, family_id, limit=limit)
        return [
            InsightItem(
                id=str(card.id),
                insight_type=card.insight_type,
                title=card.title,
                content=card.content,
                importance_score=card.importance,
                urgency_score=card.urgency,
                suggested_action=card.suggested_action,
                action_options=card.action_options,
                status=card.status,
                created_at=card.created_at,
                entity_refs=[
                    InsightEntityRefItem(
                        entity_type=e.entity_type,
                        entity_id=str(e.entity_id),
                    )
                    for e in card.entities
                ],
            )
            for card in cards
        ]
