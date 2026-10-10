"""Unified Insights API — /api/v1/insights/*

Endpoints for the unified insight system (insights + insight_entities tables):
  - POST /{id}/feedback       — Unified feedback
  - POST /{id}/adopt          — Adopt insight to trip
  - POST /{id}/trip-task-done — Trip task completion
  - POST /{id}/action         — Execute action chip
  - POST /{id}/entities/{entity_id}/done — Per-entity completion
  - POST /batch-feedback      — Batch feedback
"""
import logging
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import get_current_user, get_current_family
from ...core.utils.timezone import utc_now
from ...db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["Insights"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

# All feedback types accepted by the unified feedback endpoint
_VALID_FEEDBACK_TYPES = frozenset({
    "useful", "not_useful", "too_frequent", "not_relevant",
    "incorrect", "defer", "never",
    # New types
    "acknowledged", "not_now",
    # Swipe-to-dismiss from mobile
    "dismiss",
    # Legacy 3-type values accepted for backward compat
    "ignored", "never_again",
})


class UnifiedFeedbackRequest(BaseModel):
    """Unified feedback request for the insights table."""
    feedback: str  # acknowledged, defer, not_useful, not_relevant, incorrect, never, useful, not_now
    reason: Optional[str] = None


class UnifiedFeedbackResponse(BaseModel):
    """Unified feedback response."""
    success: bool
    message: str
    insight_id: str
    new_status: str


class InsightAdoptRequest(BaseModel):
    """Adopt an insight to a trip."""
    trip_id: UUID


class InsightAdoptResponse(BaseModel):
    """Response for insight adoption."""
    success: bool
    insight_id: str
    trip_id: str
    adopted_entity_count: int


class TripTaskDoneRequest(BaseModel):
    """Mark trip-related insight tasks as done."""
    trip_id: UUID
    completed_entity_ids: Optional[List[UUID]] = None


class TripTaskDoneResponse(BaseModel):
    """Response for trip task completion."""
    success: bool
    insight_id: str
    completed_count: int
    all_done: bool


class BatchFeedbackRequest(BaseModel):
    """Batch feedback for multiple insights."""
    insight_ids: List[UUID]
    feedback: str
    reason: Optional[str] = None


class BatchFeedbackResponse(BaseModel):
    """Response for batch feedback."""
    success: bool
    processed: int
    skipped: int
    results: List[Dict[str, str]] = Field(default_factory=list)


class InsightActionRequest(BaseModel):
    """Execute an action chip on an insight."""
    action_type: str
    action_payload: Optional[dict] = None


class InsightActionResponse(BaseModel):
    """Response for insight action execution."""
    success: bool
    insight_id: str
    action_type: str
    result: Optional[dict] = None


class EntityDoneResponse(BaseModel):
    """Response for per-entity completion."""
    success: bool
    insight_id: str
    entity_id: str
    all_done: bool


# ---------------------------------------------------------------------------
# Query endpoints
# ---------------------------------------------------------------------------


@router.get("/for-trip/{trip_id}")
async def get_insights_for_trip(
    trip_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get insights related to a specific trip."""

    from ...modules.insight.insight_query_service import InsightQueryService

    svc = InsightQueryService(db)
    try:
        cards = await svc.get_for_trip(user_id, trip_id, limit=limit)
    except Exception as e:
        logger.error("get_insights_for_trip failed for trip %s: %s", trip_id, e)
        raise HTTPException(status_code=500, detail="Failed to fetch trip insights")

    def _urgency_to_str(val) -> str:
        if isinstance(val, int):
            if val >= 90:
                return "critical"
            if val >= 70:
                return "high"
            if val >= 40:
                return "normal"
            return "low"
        return str(val or "normal")

    return {
        "insights": [
            {**card.model_dump(), "urgency": _urgency_to_str(card.urgency)}
            for card in cards
        ],
    }


# ---------------------------------------------------------------------------
# Wave delivery endpoints
# ---------------------------------------------------------------------------


class WaveConfigItem(BaseModel):
    """Single wave configuration."""
    name: str = Field(..., min_length=1, max_length=20)
    enabled: bool = True
    hour: int = Field(..., ge=0, le=23)


class WaveConfigResponse(BaseModel):
    """Response for wave configuration query."""
    waves: List[WaveConfigItem]


class WaveConfigUpdateRequest(BaseModel):
    """Update wave delivery configuration."""
    waves: List[WaveConfigItem]


@router.get("/for-wave/{wave_name}")
async def get_insights_for_wave(
    wave_name: str,
    limit: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get insights for a specific delivery wave.

    Waves: morning (7:00), noon (12:00), evening (17:00), night (21:00).
    Each wave returns insights filtered by focus types relevant to that time of day.
    """
    from ...modules.insight.delivery_timing_engine import WAVE_NAMES

    if wave_name not in WAVE_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown wave '{wave_name}'. Must be one of: {list(WAVE_NAMES)}",
        )

    from ...modules.insight.insight_query_service import InsightQueryService

    svc = InsightQueryService(db)
    try:
        cards = await svc.get_for_wave(
            user_id=user_id,
            family_id=family_id,
            wave_name=wave_name,
            limit=limit,
        )
    except Exception as e:
        logger.error("get_for_wave failed for wave %s: %s", wave_name, e)
        raise HTTPException(status_code=500, detail="Failed to fetch wave insights")

    return {
        "wave": wave_name,
        "insights": [card.model_dump() for card in cards],
        "count": len(cards),
    }


@router.get("/config/waves", response_model=WaveConfigResponse)
async def get_wave_config(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get the user's delivery wave configuration."""
    from ...modules.insight.delivery_timing_engine import WAVE_CONFIGS
    from ...modules.insight.models import UserInsightSettings

    result = await db.execute(
        select(UserInsightSettings).where(
            UserInsightSettings.user_id == user_id,
        )
    )
    settings = result.scalar_one_or_none()

    # Merge user overrides with defaults
    user_waves = (settings.delivery_waves if settings and settings.delivery_waves else {})

    wave_items = []
    for w in WAVE_CONFIGS:
        override = user_waves.get(w.name, {})
        wave_items.append(WaveConfigItem(
            name=w.name,
            enabled=override.get("enabled", True),
            hour=override.get("hour", w.hour),
        ))

    return WaveConfigResponse(waves=wave_items)


@router.patch("/config/waves", response_model=WaveConfigResponse)
async def update_wave_config(
    body: WaveConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Update the user's delivery wave configuration.

    Allows enabling/disabling waves and customizing delivery hours.
    """
    from ...modules.insight.delivery_timing_engine import WAVE_NAMES, WAVE_CONFIGS
    from ...modules.insight.models import UserInsightSettings

    # Validate wave names (hour range already enforced by Pydantic Field)
    for item in body.waves:
        if item.name not in WAVE_NAMES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown wave '{item.name}'. Must be one of: {list(WAVE_NAMES)}",
            )

    result = await db.execute(
        select(UserInsightSettings).where(
            UserInsightSettings.user_id == user_id,
        )
    )
    settings = result.scalar_one_or_none()

    # Build delivery_waves JSONB
    waves_config = {}
    for item in body.waves:
        waves_config[item.name] = {
            "enabled": item.enabled,
            "hour": item.hour,
        }

    if settings is None:
        settings = UserInsightSettings(
            user_id=user_id,
            family_id=family_id,
            delivery_waves=waves_config,
        )
        db.add(settings)
    else:
        # Merge with existing config (immutable — new dict for SQLAlchemy change detection)
        merged = {**(settings.delivery_waves or {}), **waves_config}
        settings.delivery_waves = merged

    await db.commit()

    # Return updated config
    merged = settings.delivery_waves or {}
    wave_items = []
    for w in WAVE_CONFIGS:
        override = merged.get(w.name, {})
        wave_items.append(WaveConfigItem(
            name=w.name,
            enabled=override.get("enabled", True),
            hour=override.get("hour", w.hour),
        ))

    return WaveConfigResponse(waves=wave_items)


# ---------------------------------------------------------------------------
# Legacy unified feedback — auto-detects insight table (PLAN-006)
# ---------------------------------------------------------------------------


@router.post("/{insight_id}/feedback", response_model=UnifiedFeedbackResponse)
async def submit_unified_insight_feedback(
    insight_id: UUID,
    body: UnifiedFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> UnifiedFeedbackResponse:
    """Unified feedback endpoint for the insights table.

    Routes all feedback to InsightFeedbackService which handles status
    transitions, cumulative dismiss upgrade, and regen suppression.
    """

    if body.feedback not in _VALID_FEEDBACK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feedback. Must be one of: {sorted(_VALID_FEEDBACK_TYPES)}",
        )

    from ...modules.insight.insight_feedback_service import InsightFeedbackService
    svc = InsightFeedbackService(db)
    try:
        updated = await svc.record_feedback(
            insight_id=insight_id,
            user_id=user_id,
            feedback=body.feedback,
            reason=body.reason,
        )
        new_status = updated.status if hasattr(updated, "status") else body.feedback
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("InsightFeedbackService error for %s: %s", insight_id, e)
        raise HTTPException(status_code=500, detail="Failed to record feedback")

    message_map = {
        "useful": "反馈已记录，谢谢",
        "not_useful": "已记录，我们会改进",
        "too_frequent": "已记录，减少类似提醒",
        "not_relevant": "已记录，减少不相关内容",
        "incorrect": "已记录，感谢指正",
        "defer": "已推迟",
        "not_now": "已推迟",
        "dismiss": "已忽略",
        "never": "已设置为不再提醒",
        "acknowledged": "已知悉",
        "ignored": "已记录",
        "never_again": "已设置为不再提醒",
    }
    return UnifiedFeedbackResponse(
        success=True,
        message=message_map.get(body.feedback, "已记录"),
        insight_id=str(insight_id),
        new_status=new_status,
    )


# ---------------------------------------------------------------------------
# New unified insight endpoints (insights table only)
# ---------------------------------------------------------------------------


@router.post("/{insight_id}/adopt", response_model=InsightAdoptResponse)
async def adopt_insight_to_trip(
    insight_id: UUID,
    body: InsightAdoptRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Adopt an insight into a trip.

    Delegates to InsightAdoptService which handles optimistic locking,
    entity upsert, preference signal, and domain bridge writeback
    (favor mark_in_progress, temperature record_interaction_intent).
    """

    from ...modules.insight.insight_adopt_service import InsightAdoptService
    from ...modules.insight.models import InsightNotActionableError

    svc = InsightAdoptService(db)
    try:
        updated = await svc.adopt_to_trip(
            insight_id=insight_id,
            user_id=user_id,
            trip_id=body.trip_id,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InsightNotActionableError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("InsightAdoptService error for %s: %s", insight_id, e)
        raise HTTPException(status_code=500, detail="Failed to adopt insight")

    # Count adopted entities
    adopted_count = sum(
        1 for e in (updated.entities or []) if e.adopted_at is not None
    )

    return InsightAdoptResponse(
        success=True,
        insight_id=str(insight_id),
        trip_id=str(body.trip_id),
        adopted_entity_count=adopted_count,
    )


@router.post("/{insight_id}/trip-task-done", response_model=TripTaskDoneResponse)
async def trip_task_done(
    insight_id: UUID,
    body: TripTaskDoneRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Mark trip-related insight tasks as completed.

    Delegates to InsightAdoptService which handles per-entity done_at,
    all-done check, status transition, event publishing, and domain bridge
    writeback (favor mark_reciprocated, commitment mark_followed_up,
    temperature record_interaction).
    """

    from ...modules.insight.insight_adopt_service import InsightAdoptService
    from ...modules.insight.models import InsightNotActionableError

    svc = InsightAdoptService(db)
    try:
        updated = await svc.mark_trip_task_done(
            insight_id=insight_id,
            user_id=user_id,
            trip_id=body.trip_id,
            completed_entity_ids=body.completed_entity_ids,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsightNotActionableError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("InsightAdoptService.mark_trip_task_done error for %s: %s", insight_id, e)
        raise HTTPException(status_code=500, detail="Failed to mark trip task done")

    # Check all-done state from the updated insight
    all_done = updated.status == "acted"
    completed_count = sum(
        1 for e in (updated.entities or [])
        if e.done_at is not None and e.role in ("primary", "related")
    )

    return TripTaskDoneResponse(
        success=True,
        insight_id=str(insight_id),
        completed_count=completed_count,
        all_done=all_done,
    )


@router.post("/{insight_id}/action", response_model=InsightActionResponse)
async def execute_insight_action(
    insight_id: UUID,
    body: InsightActionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Execute an action chip on an insight.

    Dispatches typed actions (open_chat, create_pending_action, open_detail,
    dismiss) based on the action_type. Records action execution and updates
    insight status as appropriate.
    """

    from ...modules.insight.models import (
        Insight,
        InsightStatus,
        ActionType,
        InsightNotActionableError,
    )

    insight = await _get_unified_insight(db, insight_id, user_id)
    now = utc_now()

    # Validate action_type
    try:
        action_type = ActionType(body.action_type)
    except ValueError:
        valid_types = [at.value for at in ActionType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action_type. Must be one of: {valid_types}",
        )

    # Check insight is actionable (not already dismissed/expired/acted)
    terminal_statuses = {
        InsightStatus.DISMISSED.value,
        InsightStatus.EXPIRED.value,
        InsightStatus.ACTED.value,
    }
    if insight.status in terminal_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Insight is in terminal status '{insight.status}' and cannot be actioned",
        )

    result_data = None

    if action_type == ActionType.DISMISS:
        # Handle dismiss as feedback
        from ...modules.insight.insight_feedback_service import InsightFeedbackService
        svc = InsightFeedbackService(db)
        try:
            await svc.record_feedback(
                insight_id=insight_id,
                user_id=user_id,
                feedback="not_useful",
                reason=body.action_payload.get("reason") if body.action_payload else None,
            )
        except Exception as e:
            logger.error("Failed to dismiss insight %s: %s", insight_id, e)
            raise HTTPException(status_code=500, detail="Failed to dismiss insight")
        result_data = {"new_status": "dismissed"}

    elif action_type == ActionType.CREATE_PENDING_ACTION:
        # Create a PendingAction from the insight
        try:
            from ...modules.conversation.pending_action import PendingAction, ActionStatus
            from datetime import timedelta

            extra_payload = body.action_payload or {}
            pa_action_type = extra_payload.get("pending_action_type", "custom")
            pa_expires = now + timedelta(days=30)

            pending = PendingAction(
                user_id=user_id,
                family_id=family_id,
                action_type=pa_action_type,
                payload={
                    "insight_id": str(insight_id),
                    "insight_type": insight.insight_type,
                    "title": extra_payload.get("title", insight.title),
                    "content": extra_payload.get("description", insight.content),
                    **{k: v for k, v in extra_payload.items()
                       if k not in ("pending_action_type", "title", "description")},
                },
                display_data={
                    "title": extra_payload.get("title", insight.title),
                    "content": extra_payload.get("description", insight.content),
                    "source": "insight_action",
                },
                status=ActionStatus.PENDING.value,
                expires_at=pa_expires,
            )
            # source_entity_id exists in DB (migration 120) but not on ORM
            pending.__dict__["source_entity_id"] = insight_id
            db.add(pending)
            result_data = {"pending_action_created": True}
        except Exception as e:
            logger.error("Failed to create PendingAction from insight %s: %s", insight_id, e)
            raise HTTPException(status_code=500, detail="Failed to create pending action")

    elif action_type in (ActionType.OPEN_CHAT, ActionType.OPEN_DETAIL):
        # These are client-side navigation actions; record interaction and
        # transition to active if pending (validated via VALID_TRANSITIONS)
        from ...modules.insight.models import VALID_TRANSITIONS
        if insight.status == InsightStatus.PENDING.value:
            allowed = VALID_TRANSITIONS.get(InsightStatus.PENDING, frozenset())
            if InsightStatus.ACTIVE in allowed:
                insight.status = InsightStatus.ACTIVE.value
                insight.activated_at = now
        result_data = {"action_recorded": True}

    elif action_type == ActionType.ACKNOWLEDGE:
        # Record acknowledgement — transitions insight to acknowledged status
        logger.info("Insight %s acknowledged by user %s", insight_id, user_id)
        result_data = {"acknowledged": True}

    elif action_type == ActionType.SNOOZE:
        # Snooze insight — client provides snooze_until in payload
        logger.info("Insight %s snoozed by user %s", insight_id, user_id)
        result_data = {"snoozed": True}

    elif action_type == ActionType.GENERATE_GREETING:
        # Trigger greeting generation — to be implemented by greeting service
        logger.info("Generate greeting requested for insight %s by user %s", insight_id, user_id)
        result_data = {"greeting_generation_queued": True}

    elif action_type == ActionType.SEND_CARE_MESSAGE:
        # Send care message to a person — client-side flow with person_id
        logger.info("Send care message requested for insight %s by user %s", insight_id, user_id)
        result_data = {"care_message_initiated": True}

    elif action_type == ActionType.SHARE:
        # Share insight content — client-side sharing flow
        logger.info("Share requested for insight %s by user %s", insight_id, user_id)
        result_data = {"share_initiated": True}

    elif action_type == ActionType.CREATE_MEMORY:
        # Create a memory record from insight content — to be implemented
        logger.info("Create memory requested for insight %s by user %s", insight_id, user_id)
        result_data = {"memory_creation_queued": True}

    elif action_type == ActionType.SET_REMINDER:
        # Set a reminder for this insight — client provides reminder time in payload
        logger.info("Set reminder requested for insight %s by user %s", insight_id, user_id)
        result_data = {"reminder_set": True}

    await db.commit()

    return InsightActionResponse(
        success=True,
        insight_id=str(insight_id),
        action_type=body.action_type,
        result=result_data,
    )


@router.post(
    "/{insight_id}/entities/{entity_id}/done",
    response_model=EntityDoneResponse,
)
async def mark_entity_done(
    insight_id: UUID,
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Mark a single entity within an insight as done.

    Delegates to InsightAdoptService.mark_trip_task_done with explicit
    completed_entity_ids for consistent domain bridge writeback.
    If all entities for the insight are now done, transitions the insight
    to 'acted' status.
    """

    from ...modules.insight.insight_adopt_service import InsightAdoptService
    from ...modules.insight.models import InsightEntity, InsightNotActionableError

    # Find the trip_id associated with this insight (for service delegation)
    trip_stmt = select(InsightEntity).where(
        InsightEntity.insight_id == insight_id,
        InsightEntity.entity_type == "trip",
        InsightEntity.adopted_at.isnot(None),
    )
    result = await db.execute(trip_stmt)
    trip_entity = result.scalars().first()

    if trip_entity is not None:
        # Delegating to service for proper domain bridge writeback
        svc = InsightAdoptService(db)
        try:
            updated = await svc.mark_trip_task_done(
                insight_id=insight_id,
                user_id=user_id,
                trip_id=trip_entity.entity_id,
                completed_entity_ids=[entity_id],
            )
            await db.commit()
            all_done = updated.status == "acted"
        except (ValueError, InsightNotActionableError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("mark_entity_done service error for %s/%s: %s", insight_id, entity_id, e)
            raise HTTPException(status_code=500, detail="Failed to mark entity done")
    else:
        # No trip context — direct entity update (non-adopted insight)
        from ...modules.insight.models import Insight, InsightStatus
        from ...modules.insight.insight_lifecycle import transition_status, ensure_active_before

        insight = await _get_unified_insight(db, insight_id, user_id)
        now = utc_now()

        entity_stmt = select(InsightEntity).where(
            InsightEntity.insight_id == insight_id,
            InsightEntity.entity_id == entity_id,
        )
        entity_result = await db.execute(entity_stmt)
        entity = entity_result.scalar_one_or_none()

        if entity is None:
            raise HTTPException(
                status_code=404,
                detail=f"Entity {entity_id} not found for insight {insight_id}",
            )

        if entity.done_at is None:
            entity.done_at = now

        # Check if all primary/related entities are now done
        all_stmt = select(InsightEntity).where(
            InsightEntity.insight_id == insight_id,
            InsightEntity.role.in_(["primary", "related"]),
        )
        all_result = await db.execute(all_stmt)
        all_entities = list(all_result.scalars().all())
        all_done = all(e.done_at is not None for e in all_entities) if all_entities else False

        if all_done and insight.status not in (
            InsightStatus.DISMISSED.value,
            InsightStatus.EXPIRED.value,
            InsightStatus.ACTED.value,
        ):
            ensure_active_before(insight, InsightStatus.ACTED)
            transition_status(insight, InsightStatus.ACTED)
            insight.acted_at = now

        await db.commit()

    return EntityDoneResponse(
        success=True,
        insight_id=str(insight_id),
        entity_id=str(entity_id),
        all_done=all_done,
    )


@router.post("/batch-feedback", response_model=BatchFeedbackResponse)
async def batch_feedback(
    body: BatchFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Apply feedback to multiple insights at once.

    Processes each insight individually so that per-insight transition
    validation and cumulative upgrade logic still apply. Failures on
    individual insights are logged and skipped.
    """

    if body.feedback not in _VALID_FEEDBACK_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feedback. Must be one of: {sorted(_VALID_FEEDBACK_TYPES)}",
        )

    from ...modules.insight.insight_feedback_service import InsightFeedbackService
    svc = InsightFeedbackService(db)

    results = []
    skipped = 0

    for iid in body.insight_ids:
        try:
            updated = await svc.record_feedback(
                insight_id=iid,
                user_id=user_id,
                feedback=body.feedback,
                reason=body.reason,
            )
            results.append({
                "insight_id": str(iid),
                "new_status": updated.status,
            })
        except Exception as e:
            logger.warning("Batch feedback skipped insight %s: %s", iid, e)
            skipped += 1

    await db.commit()

    return BatchFeedbackResponse(
        success=True,
        processed=len(results),
        skipped=skipped,
        results=results,
    )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_unified_insight(
    db: AsyncSession,
    insight_id: UUID,
    user_id: UUID,
):
    """Fetch an insight from the unified insights table.

    Raises HTTPException 404 if not found.
    """
    from ...modules.insight.models import Insight

    result = await db.execute(
        select(Insight).where(
            Insight.id == insight_id,
            Insight.user_id == user_id,
        )
    )
    insight = result.scalar_one_or_none()

    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found")

    return insight


