"""Itinerary API endpoints"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from ....db.session import get_db
from ....core.auth import get_current_user, get_current_family
from ....core.llm import openai_adapter
from ..models.trip_itinerary import TripItinerary
from ..models.trip_plan import TripPlan
from ..schemas.itinerary import (
    TripItineraryResponse,
    TripItineraryListResponse,
    SmartItineraryRequest,
    SmartItineraryResponse,
    ItineraryAdjustmentRequest,
    ItineraryAdjustmentResponse,
    ItineraryStyleEnum,
    ActivityUpdateRequest,
    ActivityCreateRequest,
    ActivityDeleteRequest,
    DaySwapRequest,
    IncrementalUpdateResponse,
)
from ..services.itinerary_planner import ItineraryPlanner
from ..services.smart_itinerary_planner import SmartItineraryPlanner, ItineraryStyle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips/plans/{trip_id}/itinerary", tags=["trip-itinerary"])


def _compute_period(time_str: str) -> str:
    """Derive the day-period label from an HH:MM time string.

    Returns one of '上午', '下午', '晚上'.
    """
    if not time_str:
        return "上午"
    try:
        hour = int(time_str.split(":")[0])
    except (ValueError, IndexError):
        return "上午"
    if hour < 12:
        return "上午"
    if hour < 18:
        return "下午"
    return "晚上"


def _enrich_schedule(schedule: List[dict]) -> List[dict]:
    """Add ``period`` to each activity if not already present."""
    enriched = []
    for item in schedule:
        if not isinstance(item, dict):
            enriched.append(item)
            continue
        if not item.get("period"):
            enriched.append({**item, "period": _compute_period(item.get("time", ""))})
        else:
            enriched.append(item)
    return enriched


@router.get("")
async def get_trip_itinerary(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get all itineraries for a trip."""
    try:
        result = await db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .order_by(TripItinerary.day_number)
        )
        itineraries = result.scalars().all()

        logger.info(f"GET /itinerary for trip {trip_id}: found {len(itineraries)} days")

        items = []
        for itinerary in itineraries:
            try:
                schedule_len = len(itinerary.schedule) if itinerary.schedule else 0
                logger.info(f"  Day {itinerary.day_number}: {schedule_len} activities in schedule")

                # Build response dict manually to avoid validation issues
                item_dict = {
                    "itinerary_id": str(itinerary.itinerary_id),
                    "trip_id": str(itinerary.trip_id),
                    "day_number": itinerary.day_number,
                    "schedule": _enrich_schedule(itinerary.schedule or []),
                    "packing_notes": itinerary.packing_notes,
                    "created_at": itinerary.created_at.isoformat() if itinerary.created_at else None,
                    "updated_at": itinerary.updated_at.isoformat() if itinerary.updated_at else None,
                    "total_estimated_cost": itinerary.total_estimated_cost,
                    "activity_count": itinerary.activity_count,
                }
                items.append(item_dict)
            except Exception as e:
                logger.error(f"Error processing day {itinerary.day_number}: {e}")
                # Still include the day with basic info
                items.append({
                    "itinerary_id": str(itinerary.itinerary_id),
                    "trip_id": str(itinerary.trip_id),
                    "day_number": itinerary.day_number,
                    "schedule": [],
                    "packing_notes": None,
                    "created_at": itinerary.created_at.isoformat() if itinerary.created_at else None,
                    "updated_at": itinerary.updated_at.isoformat() if itinerary.updated_at else None,
                    "total_estimated_cost": 0,
                    "activity_count": 0,
                })

        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.error(f"Error fetching itinerary for trip {trip_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_itinerary(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Generate complete itinerary for a trip (basic version)."""
    try:
        # Get trip details
        result = await db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = result.scalar_one_or_none()

        if not trip:
            raise HTTPException(status_code=404, detail="Travel plan not found")

        planner = ItineraryPlanner(db, openai_adapter)

        # Build family composition from participants (simplified for now)
        family_composition = {
            "children": [],
            "elderly": [],
            "special_needs": []
        }

        # Generate daily schedule
        itineraries = await planner.generate_daily_schedule(
            trip_id=trip_id,
            destination=trip.destination,
            start_date=trip.start_date,
            end_date=trip.end_date,
            family_composition=family_composition,
            budget=float(trip.budget) if trip.budget else None,
            preferences=None
        )

        try:
            from ...curation.tasks import trigger_curation_if_enabled
            await trigger_curation_if_enabled(
                family_id,
                "auto_curate_on_trip_create",
                "itinerary_updated",
                payload={"trip_id": str(trip_id)},
                db=db,
            )
        except Exception as exc:
            logger.debug("Curation trigger skipped for itinerary generate: %s", exc)

        return {
            "trip_id": str(trip_id),
            "message": "Itinerary generated successfully",
            "status": "completed",
            "itineraries": itineraries
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-smart")
async def generate_smart_itinerary(
    trip_id: UUID,
    request: SmartItineraryRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    生成智能行程规划

    根据用户选择的风格和家庭成员组成，生成专业级别的详细行程，
    包括每个活动的专业建议、设计依据和备选方案。

    风格选项：
    - intensive: 紧凑型 - 景点密集，充分利用时间
    - relaxed: 轻松型 - 慢节奏，充足休息
    - budget: 经济型 - 控制花费，高性价比
    - luxury: 豪华型 - 高端体验，五星服务
    - adventure: 探险型 - 户外活动，自然风光
    - cultural: 文化型 - 博物馆、历史遗迹
    """
    try:
        # Get trip details
        result = await db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = result.scalar_one_or_none()

        if not trip:
            raise HTTPException(status_code=404, detail="Travel plan not found")

        # Convert schema enum to service enum
        styles = [ItineraryStyle(s.value) for s in request.styles]

        # Build family composition
        family_composition = {
            "children": [],
            "elderly": [],
            "special_needs": []
        }

        if request.family_composition:
            family_composition["children"] = [
                {"age": c.age, "name": c.name} for c in request.family_composition.children
            ]
            family_composition["elderly"] = [
                {"age": e.age, "name": e.name} for e in request.family_composition.elderly
            ]
            family_composition["special_needs"] = request.family_composition.special_needs

        # Create smart planner and generate
        planner = SmartItineraryPlanner(db, openai_adapter)
        smart_result = await planner.generate_smart_itinerary(
            trip_id=trip_id,
            destination=trip.destination,
            start_date=trip.start_date,
            end_date=trip.end_date,
            styles=styles,
            family_composition=family_composition,
            budget=float(trip.budget) if trip.budget else None,
            preferences=request.preferences
        )

        try:
            from ...curation.tasks import trigger_curation_if_enabled
            await trigger_curation_if_enabled(
                family_id,
                "auto_curate_on_trip_create",
                "itinerary_updated",
                payload={"trip_id": str(trip_id)},
                db=db,
            )
        except Exception as exc:
            logger.debug("Curation trigger skipped for itinerary generate-smart: %s", exc)

        return smart_result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/adjust", response_model=ItineraryAdjustmentResponse)
async def adjust_itinerary(
    trip_id: UUID,
    request: ItineraryAdjustmentRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    根据用户请求调整行程

    支持自然语言请求，如：
    - "今天想轻松一点"
    - "下午有事，能不能把景点换到明天"
    - "想增加一个购物行程"
    """
    try:
        # Verify trip exists
        result = await db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = result.scalar_one_or_none()

        if not trip:
            raise HTTPException(status_code=404, detail="Travel plan not found")

        planner = SmartItineraryPlanner(db, openai_adapter)
        adjustment_result = await planner.adjust_itinerary(
            trip_id=trip_id,
            adjustment_request=request.adjustment_request,
            current_day=request.current_day
        )

        return adjustment_result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/styles")
async def get_itinerary_styles(
    user_id: UUID = Depends(get_current_user),
):
    """
    获取可用的行程风格列表

    返回所有可选的行程风格及其描述，供前端展示选择。
    """
    from ..services.smart_itinerary_planner import STYLE_CONFIGS, ItineraryStyle

    styles = []
    for style in ItineraryStyle:
        config = STYLE_CONFIGS[style]
        styles.append({
            "value": style.value,
            "name": config["name"],
            "description": config["description"],
            "daily_attractions": config["daily_attractions"],
            "pace": config["pace"],
            "wake_time": config["wake_time"],
            "end_time": config["end_time"],
            "constraints": config["constraints"]
        })

    return {"styles": styles}


# ============ Incremental Update Endpoints (FR-020) ============

@router.put("/day/{day_number}/activity", response_model=IncrementalUpdateResponse)
async def update_activity(
    trip_id: UUID,
    day_number: int,
    request: ActivityUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    更新指定天的某个活动

    增量更新，不影响其他活动。
    """
    try:
        # Get the itinerary for this day
        result = await db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .where(TripItinerary.day_number == day_number)
        )
        itinerary = result.scalar_one_or_none()

        if not itinerary:
            raise HTTPException(status_code=404, detail=f"Day {day_number} itinerary not found")

        schedule = itinerary.schedule or []
        if request.activity_index >= len(schedule):
            raise HTTPException(status_code=400, detail="Activity index out of range")

        # Update the specific activity
        activity = schedule[request.activity_index]
        if request.time is not None:
            activity["time"] = request.time
        if request.duration_minutes is not None:
            activity["duration_minutes"] = request.duration_minutes
        if request.title is not None:
            activity["title"] = request.title
        if request.location is not None:
            activity["location"] = request.location
        if request.description is not None:
            activity["description"] = request.description
        if request.estimated_cost is not None:
            activity["estimated_cost"] = request.estimated_cost

        # Sort by time after update
        schedule.sort(key=lambda x: x.get("time", "00:00"))

        itinerary.schedule = schedule
        await db.commit()

        try:
            from ...curation.tasks import trigger_curation_if_enabled
            await trigger_curation_if_enabled(
                family_id,
                "auto_curate_on_trip_create",
                "itinerary_updated",
                payload={"trip_id": str(trip_id)},
                db=db,
            )
        except Exception as exc:
            logger.debug("Curation trigger skipped for update_activity: %s", exc)

        # Calculate new day summary
        total_cost = sum(a.get("estimated_cost", 0) for a in schedule)
        activity_count = len(schedule)

        return IncrementalUpdateResponse(
            success=True,
            message=f"Activity updated successfully",
            updated_day=day_number,
            updated_schedule=schedule,
            new_day_summary={
                "total_cost": total_cost,
                "walking_distance_km": 0,  # Would need calculation
                "activity_count": activity_count,
                "energy_level": "适中"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/day/{day_number}/activity", response_model=IncrementalUpdateResponse)
async def add_activity(
    trip_id: UUID,
    day_number: int,
    request: ActivityCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    向指定天添加新活动

    活动会按时间顺序自动排序。
    """
    try:
        # Get or create itinerary for this day
        result = await db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .where(TripItinerary.day_number == day_number)
        )
        itinerary = result.scalar_one_or_none()

        if not itinerary:
            # Create new day itinerary
            itinerary = TripItinerary(
                trip_id=trip_id,
                day_number=day_number,
                schedule=[]
            )
            db.add(itinerary)

        schedule = itinerary.schedule or []

        # Add new activity
        new_activity = {
            "time": request.time,
            "duration_minutes": request.duration_minutes,
            "activity_type": request.activity_type,
            "title": request.title,
            "location": request.location or "",
            "description": request.description or "",
            "estimated_cost": request.estimated_cost or 0,
            "professional_advice": None,
            "alternatives": []
        }
        schedule.append(new_activity)

        # Sort by time
        schedule.sort(key=lambda x: x.get("time", "00:00"))

        itinerary.schedule = schedule
        await db.commit()

        try:
            from ...curation.tasks import trigger_curation_if_enabled
            await trigger_curation_if_enabled(
                family_id,
                "auto_curate_on_trip_create",
                "itinerary_updated",
                payload={"trip_id": str(trip_id)},
                db=db,
            )
        except Exception as exc:
            logger.debug("Curation trigger skipped for add_activity: %s", exc)

        total_cost = sum(a.get("estimated_cost", 0) for a in schedule)
        activity_count = len(schedule)

        return IncrementalUpdateResponse(
            success=True,
            message=f"Activity added to day {day_number}",
            updated_day=day_number,
            updated_schedule=schedule,
            new_day_summary={
                "total_cost": total_cost,
                "walking_distance_km": 0,
                "activity_count": activity_count,
                "energy_level": "适中"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/day/{day_number}/activity/{activity_index}", response_model=IncrementalUpdateResponse)
async def delete_activity(
    trip_id: UUID,
    day_number: int,
    activity_index: int,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    删除指定天的某个活动
    """
    try:
        result = await db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .where(TripItinerary.day_number == day_number)
        )
        itinerary = result.scalar_one_or_none()

        if not itinerary:
            raise HTTPException(status_code=404, detail=f"Day {day_number} itinerary not found")

        schedule = itinerary.schedule or []
        if activity_index >= len(schedule):
            raise HTTPException(status_code=400, detail="Activity index out of range")

        # Remove activity
        deleted = schedule.pop(activity_index)
        itinerary.schedule = schedule
        await db.commit()

        try:
            from ...curation.tasks import trigger_curation_if_enabled
            await trigger_curation_if_enabled(
                family_id,
                "auto_curate_on_trip_create",
                "itinerary_updated",
                payload={"trip_id": str(trip_id)},
                db=db,
            )
        except Exception as exc:
            logger.debug("Curation trigger skipped for delete_activity: %s", exc)

        total_cost = sum(a.get("estimated_cost", 0) for a in schedule)
        activity_count = len(schedule)

        return IncrementalUpdateResponse(
            success=True,
            message=f"Activity '{deleted.get('title', 'Unknown')}' deleted",
            updated_day=day_number,
            updated_schedule=schedule,
            new_day_summary={
                "total_cost": total_cost,
                "walking_distance_km": 0,
                "activity_count": activity_count,
                "energy_level": "适中"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/swap-days", response_model=IncrementalUpdateResponse)
async def swap_days(
    trip_id: UUID,
    request: DaySwapRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """
    交换两天的行程

    完整交换两天的所有活动安排。
    """
    try:
        if request.source_day == request.target_day:
            raise HTTPException(status_code=400, detail="Cannot swap a day with itself")

        # Get both days
        result = await db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .where(TripItinerary.day_number.in_([request.source_day, request.target_day]))
        )
        itineraries = {it.day_number: it for it in result.scalars().all()}

        source = itineraries.get(request.source_day)
        target = itineraries.get(request.target_day)

        if not source and not target:
            raise HTTPException(status_code=404, detail="Neither day has an itinerary")

        # Swap schedules
        source_schedule = source.schedule if source else []
        target_schedule = target.schedule if target else []

        if source:
            source.schedule = target_schedule
        else:
            # Create new itinerary for source day
            source = TripItinerary(
                trip_id=trip_id,
                day_number=request.source_day,
                schedule=target_schedule
            )
            db.add(source)

        if target:
            target.schedule = source_schedule
        else:
            # Create new itinerary for target day
            target = TripItinerary(
                trip_id=trip_id,
                day_number=request.target_day,
                schedule=source_schedule
            )
            db.add(target)

        await db.commit()

        try:
            from ...curation.tasks import trigger_curation_if_enabled
            await trigger_curation_if_enabled(
                family_id,
                "auto_curate_on_trip_create",
                "itinerary_updated",
                payload={"trip_id": str(trip_id)},
                db=db,
            )
        except Exception as exc:
            logger.debug("Curation trigger skipped for swap_days: %s", exc)

        return IncrementalUpdateResponse(
            success=True,
            message=f"Day {request.source_day} and Day {request.target_day} swapped successfully",
            updated_day=request.source_day
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
