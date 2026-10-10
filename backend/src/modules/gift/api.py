"""Unified gift API router.

Merges endpoints from:
  - api/v1/gifts.py (recommendations, history, memory, popular/trending, saved)
  - api/v1/gift_tasks.py (task CRUD, generate, regenerate)
  - api/v1/gift_dashboard.py (dashboard, stats, member summary)

All endpoints live under /gifts/* prefix.
"""
import logging
import random
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import CurrentUser, get_current_family, get_current_user, verify_member_belongs_to_family
from ...core.auth.encryption_service import EncryptionService
from ...config.settings import settings
from ...db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gifts", tags=["gifts"])


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic request / response schemas (inlined from old schema files)
# ═══════════════════════════════════════════════════════════════════════════════


class GenerateRecommendationRequest(BaseModel):
    member_id: UUID4
    occasion: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    preferences: Optional[List[str]] = None
    exclude_categories: Optional[List[str]] = None
    urgency: Optional[str] = None
    related_date_id: Optional[UUID4] = None


class SelectOptionRequest(BaseModel):
    option_index: int


class RecordGiftRequest(BaseModel):
    member_id: UUID4
    gift_name: str
    category: str
    occasion: str
    date_given: str
    price: Optional[float] = None
    purchase_url: Optional[str] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None


class AddFeedbackRequest(BaseModel):
    feedback_rating: str
    feedback_text: Optional[str] = None


class AddContextRequest(BaseModel):
    member_id: str
    context_type: str
    value: str
    categories: Optional[List[str]] = None


class ExtractContextRequest(BaseModel):
    member_id: Optional[str] = None
    text: str


class GiftTaskCreate(BaseModel):
    important_date_id: Optional[UUID4] = None
    member_id: UUID4
    occasion: str
    occasion_date: date
    occasion_title: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    notes: Optional[str] = None


class GiftTaskUpdate(BaseModel):
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    notes: Optional[str] = None
    occasion_date: Optional[date] = None


class GenerateTaskRecommendationRequest(BaseModel):
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    user_preferences: Optional[str] = None


class RegenerateRecommendationRequest(BaseModel):
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    additional_preferences: Optional[str] = None
    exclude_categories: Optional[List[str]] = None
    exclude_previous: bool = True


# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

# Category mapping: backend ↔ frontend
BACKEND_TO_FRONTEND_CATEGORY: Dict[str, str] = {
    "electronics": "electronics",
    "fashion": "fashion",
    "jewelry": "jewelry",
    "cosmetics": "beauty",
    "health": "other",
    "books": "books",
    "toys": "toys",
    "sports": "sports",
    "home": "home",
    "food": "food",
    "experience": "other",
    "custom": "other",
}

FRONTEND_TO_BACKEND_CATEGORY: Dict[str, Optional[str]] = {
    "electronics": "electronics",
    "fashion": "fashion",
    "beauty": "cosmetics",
    "food": "food",
    "home": "home",
    "sports": "sports",
    "books": "books",
    "toys": "toys",
    "jewelry": "jewelry",
    "other": None,
}

CATEGORY_INTEREST_KEYWORDS: Dict[str, List[str]] = {
    "electronics": ["科技", "数码", "电子", "游戏", "手机", "电脑", "摄影", "智能"],
    "fashion": ["时尚", "穿搭", "服装", "衣服", "潮流", "休闲"],
    "jewelry": ["珠宝", "首饰", "手表", "配饰", "奢侈品"],
    "cosmetics": ["护肤", "美妆", "化妆", "美容", "保养"],
    "health": ["健康", "养生", "保健", "运动", "健身"],
    "books": ["阅读", "书籍", "文学", "学习", "知识"],
    "toys": ["玩具", "动漫", "游戏", "手办", "乐高"],
    "sports": ["运动", "健身", "户外", "跑步", "篮球", "足球"],
    "home": ["家居", "生活", "厨房", "装饰", "收纳"],
    "food": ["美食", "零食", "吃货", "烹饪", "咖啡", "茶"],
}


def _generate_recommendation_reason(gift: dict) -> str:
    """Generate a recommendation reason based on gift attributes."""
    rating = gift.get("rating", 0)
    review_count = gift.get("review_count", 0)
    discount_percent = gift.get("discount_percent", 0)
    brand = gift.get("brand", "")
    category = gift.get("category", "")
    reasons: List[str] = []

    if rating and float(rating) >= 4.8:
        reasons.append("口碑爆款")
    elif rating and float(rating) >= 4.5:
        reasons.append("好评如潮")
    if review_count and review_count >= 10000:
        reasons.append("万人推荐")
    elif review_count and review_count >= 5000:
        reasons.append("热销好物")
    if discount_percent and discount_percent >= 20:
        reasons.append(f"限时{discount_percent}%优惠")
    elif discount_percent and discount_percent >= 10:
        reasons.append("超值特惠")
    premium = ["Apple", "Dyson", "SK-II", "La Mer", "Cartier", "Tiffany", "Chanel", "Dior", "LEGO"]
    if brand and any(pb.lower() in brand.lower() for pb in premium):
        reasons.append("大牌品质")

    category_reasons = {
        "electronics": "科技潮品，实用之选",
        "fashion": "时尚百搭，品味之选",
        "jewelry": "精致闪耀，传递心意",
        "cosmetics": "美丽秘籍，呵护肌肤",
        "beauty": "美丽秘籍，呵护肌肤",
        "health": "关爱健康，贴心之选",
        "books": "精神食粮，知识礼物",
        "toys": "童趣满满，欢乐相伴",
        "sports": "活力生活，运动达人",
        "home": "品质生活，温馨家居",
        "food": "美味佳品，舌尖享受",
    }
    if not reasons:
        reasons.append(category_reasons.get(category, "精选好物，送礼佳品"))
    return "，".join(reasons[:2])


def _calculate_preference_score(
    gift: dict, member_tags: list, member_preferences: dict
) -> float:
    """Calculate preference match score (0-1)."""
    if not member_tags and not member_preferences:
        return 0.5
    score = 0.0
    gift_category = gift.get("category", "")
    gift_name = gift.get("name", "").lower()
    gift_brand = (gift.get("brand") or "").lower()

    for tag in member_tags:
        tag_lower = tag.lower() if isinstance(tag, str) else ""
        for kw in CATEGORY_INTEREST_KEYWORDS.get(gift_category, []):
            if kw in tag_lower or tag_lower in kw:
                score += 0.3
                break
        if tag_lower and (tag_lower in gift_name or tag_lower in gift_brand):
            score += 0.2

    if member_preferences:
        liked = member_preferences.get("liked_categories", [])
        disliked = member_preferences.get("disliked_categories", [])
        if gift_category in liked:
            score += 0.3
        if gift_category in disliked:
            score -= 0.5
        brand_prefs = member_preferences.get("brands", {})
        if gift_brand in [b.lower() for b in brand_prefs.get("liked", [])]:
            score += 0.2
        if gift_brand in [b.lower() for b in brand_prefs.get("disliked", [])]:
            score -= 0.3

    return max(0.0, min(1.0, 0.5 + score))


def _get_llm_provider():
    from ...core.llm import OpenAIAdapter
    return OpenAIAdapter(settings.openai_api_key)


async def _task_to_response(task, session: AsyncSession) -> Dict[str, Any]:
    """Convert a GiftTask model to API response dict."""
    from ...modules.member.repositories.member_repository import MemberRepository
    member_repo = MemberRepository(session)
    member = await member_repo.get_by_id(task.member_id)
    member_name = member.name if member else "Unknown"
    days_until = (task.occasion_date - date.today()).days

    return {
        "id": str(task.id),
        "family_id": str(task.family_id),
        "important_date_id": str(task.important_date_id) if task.important_date_id else None,
        "member_id": str(task.member_id),
        "member_name": member_name,
        "occasion": task.occasion,
        "occasion_date": task.occasion_date.isoformat(),
        "occasion_title": task.occasion_title,
        "days_until": days_until,
        "scheduled_time": task.scheduled_time.isoformat() if task.scheduled_time else None,
        "trigger_source": task.trigger_source,
        "status": task.status,
        "budget_min": task.budget_min,
        "budget_max": task.budget_max,
        "recommendation_id": str(task.recommendation_id) if task.recommendation_id else None,
        "has_recommendation": task.recommendation_id is not None,
        "error_message": task.error_message,
        "retry_count": task.retry_count,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Recommendation endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/recommendations", status_code=status.HTTP_201_CREATED)
async def generate_recommendation(
    request: GenerateRecommendationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Generate gift recommendation for a member."""
    await verify_member_belongs_to_family(request.member_id, family_id, db)
    from .recommendation_service import RecommendationService

    llm = _get_llm_provider()
    encryption = EncryptionService()
    service = RecommendationService(db, llm, encryption)
    user_preferences = ", ".join(request.preferences) if request.preferences else None

    return await service.generate_recommendation(
        family_id=family_id,
        requester_user_id=user_id,
        recipient_member_id=request.member_id,
        occasion=request.occasion,
        budget_min=request.budget_min,
        budget_max=request.budget_max,
        user_preferences=user_preferences,
        related_date_id=request.related_date_id,
    )


@router.get("/recommendations")
async def list_recommendations(
    rec_status: Optional[str] = Query(None, alias="status"),
    member_id: Optional[UUID] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """List gift recommendations."""
    from .recommendation_service import RecommendationService

    llm = _get_llm_provider()
    encryption = EncryptionService()
    service = RecommendationService(db, llm, encryption)
    recs = await service.list_recommendations(family_id, rec_status, member_id, limit, offset)
    return {"recommendations": recs, "total": len(recs)}


@router.get("/recommendations/{recommendation_id}")
async def get_recommendation(recommendation_id: UUID4, db: AsyncSession = Depends(get_db)):
    """Get a specific recommendation."""
    from .recommendation_service import RecommendationService

    llm = _get_llm_provider()
    encryption = EncryptionService()
    service = RecommendationService(db, llm, encryption)
    rec = await service.get_recommendation(recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.post("/recommendations/{recommendation_id}/view")
async def mark_viewed(recommendation_id: UUID4, db: AsyncSession = Depends(get_db)):
    """Mark recommendation as viewed."""
    from .recommendation_service import RecommendationService

    llm = _get_llm_provider()
    encryption = EncryptionService()
    service = RecommendationService(db, llm, encryption)
    rec = await service.mark_viewed(recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.post("/recommendations/{recommendation_id}/select")
async def select_option(
    recommendation_id: UUID4,
    request: SelectOptionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Select a gift option from recommendations."""
    from .recommendation_service import RecommendationService

    llm = _get_llm_provider()
    encryption = EncryptionService()
    service = RecommendationService(db, llm, encryption)
    rec = await service.select_option(recommendation_id, request.option_index)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


# ═══════════════════════════════════════════════════════════════════════════════
# History endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/history", status_code=status.HTTP_201_CREATED)
async def record_gift(
    request: RecordGiftRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Record a gift in history."""
    await verify_member_belongs_to_family(request.member_id, family_id, db)
    from .history_service import HistoryService

    encryption = EncryptionService()
    service = HistoryService(db, encryption)
    occasion_date = datetime.fromisoformat(request.date_given.replace("Z", "+00:00")).date()
    return await service.record_gift(
        family_id=family_id,
        giver_user_id=user_id,
        recipient_member_id=request.member_id,
        gift_name=request.gift_name,
        gift_category=request.category,
        occasion=request.occasion,
        occasion_date=occasion_date,
        gift_price=request.price,
        notes=request.notes,
    )


@router.get("/history")
async def list_history(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """List all gift history for the family."""
    from .history_service import HistoryService

    encryption = EncryptionService()
    service = HistoryService(db, encryption)
    return await service.list_history(family_id, limit, offset)


@router.get("/history/record/{history_id}")
async def get_history_record(
    history_id: UUID4,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get a specific gift history record."""
    from .history_service import HistoryService

    encryption = EncryptionService()
    service = HistoryService(db, encryption)
    h = await service.get_history(history_id, family_id)
    if not h:
        raise HTTPException(status_code=404, detail="Gift history not found")
    return h


@router.get("/history/{member_id}")
async def get_member_history(
    member_id: UUID4,
    years_back: int = 3,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get gift history for a specific member."""
    from .history_service import HistoryService

    encryption = EncryptionService()
    service = HistoryService(db, encryption)
    return await service.get_recipient_history(member_id, family_id, years_back)


@router.post("/history/{history_id}/feedback")
async def add_feedback(
    history_id: UUID4,
    request: AddFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Add feedback to a gift history record."""
    from .history_service import HistoryService

    encryption = EncryptionService()
    service = HistoryService(db, encryption)
    h = await service.add_feedback(history_id, family_id, request.feedback_rating, request.feedback_text)
    if not h:
        raise HTTPException(status_code=404, detail="Gift history not found")
    return h


# ═══════════════════════════════════════════════════════════════════════════════
# Memory & context endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/memory/{member_id}")
async def get_member_memory(
    member_id: str,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get comprehensive gift memory for a member."""
    from .memory_service import GiftMemoryService

    service = GiftMemoryService(db)
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
    """Get full recommendation context for generating personalized recommendations."""
    from .memory_service import GiftMemoryService

    service = GiftMemoryService(db)
    return await service.get_recommendation_context(UUID(member_id), family_id, occasion)


@router.post("/memory/context")
async def add_context(
    request: AddContextRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Manually add a context entry for a member."""
    from .memory_service import GiftMemoryService

    service = GiftMemoryService(db)
    ctx = await service.add_manual_context(
        family_id=family_id,
        user_id=user_id,
        member_id=request.member_id,
        context_type=request.context_type,
        value=request.value,
        categories=request.categories,
    )
    await db.commit()
    return {
        "id": str(ctx.id),
        "context_type": ctx.context_type,
        "value": ctx.extracted_value,
        "categories": ctx.affected_categories,
        "created_at": ctx.created_at.isoformat() if ctx.created_at else None,
    }


@router.post("/memory/extract")
async def extract_context_from_text(
    request: ExtractContextRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Extract gift-related context from conversation text."""
    from .memory_service import GiftMemoryService

    service = GiftMemoryService(db)
    contexts = await service.extract_and_store_context(
        family_id=family_id,
        user_id=user_id,
        member_id=request.member_id,
        text=request.text,
    )
    await db.commit()
    return {
        "extracted_count": len(contexts),
        "contexts": [
            {
                "id": str(c.id),
                "type": c.context_type,
                "raw_text": c.raw_text,
                "extracted_value": c.extracted_value,
                "categories": c.affected_categories,
                "sentiment": c.sentiment,
                "confidence": c.confidence,
            }
            for c in contexts
        ],
    }


@router.get("/memory/{member_id}/dedup")
async def get_dedup_context(member_id: str, db: AsyncSession = Depends(get_db)):
    """Get deduplication context for a member."""
    from .memory_service import GiftMemoryService

    service = GiftMemoryService(db)
    return await service.get_dedup_context(UUID(member_id))


@router.post("/memory/{member_id}/notes")
async def add_special_note(
    member_id: str,
    note: str,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Add a special note about a member for gift recommendations."""
    from .memory_service import GiftMemoryService

    service = GiftMemoryService(db)
    await service.memory_repo.get_or_create(UUID(member_id), family_id)
    await service.memory_repo.add_special_note(UUID(member_id), note)
    await db.commit()
    return {"status": "success", "note": note}


# ═══════════════════════════════════════════════════════════════════════════════
# Smart dates & budget suggestion
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/smart-dates/{member_id}")
async def get_smart_dates(
    member_id: str,
    days_ahead: int = 90,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get smart date suggestions for a member."""
    from .smart_date_service import SmartDateService

    service = SmartDateService(db)
    return await service.get_smart_dates_for_member(
        member_id=UUID(member_id), family_id=family_id, days_ahead=days_ahead
    )


@router.get("/budget-suggestion/{member_id}")
async def get_budget_suggestion(
    member_id: str,
    occasion: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get intelligent budget suggestion for a member."""
    from .budget_suggestion_service import BudgetSuggestionService

    service = BudgetSuggestionService(db)
    result = await service.calculate_suggested_budget(
        member_id=UUID(member_id), family_id=family_id, occasion=occasion
    )
    return result.to_dict()
