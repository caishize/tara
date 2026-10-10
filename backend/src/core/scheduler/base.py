"""
Base Scheduler

Abstract base class for all scheduler implementations.
"""

import asyncio
import logging
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

from ..utils.timezone import utc_now
from .execution import JobExecution, JobExecutionStatus, TriggerType
from .job import ScheduledJob
from .store import execution_store


logger = logging.getLogger(__name__)


class SchedulerStatus:
    """Status information for a scheduler."""

    def __init__(
        self,
        name: str,
        scheduler_type: str,
        is_running: bool,
        is_paused: bool,
        started_at: Optional[datetime],
        jobs: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ):
        self.name = name
        self.scheduler_type = scheduler_type
        self.is_running = is_running
        self.is_paused = is_paused
        self.started_at = started_at
        self.jobs = jobs
        self.stats = stats

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "type": self.scheduler_type,
            "status": "running" if self.is_running else ("paused" if self.is_paused else "stopped"),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "jobs": self.jobs,
            "stats": self.stats,
        }


class BaseScheduler(ABC):
    """
    Abstract base class for schedulers.

    Provides common functionality for all scheduler types:
    - Job registration and management
    - Execution tracking
    - Start/stop lifecycle
    - Pause/resume support
    - Duplicate execution prevention
    """

    def __init__(self, name: str, batch_size: int = 50):
        """
        Initialize the scheduler.

        Args:
            name: Unique name for this scheduler
            batch_size: Maximum number of tasks to process per batch
        """
        self.name = name
        self.batch_size = batch_size
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._paused = False
        self._started_at: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None
        self._running_jobs: Set[str] = set()  # Jobs currently executing
        self._lock = asyncio.Lock()

    @property
    def scheduler_type(self) -> str:
        """Return the type name of this scheduler."""
        return self.__class__.__name__

    def register_job(self, job: ScheduledJob) -> None:
        """
        Register a job with this scheduler.

        Args:
            job: The job to register

        Raises:
            ValueError: If a job with the same name already exists
        """
        if job.name in self._jobs:
            raise ValueError(f"Job '{job.name}' already registered in scheduler '{self.name}'")
        self._jobs[job.name] = job
        logger.info(f"Registered job '{job.name}' in scheduler '{self.name}'")

    def unregister_job(self, job_name: str) -> Optional[ScheduledJob]:
        """
        Unregister a job from this scheduler.

        Args:
            job_name: Name of the job to unregister

        Returns:
            The unregistered job, or None if not found
        """
        job = self._jobs.pop(job_name, None)
        if job:
            logger.info(f"Unregistered job '{job_name}' from scheduler '{self.name}'")
        return job

    def get_job(self, job_name: str) -> Optional[ScheduledJob]:
        """Get a job by name."""
        return self._jobs.get(job_name)

    def get_all_jobs(self) -> List[ScheduledJob]:
        """Get all registered jobs."""
        return list(self._jobs.values())

    def get_enabled_jobs(self) -> List[ScheduledJob]:
        """Get all enabled jobs, sorted by priority."""
        jobs = [j for j in self._jobs.values() if j.enabled]
        return sorted(jobs, key=lambda j: j.priority)

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning(f"Scheduler '{self.name}' is already running")
            return

        self._running = True
        self._paused = False
        self._started_at = utc_now()
        self._task = asyncio.create_task(self._run())
        logger.info(f"Scheduler '{self.name}' started")

    async def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the scheduler.

        Args:
            timeout: Maximum time to wait for current jobs to complete
        """
        if not self._running:
            return

        logger.info(f"Stopping scheduler '{self.name}'...")
        self._running = False

        if self._task:
            # Wait for the scheduler task to complete
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Scheduler '{self.name}' stop timed out after {timeout}s, cancelling..."
                )
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass

            self._task = None

        self._started_at = None
        logger.info(f"Scheduler '{self.name}' stopped")

    async def pause(self) -> None:
        """Pause the scheduler (jobs stop executing but scheduler keeps running)."""
        if not self._running:
            logger.warning(f"Cannot pause scheduler '{self.name}' - not running")
            return

        self._paused = True
        logger.info(f"Scheduler '{self.name}' paused")

    async def resume(self) -> None:
        """Resume a paused scheduler."""
        if not self._running:
            logger.warning(f"Cannot resume scheduler '{self.name}' - not running")
            return

        self._paused = False
        logger.info(f"Scheduler '{self.name}' resumed")

    @abstractmethod
    async def _run(self) -> None:
        """
        Main scheduler loop. Must be implemented by subclasses.

        This method should:
        1. Run in a loop while self._running is True
        2. Check self._paused before executing jobs
        3. Call self._execute_job() to run individual jobs
        """
        pass

    async def _execute_job(
        self,
        job: ScheduledJob,
        trigger_type: TriggerType = TriggerType.SCHEDULED
    ) -> JobExecution:
        """
        Execute a single job with tracking and error handling.

        Args:
            job: The job to execute
            trigger_type: How the execution was triggered

        Returns:
            The execution record
        """
        # Check for duplicate execution
        async with self._lock:
            if job.name in self._running_jobs:
                logger.warning(
                    f"Job '{job.name}' is already running in scheduler '{self.name}', skipping"
                )
                execution = JobExecution(
                    job_name=job.name,
                    scheduler_name=self.name,
                    trigger_type=trigger_type,
                )
                execution.status = JobExecutionStatus.CANCELLED
                execution.error_message = "Job already running"
                return execution

            self._running_jobs.add(job.name)

        execution = JobExecution(
            job_name=job.name,
            scheduler_name=self.name,
            trigger_type=trigger_type,
        )

        try:
            execution.start()
            logger.debug(f"Executing job '{job.name}' in scheduler '{self.name}'")

            # Execute with timeout
            try:
                result = await asyncio.wait_for(
                    job.func(),
                    timeout=job.timeout_seconds
                )
                execution.complete(result_summary=result)
                job.record_success()
                logger.debug(
                    f"Job '{job.name}' completed successfully "
                    f"(duration: {execution.duration_ms}ms)"
                )
            except asyncio.TimeoutError:
                execution.timeout()
                job.record_failure()
                logger.error(
                    f"Job '{job.name}' timed out after {job.timeout_seconds}s"
                )
            except Exception as e:
                tb = traceback.format_exc()
                execution.fail(str(e), tb)
                job.record_failure()
                logger.error(
                    f"Job '{job.name}' failed: {e}",
                    exc_info=True
                )

        finally:
            # Remove from running set
            async with self._lock:
                self._running_jobs.discard(job.name)

            # Save execution record
            await execution_store.save(execution)

        return execution

    async def trigger_job(self, job_name: str) -> JobExecution:
        """
        Manually trigger a job execution.

        Args:
            job_name: Name of the job to trigger

        Returns:
            The execution record

        Raises:
            ValueError: If job not found
        """
        job = self.get_job(job_name)
        if not job:
            raise ValueError(f"Job '{job_name}' not found in scheduler '{self.name}'")

        logger.info(f"Manually triggering job '{job_name}'")
        return await self._execute_job(job, TriggerType.MANUAL)

    def is_job_running(self, job_name: str) -> bool:
        """Check if a job is currently running."""
        return job_name in self._running_jobs

    async def get_status(self) -> SchedulerStatus:
        """Get the current status of this scheduler."""
        stats = await execution_store.get_stats(self.name)
        jobs_info = []

        for job in self._jobs.values():
            job_info = job.to_dict()
            job_info["is_running"] = job.name in self._running_jobs
            jobs_info.append(job_info)

        return SchedulerStatus(
            name=self.name,
            scheduler_type=self.scheduler_type,
            is_running=self._running,
            is_paused=self._paused,
            started_at=self._started_at,
            jobs=jobs_info,
            stats=stats,
        )
