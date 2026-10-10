"""
Interval Scheduler

Executes jobs at fixed time intervals.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from ..utils.timezone import utc_now
from .base import BaseScheduler
from .job import ScheduledJob


logger = logging.getLogger(__name__)


class IntervalScheduler(BaseScheduler):
    """
    Scheduler that executes jobs at fixed intervals.

    Example usage:
        scheduler = IntervalScheduler("reminder", interval_seconds=60)
        scheduler.register_job(ScheduledJob(
            name="send_reminders",
            func=send_pending_reminders,
            description="Send pending reminders"
        ))
        await scheduler.start()
    """

    def __init__(
        self,
        name: str,
        interval_seconds: int = 60,
        batch_size: int = 50,
        run_immediately: bool = False
    ):
        """
        Initialize the interval scheduler.

        Args:
            name: Unique name for this scheduler
            interval_seconds: Time between job executions
            batch_size: Maximum jobs to process per interval
            run_immediately: Whether to run jobs immediately on start
        """
        super().__init__(name, batch_size)
        self.interval_seconds = interval_seconds
        self.run_immediately = run_immediately
        self._last_run: Optional[datetime] = None

    @property
    def scheduler_type(self) -> str:
        return "IntervalScheduler"

    async def _run(self) -> None:
        """Main scheduler loop - runs jobs at fixed intervals."""
        logger.info(
            f"IntervalScheduler '{self.name}' loop started "
            f"(interval={self.interval_seconds}s, batch_size={self.batch_size})"
        )

        # Run immediately if configured
        if self.run_immediately and not self._paused:
            await self._run_all_jobs()

        while self._running:
            try:
                # Wait for next interval
                await asyncio.sleep(self.interval_seconds)

                # Skip if paused
                if self._paused:
                    logger.debug(f"Scheduler '{self.name}' is paused, skipping interval")
                    continue

                # Run all enabled jobs
                await self._run_all_jobs()

            except asyncio.CancelledError:
                logger.info(f"IntervalScheduler '{self.name}' loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in IntervalScheduler '{self.name}' loop: {e}", exc_info=True)
                # Continue running, don't let one error stop the scheduler

    async def _run_all_jobs(self) -> None:
        """Execute all enabled jobs."""
        self._last_run = utc_now()
        jobs = self.get_enabled_jobs()

        if not jobs:
            logger.debug(f"No enabled jobs in scheduler '{self.name}'")
            return

        logger.debug(f"Running {len(jobs)} jobs in scheduler '{self.name}'")

        # Run jobs in priority order, up to batch_size
        for job in jobs[:self.batch_size]:
            if not self._running:
                break

            try:
                await self._execute_job(job)
            except Exception as e:
                logger.error(f"Failed to execute job '{job.name}': {e}", exc_info=True)

            # Small delay between jobs to avoid overwhelming resources
            if self._running:
                await asyncio.sleep(0.1)

    async def get_status(self):
        """Get status with interval-specific info."""
        status = await super().get_status()
        status.stats["interval_seconds"] = self.interval_seconds
        if self._last_run:
            next_run = self._last_run + timedelta(seconds=self.interval_seconds)
            status.stats["next_run"] = next_run.isoformat()
        return status


class ConditionalIntervalScheduler(IntervalScheduler):
    """
    Interval scheduler that only runs when a condition is met.

    Useful for promotional period price checks that should only run
    during specific time periods.
    """

    def __init__(
        self,
        name: str,
        interval_seconds: int = 60,
        batch_size: int = 50,
        run_immediately: bool = False,
        condition_func: Optional[callable] = None
    ):
        """
        Initialize the conditional interval scheduler.

        Args:
            name: Unique name for this scheduler
            interval_seconds: Time between job executions
            batch_size: Maximum jobs to process per interval
            run_immediately: Whether to run jobs immediately on start
            condition_func: Function that returns True if jobs should run
        """
        super().__init__(name, interval_seconds, batch_size, run_immediately)
        self._condition_func = condition_func or (lambda: True)

    @property
    def scheduler_type(self) -> str:
        return "ConditionalIntervalScheduler"

    def set_condition(self, condition_func: callable) -> None:
        """Set the condition function."""
        self._condition_func = condition_func

    async def _run_all_jobs(self) -> None:
        """Execute all enabled jobs if condition is met."""
        if not self._condition_func():
            logger.debug(
                f"Condition not met for scheduler '{self.name}', skipping jobs"
            )
            return

        await super()._run_all_jobs()
