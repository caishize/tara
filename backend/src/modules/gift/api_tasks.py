"""Gift task API endpoints.

Split from api.py for file size management.
Task CRUD, generate, regenerate, and task recommendation endpoints.
"""
import logging
from datetime import date
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import get_current_family, get_current_user
from ...db.session import get_db
from .api import (
    GiftTaskCreate,
    GiftTaskUpdate,
    GenerateTaskRecommendationRequest,
    RegenerateRecommendationRequest,
    _get_llm_provider,
    _task_to_response,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gifts", tags=["gifts"])


@router.get("/tasks")
async def list_tasks(
    task_status: Optional[str] = Query(None, alias="status"),
    member_id: Optional[UUID] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """List gift tasks."""
    from .task_service import GiftTaskService
    from .models import TaskStatus as TS

    svc = GiftTaskService(session)
    if member_id:
        tasks = await svc.repo.get_by_member(
            member_id=member_id,
            family_id=family_id,
            status=TS(task_status) if task_status else None,
            from_date=from_date,
            to_date=to_date,
        )
    else:
        tasks = await svc.get_upcoming_tasks(family_id, days=365)
        if task_status:
            tasks = [t for t in tasks if t.status == task_status]

    total = len(tasks)
    start = (page - 1) * page_size
    paginated = tasks[start : start + page_size]
    items = [await _task_to_response(t, session) for t in paginated]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/tasks/upcoming")
async def get_upcoming_tasks(
    days: int = Query(60, ge=1, le=365),
    include_overdue: bool = True,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get upcoming tasks (including overdue)."""
    from .task_service import GiftTaskService

    svc = GiftTaskService(session)
    tasks = await svc.repo.get_upcoming_tasks(family_id, days, include_overdue=include_overdue)
    return {
        "items": [await _task_to_response(t, session) for t in tasks],
        "total": len(tasks),
    }


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get task details."""
    from .task_service import GiftTaskService

    svc = GiftTaskService(session)
    task = await svc.get_task(task_id, family_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return await _task_to_response(task, session)


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    data: GiftTaskCreate,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Create a gift task."""
    from .task_service import GiftTaskService
    from .models import TriggerSource

    svc = GiftTaskService(session)
    task = await svc.create_task_for_date(
        family_id=family_id,
        date_id=data.important_date_id,
        member_id=data.member_id,
        date_type=data.occasion,
        occasion_date=data.occasion_date,
        title=data.occasion_title or "",
        trigger_source=TriggerSource.MANUAL,
        budget_min=data.budget_min,
        budget_max=data.budget_max,
        notes=data.notes,
    )
    if not task:
        raise HTTPException(status_code=409, detail="Task already exists for this date and year")
    await session.commit()
    return await _task_to_response(task, session)


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: UUID,
    data: GiftTaskUpdate,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Update a gift task."""
    from .task_service import GiftTaskService
    from .models import TaskStatus as TS

    svc = GiftTaskService(session)
    task = await svc.get_task(task_id, family_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in [TS.PENDING.value, TS.SCHEDULED.value]:
        raise HTTPException(status_code=400, detail="Can only update pending or scheduled tasks")

    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await svc.repo.update_status(task_id, TS(task.status), **update_data)
    await session.commit()
    task = await svc.get_task(task_id, family_id)
    return await _task_to_response(task, session)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Cancel a gift task."""
    from .task_service import GiftTaskService

    svc = GiftTaskService(session)
    if not await svc.cancel_task(task_id, family_id):
        raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
    await session.commit()


@router.post("/tasks/{task_id}/generate")
async def generate_task_recommendation(
    task_id: UUID,
    data: Optional[GenerateTaskRecommendationRequest] = None,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
    current_user_id: UUID = Depends(get_current_user),
):
    """Trigger recommendation generation for a task."""
    from .task_service import GiftTaskService
    from .recommendation_service import SmartRecommendationService
    from .models import TaskStatus as TS

    svc = GiftTaskService(session)
    task = await svc.get_task(task_id, family_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in [TS.PENDING.value, TS.FAILED.value]:
        raise HTTPException(status_code=400, detail=f"Cannot generate for status: {task.status}")

    if data:
        if data.budget_min:
            task.budget_min = data.budget_min
        if data.budget_max:
            task.budget_max = data.budget_max

    try:
        llm = _get_llm_provider()
        smart_svc = SmartRecommendationService(session, llm)
        result = await smart_svc.generate_for_task(task=task, requester_user_id=current_user_id)
        await session.commit()
        return {
            "recommendation_id": result["id"],
            "task_id": str(task_id),
            "member_name": result["member_name"],
            "occasion": result["occasion"],
            "options_count": len(result["recommendations"]),
            "personalization_score": result["personalization_score"],
            "processing_time_ms": result["processing_time_ms"],
            "dedup_warnings": result["dedup_warnings"],
        }
    except Exception as e:
        logger.error("Failed to generate recommendation: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to generate: {e}")


@router.post("/tasks/{task_id}/regenerate")
async def regenerate_recommendation(
    task_id: UUID,
    data: Optional[RegenerateRecommendationRequest] = None,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
    current_user_id: UUID = Depends(get_current_user),
):
    """Regenerate recommendation for a task (swap out previous)."""
    from .task_service import GiftTaskService
    from .recommendation_service import SmartRecommendationService, RecommendationRepository
    from .models import TaskStatus as TS

    svc = GiftTaskService(session)
    task = await svc.get_task(task_id, family_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in [TS.COMPLETED.value, TS.FAILED.value, TS.PENDING.value]:
        raise HTTPException(status_code=400, detail=f"Cannot regenerate for status: {task.status}")

    previous_gift_names: List[str] = []
    old_rec_id = task.recommendation_id
    if data and data.exclude_previous and old_rec_id:
        rec_repo = RecommendationRepository(session)
        old_rec = await rec_repo.get_by_id(old_rec_id)
        if old_rec and old_rec.recommendations:
            for opt in old_rec.recommendations:
                if isinstance(opt, dict) and "name" in opt:
                    previous_gift_names.append(opt["name"])

    if data:
        if data.budget_min:
            task.budget_min = data.budget_min
        if data.budget_max:
            task.budget_max = data.budget_max

    if old_rec_id:
        if task.recommendation_history is None:
            task.recommendation_history = []
        if old_rec_id not in task.recommendation_history:
            task.recommendation_history = [*task.recommendation_history, old_rec_id]

    await svc.repo.update_status(task_id, TS.PENDING)
    task.recommendation_id = None

    try:
        llm = _get_llm_provider()
        smart_svc = SmartRecommendationService(session, llm)
        result = await smart_svc.generate_for_task(
            task=task,
            requester_user_id=current_user_id,
            additional_preferences=data.additional_preferences if data else None,
            exclude_categories=data.exclude_categories if data else None,
            exclude_gift_names=previous_gift_names or None,
        )
        await session.commit()
        return {
            "recommendation_id": result["id"],
            "task_id": str(task_id),
            "member_name": result["member_name"],
            "occasion": result["occasion"],
            "options_count": len(result["recommendations"]),
            "personalization_score": result["personalization_score"],
            "processing_time_ms": result["processing_time_ms"],
            "dedup_warnings": result["dedup_warnings"],
        }
    except Exception as e:
        logger.error("Failed to regenerate recommendation: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to regenerate: {e}")


@router.get("/tasks/{task_id}/recommendation")
async def get_task_recommendation(
    task_id: UUID,
    session: AsyncSession = Depends(get_db),
    family_id: UUID = Depends(get_current_family),
):
    """Get the recommendation linked to a task."""
    from .task_service import GiftTaskService
    from .recommendation_service import RecommendationRepository

    svc = GiftTaskService(session)
    task = await svc.get_task(task_id, family_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.recommendation_id:
        return {"recommendation": None, "message": "No recommendation generated yet"}

    rec_repo = RecommendationRepository(session)
    rec = await rec_repo.get_by_id(task.recommendation_id)
    if not rec:
        return {"recommendation": None, "message": "Recommendation not found"}
    return {
        "recommendation": {
            "id": str(rec.id),
            "status": rec.status,
            "options": rec.recommendations,
            "dedup_warnings": rec.dedup_warnings,
            "created_at": rec.created_at.isoformat(),
            "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
        }
    }
