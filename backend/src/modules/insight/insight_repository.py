"""Insight & Association Repository - Memory associations and cleanup.

MemoryRepository inherits from InsightRepository to compose both sets of operations.
Insight CRUD is now handled by InsightPipeline, InsightFeedbackService,
InsightQueryService, etc. for the unified `insights` table.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from ..memory.models import (
    ConversationMemory,
    MemoryAssociation,
    MemoryStatus,
)

logger = get_logger(__name__)


class InsightRepository:
    """Repository for memory associations and cleanup operations.

    Insight CRUD for the unified `insights` table is handled by dedicated
    services (InsightPipeline, InsightFeedbackService, InsightQueryService).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Memory Association ====================

    async def create_association(
        self,
        memory_id_a: UUID,
        memory_id_b: UUID,
        association_type: str,
        strength: float = 0.5,
        reason: Optional[str] = None,
        is_auto_generated: bool = True,
    ) -> Optional[MemoryAssociation]:
        """Create an association between two memories."""
        association = MemoryAssociation(
            memory_id_a=memory_id_a,
            memory_id_b=memory_id_b,
            association_type=association_type,
            strength=strength,
            reason=reason,
            is_auto_generated=is_auto_generated,
        )
        self.db.add(association)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            logger.debug(
                "Association already exists: %s <-> %s (%s)",
                memory_id_a,
                memory_id_b,
                association_type,
            )
            return None
        await self.db.refresh(association)
        return association

    async def get_associated_memories(
        self, memory_id: UUID, limit: int = 10,
    ) -> List[ConversationMemory]:
        """Get memories associated with a given memory."""
        query = select(MemoryAssociation).where(
            or_(
                MemoryAssociation.memory_id_a == memory_id,
                MemoryAssociation.memory_id_b == memory_id,
            )
        ).order_by(MemoryAssociation.strength.desc()).limit(limit)

        result = await self.db.execute(query)
        associations = list(result.scalars().all())

        other_ids = []
        for assoc in associations:
            if assoc.memory_id_a == memory_id:
                other_ids.append(assoc.memory_id_b)
            else:
                other_ids.append(assoc.memory_id_a)

        if not other_ids:
            return []

        mem_result = await self.db.execute(
            select(ConversationMemory).where(ConversationMemory.id.in_(other_ids))
        )
        return list(mem_result.scalars().all())

    # ==================== Cleanup ====================

    async def cleanup_expired_memories(self) -> int:
        """Mark expired memories as expired."""
        now = utc_now()
        result = await self.db.execute(
            update(ConversationMemory)
            .where(
                ConversationMemory.expires_at.isnot(None),
                ConversationMemory.expires_at < now,
                ConversationMemory.status == MemoryStatus.ACTIVE.value,
            )
            .values(status=MemoryStatus.EXPIRED.value, updated_at=now)
        )
        await self.db.commit()
        return result.rowcount
