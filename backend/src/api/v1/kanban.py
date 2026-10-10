"""Kanban API routes - /api/v1/kanban/*

Thin routing layer for kanban view, memory lane, preparation management,
curated timeline, directional timeline, curation triggers, and event CRUD.
Delegates to kanban module services and curation services.
"""
from datetime import date, datetime, timedelta
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import get_current_user, get_current_family, require_auth
from ...core.utils.timezone import local_today, utc_now
from ...db.session import get_db
from ...modules.curation.models import CuratedEvent as CuratedEventModel, CurationJob
from ...modules.curation.schemas import (
    CuratedTimelineResponse,
    CurationJobResponse,
    CurationRequestResponse,
)
from ...modules.curation.services.curation_service import SecretaryCurationService
from ...modules.views.kanban_schemas import (
    EventDetailResponse,
    EventSearchResponse,
    FutureViewResponse,
    InsightFeedGroupedResponse,
    InsightFeedResponse,
    KanbanResponse,
    MemoryLaneResponse,
    OnThisDayResponse,
    PreparationItem,
    TimelineResponse,
    UpdateEventStatusRequest,
)
from ...modules.views.services.event_detail_service import EventDetailService
from ...modules.views.services.kanban_service import KanbanService
from ...modules.views.services.memory_lane_service import MemoryLaneService
from ...modules.views.services.preparation_service import PreparationService
from ...modules.views.services.search_service import SearchService
from ...modules.views.services.timeline_service import TimelineService

router = APIRouter(prefix="/kanban", tags=["Kanban"])


# ==================== Request Models ====================


class PreparationUpdateRequest(BaseModel):
    item_key: Optional[str] = None
    item_index: Optional[int] = None
    done: bool


class PreparationAddRequest(BaseModel):
    item: str
    source: str = "manual"


class PreparationRemoveRequest(BaseModel):
    item_key: Optional[str] = None
    item_index: Optional[int] = None


class CreateEventRequest(BaseModel):
    title: str = Field(..., max_length=500)
    start_time: datetime
    end_time: Optional[datetime] = None
    event_type: Optional[str] = None
    location: Optional[str] = None
    priority: str = "normal"
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


# ==================== Kanban View ====================


@router.get("/", response_model=KanbanResponse, include_in_schema=False)
@router.get("", response_model=KanbanResponse)
async def get_kanban_view(
    limit: int = Query(100, ge=1, le=500, description="Max events to fetch"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get semantic kanban view of future events."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = KanbanService(db)
    return await service.get_kanban_view(
        family_id=effective_family_id,
        user_id=user_id,
        limit=limit,
    )


# ==================== Insight Feed ====================


@router.get("/insight-feed")
async def get_insight_feed(
    limit: int = Query(100, ge=1, le=500, description="Max insights to fetch"),
    format: Optional[Literal["flat", "grouped"]] = Query(
        None, description="Response format: flat (legacy) or grouped",
    ),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get insight-centric feed view with entity-resolved insights.

    Use ``?format=grouped`` to receive insights organized into semantic
    groups (today_focus, relationship_care, coming_up, patterns).
    Default (flat) returns the legacy flat list for backward compatibility.
    """
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = KanbanService(db)
    flat_feed = await service.get_insight_feed(
        family_id=effective_family_id,
        user_id=user_id,
        limit=limit,
    )

    if format == "grouped":
        return service.group_insight_feed(flat_feed)

    return flat_feed


# ==================== Future View (V4) ====================


@router.get("/future-view", response_model=FutureViewResponse)
async def get_future_view(
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get unified future view with trips, AI suggestions, upcoming events, and family pulse."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = KanbanService(db)
    return await service.get_future_view(
        family_id=effective_family_id,
        user_id=user_id,
    )


class AcceptSuggestionRequest(BaseModel):
    """Request to adopt an AI suggestion sub-item into a trip."""
    trip_id: str
    item_text: str
    insight_id: Optional[str] = None


@router.post("/future-view/accept-suggestion")
async def accept_suggestion_to_trip(
    request: AcceptSuggestionRequest,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Accept an AI suggestion sub-item by marking it on the insight record.

    Updates the insight's source_context.adopted_items with the sub-item text.
    When all parsed sub-items are adopted, marks the insight as 'acted'.
    The adopted items appear as tasks in the trip card via _future_view_trips().
    """
    user_id, effective_family_id = require_auth(family_id=family_id)

    if not request.insight_id:
        raise HTTPException(status_code=400, detail="insight_id is required")

    from ...modules.insight.models import Insight

    insight_uuid = UUID(request.insight_id)
    insight = await db.get(Insight, insight_uuid)

    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found")

    # Update source_context with the adopted sub-item
    source_ctx = dict(insight.source_context or {})
    adopted_items: list = list(source_ctx.get("adopted_items", []))

    # Avoid duplicates
    item_text = request.item_text.strip()
    if item_text not in adopted_items:
        adopted_items.append(item_text)

    source_ctx["adopted_items"] = adopted_items
    source_ctx["related_trip_id"] = request.trip_id

    # Check if all parsed sub-items are now adopted → mark as fully acted
    from ...modules.views.services.kanban_service import KanbanService
    content_subs = KanbanService._parse_content_sub_items(
        insight.content or "", str(insight.id), request.trip_id,
    )
    all_sub_labels = {s["label"].strip() for s in content_subs}
    all_adopted = all_sub_labels and all_sub_labels.issubset(set(adopted_items))

    if all_adopted:
        insight.status = "acted"
        insight.acted_at = utc_now()

    from sqlalchemy.orm.attributes import flag_modified
    insight.source_context = source_ctx
    flag_modified(insight, "source_context")
    await db.commit()

    return {"status": "ok", "adopted_count": len(adopted_items)}


@router.get("/future-view/upcoming")
async def get_future_view_upcoming(
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(10, ge=1, le=50, description="Page size"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Paginated upcoming items for lazy loading in the future view."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = KanbanService(db)
    return await service.get_future_view_upcoming_page(
        family_id=effective_family_id,
        offset=offset,
        limit=limit,
    )


# ==================== Memory Lane ====================


@router.get("/memory-lane", response_model=MemoryLaneResponse)
async def get_memory_lane(
    limit: int = Query(50, ge=1, le=200, description="Maximum events"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    year: Optional[int] = Query(None, description="Filter by year"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get memory lane with story groups and yearly stats."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = MemoryLaneService(db)
    return await service.get_memory_lane(
        family_id=effective_family_id,
        user_id=user_id,
        limit=limit,
        offset=offset,
        year=year,
    )


# ==================== On This Day ====================


@router.get("/on-this-day", response_model=OnThisDayResponse)
async def get_on_this_day(
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get events from previous years on the same calendar day."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = MemoryLaneService(db)
    return await service.get_on_this_day(
        family_id=effective_family_id,
        user_id=user_id,
    )


# ==================== Event Search ====================


@router.get("/search", response_model=EventSearchResponse)
async def search_events(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across curated events."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    parsed_types = None
    if event_types:
        parsed_types = [t.strip() for t in event_types.split(",") if t.strip()]

    service = SearchService(db)
    return await service.search_events(
        family_id=effective_family_id,
        query=q,
        event_types=parsed_types,
        limit=limit,
    )


# ==================== Event Search (alias for mobile compatibility) ====================


@router.get("/events/search", response_model=EventSearchResponse)
async def search_events_alias(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Search curated events (alias for /search, used by mobile client)."""
    return await search_events(
        q=q,
        event_types=event_types,
        limit=limit,
        family_id=family_id,
        db=db,
    )


# ==================== Event Detail ====================


@router.get("/events/{event_id}/context", response_model=EventDetailResponse)
async def get_event_context(
    event_id: UUID,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get enriched context for a single event (associations + related memories)."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = EventDetailService(db)
    result = await service.get_event_detail(
        event_id=event_id,
        family_id=effective_family_id,
        user_id=user_id,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return result


# ==================== Preparation CRUD ====================


@router.patch("/events/{event_id}/preparation")
async def update_preparation_item(
    event_id: UUID,
    request: PreparationUpdateRequest,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Toggle done status of a preparation checklist item."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = PreparationService(db)
    result = await service.update_preparation_item(
        event_id=event_id,
        family_id=effective_family_id,
        item_key=request.item_key or "",
        done=request.done,
        item_index=request.item_index,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Event or item not found")

    return {"success": True, "preparation_items": [i.model_dump() for i in result]}


@router.patch("/trips/{trip_id}/preparation")
async def update_trip_preparation_item(
    trip_id: UUID,
    request: PreparationUpdateRequest,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Toggle done status of a trip preparation item by trip_id + item_key."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = PreparationService(db)
    result = await service.update_preparation_item_by_trip(
        trip_id=trip_id,
        family_id=effective_family_id,
        item_key=request.item_key or "",
        done=request.done,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Trip or item not found")

    return {"success": True, "preparation_items": [i.model_dump() for i in result]}


@router.post("/events/{event_id}/preparation")
async def add_preparation_item(
    event_id: UUID,
    request: PreparationAddRequest,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Add a new preparation item to an event."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = PreparationService(db)
    result = await service.add_preparation_item(
        event_id=event_id,
        family_id=effective_family_id,
        item=request.item,
        source=request.source,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return {"success": True, "preparation_items": [i.model_dump() for i in result]}


@router.delete("/events/{event_id}/preparation")
async def remove_preparation_item(
    event_id: UUID,
    request: PreparationRemoveRequest,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Remove a preparation item from an event."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = PreparationService(db)
    result = await service.remove_preparation_item(
        event_id=event_id,
        family_id=effective_family_id,
        item_key=request.item_key or "",
        item_index=request.item_index,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Event or item not found")

    return {"success": True, "preparation_items": [i.model_dump() for i in result]}


# ==================== Curated Timeline ====================


@router.get("/curated-timeline", response_model=CuratedTimelineResponse)
async def get_curated_timeline(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    tier: Optional[str] = Query(None, description="Visibility tier filter: focus, standard, detail"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get AI-curated timeline of deduplicated events."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    if start_date is None:
        start_date = local_today()
    if end_date is None:
        end_date = start_date + timedelta(days=14)

    service = SecretaryCurationService(db)
    return await service.get_curated_timeline(
        family_id=effective_family_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        tier=tier,
    )


# ==================== Directional Timeline ====================


@router.get("/directional-timeline", response_model=TimelineResponse)
async def get_directional_timeline(
    direction: Literal["past", "future"] = Query("future"),
    days: int = Query(14, ge=1, le=30),
    cursor: Optional[str] = Query(None, description="Date cursor (YYYY-MM-DD)"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get directional timeline with day groups (past or future)."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = TimelineService(db)
    return await service.get_timeline(
        user_id=user_id,
        family_id=effective_family_id,
        direction=direction,
        days=days,
        cursor=cursor,
    )


# ==================== Curation Trigger ====================


@router.post("/request-curation", response_model=CurationRequestResponse)
async def request_curation(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual curation job (async via Celery)."""
    from ...modules.curation.tasks import trigger_curation_async

    user_id, effective_family_id = require_auth(family_id=family_id)

    # Create a pending job record so the client has a job_id to poll
    job = CurationJob(
        family_id=effective_family_id,
        trigger_type="manual",
    )
    if start_date:
        job.date_range_start = start_date
    if end_date:
        job.date_range_end = end_date

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch to Celery (respect_cooldown=False for manual triggers)
    dispatched = trigger_curation_async(
        effective_family_id,
        trigger_type="manual",
        respect_cooldown=False,
        start_date=start_date,
        end_date=end_date,
        existing_job_id=job.id,
    )

    if not dispatched:
        job.status = "failed"
        job.error_message = "Failed to dispatch curation task to broker."
        job.completed_at = utc_now()
        await db.commit()
        return CurationRequestResponse(
            job_id=str(job.id),
            status="failed",
            message="Failed to dispatch curation task",
        )

    return CurationRequestResponse(
        job_id=str(job.id),
        status="pending",
        message="Curation job started",
    )


@router.get("/curation-status/{job_id}", response_model=CurationJobResponse)
async def get_curation_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get status of a curation job."""
    require_auth()

    stmt = select(CurationJob).where(CurationJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="Curation job not found")

    return CurationJobResponse(
        job_id=str(job.id),
        status=job.status,
        trigger_type=job.trigger_type,
        date_range_start=job.date_range_start,
        date_range_end=job.date_range_end,
        events_processed=job.events_processed,
        events_curated=job.events_curated,
        associations_created=job.associations_created,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


# ==================== Event CRUD ====================


@router.post("/events")
async def create_event(
    request: CreateEventRequest,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Create a new curated event via mini-curation."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = SecretaryCurationService(db)
    event, _hints = await service.mini_curate(
        family_id=effective_family_id,
        user_id=user_id,
        title=request.title,
        event_type=request.event_type or "other",
        start_time=request.start_time,
        end_time=request.end_time,
        location=request.location,
    )

    if event is None:
        raise HTTPException(status_code=500, detail="Failed to create event")

    return {
        "id": str(event.id),
        "title": event.title,
        "status": event.status,
    }


@router.patch("/events/{event_id}/status")
async def update_event_status(
    event_id: UUID,
    request: UpdateEventStatusRequest,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Update the status of a curated event."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    stmt = select(CuratedEventModel).where(
        and_(
            CuratedEventModel.id == event_id,
            CuratedEventModel.family_id == effective_family_id,
        )
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event.status = request.status
    if request.notes is not None:
        event.notes = request.notes
    await db.commit()

    return {"success": True, "id": str(event.id), "status": event.status}


@router.delete("/events/{event_id}")
async def cancel_event(
    event_id: UUID,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Cancel (soft-delete) a curated event."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    stmt = select(CuratedEventModel).where(
        and_(
            CuratedEventModel.id == event_id,
            CuratedEventModel.family_id == effective_family_id,
        )
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event.status = "cancelled"
    event.is_active = False
    await db.commit()

    return {"success": True, "id": str(event.id)}



# NOTE: Legacy endpoint /future-view/accept-suggestion is defined above (line ~158)
# as accept_suggestion_to_trip(). It handles sub-item level adoption.
# Clients should eventually migrate to POST /api/v1/insights/{id}/adopt
# for whole-insight adoption.
