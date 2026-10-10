"""
People (Person Profiles) API endpoints.

Unified person management - family members + external contacts.
Split from members.py to keep file sizes under 800 lines.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from ...db.session import get_db
from ...core.auth import get_current_user, get_current_family
from .member_schemas import PersonProfileResponse


router = APIRouter(prefix="/members", tags=["People"])


def _person_to_dict(p) -> dict:
    """Convert PersonProfile DTO to dict for API response."""
    return {
        "id": p.id,
        "family_id": p.family_id,
        "name": p.name,
        "member_id": p.member_id,
        "aliases": p.aliases,
        "relationship": p.relationship,
        "relationship_context": p.relationship_context,
        "organization": p.organization,
        "location": p.location,
        "preferences": p.preferences,
        "favor_balance": p.favor_balance,
        "mention_count": p.mention_count,
        "last_mentioned_at": (
            p.last_mentioned_at.isoformat() if p.last_mentioned_at else None
        ),
        "importance": p.importance,
        "needs_contact": p.needs_contact,
        "owes_favor": p.owes_favor,
        "status": p.status,
    }


@router.get("/people", response_model=List[PersonProfileResponse])
async def list_people(
    min_importance: Optional[float] = None,
    relationship: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """List person profiles (family members + external contacts)."""
    from ...modules.member.person_service import PersonService

    service = PersonService(db)
    profiles = await service.list_people(
        family_id=str(family_id),
        min_importance=min_importance,
        relationship=relationship,
        limit=limit,
        offset=offset,
    )
    return [_person_to_dict(p) for p in profiles]


@router.get("/people/neglected", response_model=List[PersonProfileResponse])
async def get_neglected_people(
    threshold_days: int = 90,
    min_importance: float = 5.0,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get important people who haven't been contacted recently."""
    from ...modules.member.person_service import PersonService

    service = PersonService(db)
    profiles = await service.get_neglected(
        family_id=str(family_id),
        threshold_days=threshold_days,
        min_importance=min_importance,
    )
    return [_person_to_dict(p) for p in profiles]


@router.get("/people/favors", response_model=List[PersonProfileResponse])
async def get_favor_balances(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get people with non-zero favor balances."""
    from ...modules.member.person_service import PersonService

    service = PersonService(db)
    profiles = await service.get_people_with_favors(family_id=str(family_id))
    return [_person_to_dict(p) for p in profiles]


@router.get("/people/{person_id}", response_model=PersonProfileResponse)
async def get_person(
    person_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get a person profile by ID."""
    from ...modules.member.person_service import PersonService

    service = PersonService(db)
    profile = await service.get_profile(
        person_id=str(person_id),
        family_id=str(family_id),
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        )
    return _person_to_dict(profile)
