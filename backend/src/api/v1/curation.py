"""Curation API routes - /api/v1/curation/*

Thin routing layer for curation management (internal).
Delegates to curation module services.

Endpoints:
    POST /curation/trigger          - Trigger curation pipeline
    GET  /curation/jobs/{id}        - Curation job status
    GET  /curation/work-report      - Curation work report
"""

import logging
from datetime import date as date_type
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import get_current_user, get_current_family
from ...core.utils.timezone import utc_now
from ...db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/curation", tags=["curation"])


# --- Request / Response schemas ---

class TriggerCurationRequest(BaseModel):
    """Trigger a curation pipeline run."""
    start_date: Optional[str] = None  # ISO format YYYY-MM-DD
    end_date: Optional[str] = None    # ISO format YYYY-MM-DD


class CurationJobResponse(BaseModel):
    """Curation job status."""
    job_id: str
    status: str  # pending, running, completed, failed
    trigger_type: str
    events_processed: int = 0
    events_curated: int = 0
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


# --- Endpoints ---

@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_curation(
    request: TriggerCurationRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Trigger the curation pipeline for the family.

    Dispatches curation to a background Celery task and returns immediately.
    Use GET /curation/jobs/{job_id} to poll status.
    """
    from ...modules.curation.models import CurationJob
    from ...modules.curation.tasks import trigger_curation_async

    # Create a pending job record so the client has a job_id to poll
    start_date: Optional[date_type] = None
    end_date: Optional[date_type] = None
    job = CurationJob(
        family_id=family_id,
        trigger_type="manual",
    )
    if request.start_date:
        try:
            start_date = date_type.fromisoformat(request.start_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid start_date format: {request.start_date}",
            ) from exc
        job.date_range_start = start_date
    if request.end_date:
        try:
            end_date = date_type.fromisoformat(request.end_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid end_date format: {request.end_date}",
            ) from exc
        job.date_range_end = end_date

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch to Celery (respect_cooldown=False for manual triggers)
    dispatched = trigger_curation_async(
        family_id,
        trigger_type="manual",
        respect_cooldown=False,
        start_date=start_date,
        end_date=end_date,
        existing_job_id=job.id,
    )

    if not dispatched:
        logger.warning("Failed to dispatch curation task for family %s", family_id)
        job.status = "failed"
        job.error_message = "Failed to dispatch curation task to broker."
        job.completed_at = utc_now()
        await db.commit()
        return {
            "job_id": str(job.id),
            "status": "failed",
            "message": "Failed to dispatch curation task",
        }

    return {
        "job_id": str(job.id),
        "status": "pending",
        "message": "Curation triggered successfully",
    }


@router.get("/jobs/{job_id}", response_model=CurationJobResponse)
async def get_curation_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Get status of a curation job."""
    from ...modules.curation.models import CurationJob

    result = await db.execute(
        select(CurationJob).where(
            CurationJob.id == job_id,
            CurationJob.family_id == family_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Curation job not found",
        )

    return {
        "job_id": str(job.id),
        "status": job.status,
        "trigger_type": job.trigger_type,
        "events_processed": job.events_processed or 0,
        "events_curated": job.events_curated or 0,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/work-report")
async def get_work_report(
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
) -> Dict[str, Any]:
    """Get curation work report with summary statistics."""
    from datetime import timedelta

    from ...core.utils.timezone import utc_now
    from ...modules.curation.models import CurationJob

    since = utc_now() - timedelta(days=days)

    result = await db.execute(
        select(CurationJob).where(
            CurationJob.family_id == family_id,
            CurationJob.created_at >= since,
        ).order_by(CurationJob.created_at.desc())
    )
    jobs = result.scalars().all()

    total_processed = sum(j.events_processed or 0 for j in jobs)
    total_created = sum(j.events_curated or 0 for j in jobs)
    completed = [j for j in jobs if j.status == "completed"]
    failed = [j for j in jobs if j.status == "failed"]

    return {
        "period_days": days,
        "total_jobs": len(jobs),
        "completed_jobs": len(completed),
        "failed_jobs": len(failed),
        "total_events_processed": total_processed,
        "total_events_curated": total_created,
        "recent_jobs": [
            {
                "job_id": str(j.id),
                "status": j.status,
                "trigger_type": j.trigger_type,
                "events_processed": j.events_processed or 0,
                "events_curated": j.events_curated or 0,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs[:10]
        ],
    }
