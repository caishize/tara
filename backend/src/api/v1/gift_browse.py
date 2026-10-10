"""
Gift browse, save, and popular/trending API endpoints.

Handles saved gifts, popular gift discovery, and preference scoring.
Also provides /trending and /recommend aliases for frontend compatibility.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, UUID4
from typing import List, Optional
from uuid import UUID

from ...db.session import get_db
from ...core.auth import get_current_user, get_current_family

router = APIRouter(prefix="/gifts", tags=["gifts"])


# Category mapping from trending_gifts (backend) to gift entity (frontend)
BACKEND_TO_FRONTEND_CATEGORY = {
    "electronics": "electronics",
    "fashion": "fashion",
    "jewelry": "jewelry",
    "cosmetics": "beauty",      # Map cosmetics -> beauty
    "health": "other",          # Map health -> other
    "books": "books",
    "toys": "toys",
    "sports": "sports",
    "home": "home",
    "food": "food",
    "experience": "other",      # Map experience -> other
    "custom": "other",          # Map custom -> other
}

# Reverse mapping for API queries
FRONTEND_TO_BACKEND_CATEGORY = {
    "electronics": "electronics",
    "fashion": "fashion",
    "beauty": "cosmetics",      # Map beauty -> cosmetics
    "food": "food",
    "home": "home",
    "sports": "sports",
    "books": "books",
    "toys": "toys",
    "jewelry": "jewelry",
    "other": None,              # 'other' needs special handling
}

# Category to interest tag mapping for preference filtering
CATEGORY_INTEREST_KEYWORDS = {
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
    name = gift.get("name", "")
    brand = gift.get("brand", "")
    rating = gift.get("rating", 0)
    review_count = gift.get("review_count", 0)
    discount_percent = gift.get("discount_percent", 0)
    category = gift.get("category", "")

    reasons = []

    # Rating-based reasons
    if rating and float(rating) >= 4.8:
        reasons.append("口碑爆款")
    elif rating and float(rating) >= 4.5:
        reasons.append("好评如潮")

    # Review count based reasons
    if review_count and review_count >= 10000:
        reasons.append("万人推荐")
    elif review_count and review_count >= 5000:
        reasons.append("热销好物")

    # Discount based reasons
    if discount_percent and discount_percent >= 20:
        reasons.append(f"限时{discount_percent}%优惠")
    elif discount_percent and discount_percent >= 10:
        reasons.append("超值特惠")

    # Brand based reasons
    premium_brands = ["Apple", "Dyson", "SK-II", "La Mer", "Cartier", "Tiffany", "Chanel", "Dior", "LEGO"]
    if brand and any(pb.lower() in brand.lower() for pb in premium_brands):
        reasons.append("大牌品质")

    # Category based fallback reasons
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

    return "，".join(reasons[:2])  # Return at most 2 reasons


def _calculate_preference_score(gift: dict, member_tags: list, member_preferences: dict) -> float:
    """
    Calculate a preference score for a gift based on member's interests.

    Returns a score from 0.0 to 1.0 indicating how well the gift matches the member's preferences.
    """
    if not member_tags and not member_preferences:
        return 0.5  # Neutral score if no preference data

    score = 0.0
    gift_category = gift.get("category", "")
    gift_name = gift.get("name", "").lower()
    gift_brand = (gift.get("brand") or "").lower()

    # Check category match with member tags
    category_keywords = CATEGORY_INTEREST_KEYWORDS.get(gift_category, [])
    for tag in member_tags:
        tag_lower = tag.lower() if isinstance(tag, str) else ""
        # Direct category keyword match
        for keyword in category_keywords:
            if keyword in tag_lower or tag_lower in keyword:
                score += 0.3
                break
        # Check if tag appears in gift name or brand
        if tag_lower and (tag_lower in gift_name or tag_lower in gift_brand):
            score += 0.2

    # Check profile preferences if available
    if member_preferences:
        # Check gift category preferences
        liked_categories = member_preferences.get("liked_categories", [])
        disliked_categories = member_preferences.get("disliked_categories", [])

        if gift_category in liked_categories:
            score += 0.3
        if gift_category in disliked_categories:
            score -= 0.5

        # Check brand preferences
        brand_prefs = member_preferences.get("brands", {})
        if gift_brand in [b.lower() for b in brand_prefs.get("liked", [])]:
            score += 0.2
        if gift_brand in [b.lower() for b in brand_prefs.get("disliked", [])]:
            score -= 0.3

    # Normalize to 0-1 range
    return max(0.0, min(1.0, 0.5 + score))


# Endpoints

@router.get("/saved")
async def get_saved_gifts(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """
    Get current user's saved gifts.

    Proxies to /user/saved-gifts endpoint.
    Returns gifts in the format expected by frontend Gift entity.
    """
    from ...modules.gift.trending_service import UserGiftSaveService

    service = UserGiftSaveService(db)
    items, total = await service.get_user_saved_gifts(
        user_id=user_id,
        page=1,
        page_size=100  # Get all saved gifts
    )

    # Transform to match frontend Gift entity format
    result = []
    for item in items:
        gift = item.get("gift", {})
        frontend_category = BACKEND_TO_FRONTEND_CATEGORY.get(
            gift.get("category", "other"),
            "other"
        )
        result.append({
            "id": gift.get("id"),
            "name": gift.get("name"),
            "description": gift.get("description") or _generate_recommendation_reason(gift),
            "image_url": gift.get("image_url"),
            "price": float(gift.get("price", 0)),
            "original_price": float(gift.get("original_price")) if gift.get("original_price") else None,
            "category": frontend_category,
            "brand": gift.get("brand"),
            "rating": float(gift.get("rating", 0)) if gift.get("rating") else 0,
            "review_count": gift.get("review_count", 0),
            "purchase_url": gift.get("product_url"),
            "is_saved": True,
            "created_at": item.get("saved_at"),
        })

    return result


@router.post("/{gift_id}/save", status_code=status.HTTP_201_CREATED)
async def save_gift(
    gift_id: UUID4,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Save a gift to user's collection."""
    from ...modules.gift.trending_service import UserGiftSaveService

    service = UserGiftSaveService(db)

    try:
        result = await service.save_gift(
            user_id=user_id,
            gift_id=gift_id,
            note=None
        )
        await db.commit()
        return {"status": "success", "gift_id": str(gift_id)}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{gift_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_gift(
    gift_id: UUID4,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Remove a gift from user's saved collection."""
    from ...modules.gift.trending_service import UserGiftSaveService

    service = UserGiftSaveService(db)
    success = await service.unsave_gift(user_id=user_id, gift_id=gift_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved gift not found"
        )

    await db.commit()


@router.get("/popular")
async def get_popular_gifts(
    category: Optional[str] = None,
    member_id: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    Get popular/trending gifts.

    This endpoint proxies data from the trending_gifts module.
    Category names are mapped to match frontend expectations.

    If member_id is provided, gifts will be sorted by preference match score.
    """
    from ...modules.gift.trending_service import TrendingGiftService
    from ...modules.member.member_service import MemberService

    service = TrendingGiftService(db)

    # Get member preferences if member_id provided
    member_tags = []
    member_preferences = {}
    if member_id:
        try:
            member_svc = MemberService(db)
            member_info = await member_svc.get_member(member_id, str(family_id))
            if member_info:
                member_tags = member_info.tags or []
                if member_info.preferences:
                    member_preferences = member_info.preferences
                else:
                    profile_info = await member_svc.get_member_profile(member_id, str(family_id))
                    if profile_info and profile_info.preferences:
                        member_preferences = profile_info.preferences
        except Exception:
            pass  # Continue without personalization if error

    # Map frontend category to backend category
    backend_category = None
    if category:
        backend_category = FRONTEND_TO_BACKEND_CATEGORY.get(category, category)

    # Get more gifts if personalization is needed (to ensure we have enough after sorting)
    fetch_limit = limit * 2 if member_id else limit

    if backend_category:
        # Get gifts for specific category
        gifts, total = await service.get_gifts_by_category(
            category=backend_category,
            page=1,
            page_size=fetch_limit,
            sort_by="popularity"
        )
    else:
        # Get a balanced mix from all categories to ensure variety
        # Instead of just sorting by popularity, sample from each category
        import random
        all_categories = list(FRONTEND_TO_BACKEND_CATEGORY.values())
        items_per_category = max(2, fetch_limit // len(all_categories))

        mixed_gifts = []
        for cat in all_categories:
            cat_gifts, _ = await service.get_gifts_by_category(
                category=cat,
                page=1,
                page_size=items_per_category,
                sort_by="popularity"
            )
            mixed_gifts.extend(cat_gifts)

        # Shuffle to mix categories, then sort by popularity within the mix
        random.shuffle(mixed_gifts)
        gifts = mixed_gifts[:fetch_limit]
        total = len(gifts)

    # Transform response to match frontend Gift entity format
    result = []
    for gift in gifts:
        # Map backend category to frontend category
        frontend_category = BACKEND_TO_FRONTEND_CATEGORY.get(
            gift.get("category", "other"),
            "other"
        )

        # Use stored description if available, otherwise generate dynamically
        description = gift.get("description")
        if not description:
            description = _generate_recommendation_reason(gift)

        # Calculate preference score if member_id provided
        preference_score = 0.5
        if member_id:
            preference_score = _calculate_preference_score(gift, member_tags, member_preferences)

        result.append({
            "id": gift.get("id"),
            "name": gift.get("name"),
            "description": description,
            "image_url": gift.get("image_url"),
            "price": float(gift.get("price", 0)),
            "original_price": float(gift.get("original_price")) if gift.get("original_price") else None,
            "category": frontend_category,
            "brand": gift.get("brand"),
            "rating": float(gift.get("rating", 0)) if gift.get("rating") else 0,
            "review_count": gift.get("review_count", 0),
            "purchase_url": gift.get("product_url"),
            "is_saved": gift.get("is_saved", False),
            "created_at": gift.get("updated_at"),
            "_preference_score": preference_score,  # Internal field for sorting
        })

    # Sort by preference score if member_id provided
    if member_id:
        result.sort(key=lambda x: (-x["_preference_score"], -x.get("rating", 0)))

    # Remove internal preference score field and limit results
    for item in result:
        item.pop("_preference_score", None)

    return result[:limit]


# ── Frontend-compatible aliases ──────────────────────────────────────────────


@router.get("/trending")
async def get_trending_gifts(
    category: Optional[str] = None,
    member_id: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Alias for /popular — frontend calls /gifts/trending."""
    return await get_popular_gifts(
        category=category,
        member_id=member_id,
        limit=limit,
        db=db,
        user_id=user_id,
        family_id=family_id,
    )


class RecommendRequest(BaseModel):
    member_id: UUID4
    occasion: str
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    urgency: Optional[str] = None


@router.post("/recommend", status_code=status.HTTP_201_CREATED)
async def generate_recommendation_alias(
    request: RecommendRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Alias for POST /gifts/recommendations — frontend calls POST /gifts/recommend."""
    from ...core.auth import verify_member_belongs_to_family
    from ...modules.gift.recommendation_service import RecommendationService
    from ...core.llm import OpenAIAdapter
    from ...core.auth.encryption_service import EncryptionService
    from ...config.settings import settings

    await verify_member_belongs_to_family(request.member_id, family_id, db)

    llm = OpenAIAdapter(settings.openai_api_key)
    encryption = EncryptionService()
    service = RecommendationService(db, llm, encryption)

    return await service.generate_recommendation(
        family_id=family_id,
        requester_user_id=user_id,
        recipient_member_id=request.member_id,
        occasion=request.occasion,
        budget_min=request.budget_min,
        budget_max=request.budget_max,
    )


@router.get("/recommend")
async def list_recommendations_alias(
    rec_status: Optional[str] = Query(None, alias="status"),
    member_id: Optional[UUID] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Alias for GET /gifts/recommendations — frontend calls GET /gifts/recommend."""
    from ...modules.gift.models_enums import RecommendStatus
    from ...modules.gift.recommendation_service import RecommendationService
    from ...core.llm import OpenAIAdapter
    from ...core.auth.encryption_service import EncryptionService
    from ...config.settings import settings

    if rec_status:
        valid_statuses = {s.value for s in RecommendStatus}
        if rec_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}",
            )

    llm = OpenAIAdapter(settings.openai_api_key)
    encryption = EncryptionService()
    service = RecommendationService(db, llm, encryption)

    recs = await service.list_recommendations(family_id, rec_status, member_id, limit, offset)
    return {"recommendations": recs, "total": len(recs)}
