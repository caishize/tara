"""
Job Execution Models

Defines the data structures for tracking job executions.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Any
from uuid import UUID, uuid4

from ..utils.timezone import utc_now


class JobExecutionStatus(str, Enum):
    """Status of a job execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TriggerType(str, Enum):
    """How the job execution was triggered."""
    SCHEDULED = "scheduled"  # Triggered by scheduler
    MANUAL = "manual"  # Triggered manually via API


class JobPriority(str, Enum):
    """Priority level for job execution."""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

    def __lt__(self, other):
        """Compare priorities for sorting."""
        if not isinstance(other, JobPriority):
            return NotImplemented
        priority_order = {JobPriority.HIGH: 0, JobPriority.NORMAL: 1, JobPriority.LOW: 2}
        return priority_order[self] < priority_order[other]


@dataclass
class JobExecution:
    """
    Represents a single execution of a scheduled job.

    Attributes:
        id: Unique identifier for this execution
        job_name: Name of the job that was executed
        scheduler_name: Name of the scheduler that ran this job
        status: Current status of the execution
        trigger_type: How the execution was triggered
        started_at: When the execution started
        completed_at: When the execution completed
        duration_ms: How long the execution took in milliseconds
        error_message: Error message if failed
        error_traceback: Full traceback if failed
        result_summary: Summary of the execution result (JSON-serializable)
        created_at: When this record was created
    """
    job_name: str
    scheduler_name: str
    status: JobExecutionStatus = JobExecutionStatus.PENDING
    trigger_type: TriggerType = TriggerType.SCHEDULED
    id: UUID = field(default_factory=uuid4)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=utc_now)

    def start(self) -> None:
        """Mark the execution as started."""
        self.status = JobExecutionStatus.RUNNING
        self.started_at = utc_now()

    def complete(self, result_summary: Optional[Dict[str, Any]] = None) -> None:
        """Mark the execution as completed successfully."""
        self.status = JobExecutionStatus.COMPLETED
        self.completed_at = utc_now()
        self.result_summary = result_summary
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)

    def fail(self, error_message: str, error_traceback: Optional[str] = None) -> None:
        """Mark the execution as failed."""
        self.status = JobExecutionStatus.FAILED
        self.completed_at = utc_now()
        self.error_message = error_message
        self.error_traceback = error_traceback
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)

    def cancel(self) -> None:
        """Mark the execution as cancelled."""
        self.status = JobExecutionStatus.CANCELLED
        self.completed_at = utc_now()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)

    def timeout(self) -> None:
        """Mark the execution as timed out."""
        self.status = JobExecutionStatus.TIMEOUT
        self.completed_at = utc_now()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "job_name": self.job_name,
            "scheduler_name": self.scheduler_name,
            "status": self.status.value,
            "trigger_type": self.trigger_type.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "result_summary": self.result_summary,
            "created_at": self.created_at.isoformat(),
        }
