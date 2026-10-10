"""
Scheduler Manager

Central manager for all schedulers in the application.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from .base import BaseScheduler, SchedulerStatus
from .execution import JobExecution


logger = logging.getLogger(__name__)


class SchedulerManager:
    """
    Central manager for all schedulers.

    Provides:
    - Registration of multiple schedulers
    - Bulk start/stop operations
    - Aggregated status querying
    - Manual job triggering

    Example usage:
        manager = SchedulerManager()
        manager.register("reminders", reminder_scheduler)
        manager.register("gifts", gift_scheduler)
        await manager.start_all()
    """

    _instance: Optional["SchedulerManager"] = None

    def __new__(cls) -> "SchedulerManager":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the manager (only once due to singleton)."""
        if self._initialized:
            return

        self._schedulers: Dict[str, BaseScheduler] = {}
        self._started = False
        self._initialized = True

    def register(self, name: str, scheduler: BaseScheduler) -> None:
        """
        Register a scheduler with the manager.

        Args:
            name: Unique name for the scheduler
            scheduler: The scheduler instance to register

        Raises:
            ValueError: If a scheduler with the same name already exists
        """
        if name in self._schedulers:
            raise ValueError(f"Scheduler '{name}' already registered")

        self._schedulers[name] = scheduler
        logger.info(f"Registered scheduler '{name}' ({scheduler.scheduler_type})")

    def unregister(self, name: str) -> Optional[BaseScheduler]:
        """
        Unregister a scheduler.

        Args:
            name: Name of the scheduler to unregister

        Returns:
            The unregistered scheduler, or None if not found
        """
        scheduler = self._schedulers.pop(name, None)
        if scheduler:
            logger.info(f"Unregistered scheduler '{name}'")
        return scheduler

    def get(self, name: str) -> Optional[BaseScheduler]:
        """Get a scheduler by name."""
        return self._schedulers.get(name)

    def get_all(self) -> Dict[str, BaseScheduler]:
        """Get all registered schedulers."""
        return self._schedulers.copy()

    async def start_all(self) -> None:
        """Start all registered schedulers."""
        if self._started:
            logger.warning("Scheduler manager already started")
            return

        logger.info(f"Starting {len(self._schedulers)} schedulers...")

        # Start all schedulers concurrently
        tasks = []
        for name, scheduler in self._schedulers.items():
            logger.info(f"Starting scheduler '{name}'...")
            tasks.append(scheduler.start())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._started = True
        logger.info("All schedulers started")

    async def stop_all(self, timeout: float = 30.0) -> None:
        """
        Stop all registered schedulers.

        Args:
            timeout: Maximum time to wait for each scheduler to stop
        """
        if not self._started:
            return

        logger.info(f"Stopping {len(self._schedulers)} schedulers...")

        # Stop all schedulers concurrently
        tasks = []
        for name, scheduler in self._schedulers.items():
            logger.info(f"Stopping scheduler '{name}'...")
            tasks.append(scheduler.stop(timeout=timeout))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._started = False
        logger.info("All schedulers stopped")

    async def pause_all(self) -> None:
        """Pause all registered schedulers."""
        logger.info("Pausing all schedulers...")
        for scheduler in self._schedulers.values():
            await scheduler.pause()

    async def resume_all(self) -> None:
        """Resume all registered schedulers."""
        logger.info("Resuming all schedulers...")
        for scheduler in self._schedulers.values():
            await scheduler.resume()

    async def get_all_status(self) -> List[SchedulerStatus]:
        """Get status of all registered schedulers."""
        statuses = []
        for scheduler in self._schedulers.values():
            status = await scheduler.get_status()
            statuses.append(status)
        return statuses

    async def trigger_job(
        self,
        scheduler_name: str,
        job_name: str
    ) -> JobExecution:
        """
        Manually trigger a job execution.

        Args:
            scheduler_name: Name of the scheduler
            job_name: Name of the job to trigger

        Returns:
            The job execution record

        Raises:
            ValueError: If scheduler or job not found
        """
        scheduler = self.get(scheduler_name)
        if not scheduler:
            raise ValueError(f"Scheduler '{scheduler_name}' not found")

        return await scheduler.trigger_job(job_name)

    def is_job_running(self, scheduler_name: str, job_name: str) -> bool:
        """
        Check if a job is currently running.

        Args:
            scheduler_name: Name of the scheduler
            job_name: Name of the job

        Returns:
            True if the job is running
        """
        scheduler = self.get(scheduler_name)
        if not scheduler:
            return False
        return scheduler.is_job_running(job_name)

    @property
    def is_started(self) -> bool:
        """Check if the manager has started all schedulers."""
        return self._started

    def reset(self) -> None:
        """
        Reset the manager (for testing purposes).

        Warning: This will clear all registered schedulers.
        """
        self._schedulers.clear()
        self._started = False


# Global manager instance
scheduler_manager = SchedulerManager()
