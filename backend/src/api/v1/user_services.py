"""
User stats, smart services, and feedback API endpoints.

Split from members.py to keep file sizes under 800 lines.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from ...core.utils.timezone import utc_now
from ...db.session import get_db
from ...core.auth import get_current_user, get_current_family


router = APIRouter(prefix="/members", tags=["User Services"])

logger = logging.getLogger(__name__)


class UserStatsResponse(BaseModel):
    """User statistics response."""
    model_config = ConfigDict(from_attributes=True)

    days_since_joined: int
    total_records: int
    completed_goals: int
    family_member_count: int
    upcoming_events_count: int
    active_services_count: int
    member_counts_by_type: dict = {}


class SmartServiceInfo(BaseModel):
    """Smart service information for display."""
    id: str
    display_name: str
    description: str
    icon: str
    category: str
    is_enabled: bool
    is_running: bool
    last_run: Optional[str] = None
    last_status: Optional[str] = None
    next_run: Optional[str] = None
    total_executions: int = 0
    success_rate: float = 0.0


class SmartServicesResponse(BaseModel):
    """Response containing all smart services."""
    services: List[SmartServiceInfo]
    total_count: int
    active_count: int


class FeedbackRequest(BaseModel):
    """User feedback request."""
    content: str
    contact_info: Optional[str] = None


class FeedbackResponse(BaseModel):
    """Feedback submission response."""
    success: bool
    message: str


# Service configuration mapping
_SERVICE_CONFIGS = {
    "reminder_scheduler": {
        "display_name": "重要日期提醒",
        "description": "生日、纪念日、节日自动提醒",
        "icon": "notifications_active",
        "category": "reminder",
    },
    "holiday_sync_scheduler": {
        "display_name": "节日同步",
        "description": "自动同步公共假期信息",
        "icon": "celebration",
        "category": "sync",
    },
    "holiday_preparation_scheduler": {
        "display_name": "节日准备提醒",
        "description": "节日前的礼物和准备提醒",
        "icon": "card_giftcard",
        "category": "reminder",
    },
    "gift_scheduler": {
        "display_name": "智能礼物推荐",
        "description": "根据家人喜好智能推荐礼物",
        "icon": "redeem",
        "category": "recommendation",
    },
    "price_scheduler": {
        "display_name": "价格监控",
        "description": "关注商品降价及时提醒",
        "icon": "trending_down",
        "category": "monitoring",
    },
}


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get user statistics (days used, records count, etc.)."""
    from datetime import timezone, timedelta
    from ...modules.member.models.member import Member
    from ...modules.date_manager.models import ImportantDate
    from ...modules.gift.models import GiftHistory
    from ...modules.trip.models.trip_plan import TripPlan

    days_since_joined = 0

    member_stmt = select(Member).where(Member.id == user_id)
    result = await db.execute(member_stmt)
    member = result.scalar_one_or_none()

    if member and member.created_at:
        days_since_joined = (utc_now() - member.created_at.replace(tzinfo=timezone.utc)).days
    else:
        earliest_member_stmt = select(Member).where(
            Member.family_id == family_id,
            Member.is_deleted == False,
        ).order_by(Member.created_at.asc()).limit(1)
        result = await db.execute(earliest_member_stmt)
        earliest_member = result.scalar_one_or_none()
        if earliest_member and earliest_member.created_at:
            days_since_joined = (utc_now() - earliest_member.created_at.replace(tzinfo=timezone.utc)).days

    if days_since_joined <= 0:
        days_since_joined = 1

    member_count_stmt = select(func.count()).select_from(Member).where(
        Member.family_id == family_id,
        Member.is_deleted == False,
    )
    result = await db.execute(member_count_stmt)
    family_member_count = result.scalar() or 0

    date_count_stmt = select(func.count()).select_from(ImportantDate).where(
        ImportantDate.family_id == family_id,
    )
    result = await db.execute(date_count_stmt)
    date_count = result.scalar() or 0

    gift_count_stmt = select(func.count()).select_from(GiftHistory).where(
        GiftHistory.family_id == family_id,
    )
    result = await db.execute(gift_count_stmt)
    gift_count = result.scalar() or 0

    travel_count_stmt = select(func.count()).select_from(TripPlan).where(
        TripPlan.family_id == family_id,
    )
    result = await db.execute(travel_count_stmt)
    travel_count = result.scalar() or 0

    total_records = date_count + gift_count + travel_count

    today = utc_now().date()
    thirty_days_later = today + timedelta(days=30)
    try:
        upcoming_stmt = select(func.count()).select_from(ImportantDate).where(
            ImportantDate.family_id == family_id,
            ImportantDate.date >= today,
            ImportantDate.date <= thirty_days_later,
        )
        result = await db.execute(upcoming_stmt)
        upcoming_events_count = result.scalar() or 0
    except Exception:
        upcoming_events_count = 0

    try:
        from ...core.scheduler import scheduler_manager
        statuses = await scheduler_manager.get_all_status()
        active_services_count = sum(1 for s in statuses if s.is_running)
    except Exception:
        active_services_count = 0

    # Member counts by relationship type
    from ...modules.member.models.member import MemberRelation
    member_type_stmt = (
        select(
            MemberRelation.relation_type,
            func.count().label("count"),
        )
        .where(
            MemberRelation.family_id == family_id,
            MemberRelation.from_member_id == user_id,
        )
        .group_by(MemberRelation.relation_type)
    )
    type_result = await db.execute(member_type_stmt)
    member_counts_by_type = {}
    for row in type_result.all():
        rel_type = row.relation_type
        # Handle enum values
        type_str = rel_type.value if hasattr(rel_type, 'value') else str(rel_type)
        member_counts_by_type[type_str] = row.count

    return UserStatsResponse(
        days_since_joined=days_since_joined,
        total_records=total_records,
        completed_goals=0,
        family_member_count=family_member_count,
        upcoming_events_count=upcoming_events_count,
        active_services_count=active_services_count,
        member_counts_by_type=member_counts_by_type,
    )


@router.get("/smart-services", response_model=SmartServicesResponse)
async def get_smart_services(
    user_id: UUID = Depends(get_current_user),
):
    """Get all smart services with their status."""
    from ...core.scheduler import scheduler_manager

    services = []
    active_count = 0

    try:
        statuses = await scheduler_manager.get_all_status()

        for svc_status in statuses:
            config = _SERVICE_CONFIGS.get(svc_status.name, {
                "display_name": svc_status.name,
                "description": "",
                "icon": "settings",
                "category": "other",
            })

            is_enabled = svc_status.is_running or svc_status.is_paused
            if svc_status.is_running:
                active_count += 1

            last_run = None
            last_status = None
            next_run = None
            if svc_status.jobs:
                for job in svc_status.jobs:
                    if job.get("last_run"):
                        if last_run is None or job["last_run"] > last_run:
                            last_run = job["last_run"]
                            last_status = job.get("last_status")
                    if job.get("next_run"):
                        if next_run is None or job["next_run"] < next_run:
                            next_run = job["next_run"]

            services.append(SmartServiceInfo(
                id=svc_status.name,
                display_name=config["display_name"],
                description=config["description"],
                icon=config["icon"],
                category=config["category"],
                is_enabled=is_enabled,
                is_running=svc_status.is_running,
                last_run=last_run,
                last_status=last_status,
                next_run=next_run,
                total_executions=svc_status.stats.get("total_executions", 0),
                success_rate=svc_status.stats.get("success_rate", 0.0),
            ))
    except Exception:
        pass

    return SmartServicesResponse(
        services=services,
        total_count=len(services),
        active_count=active_count,
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    user_id: UUID = Depends(get_current_user),
):
    """Submit user feedback."""
    logger.info("User feedback received from %s: %s", user_id, request.content)
    if request.contact_info:
        logger.info("Contact info: %s", request.contact_info)

    return FeedbackResponse(
        success=True,
        message="\u53cd\u9988\u5df2\u63d0\u4ea4\uff0c\u611f\u8c22\u60a8\u7684\u610f\u89c1\uff01",
    )


@router.get("/features")
async def get_features(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Return available features and tier status for the current user.

    Uses the V8 progressive feature unlock (4-tier) system:
      BASIC    : conversation, reminders, weather (registration)
      ADVANCED : + kanban, briefing, memory (7 days + 2 family members)
      PREMIUM  : + trip_planning, gifts, relationships (30 days or manual)
      EXPERT   : + graph_view, global_orchestration (manual only)
    """
    from datetime import timezone
    from ...modules.member.models.member import Member
    from ...modules.member.trust_service import (
        get_available_features,
        get_feature_tiers,
    )

    # Compute days_active
    member_stmt = select(Member).where(Member.id == user_id)
    result = await db.execute(member_stmt)
    member = result.scalar_one_or_none()

    days_active = 0
    if member and member.created_at:
        days_active = (utc_now() - member.created_at.replace(tzinfo=timezone.utc)).days
    if days_active < 0:
        days_active = 0

    # Count family members (excluding self)
    family_count_stmt = select(func.count()).select_from(Member).where(
        Member.family_id == family_id,
        Member.is_deleted == False,
        Member.id != user_id,
    )
    count_result = await db.execute(family_count_stmt)
    family_member_count = count_result.scalar() or 0

    # Check for manual overrides stored in member settings
    manual_overrides = None
    if member and hasattr(member, "tags") and member.tags:
        overrides = {}
        for tag in (member.tags or []):
            if isinstance(tag, str) and tag.startswith("tier_unlock:"):
                tier_name = tag.split(":", 1)[1]
                overrides[tier_name] = True
        if overrides:
            manual_overrides = overrides

    features = get_available_features(
        days_active=days_active,
        family_member_count=family_member_count,
        manual_overrides=manual_overrides,
    )
    tiers = get_feature_tiers(
        days_active=days_active,
        family_member_count=family_member_count,
        manual_overrides=manual_overrides,
    )

    return {
        "available_features": features,
        "tiers": tiers,
        "days_active": days_active,
        "family_member_count": family_member_count,
    }
