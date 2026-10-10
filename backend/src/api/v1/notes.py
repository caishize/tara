"""Secretary Notes API routes - /api/v1/notes/*

CRUD endpoints for L1 fact management (secretary notes).
Users can view, edit, confirm, and archive the AI-extracted facts
that feed into the ContextAssembler L1 layer.

Endpoints:
    GET    /notes             - List notes (with optional category/status filter)
    GET    /notes/{note_id}   - Get a single note
    POST   /notes             - Create a manual note
    PUT    /notes/{note_id}   - Update note fields
    PATCH  /notes/{note_id}   - Partial update note fields
    DELETE /notes/{note_id}   - Archive (soft-delete) a note
    POST   /notes/{id}/confirm - User confirms note accuracy
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import get_current_user, get_current_family
from ...db.session import get_db
from ...modules.memory.secretary_note_model import (
    SecretaryNote,
    NoteCategory,
    NoteStatus,
)
from ...modules.memory.secretary_note_service import SecretaryNoteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["Notes"])


# ==================== Request / Response Models ====================


class NoteResponse(BaseModel):
    id: str
    category: str
    title: str
    content: str
    confidence: float = 0.8
    is_user_confirmed: bool = False
    priority: int = 5
    status: str = "active"
    life_type: str = "permanent"
    valid_until: Optional[datetime] = None
    version: int = 1
    observation_count: int = 1
    trigger_keywords: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    superseded_by: Optional[str] = None
    contradiction_flags: Optional[list] = None


class NoteListResponse(BaseModel):
    notes: List[NoteResponse]
    total: int


class NoteCreateRequest(BaseModel):
    category: str = Field(..., description="Note category: preference, routine, important, todo, observation")
    title: str = Field(..., min_length=1, max_length=200, description="Note title")
    content: str = Field(..., min_length=1, description="Note content")
    trigger_keywords: Optional[List[str]] = Field(None, description="Keywords that trigger this note")
    priority: int = Field(5, ge=1, le=10, description="Priority level (1-10)")


class NoteUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = Field(None, description="Note category")
    priority: Optional[int] = Field(None, ge=1, le=10)
    trigger_keywords: Optional[List[str]] = None


# ==================== Helpers ====================


def _note_to_response(note: SecretaryNote) -> NoteResponse:
    return NoteResponse(
        id=str(note.id),
        category=note.category or "",
        title=note.title or "",
        content=note.content or "",
        confidence=note.confidence or 0.8,
        is_user_confirmed=note.is_user_confirmed or False,
        priority=note.priority or 5,
        status=note.status or "active",
        life_type=note.life_type or "permanent",
        valid_until=note.valid_until,
        version=note.version or 1,
        observation_count=note.observation_count or 1,
        trigger_keywords=note.trigger_keywords or [],
        created_at=note.created_at,
        updated_at=note.updated_at,
        superseded_by=str(note.superseded_by) if note.superseded_by else None,
        contradiction_flags=note.contradiction_flags,
    )


# ==================== Helpers (ownership) ====================


async def _get_owned_note(
    note_id: UUID,
    user_id: UUID,
    family_id: UUID,
    db: AsyncSession,
) -> SecretaryNote:
    """Fetch a note and verify that it belongs to the requesting user/family.

    Raises HTTPException 404 if not found or not owned.
    """
    query = select(SecretaryNote).where(
        and_(
            SecretaryNote.id == note_id,
            SecretaryNote.user_id == user_id,
            SecretaryNote.family_id == family_id,
        )
    )
    result = await db.execute(query)
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


def _validate_category(category: str) -> None:
    """Raise 400 if category is not a valid NoteCategory value."""
    valid_categories = [c.value for c in NoteCategory]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category: {category}. Must be one of {valid_categories}",
        )


# ==================== Routes ====================


@router.get("", response_model=NoteListResponse)
async def list_notes(
    category: Optional[str] = Query(None, description="Filter by category"),
    status_filter: Optional[str] = Query(
        "active", alias="status", description="Filter by status"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum notes to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """List secretary notes for the current user.

    Supports filtering by category (preference, routine, important, todo,
    observation) and status (active, completed, archived, superseded).
    """
    conditions = [
        SecretaryNote.user_id == user_id,
        SecretaryNote.family_id == family_id,
    ]
    if category:
        _validate_category(category)
        conditions.append(SecretaryNote.category == category)
    if status_filter:
        valid_statuses = [s.value for s in NoteStatus]
        if status_filter not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status_filter}. Must be one of {valid_statuses}",
            )
        conditions.append(SecretaryNote.status == status_filter)

    query = (
        select(SecretaryNote)
        .where(and_(*conditions))
        .order_by(SecretaryNote.priority.desc(), SecretaryNote.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    notes = list(result.scalars().all())

    from sqlalchemy import func

    count_query = select(func.count()).select_from(SecretaryNote).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return NoteListResponse(
        notes=[_note_to_response(n) for n in notes],
        total=total,
    )


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get a single secretary note by ID."""
    note = await _get_owned_note(note_id, user_id, family_id, db)
    return _note_to_response(note)


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: NoteCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Create a new manual secretary note.

    User-created notes are automatically set to confidence=1.0
    and is_user_confirmed=True.
    """
    _validate_category(body.category)

    service = SecretaryNoteService(db)
    note = await service.create_note(
        user_id=user_id,
        family_id=family_id,
        category=body.category,
        title=body.title,
        content=body.content,
        trigger_keywords=body.trigger_keywords,
        priority=body.priority,
    )
    return _note_to_response(note)


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    body: NoteUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Update a secretary note (full update). Increments version on content/title change."""
    note = await _get_owned_note(note_id, user_id, family_id, db)
    return await _apply_note_update(note, body, db)


@router.patch("/{note_id}", response_model=NoteResponse)
async def patch_note(
    note_id: UUID,
    body: NoteUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Partial update of a secretary note. Increments version on content/title change."""
    note = await _get_owned_note(note_id, user_id, family_id, db)
    return await _apply_note_update(note, body, db)


async def _apply_note_update(
    note: SecretaryNote,
    body: NoteUpdateRequest,
    db: AsyncSession,
) -> NoteResponse:
    """Shared logic for PUT and PATCH note updates."""
    update_kwargs = {}
    if body.title is not None:
        update_kwargs["title"] = body.title
    if body.content is not None:
        update_kwargs["content"] = body.content
    if body.category is not None:
        _validate_category(body.category)
        update_kwargs["category"] = body.category
    if body.priority is not None:
        update_kwargs["priority"] = body.priority
    if body.trigger_keywords is not None:
        update_kwargs["trigger_keywords"] = body.trigger_keywords

    if not update_kwargs:
        return _note_to_response(note)

    # Increment version if content or title changed
    if "title" in update_kwargs or "content" in update_kwargs:
        note.increment_version()

    service = SecretaryNoteService(db)
    updated = await service.update_note(note.id, **update_kwargs)
    if updated is None:
        raise HTTPException(status_code=404, detail="Note not found")

    return _note_to_response(updated)


@router.delete("/{note_id}", response_model=NoteResponse)
async def archive_note(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Archive (soft-delete) a secretary note."""
    await _get_owned_note(note_id, user_id, family_id, db)

    service = SecretaryNoteService(db)
    archived = await service.archive_note(note_id)
    if archived is None:
        raise HTTPException(status_code=404, detail="Note not found")

    return _note_to_response(archived)


@router.post("/{note_id}/confirm", response_model=NoteResponse)
async def confirm_note(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """User confirms that a secretary note is accurate.

    Sets confidence to 1.0 and is_user_confirmed to True.
    """
    await _get_owned_note(note_id, user_id, family_id, db)

    service = SecretaryNoteService(db)
    confirmed = await service.confirm_note(note_id)
    if confirmed is None:
        raise HTTPException(status_code=404, detail="Note not found")

    return _note_to_response(confirmed)
