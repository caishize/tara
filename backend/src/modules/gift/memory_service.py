"""
GiftMemoryService - Core service for managing gift memory and context.

This service acts as the central hub for:
1. Aggregating gift history into member memory
2. Extracting and storing conversation contexts
3. Building comprehensive context for recommendations
4. Providing deduplication data
"""
from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, timedelta
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from .models import GiftHistory, GiftPreference, GiftConversationContext, MemberGiftMemory
from .recommendation_service import HistoryRepository, PreferenceRepository
from .repositories import ConversationContextRepository, MemoryRepository
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class GiftMemoryService:
    """
    Service for managing gift-related memory and context.

    Provides a unified interface for:
    - Building and maintaining member gift memory
    - Extracting preferences from conversations
    - Providing context for recommendations
    - Deduplication support
    """

    # Context type mappings for extraction
    CONTEXT_PATTERNS = {
        "preference": [
            r"(她|他|TA)喜欢(.+)",
            r"(她|他|TA)爱(.+)",
            r"(她|他|TA)想要(.+)",
            r"(她|他|TA)最近在看(.+)",
            r"送(她|他|TA)(.+)应该不错",
        ],
        "dislike": [
            r"(她|他|TA)不喜欢(.+)",
            r"(她|他|TA)讨厌(.+)",
            r"不要送(.+)",
            r"别送(.+)",
            r"(她|他|TA)对(.+)过敏",
        ],
        "constraint": [
            r"预算(.+)",
            r"不超过(.+)块",
            r"(.+)以内",
            r"最多(.+)元",
        ],
        "history_mention": [
            r"上次送(的|了)(.+)",
            r"去年送(的|了)(.+)",
            r"之前送过(.+)",
            r"(她|他|TA)已经有(.+)了",
        ],
        "feedback": [
            r"(她|他|TA)说(.+)不太实用",
            r"(她|他|TA)很喜欢(.+)",
            r"(她|他|TA)觉得(.+)很好",
            r"那个(.+)不太合适",
        ],
        "brand_preference": [
            r"(她|他|TA)喜欢(.+)牌子",
            r"(她|他|TA)只用(.+)",
            r"(她|他|TA)是(.+)的粉丝",
        ],
    }

    # Category keywords mapping
    CATEGORY_KEYWORDS = {
        "electronics": ["电子", "数码", "手机", "电脑", "平板", "耳机", "音响", "相机"],
        "fashion": ["衣服", "服装", "包包", "鞋子", "围巾", "帽子", "皮带"],
        "cosmetics": ["化妆品", "护肤品", "口红", "香水", "面膜", "精华", "美妆"],
        "jewelry": ["首饰", "珠宝", "项链", "戒指", "手链", "耳环", "手表"],
        "health": ["健康", "养生", "保健品", "按摩", "运动", "健身"],
        "books": ["书", "书籍", "阅读", "小说", "杂志"],
        "toys": ["玩具", "游戏", "乐高", "手办", "模型"],
        "sports": ["运动", "健身", "球", "跑步", "瑜伽"],
        "home": ["家居", "装饰", "厨具", "餐具", "床品"],
        "food": ["食品", "美食", "零食", "巧克力", "糕点", "酒"],
        "experience": ["体验", "旅游", "SPA", "按摩", "课程", "演出", "门票"],
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.history_repo = HistoryRepository(session)
        self.preference_repo = PreferenceRepository(session)
        self.context_repo = ConversationContextRepository(session)
        self.memory_repo = MemoryRepository(session)

    async def get_member_memory(
        self,
        member_id: UUID,
        family_id: UUID
    ) -> MemberGiftMemory:
        """Get or create the gift memory for a member."""
        return await self.memory_repo.get_or_create(member_id, family_id)

    async def refresh_member_memory(
        self,
        member_id: UUID,
        family_id: UUID
    ) -> MemberGiftMemory:
        """
        Refresh/rebuild the complete memory for a member.

        This aggregates:
        - Gift history statistics
        - Preference data
        - Conversation contexts
        """
        memory = await self.memory_repo.get_or_create(member_id, family_id)

        # Update gift statistics
        await self._update_gift_stats(memory, member_id)

        # Update preferences
        await self._update_preferences(memory, member_id)

        # Update conversation insights
        await self._update_conversation_insights(memory, member_id)

        # Recalculate richness score
        memory.memory_richness_score = memory.calculate_richness_score()

        await self.session.flush()
        await self.session.refresh(memory)

        return memory

    async def _update_gift_stats(
        self,
        memory: MemberGiftMemory,
        member_id: UUID
    ) -> None:
        """Update gift statistics in memory."""
        now = utc_now()
        one_year_ago = now - timedelta(days=365)
        three_years_ago = now - timedelta(days=365 * 3)

        # Get all history for this member
        all_history = await self.history_repo.get_by_recipient(
            recipient_member_id=member_id,
            years_back=10
        )

        # Calculate stats
        total = len(all_history)
        last_year = sum(1 for h in all_history if h.occasion_date and h.occasion_date >= one_year_ago.date())
        last_3_years = sum(1 for h in all_history if h.occasion_date and h.occasion_date >= three_years_ago.date())

        # Recent gifts (last 10)
        sorted_history = sorted(all_history, key=lambda x: x.occasion_date or datetime.min.date(), reverse=True)
        recent_gifts = []
        for h in sorted_history[:10]:
            recent_gifts.append({
                "name": h.gift_name,
                "category": h.gift_category,
                "date": h.occasion_date.isoformat() if h.occasion_date else None,
                "feedback": h.feedback_rating,
                "occasion": h.occasion,
            })

        # Category counts
        category_counts = {}
        for h in all_history:
            cat = h.gift_category
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # Gifts to avoid (recent or negatively reviewed)
        gifts_to_avoid = []
        for h in sorted_history[:20]:
            # Recently given (within 1 year) - avoid repeating
            if h.occasion_date and h.occasion_date >= one_year_ago.date():
                gifts_to_avoid.append({
                    "name": h.gift_name,
                    "category": h.gift_category,
                    "reason": "recently_given",
                    "until": (datetime.combine(h.occasion_date, datetime.min.time()) + timedelta(days=365)).isoformat()
                })
            # Negative feedback
            if h.feedback_rating in ["dislike", "hate_it"]:
                gifts_to_avoid.append({
                    "name": h.gift_name,
                    "category": h.gift_category,
                    "reason": "negative_feedback",
                    "until": None  # Permanent
                })

        # Update memory
        memory.total_gifts_received = total
        memory.gifts_last_year = last_year
        memory.gifts_last_3_years = last_3_years
        memory.recent_gifts = recent_gifts
        memory.category_counts = category_counts
        memory.gifts_to_avoid = gifts_to_avoid

        if sorted_history:
            memory.last_gift_date = datetime.combine(
                sorted_history[0].occasion_date,
                datetime.min.time()
            ) if sorted_history[0].occasion_date else None

        # Build occasions history
        occasions_history = {}
        for h in all_history:
            occasion = h.occasion or "other"
            if occasion not in occasions_history:
                occasions_history[occasion] = {
                    "count": 0,
                    "last": None,
                    "typical_gifts": []
                }
            occasions_history[occasion]["count"] += 1
            if h.occasion_date:
                current_last = occasions_history[occasion]["last"]
                if not current_last or h.occasion_date.isoformat() > current_last:
                    occasions_history[occasion]["last"] = h.occasion_date.isoformat()
            if h.gift_category not in occasions_history[occasion]["typical_gifts"]:
                occasions_history[occasion]["typical_gifts"].append(h.gift_category)

        memory.occasions_history = occasions_history

    async def _update_preferences(
        self,
        memory: MemberGiftMemory,
        member_id: UUID
    ) -> None:
        """Update preference data in memory."""
        # Get top preferences
        top_prefs = await self.preference_repo.get_top_preferences(
            member_id=member_id,
            min_confidence=0.3,
            limit=10
        )

        # Get excluded (disliked) categories
        excluded = await self.preference_repo.get_excluded_categories(
            member_id=member_id,
            threshold=-0.2
        )

        # Build preference scores dict
        preference_scores = {}
        liked = []
        disliked = []

        for pref in top_prefs:
            preference_scores[pref.gift_category] = pref.preference_score
            if pref.preference_score > 0.2:
                liked.append(pref.gift_category)

        for cat in excluded:
            if cat not in preference_scores:
                preference_scores[cat] = -0.5  # Default negative
            disliked.append(cat)

        memory.liked_categories = liked
        memory.disliked_categories = disliked
        memory.preference_scores = preference_scores

    async def _update_conversation_insights(
        self,
        memory: MemberGiftMemory,
        member_id: UUID
    ) -> None:
        """Update conversation insights in memory."""
        # Get recent contexts
        contexts = await self.context_repo.get_by_member(
            member_id=member_id,
            active_only=True,
            limit=50
        )

        if not contexts:
            return

        # Aggregate insights
        recent_mentions = []
        explicit_preferences = []
        constraints = []
        keywords = set()

        for ctx in contexts:
            if ctx.context_type == "preference":
                explicit_preferences.append(ctx.extracted_value or ctx.raw_text)
            elif ctx.context_type == "dislike":
                explicit_preferences.append(f"不喜欢: {ctx.extracted_value or ctx.raw_text}")
            elif ctx.context_type == "constraint":
                constraints.append(ctx.extracted_value or ctx.raw_text)
            elif ctx.context_type in ["category_interest", "gift_idea"]:
                recent_mentions.append(ctx.raw_text)

            # Extract keywords
            if ctx.affected_categories:
                keywords.update(ctx.affected_categories)

        # Update memory
        memory.conversation_insights = {
            "recent_mentions": recent_mentions[:10],
            "explicit_preferences": explicit_preferences[:10],
            "constraints": constraints[:5],
        }
        memory.interest_keywords = list(keywords)[:20]
        memory.last_conversation_update = utc_now()

    async def extract_and_store_context(
        self,
        family_id: UUID,
        user_id: UUID,
        member_id: Optional[UUID],
        text: str,
        source: str = "conversation"
    ) -> List[GiftConversationContext]:
        """
        Extract gift-related context from text and store it.

        Args:
            family_id: Family ID
            user_id: User who mentioned this
            member_id: Member this context is about (if known)
            text: The conversation text to analyze
            source: Source of the context

        Returns:
            List of created conversation contexts
        """
        created_contexts = []

        # Try each pattern type
        for context_type, patterns in self.CONTEXT_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    # Extract the relevant part
                    for match in matches:
                        extracted = match[-1] if isinstance(match, tuple) else match

                        # Identify affected categories
                        affected_cats = self._identify_categories(extracted)

                        # Determine sentiment
                        sentiment = "positive"
                        if context_type == "dislike":
                            sentiment = "negative"
                        elif context_type == "constraint":
                            sentiment = "neutral"

                        # Create context
                        context = GiftConversationContext(
                            family_id=family_id,
                            user_id=user_id,
                            member_id=member_id,
                            context_type=context_type,
                            raw_text=text,
                            extracted_value=extracted,
                            affected_categories=affected_cats if affected_cats else None,
                            sentiment=sentiment,
                            confidence=0.8,
                            source=source,
                            mentioned_at=utc_now(),
                        )

                        created = await self.context_repo.create(context)
                        created_contexts.append(created)

        return created_contexts

    def _identify_categories(self, text: str) -> List[str]:
        """Identify gift categories mentioned in text."""
        categories = []
        text_lower = text.lower()

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if category not in categories:
                        categories.append(category)
                    break

        return categories

    async def get_recommendation_context(
        self,
        member_id: UUID,
        family_id: UUID,
        occasion: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for generating a recommendation.

        This is the main method called by the recommendation service.
        """
        # Ensure memory is up-to-date
        memory = await self.refresh_member_memory(member_id, family_id)

        # Get additional conversation context
        conversation_contexts = await self.context_repo.get_by_member(
            member_id=member_id,
            active_only=True,
            limit=20
        )

        # Build context dict
        context = {
            "member_id": str(member_id),
            "memory_richness": memory.memory_richness_score,

            # Gift history
            "gift_history": {
                "total_received": memory.total_gifts_received,
                "last_year": memory.gifts_last_year,
                "recent_gifts": memory.recent_gifts or [],
                "category_distribution": memory.category_counts or {},
                "gifts_to_avoid": memory.gifts_to_avoid or [],
            },

            # Preferences
            "preferences": {
                "liked_categories": memory.liked_categories or [],
                "disliked_categories": memory.disliked_categories or [],
                "scores": memory.preference_scores or {},
                "brands": memory.brand_preferences or {},
                "typical_price_range": {
                    "min": memory.typical_price_min,
                    "max": memory.typical_price_max,
                }
            },

            # Conversation insights
            "conversation_insights": memory.conversation_insights or {},
            "interest_keywords": memory.interest_keywords or [],

            # Relationship context
            "relationship": {
                "type": memory.relationship_type,
                "intimacy_level": memory.intimacy_level,
                "special_notes": memory.special_notes,
            },

            # Recommendation history
            "recommendation_history": {
                "total": memory.total_recommendations,
                "acceptance_rate": memory.acceptance_rate,
                "last_recommended": memory.last_recommended_items or [],
            },

            # Occasion-specific data
            "occasion_history": memory.occasions_history.get(occasion, {}) if memory.occasions_history and occasion else {},

            # Raw conversation contexts for additional detail
            "recent_conversations": [
                {
                    "type": ctx.context_type,
                    "text": ctx.raw_text,
                    "extracted": ctx.extracted_value,
                    "confidence": ctx.confidence,
                    "date": ctx.mentioned_at.isoformat() if ctx.mentioned_at else None,
                }
                for ctx in conversation_contexts[:10]
            ],
        }

        return context

    async def record_recommendation_feedback(
        self,
        member_id: UUID,
        recommendation_id: UUID,
        selected: bool,
        selected_item: Optional[Dict] = None
    ) -> None:
        """Record feedback when a recommendation is selected/rejected."""
        memory = await self.memory_repo.get_by_member(member_id)
        if not memory:
            return

        # Update stats
        memory.total_recommendations = (memory.total_recommendations or 0) + 1
        if selected:
            memory.accepted_recommendations = (memory.accepted_recommendations or 0) + 1

        # Update acceptance rate
        if memory.total_recommendations > 0:
            memory.acceptance_rate = memory.accepted_recommendations / memory.total_recommendations

        # Update last recommended items
        if selected_item:
            last_items = memory.last_recommended_items or []
            last_items.insert(0, {
                "name": selected_item.get("name"),
                "category": selected_item.get("category"),
                "date": utc_now().isoformat(),
                "selected": selected,
                "recommendation_id": str(recommendation_id),
            })
            memory.last_recommended_items = last_items[:10]  # Keep last 10

        memory.last_recommendation_date = utc_now()

        await self.session.flush()

    async def add_manual_context(
        self,
        family_id: UUID,
        user_id: UUID,
        member_id: UUID,
        context_type: str,
        value: str,
        categories: Optional[List[str]] = None
    ) -> GiftConversationContext:
        """Manually add a context entry (from UI input)."""
        sentiment = "positive"
        if context_type == "dislike":
            sentiment = "negative"
        elif context_type == "constraint":
            sentiment = "neutral"

        context = GiftConversationContext(
            family_id=family_id,
            user_id=user_id,
            member_id=member_id,
            context_type=context_type,
            raw_text=value,
            extracted_value=value,
            affected_categories=categories,
            sentiment=sentiment,
            confidence=1.0,  # Manual entries have high confidence
            source="manual_input",
            mentioned_at=utc_now(),
        )

        return await self.context_repo.create(context)

    async def get_dedup_context(
        self,
        member_id: UUID,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get deduplication context for recommendation generation."""
        memory = await self.memory_repo.get_by_member(member_id)
        if not memory:
            return {"gifts_to_avoid": [], "recent_categories": {}}

        return {
            "gifts_to_avoid": memory.gifts_to_avoid or [],
            "recent_categories": memory.category_counts or {},
            "last_recommended": memory.last_recommended_items or [],
            "negative_categories": memory.disliked_categories or [],
        }
