"""Graph API routes - /api/v1/graph/*

Thin routing layer for event graph visualization and association management.
Delegates to graph module services.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import require_auth
from ...db.session import get_db
from ...modules.views.graph_schemas import (
    AssociationDetail,
    CreateAssociationRequest,
    EventGraphResponse,
    TripSummary,
)
from ...modules.views.services.association_manager import AssociationManager
from ...modules.views.services.graph_service import EventGraphService

router = APIRouter(prefix="/graph", tags=["Graph"])


# ==================== Trip Listing ====================


@router.get("/trips/upcoming", response_model=List[TripSummary])
async def get_upcoming_trips(
    limit: int = Query(5, ge=1, le=20, description="Maximum trips to return"),
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get upcoming trips for the graph trip selector."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = EventGraphService(db)
    return await service.get_upcoming_trips(
        user_id=user_id,
        family_id=effective_family_id,
        limit=limit,
    )


# ==================== Trip Graph ====================


@router.get("/trip/{trip_id}", response_model=EventGraphResponse)
async def get_trip_graph(
    trip_id: str,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get the event graph for a specific trip."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = EventGraphService(db)
    try:
        trip_uuid = UUID(trip_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid trip_id format")

    result = await service.get_event_graph(
        trip_id=trip_uuid,
        user_id=user_id,
        family_id=effective_family_id,
    )

    return result


# ==================== Event-Centered Graph ====================


@router.get("/event/{event_id}", response_model=EventGraphResponse)
async def get_event_graph(
    event_id: UUID,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get the event graph centered on a specific event."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    service = EventGraphService(db)
    result = await service.get_event_centered_graph(
        event_id=event_id,
        user_id=user_id,
        family_id=effective_family_id,
    )

    return result


# ==================== Event Context ====================


@router.get("/event/{event_id}/context")
async def get_event_context(
    event_id: UUID,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get enriched context for a single event (associations + related memories)."""
    from ...modules.views.services.event_detail_service import EventDetailService

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


# ==================== Association Management ====================


@router.post("/associations", response_model=AssociationDetail)
async def create_association(
    request: CreateAssociationRequest,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Create a new association for an event."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    try:
        event_uuid = UUID(request.event_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid event_id format")

    manager = AssociationManager(db)
    try:
        assoc = await manager.add_association(
            event_id=event_uuid,
            family_id=effective_family_id,
            target_type=request.target_type,
            target_id=request.target_id,
            association_type=request.association_type,
            title=request.title,
            reason=request.reason,
            priority=request.priority,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Event not found")

    detail = await manager.get_association_detail(assoc.id)
    if detail is None:
        raise HTTPException(status_code=500, detail="Failed to read created association")

    return detail


@router.post("/associations/{association_id}/confirm")
async def confirm_association(
    association_id: UUID,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Confirm an association."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    manager = AssociationManager(db)
    result = await manager.confirm_association(association_id=association_id)

    if not result:
        raise HTTPException(status_code=404, detail="Association not found")

    return {"success": True, "association_id": str(association_id)}


@router.post("/associations/{association_id}/dismiss")
async def dismiss_association(
    association_id: UUID,
    family_id: Optional[UUID] = Query(None, description="Family ID"),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss an association."""
    user_id, effective_family_id = require_auth(family_id=family_id)

    manager = AssociationManager(db)
    result = await manager.dismiss_association(association_id=association_id)

    if not result:
        raise HTTPException(status_code=404, detail="Association not found")

    return {"success": True, "association_id": str(association_id)}
