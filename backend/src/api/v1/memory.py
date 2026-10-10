"""Memory API routes - /api/v1/memory/*

Thin routing layer for memory management and insights.
Delegates to memory module services.
"""
import logging
import re
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import require_auth
from ...db.session import get_db
from ...modules.memory.repository import MemoryRepository
from ...modules.memory.recall_service import MemoryRecallService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory"])


# ==================== Response Models ====================


class MemoryResponse(BaseModel):
    id: str
    memory_type: str
    content: str
    summary: str
    entities: dict = {}
    tags: List[str] = []
    importance: int = 5
    confidence: float = 0.8
    status: str = "active"
    created_at: datetime
    expires_at: Optional[datetime] = None
    recall_count: int = 0
    source_session_id: Optional[str] = None


class MemoryListResponse(BaseModel):
    memories: List[MemoryResponse]
    total: int


class MemoryRecallResponse(BaseModel):
    memories: List[MemoryResponse]
    context_summary: str
    recall_count: int


class InsightResponse(BaseModel):
    id: str
    insight_type: str
    title: str
    content: str
    priority: int = 5
    urgency: str = "normal"
    related_memory_ids: List[str] = []
    action_options: List[Any] = []
    action_data: dict = {}
    status: str = "pending"
    created_at: datetime


class InsightListResponse(BaseModel):
    insights: List[InsightResponse]
    total: int


# ==================== Helpers ====================


# Keys in entities JSONB that are internal references (used for DB queries)
# and should NOT be exposed to the frontend.
_INTERNAL_ENTITY_KEYS = {
    "trip_id", "member_id", "session_id", "event_id",
    "compressed_from", "original_count",
    "_is_continuation",
}

_UUID_RE = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
)


def _strip_internal_entities(entities: dict) -> dict:
    """Remove internal metadata keys from entities before sending to client."""
    if not entities:
        return {}
    result = {}
    for key, value in entities.items():
        # Skip known internal keys
        if key in _INTERNAL_ENTITY_KEYS:
            continue
        # Skip any key ending with _id / _ids (generic ID references)
        if key.endswith("_id") or key.endswith("_ids"):
            continue
        # Skip keys starting with underscore (private/meta)
        if key.startswith("_"):
            continue
        # Skip values that are UUIDs
        if isinstance(value, str) and _UUID_RE.match(value):
            continue
        # Skip lists of only UUIDs
        if isinstance(value, list) and value and all(
            isinstance(v, str) and _UUID_RE.match(v) for v in value
        ):
            continue
        result[key] = value
    return result


def _memory_to_response(m) -> MemoryResponse:
    return MemoryResponse(
        id=str(m.id),
        memory_type=m.memory_type,
        content=m.content,
        summary=m.summary,
        entities=_strip_internal_entities(m.entities or {}),
        tags=m.tags or [],
        importance=m.importance,
        confidence=m.confidence,
        status=m.status,
        created_at=m.created_at,
        expires_at=m.expires_at,
        recall_count=m.recall_count,
        source_session_id=str(m.source_session_id) if m.source_session_id else None,
    )


# ==================== Memory List ====================


@router.get("/list", response_model=MemoryListResponse)
async def get_user_memories(
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    status: str = Query("active", description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum memories to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """Get conversation memories for the current user."""
    user_id, _ = require_auth()

    repo = MemoryRepository(db)
    memories = await repo.get_user_memories(
        user_id=user_id,
        memory_type=memory_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    total = await repo.count_user_memories(
        user_id=user_id,
        memory_type=memory_type,
        status=status,
    )

    return MemoryListResponse(
        memories=[_memory_to_response(m) for m in memories],
        total=total,
    )


# ==================== Memory Recall ====================


@router.get("/recall", response_model=MemoryRecallResponse)
async def recall_memories(
    query: str = Query(..., description="Query text to find related memories"),
    limit: int = Query(5, ge=1, le=20, description="Maximum memories to return"),
    db: AsyncSession = Depends(get_db),
):
    """Recall memories related to a query (location, person, keyword, semantic)."""
    user_id, _ = require_auth()

    service = MemoryRecallService(db)
    memories, context_str = await service.recall_for_message(
        user_id=user_id,
        message=query,
        limit=limit,
    )

    return MemoryRecallResponse(
        memories=[_memory_to_response(m) for m in memories],
        context_summary=context_str,
        recall_count=len(memories),
    )


# ==================== Memory Search ====================


@router.get("/search")
async def search_memories(
    location: Optional[str] = Query(None, description="Search by location"),
    person: Optional[str] = Query(None, description="Search by person name"),
    tags: Optional[str] = Query(None, description="Search by tags (comma-separated)"),
    text: Optional[str] = Query(None, description="Full-text search"),
    limit: int = Query(20, ge=1, le=50, description="Maximum memories to return"),
    db: AsyncSession = Depends(get_db),
):
    """Search memories with various filters."""
    user_id, _ = require_auth()

    repo = MemoryRepository(db)
    memories = []

    if location:
        memories = await repo.search_by_location(user_id, location, limit)
    elif person:
        memories = await repo.search_by_person(user_id, person, limit)
    elif tags:
        tag_list = [t.strip() for t in tags.split(",")]
        memories = await repo.search_by_tags(user_id, tag_list, limit)
    elif text:
        memories = await repo.full_text_search(user_id, text, limit)
    else:
        raise HTTPException(status_code=400, detail="At least one search parameter required")

    return {
        "memories": [_memory_to_response(m) for m in memories],
        "total": len(memories),
    }


# ==================== Memory Status Update ====================


@router.patch("/{memory_id}/status")
async def update_memory_status(
    memory_id: UUID,
    status: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Update memory status (active, completed, cancelled, archived)."""
    from ...modules.memory.models import MemoryStatus

    user_id, _ = require_auth()

    repo = MemoryRepository(db)

    valid_statuses = [s.value for s in MemoryStatus]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    memory = await repo.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    if memory.user_id != user_id:
        raise HTTPException(status_code=404, detail="Memory not found")

    await repo.update_memory(memory_id, status=status)
    return {"message": f"Memory status updated to {status}", "memory_id": str(memory_id)}


# ==================== Memory Delete ====================


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a memory."""
    user_id, _ = require_auth()

    repo = MemoryRepository(db)

    memory = await repo.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    if memory.user_id != user_id:
        raise HTTPException(status_code=404, detail="Memory not found")

    success = await repo.delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"message": "Memory deleted", "memory_id": str(memory_id)}


# ==================== Insights ====================


@router.get("/insights", response_model=InsightListResponse)
async def get_pending_insights(
    unread_only: bool = Query(False, description="Only return unread (pending) insights"),
    include_all: bool = Query(False, description="Include all insights regardless of status/expiry (for history)"),
    min_importance: Optional[int] = Query(None, ge=1, le=10, description="Minimum importance/priority"),
    type: Optional[str] = Query(None, alias="type", description="Filter by insight type"),
    limit: int = Query(10, ge=1, le=50, description="Maximum insights to return"),
    db: AsyncSession = Depends(get_db),
):
    """Get insights for the current user with optional filters.

    Use include_all=true for the insight history page to return all insights
    regardless of status or expiry.
    """
    from sqlalchemy import select, and_, or_
    from ...modules.insight.models import Insight, InsightStatus
    from ...modules.memory.models import ConversationMemory  # noqa: F401 — needed by MemoryInsight relationship
    from ...core.utils.timezone import utc_now

    user_id, _ = require_auth()

    conditions = [Insight.user_id == user_id]

    if not include_all:
        if unread_only:
            conditions.append(Insight.status == InsightStatus.PENDING.value)
        else:
            conditions.append(Insight.status.in_([
                InsightStatus.PENDING.value, InsightStatus.ACTIVE.value,
            ]))

        now = utc_now()
        conditions.append(
            or_(
                Insight.expires_at.is_(None),
                Insight.expires_at > now,
            )
        )

    if min_importance is not None:
        conditions.append(Insight.importance >= min_importance * 10)

    if type is not None:
        conditions.append(Insight.insight_type == type)

    query = (
        select(Insight)
        .where(and_(*conditions))
        .order_by(Insight.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    insights = list(result.scalars().all())

    insight_responses = [
        InsightResponse(
            id=str(i.id),
            insight_type=i.insight_type,
            title=i.title,
            content=i.content,
            priority=max(1, min(10, (i.importance or 50) // 10)),
            urgency="high" if (i.urgency or 0) >= 70 else "normal",
            related_memory_ids=[],
            action_options=i.action_options or [],
            action_data={},
            status=i.status,
            created_at=i.created_at,
        )
        for i in insights
    ]

    return InsightListResponse(insights=insight_responses, total=len(insight_responses))


@router.post("/insights/{insight_id}/action")
async def execute_insight_action(
    insight_id: UUID,
    action: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """Execute an action on an insight (complete_plan, ignore, etc.)."""
    user_id, family_id = require_auth()

    from ...modules.insight.models import Insight, InsightStatus
    from ...modules.insight.insight_feedback_service import InsightFeedbackService

    result = await db.execute(
        select(Insight).where(Insight.id == insight_id, Insight.user_id == user_id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    plan_actions = {"complete_plan", "still_planning", "cancel_plan"}

    if action == "ignore":
        svc = InsightFeedbackService(db)
        await svc.record_feedback(
            insight_id=insight_id, user_id=user_id, feedback="not_useful",
        )
        await db.commit()
        return {"success": True, "message": "Insight dismissed"}

    if action in plan_actions:
        svc = InsightFeedbackService(db)
        await svc.record_feedback(
            insight_id=insight_id, user_id=user_id, feedback="useful",
        )
        await db.commit()
        return {"success": True, "message": f"Action '{action}' recorded"}

    # Mark as active (shown)
    if insight.status == InsightStatus.PENDING.value:
        insight.status = InsightStatus.ACTIVE.value
        insight.activated_at = utc_now()
        await db.commit()
    return {"success": True, "message": f"Opening {action}", "next_step": action}


# ==================== Insight Feedback ====================


class InsightFeedbackRequest(BaseModel):
    feedback_type: str  # useful, not_useful, too_frequent, defer, never


@router.post("/insights/{insight_id}/feedback")
async def submit_insight_feedback(
    insight_id: UUID,
    body: InsightFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback on an insight (useful/not_useful/too_frequent/defer/never)."""
    user_id, family_id = require_auth()

    valid_types = {"useful", "not_useful", "too_frequent", "defer", "never"}
    if body.feedback_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feedback_type. Must be one of: {sorted(valid_types)}",
        )

    from ...modules.insight.insight_feedback_service import InsightFeedbackService

    svc = InsightFeedbackService(db)
    try:
        updated = await svc.record_feedback(
            insight_id=insight_id,
            user_id=user_id,
            feedback=body.feedback_type,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("InsightFeedbackService error for %s: %s", insight_id, e)
        raise HTTPException(status_code=500, detail="Failed to record feedback")

    message_map = {
        "useful": "Thank you for the feedback",
        "not_useful": "Feedback recorded, we'll improve",
        "too_frequent": "We'll reduce similar notifications",
    }
    return {
        "success": True,
        "message": message_map.get(body.feedback_type, "Feedback recorded"),
    }


# ==================== Feedback Bus Helpers ====================


async def _emit_insight_feedback(
    signal_name: str,
    insight,
    user_id: UUID,
    family_id: Optional[UUID],
    source: str,
) -> None:
    """Emit a FeedbackBus signal for insight-related user actions."""
    if not family_id:
        return
    try:
        from ...core.feedback import get_feedback_bus, FeedbackSignal

        bus = get_feedback_bus()
        signal = FeedbackSignal[signal_name]
        await bus.emit(
            signal=signal,
            data={
                "insight_id": str(insight.id),
                "insight_type": getattr(insight, "insight_type", None),
            },
            family_id=family_id,
            user_id=user_id,
            source=source,
        )
    except Exception:
        logger.warning("FeedbackBus emit failed for %s", signal_name, exc_info=True)


# ==================== Memory Consolidation ====================


@router.post("/consolidate")
async def trigger_consolidation(
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger insight generation / memory consolidation."""
    from ...modules.briefing.services.insight_orchestrator import InsightOrchestrator

    user_id, family_id = require_auth()

    orchestrator = InsightOrchestrator(db)
    insights = await orchestrator.generate_all(user_id, family_id)

    return {
        "message": f"Generated {len(insights)} insights",
        "insight_count": len(insights),
        "insight_ids": [str(i.id) for i in insights],
    }


# ==================== Memory Stats ====================


class MemoryStatsResponse(BaseModel):
    total: int
    by_type: dict


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get memory statistics broken down by type."""
    from sqlalchemy import select, func as sa_func
    from ...modules.memory.models import ConversationMemory

    user_id, family_id = require_auth()

    # Total count
    total_stmt = (
        select(sa_func.count())
        .select_from(ConversationMemory)
        .where(ConversationMemory.family_id == family_id)
    )
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    # Count by type
    type_stmt = (
        select(
            ConversationMemory.memory_type,
            sa_func.count().label("count"),
        )
        .where(ConversationMemory.family_id == family_id)
        .group_by(ConversationMemory.memory_type)
    )
    type_result = await db.execute(type_stmt)
    by_type = {row.memory_type: row.count for row in type_result.all()}

    return MemoryStatsResponse(total=total, by_type=by_type)


# ==================== Memory Detail ====================


@router.get("/detail/{memory_id}", response_model=MemoryResponse)
async def get_memory_detail(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single memory by ID."""
    user_id, _ = require_auth()

    repo = MemoryRepository(db)
    memory = await repo.get_memory(memory_id)

    if not memory or memory.user_id != user_id:
        raise HTTPException(status_code=404, detail="Memory not found")

    return _memory_to_response(memory)
