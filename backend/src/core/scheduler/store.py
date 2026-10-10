"""
Job Execution Store

Persistence layer for job execution history.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID
from collections import defaultdict

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.timezone import utc_now
from .execution import JobExecution, JobExecutionStatus, TriggerType


logger = logging.getLogger(__name__)


class JobExecutionStore:
    """
    Store for job execution history.

    Provides methods to save and query job executions.
    Can operate with or without a database session (in-memory fallback).
    """

    def __init__(self, max_in_memory: int = 1000):
        """
        Initialize the store.

        Args:
            max_in_memory: Maximum executions to keep in memory (LRU)
        """
        self.max_in_memory = max_in_memory
        self._executions: List[JobExecution] = []
        self._stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "total": 0,
            "success": 0,
            "failed": 0,
            "timeout": 0,
            "cancelled": 0,
            "total_duration_ms": 0,
        })

    async def save(
        self,
        execution: JobExecution,
        session: Optional[AsyncSession] = None
    ) -> None:
        """
        Save a job execution record.

        Args:
            execution: The execution to save
            session: Optional database session for persistence
        """
        # Update in-memory store
        self._executions.append(execution)
        if len(self._executions) > self.max_in_memory:
            self._executions.pop(0)

        # Update stats
        key = f"{execution.scheduler_name}:{execution.job_name}"
        self._stats[key]["total"] += 1

        if execution.status == JobExecutionStatus.COMPLETED:
            self._stats[key]["success"] += 1
        elif execution.status == JobExecutionStatus.FAILED:
            self._stats[key]["failed"] += 1
        elif execution.status == JobExecutionStatus.TIMEOUT:
            self._stats[key]["timeout"] += 1
        elif execution.status == JobExecutionStatus.CANCELLED:
            self._stats[key]["cancelled"] += 1

        if execution.duration_ms:
            self._stats[key]["total_duration_ms"] += execution.duration_ms

        # Persist to database if session provided
        if session:
            try:
                from .job_execution import JobExecutionModel
                model = JobExecutionModel(
                    id=execution.id,
                    job_name=execution.job_name,
                    scheduler_name=execution.scheduler_name,
                    status=execution.status.value,
                    trigger_type=execution.trigger_type.value,
                    started_at=execution.started_at,
                    completed_at=execution.completed_at,
                    duration_ms=execution.duration_ms,
                    error_message=execution.error_message,
                    error_traceback=execution.error_traceback,
                    result_summary=execution.result_summary,
                    created_at=execution.created_at,
                )
                session.add(model)
                await session.commit()
            except Exception as e:
                logger.warning(f"Failed to persist execution to database: {e}")
                # Continue with in-memory only

    async def get_recent_executions(
        self,
        job_name: Optional[str] = None,
        scheduler_name: Optional[str] = None,
        status: Optional[JobExecutionStatus] = None,
        limit: int = 100,
        offset: int = 0,
        session: Optional[AsyncSession] = None
    ) -> List[JobExecution]:
        """
        Get recent job executions.

        Args:
            job_name: Filter by job name
            scheduler_name: Filter by scheduler name
            status: Filter by status
            limit: Maximum number of results
            offset: Number of results to skip
            session: Optional database session

        Returns:
            List of matching executions
        """
        # Try database first if session provided
        if session:
            try:
                from .job_execution import JobExecutionModel
                query = select(JobExecutionModel).order_by(
                    desc(JobExecutionModel.created_at)
                )

                conditions = []
                if job_name:
                    conditions.append(JobExecutionModel.job_name == job_name)
                if scheduler_name:
                    conditions.append(JobExecutionModel.scheduler_name == scheduler_name)
                if status:
                    conditions.append(JobExecutionModel.status == status.value)

                if conditions:
                    query = query.where(and_(*conditions))

                query = query.offset(offset).limit(limit)
                result = await session.execute(query)
                models = result.scalars().all()

                return [
                    JobExecution(
                        id=m.id,
                        job_name=m.job_name,
                        scheduler_name=m.scheduler_name,
                        status=JobExecutionStatus(m.status),
                        trigger_type=TriggerType(m.trigger_type),
                        started_at=m.started_at,
                        completed_at=m.completed_at,
                        duration_ms=m.duration_ms,
                        error_message=m.error_message,
                        error_traceback=m.error_traceback,
                        result_summary=m.result_summary,
                        created_at=m.created_at,
                    )
                    for m in models
                ]
            except Exception as e:
                logger.warning(f"Failed to query database, using in-memory: {e}")

        # Fallback to in-memory
        results = self._executions.copy()
        results.reverse()  # Most recent first

        if job_name:
            results = [e for e in results if e.job_name == job_name]
        if scheduler_name:
            results = [e for e in results if e.scheduler_name == scheduler_name]
        if status:
            results = [e for e in results if e.status == status]

        return results[offset:offset + limit]

    async def get_stats(
        self,
        scheduler_name: str,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Get statistics for a scheduler.

        Args:
            scheduler_name: Name of the scheduler
            session: Optional database session

        Returns:
            Statistics dict with total, success, failed counts, avg_duration
        """
        # Aggregate from in-memory stats
        total = 0
        success = 0
        failed = 0
        timeout = 0
        cancelled = 0
        total_duration = 0

        for key, stats in self._stats.items():
            if key.startswith(f"{scheduler_name}:"):
                total += stats["total"]
                success += stats["success"]
                failed += stats["failed"]
                timeout += stats["timeout"]
                cancelled += stats["cancelled"]
                total_duration += stats["total_duration_ms"]

        avg_duration = total_duration // total if total > 0 else 0

        return {
            "total_executions": total,
            "success_count": success,
            "failed_count": failed,
            "timeout_count": timeout,
            "cancelled_count": cancelled,
            "avg_duration_ms": avg_duration,
            "success_rate": round(success / total * 100, 2) if total > 0 else 0,
        }

    async def get_last_execution(
        self,
        job_name: str,
        scheduler_name: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[JobExecution]:
        """
        Get the last execution for a specific job.

        Args:
            job_name: Name of the job
            scheduler_name: Name of the scheduler
            session: Optional database session

        Returns:
            The last execution or None
        """
        executions = await self.get_recent_executions(
            job_name=job_name,
            scheduler_name=scheduler_name,
            limit=1,
            session=session
        )
        return executions[0] if executions else None

    async def cleanup_old_executions(
        self,
        days: int = 30,
        session: Optional[AsyncSession] = None
    ) -> int:
        """
        Clean up execution records older than specified days.

        Args:
            days: Number of days to keep
            session: Optional database session

        Returns:
            Number of records deleted
        """
        cutoff = utc_now() - timedelta(days=days)
        deleted = 0

        # Clean in-memory
        original_count = len(self._executions)
        self._executions = [
            e for e in self._executions
            if e.created_at >= cutoff
        ]
        deleted += original_count - len(self._executions)

        # Clean database if session provided
        if session:
            try:
                from .job_execution import JobExecutionModel
                from sqlalchemy import delete
                stmt = delete(JobExecutionModel).where(
                    JobExecutionModel.created_at < cutoff
                )
                result = await session.execute(stmt)
                await session.commit()
                deleted += result.rowcount or 0
            except Exception as e:
                logger.warning(f"Failed to cleanup database: {e}")

        logger.info(f"Cleaned up {deleted} old execution records")
        return deleted


# Global store instance
execution_store = JobExecutionStore()
