"""Relationship health suggestion strategy — decay-based contact reminders (PRD 4.4)."""
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_

from .....config.logging import get_logger
from .....core.utils.timezone import local_today
from ....relationship.algorithms.relationship_decay import RelationshipDecayCalculator
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


def _infer_relation_category(relationship: str, importance: int) -> str:
    """Infer PRD 4.4 relationship category from relationship type and importance."""
    if not relationship:
        if importance >= 8:
            return "工作贵人"
        elif importance >= 5:
            return "重要亲友"
        else:
            return "普通联系人"

    rel_lower = relationship.lower()

    family_keywords = [
        "父", "母", "爸", "妈", "老婆", "老公", "妻", "夫", "儿", "女", "孩子",
        "spouse", "parent", "child", "son", "daughter", "father", "mother",
    ]
    for kw in family_keywords:
        if kw in rel_lower:
            return "核心家人"

    relative_keywords = [
        "爷", "奶", "外公", "外婆", "岳", "公婆", "叔", "伯", "姑", "舅", "姨",
        "表", "堂", "侄", "亲戚", "朋友", "好友", "老友", "同学", "发小",
        "grandparent", "uncle", "aunt", "cousin", "friend",
    ]
    for kw in relative_keywords:
        if kw in rel_lower:
            return "重要亲友"

    work_keywords = [
        "领导", "老板", "上司", "同事", "客户", "合作", "伙伴", "老师", "贵人",
        "mentor", "colleague", "boss", "client", "partner",
    ]
    for kw in work_keywords:
        if kw in rel_lower:
            return "工作贵人"

    if importance >= 7:
        return "工作贵人"
    elif importance >= 4:
        return "重要亲友"
    else:
        return "普通联系人"


class RelationshipStrategy(SuggestionStrategy):
    """Find suggestions based on relationship health (PRD 4.4)."""

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        decay_calculator = RelationshipDecayCalculator()
        today = local_today()

        try:
            from ....memory.models import (
                ConversationMemory,
                MemoryType,
                MemoryStatus,
            )

            person_query = select(ConversationMemory).where(
                and_(
                    ConversationMemory.user_id == user_id,
                    ConversationMemory.memory_type.in_([
                        MemoryType.RELATIONSHIP.value,
                        MemoryType.FAVOR.value,
                    ]),
                    ConversationMemory.status == MemoryStatus.ACTIVE.value,
                )
            ).order_by(ConversationMemory.created_at.desc()).limit(50)

            result = await self.db.execute(person_query)
            memories = result.scalars().all()

            person_data: Dict[str, Dict[str, Any]] = {}
            for mem in memories:
                entities = mem.entities or {}
                person = entities.get("person")
                if not person:
                    continue

                if person not in person_data:
                    relationship = entities.get("relationship", "")
                    relation_category = _infer_relation_category(
                        relationship, mem.importance or 3,
                    )

                    person_data[person] = {
                        "last_contact": mem.created_at.date() if mem.created_at else today,
                        "favor_balance": 0,
                        "importance": mem.importance or 3,
                        "favors": [],
                        "relation_category": relation_category,
                    }

                if mem.created_at:
                    mem_date = mem.created_at.date()
                    if mem_date > person_data[person]["last_contact"]:
                        person_data[person]["last_contact"] = mem_date

                if mem.memory_type == MemoryType.FAVOR.value:
                    favor_direction = entities.get("favor_direction", "")
                    if favor_direction == "received":
                        person_data[person]["favor_balance"] += 1
                    elif favor_direction == "given":
                        person_data[person]["favor_balance"] -= 1

            for person, data in person_data.items():
                last_contact = data["last_contact"]
                favor_balance = data["favor_balance"]
                importance = data["importance"]

                health_percent = decay_calculator.calculate_health_percentage(
                    importance_level=importance,
                    last_interaction_date=last_contact,
                    favor_balance=favor_balance,
                )

                health_bar = decay_calculator.get_health_bar(health_percent)

                if health_percent < 60 or favor_balance > 2:
                    days_since = (today - last_contact).days

                    if favor_balance > 2:
                        suggestion_hint = "欠人情较多，建议找机会回礼"
                        priority = 75
                        urgency = "high" if favor_balance > 3 else "normal"
                    elif days_since > 90:
                        suggestion_hint = "很久没联系了，可以约一下"
                        priority = 60
                        urgency = "normal"
                    else:
                        suggestion_hint = "可以保持联系"
                        priority = 50
                        urgency = "low"

                    content_lines = [f"关系健康度: {health_bar}"]
                    if days_since > 30:
                        content_lines.append(f"上次联系: {days_since}天前")
                    if favor_balance != 0:
                        balance_str = f"+{favor_balance}" if favor_balance > 0 else str(favor_balance)
                        content_lines.append(f"人情差额: {balance_str}")
                    content_lines.append(f"建议: {suggestion_hint}")

                    relation_category = data.get("relation_category", "")
                    title_with_category = (
                        f"{person}（{relation_category}）" if relation_category else person
                    )

                    suggestions.append(Suggestion(
                        type=SuggestionType.PERSON_CORRELATION,
                        title=title_with_category,
                        content="\n".join(content_lines),
                        icon="person",
                        action_options=["schedule_meeting", "send_message", "prepare_gift", "ignore"],
                        action_data={
                            "person": person,
                            "health_percent": health_percent,
                            "favor_balance": favor_balance,
                            "days_since_contact": days_since,
                        },
                        priority=priority,
                        urgency=urgency,
                    ))

        except ImportError as e:
            logger.debug(f"Memory models not available: {e}")
        except Exception as e:
            logger.error(f"Error finding relationship health suggestions: {e}")

        return suggestions[:5]
