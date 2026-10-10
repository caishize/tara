"""Report API routes - /api/v1/report/*

Provides aggregated usage statistics and activity timelines
for the current user's family.
"""
import logging
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ...core.auth import get_current_user, get_current_family
from ...core.utils.timezone import utc_now
from ...db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["Report"])


# ==================== Response Models ====================


class ReportBreakdown(BaseModel):
    memories_extracted: int = 0
    events_managed: int = 0
    insights_generated: int = 0
    reminders_sent: int = 0
    briefings_run: int = 0
    gifts_tracked: int = 0


class ReportComparison(BaseModel):
    vs_last_period: float = 0.0


class ReportSummaryResponse(BaseModel):
    range: str
    total_actions: int
    breakdown: ReportBreakdown
    comparison: ReportComparison


class TimelineItem(BaseModel):
    timestamp: str
    action_type: str
    description: str
    status: str


class TimelineResponse(BaseModel):
    items: List[TimelineItem]
    total: int
    page: int


# ==================== Helpers ====================


def _get_date_range(range_str: str) -> tuple:
    """Return (start_dt, end_dt) for the given range and the previous period start."""
    now = utc_now()
    if range_str == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        prev_start = start - timedelta(days=1)
    elif range_str == "week":
        start = now - timedelta(days=7)
        prev_start = start - timedelta(days=7)
    elif range_str == "month":
        start = now - timedelta(days=30)
        prev_start = start - timedelta(days=30)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        prev_start = start - timedelta(days=1)
    return prev_start, start, now


# ==================== Endpoints ====================


@router.get("/summary", response_model=ReportSummaryResponse)
async def get_report_summary(
    range: str = Query("today", pattern="^(today|week|month)$"),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get aggregated report summary for the specified time range."""
    from ...modules.memory.models import ConversationMemory
    from ...modules.curation.models import CuratedEvent, CurationJob
    from ...modules.insight.models import Insight
    from ...modules.date_manager.reminder_models import EventReminder
    from ...modules.gift.models import GiftTask

    prev_start, start, end = _get_date_range(range)

    # Current period counts
    mem_count = await _count_rows(
        db, ConversationMemory, ConversationMemory.family_id == family_id,
        ConversationMemory.created_at >= start, ConversationMemory.created_at <= end,
    )
    event_count = await _count_rows(
        db, CuratedEvent, CuratedEvent.family_id == family_id,
        CuratedEvent.created_at >= start, CuratedEvent.created_at <= end,
    )
    insight_count = await _count_rows(
        db, Insight, Insight.family_id == family_id,
        Insight.created_at >= start, Insight.created_at <= end,
    )
    reminder_count = await _count_rows(
        db, EventReminder, EventReminder.user_id == user_id,
        EventReminder.status == "triggered",
        EventReminder.created_at >= start, EventReminder.created_at <= end,
    )
    job_count = await _count_rows(
        db, CurationJob, CurationJob.family_id == family_id,
        CurationJob.created_at >= start, CurationJob.created_at <= end,
    )
    gift_count = await _count_rows(
        db, GiftTask, GiftTask.family_id == family_id,
        GiftTask.created_at >= start, GiftTask.created_at <= end,
    )

    current_total = (
        mem_count + event_count + insight_count
        + reminder_count + job_count + gift_count
    )

    # Previous period total for comparison
    prev_mem = await _count_rows(
        db, ConversationMemory, ConversationMemory.family_id == family_id,
        ConversationMemory.created_at >= prev_start, ConversationMemory.created_at < start,
    )
    prev_event = await _count_rows(
        db, CuratedEvent, CuratedEvent.family_id == family_id,
        CuratedEvent.created_at >= prev_start, CuratedEvent.created_at < start,
    )
    prev_insight = await _count_rows(
        db, Insight, Insight.family_id == family_id,
        Insight.created_at >= prev_start, Insight.created_at < start,
    )
    prev_reminder = await _count_rows(
        db, EventReminder, EventReminder.user_id == user_id,
        EventReminder.status == "triggered",
        EventReminder.created_at >= prev_start, EventReminder.created_at < start,
    )
    prev_job = await _count_rows(
        db, CurationJob, CurationJob.family_id == family_id,
        CurationJob.created_at >= prev_start, CurationJob.created_at < start,
    )
    prev_gift = await _count_rows(
        db, GiftTask, GiftTask.family_id == family_id,
        GiftTask.created_at >= prev_start, GiftTask.created_at < start,
    )
    prev_total = (
        prev_mem + prev_event + prev_insight
        + prev_reminder + prev_job + prev_gift
    )

    vs_last_period = 0.0
    if prev_total > 0:
        vs_last_period = round((current_total - prev_total) / prev_total * 100, 1)

    return ReportSummaryResponse(
        range=range,
        total_actions=current_total,
        breakdown=ReportBreakdown(
            memories_extracted=mem_count,
            events_managed=event_count,
            insights_generated=insight_count,
            reminders_sent=reminder_count,
            briefings_run=job_count,
            gifts_tracked=gift_count,
        ),
        comparison=ReportComparison(vs_last_period=vs_last_period),
    )


@router.get("/timeline", response_model=TimelineResponse)
async def get_report_timeline(
    range: str = Query("week", pattern="^(today|week|month)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Get chronological activity timeline."""
    from ...modules.conversation.models import ToolExecutionLog
    from ...modules.curation.models import CurationJob

    _, start, end = _get_date_range(range)
    offset = (page - 1) * limit

    # Fetch tool execution logs
    tool_stmt = (
        select(
            ToolExecutionLog.created_at,
            ToolExecutionLog.tool_name,
            ToolExecutionLog.summary,
            ToolExecutionLog.status,
        )
        .where(
            ToolExecutionLog.family_id == family_id,
            ToolExecutionLog.created_at >= start,
            ToolExecutionLog.created_at <= end,
        )
        .order_by(ToolExecutionLog.created_at.desc())
    )
    tool_result = await db.execute(tool_stmt)
    tool_rows = tool_result.all()

    # Fetch curation jobs
    job_stmt = (
        select(
            CurationJob.created_at,
            CurationJob.trigger_type,
            CurationJob.status,
            CurationJob.events_curated,
        )
        .where(
            CurationJob.family_id == family_id,
            CurationJob.created_at >= start,
            CurationJob.created_at <= end,
        )
        .order_by(CurationJob.created_at.desc())
    )
    job_result = await db.execute(job_stmt)
    job_rows = job_result.all()

    # Merge and sort
    items = []
    for row in tool_rows:
        items.append(TimelineItem(
            timestamp=row.created_at.isoformat() if row.created_at else "",
            action_type=row.tool_name or "tool_execution",
            description=row.summary or row.tool_name or "",
            status=row.status or "unknown",
        ))
    for row in job_rows:
        desc = "Curation job ({trigger}): {n} events curated".format(
            trigger=row.trigger_type or "unknown",
            n=row.events_curated or 0,
        )
        items.append(TimelineItem(
            timestamp=row.created_at.isoformat() if row.created_at else "",
            action_type="curation_job",
            description=desc,
            status=row.status or "unknown",
        ))

    # Sort by timestamp descending
    items.sort(key=lambda x: x.timestamp, reverse=True)

    total = len(items)
    paginated = items[offset:offset + limit]

    return TimelineResponse(items=paginated, total=total, page=page)


# ==================== Internal Helpers ====================


async def _count_rows(db: AsyncSession, model, *conditions) -> int:
    """Count rows in a table matching the given conditions."""
    stmt = select(func.count()).select_from(model).where(and_(*conditions))
    result = await db.execute(stmt)
    return result.scalar() or 0
