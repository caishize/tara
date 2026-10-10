"""
Unified Scheduler Framework

This module provides a unified scheduling framework for all background tasks
in the secretary application, including:
- Date reminders
- Gift task processing
- Price monitoring
- Redis Sorted Set based per-entity scheduling

Key components:
- BaseScheduler: Abstract base class for all schedulers
- IntervalScheduler: Fixed interval execution
- CronScheduler: Cron expression based execution
- SchedulerManager: Central manager for all schedulers
- RedisScheduleStore: Redis Sorted Set per-entity scheduling
"""

from .execution import (
    JobExecutionStatus,
    TriggerType,
    JobExecution,
    JobPriority,
)
from .job import ScheduledJob, CronJob
from .retry import (
    RetryPolicy,
    FixedRetryPolicy,
    ExponentialRetryPolicy,
    RetryConfig,
)
from .base import BaseScheduler
from .interval_scheduler import IntervalScheduler, ConditionalIntervalScheduler
from .cron_scheduler import CronScheduler, MultiCronScheduler
from .manager import SchedulerManager, scheduler_manager
from .store import JobExecutionStore
from .redis_scheduler import (
    RedisScheduleStore,
    SyncRedisScheduleStore,
    TaskScheduleConfig,
    ScheduleType,
    calculate_next_run,
)
from ._async_compat import run_async
from .reschedule import reschedule_sync, reschedule_async
from .lifecycle import (
    on_user_activated,
    on_user_deactivated,
    on_family_activated,
    on_family_deactivated,
)

__all__ = [
    # Execution
    "JobExecutionStatus",
    "TriggerType",
    "JobExecution",
    "JobPriority",
    # Job
    "ScheduledJob",
    "CronJob",
    # Retry
    "RetryPolicy",
    "FixedRetryPolicy",
    "ExponentialRetryPolicy",
    "RetryConfig",
    # Schedulers
    "BaseScheduler",
    "IntervalScheduler",
    "ConditionalIntervalScheduler",
    "CronScheduler",
    "MultiCronScheduler",
    # Manager
    "SchedulerManager",
    "scheduler_manager",
    # Store
    "JobExecutionStore",
    # Redis Sorted Set Scheduler
    "RedisScheduleStore",
    "SyncRedisScheduleStore",
    "TaskScheduleConfig",
    "ScheduleType",
    "calculate_next_run",
    "run_async",
    "reschedule_sync",
    "reschedule_async",
    # Lifecycle hooks
    "on_user_activated",
    "on_user_deactivated",
    "on_family_activated",
    "on_family_deactivated",
]
