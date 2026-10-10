"""
Gift memory and context API endpoints.

Handles gift memory retrieval, context extraction, deduplication,
and special notes for members.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

from ...db.session import get_db
from ...core.auth import get_current_user, get_current_family
from ...modules.gift.memory_service import GiftMemoryService

router = APIRouter(prefix="/gifts", tags=["gifts"])


# Request Models

class AddContextRequest(BaseModel):
    """Request model for adding conversation context."""
    member_id: str
    context_type: str  # preference, dislike, constraint, etc.
    value: str
    categories: Optional[List[str]] = None


class ExtractContextRequest(BaseModel):
    """Request model for extracting context from text."""
    member_id: Optional[str] = None
    text: str


# Endpoints

@router.get("/memory/{member_id}")
async def get_member_memory(
    member_id: str,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """
    Get comprehensive gift memory for a member.

    Returns aggregated data including:
    - Gift history summary
    - Preference scores
    - Conversation insights
    - Gifts to avoid (for deduplication)
    """

    service = GiftMemoryService(db)

    # Refresh and return the memory
    memory = await service.refresh_member_memory(UUID(member_id), family_id)

    return {
        "member_id": str(member_id),
        "memory_richness": memory.memory_richness_score,
        "gift_stats": {
            "total_received": memory.total_gifts_received,
            "last_year": memory.gifts_last_year,
            "last_3_years": memory.gifts_last_3_years,
            "category_distribution": memory.category_counts or {},
        },
        "recent_gifts": memory.recent_gifts or [],
        "gifts_to_avoid": memory.gifts_to_avoid or [],
        "preferences": {
            "liked": memory.liked_categories or [],
            "disliked": memory.disliked_categories or [],
            "scores": memory.preference_scores or {},
            "brands": memory.brand_preferences or {},
        },
        "conversation_insights": memory.conversation_insights or {},
        "interest_keywords": memory.interest_keywords or [],
        "relationship": {
            "type": memory.relationship_type,
            "intimacy_level": memory.intimacy_level,
        },
        "special_notes": memory.special_notes,
        "recommendation_stats": {
            "total": memory.total_recommendations,
            "accepted": memory.accepted_recommendations,
            "acceptance_rate": memory.acceptance_rate,
        },
        "last_gift_date": memory.last_gift_date.isoformat() if memory.last_gift_date else None,
    }


@router.get("/memory/{member_id}/context")
async def get_recommendation_context(
    member_id: str,
    occasion: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """
    Get full recommendation context for generating personalized recommendations.

    This is the data that will be fed to the LLM for recommendation generation.
    """

    service = GiftMemoryService(db)

    context = await service.get_recommendation_context(UUID(member_id), family_id, occasion)

    return context


@router.post("/memory/context")
async def add_context(
    request: AddContextRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    Manually add a context entry for a member.

    Context types:
    - preference: 用户偏好 ("她喜欢护肤品")
    - dislike: 不喜欢 ("他不喜欢电子产品")
    - constraint: 约束条件 ("预算500以内")
    - brand_preference: 品牌偏好 ("她喜欢迪奥")
    - special_note: 特殊备注 ("对花粉过敏")
    """

    service = GiftMemoryService(db)

    context = await service.add_manual_context(
        family_id=family_id,
        user_id=user_id,
        member_id=request.member_id,
        context_type=request.context_type,
        value=request.value,
        categories=request.categories
    )

    await db.commit()

    return {
        "id": str(context.id),
        "context_type": context.context_type,
        "value": context.extracted_value,
        "categories": context.affected_categories,
        "created_at": context.created_at.isoformat() if context.created_at else None,
    }


@router.post("/memory/extract")
async def extract_context_from_text(
    request: ExtractContextRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    Extract gift-related context from conversation text.

    Automatically identifies:
    - Preferences ("她喜欢...")
    - Dislikes ("她不喜欢...")
    - Constraints ("预算...")
    - History mentions ("上次送的...")
    - Feedback ("她说那个...")
    """

    service = GiftMemoryService(db)

    contexts = await service.extract_and_store_context(
        family_id=family_id,
        user_id=user_id,
        member_id=request.member_id,
        text=request.text
    )

    await db.commit()

    return {
        "extracted_count": len(contexts),
        "contexts": [
            {
                "id": str(ctx.id),
                "type": ctx.context_type,
                "raw_text": ctx.raw_text,
                "extracted_value": ctx.extracted_value,
                "categories": ctx.affected_categories,
                "sentiment": ctx.sentiment,
                "confidence": ctx.confidence,
            }
            for ctx in contexts
        ]
    }


@router.get("/memory/{member_id}/dedup")
async def get_dedup_context(
    member_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    Get deduplication context for a member.

    Returns information about:
    - Gifts to avoid (recently given or negatively received)
    - Category frequencies (to avoid over-gifting in one category)
    - Last recommended items
    """
    service = GiftMemoryService(db)

    dedup = await service.get_dedup_context(UUID(member_id))

    return dedup


@router.post("/memory/{member_id}/notes")
async def add_special_note(
    member_id: str,
    note: str,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """
    Add a special note about a member for gift recommendations.

    Examples:
    - "对花粉过敏，不要送花"
    - "素食主义者"
    - "正在减肥，避免送食品"
    """

    service = GiftMemoryService(db)

    member_uuid = UUID(member_id)

    # Get or create memory
    memory = await service.memory_repo.get_or_create(member_uuid, family_id)

    # Add note
    await service.memory_repo.add_special_note(member_uuid, note)

    await db.commit()

    return {"status": "success", "note": note}


# Smart Date Selection & Budget Suggestion

@router.get("/smart-dates/{member_id}")
async def get_smart_dates(
    member_id: str,
    days_ahead: int = 90,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """
    Get smart date suggestions for a member.

    Combines:
    - Member's important dates (birthday, anniversary, etc.)
    - Natural holidays (Spring Festival, Mother's Day, etc.)
    - A general recommendation option

    Returns dates sorted by proximity, with the nearest date marked as default.
    """
    from ...modules.gift.smart_date_service import SmartDateService

    service = SmartDateService(db)
    result = await service.get_smart_dates_for_member(
        member_id=UUID(member_id),
        family_id=family_id,
        days_ahead=days_ahead
    )

    return result


@router.get("/budget-suggestion/{member_id}")
async def get_budget_suggestion(
    member_id: str,
    occasion: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """
    Get intelligent budget suggestion for a member.

    Calculates based on:
    - Historical gift amounts for this member
    - Relationship type (spouse > parent > friend)
    - Intimacy level (1-10)
    - Occasion importance (wedding > birthday > thank you)

    Returns suggested budget with min/max range and explanation factors.
    """
    from ...modules.gift.budget_suggestion_service import BudgetSuggestionService

    service = BudgetSuggestionService(db)
    result = await service.calculate_suggested_budget(
        member_id=UUID(member_id),
        family_id=family_id,
        occasion=occasion
    )

    return result.to_dict()
