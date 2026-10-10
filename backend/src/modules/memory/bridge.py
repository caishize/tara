"""Memory Bridge - Connects the session lifecycle with the memory system.

Responsibilities:
1. On session archive: extract memories from the conversation
2. On new session / rehydration: load relevant cross-session memories
3. Format memories for system prompt injection

Memory Flow:
    Active Session -> archive_session() -> MemoryBridge.on_session_archive()
        -> MemoryExtractionService.extract() -> conversation_memories table
        -> New Session -> MemoryBridge.load_memories_for_context()
        -> MemoryRecallService.recall_relevant() -> formatted memories for system prompt
"""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..conversation.models import AssistantChatSession, ConversationMessage

logger = logging.getLogger(__name__)

# Check service availability at import time, not per-call
_MEMORY_EXTRACTION_AVAILABLE = True
try:
    from .extraction_service import MemoryExtractionService
except ImportError:
    _MEMORY_EXTRACTION_AVAILABLE = False
    logger.info("MemoryExtractionService not available -- memory extraction disabled")

_MEMORY_RECALL_AVAILABLE = True
try:
    from .recall_service import MemoryRecallService
except ImportError:
    _MEMORY_RECALL_AVAILABLE = False
    logger.info("MemoryRecallService not available -- memory recall disabled")


class MemoryBridge:
    """Bridge between session lifecycle and memory system."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def on_session_archive(
        self,
        session_id: UUID,
        user_id: UUID,
        family_id: UUID,
    ) -> int:
        """Extract memories from an archived session.

        Called by SessionService.archive_session(). Returns the number
        of memories extracted.
        """
        try:
            messages = await self._load_session_messages(session_id)
            if not messages:
                logger.info(
                    "No messages to extract memories from for session %s", session_id
                )
                return 0

            if not _MEMORY_EXTRACTION_AVAILABLE:
                logger.info(
                    "MemoryExtractionService not available, skipping extraction"
                )
                return 0

            extraction_service = MemoryExtractionService(self._db)

            extracted_count = 0
            for msg in messages:
                if msg.role != "user":
                    continue
                try:
                    context = [
                        {"role": m.role, "content": m.content}
                        for m in messages
                        if m.created_at <= msg.created_at
                    ][-6:]

                    result = await extraction_service.extract_and_store(
                        user_id=user_id,
                        family_id=family_id,
                        message=msg.content,
                        context=context,
                        source_session_id=session_id,
                        source_message_id=msg.id,
                    )
                    extracted_count += len(result[0]) if result and result[0] else 0
                except Exception as e:
                    logger.warning(
                        "Failed to extract memories from message %s: %s", msg.id, e
                    )

            logger.info(
                "Extracted %d memories from session %s", extracted_count, session_id
            )
            return extracted_count

        except Exception as e:
            logger.error(
                "Memory extraction failed for session %s: %s", session_id, e
            )
            return 0

    async def load_memories_for_context(
        self,
        user_id: UUID,
        family_id: UUID,
        topic: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """Load relevant cross-session memories for agent context.

        Returns formatted memory text for system prompt injection.
        """
        try:
            if not _MEMORY_RECALL_AVAILABLE:
                return ""

            recall_service = MemoryRecallService(self._db)

            if topic:
                memories = await recall_service.recall_by_keyword(
                    user_id=user_id,
                    family_id=family_id,
                    keywords=[topic],
                    limit=limit,
                )
            else:
                memories = await recall_service.get_recent_memories(
                    user_id=user_id,
                    family_id=family_id,
                    limit=limit,
                )

            if not memories:
                return ""

            return self._format_memories_for_prompt(memories)

        except Exception as e:
            logger.warning("Failed to load memories for context: %s", e)
            return ""

    async def load_person_profiles(
        self,
        family_id: UUID,
        limit: int = 10,
    ) -> str:
        """Load person profiles for system prompt injection."""
        try:
            from ..member.models import PersonProfile

            result = await self._db.execute(
                select(PersonProfile)
                .where(PersonProfile.family_id == family_id)
                .order_by(desc(PersonProfile.updated_at))
                .limit(limit)
            )
            profiles = result.scalars().all()

            if not profiles:
                return ""

            lines = []
            for profile in profiles:
                name = getattr(profile, "name", "\u672a\u77e5")
                relationship = getattr(profile, "relationship", "")
                traits = getattr(profile, "traits", {})
                preferences = getattr(profile, "preferences", {})

                parts = [f"- **{name}** ({relationship})"]
                if traits:
                    trait_str = ", ".join(
                        f"{k}: {v}" for k, v in traits.items() if v
                    )
                    if trait_str:
                        parts.append(f"  \u7279\u5f81: {trait_str}")
                if preferences:
                    pref_str = ", ".join(
                        f"{k}: {v}" for k, v in preferences.items() if v
                    )
                    if pref_str:
                        parts.append(f"  \u504f\u597d: {pref_str}")

                lines.append("\n".join(parts))

            return "\n".join(lines)

        except ImportError:
            logger.debug("PersonProfile model not available")
            return ""
        except Exception as e:
            logger.warning("Failed to load person profiles: %s", e)
            return ""

    # -- Private helpers ---------------------------------------------------

    async def _load_session_messages(
        self, session_id: UUID
    ) -> List[ConversationMessage]:
        """Load all messages from a session."""
        result = await self._db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at)
        )
        return list(result.scalars().all())

    @staticmethod
    def _format_memories_for_prompt(memories) -> str:
        """Format recalled memories for system prompt injection."""
        lines = []
        for mem in memories:
            category = getattr(
                mem, "memory_type", getattr(mem, "category", "general")
            )
            content = getattr(mem, "content", "")
            if hasattr(category, "value"):
                category = category.value
            if content:
                lines.append(f"- [{category}] {content}")
        return "\n".join(lines)
