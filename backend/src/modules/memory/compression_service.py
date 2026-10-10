"""Memory Compression Service - Compresses and summarizes old memories.

Implements automatic compression of daily memories while preserving
critical information based on tags and importance thresholds.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import and_, distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.settings import settings
from .config import get_memory_config
from .models import ConversationMemory, MemoryStatus
from .repository import MemoryRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CompressionResult:
    """Result of a memory compression operation."""
    memories_analyzed: int
    memories_compressed: int
    critical_preserved: int
    summaries_created: int
    errors: int


@dataclass(frozen=True)
class CompressedMemorySummary:
    """A compressed summary of multiple memories."""
    date: date
    summary: str
    original_memory_ids: Tuple[UUID, ...]
    key_entities: Dict[str, Any]
    tags: Tuple[str, ...]
    importance: int


class MemoryCompressionService:
    """Service for compressing old memories into summaries."""

    def __init__(
        self,
        db: AsyncSession,
        client: Optional[AsyncAnthropic] = None,
    ):
        self.db = db
        self._memory_repo = MemoryRepository(db)
        self._config = get_memory_config()
        self._client = client
        self._model = (
            self._config.compression_model
            or settings.fast_worker_model
            or settings.intent_router_model
        )

    @property
    def client(self):
        """Get or create Anthropic client via shared factory."""
        if self._client is None:
            from ...core.llm.haiku_client import get_haiku_client
            self._client = get_haiku_client()
        return self._client

    def _is_critical_memory(self, memory: ConversationMemory) -> bool:
        """Check if a memory is critical and should never be compressed."""
        importance_threshold = getattr(
            self._config, 'compression_importance_threshold', 8
        )
        if memory.importance >= importance_threshold:
            return True

        critical_tags = getattr(
            self._config, 'critical_tags',
            ["health", "allergy", "birthday", "emergency_contact", "legal"]
        )

        memory_tags_lower = {t.lower() for t in (memory.tags or [])}
        for tag in critical_tags:
            if tag.lower() in memory_tags_lower:
                return True

        entities = memory.entities or {}
        critical_entity_keys = {"allergy", "medical", "emergency", "birthday"}
        for key in entities.keys():
            if key.lower() in critical_entity_keys:
                return True

        return False

    async def compress_daily_memories(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: date,
    ) -> CompressionResult:
        """Compress memories from a specific date into a summary."""
        logger.info(
            "Starting memory compression for user=%s, date=%s", user_id, target_date
        )

        start_of_day = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        end_of_day = datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc)

        memories = await self._get_memories_for_date(
            user_id=user_id, start_time=start_of_day, end_time=end_of_day,
        )

        if not memories:
            logger.info("No memories found for date %s", target_date)
            return CompressionResult(
                memories_analyzed=0, memories_compressed=0,
                critical_preserved=0, summaries_created=0, errors=0,
            )

        critical_memories: List[ConversationMemory] = []
        compressible_memories: List[ConversationMemory] = []

        for memory in memories:
            if self._is_critical_memory(memory):
                critical_memories.append(memory)
            else:
                compressible_memories.append(memory)

        logger.info(
            "Found %d memories: %d critical, %d compressible",
            len(memories), len(critical_memories), len(compressible_memories),
        )

        min_memories_to_compress = getattr(
            self._config, 'compression_min_memories', 3
        )
        if len(compressible_memories) < min_memories_to_compress:
            logger.info(
                "Not enough memories to compress (need %d, have %d)",
                min_memories_to_compress, len(compressible_memories),
            )
            return CompressionResult(
                memories_analyzed=len(memories), memories_compressed=0,
                critical_preserved=len(critical_memories), summaries_created=0, errors=0,
            )

        errors = 0
        summaries_created = 0

        try:
            summary = await self._generate_summary(
                memories=compressible_memories, target_date=target_date,
            )

            if summary:
                await self._create_summary_memory(
                    user_id=user_id, family_id=family_id, summary=summary,
                    original_memories=compressible_memories, target_date=target_date,
                )
                summaries_created = 1

                for memory in compressible_memories:
                    await self._memory_repo.archive_memory(memory.id)

        except Exception as e:
            logger.error("Error during memory compression: %s", e)
            errors = 1

        result = CompressionResult(
            memories_analyzed=len(memories),
            memories_compressed=len(compressible_memories) if summaries_created > 0 else 0,
            critical_preserved=len(critical_memories),
            summaries_created=summaries_created,
            errors=errors,
        )
        logger.info("Compression complete: %s", result)
        return result

    async def _get_memories_for_date(
        self, user_id: UUID, start_time: datetime, end_time: datetime,
    ) -> List[ConversationMemory]:
        """Get compressible memories created within a time range.

        Includes both ACTIVE and SUPERSEDED memories so that compression
        remains effective even when consolidation has already marked
        memories as SUPERSEDED (the two services become order-independent).
        """
        query = select(ConversationMemory).where(
            and_(
                ConversationMemory.user_id == user_id,
                ConversationMemory.status.in_([
                    MemoryStatus.ACTIVE.value,
                    MemoryStatus.SUPERSEDED.value,
                ]),
                ConversationMemory.created_at >= start_time,
                ConversationMemory.created_at <= end_time,
            )
        ).order_by(ConversationMemory.created_at.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _generate_summary(
        self,
        memories: List[ConversationMemory],
        target_date: date,
    ) -> Optional[CompressedMemorySummary]:
        """Generate a summary of memories using LLM."""
        if not memories:
            return None

        memory_texts = []
        all_tags: Set[str] = set()
        all_entities: Dict[str, Any] = {}
        max_importance = 1

        for memory in memories:
            memory_texts.append(f"- {memory.summary}")
            all_tags.update(memory.tags or [])
            if memory.entities:
                all_entities.update(memory.entities)
            max_importance = max(max_importance, memory.importance)

        memories_content = "\n".join(memory_texts)

        prompt = f"""请将以下 {target_date} 的记忆内容压缩成一个简洁的日总结。

记忆列表:
{memories_content}

要求:
1. 用中文撰写
2. 保留关键信息（人物、地点、事件）
3. 总结不超过 200 字
4. 突出重要事件和决定

请直接输出总结内容，不需要标题或前缀。"""

        try:
            response = await self.client.messages.create(
                model=self._model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            summary_text = response.content[0].text.strip()

            return CompressedMemorySummary(
                date=target_date,
                summary=summary_text,
                original_memory_ids=tuple(m.id for m in memories),
                key_entities=all_entities,
                tags=tuple(all_tags),
                importance=max_importance,
            )
        except Exception as e:
            logger.error("LLM summarization failed: %s", e)
            return None

    async def _create_summary_memory(
        self,
        user_id: UUID,
        family_id: UUID,
        summary: CompressedMemorySummary,
        original_memories: List[ConversationMemory],
        target_date: date,
    ) -> ConversationMemory:
        """Create a new memory from the compressed summary."""
        return await self._memory_repo.create_memory(
            user_id=user_id,
            family_id=family_id,
            memory_type="daily_summary",
            content=summary.summary,
            summary=f"{target_date.isoformat()} 日总结",
            entities={
                **summary.key_entities,
                "compressed_from": [str(mid) for mid in summary.original_memory_ids],
                "original_count": len(original_memories),
            },
            tags=list(summary.tags) + ["compressed", "daily_summary"],
            importance=summary.importance,
            confidence=0.9,
        )

    async def run_daily_compression(
        self, days_ago: int = 7,
    ) -> Dict[str, CompressionResult]:
        """Run compression for all users for memories from N days ago."""
        from ...core.utils.timezone import utc_now
        target_date = utc_now().date() - timedelta(days=days_ago)
        logger.debug("Running daily compression for date: %s", target_date)

        target_start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        target_end = datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc)

        query = select(
            distinct(ConversationMemory.user_id),
            ConversationMemory.family_id,
        ).where(
            and_(
                ConversationMemory.status.in_([
                    MemoryStatus.ACTIVE.value,
                    MemoryStatus.SUPERSEDED.value,
                ]),
                ConversationMemory.created_at >= target_start,
                ConversationMemory.created_at <= target_end,
            )
        )

        result = await self.db.execute(query)
        user_family_pairs = result.fetchall()

        results: Dict[str, CompressionResult] = {}

        for user_id, family_id in user_family_pairs:
            try:
                compression_result = await self.compress_daily_memories(
                    user_id=user_id, family_id=family_id, target_date=target_date,
                )
                results[str(user_id)] = compression_result
            except Exception as e:
                logger.error("Compression failed for user %s: %s", user_id, e)
                results[str(user_id)] = CompressionResult(
                    memories_analyzed=0, memories_compressed=0,
                    critical_preserved=0, summaries_created=0, errors=1,
                )

        return results
