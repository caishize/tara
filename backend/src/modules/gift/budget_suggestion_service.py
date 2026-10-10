"""
BudgetSuggestionService - Intelligent budget recommendation for gift giving.

Calculates suggested budget based on:
1. Historical gift amounts for the member
2. Relationship type (spouse, parent, friend, etc.)
3. Intimacy level (1-10)
4. Occasion importance (wedding, birthday, thank you, etc.)
"""
from typing import Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from .repositories import MemoryRepository
from .recommendation_service import HistoryRepository
from ..member.repositories.member_repository import MemberRepository
from ...config.logging import get_logger

logger = get_logger(__name__)


# Budget multipliers by relationship type
RELATIONSHIP_BUDGET_MULTIPLIERS = {
    "spouse": 1.5,
    "partner": 1.5,
    "parent": 1.3,
    "father": 1.3,
    "mother": 1.3,
    "child": 1.2,
    "son": 1.2,
    "daughter": 1.2,
    "sibling": 1.0,
    "brother": 1.0,
    "sister": 1.0,
    "grandparent": 1.1,
    "grandchild": 1.1,
    "friend": 0.8,
    "colleague": 0.6,
    "classmate": 0.7,
    "acquaintance": 0.4,
    "other": 0.7,
}

# Budget multipliers by occasion importance
OCCASION_IMPORTANCE_MULTIPLIERS = {
    "wedding": 2.0,
    "birthday": 1.5,
    "anniversary": 1.5,
    "graduation": 1.3,
    "babyShower": 1.2,
    "housewarming": 1.1,
    "holiday": 1.0,
    "thankyou": 0.8,
    "other": 0.7,
}

# Base budget when no historical data available
DEFAULT_BASE_BUDGET = 300


@dataclass
class BudgetSuggestionResponse:
    """Response model for budget suggestion."""
    suggested_budget: int
    budget_min: int
    budget_max: int
    factors: Dict[str, Any]
    confidence: float  # 0-1, how confident we are in this suggestion

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggested_budget": self.suggested_budget,
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "factors": self.factors,
            "confidence": self.confidence,
        }


class BudgetSuggestionService:
    """Service for intelligent budget suggestions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.memory_repo = MemoryRepository(session)
        self.history_repo = HistoryRepository(session)
        self.member_repo = MemberRepository(session)

    async def calculate_suggested_budget(
        self,
        member_id: UUID,
        family_id: UUID,
        occasion: Optional[str] = None
    ) -> BudgetSuggestionResponse:
        """
        Calculate suggested budget for a gift.

        Args:
            member_id: The recipient member
            family_id: The family context
            occasion: The gift occasion (birthday, anniversary, etc.)

        Returns:
            BudgetSuggestionResponse with calculated budget and explanation
        """
        # 1. Get member's gift memory
        memory = await self.memory_repo.get_or_create(member_id, family_id)

        # 2. Get historical average from memory or calculate from history
        historical_avg = await self._get_historical_average(member_id, memory)

        # 3. Get relationship context
        relationship_type = memory.relationship_type
        if not relationship_type:
            # Try to get from member's relations
            member = await self.member_repo.get_by_id(member_id)
            if member and member.relations_from:
                first_relation = member.relations_from[0]
                relation_val = first_relation.relation_type
                relationship_type = (
                    relation_val.value if hasattr(relation_val, "value") else str(relation_val)
                ).lower()

        # 4. Calculate multipliers
        relationship_mult = self._get_relationship_multiplier(relationship_type)
        intimacy_mult = self._get_intimacy_multiplier(memory.intimacy_level)
        occasion_mult = self._get_occasion_multiplier(occasion)

        # 5. Determine base budget
        if historical_avg > 0:
            base = historical_avg
            confidence_base = 0.5  # Higher confidence with historical data
        else:
            base = DEFAULT_BASE_BUDGET
            confidence_base = 0.3  # Lower confidence without data

        # 6. Apply multipliers
        suggested = base * relationship_mult * intimacy_mult * occasion_mult

        # 7. Round to nearest 50
        suggested_rounded = self._round_to_nearest(suggested, 50)

        # 8. Calculate min/max range
        budget_min = self._round_to_nearest(suggested * 0.5, 50)
        budget_max = self._round_to_nearest(suggested * 1.5, 50)

        # Ensure minimum values
        budget_min = max(50, budget_min)
        suggested_rounded = max(100, suggested_rounded)
        budget_max = max(200, budget_max)

        # 9. Calculate confidence
        confidence = self._calculate_confidence(memory, historical_avg)

        return BudgetSuggestionResponse(
            suggested_budget=suggested_rounded,
            budget_min=budget_min,
            budget_max=budget_max,
            factors={
                "base_budget": round(base, 2),
                "historical_avg": round(historical_avg, 2) if historical_avg > 0 else None,
                "relationship_type": relationship_type or "unknown",
                "relationship_multiplier": relationship_mult,
                "intimacy_level": memory.intimacy_level,
                "intimacy_multiplier": round(intimacy_mult, 2),
                "occasion": occasion,
                "occasion_multiplier": occasion_mult,
                "calculation": f"{base:.0f} x {relationship_mult:.2f} x {intimacy_mult:.2f} x {occasion_mult:.2f} = {suggested:.0f}",
            },
            confidence=confidence,
        )

    async def _get_historical_average(self, member_id: UUID, memory) -> float:
        """Get historical average gift amount for this member."""
        # First try from memory's typical price range
        if memory.typical_price_min and memory.typical_price_max:
            return (memory.typical_price_min + memory.typical_price_max) / 2

        # Otherwise calculate from gift history
        try:
            histories = await self.history_repo.get_by_recipient(member_id, years_back=3)
            if histories:
                prices = [h.gift_price for h in histories if h.gift_price and h.gift_price > 0]
                if prices:
                    return sum(prices) / len(prices)
        except Exception as e:
            logger.warning(f"Failed to get history for budget calculation: {e}")

        return 0.0

    def _get_relationship_multiplier(self, relationship_type: Optional[str]) -> float:
        """Get budget multiplier based on relationship type."""
        if not relationship_type:
            return 1.0

        # Normalize the relationship type
        normalized = relationship_type.lower().replace("_", "").replace("-", "")

        # Direct match
        if normalized in RELATIONSHIP_BUDGET_MULTIPLIERS:
            return RELATIONSHIP_BUDGET_MULTIPLIERS[normalized]

        # Partial match (e.g., "parent_in_law" contains "parent")
        for key, mult in RELATIONSHIP_BUDGET_MULTIPLIERS.items():
            if key in normalized:
                return mult

        return 1.0

    def _get_intimacy_multiplier(self, intimacy_level: Optional[int]) -> float:
        """
        Get budget multiplier based on intimacy level (1-10).

        Mapping:
        - Level 1: 0.84x (lowest)
        - Level 5: 1.0x (neutral)
        - Level 10: 1.2x (highest)
        """
        if intimacy_level is None:
            return 1.0

        # Clamp to valid range
        level = max(1, min(10, intimacy_level))

        # Linear mapping: 1->0.84, 5->1.0, 10->1.2
        return 0.8 + (level * 0.04)

    def _get_occasion_multiplier(self, occasion: Optional[str]) -> float:
        """Get budget multiplier based on occasion importance."""
        if not occasion:
            return 1.0

        return OCCASION_IMPORTANCE_MULTIPLIERS.get(occasion, 1.0)

    def _calculate_confidence(self, memory, historical_avg: float) -> float:
        """
        Calculate confidence score for the budget suggestion.

        Based on:
        - Memory richness score
        - Whether we have historical data
        - Whether we know the relationship type
        """
        confidence = 0.3  # Base confidence

        # Add for memory richness
        if memory.memory_richness_score:
            confidence += memory.memory_richness_score * 0.3

        # Add for historical data
        if historical_avg > 0:
            confidence += 0.2

        # Add for relationship context
        if memory.relationship_type:
            confidence += 0.1

        if memory.intimacy_level:
            confidence += 0.1

        return min(1.0, confidence)

    @staticmethod
    def _round_to_nearest(value: float, nearest: int) -> int:
        """Round value to nearest multiple."""
        return round(value / nearest) * nearest
