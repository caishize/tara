"""
Scheduled Job Definition

Defines the configuration and behavior of scheduled jobs.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any, Awaitable
from datetime import datetime

from ..utils.timezone import utc_now
from .execution import JobPriority


@dataclass
class ScheduledJob:
    """
    Configuration for a scheduled job.

    Attributes:
        name: Unique name for the job within its scheduler
        func: Async function to execute
        description: Human-readable description of the job
        priority: Execution priority (HIGH, NORMAL, LOW)
        timeout_seconds: Maximum execution time before timeout
        max_retries: Maximum number of retry attempts on failure
        retry_delay_seconds: Base delay between retries
        enabled: Whether the job is enabled for scheduling
        depends_on: List of job names that must complete before this job
        tags: Optional tags for categorization
    """
    name: str
    func: Callable[..., Awaitable[Dict[str, Any]]]
    description: str = ""
    priority: JobPriority = JobPriority.NORMAL
    timeout_seconds: int = 300  # 5 minutes default
    max_retries: int = 3
    retry_delay_seconds: int = 60
    enabled: bool = True
    depends_on: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # Runtime state (not persisted)
    last_run: Optional[datetime] = field(default=None, compare=False)
    last_status: Optional[str] = field(default=None, compare=False)
    next_run: Optional[datetime] = field(default=None, compare=False)
    consecutive_failures: int = field(default=0, compare=False)

    def __post_init__(self):
        """Validate job configuration."""
        if not self.name:
            raise ValueError("Job name cannot be empty")
        if not callable(self.func):
            raise ValueError(f"Job func must be callable, got {type(self.func)}")
        if self.timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {self.timeout_seconds}")
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be non-negative, got {self.max_retries}")
        if self.retry_delay_seconds < 0:
            raise ValueError(f"retry_delay_seconds must be non-negative, got {self.retry_delay_seconds}")

    def record_success(self) -> None:
        """Record a successful execution."""
        self.last_run = utc_now()
        self.last_status = "completed"
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        """Record a failed execution."""
        self.last_run = utc_now()
        self.last_status = "failed"
        self.consecutive_failures += 1

    def should_retry(self) -> bool:
        """Check if the job should be retried after failure."""
        return self.consecutive_failures < self.max_retries

    def get_retry_delay(self) -> int:
        """Get the delay before the next retry (with exponential backoff)."""
        # Exponential backoff: base_delay * 2^(failure_count - 1)
        return self.retry_delay_seconds * (2 ** max(0, self.consecutive_failures - 1))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization (excludes func)."""
        return {
            "name": self.name,
            "description": self.description,
            "priority": self.priority.value,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "enabled": self.enabled,
            "depends_on": self.depends_on,
            "tags": self.tags,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_status": self.last_status,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "consecutive_failures": self.consecutive_failures,
        }


@dataclass
class CronJob(ScheduledJob):
    """
    A job that runs on a cron schedule.

    Additional Attributes:
        cron_expression: Cron expression defining the schedule
    """
    cron_expression: str = "0 * * * *"  # Default: every hour

    def __post_init__(self):
        """Validate cron job configuration."""
        super().__post_init__()
        # Basic validation - croniter will do full validation when used
        if not self.cron_expression:
            raise ValueError("cron_expression cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = super().to_dict()
        result["cron_expression"] = self.cron_expression
        return result
