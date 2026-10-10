"""Memory Recall Service - Two-stage Retrieve-then-Filter architecture.

Stage 1 (Wide Retrieval):
  - Vector search TOP-30 (primary signal, parallel)
  - Triggered memories (highest priority, independent)
  - Keyword/location/person search TOP-10 (auxiliary, parallel)
  - Merge & deduplicate -> candidate set (~30-40 items)

Stage 2 (Precision Reranking):
  - If candidates > limit: Haiku LLM reranking -> TOP-N
  - If candidates <= limit: return directly (no LLM call)
"""

import asyncio
import json
import re
from datetime import timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from ..member.models import PersonProfile
from .utils import (
    extract_locations_async,
    extract_persons_async,
    contains_plan_keywords,
    find_person_profile_by_name,
)
from .config import memory_config
from .models import ConversationMemory, MemoryAssociation, MemoryType, MemoryStatus
from .repository import MemoryRepository

# Statuses that should be excluded from recall results
_EXCLUDED_RECALL_STATUSES = frozenset({
    MemoryStatus.SUPERSEDED.value,
    MemoryStatus.ARCHIVED.value,
    MemoryStatus.CANCELLED.value,
})

logger = get_logger(__name__)


class MemoryRecallService:
    """Service for recalling relevant memories based on context."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory_repo = MemoryRepository(db)
        self.config = memory_config
        self._embedding_service = None
        self._contact_service = None
        self._secretary_note_service = None
        self._knowledge_graph_service = None
        self._anthropic_client = None

    @property
    def embedding_service(self):
        """Lazy-load embedding service."""
        if self._embedding_service is None:
            from .embedding_service import EmbeddingService
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    @property
    def contact_service(self):
        """Lazy-load contact extraction service."""
        if self._contact_service is None:
            from .auto_contact_extraction_service import (
                AutoContactExtractionService,
            )
            self._contact_service = AutoContactExtractionService(self.db)
        return self._contact_service

    @property
    def secretary_note_service(self):
        """Lazy-load secretary note service."""
        if self._secretary_note_service is None:
            from .secretary_note_service import SecretaryNoteService
            self._secretary_note_service = SecretaryNoteService(self.db)
        return self._secretary_note_service

    @property
    def knowledge_graph_service(self):
        """Lazy-load knowledge graph service."""
        if self._knowledge_graph_service is None:
            from ..views.services.knowledge_graph_service import KnowledgeGraphService
            self._knowledge_graph_service = KnowledgeGraphService(self.db)
        return self._knowledge_graph_service

    @property
    def anthropic_client(self):
        """Lazy-init AsyncAnthropic client for reranking (connection pool reuse)."""
        if self._anthropic_client is None:
            from ...core.llm.haiku_client import get_haiku_client
            self._anthropic_client = get_haiku_client()
        return self._anthropic_client

    # ------------------------------------------------------------------
    # Two-stage recall: Retrieve-then-Filter
    # ------------------------------------------------------------------

    async def recall_for_message(
        self,
        user_id: UUID,
        message: str,
        limit: int = None,
    ) -> Tuple[List[ConversationMemory], str]:
        """Recall relevant memories using a two-stage pipeline.

        Stage 0: Collect triggered memories (highest priority, always included).
        Stage 1: Wide retrieval -- vector search + keyword/location/person
                 searches run in parallel, then merge & deduplicate.
        Stage 2: Precision reranking -- if |candidates| > limit, use Haiku
                 LLM to select the most relevant TOP-N; otherwise return as-is.

        Returns: (memories, context_string_for_llm)
        """
        if limit is None:
            limit = self.config.recall_default_limit
        if not 1 <= limit <= self.config.recall_max_limit:
            raise ValueError(
                f"limit must be between 1 and {self.config.recall_max_limit}, got {limit}"
            )

        # Extract entities once to avoid duplicate LLM/regex calls in sub-stages
        locations = await extract_locations_async(message)
        persons = await extract_persons_async(message)

        # Stage 0: Triggered memories (independent, highest priority)
        triggered_memories = await self._collect_triggered(user_id, message, locations, persons)

        # Stage 1: Wide retrieval (parallel vector + keyword searches)
        candidates = await self._wide_retrieval(user_id, message, locations, persons)

        # Merge & deduplicate (triggered first, then wide retrieval)
        all_candidates = self._merge_and_dedup(triggered_memories, candidates)

        # Defensive filter: exclude SUPERSEDED / ARCHIVED / CANCELLED
        all_candidates = [
            m for m in all_candidates
            if m.status not in _EXCLUDED_RECALL_STATUSES
        ]

        # Stage 2: Precision reranking or truncation
        if len(all_candidates) > limit:
            all_candidates = await self._rerank(message, all_candidates, limit)
        else:
            all_candidates = all_candidates[:limit]

        # Mark recalled / triggered in DB
        if all_candidates:
            await self.memory_repo.mark_memories_recalled_batch(
                [m.id for m in all_candidates]
            )
        if triggered_memories:
            await self.memory_repo.mark_memories_triggered_batch(
                [m.id for m in triggered_memories]
            )

        context_str = self._format_memories_for_llm(
            all_candidates, {}, triggered_memories
        )
        return all_candidates, context_str

    # ------------------------------------------------------------------
    # Stage 0: Triggered memory collection
    # ------------------------------------------------------------------

    async def _collect_triggered(
        self,
        user_id: UUID,
        message: str,
        locations: List[str],
        persons: List[str],
    ) -> List[ConversationMemory]:
        """Collect memories whose trigger conditions match the message."""
        triggered: List[ConversationMemory] = []
        seen_ids: set = set()

        for location in locations:
            mems = await self.memory_repo.get_triggered_memories(
                user_id, "location_mention", location,
                limit=self.config.recall_triggered_limit,
            )
            for mem in mems:
                if mem.id not in seen_ids:
                    triggered.append(mem)
                    seen_ids.add(mem.id)

        for person in persons:
            mems = await self.memory_repo.get_triggered_memories(
                user_id, "person_mention", person,
                limit=self.config.recall_triggered_limit,
            )
            for mem in mems:
                if mem.id not in seen_ids:
                    triggered.append(mem)
                    seen_ids.add(mem.id)

        return triggered

    # ------------------------------------------------------------------
    # Stage 1: Wide retrieval (parallel)
    # ------------------------------------------------------------------

    _WIDE_VECTOR_LIMIT = 30
    _WIDE_AUX_PER_ITEM_LIMIT = 3
    _WIDE_AUX_KEYWORD_LIMIT = 2

    async def _wide_retrieval(
        self,
        user_id: UUID,
        message: str,
        locations: List[str],
        persons: List[str],
    ) -> List[ConversationMemory]:
        """Stage 1: Wide parallel retrieval -- vector search as primary signal,
        keyword/location/person as auxiliary signals."""
        keywords = self._extract_keywords(message)

        tasks: List[asyncio.Task] = []

        # Primary: vector search TOP-30
        if (
            self.config.semantic_search_enabled
            and len(message) >= self.config.min_message_length
        ):
            tasks.append(
                self._semantic_search_as_memories(
                    user_id, message, limit=self._WIDE_VECTOR_LIMIT,
                )
            )

        # Auxiliary: location search (up to 3 locations, 3 results each)
        for loc in locations[:3]:
            tasks.append(
                self._safe_search(
                    self.memory_repo.search_by_location,
                    user_id, loc,
                    limit=self._WIDE_AUX_PER_ITEM_LIMIT,
                )
            )

        # Auxiliary: person search (up to 3 persons, 3 results each)
        for person in persons[:3]:
            tasks.append(
                self._safe_search(
                    self.memory_repo.search_by_person,
                    user_id, person,
                    limit=self._WIDE_AUX_PER_ITEM_LIMIT,
                )
            )

        # Auxiliary: plan memories
        if contains_plan_keywords(message):
            tasks.append(
                self._safe_search(
                    self.memory_repo.get_plan_memories,
                    user_id,
                    limit=self._WIDE_AUX_PER_ITEM_LIMIT,
                )
            )

        # Auxiliary: full-text keyword search (up to 3 keywords, 2 results each)
        for kw in keywords[:3]:
            tasks.append(
                self._safe_search(
                    self.memory_repo.full_text_search,
                    user_id, kw,
                    limit=self._WIDE_AUX_KEYWORD_LIMIT,
                )
            )

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten & deduplicate
        seen_ids: set = set()
        merged: List[ConversationMemory] = []
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("Wide retrieval sub-task failed: %s", result)
                continue
            for mem in result:
                if mem.id not in seen_ids:
                    merged.append(mem)
                    seen_ids.add(mem.id)

        return merged

    async def _semantic_search_as_memories(
        self, user_id: UUID, message: str, limit: int,
    ) -> List[ConversationMemory]:
        """Run semantic search and return plain memory objects (strip similarity scores)."""
        try:
            results = await self._semantic_search(
                user_id=user_id, query=message, limit=limit,
            )
            return [mem for mem, _similarity in results]
        except Exception as e:
            logger.warning("Semantic search failed in wide retrieval: %s", e)
            return []

    async def _safe_search(self, search_fn, *args, **kwargs) -> List[ConversationMemory]:
        """Wrap a repository search call so exceptions don't break asyncio.gather."""
        try:
            return await search_fn(*args, **kwargs)
        except Exception as e:
            logger.warning("Search sub-task failed (%s): %s", search_fn.__name__, e)
            return []

    # ------------------------------------------------------------------
    # Merge & dedup
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_and_dedup(
        triggered: List[ConversationMemory],
        candidates: List[ConversationMemory],
    ) -> List[ConversationMemory]:
        """Merge triggered (priority) and wide-retrieval candidates, deduplicate by id."""
        seen_ids: set = set()
        merged: List[ConversationMemory] = []

        # Triggered memories come first (highest priority)
        for mem in triggered:
            if mem.id not in seen_ids:
                merged.append(mem)
                seen_ids.add(mem.id)

        # Then wide retrieval candidates
        for mem in candidates:
            if mem.id not in seen_ids:
                merged.append(mem)
                seen_ids.add(mem.id)

        return merged

    # ------------------------------------------------------------------
    # Stage 2: Haiku reranking
    # ------------------------------------------------------------------

    async def _rerank(
        self, query: str, candidates: List[ConversationMemory], limit: int,
    ) -> List[ConversationMemory]:
        """Stage 2: Use Haiku LLM to rerank candidates when they exceed limit.

        Falls back to score-based sorting on any failure.
        """
        try:
            candidate_text = "\n".join(
                f"{i + 1}. [{m.memory_type}] {m.summary}"
                for i, m in enumerate(candidates)
            )
            prompt = (
                f"Given a user message and a list of candidate memories, "
                f"select the {limit} most relevant ones.\n\n"
                f"User message: {query}\n\n"
                f"Candidate memories:\n{candidate_text}\n\n"
                f"Output the indices of the most relevant memories as a JSON array "
                f"(1-based), e.g. [3, 1, 7, 2, 5]. Output ONLY the JSON array, "
                f"no explanation."
            )

            from ...config.settings import settings

            response = await asyncio.wait_for(
                self.anthropic_client.messages.create(
                    model=settings.fast_worker_model,
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=10.0,
            )
            raw_text = response.content[0].text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[-1]
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0].strip()
            indices = json.loads(raw_text)

            if not isinstance(indices, list):
                raise ValueError(f"Expected JSON array, got {type(indices).__name__}")

            reranked = [
                candidates[i - 1]
                for i in indices
                if isinstance(i, int) and 1 <= i <= len(candidates)
            ]
            return reranked[:limit]

        except Exception as e:
            logger.warning(
                "Haiku reranking failed, falling back to score-based sort: %s", e,
            )
            return self._score_and_sort(candidates)[:limit]

    # ------------------------------------------------------------------
    # Fallback score-based sorting
    # ------------------------------------------------------------------

    @staticmethod
    def _score_and_sort(
        memories: List[ConversationMemory],
    ) -> List[ConversationMemory]:
        """Sort memories by importance * recency_decay (fallback when Haiku fails)."""
        now_utc = utc_now()

        def _sort_key(m: ConversationMemory) -> float:
            base_score = (m.importance / 10.0) * getattr(m, "feedback_weight", 1.0)
            if m.created_at:
                created_utc = (
                    m.created_at.replace(tzinfo=timezone.utc)
                    if m.created_at.tzinfo is None
                    else m.created_at
                )
                days_old = (now_utc - created_utc).days
                recency_bonus = max(0, 1 - (days_old / 30)) * 0.1
                base_score += recency_bonus
            return base_score

        return sorted(memories, key=_sort_key, reverse=True)

    async def _semantic_search(
        self, user_id: UUID, query: str, limit: int = 5, exclude_ids: set = None,
    ) -> List[Tuple[ConversationMemory, float]]:
        """Perform semantic similarity search using embeddings."""
        query_embedding = await self.embedding_service.get_embedding(query)
        if not query_embedding:
            return []

        results = await self.memory_repo.semantic_search(
            user_id=user_id,
            query_embedding=query_embedding,
            similarity_threshold=self.config.semantic_similarity_threshold,
            limit=limit * 2,
        )

        filtered_results = []
        for mem, score in results:
            if exclude_ids and mem.id in exclude_ids:
                continue
            filtered_results.append((mem, score))
            if len(filtered_results) >= limit:
                break
        return filtered_results

    async def recall_by_trigger(
        self, user_id: UUID, trigger_type: str, trigger_value: str, limit: int = 5,
    ) -> List[ConversationMemory]:
        """Recall memories by specific trigger."""
        if not 1 <= limit <= 100:
            raise ValueError(f"limit must be between 1 and 100, got {limit}")
        valid_trigger_types = ("location", "person", "tag", "type")
        if trigger_type not in valid_trigger_types:
            raise ValueError(f"trigger_type must be one of {valid_trigger_types}, got {trigger_type}")

        if trigger_type == "location":
            return await self.memory_repo.search_by_location(user_id, trigger_value, limit)
        elif trigger_type == "person":
            return await self.memory_repo.search_by_person(user_id, trigger_value, limit)
        elif trigger_type == "tag":
            return await self.memory_repo.search_by_tags(user_id, [trigger_value], limit)
        elif trigger_type == "type":
            return await self.memory_repo.get_user_memories(user_id, memory_type=trigger_value, limit=limit)
        return []

    async def get_related_to_travel(
        self,
        user_id: UUID,
        destination: str,
        limit: int = 10,
        family_id: UUID = None,
    ) -> Tuple[List[ConversationMemory], str, List[Dict[str, Any]]]:
        """Get memories and contacts related to a travel destination."""
        memories = []
        suggested_contacts = []

        location_memories = await self.memory_repo.search_by_location(user_id, destination, limit=5)
        memories.extend(location_memories)

        tag_memories = await self.memory_repo.search_by_tags(
            user_id, [destination.lower(), "旅行", "出差"], limit=5
        )
        for mem in tag_memories:
            if mem not in memories:
                memories.append(mem)

        memories = list({m.id: m for m in memories}.values())
        memories.sort(key=lambda m: m.importance, reverse=True)
        memories = memories[:limit]

        if family_id:
            try:
                suggested_contacts = await self.contact_service.suggest_contacts_for_trip(
                    family_id=family_id, destination=destination,
                )
            except Exception as e:
                logger.warning(f"Failed to get contact suggestions: {e}")

        summary_parts = []
        if memories:
            summary_parts.append(f"您之前提到过关于{destination}的以下内容：")
            for mem in memories:
                summary_parts.append(f"- {mem.summary}")

            plan_mems = [m for m in memories if m.memory_type == MemoryType.PLAN.value]
            if plan_mems:
                summary_parts.append("\n\U0001f4a1 相关计划：")
                for m in plan_mems:
                    person = m.entities.get("person", "")
                    if person:
                        summary_parts.append(f"  - 之前说要找{person}")
                    else:
                        summary_parts.append(f"  - {m.summary}")

        related_tasks = []
        try:
            from ..views.repositories import FamilyTaskRepository
            task_repo = FamilyTaskRepository(self.db)
            if family_id:
                tasks = await task_repo.search_tasks_by_keyword(family_id, destination, limit=5)
                related_tasks.extend(tasks)
        except Exception as e:
            logger.warning(f"Failed to search related tasks: {e}")

        if related_tasks:
            summary_parts.append(f"\n\U0001f4cb 与{destination}相关的待办任务：")
            for task in related_tasks:
                date_str = task.due_date.strftime("%m/%d") if task.due_date else "待定"
                summary_parts.append(f"  - {task.title}（{date_str}）")

        if suggested_contacts:
            summary_parts.append(f"\n\U0001f465 {destination}的相关联系人：")
            for contact in suggested_contacts:
                name = contact.get("name", "")
                relationship = contact.get("relationship", "")
                context = contact.get("context", "")
                if relationship:
                    summary_parts.append(f"  - {name}（{relationship}）")
                else:
                    summary_parts.append(f"  - {name}")
                if context:
                    summary_parts.append(f"    \u21b3 {context}")
            summary_parts.append("\n\U0001f4a1 建议：可以考虑约这些联系人见面")

        summary = "\n".join(summary_parts) if summary_parts else ""
        return memories, summary, suggested_contacts

    async def get_proactive_reminders(
        self, user_id: UUID, context: Optional[str] = None, limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Get proactive reminders based on active memories."""
        reminders = []
        plan_memories = await self.memory_repo.get_plan_memories(user_id, limit=10)

        for mem in plan_memories:
            location = mem.entities.get("location")
            person = mem.entities.get("person")
            time_hint = mem.entities.get("time_hint")

            reminder = {
                "memory_id": str(mem.id),
                "type": mem.memory_type,
                "summary": mem.summary,
                "created_at": mem.created_at.isoformat(),
            }
            if location:
                reminder["location"] = location
                reminder["hint"] = f"您之前提到要去{location}"
            if person:
                reminder["person"] = person
                reminder["hint"] = f"您之前提到要找{person}"
            if time_hint:
                reminder["time_hint"] = time_hint

            reminders.append(reminder)

        return reminders[:limit]

    async def recall_by_keyword(
        self,
        user_id: UUID,
        family_id: UUID,
        keywords: List[str],
        limit: int = 10,
    ) -> List[ConversationMemory]:
        """Recall memories by keyword list (used by MemoryBridge)."""
        all_memories = []
        seen_ids = set()

        for keyword in keywords[:5]:
            results = await self.memory_repo.full_text_search(user_id, keyword, limit=limit)
            for mem in results:
                if mem.id not in seen_ids and mem.status not in _EXCLUDED_RECALL_STATUSES:
                    all_memories.append(mem)
                    seen_ids.add(mem.id)

        all_memories.sort(key=lambda m: m.importance, reverse=True)
        return all_memories[:limit]

    async def get_recent_memories(
        self,
        user_id: UUID,
        family_id: UUID,
        limit: int = 10,
    ) -> List[ConversationMemory]:
        """Get recent memories (used by MemoryBridge)."""
        return await self.memory_repo.get_recent_memories(user_id, days=7, limit=limit)

    async def recall_graph_connected(
        self,
        memory_id: UUID,
        depth: int = 2,
        min_strength: float = 0.3,
    ) -> List[ConversationMemory]:
        """Retrieve memories connected via association graph using recursive CTE.

        Starting from *memory_id*, traverse ``memory_associations`` edges up to
        *depth* hops, keeping only edges whose ``strength >= min_strength``.
        Returns distinct ``ConversationMemory`` objects reachable from the seed,
        excluding the seed itself and any SUPERSEDED / ARCHIVED / CANCELLED
        memories.
        """
        if depth < 1:
            return []

        cte_sql = text("""
            WITH RECURSIVE graph AS (
                -- Anchor: direct neighbours of the seed
                SELECT
                    CASE
                        WHEN ma.memory_id_a = :seed THEN ma.memory_id_b
                        ELSE ma.memory_id_a
                    END AS reached_id,
                    1 AS depth
                FROM memory_associations ma
                WHERE (ma.memory_id_a = :seed OR ma.memory_id_b = :seed)
                  AND ma.strength >= :min_strength

                UNION

                -- Recursive step
                SELECT
                    CASE
                        WHEN ma.memory_id_a = g.reached_id THEN ma.memory_id_b
                        ELSE ma.memory_id_a
                    END AS reached_id,
                    g.depth + 1 AS depth
                FROM memory_associations ma
                JOIN graph g
                  ON (ma.memory_id_a = g.reached_id OR ma.memory_id_b = g.reached_id)
                WHERE g.depth < :max_depth
                  AND ma.strength >= :min_strength
                  -- Avoid traversing back to the seed
                  AND CASE
                        WHEN ma.memory_id_a = g.reached_id THEN ma.memory_id_b
                        ELSE ma.memory_id_a
                      END != :seed
            )
            SELECT DISTINCT reached_id FROM graph
        """)

        result = await self.db.execute(
            cte_sql,
            {
                "seed": str(memory_id),
                "min_strength": min_strength,
                "max_depth": depth,
            },
        )
        rows = result.fetchall()
        if not rows:
            return []

        connected_ids = [row[0] for row in rows]

        from sqlalchemy import select as sa_select

        stmt = (
            sa_select(ConversationMemory)
            .where(
                ConversationMemory.id.in_(connected_ids),
                ConversationMemory.status.notin_(list(_EXCLUDED_RECALL_STATUSES)),
            )
            .order_by(ConversationMemory.importance.desc())
        )
        mem_result = await self.db.execute(stmt)
        return list(mem_result.scalars().all())

    async def recall_related_to_entity(
        self,
        entity_id: str,
        family_id: UUID,
        max_results: int = 10,
    ) -> List[ConversationMemory]:
        """Find memories containing *entity_id* in their ``entities`` JSONB,
        then expand one hop through associations, rank by
        ``importance * recency_decay``, and filter out SUPERSEDED memories.

        ``entity_id`` is matched against any top-level value in the JSONB
        ``entities`` column (case-insensitive substring via ``ILIKE``).
        """
        from sqlalchemy import select as sa_select, func, cast, String

        # Step 1: find seed memories whose entities contain the target value
        entity_pattern = f"%{entity_id}%"
        seed_stmt = (
            sa_select(ConversationMemory)
            .where(
                ConversationMemory.family_id == family_id,
                ConversationMemory.status.notin_(list(_EXCLUDED_RECALL_STATUSES)),
                func.cast(ConversationMemory.entities, String).ilike(entity_pattern),
            )
            .order_by(ConversationMemory.importance.desc())
            .limit(max_results * 2)
        )
        seed_result = await self.db.execute(seed_stmt)
        seed_memories = list(seed_result.scalars().all())

        if not seed_memories:
            return []

        # Step 2: 1-hop association expansion
        seed_ids = {m.id for m in seed_memories}
        expanded_ids = set()
        for sid in seed_ids:
            assoc_stmt = (
                sa_select(MemoryAssociation)
                .where(
                    (MemoryAssociation.memory_id_a == sid)
                    | (MemoryAssociation.memory_id_b == sid)
                )
                .limit(10)
            )
            assoc_result = await self.db.execute(assoc_stmt)
            for assoc in assoc_result.scalars().all():
                other = assoc.memory_id_b if assoc.memory_id_a == sid else assoc.memory_id_a
                expanded_ids.add(other)

        # Fetch expanded memories (excluding seeds already loaded & excluded statuses)
        extra_ids = expanded_ids - seed_ids
        expanded_memories = []
        if extra_ids:
            exp_stmt = (
                sa_select(ConversationMemory)
                .where(
                    ConversationMemory.id.in_(list(extra_ids)),
                    ConversationMemory.status.notin_(list(_EXCLUDED_RECALL_STATUSES)),
                )
            )
            exp_result = await self.db.execute(exp_stmt)
            expanded_memories = list(exp_result.scalars().all())

        # Step 3: rank by importance * recency_decay
        all_memories = list(seed_memories) + expanded_memories
        now = utc_now()

        def _score(mem: ConversationMemory) -> float:
            importance = mem.importance or 5
            if mem.created_at:
                created_utc = (
                    mem.created_at.replace(tzinfo=timezone.utc)
                    if mem.created_at.tzinfo is None
                    else mem.created_at
                )
                days_old = max((now - created_utc).days, 0)
                recency_decay = 1.0 / (1.0 + days_old / 30.0)
            else:
                recency_decay = 0.5
            return importance * recency_decay

        all_memories.sort(key=_score, reverse=True)

        # Deduplicate (prefer first occurrence = highest score)
        seen = set()
        unique = []
        for m in all_memories:
            if m.id not in seen:
                seen.add(m.id)
                unique.append(m)

        return unique[:max_results]

    _stop_words = frozenset({
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "自己", "这", "那", "什么", "怎么", "吗", "吧", "呢", "啊", "哦", "嗯",
        "可以", "已经", "因为", "所以", "但是", "如果", "还是", "这个", "那个",
        "他们", "我们", "你们", "她", "他", "它", "被", "把", "给", "让", "对",
    })

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract general keywords for search using jieba segmentation."""
        text = text[:2000]
        try:
            import jieba
            words = jieba.cut(text, cut_all=False)
            return [w for w in words if len(w) >= 2 and w not in self._stop_words][:5]
        except ImportError:
            words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
            return [w for w in words if w not in self._stop_words][:5]

    def _format_memories_for_llm(
        self,
        memories: List[ConversationMemory],
        recall_reasons: Dict[UUID, List[str]],
        triggered_memories: Optional[List[ConversationMemory]] = None,
    ) -> str:
        """Format memories as context string for LLM."""
        if not memories:
            return ""

        triggered_ids = {m.id for m in (triggered_memories or [])}
        parts = []

        triggered_mems = [m for m in memories if m.id in triggered_ids]
        regular_mems = [m for m in memories if m.id not in triggered_ids]

        if triggered_mems:
            parts.append("【\U0001f514 重要提醒 - 触发的记忆】")
            parts.append("以下是用户之前设置的条件提醒，现在被触发了，请务必在回复中主动提及：\n")
            for mem in triggered_mems:
                trigger_msg = mem.trigger_conditions.get("message", "") if mem.trigger_conditions else ""
                parts.append(f"\u26a1 {mem.summary}")
                if trigger_msg:
                    parts.append(f"   \U0001f4ac 提醒内容: {trigger_msg}")
                entities = mem.entities or {}
                if entities.get("person"):
                    parts.append(f"   \U0001f464 人物: {entities['person']}")
                if entities.get("location"):
                    parts.append(f"   \U0001f4cd 地点: {entities['location']}")
                parts.append("")
            parts.append("\U0001f534 请在回复中主动提醒用户这些事项！例如：\"对了，您之前说过...\"")
            parts.append("")

        if regular_mems:
            parts.append("【相关历史记忆】")
            parts.append("用户之前提到过以下内容，可以在回复时适当关联：\n")

            def format_entity(value):
                if isinstance(value, list):
                    return "、".join(str(v) for v in value if v)
                return str(value) if value else ""

            type_icons = {
                "emotion": "\U0001f4ad", "plan": "\U0001f4cb", "schedule": "\U0001f4c5",
                "relationship": "\U0001f465", "preference": "\u2764\ufe0f",
                "life_event": "\U0001f389", "location": "\U0001f4cd", "health": "\U0001f3e5",
                "work": "\U0001f4bc", "favor": "\U0001f91d", "general": "\U0001f4dd",
            }

            for mem in regular_mems:
                reasons = recall_reasons.get(mem.id, [])
                reason_str = f"({', '.join(reasons)})" if reasons else ""
                icon = type_icons.get(mem.memory_type, "\U0001f4dd")
                parts.append(f"{icon} {mem.summary} {reason_str}")

                entities = mem.entities or {}
                if entities.get("person"):
                    parts.append(f"   人物: {format_entity(entities['person'])}")
                if entities.get("location"):
                    parts.append(f"   地点: {format_entity(entities['location'])}")
                if entities.get("time_hint"):
                    parts.append(f"   时间: {format_entity(entities['time_hint'])}")

                if mem.memory_type == "favor":
                    favor_direction = entities.get("favor_direction", "")
                    favor_type = entities.get("favor_type", "")
                    if favor_direction == "received":
                        parts.append(f"   \u26a0\ufe0f 欠人情：{favor_type}，建议找机会回礼")
                    elif favor_direction == "given":
                        parts.append(f"   \u2705 送出人情：{favor_type}")

                if mem.memory_type == "preference":
                    parts.append(f"   \U0001f4a1 可作为回礼参考")

            parts.append("\n请在回复中自然地关联这些信息，帮助用户想起之前的计划。")

        return "\n".join(parts)


class ContextAwareRecallService:
    """Higher-level service combining memory recall with structured data."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.recall_service = MemoryRecallService(db)

    async def get_comprehensive_context(
        self, user_id: UUID, family_id: UUID, message: str,
    ) -> Dict[str, Any]:
        """Get comprehensive context including memories, notes, knowledge graph, and contacts."""
        result = {
            "memories": [],
            "memory_context": "",
            "travel_related": None,
            "suggested_contacts": [],
            "secretary_notes": [],
            "secretary_notes_context": "",
            "knowledge_graph": None,
            "relationship_context": "",
            "insights": [],
        }

        memories, context_str = await self.recall_service.recall_for_message(user_id, message)
        result["memories"] = [m.to_dict() for m in memories]
        result["memory_context"] = context_str

        try:
            notes = await self.recall_service.secretary_note_service.get_relevant_notes(
                user_id=user_id, context=message, limit=3,
            )
            if notes:
                result["secretary_notes"] = [n.to_dict() for n in notes]
                result["secretary_notes_context"] = await self.recall_service.secretary_note_service.format_notes_for_llm(notes)
        except Exception as e:
            logger.warning(f"Failed to get secretary notes: {e}")

        try:
            person_names = await extract_persons_async(message)
            if person_names:
                person_ids = []
                for name in person_names[:5]:
                    profile = await self._find_person_profile_by_name(user_id, name)
                    if profile:
                        person_ids.append(profile.id)

                if person_ids:
                    kg_service = self.recall_service.knowledge_graph_service
                    graph = await kg_service.get_relevant_context_graph(
                        user_id=user_id, person_ids=person_ids, depth=1,
                    )
                    if graph and graph.get("nodes"):
                        result["knowledge_graph"] = graph
                        context_person = person_names[0] if person_names else None
                        result["relationship_context"] = await kg_service.format_graph_for_llm(
                            graph, context_person=context_person
                        )
        except Exception as e:
            logger.warning(f"Failed to get knowledge graph context: {e}")

        locations = await extract_locations_async(message)
        if locations:
            travel_memories, travel_summary, suggested_contacts = await self.recall_service.get_related_to_travel(
                user_id, locations[0], family_id=family_id
            )
            if travel_memories or suggested_contacts:
                result["travel_related"] = {
                    "location": locations[0],
                    "memories": [m.to_dict() for m in travel_memories],
                    "summary": travel_summary,
                }
                result["suggested_contacts"] = suggested_contacts

        return result

    async def _find_person_profile_by_name(
        self, user_id: UUID, person_name: str,
    ) -> Optional[PersonProfile]:
        """Find a person profile by name or alias."""
        return await find_person_profile_by_name(self.db, user_id, person_name)
