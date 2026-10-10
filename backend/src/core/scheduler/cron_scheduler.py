"""
Cron Scheduler

Executes jobs based on cron expressions.
"""

import asyncio
import logging
from datetime import datetime, date
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from croniter import croniter

from .base import BaseScheduler
from .job import ScheduledJob, CronJob
from ..utils.timezone import DEFAULT_TIMEZONE


logger = logging.getLogger(__name__)


class CronScheduler(BaseScheduler):
    """
    Scheduler that executes jobs based on cron expressions.

    Each job can have its own cron expression, or all jobs can share
    a common schedule defined at the scheduler level.

    Example usage:
        scheduler = CronScheduler("gift_tasks")
        scheduler.register_job(CronJob(
            name="process_tasks",
            func=process_pending_tasks,
            cron_expression="0 2 * * *",  # 02:00 daily
            description="Process pending gift tasks"
        ))
        await scheduler.start()
    """

    def __init__(
        self,
        name: str,
        default_cron: str = "0 * * * *",  # Every hour by default
        timezone: Optional[ZoneInfo] = None,
        check_interval: int = 60,  # Check every minute
        batch_size: int = 50
    ):
        """
        Initialize the cron scheduler.

        Args:
            name: Unique name for this scheduler
            default_cron: Default cron expression for jobs without one
            timezone: Timezone for cron evaluation
            check_interval: How often to check if jobs should run (seconds)
            batch_size: Maximum jobs to process per trigger
        """
        super().__init__(name, batch_size)
        self.default_cron = default_cron
        self.timezone = timezone or DEFAULT_TIMEZONE
        self.check_interval = check_interval
        self._last_run_dates: Dict[str, date] = {}  # Track daily execution

    @property
    def scheduler_type(self) -> str:
        return "CronScheduler"

    def register_job(self, job: ScheduledJob) -> None:
        """Register a job, wrapping in CronJob if needed."""
        if not isinstance(job, CronJob):
            # Wrap regular job with default cron expression
            cron_job = CronJob(
                name=job.name,
                func=job.func,
                description=job.description,
                priority=job.priority,
                timeout_seconds=job.timeout_seconds,
                max_retries=job.max_retries,
                retry_delay_seconds=job.retry_delay_seconds,
                enabled=job.enabled,
                depends_on=job.depends_on,
                tags=job.tags,
                cron_expression=self.default_cron,
            )
            super().register_job(cron_job)
        else:
            super().register_job(job)

        # Update next run time
        self._update_next_run(job.name)

    def _update_next_run(self, job_name: str) -> None:
        """Update the next run time for a job."""
        job = self.get_job(job_name)
        if job and isinstance(job, CronJob):
            now = datetime.now(self.timezone)
            cron = croniter(job.cron_expression, now)
            job.next_run = cron.get_next(datetime)

    def _should_run_today(self, job_name: str) -> bool:
        """
        Check if a job should run today (hasn't run yet today).

        This prevents multiple executions on the same day when
        the cron expression matches multiple times.
        """
        today = datetime.now(self.timezone).date()
        last_run = self._last_run_dates.get(job_name)
        return last_run != today

    def _mark_run_today(self, job_name: str) -> None:
        """Mark a job as having run today."""
        today = datetime.now(self.timezone).date()
        self._last_run_dates[job_name] = today

    async def _run(self) -> None:
        """Main scheduler loop - checks and runs jobs based on cron."""
        logger.info(
            f"CronScheduler '{self.name}' loop started "
            f"(check_interval={self.check_interval}s, timezone={self.timezone})"
        )

        while self._running:
            try:
                # Check if any jobs should run
                if not self._paused:
                    await self._check_and_run_jobs()

                # Wait for next check
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                logger.info(f"CronScheduler '{self.name}' loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in CronScheduler '{self.name}' loop: {e}", exc_info=True)

    async def _check_and_run_jobs(self) -> None:
        """Check which jobs should run and execute them."""
        now = datetime.now(self.timezone)
        jobs_to_run = []

        for job in self.get_enabled_jobs():
            if not isinstance(job, CronJob):
                continue

            # Check if cron matches current time
            cron = croniter(job.cron_expression, now - datetime.resolution)
            next_time = cron.get_next(datetime)

            # Job should run if next_time is within the check interval
            time_diff = (next_time - now).total_seconds()
            if -self.check_interval < time_diff <= 0:
                # Check if already ran today (for daily jobs)
                if self._is_daily_job(job) and not self._should_run_today(job.name):
                    logger.debug(f"Job '{job.name}' already ran today, skipping")
                    continue

                jobs_to_run.append(job)

        # Execute jobs
        for job in jobs_to_run[:self.batch_size]:
            if not self._running:
                break

            try:
                await self._execute_job(job)
                self._mark_run_today(job.name)
                self._update_next_run(job.name)
            except Exception as e:
                logger.error(f"Failed to execute job '{job.name}': {e}", exc_info=True)

    def _is_daily_job(self, job: CronJob) -> bool:
        """
        Check if a job runs at most once per day.

        This is a heuristic based on the cron expression.
        Jobs with hour and minute but not wildcards are considered daily.
        """
        parts = job.cron_expression.split()
        if len(parts) < 2:
            return False

        minute, hour = parts[0], parts[1]
        # If both minute and hour are specific (not wildcards), it's a daily job
        return minute != "*" and hour != "*"

    def get_next_run_times(self) -> Dict[str, datetime]:
        """Get the next scheduled run time for all jobs."""
        result = {}
        now = datetime.now(self.timezone)

        for job in self.get_enabled_jobs():
            if isinstance(job, CronJob):
                cron = croniter(job.cron_expression, now)
                result[job.name] = cron.get_next(datetime)

        return result

    async def get_status(self):
        """Get status with cron-specific info."""
        status = await super().get_status()
        status.stats["timezone"] = str(self.timezone)
        status.stats["check_interval"] = self.check_interval

        # Add next run times to jobs
        next_runs = self.get_next_run_times()
        for job_info in status.jobs:
            if job_info["name"] in next_runs:
                job_info["next_run"] = next_runs[job_info["name"]].isoformat()

        return status


class MultiCronScheduler(CronScheduler):
    """
    A scheduler that can handle multiple cron expressions for different jobs.

    This is the recommended way to group related jobs that run on different
    schedules (e.g., gift tasks at 02:00, 03:00, 04:00, 05:00).
    """

    def __init__(
        self,
        name: str,
        timezone: Optional[ZoneInfo] = None,
        check_interval: int = 60,
        batch_size: int = 50
    ):
        """
        Initialize the multi-cron scheduler.

        Args:
            name: Unique name for this scheduler
            timezone: Timezone for cron evaluation
            check_interval: How often to check if jobs should run
            batch_size: Maximum jobs to process per trigger
        """
        super().__init__(
            name=name,
            default_cron="* * * * *",  # Not used, each job has its own
            timezone=timezone,
            check_interval=check_interval,
            batch_size=batch_size
        )

    def register_cron_job(
        self,
        name: str,
        func: callable,
        cron_expression: str,
        description: str = "",
        **kwargs
    ) -> CronJob:
        """
        Convenience method to register a job with a cron expression.

        Args:
            name: Job name
            func: Async function to execute
            cron_expression: Cron expression for scheduling
            description: Human-readable description
            **kwargs: Additional ScheduledJob arguments

        Returns:
            The registered CronJob
        """
        job = CronJob(
            name=name,
            func=func,
            cron_expression=cron_expression,
            description=description,
            **kwargs
        )
        self.register_job(job)
        return job
