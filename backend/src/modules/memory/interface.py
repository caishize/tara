"""Memory module public interface.

Defines abstract contracts for memory extraction, recall,
consolidation, and insight generation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MemoryEntry:
    """A single memory entry."""
    id: str
    family_id: str
    memory_type: str
    content: str
    entities: Optional[Dict[str, Any]] = None
    importance: float = 0.5
    status: str = "active"
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class InsightEntry:
    """An AI-generated insight."""
    id: str
    insight_type: str
    content: str
    importance_score: float
    push_strategy: Optional[str] = None
    created_at: Optional[datetime] = None


class IExtractionService(ABC):
    """Extract structured memories from conversations."""

    @abstractmethod
    async def extract_from_conversation(
        self,
        user_id: str,
        family_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[MemoryEntry]:
        """Extract memories from a conversation turn."""
        ...


class IRecallService(ABC):
    """Semantic retrieval and keyword-based memory recall."""

    @abstractmethod
    async def recall(
        self,
        family_id: str,
        query: str,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Recall relevant memories for a query."""
        ...

    @abstractmethod
    async def search(
        self,
        family_id: str,
        filters: Dict[str, Any],
        limit: int = 20,
        offset: int = 0,
    ) -> List[MemoryEntry]:
        """Search memories with structured filters."""
        ...


class IConsolidationService(ABC):
    """Merge, deduplicate, and compress memories."""

    @abstractmethod
    async def consolidate(self, family_id: str) -> int:
        """Run consolidation for a family. Returns count of consolidated."""
        ...


class IInsightService(ABC):
    """Generate proactive insights from memories."""

    @abstractmethod
    async def generate_insights(
        self,
        family_id: str,
        user_id: str,
    ) -> List[InsightEntry]:
        """Generate insights for a user."""
        ...


class IMemoryBridge(ABC):
    """Bridge interface for AI Engine to read/write memories."""

    @abstractmethod
    async def save_memory(
        self,
        family_id: str,
        user_id: str,
        content: str,
        memory_type: str,
        entities: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Save a new memory (called by AI Engine tools)."""
        ...

    @abstractmethod
    async def search_memory(
        self,
        family_id: str,
        query: str,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Search memories (called by AI Engine tools)."""
        ...
