"""
Secretary Note Service - High-level preference and routine tracking

This service provides:
- Pattern extraction from memories
- Note creation and management
- Context-aware note recall
- User preference tracking
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.llm import openai_adapter
from ...core.interfaces.llm_provider import LLMMessage
from ...config.logging import get_logger
from .models import (
    ConversationMemory,
    MemoryType,
    MemoryStatus,
)
from .secretary_note_model import (
    SecretaryNote,
    NoteCategory,
    NoteLifeType,
    NoteStatus,
)
from .fact_verification import (
    FactVerificationGate,
    NoteCandidate,
    VerificationAction,
)
from .utils import extract_json_from_response
from ...core.audit.service import AuditService
from ...core.observability.metrics import l1_notes_created_total, l1_notes_confirmed_total
from ...core.utils.timezone import utc_now

logger = get_logger(__name__)

# Signals indicating transient/short-lived facts
TRANSIENT_SIGNALS = ["最近", "这周", "这几天", "目前", "暂时", "临时", "现在", "当前"]

# Default validity window for transient facts
TRANSIENT_DEFAULT_DAYS = 30


class SecretaryNoteService:
    """Service for managing secretary notes (preferences, routines, observations)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = openai_adapter
        self._audit = AuditService(db)

    async def generate_notes_from_memories(
        self,
        user_id: UUID,
        family_id: UUID,
        days_back: int = 30,
    ) -> List[SecretaryNote]:
        """
        Generate secretary notes from recent memories.

        Analyzes memories to extract:
        - User preferences (seating, food, etc.)
        - Routines and patterns
        - Important information to remember

        Args:
            user_id: The user ID
            family_id: The family ID
            days_back: Number of days to look back

        Returns:
            List of newly created notes
        """
        created_notes = []

        try:
            # Get recent preference-related memories
            since = utc_now() - timedelta(days=days_back)
            memories = await self._get_relevant_memories(user_id, since)

            if not memories:
                logger.info(f"No relevant memories found for note generation")
                return []

            # Use LLM to extract notes from memories
            extracted = await self._extract_notes_via_llm(memories)

            # Fetch existing active notes for verification gate
            existing_notes = await self._get_existing_notes(user_id, family_id)
            gate = FactVerificationGate()

            # Build source message texts for evidence tracing
            source_messages = [m.content for m in memories if m.content]

            # Verify and create notes
            for note_data in extracted:
                candidate = NoteCandidate(
                    content=note_data.get("content", ""),
                    category=note_data.get("category", ""),
                    confidence=note_data.get("confidence", 0.8),
                    title=note_data.get("title", ""),
                )
                verification = gate.verify(
                    candidate=candidate,
                    existing_notes=existing_notes,
                    source_messages=source_messages,
                )

                if verification.action == VerificationAction.REJECT:
                    logger.info(
                        "Gate rejected note '%s': %s",
                        note_data.get("title", ""),
                        verification.reason,
                    )
                    continue

                if verification.action == VerificationAction.PENDING:
                    # Reduce confidence and mark as unconfirmed
                    note_data["confidence"] = min(
                        note_data.get("confidence", 0.8) * 0.7, 0.6
                    )
                    note_data["is_user_confirmed"] = False

                note = await self._create_note_if_new(
                    user_id, family_id, note_data, memories,
                )
                if note:
                    # If contradictions were detected, flag both notes
                    if verification.conflicts:
                        for existing in existing_notes:
                            if existing.category == note_data.get("category", "") and existing.id != note.id:
                                # Check if this existing note was mentioned in conflicts
                                title_str = existing.title or ""
                                if any(title_str in c for c in verification.conflicts):
                                    note.add_contradiction(existing.id)
                                    existing.add_contradiction(note.id)
                    created_notes.append(note)

            logger.info(f"Generated {len(created_notes)} secretary notes for user {user_id}")

        except Exception as e:
            logger.error(f"Error generating notes: {e}")

        return created_notes

    async def _get_relevant_memories(
        self,
        user_id: UUID,
        since: datetime,
    ) -> List[ConversationMemory]:
        """Get memories relevant for note extraction."""
        query = select(ConversationMemory).where(
            and_(
                ConversationMemory.user_id == user_id,
                ConversationMemory.status == MemoryStatus.ACTIVE.value,
                ConversationMemory.created_at >= since,
                ConversationMemory.memory_type.in_([
                    MemoryType.PREFERENCE.value,
                    MemoryType.SCHEDULE.value,
                    MemoryType.RELATIONSHIP.value,
                    MemoryType.HEALTH.value,
                ]),
            )
        ).order_by(ConversationMemory.created_at.desc()).limit(50)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _extract_notes_via_llm(
        self,
        memories: List[ConversationMemory],
    ) -> List[Dict[str, Any]]:
        """Use LLM to extract notes from memories."""
        # Prepare memory summaries
        memory_texts = []
        for m in memories:
            memory_texts.append(f"- [{m.memory_type}] {m.summary}")

        prompt = f"""分析以下用户记忆，提取有价值的秘书笔记。

记忆内容：
{chr(10).join(memory_texts)}

请识别并提取以下类型的笔记：
1. preference（偏好）：用户的喜好，如座位偏好、饮食习惯等
2. routine（例行）：用户的日常规律，如作息时间、固定安排等
3. important（重要）：需要长期记住的重要信息，如健康禁忌、重要关系等

返回JSON数组格式：
[
    {{
        "category": "preference/routine/important",
        "title": "简短标题",
        "content": "详细内容",
        "trigger_keywords": ["相关关键词"],
        "confidence": 0.8
    }}
]

规则：
- 只提取明确、有价值的信息
- 不要推测不确定的信息
- confidence表示确信程度（0.6-1.0）
- 每个类型最多提取2条

只返回JSON数组，不要其他文字。如果没有有价值的信息，返回空数组[]。"""

        try:
            response = await self.llm.chat([
                LLMMessage(role="user", content=prompt)
            ])

            # Parse JSON response using robust extraction (expecting array)
            result = extract_json_from_response(response.content, expect_array=True)
            if result is None:
                logger.warning("Failed to parse JSON array from LLM response for notes")
                return []
            return result

        except Exception as e:
            logger.warning(f"Failed to extract notes via LLM: {e}")
            return []

    @staticmethod
    def classify_life_type(
        fact_content: str,
    ) -> tuple:
        """Classify whether a fact is permanent or transient.

        Returns:
            (NoteLifeType, Optional[datetime]) - life type and optional expiry.
        """
        content_lower = fact_content.lower()
        for signal in TRANSIENT_SIGNALS:
            if signal in content_lower:
                valid_until = utc_now() + timedelta(days=TRANSIENT_DEFAULT_DAYS)
                return (NoteLifeType.TRANSIENT, valid_until)
        return (NoteLifeType.PERMANENT, None)

    async def _create_note_if_new(
        self,
        user_id: UUID,
        family_id: UUID,
        note_data: Dict[str, Any],
        source_memories: List[ConversationMemory],
    ) -> Optional[SecretaryNote]:
        """Create a note if no similar note exists."""
        # Check for existing similar note
        existing = await self._find_similar_note(
            user_id=user_id,
            category=note_data.get("category", "preference"),
            title=note_data.get("title", ""),
        )

        if existing:
            # Update existing note with new observation
            existing.record_observation()
            await self.db.commit()
            return None

        # Classify fact lifecycle
        content = note_data.get("content", "")
        life_type, valid_until = self.classify_life_type(content)

        # Create new note
        note = SecretaryNote(
            user_id=user_id,
            family_id=family_id,
            category=note_data.get("category", NoteCategory.PREFERENCE.value),
            title=note_data.get("title", ""),
            content=content,
            confidence=note_data.get("confidence", 0.8),
            is_user_confirmed=note_data.get("is_user_confirmed", False),
            trigger_keywords=note_data.get("trigger_keywords", []),
            source_memory_ids=[m.id for m in source_memories[:5]],
            life_type=life_type.value,
            valid_until=valid_until,
        )
        self.db.add(note)
        await self._audit.log_event(
            user_id=user_id,
            family_id=family_id,
            event_type="l1_note_created",
            event_data={
                "note_id": str(note.id) if note.id else None,
                "category": note.category,
                "title": note.title,
                "confidence": note.confidence,
            },
        )
        await self.db.commit()
        await self.db.refresh(note)
        l1_notes_created_total.inc()

        return note

    async def _find_similar_note(
        self,
        user_id: UUID,
        category: str,
        title: str,
    ) -> Optional[SecretaryNote]:
        """Find a similar existing note."""
        query = select(SecretaryNote).where(
            and_(
                SecretaryNote.user_id == user_id,
                SecretaryNote.category == category,
                SecretaryNote.status == NoteStatus.ACTIVE.value,
                func.similarity(SecretaryNote.title, title) > 0.6,
            )
        ).limit(1)

        try:
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception:
            # Fallback to exact match if pg_trgm not available
            query = select(SecretaryNote).where(
                and_(
                    SecretaryNote.user_id == user_id,
                    SecretaryNote.category == category,
                    SecretaryNote.title == title,
                    SecretaryNote.status == NoteStatus.ACTIVE.value,
                )
            ).limit(1)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()

    async def _get_existing_notes(
        self,
        user_id: UUID,
        family_id: UUID,
    ) -> List[SecretaryNote]:
        """Get all active notes for a user/family, used by verification gate."""
        result = await self.db.execute(
            select(SecretaryNote).where(
                SecretaryNote.user_id == user_id,
                SecretaryNote.family_id == family_id,
                SecretaryNote.status == NoteStatus.ACTIVE.value,
            )
        )
        return list(result.scalars().all())

    async def get_relevant_notes(
        self,
        user_id: UUID,
        context: str,
        limit: int = 5,
    ) -> List[SecretaryNote]:
        """
        Get notes relevant to the current context.

        Uses keyword matching and context analysis.

        Args:
            user_id: The user ID
            context: Current conversation context
            limit: Maximum notes to return

        Returns:
            List of relevant notes
        """
        # Get all active notes
        query = select(SecretaryNote).where(
            and_(
                SecretaryNote.user_id == user_id,
                SecretaryNote.status == NoteStatus.ACTIVE.value,
            )
        ).order_by(
            SecretaryNote.priority.desc(),
            SecretaryNote.confidence.desc(),
        )

        result = await self.db.execute(query)
        all_notes = list(result.scalars().all())

        # Filter by keyword matching
        relevant = []
        context_lower = context.lower()

        for note in all_notes:
            if note.matches_keywords(context):
                relevant.append((note, 1.0))  # High relevance for keyword match
            elif any(kw.lower() in context_lower for kw in (note.trigger_keywords or [])):
                relevant.append((note, 0.8))  # Medium relevance
            elif note.category == NoteCategory.IMPORTANT.value:
                # Always consider important notes
                relevant.append((note, 0.3))

        # Sort by relevance and limit
        relevant.sort(key=lambda x: (-x[1], -x[0].priority))
        notes = [n for n, _ in relevant[:limit]]

        # Mark notes as surfaced
        for note in notes:
            note.mark_surfaced()
        if notes:
            await self.db.commit()

        return notes

    async def get_notes_by_category(
        self,
        user_id: UUID,
        category: str,
        limit: int = 20,
    ) -> List[SecretaryNote]:
        """Get notes by category."""
        query = select(SecretaryNote).where(
            and_(
                SecretaryNote.user_id == user_id,
                SecretaryNote.category == category,
                SecretaryNote.status == NoteStatus.ACTIVE.value,
            )
        ).order_by(
            SecretaryNote.priority.desc(),
            SecretaryNote.created_at.desc(),
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def confirm_note(self, note_id: UUID) -> Optional[SecretaryNote]:
        """User confirms a note is accurate."""
        query = select(SecretaryNote).where(SecretaryNote.id == note_id)
        result = await self.db.execute(query)
        note = result.scalar_one_or_none()

        if note:
            note.confirm()
            await self.db.commit()
            await self.db.refresh(note)
            l1_notes_confirmed_total.inc()

        return note

    async def archive_note(self, note_id: UUID) -> Optional[SecretaryNote]:
        """Archive a note."""
        query = select(SecretaryNote).where(SecretaryNote.id == note_id)
        result = await self.db.execute(query)
        note = result.scalar_one_or_none()

        if note:
            note.archive()
            await self.db.commit()
            await self.db.refresh(note)

        return note

    async def create_note(
        self,
        user_id: UUID,
        family_id: UUID,
        category: str,
        title: str,
        content: str,
        trigger_keywords: Optional[List[str]] = None,
        priority: int = 5,
    ) -> SecretaryNote:
        """
        Create a new secretary note.

        Args:
            user_id: The user ID
            family_id: The family ID
            category: Note category (must be one of NoteCategory values)
            title: Note title (1-200 characters)
            content: Note content
            trigger_keywords: Optional list of trigger keywords
            priority: Priority level (1-10)

        Returns:
            The created SecretaryNote

        Raises:
            ValueError: If any input validation fails
        """
        # Validate category
        valid_categories = [c.value for c in NoteCategory]
        if category not in valid_categories:
            raise ValueError(f"Invalid category: {category}. Must be one of {valid_categories}")

        # Validate title
        if not title or len(title) > 200:
            raise ValueError("Title must be between 1 and 200 characters")

        # Validate content
        if not content:
            raise ValueError("Content is required")

        # Validate priority
        if not 1 <= priority <= 10:
            raise ValueError(f"Priority must be between 1 and 10, got {priority}")

        note = SecretaryNote(
            user_id=user_id,
            family_id=family_id,
            category=category,
            title=title,
            content=content,
            trigger_keywords=trigger_keywords or [],
            priority=priority,
            confidence=1.0,  # User-created notes have full confidence
            is_user_confirmed=True,
        )
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)

        return note

    async def update_note(
        self,
        note_id: UUID,
        **kwargs,
    ) -> Optional[SecretaryNote]:
        """Update a note."""
        query = select(SecretaryNote).where(SecretaryNote.id == note_id)
        result = await self.db.execute(query)
        note = result.scalar_one_or_none()

        if note:
            changed_fields = {
                k: v for k, v in kwargs.items() if hasattr(note, k)
            }
            for key, value in changed_fields.items():
                setattr(note, key, value)
            note.updated_at = utc_now()
            await self._audit.log_event(
                user_id=note.user_id,
                family_id=note.family_id,
                event_type="l1_note_updated",
                event_data={
                    "note_id": str(note_id),
                    "changed_fields": list(changed_fields.keys()),
                },
            )
            await self.db.commit()
            await self.db.refresh(note)

        return note

    async def format_notes_for_llm(
        self,
        notes: List[SecretaryNote],
    ) -> str:
        """Format notes for inclusion in LLM context."""
        if not notes:
            return ""

        parts = ["【秘书笔记 - 用户偏好和重要信息】"]
        parts.append("在回复时请参考以下信息：\n")

        category_icons = {
            "preference": "❤️",
            "routine": "🕐",
            "important": "⚠️",
            "todo": "📋",
            "observation": "👁️",
        }

        for note in notes:
            icon = category_icons.get(note.category, "📝")
            confidence_str = "（已确认）" if note.is_user_confirmed else ""
            parts.append(f"{icon} {note.title}{confidence_str}")
            parts.append(f"   {note.content}")
            parts.append("")

        return "\n".join(parts)


class TransientFactManager:
    """Manages lifecycle of transient (short-lived) secretary notes.

    Responsibilities:
    - Finds and archives expired TRANSIENT notes
    - Restores PERMANENT notes that were superseded by now-expired transients
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_expiring_facts(self, user_id: UUID) -> Dict[str, int]:
        """Find expired TRANSIENT notes, archive them, and restore superseded PERMANENTs.

        Returns:
            Dict with counts: {"archived": N, "restored": N}
        """
        now = utc_now()
        query = select(SecretaryNote).where(
            and_(
                SecretaryNote.user_id == user_id,
                SecretaryNote.status == NoteStatus.ACTIVE.value,
                SecretaryNote.life_type == NoteLifeType.TRANSIENT.value,
                SecretaryNote.valid_until.isnot(None),
                SecretaryNote.valid_until <= now,
            )
        )
        result = await self.db.execute(query)
        expired_notes = list(result.scalars().all())

        archived_count = 0
        restored_count = 0

        for note in expired_notes:
            note.status = NoteStatus.ARCHIVED.value
            note.updated_at = now
            archived_count += 1

            restored = await self._restore_superseded_permanent(note)
            if restored:
                restored_count += 1

        if expired_notes:
            await self.db.commit()

        logger.info(
            "Processed expiring facts for user %s: archived=%d, restored=%d",
            user_id, archived_count, restored_count,
        )
        return {"archived": archived_count, "restored": restored_count}

    async def _restore_superseded_permanent(
        self, transient_note: SecretaryNote,
    ) -> Optional[SecretaryNote]:
        """If a PERMANENT note was superseded by this transient, restore it."""
        query = select(SecretaryNote).where(
            and_(
                SecretaryNote.user_id == transient_note.user_id,
                SecretaryNote.status == NoteStatus.SUPERSEDED.value,
                SecretaryNote.life_type == NoteLifeType.PERMANENT.value,
                SecretaryNote.category == transient_note.category,
                SecretaryNote.title == transient_note.title,
            )
        ).order_by(SecretaryNote.updated_at.desc()).limit(1)

        result = await self.db.execute(query)
        permanent_note = result.scalar_one_or_none()

        if permanent_note:
            permanent_note.status = NoteStatus.ACTIVE.value
            permanent_note.updated_at = utc_now()
            logger.info(
                "Restored permanent note '%s' after transient expired",
                permanent_note.title,
            )
            return permanent_note

        return None
