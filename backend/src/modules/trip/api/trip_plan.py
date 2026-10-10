"""
Trip plan CRUD API endpoints.
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update as sa_update
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from ....db.session import get_db
from ....core.auth import get_current_family, get_current_user
from ..models.trip_plan import TripPlan
from ..models.trip_itinerary import TripItinerary
from ..schemas.trip_plan import (
    TripPlanCreate,
    TripPlanUpdate,
    TripPlanResponse,
    TripPlanListResponse
)
from ....core.utils.timezone import utc_now
from ....core.events import get_event_bus
from ....core.events.domain_events import (
    TripCreated,
    TripUpdated,
    TripCancelled,
    TripDeleted,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips/plans", tags=["trip-plans"])

_VALID_TRIP_TYPES = {
    "leisure",
    "family",
    "visit",
    "business_trip",
    "conference",
    "client_visit",
    "other",
}


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _parse_itinerary_payload(itinerary: Any) -> Any:
    if isinstance(itinerary, str):
        try:
            return json.loads(itinerary)
        except (ValueError, TypeError):
            return itinerary
    return itinerary


def _extract_itinerary_days(itinerary: Any) -> List[Any]:
    data = _parse_itinerary_payload(itinerary)
    if isinstance(data, dict):
        if isinstance(data.get("daily_plans"), list):
            return data["daily_plans"]
        if isinstance(data.get("itinerary"), list):
            return data["itinerary"]
        if isinstance(data.get("days"), list):
            return data["days"]
        full_itinerary = data.get("full_itinerary")
        if isinstance(full_itinerary, dict) and isinstance(full_itinerary.get("daily_plans"), list):
            return full_itinerary["daily_plans"]
        return []
    if isinstance(data, list):
        if not data:
            return []
        # If this looks like a flat list of activities, wrap into a single day
        if all(not isinstance(item, dict) for item in data):
            return [{"activities": data}]
        if all(
            isinstance(item, dict)
            and (
                "time" in item
                or "title" in item
                or "activity_type" in item
                or "location" in item
            )
            for item in data
        ):
            return [{"activities": data}]
        return data
    return []


def _normalize_activity(activity: Any) -> Dict[str, Any]:
    if isinstance(activity, dict):
        time_value = activity.get("time") or activity.get("start_time") or activity.get("start") or ""
        activity_type = activity.get("activity_type") or activity.get("type") or activity.get("category") or "other"
        title = activity.get("title") or activity.get("name") or activity.get("activity") or activity.get("label")
        location = activity.get("location") or activity.get("place") or activity.get("address") or ""
        description = (
            activity.get("description")
            or activity.get("notes")
            or activity.get("detail")
            or activity.get("summary")
            or ""
        )

        estimated_cost = activity.get("estimated_cost")
        if estimated_cost is None:
            estimated_cost = activity.get("cost_per_person") or activity.get("cost") or activity.get("price")

        item: Dict[str, Any] = {
            "time": str(time_value) if time_value is not None else "",
            "activity_type": str(activity_type) if activity_type is not None else "other",
            "title": str(title) if title is not None else "活动",
            "location": location if location is not None else "",
            "description": description if description is not None else "",
        }

        cost_value = _coerce_float(estimated_cost)
        if cost_value is not None:
            item["estimated_cost"] = cost_value

        if activity.get("booking_info") is not None:
            item["booking_info"] = activity.get("booking_info")
        if activity.get("notes") is not None:
            item["notes"] = activity.get("notes")
        if activity.get("duration_minutes") is not None:
            item["duration_minutes"] = activity.get("duration_minutes")
        elif activity.get("duration") is not None:
            item["duration_minutes"] = activity.get("duration")
        if activity.get("professional_advice") is not None:
            item["professional_advice"] = activity.get("professional_advice")
        elif activity.get("tips") is not None:
            item["professional_advice"] = activity.get("tips")
        if activity.get("alternatives") is not None:
            item["alternatives"] = activity.get("alternatives")

        return item

    return {
        "time": "",
        "activity_type": "other",
        "title": str(activity) if activity is not None else "活动",
        "location": "",
        "description": "",
    }


def _extract_schedule_and_packing(day_data: Any) -> Tuple[List[Dict[str, Any]], Any]:
    packing_notes = None
    schedule_raw: List[Any] = []

    if isinstance(day_data, dict):
        packing_notes = (
            day_data.get("packing_notes")
            or day_data.get("packing_list")
            or day_data.get("packing")
        )
        if isinstance(day_data.get("schedule"), list):
            schedule_raw = day_data["schedule"]
        elif isinstance(day_data.get("activities"), list):
            schedule_raw = day_data["activities"]
        elif isinstance(day_data.get("items"), list):
            schedule_raw = day_data["items"]
    elif isinstance(day_data, list):
        schedule_raw = day_data

    schedule = [_normalize_activity(a) for a in schedule_raw if a is not None]
    schedule.sort(key=lambda x: x.get("time") or "00:00")

    return schedule, packing_notes


def _normalize_participants(
    participants: Optional[List[UUID]],
    *,
    fallback_user_id: UUID,
) -> List[UUID]:
    """Deduplicate participants and guarantee at least one member."""
    seen = set()
    normalized: List[UUID] = []
    for pid in participants or []:
        if pid in seen:
            continue
        seen.add(pid)
        normalized.append(pid)

    if not normalized:
        normalized.append(fallback_user_id)
    return normalized


@router.post("", response_model=TripPlanResponse)
async def create_trip_plan(
    plan_data: TripPlanCreate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Create a new trip plan."""
    try:
        plan_dict = plan_data.model_dump(
            exclude={
                "itinerary",
                "people_to_meet",
                "tasks",
                "duration_days",
                "style",
            },
            exclude_unset=True,
        )

        if not plan_dict.get("family_id"):
            plan_dict["family_id"] = family_id
        if not plan_dict.get("created_by"):
            plan_dict["created_by"] = user_id

        extra_payload_style = None
        trip_type = plan_dict.get("trip_type")
        if trip_type and trip_type not in _VALID_TRIP_TYPES:
            extra_payload_style = trip_type
            plan_dict["trip_type"] = "leisure"

        plan_dict["participants"] = _normalize_participants(
            plan_dict.get("participants"),
            fallback_user_id=user_id,
        )

        extra_payload: Dict[str, Any] = {}
        if plan_data.itinerary is not None:
            extra_payload["itinerary"] = plan_data.itinerary
        if plan_data.people_to_meet:
            extra_payload["people_to_meet"] = plan_data.people_to_meet
        if plan_data.tasks:
            extra_payload["tasks"] = plan_data.tasks
        if plan_data.duration_days is not None:
            extra_payload["duration_days"] = plan_data.duration_days
        if plan_data.style:
            extra_payload["style"] = plan_data.style
        elif extra_payload_style:
            extra_payload["style"] = extra_payload_style

        if extra_payload:
            if not plan_dict.get("recommendation_context"):
                plan_dict["recommendation_context"] = extra_payload
            extra_data = plan_dict.get("extra_data") or {}
            if isinstance(extra_data, dict):
                extra_data.update(extra_payload)
                plan_dict["extra_data"] = extra_data

        # Dedup: check for existing trip with same destination + overlapping dates
        from ..services.trip_service import TripService
        trip_svc = TripService(db)
        dest_val = plan_dict.get("destination", "")
        start_val = plan_dict.get("start_date")
        end_val = plan_dict.get("end_date")
        merged = False
        if dest_val and start_val and end_val:
            existing = await trip_svc.find_matching_trip(
                family_id, dest_val, start_val, end_val,
            )
            if existing:
                # Merge into existing trip instead of creating duplicate
                for field in ("trip_name", "category", "trip_type", "notes", "description"):
                    new_val = plan_dict.get(field)
                    if new_val:
                        setattr(existing, field, new_val)
                # Extend date range rather than overwrite
                if start_val and (not existing.start_date or start_val < existing.start_date):
                    existing.start_date = start_val
                if end_val and (not existing.end_date or end_val > existing.end_date):
                    existing.end_date = end_val
                existing.updated_at = utc_now()
                trip_plan = existing
                merged = True
                await db.flush()

        if not merged:
            trip_plan = TripPlan(**plan_dict)
            db.add(trip_plan)
            await db.flush()

        # Process itinerary days (upsert by day_number)
        itinerary_days = _extract_itinerary_days(plan_data.itinerary)
        for idx, day_data in enumerate(itinerary_days):
            day_number = idx + 1
            schedule, packing_notes = _extract_schedule_and_packing(day_data)

            # Upsert: update existing day or create new
            existing_itin_stmt = select(TripItinerary).where(
                and_(
                    TripItinerary.trip_id == trip_plan.trip_id,
                    TripItinerary.day_number == day_number,
                )
            )
            existing_itin = (await db.execute(existing_itin_stmt)).scalar_one_or_none()
            if existing_itin:
                existing_itin.schedule = schedule
                existing_itin.packing_notes = packing_notes
            else:
                db.add(TripItinerary(
                    trip_id=trip_plan.trip_id,
                    day_number=day_number,
                    schedule=schedule,
                    packing_notes=packing_notes,
                ))

        # Sync trip end_date if itinerary extends beyond it
        if itinerary_days:
            TripService._sync_trip_end_date(trip_plan, len(itinerary_days))

        # Create/update memory record
        await trip_svc.create_trip_memory(
            user_id=user_id,
            family_id=family_id,
            trip=trip_plan,
            action="更新" if merged else "创建",
        )

        # Write event to outbox within the same transaction
        try:
            event_bus = get_event_bus()
            await event_bus.publish_with_outbox(db, TripCreated(
                plan_id=trip_plan.trip_id,
                family_id=trip_plan.family_id,
                user_id=user_id,
                destination=trip_plan.destination or "",
                start_date=trip_plan.start_date,
                end_date=trip_plan.end_date,
                trip_type=trip_plan.trip_type or "",
            ))
        except Exception as e:
            logger.warning("Failed to publish TripCreated event: %s", e)

        await db.commit()

        try:
            from ...curation.tasks import trigger_curation_if_enabled
            await trigger_curation_if_enabled(
                family_id,
                "auto_curate_on_trip_create",
                "trip_created",
                payload={"plan_id": str(trip_plan.trip_id)},
                db=db,
            )
        except Exception as exc:
            logger.debug("Curation trigger skipped: %s", exc)

        await db.refresh(trip_plan)

        response = TripPlanResponse.model_validate(trip_plan)
        response.duration_days = trip_plan.duration_days
        response.budget_used_percentage = trip_plan.budget_used_percentage
        response.remaining_budget = trip_plan.remaining_budget

        # Publish domain event — curation and memory modules subscribe
        if trip_plan.family_id:
            event_bus = get_event_bus()
            if merged:
                await event_bus.publish(TripUpdated(
                    plan_id=trip_plan.trip_id,
                    family_id=trip_plan.family_id,
                    destination=trip_plan.destination or "",
                ))
            else:
                await event_bus.publish(TripCreated(
                    plan_id=trip_plan.trip_id,
                    family_id=trip_plan.family_id,
                    user_id=user_id,
                    destination=trip_plan.destination or "",
                    start_date=trip_plan.start_date,
                    end_date=trip_plan.end_date,
                    trip_type=trip_plan.trip_type or "",
                ))

        return response
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create trip plan: {str(e)}")


@router.get("/{trip_id}", response_model=TripPlanResponse)
async def get_trip_plan(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get trip plan by ID."""
    result = await db.execute(
        select(TripPlan).where(TripPlan.trip_id == trip_id)
    )
    trip_plan = result.scalar_one_or_none()

    if not trip_plan:
        raise HTTPException(status_code=404, detail="Trip plan not found")

    response = TripPlanResponse.model_validate(trip_plan)
    response.duration_days = trip_plan.duration_days
    response.budget_used_percentage = trip_plan.budget_used_percentage
    response.remaining_budget = trip_plan.remaining_budget

    return response


@router.get("", response_model=TripPlanListResponse)
async def list_trip_plans(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None, pattern="^(personal|business)$"),
    include_history: bool = Query(
        False,
        description="是否包含历史/被 superseded 的行程。默认 false 仅返回 canonical 且 active 的行程。",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """List trip plans with optional filters."""
    query = select(TripPlan)

    query = query.where(TripPlan.family_id == family_id)
    if not include_history:
        query = query.where(
            TripPlan.canonical_trip_id.is_(None),
            TripPlan.is_active.is_(True),
        )
    if status:
        query = query.where(TripPlan.status == status)
    if category:
        query = query.where(TripPlan.category == category)

    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(TripPlan.created_at.desc())

    result = await db.execute(query)
    trip_plans = result.scalars().all()

    # Get total count
    count_query = select(TripPlan)
    count_query = count_query.where(TripPlan.family_id == family_id)
    if not include_history:
        count_query = count_query.where(
            TripPlan.canonical_trip_id.is_(None),
            TripPlan.is_active.is_(True),
        )
    if status:
        count_query = count_query.where(TripPlan.status == status)
    if category:
        count_query = count_query.where(TripPlan.category == category)

    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    items = []
    for plan in trip_plans:
        response = TripPlanResponse.model_validate(plan)
        response.duration_days = plan.duration_days
        response.budget_used_percentage = plan.budget_used_percentage
        response.remaining_budget = plan.remaining_budget
        items.append(response)

    return TripPlanListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.put("/{trip_id}", response_model=TripPlanResponse)
async def update_trip_plan(
    trip_id: UUID,
    plan_update: TripPlanUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Update trip plan."""
    result = await db.execute(
        select(TripPlan).where(TripPlan.trip_id == trip_id)
    )
    trip_plan = result.scalar_one_or_none()

    if not trip_plan:
        raise HTTPException(status_code=404, detail="Trip plan not found")

    # Update fields
    update_data = plan_update.model_dump(exclude_unset=True)
    if "participants" in update_data:
        update_data["participants"] = _normalize_participants(
            update_data.get("participants"),
            fallback_user_id=trip_plan.created_by or user_id,
        )
    old_status = trip_plan.status
    for field, value in update_data.items():
        setattr(trip_plan, field, value)

    # If status changed to cancelled, cascade to associated CuratedEvents
    new_status = update_data.get("status")
    if new_status == "cancelled" and old_status != "cancelled":
        from ...curation.models import CuratedEvent
        await db.execute(
            sa_update(CuratedEvent)
            .where(CuratedEvent.trip_id == trip_id)
            .values(status="cancelled", is_active=False)
        )

    # Write event to outbox within the same transaction
    try:
        event_bus = get_event_bus()
        await event_bus.publish_with_outbox(db, TripCreated(
            plan_id=trip_plan.trip_id,
            family_id=trip_plan.family_id,
            user_id=user_id,
            destination=trip_plan.destination or "",
            start_date=trip_plan.start_date,
            end_date=trip_plan.end_date,
            trip_type=trip_plan.trip_type or "",
        ))
    except Exception as e:
        logger.warning("Failed to publish TripCreated event: %s", e)

    await db.commit()

    try:
        from ...curation.tasks import trigger_curation_if_enabled
        await trigger_curation_if_enabled(
            family_id,
            "auto_curate_on_trip_create",
            "trip_updated",
            payload={"plan_id": str(trip_id)},
            db=db,
        )
    except Exception as exc:
        logger.debug("Curation trigger skipped: %s", exc)

    await db.refresh(trip_plan)

    response = TripPlanResponse.model_validate(trip_plan)
    response.duration_days = trip_plan.duration_days
    response.budget_used_percentage = trip_plan.budget_used_percentage
    response.remaining_budget = trip_plan.remaining_budget

    # Publish domain event — curation subscribes
    if trip_plan.family_id:
        event_bus = get_event_bus()
        await event_bus.publish(TripUpdated(
            plan_id=trip_plan.trip_id,
            family_id=trip_plan.family_id,
            destination=trip_plan.destination or "",
        ))

    return response


@router.delete("/{trip_id}")
async def delete_trip_plan(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Delete trip plan and publish cancellation event.

    The curation module subscribes to TripCancelled to handle:
    - Deactivating related CuratedEvent records
    - Reactivating social intents / memories that were fulfilled by this trip
    """
    result = await db.execute(
        select(TripPlan).where(TripPlan.trip_id == trip_id)
    )
    trip_plan = result.scalar_one_or_none()

    if not trip_plan:
        raise HTTPException(status_code=404, detail="Trip plan not found")

    plan_family_id = trip_plan.family_id

    # Deactivate all CuratedEvents associated with this trip BEFORE deleting
    # the TripPlan (FK ondelete="SET NULL" would orphan them otherwise).
    from ...curation.models import CuratedEvent
    await db.execute(
        sa_update(CuratedEvent)
        .where(CuratedEvent.trip_id == trip_id)
        .values(status="cancelled", is_active=False)
    )

    await db.delete(trip_plan)

    # Write cancellation + deletion events to outbox within the same transaction
    event_bus = get_event_bus()
    try:
        await event_bus.publish_with_outbox(db, TripCancelled(
            plan_id=trip_id,
            family_id=plan_family_id,
        ))
        await event_bus.publish_with_outbox(db, TripDeleted(
            plan_id=trip_id,
            family_id=plan_family_id,
        ))
    except Exception as e:
        logger.warning("Failed to publish trip plan events: %s", e)

    await db.commit()

    try:
        from ...curation.tasks import trigger_curation_if_enabled
        await trigger_curation_if_enabled(
            plan_family_id,
            "auto_curate_on_trip_create",
            "trip_deleted",
            payload={"plan_id": str(trip_id)},
            db=db,
        )
    except Exception as exc:
        logger.debug("Curation trigger skipped: %s", exc)

    return {"message": "Trip plan deleted successfully", "trip_id": str(trip_id)}


@router.get("/{trip_id}/context")
async def get_trip_context(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get enriched context for the trip detail page.

    Returns resolved participant names, real weather data,
    and preparation items from the linked curated event.
    """
    from ..schemas.trip_context import TripContextResponse
    from ..services.trip_detail_context_service import TripDetailContextService

    result = await db.execute(
        select(TripPlan).where(TripPlan.trip_id == trip_id)
    )
    trip_plan = result.scalar_one_or_none()

    if not trip_plan:
        raise HTTPException(status_code=404, detail="Trip plan not found")

    service = TripDetailContextService(db)
    context = await service.build_context(trip_plan, family_id)
    return context


@router.get("/{trip_id}/detail")
async def get_trip_detail(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Aggregated trip detail endpoint.

    Returns trip plan + itineraries + expenses + budget status + context +
    event associations in a single response. Replaces 6 serial API calls
    with 1 request using eager loading.
    """
    from sqlalchemy.orm import selectinload
    from ..models.trip_itinerary import TripItinerary
    from ..models.trip_expense import TripExpense
    from ..schemas.trip_context import TripDetailResponse
    from ..schemas.trip_plan import TripPlanResponse
    from ..services.trip_detail_context_service import TripDetailContextService
    from ..services.budget_tracker import BudgetTracker
    from sqlalchemy import func

    # --- 1. Single query with eager loading for plan + itineraries + expenses ---
    result = await db.execute(
        select(TripPlan)
        .options(
            selectinload(TripPlan.itineraries),
            selectinload(TripPlan.expenses),
        )
        .where(TripPlan.trip_id == trip_id)
    )
    trip_plan = result.scalar_one_or_none()

    if not trip_plan:
        raise HTTPException(status_code=404, detail="Trip plan not found")

    # --- 2. Serialize plan ---
    plan_response = TripPlanResponse.model_validate(trip_plan)
    plan_response.duration_days = trip_plan.duration_days
    plan_response.budget_used_percentage = trip_plan.budget_used_percentage
    plan_response.remaining_budget = trip_plan.remaining_budget
    plan_dict = plan_response.model_dump(mode="json")

    # --- 3. Serialize itineraries (already loaded) ---
    from ..api.itinerary import _enrich_schedule
    itinerary_items = []
    for it in sorted(trip_plan.itineraries, key=lambda x: x.day_number):
        itinerary_items.append({
            "itinerary_id": str(it.itinerary_id),
            "trip_id": str(it.trip_id),
            "day_number": it.day_number,
            "schedule": _enrich_schedule(it.schedule or []),
            "packing_notes": it.packing_notes,
            "created_at": it.created_at.isoformat() if it.created_at else None,
            "updated_at": it.updated_at.isoformat() if it.updated_at else None,
            "total_estimated_cost": it.total_estimated_cost,
            "activity_count": it.activity_count,
        })

    # --- 4. Serialize expenses (already loaded) + count ---
    from ..schemas.expense import TripExpenseResponse
    expense_items = [
        TripExpenseResponse.model_validate(exp).model_dump(mode="json")
        for exp in sorted(trip_plan.expenses, key=lambda x: x.expense_date, reverse=True)
    ]
    expense_total = len(trip_plan.expenses)

    # --- 5. Fetch budget status + context ---
    # A single AsyncSession cannot run concurrent DB operations safely.
    # Keep these calls sequential to avoid hidden context/budget drops.
    context_service = TripDetailContextService(db)
    budget_tracker = BudgetTracker(db)

    async def _safe_budget():
        try:
            return await budget_tracker.get_budget_status(trip_id)
        except Exception as e:
            logger.warning("Budget status failed for %s: %s", trip_id, e)
            return None

    async def _safe_context():
        try:
            return await context_service.build_context(trip_plan, family_id)
        except Exception as e:
            logger.warning("Context build failed for %s: %s", trip_id, e)
            return None

    budget_status = await _safe_budget()
    context = await _safe_context()

    # --- 6. If context has curated_event_id, fetch event associations ---
    associations = []
    related_memories = []
    curated_event_id = None
    if context is not None:
        curated_event_id = context.curated_event_id
    if curated_event_id:
        try:
            from ...views.services.event_detail_service import EventDetailService
            event_svc = EventDetailService(db)
            event_detail = await event_svc.get_event_detail(
                event_id=curated_event_id,
                family_id=family_id,
                user_id=user_id,
            )
            if event_detail:
                raw = event_detail.model_dump(mode="json") if hasattr(event_detail, 'model_dump') else {}
                for a in raw.get("associations", []):
                    associations.append({
                        "id": str(a.get("id", "")),
                        "title": a.get("title"),
                        "reason": a.get("reason"),
                        "target_type": a.get("target_type", "task"),
                        "priority": a.get("priority"),
                    })
                for m in raw.get("related_memories", []):
                    related_memories.append({
                        "id": str(m.get("id", "")),
                        "summary": m.get("summary") or m.get("content") or "",
                        "memory_type": m.get("memory_type"),
                        "created_at": m.get("created_at"),
                    })
        except Exception as e:
            logger.warning("Event context failed for %s: %s", curated_event_id, e)

    return TripDetailResponse(
        plan=plan_dict,
        itinerary=itinerary_items,
        expenses=expense_items,
        expense_total=expense_total,
        budget_status=budget_status,
        context=context,
        associations=associations,
        related_memories=related_memories,
    )


@router.get("/itinerary-styles/list")
async def get_itinerary_styles():
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
