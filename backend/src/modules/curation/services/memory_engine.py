"""
Memory Engine for curation intelligence.

Handles multi-source memory queries, social intent extraction, and relevance scoring.
"""
import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .query_utils import escape_like

from ....core.llm import openai_adapter
from ....core.interfaces.llm_provider import LLMMessage
from ...memory.models import ConversationMemory
from ..models import CuratedEvent, SocialIntent

logger = logging.getLogger(__name__)


# LLM Prompt for social intent extraction
SOCIAL_INTENT_EXTRACTION_PROMPT = """你是一个智能秘书，负责从用户对话中提取社交意图。

## 任务
从用户的对话中识别社交意图，包括：
- 想见某人（meet_person）
- 想送礼物（send_gift）
- 想去某地（visit_place）
- 想打电话（call_person）
- 其他社交行动

## 社交意图的特征
1. 包含明确的触发条件（地点、日期、事件类型）
2. 包含明确的目标人物或地点
3. 包含明确的行动描述

## 输出格式
必须返回有效的JSON格式，包含以下字段：
- has_intent: boolean
- intent_type: string (如果has_intent为true)
- target_person_name: string (可选)
- action_description: string (如果has_intent为true)
- trigger_type: string (location, date, event)
- trigger_location: string (如果trigger_type为location)
- trigger_date: string (如果trigger_type为date)
- trigger_event_type: string (如果trigger_type为event)
- confidence: float (0.0-1.0)

现在请分析以下对话内容：
"""


class MemoryEngine:
    """Memory Engine for multi-source memory queries and social intent extraction."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def extract_social_intent(
        self,
        memory: ConversationMemory,
    ) -> Optional[SocialIntent]:
        """Extract social intent from conversation memory using LLM."""
        try:
            response = await openai_adapter.chat(
                messages=[
                    LLMMessage(role="system", content=SOCIAL_INTENT_EXTRACTION_PROMPT),
                    LLMMessage(role="user", content=memory.content),
                ],
                temperature=0.3,
                max_tokens=500,
            )

            result = self._parse_intent_response(response.text)

            if not result or not result.get("has_intent"):
                return None

            intent = SocialIntent(
                family_id=memory.family_id,
                user_id=memory.user_id,
                intent_type=result.get("intent_type", "meet_person"),
                target_person_name=result.get("target_person_name"),
                action_description=result.get("action_description", ""),
                trigger_type=result.get("trigger_type", "location"),
                trigger_location=result.get("trigger_location"),
                trigger_event_type=result.get("trigger_event_type"),
                source_memory_id=memory.id,
                confidence=result.get("confidence", 0.8),
                status="active",
            )

            if result.get("trigger_date"):
                pass

            return intent

        except Exception as e:
            logger.error(f"Failed to extract social intent: {e}")
            return None

    def _parse_intent_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response JSON."""
        try:
            response_text = response_text.strip()
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            return json.loads(response_text)
        except Exception as e:
            logger.error(f"Failed to parse intent response: {e}")
            return None

    async def query_relevant_memories(
        self,
        family_id: UUID,
        context: Dict[str, Any],
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query relevant memories from multiple sources and rank by relevance."""
        all_memories = []

        conversation_memories = await self._query_conversation_memories(
            family_id, context
        )
        all_memories.extend(conversation_memories)

        social_intents = await self._query_social_intents(family_id, context)
        all_memories.extend(social_intents)

        historical_events = await self._query_historical_events(family_id, context)
        all_memories.extend(historical_events)

        scored_memories = []
        for memory in all_memories:
            score = self._calculate_relevance_score(memory, context)
            memory["relevance_score"] = score
            scored_memories.append(memory)

        scored_memories.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored_memories[:limit]

    async def _query_conversation_memories(
        self,
        family_id: UUID,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Query conversation memories."""
        query = select(ConversationMemory).where(
            ConversationMemory.family_id == family_id
        )

        if context.get("location"):
            query = query.where(
                ConversationMemory.content.ilike(f"%{escape_like(context['location'])}%", escape="\\")
            )

        if context.get("person"):
            query = query.where(
                ConversationMemory.content.ilike(f"%{escape_like(context['person'])}%", escape="\\")
            )

        query = query.order_by(ConversationMemory.created_at.desc()).limit(100)

        result = await self.session.execute(query)
        memories = result.scalars().all()

        return [
            {
                "type": "conversation",
                "id": str(mem.id),
                "content": mem.content,
                "location": None,
                "person": None,
                "date": mem.created_at,
                "text": mem.content,
            }
            for mem in memories
        ]

    async def _query_social_intents(
        self,
        family_id: UUID,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Query social intents."""
        query = select(SocialIntent).where(
            and_(
                SocialIntent.family_id == family_id,
                SocialIntent.status == "active",
            )
        )

        if context.get("location"):
            query = query.where(
                SocialIntent.trigger_location.ilike(f"%{escape_like(context['location'])}%", escape="\\")
            )

        if context.get("person"):
            query = query.where(
                SocialIntent.target_person_name.ilike(f"%{escape_like(context['person'])}%", escape="\\")
            )

        result = await self.session.execute(query)
        intents = result.scalars().all()

        return [
            {
                "type": "social_intent",
                "id": str(intent.id),
                "content": f"{intent.action_description} {intent.target_person_name or ''}",
                "location": intent.trigger_location,
                "person": intent.target_person_name,
                "date": intent.created_at,
                "text": intent.action_description,
            }
            for intent in intents
        ]

    async def _query_historical_events(
        self,
        family_id: UUID,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Query historical curated events."""
        query = select(CuratedEvent).where(
            CuratedEvent.family_id == family_id
        )

        if context.get("location"):
            query = query.where(
                or_(
                    CuratedEvent.location.ilike(f"%{escape_like(context['location'])}%", escape="\\"),
                    CuratedEvent.city.ilike(f"%{escape_like(context['location'])}%", escape="\\"),
                )
            )

        if context.get("date"):
            query = query.where(
                CuratedEvent.normalized_start < context["date"]
            )

        query = query.order_by(CuratedEvent.normalized_start.desc()).limit(50)

        result = await self.session.execute(query)
        events = result.scalars().all()

        return [
            {
                "type": "historical_event",
                "id": str(event.id),
                "content": event.title,
                "location": event.location or event.city,
                "person": None,
                "date": event.normalized_start,
                "text": event.title,
            }
            for event in events
        ]

    def _calculate_relevance_score(
        self,
        memory: Dict[str, Any],
        context: Dict[str, Any],
    ) -> float:
        """Calculate relevance score for a memory.

        Six dimensions:
        1. Location similarity (0.4 max)
        2. Person name match (0.3 max)
        3. Temporal proximity (0.2 max)
        4. Text keyword overlap (0.1 max)
        5. Entity overlap (0.3 max) -- NEW
        6. Memory type boost (multiplier) -- NEW
        """
        score = 0.0

        # Dimension 1: Location similarity
        if context.get("location") and memory.get("location"):
            if self._location_similarity(context["location"], memory["location"]) > 0.5:
                score += 0.4
            else:
                score += 0.2

        # Dimension 2: Person name match
        if context.get("person") and memory.get("person"):
            if context["person"].lower() in (memory["person"] or "").lower():
                score += 0.3

        # Dimension 3: Temporal proximity
        if context.get("date") and memory.get("date"):
            try:
                days_diff = abs((context["date"] - memory["date"]).days)
                time_score = max(0, 1 - days_diff / 365)
                score += time_score * 0.2
            except (TypeError, AttributeError):
                pass

        # Dimension 4: Text keyword overlap
        if context.get("text") and memory.get("text"):
            context_words = set(context["text"].lower().split())
            memory_words = set(memory["text"].lower().split())
            if context_words and memory_words:
                overlap = len(context_words & memory_words) / len(context_words | memory_words)
                score += overlap * 0.1

        # Dimension 5: Entity overlap (0.3 max)
        memory_entities = self._extract_entities(memory)
        context_entities = self._extract_entities(context)
        if memory_entities and context_entities:
            overlap = len(memory_entities & context_entities)
            score += min(0.3, overlap * 0.15)

        # Dimension 6: Memory type boost
        mem_type = memory.get("type", "")
        if mem_type == "social_intent":
            score *= 1.2
        elif mem_type == "conversation":
            content = str(memory.get("content") or "").lower()
            if any(kw in content for kw in ("想去", "下次", "以后", "计划", "打算")):
                score *= 1.1  # Future plan memories are more relevant

        return min(score, 1.0)

    @staticmethod
    def _extract_entities(data: Dict[str, Any]) -> set:
        """Extract entity identifiers (person names, city, date) from memory/context dict."""
        entities = set()  # type: set
        for key in ("person", "member_name", "target_name"):
            val = data.get(key)
            if val:
                entities.add(str(val).lower().strip())
        for key in ("location", "city", "destination"):
            val = data.get(key)
            if val:
                entities.add(str(val).lower().strip())
        if data.get("date"):
            entities.add(str(data["date"])[:10])  # YYYY-MM-DD
        return entities

    def _location_similarity(self, loc1: str, loc2: str) -> float:
        """Calculate location similarity (simplified)."""
        loc1 = loc1.lower().strip()
        loc2 = loc2.lower().strip()

        if loc1 == loc2:
            return 1.0
        if loc1 in loc2 or loc2 in loc1:
            return 0.8
        return 0.0

    async def check_triggered_intents(
        self,
        family_id: UUID,
        event: CuratedEvent,
    ) -> List[SocialIntent]:
        """Check if an event triggers any social intents."""
        query = select(SocialIntent).where(
            and_(
                SocialIntent.family_id == family_id,
                SocialIntent.status == "active",
            )
        )

        if event.location or event.city:
            location = event.location or event.city
            query = query.where(
                SocialIntent.trigger_location.ilike(f"%{escape_like(location)}%", escape="\\")
            )

        if event.normalized_start:
            event_date = event.normalized_start.date()
            query = query.where(
                or_(
                    SocialIntent.trigger_date == event_date,
                    SocialIntent.trigger_date.is_(None),
                )
            )

        if event.event_type:
            query = query.where(
                or_(
                    SocialIntent.trigger_event_type == event.event_type,
                    SocialIntent.trigger_event_type.is_(None),
                )
            )

        result = await self.session.execute(query)
        return list(result.scalars().all())
