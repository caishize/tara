"""Family gathering strategy — proactive family togetherness reminders."""
from datetime import timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func

from .....config.logging import get_logger
from .....core.utils.timezone import local_today
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)

# Core family relation keywords
_CORE_FAMILY_KEYWORDS = [
    "父", "母", "爸", "妈", "老婆", "老公", "妻", "夫",
    "儿", "女", "孩子", "spouse", "parent", "child",
    "son", "daughter", "father", "mother",
]

_ELDER_KEYWORDS = [
    "父", "母", "爸", "妈", "爷", "奶", "外公", "外婆",
    "公公", "婆婆", "岳父", "岳母",
    "father", "mother", "grandparent",
]

# Days without contact before triggering family gathering suggestion
_FAMILY_CONTACT_STALE_DAYS = 14
_ELDER_CONTACT_STALE_DAYS = 10


class FamilyGatheringStrategy(SuggestionStrategy):
    """Generate family togetherness suggestions.

    Proactively reminds users to spend time with family, especially:
    - Core family not seen/contacted recently
    - Free weekends that could be family time
    - Elderly parents who need more frequent check-ins
    """

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []

        try:
            from ....member.models.member import Member
            from ....member.models.member_relation import MemberRelation
            from ....memory.models import ConversationMemory

            if not family_id:
                return suggestions

            today = local_today()

            # Load family members with relations
            relation_query = select(
                MemberRelation.to_member_id,
                MemberRelation.relation_type,
            ).where(
                and_(
                    MemberRelation.family_id == family_id,
                    MemberRelation.from_member_id == user_id,
                )
            )
            relation_result = await self.db.execute(relation_query)
            relations = {
                row.to_member_id: str(
                    row.relation_type.value
                    if hasattr(row.relation_type, "value")
                    else row.relation_type
                )
                for row in relation_result
            }

            # For each family member, check last mention in memories
            for member_id, relation_type in relations.items():
                rel_lower = relation_type.lower() if relation_type else ""

                is_core_family = any(kw in rel_lower for kw in _CORE_FAMILY_KEYWORDS)
                is_elder = any(kw in rel_lower for kw in _ELDER_KEYWORDS)

                if not is_core_family:
                    continue

                # Check last memory mention
                last_mention_query = select(
                    func.max(ConversationMemory.created_at)
                ).where(
                    and_(
                        ConversationMemory.user_id == user_id,
                        ConversationMemory.entities["mentioned_members"].astext.contains(
                            str(member_id)
                        ),
                    )
                )
                last_mention_result = await self.db.execute(last_mention_query)
                last_mention = last_mention_result.scalar()

                if last_mention is None:
                    days_since = 999
                else:
                    days_since = (today - last_mention.date()).days

                # Load member name
                member_query = select(Member.name).where(Member.id == member_id)
                member_result = await self.db.execute(member_query)
                member_name = member_result.scalar() or "家人"

                threshold = _ELDER_CONTACT_STALE_DAYS if is_elder else _FAMILY_CONTACT_STALE_DAYS

                if days_since >= threshold:
                    if is_elder:
                        suggestions.append(Suggestion(
                            type=SuggestionType.FAMILY_GATHERING,
                            title=f"给{member_name}打个电话吧",
                            content=f"好久没和{member_name}联系了，TA肯定很想你，打个电话问问最近怎么样。",
                            icon="elderly",
                            related_member_ids=[str(member_id)],
                            action_options=["call_family", "send_message", "set_reminder", "ignore"],
                            priority=80,
                            urgency="normal",
                        ))
                    else:
                        suggestions.append(Suggestion(
                            type=SuggestionType.FAMILY_GATHERING,
                            title=f"找个时间陪陪{member_name}",
                            content=f"好像有一阵子没和{member_name}好好聊聊了，抽空陪陪TA。",
                            icon="family_restroom",
                            related_member_ids=[str(member_id)],
                            action_options=["call_family", "send_message", "set_reminder", "ignore"],
                            priority=70,
                            urgency="normal",
                        ))

            # Cap family suggestions to avoid overwhelming
            suggestions = sorted(suggestions, key=lambda s: s.priority, reverse=True)[:3]

        except Exception as e:
            logger.debug("FamilyGatheringStrategy skipped: %s", e)

        return suggestions
