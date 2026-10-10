"""
Itinerary Version API endpoints.
Manages multiple versions of trip itineraries.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
import uuid

from ....db.session import get_db
from ....core.auth import get_current_user, get_current_family
from ..models.itinerary_version import ItineraryVersion
from ..models.trip_plan import TripPlan
from ..models.trip_itinerary import TripItinerary
from ..schemas.itinerary_version import (
    ItineraryVersionResponse,
    ItineraryVersionSummaryResponse,
    ItineraryVersionListResponse,
    ItineraryVersionUpdate,
    ActivateVersionRequest,
)

router = APIRouter(prefix="/trips/plans/{trip_id}/versions", tags=["trip-itinerary-versions"])


@router.get("", response_model=ItineraryVersionListResponse)
async def list_versions(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get all itinerary versions for a trip."""
    # Verify trip exists
    trip_result = await db.execute(
        select(TripPlan).where(TripPlan.trip_id == trip_id)
    )
    if not trip_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Travel plan not found")

    # Get all versions
    result = await db.execute(
        select(ItineraryVersion)
        .where(ItineraryVersion.trip_id == trip_id)
        .order_by(ItineraryVersion.version_number.desc())
    )
    versions = result.scalars().all()

    items = []
    active_version_id = None

    for version in versions:
        total_days = len(version.schedules) if version.schedules else 0
        total_activities = sum(
            len(day.get("schedule", []))
            for day in (version.schedules or [])
        )

        if version.is_active:
            active_version_id = version.version_id

        items.append(ItineraryVersionSummaryResponse(
            version_id=version.version_id,
            version_number=version.version_number,
            version_name=version.version_name,
            style_tags=version.style_tags or [],
            is_active=version.is_active,
            total_estimated_cost=version.total_estimated_cost,
            total_days=total_days,
            total_activities=total_activities,
            created_at=version.created_at,
        ))

    return ItineraryVersionListResponse(
        items=items,
        total=len(items),
        active_version_id=active_version_id,
    )


@router.get("/{version_id}", response_model=ItineraryVersionResponse)
async def get_version(
    trip_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get a specific itinerary version."""
    result = await db.execute(
        select(ItineraryVersion)
        .where(
            ItineraryVersion.trip_id == trip_id,
            ItineraryVersion.version_id == version_id,
        )
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    total_days = len(version.schedules) if version.schedules else 0
    total_activities = sum(
        len(day.get("schedule", []))
        for day in (version.schedules or [])
    )

    return ItineraryVersionResponse(
        version_id=version.version_id,
        trip_id=version.trip_id,
        version_number=version.version_number,
        version_name=version.version_name,
        style_tags=version.style_tags or [],
        is_active=version.is_active,
        total_estimated_cost=version.total_estimated_cost,
        schedules=version.schedules or [],
        generation_config=version.generation_config,
        created_at=version.created_at,
        updated_at=version.updated_at,
        total_days=total_days,
        total_activities=total_activities,
    )


@router.put("/{version_id}", response_model=ItineraryVersionResponse)
async def update_version(
    trip_id: UUID,
    version_id: UUID,
    update_data: ItineraryVersionUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Update version name or activate it."""
    result = await db.execute(
        select(ItineraryVersion)
        .where(
            ItineraryVersion.trip_id == trip_id,
            ItineraryVersion.version_id == version_id,
        )
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Update fields
    if update_data.version_name is not None:
        version.version_name = update_data.version_name

    if update_data.is_active is not None and update_data.is_active:
        # Deactivate all other versions first
        await db.execute(
            select(ItineraryVersion)
            .where(ItineraryVersion.trip_id == trip_id)
        )
        all_versions = (await db.execute(
            select(ItineraryVersion).where(ItineraryVersion.trip_id == trip_id)
        )).scalars().all()

        for v in all_versions:
            v.is_active = (v.version_id == version_id)

        # Also update the main itinerary table with this version's schedules
        await _apply_version_to_itinerary(db, trip_id, version)

    await db.commit()
    await db.refresh(version)

    total_days = len(version.schedules) if version.schedules else 0
    total_activities = sum(
        len(day.get("schedule", []))
        for day in (version.schedules or [])
    )

    return ItineraryVersionResponse(
        version_id=version.version_id,
        trip_id=version.trip_id,
        version_number=version.version_number,
        version_name=version.version_name,
        style_tags=version.style_tags or [],
        is_active=version.is_active,
        total_estimated_cost=version.total_estimated_cost,
        schedules=version.schedules or [],
        generation_config=version.generation_config,
        created_at=version.created_at,
        updated_at=version.updated_at,
        total_days=total_days,
        total_activities=total_activities,
    )


@router.post("/activate")
async def activate_version(
    trip_id: UUID,
    request: ActivateVersionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Activate a specific version and apply it to the main itinerary."""
    result = await db.execute(
        select(ItineraryVersion)
        .where(
            ItineraryVersion.trip_id == trip_id,
            ItineraryVersion.version_id == request.version_id,
        )
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Deactivate all versions and activate the selected one
    all_versions = (await db.execute(
        select(ItineraryVersion).where(ItineraryVersion.trip_id == trip_id)
    )).scalars().all()

    for v in all_versions:
        v.is_active = (v.version_id == request.version_id)

    # Apply version schedules to main itinerary
    await _apply_version_to_itinerary(db, trip_id, version)

    await db.commit()

    return {
        "message": "Version activated successfully",
        "version_id": str(request.version_id),
        "version_name": version.version_name or f"方案 {version.version_number}",
    }


@router.delete("/{version_id}")
async def delete_version(
    trip_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Delete a version. Cannot delete the active version."""
    result = await db.execute(
        select(ItineraryVersion)
        .where(
            ItineraryVersion.trip_id == trip_id,
            ItineraryVersion.version_id == version_id,
        )
    )
    version = result.scalar_one_or_none()

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    if version.is_active:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the active version. Activate another version first."
        )

    await db.delete(version)
    await db.commit()

    return {"message": "Version deleted successfully", "version_id": str(version_id)}


async def _apply_version_to_itinerary(
    db: AsyncSession,
    trip_id: UUID,
    version: ItineraryVersion
):
    """Apply a version's schedules to the main trip_itineraries table."""
    # Delete existing itineraries
    existing = (await db.execute(
        select(TripItinerary).where(TripItinerary.trip_id == trip_id)
    )).scalars().all()

    for itinerary in existing:
        await db.delete(itinerary)

    # Create new itineraries from version schedules
    for day_data in (version.schedules or []):
        day_number = day_data.get("day_number", 1)
        schedule = day_data.get("schedule", [])
        packing_notes = day_data.get("packing_notes")

        new_itinerary = TripItinerary(
            itinerary_id=uuid.uuid4(),
            trip_id=trip_id,
            day_number=day_number,
            schedule=schedule,
            packing_notes=packing_notes,
        )
        db.add(new_itinerary)


async def save_itinerary_as_version(
    db: AsyncSession,
    trip_id: UUID,
    schedules: list,
    style_tags: list = None,
    generation_config: dict = None,
    version_name: str = None,
    set_active: bool = True,
) -> ItineraryVersion:
    """
    Helper function to save current itinerary as a new version.
    Called when generating new itinerary.
    """
    # Get next version number
    max_result = await db.execute(
        select(func.max(ItineraryVersion.version_number))
        .where(ItineraryVersion.trip_id == trip_id)
    )
    max_version = max_result.scalar() or 0
    next_version = max_version + 1

    # Calculate total cost
    total_cost = 0.0
    for day in schedules:
        for activity in day.get("schedule", []):
            cost = activity.get("estimated_cost")
            if cost:
                total_cost += float(cost)

    # Deactivate other versions if setting active
    if set_active:
        all_versions = (await db.execute(
            select(ItineraryVersion).where(ItineraryVersion.trip_id == trip_id)
        )).scalars().all()
        for v in all_versions:
            v.is_active = False

    # Create new version
    new_version = ItineraryVersion(
        version_id=uuid.uuid4(),
        trip_id=trip_id,
        version_number=next_version,
        version_name=version_name or f"方案 {next_version}",
        style_tags=style_tags or [],
        is_active=set_active,
        total_estimated_cost=total_cost if total_cost > 0 else None,
        schedules=schedules,
        generation_config=generation_config,
    )
    db.add(new_version)

    return new_version
