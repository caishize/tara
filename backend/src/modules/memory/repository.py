"""Memory Repository - Data access layer for conversation memories.

Insight/association/cleanup operations are in insight_repository.py.
MemoryRepository inherits from InsightRepository to compose both sets of operations.
"""

import hashlib
import inspect
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text, update, delete, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...config.logging import get_logger
from ...core.audit.service import AuditService
from ...core.utils.timezone import utc_now
from .utils import escape_like_pattern
from ..insight.insight_repository import InsightRepository
from .models import (
    ConversationMemory,
    MemoryStatus,
    MemoryType,
    SensitivityLevel,
)


def compute_content_hash(
    content: str,
    memory_type: str,
    entities: Optional[Dict[str, Any]] = None,
) -> str:
    """Compute a deterministic MD5 hash for idempotent memory writes.

    The hash is based on the normalized combination of content, memory_type,
    and sorted JSON-serialized entities.
    """
    normalized_content = content.strip()
    entities_str = json.dumps(entities or {}, sort_keys=True, ensure_ascii=False)
    raw = f"{normalized_content}|{memory_type}|{entities_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

logger = get_logger(__name__)

# Ordered from most restrictive (highest) to least restrictive (lowest).
# A downgrade means moving from a higher index to a lower index.
_SENSITIVITY_RANK: Dict[str, int] = {
    SensitivityLevel.PUBLIC.value: 0,
    SensitivityLevel.FAMILY.value: 1,
    SensitivityLevel.PRIVATE.value: 2,
    SensitivityLevel.SENSITIVE.value: 3,
}


class MemoryRepository(InsightRepository):
    """Repository for conversation memories, insights, and associations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self._audit = AuditService(db)

    # ==================== Memory CRUD ====================

    async def create_memory(
        self,
        user_id: UUID,
        family_id: UUID,
        memory_type: str,
        content: str,
        summary: str,
        entities: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        importance: int = 5,
        confidence: float = 0.8,
        source_session_id: Optional[UUID] = None,
        source_message_id: Optional[UUID] = None,
        expires_at: Optional[datetime] = None,
        trigger_conditions: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
        sensitivity_level: Optional[str] = None,
        auto_commit: bool = True,
    ) -> ConversationMemory:
        """Create a new memory with duplicate detection and content_hash idempotency."""
        if not 1 <= importance <= 10:
            raise ValueError(f"importance must be between 1 and 10, got {importance}")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {confidence}")

        # Fast-path idempotent check via content_hash
        c_hash = compute_content_hash(content, memory_type, entities)
        existing_by_hash = await self._find_by_content_hash(user_id, c_hash)
        if existing_by_hash:
            logger.info(
                "Idempotent skip: content_hash %s already exists (memory %s)",
                c_hash,
                existing_by_hash.id,
            )
            return existing_by_hash

        duplicate = await self._find_duplicate(
            user_id=user_id,
            memory_type=memory_type,
            summary=summary,
            embedding=embedding,
        )
        if duplicate:
            duplicate.importance = min(10, duplicate.importance + 1)
            if auto_commit:
                await self.db.commit()
                await self.db.refresh(duplicate)
            logger.info(
                "Skipped duplicate memory (matched '%s'), boosted importance to %d",
                duplicate.summary[:50],
                duplicate.importance,
            )
            return duplicate

        memory = ConversationMemory(
            user_id=user_id,
            family_id=family_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            entities=entities or {},
            tags=tags or [],
            importance=importance,
            confidence=confidence,
            source_session_id=source_session_id,
            source_message_id=source_message_id,
            expires_at=expires_at,
            trigger_conditions=trigger_conditions or {},
            embedding=embedding,
            content_hash=c_hash,
            sensitivity_level=sensitivity_level or SensitivityLevel.PUBLIC.value,
        )
        self.db.add(memory)

        if auto_commit:
            await self.db.commit()
            await self.db.refresh(memory)

        return memory

    async def _find_by_content_hash(
        self,
        user_id: UUID,
        content_hash: str,
    ) -> Optional[ConversationMemory]:
        """Find an active memory with the same content_hash for a user."""
        result = await self.db.execute(
            select(ConversationMemory).where(
                ConversationMemory.user_id == user_id,
                ConversationMemory.content_hash == content_hash,
                ConversationMemory.status == MemoryStatus.ACTIVE.value,
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_duplicate(
        self,
        user_id: UUID,
        memory_type: str,
        summary: str,
        embedding: Optional[List[float]] = None,
        window_days: int = 7,
        similarity_threshold: float = 0.85,
    ) -> Optional[ConversationMemory]:
        """Find a semantically similar existing memory (embedding + text)."""
        since = utc_now() - timedelta(days=window_days)
        stmt = (
            select(ConversationMemory)
            .where(
                and_(
                    ConversationMemory.user_id == user_id,
                    ConversationMemory.memory_type == memory_type,
                    ConversationMemory.status == MemoryStatus.ACTIVE.value,
                    ConversationMemory.created_at >= since,
                )
            )
            .order_by(ConversationMemory.created_at.desc())
            .limit(20)
        )
        result = await self.db.execute(stmt)
        candidates = list(result.scalars().all())

        if not candidates:
            return None

        if embedding:
            for candidate in candidates:
                if candidate.embedding:
                    sim = self._cosine_similarity(embedding, candidate.embedding)
                    if sim >= similarity_threshold:
                        return candidate

        normalized_summary = summary.strip().lower()
        for candidate in candidates:
            candidate_summary = (candidate.summary or "").strip().lower()
            if not candidate_summary:
                continue
            if (
                normalized_summary == candidate_summary
                or (len(normalized_summary) > 10 and normalized_summary in candidate_summary)
                or (len(candidate_summary) > 10 and candidate_summary in normalized_summary)
            ):
                return candidate

        return None

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    async def create_memories_batch(
        self,
        memories: List[Dict[str, Any]],
    ) -> List[ConversationMemory]:
        """Create multiple memories in batch with transaction handling."""
        if not memories:
            return []

        memory_objects = []
        try:
            for mem_data in memories:
                memory = ConversationMemory(**mem_data)
                self.db.add(memory)
                memory_objects.append(memory)

            await self.db.commit()
            for mem in memory_objects:
                try:
                    await self.db.refresh(mem)
                except Exception as e:
                    logger.warning(f"Failed to refresh memory after batch create: {e}")
            return memory_objects
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Batch memory creation failed, rolled back: {e}")
            raise

    async def get_memory(self, memory_id: UUID) -> Optional[ConversationMemory]:
        """Get a single memory by ID."""
        result = await self.db.execute(
            select(ConversationMemory)
            .where(ConversationMemory.id == memory_id)
            .options(selectinload(ConversationMemory.insights))
        )
        return result.scalar_one_or_none()

    async def get_user_memories(
        self,
        user_id: UUID,
        memory_type: Optional[str] = None,
        status: str = MemoryStatus.ACTIVE.value,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ConversationMemory]:
        """Get memories for a user."""
        query = select(ConversationMemory).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == status,
        )
        if memory_type:
            query = query.where(ConversationMemory.memory_type == memory_type)
        query = query.order_by(ConversationMemory.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_user_memories(
        self,
        user_id: UUID,
        memory_type: Optional[str] = None,
        status: str = MemoryStatus.ACTIVE.value,
    ) -> int:
        """Count total memories for a user."""
        query = select(func.count(ConversationMemory.id)).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == status,
        )
        if memory_type:
            query = query.where(ConversationMemory.memory_type == memory_type)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_family_memories(
        self,
        family_id: UUID,
        memory_types: Optional[List[str]] = None,
        status: str = MemoryStatus.ACTIVE.value,
        limit: int = 50,
    ) -> List[ConversationMemory]:
        """Get memories for a family."""
        query = select(ConversationMemory).where(
            ConversationMemory.family_id == family_id,
            ConversationMemory.status == status,
        )
        if memory_types:
            query = query.where(ConversationMemory.memory_type.in_(memory_types))
        query = query.order_by(
            ConversationMemory.importance.desc(),
            ConversationMemory.created_at.desc(),
        ).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_memory(self, memory_id: UUID, **kwargs) -> Optional[ConversationMemory]:
        """Update a memory.

        If ``sensitivity_level`` is being lowered (privacy downgrade), an
        audit event of type ``privacy_downgrade`` is logged before the
        update is committed.
        """
        new_sensitivity = kwargs.get("sensitivity_level")

        # Detect privacy downgrade before applying the update.
        old_sensitivity: Optional[str] = None
        memory_for_audit: Optional[ConversationMemory] = None
        if new_sensitivity is not None:
            memory_for_audit = await self.get_memory(memory_id)
            if memory_for_audit is not None:
                old_sensitivity = memory_for_audit.sensitivity_level

        kwargs["updated_at"] = utc_now()
        await self.db.execute(
            update(ConversationMemory)
            .where(ConversationMemory.id == memory_id)
            .values(**kwargs)
        )

        # Log privacy downgrade audit event when sensitivity is lowered.
        if (
            old_sensitivity is not None
            and new_sensitivity is not None
            and _SENSITIVITY_RANK.get(old_sensitivity, 0)
            > _SENSITIVITY_RANK.get(new_sensitivity, 0)
            and memory_for_audit is not None
        ):
            await self._audit.log_event(
                user_id=memory_for_audit.user_id,
                family_id=memory_for_audit.family_id,
                event_type="privacy_downgrade",
                event_data={
                    "memory_id": str(memory_id),
                    "old_level": old_sensitivity,
                    "new_level": new_sensitivity,
                },
            )

        await self.db.commit()
        return await self.get_memory(memory_id)

    async def mark_memory_recalled(self, memory_id: UUID) -> Optional[ConversationMemory]:
        """Mark a memory as recalled (increases recall count)."""
        await self.db.execute(
            update(ConversationMemory)
            .where(ConversationMemory.id == memory_id)
            .values(
                last_recalled_at=utc_now(),
                recall_count=ConversationMemory.recall_count + 1,
                updated_at=utc_now(),
            )
        )
        await self.db.commit()
        return await self.get_memory(memory_id)

    async def mark_memories_recalled_batch(self, memory_ids: List[UUID]) -> int:
        """Mark multiple memories as recalled in a single query."""
        if not memory_ids:
            return 0
        result = await self.db.execute(
            update(ConversationMemory)
            .where(ConversationMemory.id.in_(memory_ids))
            .values(
                last_recalled_at=utc_now(),
                recall_count=ConversationMemory.recall_count + 1,
                updated_at=utc_now(),
            )
        )
        await self.db.commit()
        return result.rowcount

    async def delete_memory(self, memory_id: UUID) -> bool:
        """Delete a memory."""
        memory = await self.get_memory(memory_id)
        if memory:
            await self._audit.log_event(
                user_id=memory.user_id,
                family_id=memory.family_id,
                event_type="memory_deleted",
                event_data={
                    "memory_id": str(memory_id),
                    "memory_type": memory.memory_type,
                    "summary": (memory.summary or "")[:200],
                },
            )
        result = await self.db.execute(
            delete(ConversationMemory).where(ConversationMemory.id == memory_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def archive_memory(self, memory_id: UUID) -> Optional[ConversationMemory]:
        """Archive a memory."""
        memory = await self.get_memory(memory_id)
        if memory:
            await self._audit.log_event(
                user_id=memory.user_id,
                family_id=memory.family_id,
                event_type="memory_archived",
                event_data={
                    "memory_id": str(memory_id),
                    "memory_type": memory.memory_type,
                    "summary": (memory.summary or "")[:200],
                },
            )
        return await self.update_memory(memory_id, status=MemoryStatus.ARCHIVED.value)

    async def complete_memory(self, memory_id: UUID) -> Optional[ConversationMemory]:
        """Mark a plan/task memory as completed."""
        return await self.update_memory(memory_id, status=MemoryStatus.COMPLETED.value)

    # ==================== Memory Search & Recall ====================

    async def search_by_tags(
        self, user_id: UUID, tags: List[str], limit: int = 20,
    ) -> List[ConversationMemory]:
        """Search memories by tags (any match)."""
        query = select(ConversationMemory).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == MemoryStatus.ACTIVE.value,
            ConversationMemory.tags.overlap(tags),
        ).order_by(ConversationMemory.importance.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_by_entities(
        self, user_id: UUID, entity_key: str, entity_value: str, limit: int = 20,
    ) -> List[ConversationMemory]:
        """Search memories by entity key-value."""
        query = select(ConversationMemory).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == MemoryStatus.ACTIVE.value,
            ConversationMemory.entities.contains({entity_key: entity_value}),
        ).order_by(ConversationMemory.importance.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_by_location(
        self, user_id: UUID, location: str, limit: int = 20,
        created_after: Optional[datetime] = None,
    ) -> List[ConversationMemory]:
        """Search memories related to a location using full-text search indexes.

        Args:
            created_after: If provided, only return memories created after this
                datetime.  Useful for filtering out stale memories from
                cancelled / completed trips to the same destination.
        """
        location_lower = location.lower()
        location_escaped = escape_like_pattern(location_lower)

        conditions = [
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == MemoryStatus.ACTIVE.value,
            or_(
                ConversationMemory.entities["location"].astext.ilike(f"%{location_escaped}%"),
                func.to_tsvector('simple', ConversationMemory.summary).op('@@')(
                    func.plainto_tsquery('simple', location)
                ),
                ConversationMemory.tags.contains([location_lower]),
            ),
        ]
        if created_after is not None:
            conditions.append(ConversationMemory.created_at >= created_after)

        query = (
            select(ConversationMemory)
            .where(*conditions)
            .order_by(ConversationMemory.importance.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_by_person(
        self, user_id: UUID, person_name: str, limit: int = 20,
    ) -> List[ConversationMemory]:
        """Search memories related to a person using full-text search indexes."""
        person_lower = person_name.lower()
        person_escaped = escape_like_pattern(person_lower)

        query = select(ConversationMemory).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == MemoryStatus.ACTIVE.value,
            or_(
                ConversationMemory.entities["person"].astext.ilike(f"%{person_escaped}%"),
                func.cast(ConversationMemory.entities["persons"], String).ilike(f"%{person_escaped}%"),
                func.to_tsvector('simple', ConversationMemory.summary).op('@@')(
                    func.plainto_tsquery('simple', person_name)
                ),
            )
        ).order_by(ConversationMemory.importance.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_recent_memories(
        self, user_id: UUID, days: int = 7, limit: int = 20,
    ) -> List[ConversationMemory]:
        """Get recent memories within N days."""
        since = utc_now() - timedelta(days=days)
        query = select(ConversationMemory).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == MemoryStatus.ACTIVE.value,
            ConversationMemory.created_at >= since,
        ).order_by(ConversationMemory.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_plan_memories(
        self, user_id: UUID, include_completed: bool = False, limit: int = 20,
    ) -> List[ConversationMemory]:
        """Get plan/schedule type memories."""
        statuses = [MemoryStatus.ACTIVE.value]
        if include_completed:
            statuses.append(MemoryStatus.COMPLETED.value)
        query = select(ConversationMemory).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.memory_type.in_([MemoryType.PLAN.value, MemoryType.SCHEDULE.value]),
            ConversationMemory.status.in_(statuses),
        ).order_by(
            ConversationMemory.importance.desc(),
            ConversationMemory.created_at.desc(),
        ).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_triggered_memories(
        self,
        user_id: UUID,
        trigger_type: str,
        trigger_value: str,
        limit: int = 10,
        proximity_km: float = 50.0,
    ) -> List[ConversationMemory]:
        """Get memories triggered by a given condition (text + proximity match)."""
        trigger_value_lower = trigger_value.lower()

        query = select(ConversationMemory).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == MemoryStatus.ACTIVE.value,
            ConversationMemory.trigger_conditions.isnot(None),
            ConversationMemory.trigger_conditions != {},
            ConversationMemory.trigger_conditions["type"].astext == trigger_type,
        ).order_by(ConversationMemory.importance.desc()).limit(limit * 3)

        result = await self.db.execute(query)
        memories = list(result.scalars().all())

        # Pass 1: exact text match
        matched_memories = []
        unmatched = []
        for mem in memories:
            cond_value = mem.trigger_conditions.get("value", "").lower()
            if cond_value in trigger_value_lower or trigger_value_lower in cond_value:
                matched_memories.append(mem)
            else:
                unmatched.append(mem)

        # Pass 2: proximity match for location triggers
        if (
            trigger_type == "location_mention"
            and len(matched_memories) < limit
            and unmatched
        ):
            try:
                from ...core.utils.geocoding import locations_within_radius

                for mem in unmatched:
                    if len(matched_memories) >= limit:
                        break
                    cond_value = mem.trigger_conditions.get("value", "")
                    if not cond_value:
                        continue
                    nearby = await locations_within_radius(
                        trigger_value, cond_value, radius_km=proximity_km,
                    )
                    if nearby:
                        matched_memories.append(mem)
            except Exception as e:
                logger.debug("Proximity matching skipped: %s", e)

        return matched_memories[:limit]

    async def mark_memory_triggered(self, memory_id: UUID) -> Optional[ConversationMemory]:
        """Mark a memory as triggered."""
        await self.db.execute(
            update(ConversationMemory)
            .where(ConversationMemory.id == memory_id)
            .values(
                last_triggered_at=utc_now(),
                trigger_count=ConversationMemory.trigger_count + 1,
                updated_at=utc_now(),
            )
        )
        await self.db.commit()
        return await self.get_memory(memory_id)

    async def mark_memories_triggered_batch(self, memory_ids: List[UUID]) -> int:
        """Mark multiple memories as triggered in a single query."""
        if not memory_ids:
            return 0
        result = await self.db.execute(
            update(ConversationMemory)
            .where(ConversationMemory.id.in_(memory_ids))
            .values(
                last_triggered_at=utc_now(),
                trigger_count=ConversationMemory.trigger_count + 1,
                updated_at=utc_now(),
            )
        )
        await self.db.commit()
        return result.rowcount

    async def full_text_search(
        self, user_id: UUID, query_text: str, limit: int = 20,
    ) -> List[ConversationMemory]:
        """Full text search in summary using PostgreSQL FTS indexes."""
        query = select(ConversationMemory).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == MemoryStatus.ACTIVE.value,
            func.to_tsvector('simple', ConversationMemory.summary).op('@@')(
                func.plainto_tsquery('simple', query_text)
            )
        ).order_by(ConversationMemory.importance.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_memories_with_embedding(
        self, user_id: UUID, limit: int = 100,
    ) -> List[ConversationMemory]:
        """Get memories that have embeddings for semantic search."""
        query = select(ConversationMemory).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == MemoryStatus.ACTIVE.value,
            ConversationMemory.embedding.isnot(None),
        ).order_by(
            (ConversationMemory.importance * ConversationMemory.feedback_weight).desc()
        ).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def has_pgvector(self) -> bool:
        """Check if pgvector extension and embedding_v column are available."""
        try:
            result = await self.db.execute(
                text("SELECT 1 FROM information_schema.columns "
                     "WHERE table_name = 'conversation_memories' "
                     "AND column_name = 'embedding_v'")
            )
            return result.scalar_one_or_none() is not None
        except Exception:
            return False

    async def update_memory_embedding(
        self, memory_id: UUID, embedding: List[float],
    ) -> bool:
        """Update the embedding for a memory (both ARRAY and pgvector columns)."""
        result = await self.db.execute(
            update(ConversationMemory)
            .where(ConversationMemory.id == memory_id)
            .values(embedding=embedding, updated_at=utc_now())
        )

        # Also update pgvector column if available
        await self._sync_embedding_v(memory_id, embedding)

        await self.db.commit()
        return result.rowcount > 0

    async def update_memory_embedding_batch(
        self, memory_embeddings: List[Tuple[UUID, List[float]]],
    ) -> int:
        """Update embeddings for multiple memories (both ARRAY and pgvector columns)."""
        if not memory_embeddings:
            return 0
        count = 0
        for memory_id, embedding in memory_embeddings:
            result = await self.db.execute(
                update(ConversationMemory)
                .where(ConversationMemory.id == memory_id)
                .values(embedding=embedding, updated_at=utc_now())
            )
            count += result.rowcount
            await self._sync_embedding_v(memory_id, embedding)
        await self.db.commit()
        return count

    async def _sync_embedding_v(
        self, memory_id: UUID, embedding: List[float],
    ) -> None:
        """Sync the pgvector embedding_v column from the ARRAY embedding.

        Silently skips if pgvector is not available.
        """
        try:
            from .config import memory_config

            expected_dimension = int(memory_config.embedding_dimension)
            if len(embedding) != expected_dimension:
                logger.debug(
                    "Skipping embedding_v sync for memory=%s: dimension mismatch "
                    "(expected=%d, got=%d)",
                    memory_id,
                    expected_dimension,
                    len(embedding),
                )
                return

            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

            # Use a nested transaction so pgvector casting/operator failures
            # do not poison the caller's outer transaction.
            nested_tx = self.db.begin_nested()
            if inspect.isawaitable(nested_tx):
                nested_tx = await nested_tx

            async with nested_tx:
                await self.db.execute(
                    text(
                        "UPDATE conversation_memories "
                        "SET embedding_v = CAST(:embedding AS vector) "
                        "WHERE id = :memory_id"
                    ),
                    {"embedding": embedding_str, "memory_id": str(memory_id)},
                )
        except Exception as e:
            logger.debug("Skipping embedding_v sync (pgvector may not be available): %s", e)

    # ==================== User Feedback ====================

    async def record_memory_dismiss(
        self, memory_id: UUID, weight_decay: float = 0.1,
    ) -> Optional[ConversationMemory]:
        """Record insight dismissal — decreases feedback_weight."""
        memory = await self.get_memory(memory_id)
        if not memory:
            return None
        new_weight = max(0.1, memory.feedback_weight - weight_decay)
        await self.db.execute(
            update(ConversationMemory)
            .where(ConversationMemory.id == memory_id)
            .values(
                dismiss_count=ConversationMemory.dismiss_count + 1,
                feedback_weight=new_weight,
                updated_at=utc_now(),
            )
        )
        await self.db.commit()
        return await self.get_memory(memory_id)

    async def record_memory_useful(
        self, memory_id: UUID, weight_boost: float = 0.1,
    ) -> Optional[ConversationMemory]:
        """Record insight useful — increases feedback_weight."""
        memory = await self.get_memory(memory_id)
        if not memory:
            return None
        new_weight = min(2.0, memory.feedback_weight + weight_boost)
        await self.db.execute(
            update(ConversationMemory)
            .where(ConversationMemory.id == memory_id)
            .values(
                useful_count=ConversationMemory.useful_count + 1,
                feedback_weight=new_weight,
                updated_at=utc_now(),
            )
        )
        await self.db.commit()
        return await self.get_memory(memory_id)

    async def mark_memories_superseded(
        self,
        memory_ids: List[UUID],
        superseded_by: UUID,
    ) -> int:
        """Mark memories as superseded by a summary/consolidated record."""
        if not memory_ids:
            return 0
        result = await self.db.execute(
            update(ConversationMemory)
            .where(ConversationMemory.id.in_(memory_ids))
            .values(
                status=MemoryStatus.SUPERSEDED.value,
                superseded_by=superseded_by,
                updated_at=utc_now(),
            )
        )
        await self.db.commit()
        return result.rowcount

    async def get_suppressed_memories(
        self, user_id: UUID, max_dismiss_count: int = 5,
    ) -> List[ConversationMemory]:
        """Get memories dismissed too many times."""
        query = select(ConversationMemory).where(
            ConversationMemory.user_id == user_id,
            ConversationMemory.status == MemoryStatus.ACTIVE.value,
            ConversationMemory.dismiss_count >= max_dismiss_count,
        ).order_by(ConversationMemory.dismiss_count.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def semantic_search(
        self,
        user_id: UUID,
        query_embedding: List[float],
        similarity_threshold: float = 0.7,
        limit: int = 10,
    ) -> List[Tuple[ConversationMemory, float]]:
        """Search memories by semantic similarity using embeddings.

        Uses a two-tier strategy:
        1. Try pgvector (O(log n) HNSW) if the extension is available.
        2. Fall back to in-memory ARRAY cosine similarity with explicit
           logging and a Prometheus metric so operators can track how
           often the fallback path is taken.
        """
        from ...core.observability.metrics import vector_search_fallback_total

        pgvector_available = await self.has_pgvector()

        if pgvector_available:
            try:
                results = await self.semantic_search_pgvector(
                    user_id=user_id,
                    query_embedding=query_embedding,
                    similarity_threshold=similarity_threshold,
                    limit=limit,
                )
                if results:
                    return results
                # pgvector returned empty -- fall through to ARRAY path
                logger.debug(
                    "pgvector search returned no results for user=%s, "
                    "falling back to in-memory ARRAY cosine",
                    user_id,
                )
                vector_search_fallback_total.labels(reason="empty_result").inc()
            except Exception as e:
                try:
                    await self.db.rollback()
                except Exception:
                    logger.debug(
                        "Failed to rollback session after pgvector search error",
                        exc_info=True,
                    )
                logger.warning(
                    "pgvector search failed for user=%s, falling back to "
                    "in-memory ARRAY cosine: %s",
                    user_id,
                    e,
                )
                vector_search_fallback_total.labels(reason="pgvector_error").inc()
        else:
            logger.info(
                "pgvector extension not available, using in-memory ARRAY "
                "cosine similarity for user=%s",
                user_id,
            )
            vector_search_fallback_total.labels(reason="no_pgvector").inc()

        # Fallback: in-memory ARRAY cosine similarity
        memories = await self.get_memories_with_embedding(user_id, limit=200)
        if not memories or not query_embedding:
            return []

        results = []
        for memory in memories:
            if memory.embedding:
                similarity = self._cosine_similarity(query_embedding, memory.embedding)
                weighted_similarity = similarity * memory.feedback_weight
                if weighted_similarity >= similarity_threshold:
                    results.append((memory, weighted_similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def semantic_search_pgvector(
        self,
        user_id: UUID,
        query_embedding: List[float],
        similarity_threshold: float = 0.7,
        limit: int = 10,
    ) -> List[Tuple[ConversationMemory, float]]:
        """Search memories using pgvector for O(log n) performance."""
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        query = text("""
            SELECT
                cm.id,
                (1 - (embedding_v <=> CAST(:embedding AS vector))) * feedback_weight as weighted_similarity
            FROM conversation_memories cm
            WHERE cm.user_id = :user_id
            AND cm.status = 'active'
            AND cm.embedding_v IS NOT NULL
            AND (1 - (embedding_v <=> CAST(:embedding AS vector))) >= :threshold
            ORDER BY weighted_similarity DESC
            LIMIT :limit
        """)

        result = await self.db.execute(
            query,
            {
                "user_id": str(user_id),
                "embedding": embedding_str,
                "threshold": similarity_threshold,
                "limit": limit,
            }
        )
        rows = result.fetchall()

        if not rows:
            return []

        id_similarity_map = {row.id: row.weighted_similarity for row in rows}

        memories_query = (
            select(ConversationMemory)
            .where(ConversationMemory.id.in_(id_similarity_map.keys()))
            .options(selectinload(ConversationMemory.insights))
        )
        memories_result = await self.db.execute(memories_query)
        memories_by_id = {m.id: m for m in memories_result.scalars().all()}

        results = []
        for memory_id, similarity in id_similarity_map.items():
            if memory_id in memories_by_id:
                results.append((memories_by_id[memory_id], similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # Insight CRUD, Association, and Cleanup methods are inherited from
    # InsightRepository (see insight_repository.py).
