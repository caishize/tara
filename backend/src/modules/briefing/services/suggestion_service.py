"""SmartSuggestionService — orchestrates strategy-based suggestion generation.

Delegates to individual strategy classes for each suggestion category,
then ranks, deduplicates, and adjusts results.
"""
from collections import defaultdict
from typing import Any, Dict, List, Optional
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now, local_today
from .suggestion_models import Suggestion, SuggestionType, SuggestionAction  # noqa: F401 — re-export
from .strategies.preparation import PreparationStrategy
from .strategies.location import LocationStrategy
from .strategies.person import PersonStrategy
from .strategies.anniversary import AnniversaryStrategy
from .strategies.memory import MemoryStrategy
from .strategies.external_data import ExternalDataStrategy
from .strategies.favor import FavorStrategy
from .strategies.relationship import RelationshipStrategy
from .strategies.gift import GiftStrategy
from .strategies.plan import PlanStrategy
from .strategies.curation import CurationStrategy
from .strategies.weather_care import WeatherCareStrategy
from .strategies.meal_care import MealCareStrategy
from .strategies.rest_care import RestCareStrategy
from .strategies.family_gathering import FamilyGatheringStrategy

logger = get_logger(__name__)

# --- Category budgeting ---
# Maximum suggestions allowed per category in the final output.
CATEGORY_BUDGETS: Dict[str, int] = {
    "care": 2,
    "relationship": 3,
    "preparation": 2,
    "memory": 2,
    "general": 1,
}

# Maps each SuggestionType to a budget category.
_TYPE_TO_CATEGORY: Dict[SuggestionType, str] = {
    SuggestionType.WEATHER_CARE: "care",
    SuggestionType.MEAL_CARE: "care",
    SuggestionType.REST_CARE: "care",
    SuggestionType.SEASONAL_CARE: "care",
    SuggestionType.FAMILY_GATHERING: "relationship",
    SuggestionType.MEETUP_SUGGESTION: "relationship",
    SuggestionType.PERSON_CORRELATION: "relationship",
    SuggestionType.PREPARATION_REMINDER: "preparation",
    SuggestionType.ANNIVERSARY_REMINDER: "preparation",
    SuggestionType.GIFT_REMINDER: "preparation",
    SuggestionType.CURATION: "preparation",
    SuggestionType.MEMORY_CORRELATION: "memory",
    SuggestionType.HISTORY_CORRELATION: "memory",
    SuggestionType.LOCATION_CORRELATION: "memory",
    SuggestionType.TIME_CORRELATION: "general",
    SuggestionType.PLAN_REMINDER: "general",
}


class SmartSuggestionService:
    """Smart suggestion service that analyzes user data and generates
    contextual, actionable suggestions via pluggable strategies.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.strategies = [
            CurationStrategy(db),
            PreparationStrategy(db),
            LocationStrategy(db),
            PersonStrategy(db),
            AnniversaryStrategy(db),
            MemoryStrategy(db),
            ExternalDataStrategy(db),
            FavorStrategy(db),
            RelationshipStrategy(db),
            GiftStrategy(db),
            PlanStrategy(db),
            # Life care strategies (caring mom features)
            WeatherCareStrategy(db),
            MealCareStrategy(db),
            RestCareStrategy(db),
            FamilyGatheringStrategy(db),
        ]

    async def generate_suggestions(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
        limit: int = 10,
    ) -> List[Suggestion]:
        """Generate smart suggestions for a user."""
        suggestions: List[Suggestion] = []

        try:
            for strategy in self.strategies:
                try:
                    results = await strategy.generate(user_id, family_id)
                    suggestions.extend(results)
                except Exception as e:
                    logger.error(
                        f"Strategy {strategy.__class__.__name__} failed: {e}"
                    )

            suggestions = await self._adjust_for_emotional_state(user_id, suggestions)

            if not suggestions:
                suggestions.extend(await self._generate_general_suggestions(user_id, family_id))

            suggestions = self._apply_category_budgets(suggestions)
            suggestions = sorted(suggestions, key=lambda x: x.priority, reverse=True)
            return suggestions[:limit]

        except Exception as e:
            logger.error(f"Error generating suggestions for user {user_id}: {e}")
            return []

    # ------------------------------------------------------------------
    # Post-processing: category budget + person dedup
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_category_budgets(
        suggestions: List[Suggestion],
        max_per_person: int = 2,
    ) -> List[Suggestion]:
        """Enforce per-category budgets and cross-strategy person dedup.

        1. Person-key dedup: if the same person appears in more than
           *max_per_person* suggestions (across all strategies), keep only
           the highest-priority ones for that person.
        2. Category budget: within each category, keep only the top N
           suggestions (sorted by priority desc) where N comes from
           ``CATEGORY_BUDGETS``.

        Returns a new list -- the input is never mutated.
        """
        # --- Step 1: person-key dedup ---
        person_groups: Dict[str, List[Suggestion]] = defaultdict(list)
        no_person: List[Suggestion] = []

        for s in suggestions:
            person = (s.action_data or {}).get("person", "")
            if person and isinstance(person, str) and person.strip():
                person_groups[person.strip()].append(s)
            else:
                no_person.append(s)

        person_deduped: List[Suggestion] = list(no_person)
        for _person, group in person_groups.items():
            if len(group) <= max_per_person:
                person_deduped.extend(group)
            else:
                ranked = sorted(group, key=lambda x: x.priority, reverse=True)
                person_deduped.extend(ranked[:max_per_person])

        # --- Step 2: category budget ---
        cat_groups: Dict[str, List[Suggestion]] = defaultdict(list)
        for s in person_deduped:
            category = _TYPE_TO_CATEGORY.get(s.type, "general")
            cat_groups[category].append(s)

        result: List[Suggestion] = []
        for category, group in cat_groups.items():
            budget = CATEGORY_BUDGETS.get(category, 3)
            ranked = sorted(group, key=lambda x: x.priority, reverse=True)
            result.extend(ranked[:budget])

        dropped = len(suggestions) - len(result)
        if dropped > 0:
            logger.info(
                "Category budget filter: %d suggestions -> %d (dropped %d)",
                len(suggestions),
                len(result),
                dropped,
            )

        return result

    # ------------------------------------------------------------------
    # Suggestion actions
    # ------------------------------------------------------------------

    async def dismiss_suggestion(
        self,
        suggestion_id: str,
        user_id: UUID,
    ) -> bool:
        """Dismiss a suggestion (mark as ignored)."""
        logger.info(f"User {user_id} dismissed suggestion {suggestion_id}")
        return True

    async def execute_suggestion_action(
        self,
        suggestion_id: str,
        action: str,
        user_id: UUID,
        action_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute an action from a suggestion."""
        logger.info(f"User {user_id} executing action '{action}' for suggestion {suggestion_id}")

        action_map = {
            "schedule_meeting": ("请选择会面时间和地点", "open_calendar"),
            "send_message": ("正在打开消息界面", "open_messaging"),
            "prepare_gift": ("正在打开礼物推荐", "open_gift_recommendations"),
            "book_restaurant": ("正在搜索附近餐厅", "open_restaurant_search"),
            "set_reminder": ("提醒已设置", "reminder_set"),
            "view_details": ("正在打开详情", "view_details"),
        }

        if action == "ignore":
            await self.dismiss_suggestion(suggestion_id, user_id)
            return {"success": True, "action": action, "message": "建议已忽略", "next_step": "dismissed"}

        if action in action_map:
            message, next_step = action_map[action]
            return {"success": True, "action": action, "message": message, "next_step": next_step}

        return {"success": False, "action": action, "message": f"未知操作: {action}", "next_step": None}

    # ------------------------------------------------------------------
    # Emotional state adjustment
    # ------------------------------------------------------------------

    async def _adjust_for_emotional_state(
        self,
        user_id: UUID,
        suggestions: List[Suggestion],
    ) -> List[Suggestion]:
        """Adjust suggestion priorities based on user's recent emotional state."""
        try:
            from ...memory.models import ConversationMemory, MemoryType
        except ImportError:
            return suggestions

        try:
            yesterday = utc_now() - timedelta(hours=24)

            emotion_query = select(ConversationMemory).where(
                and_(
                    ConversationMemory.user_id == user_id,
                    ConversationMemory.memory_type == MemoryType.EMOTION.value,
                    ConversationMemory.created_at >= yesterday,
                )
            ).order_by(ConversationMemory.created_at.desc()).limit(5)

            result = await self.db.execute(emotion_query)
            recent_emotions = result.scalars().all()

            if not recent_emotions:
                return suggestions

            negative_keywords = [
                "压力", "焦虑", "烦", "累", "困扰", "担心", "烦躁", "沮丧", "难过", "生气",
            ]
            has_negative_emotion = any(
                any(kw in (m.summary or "") for kw in negative_keywords)
                for m in recent_emotions
            )

            if not has_negative_emotion:
                return suggestions

            logger.info(f"User {user_id} has recent negative emotions, adjusting suggestions")

            adjusted: List[Suggestion] = []
            for suggestion in suggestions:
                if suggestion.type in [
                    SuggestionType.GIFT_REMINDER,
                    SuggestionType.PREPARATION_REMINDER,
                    SuggestionType.MEETUP_SUGGESTION,
                ]:
                    adjusted.append(Suggestion(
                        **{
                            **suggestion.model_dump(),
                            "priority": int(suggestion.priority * 0.8),
                            "urgency": "normal" if suggestion.urgency == "high" else suggestion.urgency,
                        }
                    ))
                else:
                    adjusted.append(suggestion)

            # LLM-generated self-care suggestion
            care_title = "今天放松一下"
            care_content = "最近似乎有些累，今晚可以早点休息，或做些轻松的事情"
            try:
                from ...insight.insight_content_generator import generate_insight_content

                emotion_summaries = ", ".join(
                    (m.summary or "")[:30] for m in recent_emotions[:3]
                )
                care_context = (
                    f"<self_care_context>\n"
                    f"  <recent_emotions>{emotion_summaries}</recent_emotions>\n"
                    f"  <suggestion_type>self_care</suggestion_type>\n"
                    f"</self_care_context>"
                )
                generated = await generate_insight_content(
                    context_xml=care_context,
                    insight_type="self_care",
                    fallback_title=care_title,
                    fallback_content=care_content,
                )
                care_title = generated["title"]
                care_content = generated["content"]
            except Exception:
                pass  # use defaults

            adjusted.append(Suggestion(
                type=SuggestionType.TIME_CORRELATION,
                title=care_title,
                content=care_content,
                icon="spa",
                action_options=["set_reminder", "ignore"],
                action_data={"suggestion_type": "self_care"},
                priority=85,
                urgency="normal",
            ))

            return adjusted

        except Exception as e:
            logger.warning(f"Error adjusting for emotional state: {e}")
            return suggestions

    # ------------------------------------------------------------------
    # General suggestions (fallback)
    # ------------------------------------------------------------------

    async def _generate_general_suggestions(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        """Generate general suggestions when no specific data-driven suggestions exist.

        Uses LLM to generate contextual suggestions based on day-of-week and
        family context, with static fallbacks on failure.
        """
        suggestions: List[Suggestion] = []
        today = local_today()
        weekday = today.weekday()
        day_of_month = today.day

        # Determine suggestion type based on timing
        _WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        day_name = _WEEKDAY_NAMES[weekday]
        is_weekend = weekday in [5, 6]

        # Query family context for richer LLM suggestions
        member_count = 0
        active_trip_count = 0
        if family_id is not None:
            from sqlalchemy import func as sa_func

            try:
                from ...member.models.member import Member

                member_result = await self.db.execute(
                    select(sa_func.count(Member.id)).where(
                        Member.family_id == family_id,
                    )
                )
                member_count = member_result.scalar() or 0
            except Exception:
                pass
            try:
                from ...trip.models.trip_plan import TripPlan

                trip_result = await self.db.execute(
                    select(sa_func.count(TripPlan.trip_id)).where(
                        and_(
                            TripPlan.family_id == family_id,
                            TripPlan.status.in_(["planning", "confirmed", "in_progress"]),
                        )
                    )
                )
                active_trip_count = trip_result.scalar() or 0
            except Exception:
                pass

        # Try LLM-generated fallback
        try:
            from ...insight.insight_content_generator import generate_insight_content

            fallback_context = (
                f"<general_suggestion_context>\n"
                f"  <weekday>{day_name}</weekday>\n"
                f"  <is_weekend>{is_weekend}</is_weekend>\n"
                f"  <day_of_month>{day_of_month}</day_of_month>\n"
                f"  <family_member_count>{member_count}</family_member_count>\n"
                f"  <active_trip_count>{active_trip_count}</active_trip_count>\n"
                f"  <suggestion_purpose>没有具体日程时的温馨提醒</suggestion_purpose>\n"
                f"</general_suggestion_context>"
            )
            generated = await generate_insight_content(
                context_xml=fallback_context,
                insight_type="general_fallback",
                fallback_title="今日小贴士",
                fallback_content="有什么重要的事情或计划？告诉我，我会帮你记住",
            )

            icon = "home" if is_weekend else "event_note"
            priority = 40 if is_weekend else 50

            suggestions.append(Suggestion(
                type=SuggestionType.TIME_CORRELATION,
                title=generated["title"],
                content=generated["content"],
                icon=icon,
                action_options=["view_details", "ignore"],
                action_data={"suggestion_type": "general_llm"},
                priority=priority,
                urgency="low" if is_weekend else "normal",
            ))
        except Exception:
            # Static fallback chain
            if weekday == 0:
                suggestions.append(Suggestion(
                    type=SuggestionType.TIME_CORRELATION,
                    title="新的一周开始",
                    content="整理一下本周的重要事项，提前做好规划",
                    icon="event_note",
                    action_options=["view_details", "ignore"],
                    action_data={"suggestion_type": "weekly_planning"},
                    priority=50,
                    urgency="normal",
                ))
            elif is_weekend:
                suggestions.append(Suggestion(
                    type=SuggestionType.TIME_CORRELATION,
                    title="享受周末时光",
                    content="周末可以多陪陪家人，或者处理一些平时没空做的事",
                    icon="home",
                    action_options=["ignore"],
                    action_data={"suggestion_type": "weekend_reminder"},
                    priority=40,
                    urgency="low",
                ))
            else:
                suggestions.append(Suggestion(
                    type=SuggestionType.HISTORY_CORRELATION,
                    title="记录重要事项",
                    content="有什么重要的事情或计划？告诉我，我会帮你记住",
                    icon="lightbulb",
                    action_options=["ignore"],
                    action_data={"suggestion_type": "onboarding"},
                    priority=30,
                    urgency="low",
                ))

        return suggestions
