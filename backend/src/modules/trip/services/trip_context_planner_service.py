"""
Trip Context Planner Service - Generate comprehensive trip plans from memories

This service provides:
- Integration of multiple destination-related memories
- LLM-based comprehensive trip planning
- Structured planning output with action items
"""

import json
from datetime import date, timedelta
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from ...memory.models import ConversationMemory

from ....core.llm import openai_adapter
from ....core.interfaces.llm_provider import LLMMessage
from ....config.logging import get_logger
from ....core.utils.timezone import utc_now, local_today
from .trip_context_types import (
    TripPlanItem,
    TripContextPlan,
    TRIP_PLANNING_PROMPT,
)

logger = get_logger(__name__)

# Re-export types for backward compatibility
__all__ = [
    "TripContextPlannerService",
    "TripPlanItem",
    "TripContextPlan",
    "TripPlanningAssistant",
]


def __getattr__(name: str) -> Any:
    """Lazy import for backward compatibility."""
    if name == "TripPlanningAssistant":
        from .trip_planning_assistant import TripPlanningAssistant
        return TripPlanningAssistant
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class TripContextPlannerService:
    """Service for generating comprehensive trip plans from memories"""

    def __init__(self, db: AsyncSession):
        self.db = db
        # Lazy import: memory module read access
        from ...memory.repository import MemoryRepository
        self.memory_repo = MemoryRepository(db)
        self.llm = openai_adapter
        self._member_repo = None  # Lazy-loaded
        self._date_repo = None  # Lazy-loaded

    @property
    def member_repo(self):
        """Lazy-load member repository"""
        if self._member_repo is None:
            from ...member.repositories.member_repository import MemberRepository
            self._member_repo = MemberRepository(self.db)
        return self._member_repo

    @property
    def date_repo(self):
        """Lazy-load date repository"""
        if self._date_repo is None:
            from ...date_manager.date_repository import ImportantDateRepository
            self._date_repo = ImportantDateRepository(self.db)
        return self._date_repo

    async def generate_trip_plan(
        self,
        user_id: UUID,
        destination: str,
        trip_start: Optional[date] = None,
        trip_end: Optional[date] = None,
        additional_context: Optional[str] = None,
        family_id: Optional[UUID] = None,
    ) -> TripContextPlan:
        """
        Generate a comprehensive trip plan based on destination-related memories.

        PRD 4.2: 时空关联建议卡片
        - 关联相关人物并计算"X年未见"
        - 关联礼物提醒
        - 关联重要日期警告

        Args:
            user_id: The user ID
            destination: The trip destination
            trip_start: Optional trip start date
            trip_end: Optional trip end date
            additional_context: Additional context from current conversation
            family_id: Optional family ID for date lookups

        Returns:
            TripContextPlan with comprehensive planning information
        """
        # 1. Gather all destination-related memories
        memories = await self._gather_destination_memories(user_id, destination)

        # 2. Build context from memories (may be empty)
        memories_context = self._build_memories_context(memories) if memories else ""

        # Even without history, analyze current conversation context (PRD 4.2)
        if not memories and not additional_context:
            return TripContextPlan(
                destination=destination,
                trip_start=trip_start,
                trip_end=trip_end,
                summary=f"关于{destination}的行程，目前没有找到相关的历史信息。",
                items=[],
                people_to_meet=[],
                tasks=[],
                reminders=[],
                raw_context="",
            )

        # 4. Add additional context if provided
        if additional_context:
            memories_context += f"\n\n【当前对话上下文】\n{additional_context}"

        # 5. Generate plan using LLM
        plan_data = await self._generate_plan_with_llm(
            destination=destination,
            trip_start=trip_start,
            trip_end=trip_end,
            memories_context=memories_context,
        )

        # 6. Build items with contact info and reminders
        items = await self._build_plan_items(
            user_id, destination, memories, plan_data, family_id, trip_start, trip_end
        )

        people_to_meet = plan_data.get("people_to_meet", [])

        return TripContextPlan(
            destination=destination,
            trip_start=trip_start,
            trip_end=trip_end,
            summary=plan_data.get("summary", ""),
            items=items,
            people_to_meet=people_to_meet,
            tasks=plan_data.get("tasks", []),
            reminders=plan_data.get("reminders", []),
            raw_context=memories_context,
        )

    async def _build_plan_items(
        self,
        user_id: UUID,
        destination: str,
        memories: List["ConversationMemory"],
        plan_data: Dict[str, Any],
        family_id: Optional[UUID],
        trip_start: Optional[date],
        trip_end: Optional[date],
    ) -> List[TripPlanItem]:
        """Build plan items with contact info, gift reminders, and date warnings."""
        items: List[TripPlanItem] = []
        people_to_meet = plan_data.get("people_to_meet", [])

        # PRD 4.2: 为每个人添加"X年未见"信息
        people_with_contact_info = []
        for person in people_to_meet:
            last_contact = await self._get_person_last_contact_info(user_id, person)
            people_with_contact_info.append({
                "name": person,
                "last_contact": last_contact,
            })

        for item_data in plan_data.get("items", []):
            source_memory_id = self._find_matching_memory_id(
                memories, item_data.get("person"), item_data.get("description")
            )

            person = item_data.get("person")
            if person:
                for p_info in people_with_contact_info:
                    if p_info["name"] == person and p_info["last_contact"]:
                        item_data["time_hint"] = (
                            f"（{p_info['last_contact']}），"
                            + (item_data.get("time_hint") or "建议约见面")
                        )
                        break

            items.append(TripPlanItem(
                category=item_data.get("category", "suggestion"),
                title=item_data.get("title", ""),
                description=item_data.get("description", ""),
                priority=item_data.get("priority", 5),
                person=item_data.get("person"),
                location=destination,
                time_hint=item_data.get("time_hint"),
                source_memory_id=source_memory_id,
            ))

        # PRD 4.2: 添加礼物提醒
        gift_reminders = await self._find_gift_reminders(user_id, destination, people_to_meet)
        for gift in gift_reminders:
            items.append(TripPlanItem(
                category="task",
                title=gift.get("gift_hint", "礼物提醒")[:30],
                description=gift.get("gift_hint", ""),
                priority=7,
                person=gift.get("person"),
                location=destination,
                time_hint=None,
            ))

        # PRD 4.2: 添加重要日期警告
        if family_id:
            date_reminders = await self._find_important_dates_during_trip(
                family_id, trip_start, trip_end
            )
            for date_reminder in date_reminders:
                items.append(TripPlanItem(
                    category="reminder",
                    title=f"{date_reminder['title']}",
                    description=date_reminder.get("suggestion", ""),
                    priority=9,
                    person=None,
                    location=None,
                    time_hint=date_reminder.get("suggestion"),
                ))

        # 按优先级排序
        items.sort(key=lambda x: x.priority, reverse=True)
        return items

    async def _gather_destination_memories(
        self,
        user_id: UUID,
        destination: str,
    ) -> List["ConversationMemory"]:
        """Gather all memories related to a destination"""
        memories: List["ConversationMemory"] = []
        seen_ids: set = set()

        # Search by location
        location_memories = await self.memory_repo.search_by_location(
            user_id, destination, limit=10
        )
        for mem in location_memories:
            if mem.id not in seen_ids:
                memories.append(mem)
                seen_ids.add(mem.id)

        # Search by tags (PRD 4.2: 代购/购物任务关联)
        tag_memories = await self.memory_repo.search_by_tags(
            user_id, [destination.lower(), "旅行", "出差", "代购", "购物", "买", "礼物"], limit=10
        )
        for mem in tag_memories:
            if mem.id not in seen_ids:
                memories.append(mem)
                seen_ids.add(mem.id)

        # Get plan memories that mention the destination
        plan_memories = await self.memory_repo.get_plan_memories(user_id, limit=20)
        for mem in plan_memories:
            if mem.id not in seen_ids:
                location = (mem.entities or {}).get("location", "")
                summary_lower = (mem.summary or "").lower()
                if destination.lower() in location.lower() or destination.lower() in summary_lower:
                    memories.append(mem)
                    seen_ids.add(mem.id)

        # Get triggered memories for this destination
        triggered = await self.memory_repo.get_triggered_memories(
            user_id, "location_mention", destination, limit=5
        )
        for mem in triggered:
            if mem.id not in seen_ids:
                memories.append(mem)
                seen_ids.add(mem.id)

        # Sort by importance
        memories.sort(key=lambda m: m.importance, reverse=True)

        return memories[:15]  # Limit to top 15

    def _build_memories_context(self, memories: List["ConversationMemory"]) -> str:
        """Build context string from memories for LLM"""
        if not memories:
            return ""

        parts: List[str] = []
        for i, mem in enumerate(memories, 1):
            entities = mem.entities or {}
            parts.append(f"{i}. [{mem.memory_type}] {mem.summary}")

            entity_details: List[str] = []

            # 支持多人场景：优先使用 persons 数组
            persons = entities.get("persons")
            person = entities.get("person")
            if persons and isinstance(persons, list):
                entity_details.append(f"人物: {', '.join(persons)}")
            elif person:
                entity_details.append(f"人物: {person}")

            for key, label in [("location", "地点"), ("time_hint", "时间"), ("relationship", "关系")]:
                if entities.get(key):
                    entity_details.append(f"{label}: {entities[key]}")

            trigger_msg = (mem.trigger_conditions or {}).get("message")
            if trigger_msg:
                entity_details.append(f"提醒: {trigger_msg}")

            for detail in entity_details:
                parts.append(f"   - {detail}")
            parts.append("")

        return "\n".join(parts)

    async def _generate_plan_with_llm(
        self,
        destination: str,
        trip_start: Optional[date],
        trip_end: Optional[date],
        memories_context: str,
    ) -> Dict[str, Any]:
        """Generate plan using LLM"""
        if trip_start and trip_end:
            trip_dates = f"{trip_start.strftime('%Y年%m月%d日')} 至 {trip_end.strftime('%Y年%m月%d日')}"
        elif trip_start:
            trip_dates = f"从 {trip_start.strftime('%Y年%m月%d日')} 开始"
        else:
            trip_dates = "时间待定"

        prompt = TRIP_PLANNING_PROMPT.format(
            destination=destination,
            trip_dates=trip_dates,
            memories_context=memories_context,
        )

        try:
            response = await self.llm.chat(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.5,
                max_tokens=1500,
            )

            text = response.text.strip()

            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            return json.loads(text)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise RuntimeError(f"行程上下文规划解析失败: {e}")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise RuntimeError(f"行程上下文规划失败: {e}")

    def _find_matching_memory_id(
        self,
        memories: List["ConversationMemory"],
        person: Optional[str],
        description: Optional[str],
    ) -> Optional[UUID]:
        """Find the memory ID that matches a plan item"""
        if not person and not description:
            return None

        for mem in memories:
            entities = mem.entities or {}
            mem_person = entities.get("person", "")

            if person and mem_person and person.lower() in mem_person.lower():
                return mem.id

            if description and mem.summary:
                if any(word in mem.summary for word in description.split()[:5]):
                    return mem.id

        return None

    async def _get_person_last_contact_info(
        self,
        user_id: UUID,
        person_name: str,
    ) -> Optional[str]:
        """
        获取与某人的最后联系信息（PRD 4.2 要求的"X年未见"）

        Returns:
            描述字符串，如"5年未见"、"上月见过"，或None
        """
        try:
            person_memories = await self.memory_repo.search_by_person(
                user_id, person_name, limit=10
            )

            if not person_memories:
                return None

            latest_memory = max(person_memories, key=lambda m: m.created_at)
            days = (utc_now() - latest_memory.created_at).days

            if days < 7:
                return "近日有联系"
            if days < 30:
                return f"{days // 7}周前联系"
            if days < 365:
                return f"{days // 30}个月未见"
            return f"{days // 365}年未见"

        except Exception as e:
            logger.warning(f"Failed to get last contact info for {person_name}: {e}")
            return None

    async def _find_gift_reminders(
        self,
        user_id: UUID,
        destination: str,
        people: List[str],
    ) -> List[Dict[str, Any]]:
        """
        查找与目的地或相关人物有关的礼物提醒（PRD 4.2）
        """
        gift_keywords = ["礼物", "买", "带", "特产", "绘本", "玩具", "送"]
        person_gift_keywords = ["礼物", "喜欢", "想要", "绘本", "玩具"]
        gift_reminders: List[Dict[str, Any]] = []
        seen_hints: set = set()

        def is_gift_memory(summary: str, keywords: list) -> bool:
            summary_lower = (summary or "").lower()
            return any(kw in summary_lower for kw in keywords)

        def add_reminder(person: Optional[str], hint: str, source: str) -> None:
            if hint and hint not in seen_hints:
                seen_hints.add(hint)
                gift_reminders.append({"person": person, "gift_hint": hint, "source": source})

        try:
            location_memories = await self.memory_repo.search_by_location(
                user_id, destination, limit=20
            )
            for mem in location_memories:
                if is_gift_memory(mem.summary, gift_keywords):
                    add_reminder((mem.entities or {}).get("person"), mem.summary, "location")

            for person in people:
                person_memories = await self.memory_repo.search_by_person(
                    user_id, person, limit=10
                )
                for mem in person_memories:
                    if is_gift_memory(mem.summary, person_gift_keywords):
                        add_reminder(person, mem.summary, "person")

        except Exception as e:
            logger.warning(f"Failed to find gift reminders: {e}")

        return gift_reminders[:3]

    async def _find_important_dates_during_trip(
        self,
        family_id: UUID,
        trip_start: Optional[date],
        trip_end: Optional[date],
    ) -> List[Dict[str, Any]]:
        """查找行程期间的重要日期（PRD 4.2 的警告提醒）"""
        date_reminders: List[Dict[str, Any]] = []

        if not trip_start:
            return date_reminders

        try:
            look_ahead_start = trip_start - timedelta(days=3)
            look_ahead_end = trip_end if trip_end else trip_start + timedelta(days=7)

            upcoming_dates = await self.date_repo.get_upcoming_dates(
                family_id,
                days=(look_ahead_end - local_today()).days + 3
            )

            today = local_today()

            for imp_date in upcoming_dates:
                try:
                    imp_date_obj = date(today.year, imp_date.month, imp_date.day)
                    if imp_date_obj < today:
                        imp_date_obj = date(today.year + 1, imp_date.month, imp_date.day)
                except ValueError:
                    continue

                if look_ahead_start <= imp_date_obj <= look_ahead_end:
                    days_until = (imp_date_obj - today).days

                    if days_until <= 0:
                        suggestion = "今天记得送祝福"
                    elif days_until <= 3:
                        suggestion = "建议今天寄出礼物"
                    else:
                        suggestion = f"还有{days_until}天，提前准备"

                    date_reminders.append({
                        "title": imp_date.title,
                        "date": imp_date_obj,
                        "days_until": days_until,
                        "suggestion": suggestion,
                        "date_type": imp_date.date_type,
                    })

        except Exception as e:
            logger.warning(f"Failed to find important dates during trip: {e}")

        return date_reminders[:3]

    async def get_quick_context(
        self,
        user_id: UUID,
        destination: str,
    ) -> Optional[str]:
        """
        Get a quick context string for a destination without full planning.

        This is used for real-time conversation context injection.
        """
        memories = await self._gather_destination_memories(user_id, destination)

        if not memories:
            return None

        people: set = set()
        plans: List[str] = []

        for mem in memories[:5]:
            entities = mem.entities or {}
            if entities.get("person"):
                people.add(entities["person"])
            from ...memory.models import MemoryType
            if mem.memory_type in [MemoryType.PLAN.value, MemoryType.SCHEDULE.value]:
                plans.append(mem.summary)

        parts: List[str] = []
        if people:
            parts.append(f"您之前提到在{destination}要见的人: {', '.join(people)}")
        if plans:
            parts.append(f"相关计划: {'; '.join(plans[:3])}")

        return "\n".join(parts) if parts else None
