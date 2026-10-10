"""Gift trending, saved gifts, and dashboard API endpoints.

Split from api.py for file size management.
Popular/trending gifts, user saved gifts, and dashboard endpoints.
"""
import logging
import random
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import get_current_family, get_current_user
from ...db.session import get_db
from .api import (
    BACKEND_TO_FRONTEND_CATEGORY,
    FRONTEND_TO_BACKEND_CATEGORY,
    CATEGORY_INTEREST_KEYWORDS,
    _generate_recommendation_reason,
    _calculate_preference_score,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gifts", tags=["gifts"])


# ═══════════════════════════════════════════════════════════════════════════════
# Popular / trending gifts
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/popular")
async def get_popular_gifts(
    category: Optional[str] = None,
    member_id: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get popular/trending gifts, optionally personalised for a member."""
    from .trending_service import TrendingGiftService

    service = TrendingGiftService(db)
    member_tags: list = []
    member_preferences: dict = {}

    if member_id:
        try:
            from ...modules.member.repositories.member_repository import MemberRepository
            member_repo = MemberRepository(db)
            member = await member_repo.get_by_id(UUID(member_id))
            if member:
                member_tags = member.tags or []
                if member.profile and member.profile.preferences:
                    member_preferences = member.profile.preferences
        except Exception:
            pass

    backend_category = FRONTEND_TO_BACKEND_CATEGORY.get(category, category) if category else None
    fetch_limit = limit * 2 if member_id else limit

    if backend_category:
        gifts, _ = await service.get_gifts_by_category(
            category=backend_category, page=1, page_size=fetch_limit, sort_by="popularity"
        )
    else:
        all_cats = [c for c in FRONTEND_TO_BACKEND_CATEGORY.values() if c]
        items_per = max(2, fetch_limit // len(all_cats))
        mixed: List[Dict[str, Any]] = []
        for cat in all_cats:
            cat_gifts, _ = await service.get_gifts_by_category(
                category=cat, page=1, page_size=items_per, sort_by="popularity"
            )
            mixed.extend(cat_gifts)
        random.shuffle(mixed)
        gifts = mixed[:fetch_limit]

    result = []
    for gift in gifts:
        fe_cat = BACKEND_TO_FRONTEND_CATEGORY.get(gift.get("category", "other"), "other")
        desc = gift.get("description") or _generate_recommendation_reason(gift)
        pref_score = 0.5
        if member_id:
            pref_score = _calculate_preference_score(gift, member_tags, member_preferences)
        result.append({
            "id": gift.get("id"),
            "name": gift.get("name"),
            "description": desc,
            "image_url": gift.get("image_url"),
            "price": float(gift.get("price", 0)),
            "original_price": float(gift["original_price"]) if gift.get("original_price") else None,
            "category": fe_cat,
            "brand": gift.get("brand"),
            "rating": float(gift.get("rating", 0)) if gift.get("rating") else 0,
            "review_count": gift.get("review_count", 0),
            "purchase_url": gift.get("product_url"),
            "is_saved": gift.get("is_saved", False),
            "created_at": gift.get("updated_at"),
            "_pref": pref_score,
        })

    if member_id:
        result.sort(key=lambda x: (-x["_pref"], -x.get("rating", 0)))
    for item in result:
        item.pop("_pref", None)
    return result[:limit]


# ═══════════════════════════════════════════════════════════════════════════════
# User saved gifts
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/saved")
async def get_saved_gifts(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Get current user's saved gifts."""
    from .trending_service import UserGiftSaveService

    service = UserGiftSaveService(db)
    items, _ = await service.get_user_saved_gifts(user_id=user_id, page=1, page_size=100)
    result = []
    for item in items:
        gift = item.get("gift", {})
        fe_cat = BACKEND_TO_FRONTEND_CATEGORY.get(gift.get("category", "other"), "other")
        result.append({
            "id": gift.get("id"),
            "name": gift.get("name"),
            "description": gift.get("description") or _generate_recommendation_reason(gift),
            "image_url": gift.get("image_url"),
            "price": float(gift.get("price", 0)),
            "original_price": float(gift["original_price"]) if gift.get("original_price") else None,
            "category": fe_cat,
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
    from .trending_service import UserGiftSaveService

    service = UserGiftSaveService(db)
    try:
        await service.save_gift(user_id=user_id, gift_id=gift_id)
        await db.commit()
        return {"status": "success", "gift_id": str(gift_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{gift_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_gift(
    gift_id: UUID4,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
):
    """Remove a gift from user's saved collection."""
    from .trending_service import UserGiftSaveService

    service = UserGiftSaveService(db)
    success = await service.unsave_gift(user_id=user_id, gift_id=gift_id)
    if not success:
        raise HTTPException(status_code=404, detail="Saved gift not found")
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/dashboard")
async def get_dashboard(
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get gift dashboard aggregated data."""
    from .dashboard_service import DashboardService

    svc = DashboardService(session)
    return await svc.get_dashboard(family_id)


@router.get("/dashboard/stats")
async def get_stats(
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get gift statistics."""
    from .dashboard_service import DashboardService

    svc = DashboardService(session)
    data = await svc.get_dashboard(family_id)
    return data["stats"]


@router.get("/dashboard/member/{member_id}")
async def get_member_gift_summary(
    member_id: UUID,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get member gift summary."""
    from .dashboard_service import DashboardService

    svc = DashboardService(session)
    data = await svc.get_member_gift_summary(family_id, member_id)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@router.get("/dashboard/member/{member_id}/preferences")
async def get_member_preferences(
    member_id: UUID,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get member preference summary."""
    from .recommendation_service import PreferenceLearningService

    svc = PreferenceLearningService(session)
    return await svc.get_preference_summary(member_id)


@router.get("/dashboard/member/{member_id}/dedup-analysis")
async def get_member_dedup_analysis(
    member_id: UUID,
    years_back: int = Query(3, ge=1, le=5),
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get member dedup analysis."""
    from .recommendation_service import DedupAnalyzer

    analyzer = DedupAnalyzer(session)
    analysis = await analyzer.analyze(member_id=member_id, family_id=family_id, years_back=years_back)
    return analyzer.to_dict(analysis)


@router.post("/dashboard/member/{member_id}/infer-preferences")
async def infer_member_preferences(
    member_id: UUID,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Infer member preferences from history."""
    from .recommendation_service import PreferenceLearningService

    svc = PreferenceLearningService(session)
    count = await svc.infer_from_history(member_id, family_id)
    await session.commit()
    return {"message": f"Inferred {count} preferences from history", "inferred_count": count}


@router.get("/dashboard/upcoming-occasions")
async def get_upcoming_occasions(
    days: int = Query(60, ge=1, le=365),
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get upcoming gift occasions."""
    from .task_service import GiftTaskService
    from ...modules.member.repositories.member_repository import MemberRepository

    svc = GiftTaskService(session)
    tasks = await svc.get_upcoming_tasks(family_id, days)
    member_repo = MemberRepository(session)

    occasions = []
    for task in tasks:
        member = await member_repo.get_by_id(task.member_id)
        occasions.append({
            "task_id": str(task.id),
            "member_id": str(task.member_id),
            "member_name": member.name if member else "Unknown",
            "occasion": task.occasion,
            "occasion_title": task.occasion_title,
            "occasion_date": task.occasion_date.isoformat(),
            "days_until": (task.occasion_date - date.today()).days,
            "status": task.status,
            "has_recommendation": task.recommendation_id is not None,
        })
    occasions.sort(key=lambda x: x["days_until"])
    return {"items": occasions, "total": len(occasions)}
