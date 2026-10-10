"""Lightweight Graph-RAG wrapper over the memory recall service.

Exposes graph-traversal retrieval methods (BFS via recursive CTE and
entity-based 1-hop expansion) behind a dedicated class, making it easy
to compose graph-augmented retrieval into higher-level pipelines.

All heavy lifting is delegated to :class:`MemoryRecallService`; this
class adds no new logic — it is a naming/API refactoring layer.
"""

from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .models import ConversationMemory
from .recall_service import MemoryRecallService


class LightweightGraphRAG:
    """Graph-augmented retrieval for the memory knowledge graph.

    Wraps the graph-traversal primitives in :class:`MemoryRecallService`:

    * **traverse** — recursive CTE BFS over ``memory_associations``
    * **entity_search** — entity-based seed search + 1-hop expansion

    Usage::

        graph_rag = LightweightGraphRAG(db_session)
        connected = await graph_rag.traverse(seed_memory_id, depth=2)
        related   = await graph_rag.entity_search("Alice", family_id)
    """

    def __init__(self, db: AsyncSession) -> None:
        self._recall_service = MemoryRecallService(db)

    async def traverse(
        self,
        memory_id: UUID,
        depth: int = 2,
        min_strength: float = 0.3,
    ) -> List[ConversationMemory]:
        """BFS traversal of the memory association graph.

        Starting from *memory_id*, walk up to *depth* hops through
        ``memory_associations`` edges whose strength meets the threshold.

        Delegates to :meth:`MemoryRecallService.recall_graph_connected`.
        """
        return await self._recall_service.recall_graph_connected(
            memory_id=memory_id,
            depth=depth,
            min_strength=min_strength,
        )

    async def entity_search(
        self,
        entity_id: str,
        family_id: UUID,
        max_results: int = 10,
    ) -> List[ConversationMemory]:
        """Entity-based search with 1-hop graph expansion.

        Finds memories whose ``entities`` JSONB contains *entity_id*,
        expands one hop through associations, and ranks results by
        ``importance * recency_decay``.

        Delegates to :meth:`MemoryRecallService.recall_related_to_entity`.
        """
        return await self._recall_service.recall_related_to_entity(
            entity_id=entity_id,
            family_id=family_id,
            max_results=max_results,
        )
