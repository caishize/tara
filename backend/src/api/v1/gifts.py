"""
Gift recommendation API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, UUID4
from typing import List, Optional
from datetime import date
from uuid import UUID

from ...db.session import get_db
from ...core.auth import get_current_user, get_current_family, verify_member_belongs_to_family
from ...modules.gift.recommendation_service import RecommendationService
from ...modules.gift.history_service import HistoryService
from ...core.llm import OpenAIAdapter
from ...core.auth.encryption_service import EncryptionService
from ...config.settings import settings

router = APIRouter(prefix="/gifts", tags=["gifts"])


# Request/Response Models
class GenerateRecommendationRequest(BaseModel):
    member_id: UUID4  # Changed from recipient_member_id to match frontend
    occasion: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    preferences: Optional[List[str]] = None  # Changed from user_preferences string to list
    exclude_categories: Optional[List[str]] = None  # Added
    urgency: Optional[str] = None  # Added
    related_date_id: Optional[UUID4] = None


class SelectOptionRequest(BaseModel):
    option_index: int


class RecordGiftRequest(BaseModel):
    member_id: UUID4  # Changed from recipient_member_id
    gift_name: str
    category: str  # Changed from gift_category
    occasion: str
    date_given: str  # Changed from occasion_date, frontend sends ISO string
    price: Optional[float] = None  # Changed from gift_price
    purchase_url: Optional[str] = None  # Added
    image_url: Optional[str] = None  # Added
    notes: Optional[str] = None


class AddFeedbackRequest(BaseModel):
    feedback_rating: str  # love_it, like_it, neutral, dislike, hate_it
    feedback_text: Optional[str] = None


# Endpoints

@router.post("/recommendations", status_code=status.HTTP_201_CREATED)
async def generate_recommendation(
    request: GenerateRecommendationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Generate gift recommendation for a member."""
    await verify_member_belongs_to_family(request.member_id, family_id, db)

    llm = OpenAIAdapter(settings.openai_api_key)
    encryption = EncryptionService()

    service = RecommendationService(db, llm, encryption)

    # Convert preferences list to string for backend service
    user_preferences = ', '.join(request.preferences) if request.preferences else None

    recommendation = await service.generate_recommendation(
        family_id=family_id,
        requester_user_id=user_id,
        recipient_member_id=request.member_id,
        occasion=request.occasion,
        budget_min=request.budget_min,
        budget_max=request.budget_max,
        user_preferences=user_preferences,
        related_date_id=request.related_date_id
    )

    return recommendation


@router.get("/recommendations")
async def list_recommendations(
    status: Optional[str] = None,
    member_id: Optional[UUID] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """List gift recommendations, optionally filtered by member."""

    llm = OpenAIAdapter(settings.openai_api_key)
    encryption = EncryptionService()

    service = RecommendationService(db, llm, encryption)

    recommendations = await service.list_recommendations(family_id, status, member_id, limit, offset)
    return {"recommendations": recommendations, "total": len(recommendations)}


@router.get("/recommendations/{recommendation_id}")
async def get_recommendation(
    recommendation_id: UUID4,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get a specific recommendation."""
    llm = OpenAIAdapter(settings.openai_api_key)
    encryption = EncryptionService()

    service = RecommendationService(db, llm, encryption)

    recommendation = await service.get_recommendation(recommendation_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return recommendation


@router.post("/recommendations/{recommendation_id}/view")
async def mark_viewed(
    recommendation_id: UUID4,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Mark recommendation as viewed."""
    llm = OpenAIAdapter(settings.openai_api_key)
    encryption = EncryptionService()

    service = RecommendationService(db, llm, encryption)

    recommendation = await service.mark_viewed(recommendation_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return recommendation


@router.post("/recommendations/{recommendation_id}/select")
async def select_option(
    recommendation_id: UUID4,
    request: SelectOptionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Select a gift option from recommendations."""
    llm = OpenAIAdapter(settings.openai_api_key)
    encryption = EncryptionService()

    service = RecommendationService(db, llm, encryption)

    recommendation = await service.select_option(recommendation_id, request.option_index)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return recommendation


@router.post("/history", status_code=status.HTTP_201_CREATED)
async def record_gift(
    request: RecordGiftRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Record a gift in history."""
    await verify_member_belongs_to_family(request.member_id, family_id, db)

    encryption = EncryptionService()

    service = HistoryService(db, encryption)

    # Parse date string to date object
    from datetime import datetime
    occasion_date = datetime.fromisoformat(request.date_given.replace('Z', '+00:00')).date()

    history = await service.record_gift(
        family_id=family_id,
        giver_user_id=user_id,
        recipient_member_id=request.member_id,
        gift_name=request.gift_name,
        gift_category=request.category,
        occasion=request.occasion,
        occasion_date=occasion_date,
        gift_price=request.price,
        gift_description=None,  # Not sent by frontend
        notes=request.notes
    )

    return history


@router.get("/history")
async def list_history(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """List all gift history for the family."""

    encryption = EncryptionService()

    service = HistoryService(db, encryption)

    histories = await service.list_history(family_id, limit, offset)
    return histories  # Return list directly to match frontend expectations


@router.get("/history/record/{history_id}")
async def get_history_record(
    history_id: UUID4,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get a specific gift history record by history ID."""

    encryption = EncryptionService()

    service = HistoryService(db, encryption)

    history = await service.get_history(history_id, family_id)
    if not history:
        raise HTTPException(status_code=404, detail="Gift history not found")

    return history


@router.get("/history/{member_id}")
async def get_member_history(
    member_id: UUID4,
    years_back: int = 3,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get gift history for a specific member (frontend expects this path)."""

    encryption = EncryptionService()

    service = HistoryService(db, encryption)

    # Get histories for this specific member
    histories = await service.get_recipient_history(member_id, family_id, years_back)
    return histories  # Return list directly to match frontend expectations


@router.post("/history/{history_id}/feedback")
async def add_feedback(
    history_id: UUID4,
    request: AddFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Add feedback to a gift history record."""

    encryption = EncryptionService()

    service = HistoryService(db, encryption)

    history = await service.add_feedback(
        history_id,
        family_id,
        request.feedback_rating,
        request.feedback_text
    )

    if not history:
        raise HTTPException(status_code=404, detail="Gift history not found")

    return history
