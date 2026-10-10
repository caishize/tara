"""
Work Report Service - Aggregates curation and hygiene data for the work report.

Provides summary statistics and detailed views of curation jobs
and hygiene run logs for display in the mobile app.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func, desc
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ....core.utils.timezone import utc_now
from ...curation.models import CurationJob, CuratedEvent, EventAssociation, HygieneRunLog
from ..schemas import (
    WorkReportResponse,
    WorkReportSummary,
    CurationJobSummaryItem,
    CurationJobDetailResponse,
    CuratedEventItem,
    AssociationItem,
    HygieneRunLogItem,
    HygieneRunLogListResponse,
)

logger = get_logger(__name__)


class WorkReportService:
    """Aggregates curation and hygiene data into work reports."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_work_report(
        self,
        family_id: UUID,
        days: int = 30,
        limit: int = 20,
    ) -> WorkReportResponse:
        """Get aggregated work report with summary and recent jobs/logs."""
        cutoff = utc_now() - timedelta(days=days)

        curation_jobs = await self._get_curation_jobs(family_id, cutoff, limit)
        hygiene_logs = await self._get_hygiene_logs(family_id, cutoff, limit)
        summary = await self._build_summary(family_id, cutoff)

        return WorkReportResponse(
            summary=summary,
            curation_jobs=curation_jobs,
            hygiene_logs=hygiene_logs,
        )

    async def get_curation_job_detail(
        self,
        job_id: UUID,
        family_id: UUID,
    ) -> Optional[CurationJobDetailResponse]:
        """Get detailed view of a single curation job."""
        stmt = select(CurationJob).where(
            and_(
                CurationJob.id == job_id,
                CurationJob.family_id == family_id,
            )
        )
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            return None

        job_item = self._to_curation_job_item(job)
        curated_events = await self._get_job_curated_events(job)
        associations = await self._get_job_associations(job)

        return CurationJobDetailResponse(
            job=job_item,
            curated_events=curated_events,
            associations=associations,
        )

    async def get_hygiene_logs(
        self,
        family_id: UUID,
        days: int = 30,
        limit: int = 20,
    ) -> HygieneRunLogListResponse:
        """Get recent hygiene run logs."""
        cutoff = utc_now() - timedelta(days=days)
        logs = await self._get_hygiene_logs(family_id, cutoff, limit)

        count_stmt = (
            select(func.count())
            .select_from(HygieneRunLog)
            .where(
                and_(
                    HygieneRunLog.family_id == family_id,
                    HygieneRunLog.created_at >= cutoff,
                )
            )
        )
        result = await self.session.execute(count_stmt)
        total = result.scalar() or 0

        return HygieneRunLogListResponse(logs=logs, total=total)

    async def _get_curation_jobs(
        self,
        family_id: UUID,
        cutoff: datetime,
        limit: int,
    ) -> List[CurationJobSummaryItem]:
        stmt = (
            select(CurationJob)
            .where(
                and_(
                    CurationJob.family_id == family_id,
                    CurationJob.created_at >= cutoff,
                )
            )
            .order_by(desc(CurationJob.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        jobs = result.scalars().all()
        return [self._to_curation_job_item(j) for j in jobs]

    async def _get_hygiene_logs(
        self,
        family_id: UUID,
        cutoff: datetime,
        limit: int,
    ) -> List[HygieneRunLogItem]:
        stmt = (
            select(HygieneRunLog)
            .where(
                and_(
                    HygieneRunLog.family_id == family_id,
                    HygieneRunLog.created_at >= cutoff,
                )
            )
            .order_by(desc(HygieneRunLog.created_at))
            .limit(limit)
        )
        try:
            result = await self.session.execute(stmt)
            logs = result.scalars().all()
            return [self._to_hygiene_log_item(log) for log in logs]
        except ProgrammingError:
            logger.warning("hygiene_run_logs table does not exist yet; returning empty list")
            await self.session.rollback()
            return []

    async def _build_summary(
        self,
        family_id: UUID,
        cutoff: datetime,
    ) -> WorkReportSummary:
        curation_stats_stmt = (
            select(
                func.count().label("total"),
                func.count().filter(CurationJob.status == "completed").label("success"),
                func.count().filter(CurationJob.status == "failed").label("failed"),
                func.coalesce(func.sum(CurationJob.events_curated), 0).label("events_curated"),
                func.coalesce(func.sum(CurationJob.associations_created), 0).label("associations"),
            )
            .select_from(CurationJob)
            .where(
                and_(
                    CurationJob.family_id == family_id,
                    CurationJob.created_at >= cutoff,
                )
            )
        )
        result = await self.session.execute(curation_stats_stmt)
        curation = result.one()

        hygiene_total = 0
        hygiene_actions = 0
        try:
            hygiene_stats_stmt = (
                select(
                    func.count().label("total"),
                    func.coalesce(func.sum(HygieneRunLog.total_actions), 0).label("actions"),
                )
                .select_from(HygieneRunLog)
                .where(
                    and_(
                        HygieneRunLog.family_id == family_id,
                        HygieneRunLog.created_at >= cutoff,
                    )
                )
            )
            result = await self.session.execute(hygiene_stats_stmt)
            hygiene = result.one()
            hygiene_total = hygiene.total
            hygiene_actions = int(hygiene.actions)
        except ProgrammingError:
            logger.warning("hygiene_run_logs table does not exist yet; skipping hygiene stats")
            await self.session.rollback()

        return WorkReportSummary(
            total_curation_runs=curation.total,
            successful_curation_runs=curation.success,
            failed_curation_runs=curation.failed,
            total_events_curated=int(curation.events_curated),
            total_associations_created=int(curation.associations),
            total_hygiene_runs=hygiene_total,
            total_hygiene_actions=hygiene_actions,
        )

    async def _get_job_curated_events(
        self,
        job: CurationJob,
    ) -> List[CuratedEventItem]:
        """Get curated events created by this job (by time window)."""
        if not job.started_at or not job.completed_at:
            return []

        stmt = (
            select(CuratedEvent)
            .where(
                and_(
                    CuratedEvent.family_id == job.family_id,
                    CuratedEvent.created_at >= job.started_at,
                    CuratedEvent.created_at <= job.completed_at + timedelta(seconds=5),
                )
            )
            .order_by(CuratedEvent.normalized_start)
            .limit(100)
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()

        return [
            CuratedEventItem(
                id=str(e.id),
                title=e.title,
                event_type=e.event_type,
                source_types=e.source_types or [],
                merged_count=e.merged_count,
                dedup_reason=e.dedup_reason,
                start_time=e.normalized_start,
                end_time=e.normalized_end,
                status=e.status,
            )
            for e in events
        ]

    async def _get_job_associations(
        self,
        job: CurationJob,
    ) -> List[AssociationItem]:
        """Get associations created by this job (by time window)."""
        if not job.started_at or not job.completed_at:
            return []

        stmt = (
            select(EventAssociation)
            .where(
                and_(
                    EventAssociation.family_id == job.family_id,
                    EventAssociation.created_at >= job.started_at,
                    EventAssociation.created_at <= job.completed_at + timedelta(seconds=5),
                )
            )
            .order_by(EventAssociation.created_at)
            .limit(100)
        )
        result = await self.session.execute(stmt)
        associations = result.scalars().all()

        return [
            AssociationItem(
                id=str(a.id),
                title=a.title,
                association_type=a.association_type,
                target_type=a.target_type,
                reason=a.reason,
                priority=a.priority,
                confidence=a.confidence,
            )
            for a in associations
        ]

    @staticmethod
    def _to_curation_job_item(job: CurationJob) -> CurationJobSummaryItem:
        return CurationJobSummaryItem(
            job_id=str(job.id),
            status=job.status,
            trigger_type=job.trigger_type,
            date_range_start=job.date_range_start,
            date_range_end=job.date_range_end,
            events_processed=job.events_processed,
            events_curated=job.events_curated,
            associations_created=job.associations_created,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
            error_message=job.error_message,
        )

    @staticmethod
    def _to_hygiene_log_item(log: HygieneRunLog) -> HygieneRunLogItem:
        return HygieneRunLogItem(
            id=str(log.id),
            family_id=str(log.family_id),
            inactive_deleted=log.inactive_deleted,
            cancelled_deleted=log.cancelled_deleted,
            dismissed_deleted=log.dismissed_deleted,
            auto_completed=log.auto_completed,
            jobs_purged=log.jobs_purged,
            total_actions=log.total_actions,
            status=log.status,
            error_message=log.error_message,
            started_at=log.started_at,
            completed_at=log.completed_at,
            duration_seconds=log.duration_seconds,
            created_at=log.created_at,
        )
