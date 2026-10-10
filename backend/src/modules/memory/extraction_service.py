"""Memory Extraction Service - Extract memories from user conversations using LLM.

Analyzes user messages and extracts:
- Emotional states, plans, intentions, relationships
- Preferences, life events, location information
- Health info, work-related info, favor events
- Trigger conditions for conditional recall
"""

import asyncio
import json
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.llm import openai_adapter
from ...config.logging import get_logger
from ...core.interfaces.llm_provider import LLMMessage
from ...core.utils.timezone import utc_now
from .config import memory_config
from .models import ConversationMemory, MemoryStatus, MemoryType, classify_sensitivity
from .repository import MemoryRepository

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MemoryExtractionError(Exception):
    """Base exception for memory extraction errors."""


class LLMExtractionError(MemoryExtractionError):
    """Error during LLM call for extraction."""


class ParsingError(MemoryExtractionError):
    """Error parsing LLM response."""


class StorageError(MemoryExtractionError):
    """Error storing extracted memories."""


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

MEMORY_EXTRACTION_PROMPT = """你是一个智能信息提取助手。分析用户的对话内容，提取值得记住的关键信息。

【提取规则】
1. 只提取有价值的信息，忽略无意义的闲聊
2. 提取用户表达的情绪、计划、偏好、人物关系等
3. 为每条记忆生成简洁的摘要
4. 提取关键实体（人物、地点、时间等）
5. 评估重要性（1-10）和你的提取置信度（0-1）
6. 🔴 重要：识别"条件触发"的表达，如"下次去北京的时候找李思远"

【记忆类型】
- emotion: 情绪状态（必须包含 sentiment 和 emotion_intensity）
- plan: 未来计划
- schedule: 有时间约束的安排
- relationship: 人物关系
- preference: 喜好偏好
- life_event: 重要事件
- location: 地点信息
- health: 健康信息
- work: 工作相关
- favor: 🔴 人情事件
- general: 其他值得记住的信息

【人情事件识别】🔴
当用户提到别人帮了用户或用户帮了别人时，提取为 favor 类型。
记录: person, favor_direction ("received"/"given"), favor_type, favor_weight (1-3)

【条件触发识别】🔴
当用户表达"下次...的时候"、"以后去...时"等条件性计划时，提取trigger_conditions：
触发类型: location_mention, person_mention, keyword_mention

【用户消息】
{user_message}

【对话上下文】
{context}

【输出格式】
返回JSON数组：
```json
[
  {{
    "memory_type": "类型",
    "summary": "简洁的记忆摘要（一句话）",
    "entities": {{
      "person": "人物名",
      "persons": ["人物1", "人物2"],
      "location": "地点",
      "time_hint": "时间线索",
      "relationship": "关系",
      "emotion": "情绪",
      "sentiment": "positive|negative|mixed|neutral",
      "emotion_intensity": 3,
      "event": "事件"
    }},
    "tags": ["标签1", "标签2"],
    "importance": 5,
    "confidence": 0.8,
    "expires_days": null,
    "trigger_conditions": null
  }}
]
```

如果没有值得提取的信息，返回空数组 []

注意：
- 只返回JSON，不要其他内容
- entities中只包含实际提取到的字段
- 🔴 emotion/work 类型必须包含 sentiment（positive/negative/mixed/neutral）和 emotion_intensity（1-5）
- 🔴 多人场景：同时填写 person（逗号分隔）和 persons（数组）
- tags用于后续检索，多人场景下每个人名都要加入tags
- expires_days: 短期记忆设置过期天数，否则null
- trigger_conditions: 只有条件性计划时才填写

【纠错识别】🔴
当用户否定或修正之前的信息时，添加：
  "corrects": {{
    "target_summary_hint": "被纠正的记忆摘要关键词",
    "reason": "纠正原因"
  }}
"""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MemoryExtractionService:
    """Service for extracting memories from conversations using LLM."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = openai_adapter
        self.memory_repo = MemoryRepository(db)
        self.config = memory_config
        self._embedding_service = None

    @property
    def embedding_service(self):
        """Lazy-load embedding service to avoid circular imports."""
        if self._embedding_service is None:
            from .embedding_service import EmbeddingService

            self._embedding_service = EmbeddingService()
        return self._embedding_service

    async def extract_from_message(
        self,
        user_id: UUID,
        family_id: UUID,
        message: str,
        context: Optional[List[Dict[str, str]]] = None,
        source_session_id: Optional[UUID] = None,
        source_message_id: Optional[UUID] = None,
    ) -> List[ConversationMemory]:
        """Extract memories from a user message."""
        if len(message.strip()) < self.config.min_message_length:
            return []

        skip_patterns = [
            r"^(你好|嗨|hi|hello|早|晚安|谢谢|好的|ok|行|嗯|哦)$",
            r"^(在吗|忙吗|有空吗)$",
        ]
        message_lower = message.lower().strip()
        for pattern in skip_patterns:
            if re.match(pattern, message_lower, re.IGNORECASE):
                return []

        context_str = ""
        if context:
            context_str = "\n".join(
                f"{msg['role']}: {msg['content']}" for msg in context[-5:]
            )

        extracted = await self._call_llm_with_retry(message, context_str)
        if not extracted:
            return []

        created_memories = []
        try:
            for mem_data in extracted:
                memory = await self._store_single_memory(
                    user_id=user_id,
                    family_id=family_id,
                    message=message,
                    mem_data=mem_data,
                    source_session_id=source_session_id,
                    source_message_id=source_message_id,
                    auto_commit=True,
                )
                if memory:
                    created_memories.append(memory)
                    logger.info(
                        "Extracted memory: type=%s, summary=%s...",
                        memory.memory_type,
                        memory.summary[:50],
                    )
        except SQLAlchemyError as e:
            logger.error("Memory storage failed: %s", e)
        except Exception as e:
            logger.error("Unexpected error in memory storage: %s", e)

        if created_memories:
            # Publish domain events for each extracted memory
            # Use publish_with_outbox to ensure cross-process consumers
            # (curation-workers, briefing-workers) receive via Redis Streams
            try:
                from ...core.events import get_event_bus
                from ...core.events.domain_events import MemoryExtracted
                event_bus = get_event_bus()
                for memory in created_memories:
                    mentioned = []
                    persons = (memory.entities or {}).get("persons")
                    if isinstance(persons, list):
                        mentioned.extend(persons)
                    person = (memory.entities or {}).get("person")
                    if person and person not in mentioned:
                        mentioned.append(person)
                    await event_bus.publish_with_outbox(
                        self.db,
                        MemoryExtracted(
                            memory_id=memory.id,
                            family_id=family_id,
                            user_id=user_id,
                            memory_type=memory.memory_type or "",
                            entities=memory.entities or {},
                            mentioned_persons=mentioned,
                        ),
                    )
                # Commit outbox rows (memories already committed by auto_commit)
                await self.db.commit()
            except Exception as e:
                logger.warning("Failed to publish MemoryExtracted event: %s", e)

            try:
                await self._auto_associate_memories(user_id, created_memories)
            except Exception as e:
                logger.warning("Memory association failed (non-critical): %s", e)

            try:
                await self._auto_extract_contacts(
                    user_id, family_id, created_memories
                )
            except Exception as e:
                logger.warning("Contact auto-extraction failed (non-critical): %s", e)

            # C5: Invalidate context cache after new memories are stored
            try:
                from ...ai_engine.context_assembler import ContextAssembler
                await ContextAssembler.invalidate_context_cache(user_id)
            except Exception as e:
                logger.debug("C5: Failed to invalidate context cache: %s", e)

        return created_memories

    async def extract_and_store(
        self,
        user_id: UUID,
        family_id: UUID,
        message: str,
        context: Optional[List[Dict[str, str]]] = None,
        source_session_id: Optional[UUID] = None,
        source_message_id: Optional[UUID] = None,
    ) -> Tuple[List[ConversationMemory], Optional[str]]:
        """Extract memories and return them along with a context hint."""
        memories = await self.extract_from_message(
            user_id=user_id,
            family_id=family_id,
            message=message,
            context=context,
            source_session_id=source_session_id,
            source_message_id=source_message_id,
        )
        context_hint = None
        if memories:
            hints = [f"- [{mem.memory_type}] {mem.summary}" for mem in memories]
            context_hint = "\u3010\u5df2\u63d0\u53d6\u7684\u65b0\u8bb0\u5fc6\u3011\n" + "\n".join(hints)
        return memories, context_hint

    # -- LLM interaction ---------------------------------------------------

    async def _call_llm_with_retry(
        self,
        message: str,
        context_str: str,
    ) -> List[Dict[str, Any]]:
        """Call LLM for extraction with retry on transient failures."""
        prompt = MEMORY_EXTRACTION_PROMPT.format(
            user_message=message,
            context=context_str or "\uff08\u65e0\u4e0a\u4e0b\u6587\uff09",
        )

        last_error = None
        for attempt in range(self.config.llm_max_retries + 1):
            try:
                response = await self.llm.chat(
                    messages=[LLMMessage(role="user", content=prompt)],
                    temperature=self.config.extraction_temperature,
                    max_tokens=self.config.extraction_max_tokens,
                )
                return self._parse_extraction_response(response.text)
            except json.JSONDecodeError as e:
                logger.warning("JSON parse error on attempt %d: %s", attempt + 1, e)
                last_error = ParsingError(f"Failed to parse LLM response: {e}")
            except Exception as e:
                error_str = str(e).lower()
                is_transient = any(
                    kw in error_str
                    for kw in [
                        "timeout", "rate limit", "connection",
                        "temporarily", "overloaded", "503", "502", "504",
                    ]
                )
                if is_transient and attempt < self.config.llm_max_retries:
                    logger.warning(
                        "Transient LLM error on attempt %d, retrying: %s",
                        attempt + 1, e,
                    )
                    await asyncio.sleep(self.config.llm_retry_delay * (attempt + 1))
                    last_error = LLMExtractionError(f"LLM call failed: {e}")
                else:
                    logger.error("LLM extraction failed: %s", e)
                    last_error = LLMExtractionError(f"LLM call failed: {e}")
                    break

        if last_error:
            logger.error("Memory extraction failed after retries: %s", last_error)
        return []

    # -- Storage -----------------------------------------------------------

    async def _store_single_memory(
        self,
        user_id: UUID,
        family_id: UUID,
        message: str,
        mem_data: Dict[str, Any],
        source_session_id: Optional[UUID],
        source_message_id: Optional[UUID],
        auto_commit: bool = False,
    ) -> Optional[ConversationMemory]:
        """Store a single extracted memory."""
        expires_at = None
        if mem_data.get("expires_days"):
            try:
                expires_days = int(mem_data["expires_days"])
                if expires_days > 0:
                    expires_at = utc_now() + timedelta(days=expires_days)
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid expires_days value: %s", mem_data.get("expires_days")
                )

        trigger_conditions = mem_data.get("trigger_conditions")
        if trigger_conditions:
            trigger_conditions = self._validate_trigger_conditions(trigger_conditions)

        embedding = None
        if self.config.semantic_search_enabled:
            try:
                text_for_embedding = mem_data.get("summary", message[:100])
                embedding = await self.embedding_service.get_embedding(
                    text_for_embedding
                )
            except Exception as e:
                logger.warning("Failed to generate embedding for memory: %s", e)

        corrects = mem_data.get("corrects")
        if corrects and isinstance(corrects, dict):
            hint = corrects.get("target_summary_hint", "")
            if hint:
                await self._supersede_matching_memory(
                    user_id, hint, corrects.get("reason", "\u7528\u6237\u7ea0\u6b63")
                )

        memory_type = mem_data.get("memory_type", MemoryType.GENERAL.value)
        entities = mem_data.get("entities", {})
        sensitivity_level = classify_sensitivity(memory_type, message, entities)

        return await self.memory_repo.create_memory(
            user_id=user_id,
            family_id=family_id,
            memory_type=memory_type,
            content=message,
            summary=mem_data.get("summary", message[:100]),
            entities=entities,
            tags=mem_data.get("tags", []),
            importance=mem_data.get("importance", self.config.default_importance),
            confidence=mem_data.get("confidence", self.config.default_confidence),
            source_session_id=source_session_id,
            source_message_id=source_message_id,
            expires_at=expires_at,
            trigger_conditions=trigger_conditions,
            embedding=embedding,
            sensitivity_level=sensitivity_level.value,
            auto_commit=auto_commit,
        )

    async def _supersede_matching_memory(
        self,
        user_id: UUID,
        summary_hint: str,
        reason: str,
    ) -> None:
        """Find and mark as superseded any active memory matching the hint."""
        hint_lower = summary_hint.strip().lower()
        if len(hint_lower) < 2:
            return

        stmt = (
            select(ConversationMemory)
            .where(
                and_(
                    ConversationMemory.user_id == user_id,
                    ConversationMemory.status == MemoryStatus.ACTIVE.value,
                    func.lower(ConversationMemory.summary).contains(hint_lower),
                )
            )
            .order_by(ConversationMemory.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        old_memory = result.scalar_one_or_none()

        if old_memory:
            old_memory.status = MemoryStatus.SUPERSEDED.value
            logger.info(
                "Superseded memory '%s' (reason: %s)",
                old_memory.summary[:50],
                reason,
            )

    # -- Validation --------------------------------------------------------

    def _validate_trigger_conditions(
        self, conditions: Any
    ) -> Optional[Dict[str, Any]]:
        """Validate and normalize trigger conditions structure."""
        if not isinstance(conditions, dict):
            return None

        valid_types = [
            "location_mention", "person_mention",
            "keyword_mention", "date_approaching",
        ]
        valid_actions = ["notify", "remind", "suggest"]

        cond_type = conditions.get("type")
        cond_value = conditions.get("value")
        if not cond_type or not cond_value:
            return None
        if cond_type not in valid_types:
            logger.warning("Invalid trigger type: %s", cond_type)
            return None

        return {
            "type": cond_type,
            "value": str(cond_value).strip(),
            "action": (
                conditions.get("action", "notify")
                if conditions.get("action") in valid_actions
                else "notify"
            ),
            "message": conditions.get("message", ""),
        }

    def _parse_extraction_response(
        self, response_text: str
    ) -> List[Dict[str, Any]]:
        """Parse LLM response to extract memory data."""
        try:
            text = response_text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)
            if isinstance(data, dict):
                data = [data]

            return [mem for mem in data if self._validate_memory_data(mem)]
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse extraction response: %s", e)
            return []
        except Exception as e:
            logger.error("Error parsing extraction response: %s", e)
            return []

    def _validate_memory_data(self, mem_data: Dict[str, Any]) -> bool:
        """Validate extracted memory data."""
        if not mem_data.get("summary"):
            return False

        valid_types = [t.value for t in MemoryType]
        if mem_data.get("memory_type", "general") not in valid_types:
            mem_data["memory_type"] = "general"

        importance = mem_data.get("importance", 5)
        if not isinstance(importance, int) or importance < 1 or importance > 10:
            mem_data["importance"] = 5

        confidence = mem_data.get("confidence", 0.8)
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            mem_data["confidence"] = 0.8

        return True

    # -- Auto-association --------------------------------------------------

    async def _auto_extract_contacts(
        self,
        user_id: UUID,
        family_id: UUID,
        memories: List[ConversationMemory],
    ):
        """Automatically extract and save contacts mentioned in memories."""
        from .auto_contact_extraction_service import (
            AutoContactExtractionService,
        )

        contact_service = AutoContactExtractionService(self.db)
        created_contacts = await contact_service.extract_contacts_from_memories(
            user_id=user_id,
            family_id=family_id,
            memories=memories,
        )
        if created_contacts:
            contact_names = [c[0].name for c in created_contacts]
            logger.info(
                "Auto-extracted %d contact(s) from conversation: %s",
                len(created_contacts),
                ", ".join(contact_names),
            )

    async def _auto_associate_memories(
        self,
        user_id: UUID,
        new_memories: List[ConversationMemory],
    ):
        """Automatically associate new memories with existing related memories."""
        try:
            for memory in new_memories:
                related = []

                location = memory.entities.get("location")
                if location:
                    loc_related = await self.memory_repo.search_by_location(
                        user_id, location, limit=5
                    )
                    related.extend(
                        [
                            (m, "location", self.config.association_location_strength)
                            for m in loc_related
                            if m.id != memory.id
                        ]
                    )

                persons_list = []
                persons = memory.entities.get("persons")
                if persons and isinstance(persons, list):
                    persons_list.extend(persons)
                person = memory.entities.get("person")
                if person:
                    for p in (
                        person.replace("\u3001", ",").replace("\uff0c", ",").split(",")
                    ):
                        p = p.strip()
                        if p and p not in persons_list:
                            persons_list.append(p)

                for p in persons_list:
                    person_related = await self.memory_repo.search_by_person(
                        user_id, p, limit=5
                    )
                    related.extend(
                        [
                            (m, "person", self.config.association_person_strength)
                            for m in person_related
                            if m.id != memory.id
                        ]
                    )

                seen_pairs = set()
                for related_mem, assoc_type, strength in related:
                    pair_key = (related_mem.id, assoc_type)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    reason_detail = (
                        location
                        if assoc_type == "location"
                        else (", ".join(persons_list) if persons_list else person)
                    )
                    await self.memory_repo.create_association(
                        memory_id_a=memory.id,
                        memory_id_b=related_mem.id,
                        association_type=assoc_type,
                        strength=strength,
                        reason=f"Shared {assoc_type}: {reason_detail}",
                    )
        except Exception as e:
            logger.error("Error auto-associating memories: %s", e)


class MemoryExtractionServiceAsync:
    """Async wrapper for background memory extraction."""

    @staticmethod
    async def extract_async(
        db: AsyncSession,
        user_id: UUID,
        family_id: UUID,
        message: str,
        context: Optional[List[Dict[str, str]]] = None,
        source_session_id: Optional[UUID] = None,
        source_message_id: Optional[UUID] = None,
    ):
        """Extract memories in the background."""
        service = MemoryExtractionService(db)
        await service.extract_from_message(
            user_id=user_id,
            family_id=family_id,
            message=message,
            context=context,
            source_session_id=source_session_id,
            source_message_id=source_message_id,
        )
