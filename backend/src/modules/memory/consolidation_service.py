"""Memory Consolidation Service - Periodic consolidation of short-term to long-term memory.

Provides:
- Weekly memory consolidation (short-term -> long-term)
- Person profile generation and updates
- Memory summarization using LLM
- Archival of consolidated memories
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
from collections import defaultdict

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.llm import openai_adapter
from ...config.logging import get_logger
from ...core.interfaces.llm_provider import LLMMessage
from ...core.utils.timezone import utc_now
from ..member.models import PersonProfile, ProfileStatus
from .utils import extract_json_from_response, find_person_profile_by_name
from .models import (
    ConversationMemory,
    MemorySummary,
    MemoryStatus,
    MemoryType,
    SummaryType,
)
from .repository import MemoryRepository

logger = get_logger(__name__)


def compute_summary_confidence(
    memories: List[ConversationMemory],
) -> float:
    """Compute a confidence score for a memory summary.

    The score is based on three factors:
    1. Source memory count -- more sources = higher confidence (saturates at 10).
    2. Agreement -- how consistent the importance ratings are across sources
       (lower variance = higher confidence).
    3. Recency -- more recent memories contribute more confidence.

    Returns a float in [0.0, 1.0].
    """
    if not memories:
        return 0.0

    # Factor 1: source count (0.0 .. 1.0, saturates at 10 memories)
    count_factor = min(len(memories) / 10.0, 1.0)

    # Factor 2: agreement (inverse coefficient of variation of importance)
    importances = [float(m.importance or 5) for m in memories]
    mean_imp = sum(importances) / len(importances) if importances else 5.0
    if mean_imp > 0 and len(importances) > 1:
        variance = sum((x - mean_imp) ** 2 for x in importances) / len(importances)
        std_dev = variance ** 0.5
        cv = std_dev / mean_imp  # coefficient of variation
        agreement_factor = max(0.0, 1.0 - cv)
    else:
        agreement_factor = 1.0

    # Factor 3: recency (average age in days, decayed)
    now = utc_now()
    ages_days = []
    for m in memories:
        if m.created_at:
            created = m.created_at
            if created.tzinfo is None:
                from datetime import timezone
                created = created.replace(tzinfo=timezone.utc)
            age = max((now - created).days, 0)
            ages_days.append(age)
    if ages_days:
        avg_age = sum(ages_days) / len(ages_days)
        recency_factor = 1.0 / (1.0 + avg_age / 30.0)
    else:
        recency_factor = 0.5

    # Weighted combination
    score = 0.4 * count_factor + 0.3 * agreement_factor + 0.3 * recency_factor
    return round(min(max(score, 0.0), 1.0), 4)


class MemoryConsolidationService:
    """Service for consolidating short-term memories into long-term storage."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory_repo = MemoryRepository(db)
        self.llm = openai_adapter

    async def consolidate_weekly_memories(
        self,
        user_id: UUID,
        family_id: UUID,
        days_back: int = 7,
    ) -> Dict[str, Any]:
        """Consolidate memories from the past week into long-term storage."""
        results = {
            "memories_processed": 0,
            "person_profiles_updated": 0,
            "summaries_created": 0,
            "errors": [],
        }

        try:
            since = utc_now() - timedelta(days=days_back)
            memories = await self._get_unconsolidated_memories(user_id, since)

            if not memories:
                logger.debug(f"No unconsolidated memories found for user {user_id}")
                return results

            results["memories_processed"] = len(memories)
            logger.debug(f"Processing {len(memories)} memories for consolidation")

            person_memories = self._group_by_person(memories)
            for person_name, person_mems in person_memories.items():
                try:
                    await self._update_person_profile(user_id, family_id, person_name, person_mems)
                    results["person_profiles_updated"] += 1
                except Exception as e:
                    logger.error(f"Error updating profile for {person_name}: {e}")
                    results["errors"].append(f"Profile update failed for {person_name}: {str(e)}")

            topic_memories = self._group_by_topic(memories)
            for topic, topic_mems in topic_memories.items():
                if len(topic_mems) >= 2:
                    try:
                        await self._create_topic_summary(
                            user_id, family_id, topic, topic_mems, since, utc_now()
                        )
                        results["summaries_created"] += 1
                    except Exception as e:
                        logger.error(f"Error creating summary for {topic}: {e}")
                        results["errors"].append(f"Summary creation failed for {topic}: {str(e)}")

            try:
                await self._create_period_summary(user_id, family_id, memories, since, utc_now())
                results["summaries_created"] += 1
            except Exception as e:
                logger.error(f"Error creating period summary: {e}")
                results["errors"].append(f"Period summary creation failed: {str(e)}")

            memory_ids = [m.id for m in memories]
            await self._mark_memories_consolidated(memory_ids)

            logger.info(f"Consolidation complete: {results}")

        except Exception as e:
            logger.error(f"Memory consolidation failed: {e}")
            results["errors"].append(f"Consolidation failed: {str(e)}")

        return results

    async def _get_unconsolidated_memories(
        self, user_id: UUID, since: datetime,
    ) -> List[ConversationMemory]:
        """Get memories that haven't been consolidated yet."""
        query = select(ConversationMemory).where(
            and_(
                ConversationMemory.user_id == user_id,
                ConversationMemory.status == MemoryStatus.ACTIVE.value,
                ConversationMemory.created_at >= since,
                or_(
                    ConversationMemory.is_consolidated.is_(None),
                    ConversationMemory.is_consolidated == False,
                ),
            )
        ).order_by(ConversationMemory.created_at)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    def _group_by_person(
        self, memories: List[ConversationMemory],
    ) -> Dict[str, List[ConversationMemory]]:
        """Group memories by person mentioned."""
        person_memories = defaultdict(list)
        for memory in memories:
            entities = memory.entities or {}
            person = entities.get("person")
            persons = entities.get("persons", [])
            if person:
                person_memories[person].append(memory)
            for p in persons:
                person_memories[p].append(memory)
        return dict(person_memories)

    def _group_by_topic(
        self, memories: List[ConversationMemory],
    ) -> Dict[str, List[ConversationMemory]]:
        """Group memories by topic (memory type)."""
        topic_memories = defaultdict(list)
        for memory in memories:
            topic_memories[memory.memory_type].append(memory)
        return dict(topic_memories)

    async def _update_person_profile(
        self,
        user_id: UUID,
        family_id: UUID,
        person_name: str,
        memories: List[ConversationMemory],
    ) -> PersonProfile:
        """Update or create a person profile based on memories."""
        profile = await find_person_profile_by_name(self.db, user_id, person_name)

        if not profile:
            profile = PersonProfile(
                user_id=user_id,
                family_id=family_id,
                name=person_name,
                aliases=[],
                source_memory_ids=[],
            )
            self.db.add(profile)

        # Auto-fill member_id if missing
        if not profile.member_id:
            from ..member.models.member import Member
            member_stmt = select(Member).where(
                Member.family_id == family_id,
                Member.name == person_name,
                or_(Member.is_deleted.is_(None), Member.is_deleted == False),
            ).limit(1)
            member_result = await self.db.execute(member_stmt)
            matched_member = member_result.scalar_one_or_none()
            if matched_member:
                profile.member_id = matched_member.id

        aggregated = await self._aggregate_person_info(person_name, memories)

        if aggregated.get("relationship"):
            profile.relationship = aggregated["relationship"]
        if aggregated.get("location"):
            profile.location = aggregated["location"]
        if aggregated.get("organization"):
            profile.organization = aggregated["organization"]
        if aggregated.get("preferences"):
            profile.update_preferences(aggregated["preferences"])

        for favor in aggregated.get("favors", []):
            profile.record_favor(
                favor_type=favor["type"],
                description=favor["description"],
                weight=favor.get("weight", 1.0),
            )

        for alias in aggregated.get("aliases", []):
            profile.add_alias(alias)

        for memory in memories:
            if profile.source_memory_ids is None:
                profile.source_memory_ids = []
            if memory.id not in profile.source_memory_ids:
                profile.source_memory_ids = [*profile.source_memory_ids, memory.id]

        profile.mention_count = (profile.mention_count or 0) + len(memories)
        if memories:
            memory_dates = [m.created_at for m in memories if m.created_at]
            if memory_dates:
                profile.last_mentioned_at = max(memory_dates)
        profile.updated_at = utc_now()

        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def _aggregate_person_info(
        self, person_name: str, memories: List[ConversationMemory],
    ) -> Dict[str, Any]:
        """Use LLM to aggregate person information from memories."""
        memory_texts = [f"- [{m.memory_type}] {m.summary}" for m in memories]

        prompt = f"""分析以下关于"{person_name}"的记忆，提取并汇总关键信息。

记忆内容：
{chr(10).join(memory_texts)}

请返回JSON格式，包含以下字段（如果信息存在）：
{{
    "relationship": "与用户的关系（朋友/同事/客户/亲戚等）",
    "location": "所在城市或地区",
    "organization": "公司或组织",
    "preferences": {{
        "likes": ["喜欢的事物"],
        "dislikes": ["不喜欢的事物"]
    }},
    "aliases": ["其他称呼或昵称"],
    "favors": [
        {{"type": "received/given", "description": "描述", "weight": 1.0}}
    ]
}}

只返回JSON，不要其他文字。如果某字段信息不确定，请省略该字段。"""

        try:
            response = await self.llm.chat([LLMMessage(role="user", content=prompt)])
            result = extract_json_from_response(response.content)
            if result is None:
                logger.warning("Failed to parse JSON from LLM response for person info")
                return {}
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.warning(f"Failed to aggregate person info via LLM: {e}")
            return {}

    async def _create_topic_summary(
        self,
        user_id: UUID,
        family_id: UUID,
        topic: str,
        memories: List[ConversationMemory],
        period_start: datetime,
        period_end: datetime,
    ) -> MemorySummary:
        """Create a topic summary from related memories."""
        memory_texts = [f"- {m.summary}" for m in memories]

        prompt = f"""请为以下关于"{topic}"的记忆生成一个简洁的汇总：

{chr(10).join(memory_texts)}

要求：
1. 用1-2句话概括主要内容
2. 突出关键信息和趋势
3. 使用中文

只返回汇总文字，不要其他内容。"""

        try:
            response = await self.llm.chat([LLMMessage(role="user", content=prompt)])
            summary_content = response.content.strip()
        except Exception as e:
            logger.warning(f"Failed to generate topic summary via LLM: {e}")
            summary_content = f"关于{topic}的{len(memories)}条记忆"

        memory_ids = [m.id for m in memories]
        confidence = compute_summary_confidence(memories)
        summary = MemorySummary(
            user_id=user_id,
            family_id=family_id,
            summary_type=SummaryType.TOPIC_SUMMARY.value,
            title=f"主题汇总: {topic}",
            content=summary_content,
            source_memory_ids=memory_ids,
            consolidated_entities={
                "topic": topic,
                "memory_count": len(memories),
            },
            tags=[topic],
            period_start=period_start,
            period_end=period_end,
            importance=max((m.importance for m in memories if m.importance is not None), default=5),
            confidence_score=confidence,
        )
        self.db.add(summary)
        await self.db.flush()

        # Mark original memories as superseded by this summary
        await self.memory_repo.mark_memories_superseded(
            memory_ids=memory_ids,
            superseded_by=summary.id,
        )

        await self.db.refresh(summary)
        return summary

    async def _create_period_summary(
        self,
        user_id: UUID,
        family_id: UUID,
        memories: List[ConversationMemory],
        period_start: datetime,
        period_end: datetime,
    ) -> MemorySummary:
        """Create a period summary for all memories in the time range."""
        type_counts = defaultdict(int)
        persons_mentioned = set()
        locations_mentioned = set()

        for memory in memories:
            type_counts[memory.memory_type] += 1
            entities = memory.entities or {}
            if entities.get("person"):
                persons_mentioned.add(entities["person"])
            if entities.get("location"):
                locations_mentioned.add(entities["location"])

        summary_parts = [f"- {mtype}: {count}条" for mtype, count in type_counts.items()]
        if persons_mentioned:
            summary_parts.append(f"- 提到的人物: {', '.join(list(persons_mentioned)[:5])}")
        if locations_mentioned:
            summary_parts.append(f"- 提到的地点: {', '.join(list(locations_mentioned)[:5])}")

        prompt = f"""请为以下周报数据生成一个简洁的汇总（1-2句话）：

本周记忆统计:
{chr(10).join(summary_parts)}

要求使用中文，突出本周的重点关注领域。只返回汇总文字。"""

        try:
            response = await self.llm.chat([LLMMessage(role="user", content=prompt)])
            summary_content = response.content.strip()
        except Exception as e:
            logger.warning(f"Failed to generate period summary via LLM: {e}")
            summary_content = f"本周共记录{len(memories)}条记忆"

        memory_ids = [m.id for m in memories]
        period_str = period_start.strftime("%Y-%m-%d")
        confidence = compute_summary_confidence(memories)
        summary = MemorySummary(
            user_id=user_id,
            family_id=family_id,
            summary_type=SummaryType.PERIOD_SUMMARY.value,
            title=f"周报: {period_str}",
            content=summary_content,
            source_memory_ids=memory_ids,
            consolidated_entities={
                "type_counts": dict(type_counts),
                "persons": list(persons_mentioned),
                "locations": list(locations_mentioned),
                "total_count": len(memories),
            },
            tags=["周报"],
            period_start=period_start,
            period_end=period_end,
            importance=5,
            confidence_score=confidence,
        )
        self.db.add(summary)
        await self.db.flush()

        # Mark any remaining ACTIVE memories as superseded by this period summary.
        # Memories already superseded by topic summaries are skipped (status != ACTIVE).
        still_active = [
            m.id for m in memories
            if m.status == MemoryStatus.ACTIVE.value
        ]
        if still_active:
            await self.memory_repo.mark_memories_superseded(
                memory_ids=still_active,
                superseded_by=summary.id,
            )

        await self.db.refresh(summary)
        return summary

    async def _mark_memories_consolidated(self, memory_ids: List[UUID]) -> int:
        """Mark memories as consolidated."""
        if not memory_ids:
            return 0
        result = await self.db.execute(
            update(ConversationMemory)
            .where(ConversationMemory.id.in_(memory_ids))
            .values(is_consolidated=True, updated_at=utc_now())
        )
        await self.db.commit()
        return result.rowcount

    async def get_person_profiles(
        self,
        user_id: UUID,
        limit: int = 50,
        min_importance: int = 1,
    ) -> List[PersonProfile]:
        """Get all person profiles for a user."""
        query = select(PersonProfile).where(
            and_(
                PersonProfile.user_id == user_id,
                PersonProfile.status == ProfileStatus.ACTIVE.value,
                PersonProfile.importance >= min_importance,
            )
        ).order_by(
            PersonProfile.importance.desc(),
            PersonProfile.last_mentioned_at.desc(),
        ).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_neglected_contacts(
        self,
        user_id: UUID,
        threshold_days: int = 90,
        min_importance: int = 5,
    ) -> List[PersonProfile]:
        """Get contacts that haven't been mentioned in a while."""
        threshold = utc_now() - timedelta(days=threshold_days)
        query = select(PersonProfile).where(
            and_(
                PersonProfile.user_id == user_id,
                PersonProfile.status == ProfileStatus.ACTIVE.value,
                PersonProfile.importance >= min_importance,
                or_(
                    PersonProfile.last_mentioned_at.is_(None),
                    PersonProfile.last_mentioned_at < threshold,
                ),
            )
        ).order_by(PersonProfile.importance.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_pending_favors(self, user_id: UUID) -> List[PersonProfile]:
        """Get contacts with pending favor balance (we owe them)."""
        query = select(PersonProfile).where(
            and_(
                PersonProfile.user_id == user_id,
                PersonProfile.status == ProfileStatus.ACTIVE.value,
                PersonProfile.favor_balance < -0.5,
            )
        ).order_by(PersonProfile.favor_balance)
        result = await self.db.execute(query)
        return list(result.scalars().all())
