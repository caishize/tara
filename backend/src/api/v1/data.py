"""Data Management API routes - /api/v1/data/*

Provides data statistics and deletion endpoints for user data management.
All delete operations require password verification.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ...core.auth import get_current_user, get_current_family
from ...core.auth.auth_service import verify_password
from ...db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["Data Management"])


# ==================== Request / Response Models ====================


class DataStatsResponse(BaseModel):
    chat_sessions: int = 0
    chat_messages: int = 0
    memories: int = 0
    insights: int = 0
    events: int = 0
    trips: int = 0
    gifts: int = 0


class DeleteRequest(BaseModel):
    password: str


class DeleteResponse(BaseModel):
    success: bool
    message: str
    deleted_count: int = 0


# ==================== Helpers ====================


async def _verify_user_password(
    db: AsyncSession, user_id: UUID, password: str
) -> None:
    """Verify the current user's password. Raises 403 on failure."""
    from ...modules.member.models import User

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect password",
        )


async def _count_table(db: AsyncSession, model, *conditions) -> int:
    """Count rows matching conditions."""
    stmt = select(func.count()).select_from(model).where(and_(*conditions))
    result = await db.execute(stmt)
    return result.scalar() or 0


# ==================== Endpoints ====================


@router.get("/stats", response_model=DataStatsResponse)
async def get_data_stats(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get counts of all user data categories."""
    from ...modules.conversation.models import (
        AssistantChatSession,
        ConversationMessage,
    )
    from ...modules.memory.models import ConversationMemory
    from ...modules.insight.models import Insight
    from ...modules.curation.models import CuratedEvent
    from ...modules.trip.models.trip_plan import TripPlan
    from ...modules.gift.models import GiftHistory

    sessions_count = await _count_table(
        db, AssistantChatSession,
        AssistantChatSession.user_id == user_id,
    )

    # Count messages via sessions belonging to the user
    msg_stmt = (
        select(func.count())
        .select_from(ConversationMessage)
        .join(
            AssistantChatSession,
            ConversationMessage.session_id == AssistantChatSession.id,
        )
        .where(AssistantChatSession.user_id == user_id)
    )
    msg_result = await db.execute(msg_stmt)
    messages_count = msg_result.scalar() or 0

    memories_count = await _count_table(
        db, ConversationMemory,
        ConversationMemory.family_id == family_id,
    )
    insights_count = await _count_table(
        db, Insight,
        Insight.family_id == family_id,
    )
    events_count = await _count_table(
        db, CuratedEvent,
        CuratedEvent.family_id == family_id,
    )
    trips_count = await _count_table(
        db, TripPlan,
        TripPlan.family_id == family_id,
    )
    gifts_count = await _count_table(
        db, GiftHistory,
        GiftHistory.family_id == family_id,
    )

    return DataStatsResponse(
        chat_sessions=sessions_count,
        chat_messages=messages_count,
        memories=memories_count,
        insights=insights_count,
        events=events_count,
        trips=trips_count,
        gifts=gifts_count,
    )


@router.delete("/chat-history", response_model=DeleteResponse)
async def delete_chat_history(
    body: DeleteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Delete all chat history for the current user. Requires password."""
    await _verify_user_password(db, user_id, body.password)

    from ...modules.conversation.models import (
        AssistantChatSession,
        ConversationMessage,
        ToolExecutionLog,
    )

    # Get user's session IDs
    session_ids_stmt = select(AssistantChatSession.id).where(
        AssistantChatSession.user_id == user_id,
    )
    session_result = await db.execute(session_ids_stmt)
    session_ids = [row[0] for row in session_result.all()]

    deleted = 0
    if session_ids:
        # Delete messages
        msg_stmt = delete(ConversationMessage).where(
            ConversationMessage.session_id.in_(session_ids)
        )
        msg_result = await db.execute(msg_stmt)
        deleted += msg_result.rowcount or 0

        # Delete tool execution logs
        log_stmt = delete(ToolExecutionLog).where(
            ToolExecutionLog.session_id.in_(session_ids)
        )
        log_result = await db.execute(log_stmt)
        deleted += log_result.rowcount or 0

        # Delete sessions
        sess_stmt = delete(AssistantChatSession).where(
            AssistantChatSession.user_id == user_id,
        )
        sess_result = await db.execute(sess_stmt)
        deleted += sess_result.rowcount or 0

    await db.commit()

    return DeleteResponse(
        success=True,
        message="Chat history deleted successfully",
        deleted_count=deleted,
    )


@router.delete("/memories", response_model=DeleteResponse)
async def delete_memories(
    body: DeleteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Delete all memories and related data for the family. Requires password."""
    await _verify_user_password(db, user_id, body.password)

    from ...modules.memory.models import (
        ConversationMemory,
        MemoryAssociation,
        MemorySummary,
    )
    from ...modules.memory.secretary_note_model import SecretaryNote
    from ...modules.insight.models import Insight, InsightFeedback

    deleted = 0

    # Delete insight feedbacks first (FK to insights)
    fb_stmt = delete(InsightFeedback).where(
        InsightFeedback.family_id == family_id,
    )
    fb_result = await db.execute(fb_stmt)
    deleted += fb_result.rowcount or 0

    # Delete insights (FK to conversation_memories)
    ins_stmt = delete(Insight).where(
        Insight.family_id == family_id,
    )
    ins_result = await db.execute(ins_stmt)
    deleted += ins_result.rowcount or 0

    # Delete memory associations (FK to conversation_memories)
    # Associations reference memory IDs, delete those belonging to the family's memories
    family_mem_ids = select(ConversationMemory.id).where(
        ConversationMemory.family_id == family_id,
    )
    assoc_stmt = delete(MemoryAssociation).where(
        MemoryAssociation.memory_id_a.in_(family_mem_ids)
    )
    assoc_result = await db.execute(assoc_stmt)
    deleted += assoc_result.rowcount or 0

    # Delete memory summaries
    summ_stmt = delete(MemorySummary).where(
        MemorySummary.family_id == family_id,
    )
    summ_result = await db.execute(summ_stmt)
    deleted += summ_result.rowcount or 0

    # Delete secretary notes
    note_stmt = delete(SecretaryNote).where(
        SecretaryNote.family_id == family_id,
    )
    note_result = await db.execute(note_stmt)
    deleted += note_result.rowcount or 0

    # Delete conversation memories
    mem_stmt = delete(ConversationMemory).where(
        ConversationMemory.family_id == family_id,
    )
    mem_result = await db.execute(mem_stmt)
    deleted += mem_result.rowcount or 0

    await db.commit()

    return DeleteResponse(
        success=True,
        message="Memories and related data deleted successfully",
        deleted_count=deleted,
    )


@router.delete("/events", response_model=DeleteResponse)
async def delete_events(
    body: DeleteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Delete all curated events and related data for the family. Requires password."""
    await _verify_user_password(db, user_id, body.password)

    from ...modules.curation.models import (
        CuratedEvent,
        EventAssociation,
        PreparationItem,
    )

    deleted = 0

    # Get family event IDs for cascading deletes
    family_event_ids = select(CuratedEvent.id).where(
        CuratedEvent.family_id == family_id,
    )

    # Delete preparation items (FK to curated_events)
    prep_stmt = delete(PreparationItem).where(
        PreparationItem.event_id.in_(family_event_ids)
    )
    prep_result = await db.execute(prep_stmt)
    deleted += prep_result.rowcount or 0

    # Delete event associations (FK to curated_events)
    assoc_stmt = delete(EventAssociation).where(
        EventAssociation.family_id == family_id,
    )
    assoc_result = await db.execute(assoc_stmt)
    deleted += assoc_result.rowcount or 0

    # Delete curated events
    event_stmt = delete(CuratedEvent).where(
        CuratedEvent.family_id == family_id,
    )
    event_result = await db.execute(event_stmt)
    deleted += event_result.rowcount or 0

    await db.commit()

    return DeleteResponse(
        success=True,
        message="Events and related data deleted successfully",
        deleted_count=deleted,
    )


@router.delete("/all", response_model=DeleteResponse)
async def delete_all_data(
    body: DeleteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Delete all user data (chat, memories, events). Requires password."""
    await _verify_user_password(db, user_id, body.password)

    total_deleted = 0

    # Delete chat history
    from ...modules.conversation.models import (
        AssistantChatSession,
        ConversationMessage,
        ToolExecutionLog,
    )

    session_ids_stmt = select(AssistantChatSession.id).where(
        AssistantChatSession.user_id == user_id,
    )
    session_result = await db.execute(session_ids_stmt)
    session_ids = [row[0] for row in session_result.all()]

    if session_ids:
        msg_result = await db.execute(
            delete(ConversationMessage).where(
                ConversationMessage.session_id.in_(session_ids)
            )
        )
        total_deleted += msg_result.rowcount or 0

        log_result = await db.execute(
            delete(ToolExecutionLog).where(
                ToolExecutionLog.session_id.in_(session_ids)
            )
        )
        total_deleted += log_result.rowcount or 0

        sess_result = await db.execute(
            delete(AssistantChatSession).where(
                AssistantChatSession.user_id == user_id,
            )
        )
        total_deleted += sess_result.rowcount or 0

    # Delete memories and insights
    from ...modules.memory.models import (
        ConversationMemory,
        MemoryAssociation,
        MemorySummary,
    )
    from ...modules.memory.secretary_note_model import SecretaryNote
    from ...modules.insight.models import Insight, InsightFeedback

    fb_result = await db.execute(
        delete(InsightFeedback).where(InsightFeedback.family_id == family_id)
    )
    total_deleted += fb_result.rowcount or 0

    ins_result = await db.execute(
        delete(Insight).where(Insight.family_id == family_id)
    )
    total_deleted += ins_result.rowcount or 0

    family_mem_ids = select(ConversationMemory.id).where(
        ConversationMemory.family_id == family_id,
    )
    assoc_result = await db.execute(
        delete(MemoryAssociation).where(
            MemoryAssociation.memory_id_a.in_(family_mem_ids)
        )
    )
    total_deleted += assoc_result.rowcount or 0

    summ_result = await db.execute(
        delete(MemorySummary).where(MemorySummary.family_id == family_id)
    )
    total_deleted += summ_result.rowcount or 0

    note_result = await db.execute(
        delete(SecretaryNote).where(SecretaryNote.family_id == family_id)
    )
    total_deleted += note_result.rowcount or 0

    mem_result = await db.execute(
        delete(ConversationMemory).where(ConversationMemory.family_id == family_id)
    )
    total_deleted += mem_result.rowcount or 0

    # Delete events
    from ...modules.curation.models import (
        CuratedEvent,
        EventAssociation,
        PreparationItem,
    )

    family_event_ids = select(CuratedEvent.id).where(
        CuratedEvent.family_id == family_id,
    )
    prep_result = await db.execute(
        delete(PreparationItem).where(
            PreparationItem.event_id.in_(family_event_ids)
        )
    )
    total_deleted += prep_result.rowcount or 0

    ea_result = await db.execute(
        delete(EventAssociation).where(EventAssociation.family_id == family_id)
    )
    total_deleted += ea_result.rowcount or 0

    ev_result = await db.execute(
        delete(CuratedEvent).where(CuratedEvent.family_id == family_id)
    )
    total_deleted += ev_result.rowcount or 0

    await db.commit()

    return DeleteResponse(
        success=True,
        message="All data deleted successfully",
        deleted_count=total_deleted,
    )
